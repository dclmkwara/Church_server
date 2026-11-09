"""Server-enforced, auditable edits for submitted count records."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4, uuid5

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.filters import scope_filter

from app.models.counts import Count, SubmissionEditRevision
from app.services.analytics.program_config import (
    SUBMISSION_EDIT_WINDOW_HOURS, SUBMISSION_MAX_EDITS,
    SUBMISSION_RETURN_EXTRA_EDITS,
)
from app.api import deps

COUNT_FIELDS = {"total", "adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls", "note", "count_mode", "section_label"}


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if value is not None and value.__class__.__name__ == "Decimal":
        return str(value)
    return value


async def edit_own_submission(
    db: AsyncSession, *, model: Any, submission_type: str, submission_id: UUID,
    edit_id: UUID, base_revision: int, values: dict[str, Any], actor: Any,
    allowed_fields: set[str], approval_locks: bool = False,
) -> dict[str, Any]:
    """Apply an owner edit under a row lock and append its idempotent revision."""
    row = (await db.execute(select(model).where(model.id == submission_id).with_for_update())).scalar_one_or_none()
    if row is None or getattr(row, "is_deleted", False):
        raise HTTPException(404, "Submission not found")
    deps.ensure_path_in_scope(actor, row.path, detail="Submission outside your scope")
    if str(row.entered_by_id) != str(actor.user_id):
        raise HTTPException(403, "Only the original submitter can edit this submission")
    if not values or set(values) - allowed_fields:
        raise HTTPException(422, "The edit contains unsupported fields")
    revisions = list((await db.execute(select(SubmissionEditRevision).where(
        SubmissionEditRevision.submission_type == submission_type,
        SubmissionEditRevision.submission_id == row.id,
    ).order_by(SubmissionEditRevision.revision_no))).scalars().all())
    existing = next((item for item in revisions if item.edit_id == edit_id), None)
    if existing:
        return {"id": str(row.id), "revision": existing.revision_no, "duplicate": True}
    latest = revisions[-1].revision_no if revisions else 0
    if latest != base_revision:
        raise HTTPException(409, detail={"code": "stale_revision", "current_revision": latest})
    last_return = next((item for item in reversed(revisions) if item.action == "returned"), None)
    now = datetime.now(timezone.utc)
    opened = last_return.created_at if last_return else row.created_at
    if opened is None or now > opened + timedelta(hours=SUBMISSION_EDIT_WINDOW_HOURS):
        raise HTTPException(409, "The 24-hour edit window has closed. The change was not applied.")
    edits = sum(item.action == "edit" for item in revisions)
    limit = SUBMISSION_MAX_EDITS + (SUBMISSION_RETURN_EXTRA_EDITS if last_return else 0)
    if edits >= limit:
        raise HTTPException(409, "The edit limit has been reached. The change was not applied.")
    status_value = str(getattr(row, "status", "")).lower()
    if approval_locks and status_value == "approved":
        raise HTTPException(409, "Approval locked this submission. Ask the accepting pastor to return it for correction.")
    before = {key: _json_value(getattr(row, key, None)) for key in values}
    if submission_type == "worker_attendance":
        from app.models.attendance import WorkerAttendance
        from app.models.user import Worker
        supplied = values.get("present_workers")
        if supplied is not None:
            if not isinstance(supplied, list):
                raise HTTPException(422, "present_workers must be a list of worker IDs")
            selected_ids = [str(item) for item in supplied]
            if len(selected_ids) != len(set(selected_ids)):
                raise HTTPException(422, "A worker can appear only once in the submitted attendance")
            expected_ids = {str(item) for item in (row.expected_worker_ids or [])}
            if not set(selected_ids).issubset(expected_ids):
                raise HTTPException(422, "Attendance edits must use the roster captured for this meeting")
            selected_uuids = [UUID(item) for item in selected_ids]
            workers = list((await db.execute(select(Worker).where(
                Worker.worker_id.in_(selected_uuids), Worker.is_deleted.is_(False),
                scope_filter(Worker.path, str(row.path)),
            ))).scalars().all()) if selected_uuids else []
            worker_by_id = {str(worker.worker_id): worker for worker in workers}
            if set(selected_ids) != set(worker_by_id):
                raise HTTPException(409, "A worker from this captured roster is no longer available; contact your pastor.")
            linked_rows = list((await db.execute(select(WorkerAttendance).where(
                WorkerAttendance.submission_id == row.id,
                WorkerAttendance.is_deleted.is_(False),
            ).with_for_update())).scalars().all())
            linked_by_worker = {str(item.worker_id): item for item in linked_rows}
            for worker_id, linked in linked_by_worker.items():
                linked.status = "present" if worker_id in selected_ids else "absent"
            present_snapshot = []
            for worker_id in selected_ids:
                worker = worker_by_id[worker_id]
                present_snapshot.append({"worker_id": worker_id, "worker_name": worker.name})
                if worker_id not in linked_by_worker:
                    db.add(WorkerAttendance(
                        submission_id=row.id, client_id=uuid5(row.client_id, worker_id),
                        path=str(worker.path), program_scope_path=str(row.program_scope_path or row.path),
                        location_id=worker.location_id, event_id=row.event_id, assignment_id=row.assignment_id,
                        date=row.date, church_type=worker.church_type, program_level=row.program_level,
                        program_domain_id=row.program_domain_id, program_type_id=row.program_type_id,
                        program_domain=row.program_domain, program_type=row.program_type,
                        worker_id=worker.worker_id, worker_name=worker.name, worker_phone=worker.phone,
                        worker_unit=worker.unit, status="present", entered_by_id=actor.user_id,
                    ))
            row.present_workers = present_snapshot
            row.present_count = len(present_snapshot)
            values["present_workers"] = selected_ids
            values["present_count"] = row.present_count
        if "note" in values:
            row.note = values["note"]
    elif submission_type in {"fellowship_attendance", "fellowship_offering"}:
        from app.models.fellowship_activities import FellowshipAttendance
        if submission_type == "fellowship_attendance":
            for key in ("men", "women", "youths", "children"):
                if key in values:
                    value = values[key]
                    if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 999999:
                        raise HTTPException(422, f"{key} must be a whole number from 0 to 999999")
            for key, value in values.items():
                setattr(row, key, value.strip() or None if key in {"topic", "note"} and isinstance(value, str) else value)
            row.total = sum(int(getattr(row, key, 0) or 0) for key in ("men", "women", "youths", "children"))
        else:
            amount = values.get("amount")
            if amount is not None:
                try:
                    amount = float(amount)
                except (TypeError, ValueError):
                    raise HTTPException(422, "Offering amount must be a positive number")
                if amount <= 0 or amount > 9999999999.99:
                    raise HTTPException(422, "Offering amount must be greater than zero")
                row.amount = amount
            if "note" in values:
                row.note = values["note"]
    else:
        for key, value in values.items():
            setattr(row, key, value)
    if status_value == "returned":
        row.status = "corrected" if hasattr(row, "status") else row.status
    if submission_type == "fellowship_attendance":
        row.total = sum(int(getattr(row, key, 0) or 0) for key in ("men", "women", "youths", "children"))
    db.add(SubmissionEditRevision(
        submission_type=submission_type, submission_id=row.id, edit_id=edit_id,
        revision_no=latest + 1, action="edit", editor_id=actor.user_id,
        before_values=before, after_values={key: _json_value(getattr(row, key, None)) for key in values},
    ))
    await db.commit()
    return {"id": str(row.id), "revision": latest + 1, "duplicate": False, "edited_at": now.isoformat()}


async def edit_count_submission(
    db: AsyncSession, *, count_id: UUID, edit_id: UUID,
    base_revision: int, values: dict[str, Any], actor: Any,
) -> dict[str, Any]:
    row = (await db.execute(select(Count).where(Count.id == count_id).with_for_update())).scalar_one_or_none()
    if row is None or row.is_deleted:
        raise HTTPException(404, "Count submission not found")
    deps.ensure_path_in_scope(actor, row.path, detail="Count submission outside your scope")
    if str(row.entered_by_id) != str(actor.user_id):
        raise HTTPException(403, "Only the original submitter can edit this count")
    if not values or set(values) - COUNT_FIELDS:
        raise HTTPException(422, "The edit contains unsupported fields")
    if "count_mode" in values and values["count_mode"] != row.count_mode:
        raise HTTPException(422, "The reporting mode cannot be changed after submission")
    existing = (await db.execute(select(SubmissionEditRevision).where(
        SubmissionEditRevision.submission_type == "count",
        SubmissionEditRevision.submission_id == row.id,
        SubmissionEditRevision.edit_id == edit_id,
    ))).scalar_one_or_none()
    if existing is not None:
        return {"id": str(row.id), "status": row.status, "revision": existing.revision_no, "duplicate": True}
    revisions = list((await db.execute(select(SubmissionEditRevision).where(
        SubmissionEditRevision.submission_type == "count",
        SubmissionEditRevision.submission_id == row.id,
    ).order_by(SubmissionEditRevision.revision_no))).scalars().all())
    latest_revision = revisions[-1].revision_no if revisions else 0
    if base_revision != latest_revision:
        raise HTTPException(409, detail={"code": "stale_revision", "current_revision": latest_revision})
    if str(row.status).lower() in {"approved", "rejected"}:
        raise HTTPException(409, "Approved or rejected submissions are locked")
    last_return = next((rev for rev in reversed(revisions) if rev.action == "returned"), None)
    opened_at = last_return.created_at if last_return else row.created_at
    now = datetime.now(timezone.utc)
    if opened_at is None or now > opened_at + timedelta(hours=SUBMISSION_EDIT_WINDOW_HOURS):
        raise HTTPException(409, "The 24-hour edit window has closed. Ask the accepting pastor to return it for correction.")
    edits_total = sum(1 for rev in revisions if rev.action == "edit")
    limit = SUBMISSION_MAX_EDITS + (SUBMISSION_RETURN_EXTRA_EDITS if last_return else 0)
    if edits_total >= limit:
        raise HTTPException(409, "The edit limit has been reached. Ask the accepting pastor to return it for correction.")
    if values.get("count_mode") == "section" and not str(values.get("section_label") or row.section_label or "").strip():
        raise HTTPException(422, "Section counts require a label")
    if values.get("count_mode") == "single" and str(values.get("section_label") or "").strip():
        raise HTTPException(422, "Single counts cannot include a section label")
    before = {key: _json_value(getattr(row, key)) for key in values}
    for key, value in values.items():
        if key in {"total", "adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls"}:
            if not isinstance(value, int) or isinstance(value, bool) or value < 0 or value > 999999:
                raise HTTPException(422, f"{key} must be a whole number from 0 to 999999")
        setattr(row, key, value.strip() or None if key in {"note", "section_label"} and isinstance(value, str) else value)
    category_fields = {"adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls"}
    if category_fields & set(values):
        row.calculate_total()
        if "total" in values and row.total != values["total"]:
            raise HTTPException(422, "Total must match the demographic breakdown")
    elif "total" in values:
        row.total = values["total"]
    if row.status == "returned":
        row.status = "pending"
    revision_no = latest_revision + 1
    revision = SubmissionEditRevision(
        submission_type="count", submission_id=row.id, edit_id=edit_id,
        revision_no=revision_no, action="edit", editor_id=actor.user_id,
        before_values=before,
        after_values={key: _json_value(getattr(row, key)) for key in values},
    )
    db.add(revision)
    await db.commit()
    return {"id": str(row.id), "status": row.status, "revision": revision_no, "duplicate": False, "edited_at": now.isoformat()}


async def return_count_for_correction(
    db: AsyncSession, *, rows: list[Count], actor: Any, reason: str,
) -> list[str]:
    clean_reason = reason.strip()
    if not clean_reason:
        raise HTTPException(422, "A correction reason is required")
    locked_rows = list((await db.execute(select(Count).where(
        Count.id.in_([row.id for row in rows]),
    ).with_for_update())).scalars().all()) if rows else []
    for row in locked_rows:
        revision_rows = list((await db.execute(select(SubmissionEditRevision).where(
            SubmissionEditRevision.submission_type == "count",
            SubmissionEditRevision.submission_id == row.id,
        ).order_by(SubmissionEditRevision.revision_no))).scalars().all())
        revision_no = revision_rows[-1].revision_no + 1 if revision_rows else 1
        db.add(SubmissionEditRevision(
            submission_type="count", submission_id=row.id, edit_id=uuid4(),
            revision_no=revision_no, action="returned", editor_id=actor.user_id,
            before_values={"status": row.status}, after_values={"status": "returned"}, reason=clean_reason,
        ))
        row.status = "returned"
    return [str(row.id) for row in locked_rows]
