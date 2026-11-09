"""
Count submission and retrieval routes.

Handles population count data collection with offline sync support.
"""
from typing import Any, List, Optional
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, or_, and_
from sqlalchemy.orm import aliased
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo

from app.api import deps
from app.db.filters import ltree_subpath as _ltree_subpath
from app.db.filters import scope_filter as _scope_filter
from app.crud.crud_counts import count as crud_count
from app.schemas.counts import CountCreate, CountEditRequest, CountReturnRequest, CountResponse, CountUpdate, CountGroupCloseRequest, CountGroupResolveRequest, CountSectionSuggestionInput
from app.schemas.sync import SyncResult
from app.services.statistics_service import StatisticsService
from app.models.user import User, Role, Worker, user_roles
from app.models.counts import Count, CountGroup, CountSectionSuggestion, CountReminderRecipient, SubmissionEditRevision
from app.models.programs import ProgramCampaign, ProgramEvent, ProgramType, ProgramDomain
from app.models.location import Location
from app.db.filters import scope_filter
from app.db.filters import scope_or_ancestor_filter
from app.services.analytics.program_config import (
    PENDING_ACCEPTOR_ALERT_HOURS, PENDING_NEXT_LEVEL_ALERT_HOURS,
    MISSING_HOURS_AFTER_OCCURRENCE,
    SUBMISSION_EDIT_WINDOW_HOURS, SUBMISSION_MAX_EDITS, SUBMISSION_RETURN_EXTRA_EDITS,
)
from app.utils.count_sections import legacy_section_label
from app.services.submission_editing import edit_count_submission, return_count_for_correction
from app.utils.count_groups import missing_suggested_labels, count_group_is_past_deadline
from app.core import analytics_cache

router = APIRouter()
_LAGOS = ZoneInfo("Africa/Lagos")
COUNT_PENDING = "pending"
COUNT_APPROVED = "approved"
COUNT_REJECTED = "rejected"


class CountRejection(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)


class CountReminder(BaseModel):
    location_id: UUID
    program_type_id: int
    occurrence_date: date


def _count_reminder_recipient_query(location: Location):
    """Only active, approved usher/pastor accounts at this exact location."""
    return (
        select(User.user_id)
        .join(user_roles, user_roles.c.user_id == User.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(
            User.path == location.path,
            User.is_active.is_(True),
            User.approval_status == "approved",
            User.is_deleted.is_(False),
            Role.is_deleted.is_(False),
            Role.role_name.in_(("Location Usher", "Location Pastor")),
        )
        .distinct()
    )


def _path_covers(scope_path: str | None, descendant_path: str) -> bool:
    scope = str(scope_path or "").strip(".").lower()
    descendant = str(descendant_path or "").strip(".").lower()
    return bool(scope) and (scope == descendant or descendant.startswith(scope + "."))


def _acceptor_score(program_level: str | None) -> int | None:
    return {"local": 3, "location": 3, "group": 4, "region": 5}.get(str(program_level or "").lower())


def _calendar_date(value: datetime | date) -> date:
    if isinstance(value, datetime):
        value = value.astimezone(_LAGOS) if value.tzinfo else value.replace(tzinfo=_LAGOS)
        return value.date()
    return value


def _count_group_key(row: Count) -> tuple:
    if row.count_group_id:
        return ("group", str(row.count_group_id))
    program_key = ("id", row.program_type_id) if row.program_type_id is not None else ("legacy", (row.program_type or "").strip().lower())
    # New submissions use count_group_id; this fallback is for legacy rows and
    # retains event identity so separate scheduled sessions cannot merge.
    return (str(row.location_id), program_key, _calendar_date(row.date), str(row.event_id or "none"))


def _split_count_conflict(rows: list[Count]) -> bool:
    modes = {str(row.count_mode).lower() for row in rows if row.count_mode}
    split_statuses = {str(row.status).lower() for row in rows if row.count_mode}
    return (
        len(modes) > 1
        or ("single" in modes and sum(1 for row in rows if row.count_mode == "single") > 1)
        or (bool(modes) and len(split_statuses) > 1)
    )


async def _rows_for_group(db: AsyncSession, base: Count, *, pending_only: bool = False) -> list[Count]:
    if base.count_group_id:
        filters = [
            Count.count_group_id == base.count_group_id,
            Count.is_deleted.is_(False),
            Count.status.in_([COUNT_PENDING, COUNT_APPROVED]),
        ]
        if pending_only:
            filters.append(Count.status == COUNT_PENDING)
        return list((await db.execute(select(Count).where(*filters).order_by(Count.created_at, Count.id))).scalars().all())
    occurrence = _calendar_date(base.date)
    start = datetime.combine(occurrence, time.min, _LAGOS).astimezone(timezone.utc)
    end = datetime.combine(occurrence + timedelta(days=1), time.min, _LAGOS).astimezone(timezone.utc)
    filters = [
        Count.location_id == base.location_id,
        Count.date >= start,
        Count.date < end,
        Count.is_deleted.is_(False),
        Count.status.in_([COUNT_PENDING, COUNT_APPROVED]),
    ]
    if base.program_type_id is not None:
        filters.append(Count.program_type_id == base.program_type_id)
    else:
        filters.append(func.lower(func.trim(func.coalesce(Count.program_type, ""))) == (base.program_type or "").strip().lower())
    if pending_only:
        filters.append(Count.status == "pending")
    result = await db.execute(select(Count).where(*filters).order_by(Count.created_at, Count.id))
    return list(result.scalars().all())


def _review_group_payload(
    rows: list[Count], *, now: datetime, score: int,
    location_by_id: dict[str, Location], program_by_id: dict[int, ProgramType],
    event_by_id: dict[str, ProgramEvent], submitter_names: dict[str, str],
    history_by_id: dict[str, Count],
    group_by_id: dict[str, CountGroup],
) -> dict[str, Any]:
    base = rows[0]
    location = location_by_id.get(str(base.location_id))
    program_type_row = program_by_id.get(base.program_type_id) if base.program_type_id is not None else None
    event = event_by_id.get(str(base.event_id)) if base.event_id else None
    pending_rows = [row for row in rows if str(row.status).lower() == COUNT_PENDING]
    earliest = min((row.created_at for row in pending_rows if row.created_at), default=now)
    age_hours = max(0, (now - earliest).total_seconds() / 3600)
    expected_score = _acceptor_score(base.program_level)
    section_labels = set()
    modes = {str(row.count_mode).lower() for row in rows if row.count_mode}
    split_conflict = _split_count_conflict(rows)
    group = group_by_id.get(str(base.count_group_id)) if base.count_group_id else None
    labels = [str(row.section_label or "").strip().casefold() for row in rows if row.count_mode == "section"]
    split_conflict = split_conflict or len(labels) != len(set(labels)) or bool(group and group.state == "conflict")
    awaiting_close = bool(group and group.count_mode == "section" and group.state == "open")
    correction_history = []
    for row in rows:
        section_label = row.section_label or legacy_section_label(row.note)
        if section_label:
            section_labels.add(section_label)
        prior = history_by_id.get(str(row.supersedes_id)) if row.supersedes_id else None
        if prior and not prior.is_deleted:
            correction_history.append({
                "supersedes_id": str(prior.id), "status": prior.status,
                "rejection_reason": prior.rejection_reason or "",
                "rejected_at": prior.rejected_at.isoformat() if prior.rejected_at else "",
                "rejected_by_id": str(prior.rejected_by_id or ""),
            })
    return {
        "count_id": str(base.id), "count_group_id": str(base.count_group_id or ""), "group_key": list(_count_group_key(base)),
        "service_id": group.service_id if group else "legacy",
        "location_id": str(base.location_id), "program_type_id": base.program_type_id,
        "program_type": base.program_type or (program_type_row.name if program_type_row else "Unclassified program"),
        "event_title": (event.title if event and event.title else "") or "", "location": location.location_name if location else str(base.location_id),
        "program_level": base.program_level or "Local",
        "program_scope_path": str(base.program_scope_path or base.path), "event_id": str(base.event_id or ""),
        "date": _calendar_date(base.date).isoformat(), "total": None if split_conflict else sum(int(row.total or 0) for row in pending_rows),
        "categories": None if split_conflict else {field: sum(int(getattr(row, field, 0) or 0) for row in pending_rows) for field in ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")},
        "submission_count": len(pending_rows), "section_count": sum(1 for row in rows if row.count_mode == "section") or (len(section_labels) if section_labels else len(rows)),
        "section_labels": sorted(section_labels), "sections_recorded": bool(section_labels),
        "split_count": bool(modes), "mode_recorded": bool(modes), "group_state": "conflict" if split_conflict else (group.state if group else "open"),
        "auto_closed": bool(group and group.auto_closed_at), "close_reason": group.close_reason if group else None,
        "parts": [{"count_id": str(row.id), "section_label": row.section_label, "count_mode": row.count_mode,
                   "total": int(row.total or 0), "status": str(row.status).lower(), "submitter_id": str(row.entered_by_id)}
                  for row in sorted((item for item in rows if not item.is_deleted), key=lambda item: (str(item.section_label or "").casefold(), str(item.id)))],
        "submitters": sorted({submitter_names.get(str(row.entered_by_id), str(row.entered_by_id)) for row in rows}),
        "correction_history": correction_history,
        "age_hours": round(age_hours, 1),
        "flag_10h": age_hours >= PENDING_ACCEPTOR_ALERT_HOURS,
        "flag_24h": age_hours >= PENDING_NEXT_LEVEL_ALERT_HOURS,
        "actionable": score == expected_score and not split_conflict and not awaiting_close,
        "awaiting_close": awaiting_close,
        "group_conflict": split_conflict,
        "escalated": expected_score is not None and score == expected_score + 1 and age_hours >= PENDING_NEXT_LEVEL_ALERT_HOURS,
        "auto_accepted": all(bool(row.auto_accepted) for row in rows),
        "row_ids": [str(row.id) for row in rows],
    }


@router.post(
    "/",
    response_model=CountResponse,
    dependencies=[Depends(deps.PermissionChecker("counts:create"))],
)
async def create_count(
    *,
    db: AsyncSession = Depends(deps.get_db),
    count_in: CountCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Submit a new population count.
    
    Supports offline sync via client_id for idempotency.
    If a count with the same client_id already exists, returns the existing record.
    """
    if not count_in.assignment_id:
        await deps.get_location_in_scope(
            db,
            current_user=current_user,
            location_id=count_in.location_id,
            detail="Count location outside your scope",
        )
    created = await crud_count.create(
        db,
        obj_in=count_in,
        user_id=current_user.user_id,
        require_assignment=deps.highest_role_score(current_user) == 1,
    )
    if not count_in.assignment_id:
        deps.ensure_path_in_scope(current_user, created.path, detail="Existing count is outside your scope")
    await _broadcast_event("count_created", {"id": str(created.id), "location_id": created.location_id})
    return created


async def _broadcast_event(event_type: str, payload: dict) -> None:
    try:
        from app.api.v1.routes.websocket import manager
        import json
        await manager.broadcast(json.dumps({"type": event_type, "data": payload}))
    except Exception:
        # Avoid failing request if broadcast fails
        pass


@router.get(
    "/",
    response_model=List[CountResponse],
    dependencies=[Depends(deps.PermissionChecker("counts:read"))],
)
async def read_counts(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """
    Retrieve counts with hierarchical scope filtering.
    """
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    
    rows = await crud_count.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )
    return deps.filter_rows_in_scope(rows, current_user)

@router.get(
    "/aggregate",
    dependencies=[Depends(deps.PermissionChecker("counts:read"))],
)
async def aggregate_counts(
    program_domain: Optional[str] = Query(None, description="Program domain name or slug"),
    program_type: Optional[str] = Query(None, description="Program type name or slug"),
    program_level: Optional[str] = Query(None, description="Program reporting level"),
    location_id: Optional[str] = Query(None, description="Filter by location id"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Aggregate counts within scope, grouped by location_id.
    """
    scope_path = deps.effective_scope_path(current_user)
    query = select(
        Count.location_id.label("location_id"),
        func.sum(Count.adult_male).label("adult_male"),
        func.sum(Count.adult_female).label("adult_female"),
        func.sum(Count.youth_male).label("youth_male"),
        func.sum(Count.youth_female).label("youth_female"),
        func.sum(Count.boys).label("boys"),
        func.sum(Count.girls).label("girls"),
        func.sum(Count.total).label("total"),
    ).where(
        deps.scope_condition(Count.path, current_user),
        Count.is_deleted == False
    )

    if start_date:
        query = query.where(Count.date >= start_date)
    if end_date:
        query = query.where(Count.date <= end_date)
    if location_id:
        query = query.where(Count.location_id == location_id)
    if program_level:
        query = query.where(Count.program_level == program_level)

    if program_domain or program_type:
        query = query.join(ProgramEvent, ProgramEvent.id == Count.event_id, isouter=True)
        query = query.join(ProgramType, or_(ProgramType.id == Count.program_type_id, ProgramType.id == ProgramEvent.program_type_id), isouter=True)
        query = query.join(ProgramDomain, or_(ProgramDomain.id == Count.program_domain_id, ProgramDomain.id == ProgramType.domain_id), isouter=True)
        if program_domain:
            query = query.where(or_(Count.program_domain == program_domain, ProgramDomain.name == program_domain, ProgramDomain.slug == program_domain))
        if program_type:
            query = query.where(or_(Count.program_type == program_type, ProgramType.name == program_type, ProgramType.slug == program_type))

    query = query.group_by(Count.location_id).order_by(Count.location_id)
    result = await db.execute(query)
    return [dict(row._mapping) for row in result.all()]


@router.get(
    "/aggregate-flex",
    dependencies=[Depends(deps.PermissionChecker("counts:read"))],
)
async def aggregate_counts_flexible(
    view_level: str = Query(..., description="state, region, group, location"),
    program_domain: Optional[str] = Query(None, description="Program domain name or slug"),
    program_type: Optional[str] = Query(None, description="Program type name or slug"),
    program_level: Optional[str] = Query(None, description="Program reporting level"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Aggregate counts by hierarchy level using ltree subpath grouping.
    """
    level_map = {
        "state": 3,
        "region": 4,
        "group": 5,
        "location": 6,
    }
    level_key = view_level.strip().lower()
    if level_key not in level_map:
        raise HTTPException(status_code=400, detail="Invalid view_level")

    scope_path = deps.effective_scope_path(current_user)
    segment_count = level_map[level_key]

    group_path = _ltree_subpath(Count.path, segment_count).label("group_path")

    query = select(
        group_path,
        func.sum(Count.adult_male).label("adult_male"),
        func.sum(Count.adult_female).label("adult_female"),
        func.sum(Count.youth_male).label("youth_male"),
        func.sum(Count.youth_female).label("youth_female"),
        func.sum(Count.boys).label("boys"),
        func.sum(Count.girls).label("girls"),
        func.sum(Count.total).label("total"),
    ).where(
        deps.scope_condition(Count.path, current_user),
        Count.is_deleted == False
    )

    if start_date:
        query = query.where(Count.date >= start_date)
    if end_date:
        query = query.where(Count.date <= end_date)
    if program_level:
        query = query.where(Count.program_level == program_level)

    if program_domain or program_type:
        query = query.join(ProgramEvent, ProgramEvent.id == Count.event_id, isouter=True)
        query = query.join(ProgramType, or_(ProgramType.id == Count.program_type_id, ProgramType.id == ProgramEvent.program_type_id), isouter=True)
        query = query.join(ProgramDomain, or_(ProgramDomain.id == Count.program_domain_id, ProgramDomain.id == ProgramType.domain_id), isouter=True)
        if program_domain:
            query = query.where(or_(Count.program_domain == program_domain, ProgramDomain.name == program_domain, ProgramDomain.slug == program_domain))
        if program_type:
            query = query.where(or_(Count.program_type == program_type, ProgramType.name == program_type, ProgramType.slug == program_type))

    query = query.group_by(group_path).order_by(group_path)
    result = await db.execute(query)
    return [dict(row._mapping) for row in result.all()]


@router.get("/review/groups", dependencies=[Depends(deps.PermissionChecker("counts:review"))])
async def list_count_review_groups(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List pending count groups for the acceptor and one overdue escalation tier."""
    score = deps.highest_role_score(current_user)
    scope_path = deps.effective_scope_path(current_user)
    prior_count = aliased(Count)
    result = await db.execute(
        select(
            Count, Location.location_name, Location.path, ProgramType.name,
            ProgramEvent.title, ProgramCampaign.title, User.name, prior_count,
        ).select_from(Count)
        .outerjoin(Location, Location.location_id == Count.location_id)
        .outerjoin(ProgramType, ProgramType.id == Count.program_type_id)
        .outerjoin(ProgramEvent, ProgramEvent.id == Count.event_id)
        .outerjoin(ProgramCampaign, ProgramCampaign.id == ProgramEvent.campaign_id)
        .outerjoin(User, User.user_id == Count.entered_by_id)
        .outerjoin(prior_count, prior_count.id == Count.supersedes_id)
        .where(
                scope_filter(Count.path, scope_path), Count.is_deleted.is_(False), Count.status.in_([COUNT_PENDING, COUNT_APPROVED])
        ).order_by(Count.created_at, Count.id)
    )
    review_rows = list(result.all())
    pending = [row[0] for row in review_rows if str(row[0].status).lower() == COUNT_PENDING]
    grouped: dict[tuple, list[Count]] = {}
    pending_group_keys = {_count_group_key(row) for row in pending}
    for row in (item[0] for item in review_rows):
        key = _count_group_key(row)
        if key in pending_group_keys:
            grouped.setdefault(key, []).append(row)
    await _auto_close_elapsed_groups(db, {row.count_group_id for rows in grouped.values() for row in rows if row.count_group_id})
    location_by_id = {}
    program_by_id = {}
    event_by_id = {}
    submitter_names = {}
    from types import SimpleNamespace
    history_by_id = {}
    for count_row, location_name, location_path, program_name, event_title, campaign_title, submitter_name, prior in review_rows:
        if count_row.location_id and location_name:
            location_by_id[str(count_row.location_id)] = SimpleNamespace(location_name=location_name, path=location_path)
        if count_row.program_type_id is not None and program_name:
            program_by_id[count_row.program_type_id] = SimpleNamespace(name=program_name)
        if count_row.event_id:
            event_by_id[str(count_row.event_id)] = SimpleNamespace(title=event_title or campaign_title)
        if count_row.entered_by_id and submitter_name:
            submitter_names[str(count_row.entered_by_id)] = submitter_name
        if prior is not None and not prior.is_deleted:
            history_by_id[str(prior.id)] = prior
    now = datetime.now(timezone.utc)
    group_ids = {row.count_group_id for rows in grouped.values() for row in rows if row.count_group_id}
    group_by_id = {}
    if group_ids:
        group_rows = (await db.execute(select(CountGroup).where(CountGroup.id.in_(group_ids)))).scalars().all()
        group_by_id = {str(group.id): group for group in group_rows}
    pending_ids = [row.id for row in pending]
    revision_rows = []
    if pending_ids:
        revision_rows = list((await db.execute(select(SubmissionEditRevision).where(
            SubmissionEditRevision.submission_type == "count",
            SubmissionEditRevision.submission_id.in_(pending_ids),
        ).order_by(SubmissionEditRevision.revision_no))).scalars().all())
    revisions_by_submission: dict[str, list[SubmissionEditRevision]] = {}
    for revision in revision_rows:
        revisions_by_submission.setdefault(str(revision.submission_id), []).append(revision)
    payload = []
    for rows in grouped.values():
        item = _review_group_payload(
            rows, now=now, score=score,
            location_by_id=location_by_id, program_by_id=program_by_id,
            event_by_id=event_by_id, submitter_names=submitter_names,
            history_by_id=history_by_id, group_by_id=group_by_id,
        )
        row_revisions = [revision for row in rows for revision in revisions_by_submission.get(str(row.id), [])]
        last_return = max((revision.created_at for revision in row_revisions if revision.action == "returned" and revision.created_at), default=None)
        edit_floor = last_return or min((row.created_at for row in rows if row.created_at), default=now)
        item["edited_count"] = sum(1 for revision in row_revisions if revision.action == "edit" and (last_return is None or revision.created_at > last_return))
        item["last_edited_at"] = max((revision.created_at for revision in row_revisions if revision.action == "edit" and revision.created_at), default=None)
        item["edit_window_hours_left"] = max(0, round(24 - (now - edit_floor).total_seconds() / 3600, 1))
        item["return_reason"] = next((revision.reason for revision in reversed(row_revisions) if revision.action == "returned"), "")
        if item["actionable"] or item["escalated"] or item["awaiting_close"] or item["group_conflict"]:
            payload.append(item)
    return sorted(payload, key=lambda item: (-item["age_hours"], item["date"], item["program_type"]))


async def _review_target(db: AsyncSession, count_id: UUID, current_user: User, *, allow_return: bool = False) -> tuple[Count, list[Count]]:
    base = await db.get(Count, count_id)
    if not base or base.is_deleted:
        raise HTTPException(status_code=404, detail="Count submission not found")
    deps.ensure_path_in_scope(current_user, base.path, detail="Count submission outside your jurisdiction")
    score = deps.highest_role_score(current_user)
    if _acceptor_score(base.program_level) != score:
        raise HTTPException(status_code=403, detail="Only the pastor assigned to this reporting level can review this count")
    if base.count_group_id:
        group = await db.get(CountGroup, base.count_group_id)
        if not allow_return and group and group.count_mode == "section" and group.state != "complete":
            raise HTTPException(status_code=409, detail="The lead usher must close this count group before it can be approved")
        if not allow_return and group and group.state == "conflict":
            raise HTTPException(status_code=409, detail="Resolve this count-group conflict before approval")
    rows = await _rows_for_group(db, base)
    eligible_states = {COUNT_PENDING, COUNT_APPROVED} if allow_return else {COUNT_PENDING}
    if not any(str(row.status).lower() in eligible_states for row in rows):
        raise HTTPException(status_code=409, detail="This count group no longer has pending submissions")
    for row in rows:
        deps.ensure_path_in_scope(current_user, row.path, detail="Count group contains a submission outside your jurisdiction")
    return base, rows


async def _section_suggestions(db: AsyncSession, location_id: str) -> list[dict[str, Any]]:
    saved = (await db.execute(select(CountSectionSuggestion).where(
        CountSectionSuggestion.location_id == location_id,
    ))).scalars().all()
    saved_by_key = {row.label_key: row for row in saved}
    prior_rows = (await db.execute(select(Count.section_label, Count.date).where(
        Count.location_id == location_id, Count.count_mode == "section",
        Count.section_label.is_not(None), Count.is_deleted.is_(False),
        Count.status.in_([COUNT_PENDING, COUNT_APPROVED]),
    ).order_by(Count.date.desc(), Count.created_at.desc()).limit(250))).all()
    ordered: list[str] = []
    seen: set[str] = set()
    for label, _date in prior_rows:
        clean = str(label or "").strip()
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            ordered.append(clean)
    for row in sorted(saved, key=lambda item: item.last_modify, reverse=True):
        if row.label_key not in seen:
            ordered.insert(0, row.label)
            seen.add(row.label_key)
    return [{"label": label, "hidden": bool(saved_by_key.get(label.casefold()) and saved_by_key[label.casefold()].is_hidden)}
            for label in ordered]


async def _auto_close_elapsed_groups(db: AsyncSession, group_ids: set[UUID]) -> None:
    if not group_ids:
        return
    now_local = datetime.now(_LAGOS)
    groups = (await db.execute(select(CountGroup).where(
        CountGroup.id.in_(group_ids), CountGroup.state == "open",
        CountGroup.finalized_at.is_(None), CountGroup.auto_closed_at.is_(None),
    ).with_for_update())).scalars().all()
    changed = False
    for group in groups:
        if count_group_is_past_deadline(group.occurrence_date, now_local):
            group.state = "complete"
            group.auto_closed_at = now_local
            changed = True
    if changed:
        await db.commit()


@router.get("/suggestions/{location_id}", dependencies=[Depends(deps.PermissionChecker("counts:read"))])
async def list_count_section_suggestions(
    location_id: str,
    program_domain: Optional[str] = Query(None, max_length=80),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(404, "Location not found")
    deps.ensure_path_in_scope(current_user, location.path, detail="Location outside your scope")
    items = await _section_suggestions(db, location_id)
    if not items:
        items.extend({"label": label, "hidden": False, "default": True} for label in ("A", "B", "C"))
    if str(program_domain or "").strip().lower() in {"retreat", "crusade"}:
        existing = {str(item["label"]).casefold() for item in items}
        defaults = [label for label in ("Adult", "Campus", "Youth", "Children") if label.casefold() not in existing]
        items.extend({"label": label, "hidden": False, "default": True} for label in defaults)
    return items


@router.get("/services/{location_id}/{occurrence_date}", dependencies=[Depends(deps.PermissionChecker("counts:read"))])
async def list_prior_count_services(
    location_id: str,
    occurrence_date: date,
    program_type: str = Query(..., min_length=1, max_length=120),
    event_id: Optional[UUID] = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return session names previously used for this location/program/date."""
    location = await db.get(Location, location_id)
    if location is None:
        raise HTTPException(404, "Location not found")
    deps.ensure_path_in_scope(current_user, location.path, detail="Location outside your scope")
    query = select(CountGroup.service_id).join(Count, Count.count_group_id == CountGroup.id).where(
        CountGroup.location_id == location_id,
        CountGroup.occurrence_date == occurrence_date,
        Count.is_deleted.is_(False),
    )
    if event_id:
        query = query.where(Count.event_id == event_id)
    else:
        query = query.where(Count.event_id.is_(None), func.lower(Count.program_type) == program_type.strip().lower())
    services = sorted(set((await db.execute(query.distinct())).scalars().all()))
    return {"services": services}


@router.put("/suggestions/{location_id}", dependencies=[Depends(deps.PermissionChecker("counts:update"))])
async def update_count_section_suggestions(
    location_id: str,
    payload: list[CountSectionSuggestionInput],
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(404, "Location not found")
    deps.ensure_path_in_scope(current_user, location.path, detail="Location outside your scope")
    seen: set[str] = set()
    for item in payload:
        label = item.label.strip()
        key = label.casefold()
        if key in seen:
            raise HTTPException(422, "Suggestion labels must be unique")
        seen.add(key)
        previous_key = (item.previous_label or label).strip().casefold()
        row = (await db.execute(select(CountSectionSuggestion).where(
            CountSectionSuggestion.location_id == location_id,
            CountSectionSuggestion.label_key == previous_key,
        ).with_for_update())).scalar_one_or_none()
        if row is None:
            row = CountSectionSuggestion(location_id=location_id, label=label, label_key=key, updated_by_id=current_user.user_id)
            db.add(row)
        else:
            row.label, row.label_key, row.is_hidden, row.updated_by_id = label, key, item.hidden, current_user.user_id
    await db.commit()
    return {"suggestions": await _section_suggestions(db, location_id)}


@router.post("/groups/{count_id}/close", dependencies=[Depends(deps.PermissionChecker("counts:create"))])
async def close_count_group(
    count_id: UUID,
    payload: CountGroupCloseRequest = CountGroupCloseRequest(),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Close the local count group so it is ready for pastor approval."""
    row = await db.get(Count, count_id)
    if row is None or row.is_deleted or row.count_group_id is None:
        raise HTTPException(404, "Count group not found")
    deps.ensure_path_in_scope(current_user, row.path, detail="Count group outside your scope")
    if deps.effective_scope_path(current_user) != str(row.path) or (getattr(current_user, "location_id", None) is not None and str(current_user.location_id) != str(row.location_id)):
        raise HTTPException(403, "Only an usher, administrator, or pastor assigned to this location can close its count")
    group = await db.get(CountGroup, row.count_group_id, with_for_update=True)
    if group is None:
        raise HTTPException(404, "Count group not found")
    if group.state == "conflict":
        raise HTTPException(409, "Resolve the count-group conflict before closing it")
    labels = list((await db.execute(select(Count.section_label).where(
        Count.count_group_id == group.id, Count.is_deleted.is_(False),
        Count.count_mode == "section", Count.status.in_([COUNT_PENDING, COUNT_APPROVED]),
    ))).scalars().all())
    suggestions = await _section_suggestions(db, str(group.location_id))
    reported = {str(label or "").strip().casefold() for label in labels}
    missing = missing_suggested_labels(suggestions, reported)
    if missing and not payload.confirm_missing_suggestions:
        return {"count_group_id": str(group.id), "confirmation_required": True, "missing_suggested_labels": missing}
    group.state = "complete"
    group.finalized_by = current_user.user_id
    group.finalized_at = datetime.now(timezone.utc)
    group.close_reason = None
    await db.commit()
    return {"count_group_id": str(group.id), "state": group.state, "finalized_by": str(group.finalized_by), "finalized_at": group.finalized_at.isoformat(), "missing_suggested_labels": missing, "ready_for_approval": True}


@router.post("/groups/{count_id}/resolve", dependencies=[Depends(deps.PermissionChecker("counts:create"))])
async def resolve_count_group_conflict(
    count_id: UUID,
    payload: CountGroupResolveRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    base = await db.get(Count, count_id)
    if base is None or base.is_deleted or base.count_group_id is None:
        raise HTTPException(404, "Count group not found")
    deps.ensure_path_in_scope(current_user, base.path, detail="Count group outside your scope")
    rows = await _rows_for_group(db, base)
    base_group = await db.get(CountGroup, base.count_group_id, with_for_update=True)
    if base_group is None:
        raise HTTPException(404, "Count group not found")
    if deps.effective_scope_path(current_user) != str(base.path):
        raise HTTPException(403, "Only a user assigned to this location can resolve its count conflict")
    if payload.action in {"keep_one", "replace"}:
        raise HTTPException(409, "Count parts are preserved. Resolve a conflict by correcting the affected submission; rows cannot be removed here.")
    else:
        if not payload.replace_count_id or not (payload.new_label or "").strip():
            raise HTTPException(422, "Choose the duplicate section to relabel and enter its new label")
        target = next((row for row in rows if row.id == payload.replace_count_id), None)
        if target is None or target.count_mode != "section":
            raise HTTPException(422, "Choose a section row from this group")
        new_label = payload.new_label.strip()
        if any(row.id != target.id and row.count_mode == "section" and (row.section_label or "").casefold() == new_label.casefold() for row in rows):
            raise HTTPException(409, "That section label is already used in this group")
        before = {"section_label": target.section_label}
        target.section_label = new_label
        target.last_modify = datetime.now(timezone.utc)
        prior_revisions = list((await db.execute(select(SubmissionEditRevision).where(
            SubmissionEditRevision.submission_type == "count", SubmissionEditRevision.submission_id == target.id,
        ).order_by(SubmissionEditRevision.revision_no))).scalars().all())
        db.add(SubmissionEditRevision(
            submission_type="count", submission_id=target.id, edit_id=uuid4(),
            revision_no=(prior_revisions[-1].revision_no + 1 if prior_revisions else 1),
            action="resolved", editor_id=current_user.user_id, before_values=before,
            after_values={"section_label": new_label}, reason="Lead usher resolved duplicate section labels",
        ))
    remaining = [row for row in rows if not row.is_deleted]
    modes = {row.count_mode for row in remaining if row.count_mode}
    single_conflict = "single" in modes and len([row for row in remaining if row.count_mode == "single"]) > 1
    labels = [row.section_label.strip().casefold() for row in remaining if row.count_mode == "section" and row.section_label]
    duplicate_labels = len(labels) != len(set(labels))
    base_group.state = "conflict" if len(modes) > 1 or single_conflict or duplicate_labels else (
        "complete" if modes == {"single"} and len(remaining) == 1 else "open"
    )
    base_group.finalized_at = None
    base_group.finalized_by = None
    base_group.close_reason = None
    await db.commit()
    return {"count_group_id": str(base_group.id), "state": base_group.state, "active_count_ids": [str(row.id) for row in remaining]}


@router.post("/review/{count_id}/approve", dependencies=[Depends(deps.PermissionChecker("counts:review"))])
async def approve_count_group(
    count_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Approve every pending row in the selected program/location/date group."""
    _, rows = await _review_target(db, count_id, current_user)
    if _split_count_conflict(rows):
        raise HTTPException(409, "Conflicting single and section submissions must be resolved before approval")
    reviewed_at = datetime.now(timezone.utc)
    for row in rows:
        row.status = COUNT_APPROVED
        row.approved_by_id = current_user.user_id
        row.approved_at = reviewed_at
        row.auto_accepted = False
        row.rejection_reason = None
        row.rejected_by_id = None
        row.rejected_at = None
    await db.commit()
    analytics_cache.clear()
    return {"status": "approved", "approved_by_id": str(current_user.user_id), "approved_at": reviewed_at, "count_ids": [str(row.id) for row in rows]}


@router.post("/review/{count_id}/reject", dependencies=[Depends(deps.PermissionChecker("counts:review"))])
async def reject_count_group(
    count_id: UUID,
    payload: CountRejection,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Reject every pending row in a count group with an auditable reason."""
    _, rows = await _review_target(db, count_id, current_user)
    if _split_count_conflict(rows):
        raise HTTPException(409, "Conflicting submissions must be resolved before returning this count group")
    rejected_at = datetime.now(timezone.utc)
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="A rejection reason is required")
    for row in rows:
        row.status = COUNT_REJECTED
        row.rejection_reason = reason
        row.rejected_by_id = current_user.user_id
        row.rejected_at = rejected_at
    await db.commit()
    analytics_cache.clear()
    return {"status": "rejected", "rejected_by_id": str(current_user.user_id), "rejected_at": rejected_at, "reason": reason, "count_ids": [str(row.id) for row in rows]}


@router.post("/review/{count_id}/return", dependencies=[Depends(deps.PermissionChecker("counts:review"))])
async def return_count_group(
    count_id: UUID,
    payload: CountReturnRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return all pending sections in this reporting group to their own submitters."""
    base, rows = await _review_target(db, count_id, current_user, allow_return=True)
    returnable_rows = [row for row in rows if str(row.status).lower() in {COUNT_PENDING, COUNT_APPROVED}]
    row_ids = await return_count_for_correction(db, rows=returnable_rows, actor=current_user, reason=payload.reason)
    if base.count_group_id:
        group = await db.get(CountGroup, base.count_group_id, with_for_update=True)
        if group:
            group.state = "open"
            group.finalized_by = None
            group.finalized_at = None
            group.auto_closed_at = None
            group.close_reason = payload.reason.strip()
    await db.commit()
    analytics_cache.clear()
    return {"status": "returned", "reason": payload.reason.strip(), "count_ids": row_ids}


@router.post("/{count_id}/edit")
async def edit_own_count(
    count_id: UUID,
    payload: CountEditRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return await edit_count_submission(
        db, count_id=count_id, edit_id=payload.edit_id,
        base_revision=payload.base_revision, values=payload.values, actor=current_user,
    )


@router.get("/mine/editable")
async def list_my_editable_counts(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List this account's own non-locked count submissions and edit allowance."""
    rows = list((await db.execute(select(Count, ProgramType.name, ProgramEvent.title).outerjoin(
        ProgramType, ProgramType.id == Count.program_type_id,
    ).outerjoin(ProgramEvent, ProgramEvent.id == Count.event_id).where(
        Count.entered_by_id == current_user.user_id,
        Count.is_deleted.is_(False),
        Count.status.in_([COUNT_PENDING, "returned", COUNT_APPROVED]),
    ).order_by(Count.created_at.desc()).limit(100))).all())
    if not rows:
        return []
    count_rows = [item[0] for item in rows]
    groups_by_id = {}
    group_ids = {row.count_group_id for row in count_rows if row.count_group_id}
    if group_ids:
        await _auto_close_elapsed_groups(db, group_ids)
        groups = (await db.execute(select(CountGroup).where(CountGroup.id.in_(group_ids)))).scalars().all()
        groups_by_id = {group.id: group for group in groups}
    active_group_rows = []
    if group_ids:
        active_group_rows = (await db.execute(select(Count).where(
            Count.count_group_id.in_(group_ids), Count.is_deleted.is_(False),
            Count.status.in_([COUNT_PENDING, COUNT_APPROVED]),
        ))).scalars().all()
    group_sections: dict[str, list[str]] = {}
    group_totals: dict[str, int] = {}
    group_categories: dict[str, dict[str, int]] = {}
    for grouped_row in active_group_rows:
        key = str(grouped_row.count_group_id)
        if grouped_row.count_mode == "section" and grouped_row.section_label:
            group_sections.setdefault(key, []).append(grouped_row.section_label)
        group_totals[key] = group_totals.get(key, 0) + int(grouped_row.total or 0)
        totals = group_categories.setdefault(key, {field: 0 for field in ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")})
        for field in totals:
            totals[field] += int(getattr(grouped_row, field) or 0)
    revisions = list((await db.execute(select(SubmissionEditRevision).where(
        SubmissionEditRevision.submission_type == "count",
        SubmissionEditRevision.submission_id.in_([row.id for row in count_rows]),
    ).order_by(SubmissionEditRevision.revision_no))).scalars().all())
    by_id: dict[str, list[SubmissionEditRevision]] = {}
    for revision in revisions:
        by_id.setdefault(str(revision.submission_id), []).append(revision)
    now = datetime.now(timezone.utc)
    output = []
    for row, program_name, event_title in rows:
        history = by_id.get(str(row.id), [])
        last_return = next((item for item in reversed(history) if item.action == "returned"), None)
        opened = last_return.created_at if last_return else row.created_at
        remaining_seconds = max(0, SUBMISSION_EDIT_WINDOW_HOURS * 3600 - (now - opened).total_seconds()) if opened else 0
        hours_left = round(remaining_seconds / 3600, 1)
        edits = sum(1 for item in history if item.action == "edit")
        limit = SUBMISSION_MAX_EDITS + (SUBMISSION_RETURN_EXTRA_EDITS if last_return else 0)
        locked = str(row.status).lower() == COUNT_APPROVED or remaining_seconds <= 0 or edits >= limit
        output.append({
            "id": str(row.id), "status": row.status, "date": _calendar_date(row.date).isoformat(),
            "event_id": str(row.event_id or ""),
            "program_type": row.program_type or program_name or event_title or "Unclassified program", "location_id": str(row.location_id),
            "total": int(row.total or 0), "categories": {field: int(getattr(row, field) or 0) for field in ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")},
            "count_mode": row.count_mode, "section_label": row.section_label,
            "service_id": groups_by_id.get(row.count_group_id).service_id if row.count_group_id in groups_by_id else "main",
            "can_close_group": bool(row.count_group_id and deps.effective_scope_path(current_user) == str(row.path)),
            "revision": len(history), "edits_used": edits, "edits_remaining": max(0, limit - edits),
            "locked": locked,
            "locked_message": ("Approved reports are locked." if str(row.status).lower() == COUNT_APPROVED else "The 24-hour edit window has closed." if remaining_seconds <= 0 else "The edit limit has been reached." if edits >= limit else ""),
            "hours_remaining": hours_left, "return_reason": last_return.reason if last_return else None,
            "count_group_state": groups_by_id.get(row.count_group_id).state if row.count_group_id in groups_by_id else None,
            "auto_closed": bool(groups_by_id.get(row.count_group_id) and groups_by_id[row.count_group_id].auto_closed_at),
            "service_id": groups_by_id.get(row.count_group_id).service_id if row.count_group_id in groups_by_id else "legacy",
            "can_close_group": bool(row.count_group_id and deps.effective_scope_path(current_user) == str(row.path)),
            "reported_sections": sorted(set(group_sections.get(str(row.count_group_id), [])), key=str.casefold),
            "group_total": None if groups_by_id.get(row.count_group_id) and groups_by_id[row.count_group_id].state == "conflict" else group_totals.get(str(row.count_group_id)),
            "group_categories": None if groups_by_id.get(row.count_group_id) and groups_by_id[row.count_group_id].state == "conflict" else group_categories.get(str(row.count_group_id)),
        })
    return output


@router.get("/{count_id}/edit-history", dependencies=[Depends(deps.PermissionChecker("counts:read"))])
async def count_edit_history(
    count_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    row = await db.get(Count, count_id)
    if row is None or row.is_deleted:
        raise HTTPException(404, "Count submission not found")
    deps.ensure_path_in_scope(current_user, row.path, detail="Count history outside your scope")
    revisions = (await db.execute(select(SubmissionEditRevision).where(
        SubmissionEditRevision.submission_type == "count",
        SubmissionEditRevision.submission_id == row.id,
    ).order_by(SubmissionEditRevision.revision_no))).scalars().all()
    return {"submission_id": str(row.id), "status": row.status, "history": [
        {"revision": item.revision_no, "action": item.action, "editor_id": str(item.editor_id),
         "before": item.before_values, "after": item.after_values, "reason": item.reason,
         "created_at": item.created_at.isoformat() if item.created_at else None}
        for item in revisions
    ]}


@router.get("/{count_id}/history", dependencies=[Depends(deps.PermissionChecker("counts:read"))])
async def count_history(
    count_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return the rejected submission and all linked corrections in its history."""
    base = await db.get(Count, count_id)
    if not base or base.is_deleted:
        raise HTTPException(status_code=404, detail="Count submission not found")
    deps.ensure_path_in_scope(current_user, base.path, detail="Count submission outside your jurisdiction")
    lineage_ids = {base.id}
    if base.supersedes_id:
        lineage_ids.add(base.supersedes_id)
    while True:
        result = await db.execute(select(Count.id).where(Count.supersedes_id.in_(lineage_ids)))
        found = {row[0] for row in result.all()}
        new_ids = found - lineage_ids
        if not new_ids:
            break
        lineage_ids.update(new_ids)
    rows = (await db.execute(select(Count).where(Count.id.in_(lineage_ids), Count.is_deleted.is_(False)).order_by(Count.created_at, Count.id))).scalars().all()
    for row in rows:
        deps.ensure_path_in_scope(current_user, row.path, detail="Count history outside your jurisdiction")
    return {"history": [CountResponse.model_validate(row).model_dump(mode="json") for row in rows]}


@router.post("/review/remind", dependencies=[Depends(deps.PermissionChecker("counts:remind"))])
async def remind_unreported_location(
    payload: CountReminder,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Send the existing in-app broadcast to one location with no Sunday report."""
    if deps.highest_role_score(current_user) < 2:
        raise HTTPException(status_code=403, detail="Level 2 or higher authority is required to remind a location")
    location_result = await db.execute(
        select(Location).where(Location.location_id == str(payload.location_id)).with_for_update()
    )
    location = location_result.scalar_one_or_none()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    deps.ensure_path_in_scope(current_user, location.path, detail="Location outside your jurisdiction")
    program_type = await db.get(ProgramType, payload.program_type_id)
    if not program_type or program_type.slug != "sunday_worship_service":
        raise HTTPException(status_code=422, detail="Reminders currently support Sunday Worship only")
    start = datetime.combine(payload.occurrence_date, time.min, _LAGOS).astimezone(timezone.utc)
    end = datetime.combine(payload.occurrence_date + timedelta(days=1), time.min, _LAGOS).astimezone(timezone.utc)
    existing = await db.execute(select(Count.id).where(
        Count.date >= start, Count.date < end, Count.program_type_id == program_type.id,
        Count.is_deleted.is_(False), Count.program_scope_path.is_not(None),
        scope_or_ancestor_filter(Count.program_scope_path, str(location.path)),
    ).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A report already exists for this location or a combined scope covering it")
    event = await db.execute(select(ProgramEvent.id).where(
        ProgramEvent.program_type_id == program_type.id, ProgramEvent.date == payload.occurrence_date,
        ProgramEvent.approval_status == "approved", ProgramEvent.is_deleted.is_(False),
        ProgramEvent.reporting_scope.in_(["group", "region", "state"]),
        scope_or_ancestor_filter(ProgramEvent.path, str(location.path)),
    ).limit(1))
    if event.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="An approved combined event covers this location")
    now = datetime.now(timezone.utc)
    recent_reminder = await db.execute(
        select(CountReminderRecipient.sent_at)
        .where(
            CountReminderRecipient.location_id == str(location.location_id),
            CountReminderRecipient.occurrence_date == payload.occurrence_date,
            CountReminderRecipient.sent_at >= now - timedelta(hours=24),
        )
        .order_by(CountReminderRecipient.sent_at.desc())
        .limit(1)
    )
    previous_sent_at = recent_reminder.scalar_one_or_none()
    if previous_sent_at is not None:
        elapsed = max(int((now - previous_sent_at).total_seconds() // 3600), 0)
        raise HTTPException(status_code=429, detail=f"Reminded {elapsed}h ago")

    recipient_result = await db.execute(_count_reminder_recipient_query(location))
    recipient_ids = list(recipient_result.scalars().all())
    if not recipient_ids:
        raise HTTPException(status_code=409, detail="No usher or pastor on record")

    reminder_id = uuid4()
    db.add_all([
        CountReminderRecipient(
            reminder_id=reminder_id,
            recipient_user_id=recipient_id,
            sent_by_id=current_user.user_id,
            location_id=str(location.location_id),
            occurrence_date=payload.occurrence_date,
            sent_at=now,
        )
        for recipient_id in recipient_ids
    ])
    await db.commit()
    return {
        "status": "sent", "reminder_id": str(reminder_id), "location_id": str(location.location_id),
        "occurrence_date": payload.occurrence_date.isoformat(), "sent_at": now,
        "recipient_count": len(recipient_ids),
    }


@router.get("/review/unreported")
async def list_unreported_sunday_locations(
    occurrence_date: date = Query(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List uncovered locations for a Sunday for authorized reviewers/reminders."""
    if not (deps.has_permission(current_user, "counts:review") or deps.has_permission(current_user, "counts:remind")):
        raise HTTPException(status_code=403, detail="Count review or reminder permission is required")
    if occurrence_date.weekday() != 6:
        raise HTTPException(status_code=422, detail="Sunday Worship reminders require a Sunday date")
    scope_path = deps.effective_scope_path(current_user)
    type_result = await db.execute(select(ProgramType).where(ProgramType.slug == "sunday_worship_service", ProgramType.is_deleted.is_(False)))
    program_type = type_result.scalars().first()
    if not program_type:
        return []
    locations_result = await db.execute(select(Location).where(
        scope_filter(Location.path, scope_path),
        or_(Location.is_active.is_(True), and_(Location.is_active.is_(False), Location.closed_on.is_not(None), Location.closed_on > occurrence_date)),
        or_(Location.opened_on.is_(None), Location.opened_on <= occurrence_date),
        or_(Location.closed_on.is_(None), Location.closed_on > occurrence_date),
    ).order_by(Location.location_name))
    locations = list(locations_result.scalars().all())
    if not locations:
        return []
    start = datetime.combine(occurrence_date, time.min, _LAGOS).astimezone(timezone.utc)
    end = datetime.combine(occurrence_date + timedelta(days=1), time.min, _LAGOS).astimezone(timezone.utc)
    reports_result = await db.execute(select(Count).where(
        Count.program_type_id == program_type.id, Count.date >= start, Count.date < end,
        Count.is_deleted.is_(False), Count.program_scope_path.is_not(None),
        or_(scope_filter(Count.path, scope_path), scope_or_ancestor_filter(Count.program_scope_path, scope_path)),
    ))
    reports = list(reports_result.scalars().all())
    events_result = await db.execute(select(ProgramEvent).where(
        ProgramEvent.program_type_id == program_type.id, ProgramEvent.date == occurrence_date,
        ProgramEvent.approval_status == "approved", ProgramEvent.is_deleted.is_(False),
        ProgramEvent.reporting_scope.in_(["group", "region", "state"]),
        scope_or_ancestor_filter(ProgramEvent.path, scope_path),
    ))
    combined_events = list(events_result.scalars().all())
    uncovered = []
    for location in locations:
        has_report = any(_path_covers(str(row.program_scope_path), str(location.path)) for row in reports)
        has_scheduled_cover = any(_path_covers(str(event.path), str(location.path)) for event in combined_events)
        if not has_report and not has_scheduled_cover:
            uncovered.append({"location_id": str(location.location_id), "location": location.location_name, "path": str(location.path), "date": occurrence_date.isoformat(), "program_type_id": program_type.id})
    return uncovered


@router.get(
    "/{count_id}",
    response_model=CountResponse,
    dependencies=[Depends(deps.PermissionChecker("counts:read"))],
)
async def read_count(
    *,
    db: AsyncSession = Depends(deps.get_db),
    count_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a specific count by ID."""
    count = await crud_count.get(db, id=count_id)
    if not count:
        raise HTTPException(status_code=404, detail="Count not found")
    deps.ensure_path_in_scope(current_user, count.path, detail="Count outside your scope")
    return count


@router.put(
    "/{count_id}",
    response_model=CountResponse,
    dependencies=[Depends(deps.PermissionChecker("counts:update"))],
)
async def update_count(
    *,
    db: AsyncSession = Depends(deps.get_db),
    count_id: UUID,
    count_in: CountUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a count record."""
    count = await crud_count.get(db, id=count_id)
    if not count:
        raise HTTPException(status_code=404, detail="Count not found")
    deps.ensure_path_in_scope(current_user, count.path, detail="Count outside your scope")
    
    updated_count = await crud_count.update(db, db_obj=count, obj_in=count_in)
    
    # CRUD recalculates and commits the derived total in the same transaction.
    
    return updated_count


@router.post(
    "/batch",
    response_model=SyncResult,
    dependencies=[Depends(deps.PermissionChecker("counts:create"))],
)
async def batch_create_counts(
    *,
    db: AsyncSession = Depends(deps.get_db),
    items: List[CountCreate],
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Batch submit counts (offline sync convenience).

    Performance changes:
    - All client_id duplicates are resolved in a single WHERE IN query
      before the loop — was one DB round-trip per item.
    - All unique location IDs are scope-validated in a single batch call
      before the loop — was one DB round-trip per item.
    - Items for out-of-scope locations are rejected immediately without
      attempting an insert.
    """
    from sqlalchemy import select as _select
    from app.models.counts import Count as _Count
    from app.models.location import Location

    sync_result = SyncResult()
    details = []

    if not items:
        return sync_result
    if any(item.client_id is None for item in items):
        raise HTTPException(status_code=422, detail="Every count batch item requires a stable client_id")

    # ── 1. Pre-fetch existing client_ids in ONE query ─────────────────────
    client_ids_in = [i.client_id for i in items if i.client_id]
    existing_by_client_id: dict = {}
    if client_ids_in:
        rows = (await db.execute(
            _select(_Count.client_id, _Count.id).where(
                _Count.client_id.in_(client_ids_in)
            )
        )).all()
        existing_by_client_id = {str(row.client_id): str(row.id) for row in rows}

    # ── 2. Pre-validate all unique location IDs in scope ─────────────────
    unique_location_ids = {i.location_id for i in items}
    locations = (await db.execute(
        _select(Location.location_id, Location.path).where(
            Location.location_id.in_(unique_location_ids)
        )
    )).all()
    valid_location_ids: set = set()
    for loc in locations:
        try:
            deps.ensure_path_in_scope(
                current_user, loc.path, detail="Count location outside your scope"
            )
            valid_location_ids.add(str(loc.location_id))
        except Exception:
            pass  # location is out of scope — will be caught per item below

    # ── 3. Process items — only CRUD inserts remain in the loop ──────────
    for item in items:
        client_id_str = str(item.client_id) if item.client_id else None
        try:
            # Validate the submitted location before any idempotency lookup so
            # guessed client IDs cannot reveal records from another scope.
            if str(item.location_id) not in valid_location_ids:
                sync_result.errors += 1
                details.append({
                    "client_id": client_id_str,
                    "error": "Count location outside your scope",
                    "status": "error",
                })
                continue

            # Duplicate check (O(1) dict lookup, not a DB call)
            if client_id_str and client_id_str in existing_by_client_id:
                existing = await crud_count.get_by_client_id(db, client_id=item.client_id)
                if existing is None:
                    existing_by_client_id.pop(client_id_str, None)
                else:
                    try:
                        deps.ensure_path_in_scope(current_user, existing.path, detail="Existing count is outside your scope")
                    except HTTPException:
                        sync_result.errors += 1
                        details.append({"client_id": client_id_str, "error": "Existing count is outside your scope", "status": "error"})
                        continue
                    sync_result.duplicates += 1
                    details.append({
                        "client_id": client_id_str,
                        "id": str(existing.id),
                        "status": "duplicate",
                    })
                    continue

            # The only remaining DB call per item is the actual insert
            created = await crud_count.create(db, obj_in=item, user_id=current_user.user_id)
            if getattr(created, "_was_duplicate_submission", False):
                deps.ensure_path_in_scope(current_user, created.path, detail="Existing count is outside your scope")
                sync_result.duplicates += 1
                status_value = "duplicate"
            else:
                sync_result.synced += 1
                status_value = "synced"
            details.append({
                "client_id": client_id_str,
                "id": str(created.id),
                "status": status_value,
            })
        except HTTPException as exc:
            await db.rollback()
            sync_result.errors += 1
            details.append({
                "client_id": client_id_str,
                "error": exc.detail,
                "status": "error",
            })
        except Exception as exc:
            await db.rollback()
            sync_result.errors += 1
            details.append({
                "client_id": client_id_str,
                "error": str(exc),
                "status": "error",
            })

    sync_result.details = details
    return sync_result


@router.get(
    "/stats",
    dependencies=[Depends(deps.PermissionChecker("counts:read"))],
)
async def get_count_stats(
    program_domain: str = None,
    program_type: str = None,
    location_id: str = None,
    start_month: int = None,
    end_month: int = None,
    start_year: int = None,
    end_year: int = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return aggregated population stats (wrapper around statistics service)."""
    scope_path = deps.effective_scope_path(current_user)
    stats = await StatisticsService.get_population_statistics(
        db,
        scope_path,
        program_domain,
        program_type,
        location_id,
        None,
        start_month,
        end_month,
        start_year,
        end_year,
    )
    return stats

@router.delete(
    "/{count_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("counts:delete"))],
)
async def delete_count(
    *,
    db: AsyncSession = Depends(deps.get_db),
    count_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a count record."""
    count = await crud_count.get(db, id=count_id)
    if not count:
        raise HTTPException(status_code=404, detail="Count not found")
    deps.ensure_path_in_scope(current_user, count.path, detail="Count outside your scope")
    
    await crud_count.update(
        db,
        db_obj=count,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.now(timezone.utc)}
    )
    return None
