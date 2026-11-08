"""Unique-worker reporting for recurring and combined meetings."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.filters import scope_filter, scope_or_ancestor_filter
from app.models.attendance import WorkerAttendance, WorkerAttendanceSubmission
from app.models.programs import ProgramEvent, ProgramType
from app.models.user import Worker


def _day(value: Any) -> str:
    return (value.date() if isinstance(value, datetime) else value).isoformat()


def _meeting_key(event_id: Any, day: str, type_id: Any, type_slug: str, scope_path: Any) -> tuple[str, str, str, str]:
    return (str(event_id or ""), day, str(type_id or type_slug), str(scope_path or ""))


async def worker_meeting_analytics(
    db: AsyncSession,
    scope_path: str,
    *,
    location_id: str | None = None,
    program_type_slug: str | None = None,
) -> dict[str, Any]:
    """Deduplicate roster and present IDs per meeting, crediting home locations.

    New submissions carry the complete roster IDs. For legacy rows, the largest
    captured roster count is used once per meeting and marked as a legacy
    estimate; old rows cannot identify which ushers saw the same worker.
    """
    sub_type = aliased(ProgramType)
    sub_event = aliased(ProgramEvent)
    sub_event_type = aliased(ProgramType)
    sub_slug = func.coalesce(
        sub_type.slug, sub_event_type.slug,
        func.replace(func.lower(WorkerAttendanceSubmission.program_type), " ", "_"),
    )
    sub_type_id = func.coalesce(sub_type.id, sub_event_type.id)
    sub_scope = func.coalesce(
        cast(WorkerAttendanceSubmission.program_scope_path, String),
        cast(WorkerAttendanceSubmission.path, String),
    )
    sub_query = (
        select(WorkerAttendanceSubmission, sub_slug.label("type_slug"), sub_type.name.label("type_name"), sub_type_id.label("type_id"), sub_scope.label("meeting_scope"))
        .outerjoin(sub_type, WorkerAttendanceSubmission.program_type_id == sub_type.id)
        .outerjoin(sub_event, WorkerAttendanceSubmission.event_id == sub_event.id)
        .outerjoin(sub_event_type, sub_event.program_type_id == sub_event_type.id)
        .where(
            scope_or_ancestor_filter(sub_scope, scope_path),
            WorkerAttendanceSubmission.is_deleted.is_(False),
            *(([sub_slug == program_type_slug]) if program_type_slug else []),
        )
    )
    submission_rows = (await db.execute(sub_query)).all()

    expected_ids: set[UUID] = set()
    for submission, *_ in submission_rows:
        if submission.expected_worker_ids:
            for raw_id in submission.expected_worker_ids:
                try:
                    expected_ids.add(UUID(str(raw_id)))
                except (TypeError, ValueError):
                    continue
    eligible_workers: set[str] = set()
    if expected_ids:
        worker_query = select(Worker.worker_id).where(
            Worker.worker_id.in_(expected_ids),
            scope_filter(Worker.path, scope_path),
            Worker.is_deleted.is_(False),
        )
        if location_id:
            worker_query = worker_query.where(Worker.location_id == location_id)
        eligible_workers = {str(worker_id) for worker_id in (await db.execute(worker_query)).scalars().all()}

    attendance_type = aliased(ProgramType)
    attendance_event = aliased(ProgramEvent)
    attendance_event_type = aliased(ProgramType)
    attendance_slug = func.coalesce(
        attendance_type.slug, attendance_event_type.slug,
        func.replace(func.lower(WorkerAttendance.program_type), " ", "_"),
    )
    attendance_type_id = func.coalesce(attendance_type.id, attendance_event_type.id)
    attendance_scope = func.coalesce(
        cast(WorkerAttendance.program_scope_path, String),
        cast(WorkerAttendance.path, String),
    )
    attendance_query = (
        select(
            WorkerAttendance.worker_id, WorkerAttendance.event_id, WorkerAttendance.date,
            WorkerAttendance.status, attendance_slug.label("type_slug"),
            attendance_type.name.label("type_name"), attendance_type_id.label("type_id"),
            attendance_scope.label("meeting_scope"),
        )
        .outerjoin(attendance_type, WorkerAttendance.program_type_id == attendance_type.id)
        .outerjoin(attendance_event, WorkerAttendance.event_id == attendance_event.id)
        .outerjoin(attendance_event_type, attendance_event.program_type_id == attendance_event_type.id)
        .where(
            scope_filter(WorkerAttendance.path, scope_path),
            WorkerAttendance.is_deleted.is_(False),
            *(([WorkerAttendance.location_id == location_id]) if location_id else []),
            *(([attendance_slug == program_type_slug]) if program_type_slug else []),
        )
    )
    attendance_rows = (await db.execute(attendance_query)).all()

    meetings: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for submission, type_slug, type_name, type_id, meeting_scope in submission_rows:
        day = _day(submission.date)
        slug = str(type_slug or "unknown")
        key = _meeting_key(submission.event_id, day, type_id, slug, meeting_scope)
        meeting = meetings.setdefault(key, {
            "day": day, "type_slug": slug, "type_name": str(type_name or submission.program_type),
            "scope": str(meeting_scope or ""), "expected_ids": set(), "has_roster_ids": False,
            "legacy_expected": 0, "workers": defaultdict(set),
        })
        if submission.expected_worker_ids is not None:
            meeting["has_roster_ids"] = True
            for raw_id in submission.expected_worker_ids or []:
                worker_key = str(raw_id)
                if worker_key in eligible_workers:
                    meeting["expected_ids"].add(worker_key)
        else:
            meeting["legacy_expected"] = max(meeting["legacy_expected"], int(submission.expected_workers_count or 0))

    for row in attendance_rows:
        day = _day(row.date)
        slug = str(row.type_slug or "unknown")
        key = _meeting_key(row.event_id, day, row.type_id, slug, row.meeting_scope)
        meeting = meetings.setdefault(key, {
            "day": day, "type_slug": slug, "type_name": str(row.type_name or slug.replace("_", " ").title()),
            "scope": str(row.meeting_scope or ""), "expected_ids": set(), "has_roster_ids": False,
            "legacy_expected": 0, "workers": defaultdict(set),
        })
        meeting["workers"][str(row.worker_id)].add(str(row.status or "").lower())

    # Do not allocate a legacy group/region roster count to one Location: its
    # old submission contains no IDs with which to identify the home-location share.
    for key, meeting in meetings.items():
        if not meeting["has_roster_ids"] and meeting["scope"] and not (
            meeting["scope"] == scope_path or meeting["scope"].startswith(scope_path + ".")
        ):
            meeting["legacy_expected"] = 0

    by_type: dict[str, dict[str, Any]] = {}
    by_month: dict[tuple[str, str], dict[str, int]] = {}
    for meeting in meetings.values():
        expected = len(meeting["expected_ids"]) if meeting["has_roster_ids"] else meeting["legacy_expected"]
        statuses = meeting["workers"].values()
        present = late = explicit_absent = excused = 0
        for values in statuses:
            if "present" in values:
                present += 1
            elif "late" in values:
                late += 1
            elif "excused" in values:
                excused += 1
            elif "absent" in values:
                explicit_absent += 1
        absent = max(explicit_absent, expected - present - late - excused, 0)
        type_row = by_type.setdefault(meeting["type_slug"], {
            "program_type": meeting["type_slug"], "label": meeting["type_name"],
            "present": 0, "late": 0, "absent": 0, "excused": 0, "expected": 0,
            "meetings": 0, "records": 0, "legacy_roster_meetings": 0,
        })
        for name, value in (("present", present), ("late", late), ("absent", absent), ("excused", excused), ("expected", expected)):
            type_row[name] += value
        type_row["meetings"] += 1
        type_row["records"] += len(meeting["workers"])
        type_row["legacy_roster_meetings"] += int(not meeting["has_roster_ids"])
        month = meeting["day"][:7]
        trend = by_month.setdefault((meeting["type_slug"], month), {"present": 0, "late": 0, "absent": 0, "excused": 0, "expected": 0, "meetings": 0})
        for name, value in (("present", present), ("late", late), ("absent", absent), ("excused", excused), ("expected", expected)):
            trend[name] += value
        trend["meetings"] += 1

    ranking = []
    for row in by_type.values():
        row["attendance_rate"] = round((row["present"] + row["late"]) * 100 / row["expected"], 1) if row["expected"] else None
        ranking.append(row)
    ranking.sort(key=lambda row: ((row["present"] + row["late"]), row["meetings"]), reverse=True)
    selected_slug = program_type_slug or (ranking[0]["program_type"] if ranking else "")
    monthly = [
        {"period": month, **values,
         "attendance_rate": round((values["present"] + values["late"]) * 100 / values["expected"], 1) if values["expected"] else None}
        for (slug, month), values in sorted(by_month.items()) if slug == selected_slug
    ]
    selected = next((row for row in ranking if row["program_type"] == selected_slug), None)
    return {"ranking": ranking, "monthly_trend": monthly, "summary": selected, "deduplicated": True}
