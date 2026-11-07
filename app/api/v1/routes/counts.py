"""
Count submission and retrieval routes.

Handles population count data collection with offline sync support.
"""
from typing import Any, List, Optional
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, or_, and_
from pydantic import BaseModel, Field
from zoneinfo import ZoneInfo

from app.api import deps
from app.db.filters import ltree_subpath as _ltree_subpath
from app.db.filters import scope_filter as _scope_filter
from app.crud.crud_counts import count as crud_count
from app.schemas.counts import CountCreate, CountResponse, CountUpdate
from app.schemas.sync import SyncResult
from app.services.statistics_service import StatisticsService
from app.models.user import User
from app.models.counts import Count
from app.models.programs import ProgramEvent, ProgramType, ProgramDomain
from app.models.location import Location
from app.models.user import Worker
from app.models.broadcast import BroadcastMessage
from app.db.filters import scope_filter
from app.db.filters import scope_or_ancestor_filter
from app.services.analytics.program_config import PENDING_ACCEPTOR_ALERT_HOURS, PENDING_NEXT_LEVEL_ALERT_HOURS
from app.utils.count_sections import legacy_section_label

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
    program_key = ("id", row.program_type_id) if row.program_type_id is not None else ("legacy", (row.program_type or "").strip().lower())
    return (str(row.location_id), program_key, _calendar_date(row.date), str(row.program_level or "").lower(), str(row.program_scope_path or ""), str(row.event_id or ""))


async def _rows_for_group(db: AsyncSession, base: Count, *, pending_only: bool = False) -> list[Count]:
    occurrence = _calendar_date(base.date)
    start = datetime.combine(occurrence, time.min, _LAGOS).astimezone(timezone.utc)
    end = datetime.combine(occurrence + timedelta(days=1), time.min, _LAGOS).astimezone(timezone.utc)
    filters = [
        Count.location_id == base.location_id,
        Count.date >= start,
        Count.date < end,
        Count.is_deleted.is_(False),
        Count.program_level == base.program_level if base.program_level is not None else Count.program_level.is_(None),
        Count.program_scope_path == base.program_scope_path if base.program_scope_path is not None else Count.program_scope_path.is_(None),
        Count.event_id == base.event_id if base.event_id is not None else Count.event_id.is_(None),
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
) -> dict[str, Any]:
    base = rows[0]
    location = location_by_id.get(str(base.location_id))
    program_type_row = program_by_id.get(base.program_type_id) if base.program_type_id is not None else None
    event = event_by_id.get(str(base.event_id)) if base.event_id else None
    earliest = min((row.created_at for row in rows if row.created_at), default=now)
    age_hours = max(0, (now - earliest).total_seconds() / 3600)
    expected_score = _acceptor_score(base.program_level)
    section_labels = set()
    correction_history = []
    for row in rows:
        # Legacy only: B5 will replace the note prefix with dedicated columns.
        section_label = legacy_section_label(row.note)
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
        "count_id": str(base.id), "group_key": list(_count_group_key(base)),
        "location_id": str(base.location_id), "program_type_id": base.program_type_id,
        "program_type": base.program_type or (program_type_row.name if program_type_row else "Unclassified program"),
        "event_title": (event.title if event and event.title else "") or "", "location": location.location_name if location else str(base.location_id),
        "program_level": base.program_level or "Local",
        "program_scope_path": str(base.program_scope_path or base.path), "event_id": str(base.event_id or ""),
        "date": _calendar_date(base.date).isoformat(), "total": sum(int(row.total or 0) for row in rows),
        "categories": {field: sum(int(getattr(row, field, 0) or 0) for row in rows) for field in ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")},
        "submission_count": len(rows), "section_count": len(section_labels) if section_labels else len(rows),
        "section_labels": sorted(section_labels), "sections_recorded": bool(section_labels),
        "submitters": sorted({submitter_names.get(str(row.entered_by_id), str(row.entered_by_id)) for row in rows}),
        "correction_history": correction_history,
        "age_hours": round(age_hours, 1),
        "flag_10h": age_hours >= PENDING_ACCEPTOR_ALERT_HOURS,
        "flag_24h": age_hours >= PENDING_NEXT_LEVEL_ALERT_HOURS,
        "actionable": score == expected_score,
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
    result = await db.execute(
        select(Count).where(
            scope_filter(Count.path, scope_path), Count.is_deleted.is_(False), Count.status == COUNT_PENDING
        ).order_by(Count.created_at, Count.id)
    )
    pending = list(result.scalars().all())
    grouped: dict[tuple, list[Count]] = {}
    for row in pending:
        grouped.setdefault(_count_group_key(row), []).append(row)
    location_ids = {row.location_id for row in pending}
    program_ids = {row.program_type_id for row in pending if row.program_type_id is not None}
    event_ids = {row.event_id for row in pending if row.event_id is not None}
    submitter_ids = {row.entered_by_id for row in pending if row.entered_by_id is not None}
    prior_ids = {row.supersedes_id for row in pending if row.supersedes_id is not None}
    location_rows = (await db.execute(select(Location).where(Location.location_id.in_(location_ids)))).scalars().all() if location_ids else []
    program_rows = (await db.execute(select(ProgramType).where(ProgramType.id.in_(program_ids)))).scalars().all() if program_ids else []
    event_rows = (await db.execute(select(ProgramEvent).where(ProgramEvent.id.in_(event_ids)))).scalars().all() if event_ids else []
    user_rows = (await db.execute(select(User.user_id, User.name).where(User.user_id.in_(submitter_ids)))).all() if submitter_ids else []
    prior_rows = (await db.execute(select(Count).where(Count.id.in_(prior_ids), Count.is_deleted.is_(False)))).scalars().all() if prior_ids else []
    location_by_id = {str(row.location_id): row for row in location_rows}
    program_by_id = {row.id: row for row in program_rows}
    event_by_id = {str(row.id): row for row in event_rows}
    submitter_names = {str(user_id): name for user_id, name in user_rows}
    history_by_id = {str(row.id): row for row in prior_rows}
    now = datetime.now(timezone.utc)
    payload = []
    for rows in grouped.values():
        item = _review_group_payload(
            rows, now=now, score=score,
            location_by_id=location_by_id, program_by_id=program_by_id,
            event_by_id=event_by_id, submitter_names=submitter_names,
            history_by_id=history_by_id,
        )
        if item["actionable"] or item["escalated"]:
            payload.append(item)
    return sorted(payload, key=lambda item: (-item["age_hours"], item["date"], item["program_type"]))


async def _review_target(db: AsyncSession, count_id: UUID, current_user: User) -> tuple[Count, list[Count]]:
    base = await db.get(Count, count_id)
    if not base or base.is_deleted:
        raise HTTPException(status_code=404, detail="Count submission not found")
    deps.ensure_path_in_scope(current_user, base.path, detail="Count submission outside your jurisdiction")
    score = deps.highest_role_score(current_user)
    if _acceptor_score(base.program_level) != score:
        raise HTTPException(status_code=403, detail="Only the pastor assigned to this reporting level can review this count")
    rows = await _rows_for_group(db, base, pending_only=True)
    if not rows:
        raise HTTPException(status_code=409, detail="This count group no longer has pending submissions")
    for row in rows:
        deps.ensure_path_in_scope(current_user, row.path, detail="Count group contains a submission outside your jurisdiction")
    return base, rows


@router.post("/review/{count_id}/approve", dependencies=[Depends(deps.PermissionChecker("counts:review"))])
async def approve_count_group(
    count_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Approve every pending row in the selected program/location/date group."""
    _, rows = await _review_target(db, count_id, current_user)
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
    return {"status": "rejected", "rejected_by_id": str(current_user.user_id), "rejected_at": rejected_at, "reason": reason, "count_ids": [str(row.id) for row in rows]}


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


@router.post("/review/remind", dependencies=[Depends(deps.PermissionChecker("counts:review"))])
async def remind_unreported_location(
    payload: CountReminder,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Send the existing in-app broadcast to one location with no Sunday report."""
    if deps.highest_role_score(current_user) < 3:
        raise HTTPException(status_code=403, detail="A pastor-level reviewer is required to remind a location")
    location = await db.get(Location, payload.location_id)
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
    message = BroadcastMessage(
        sender_id=current_user.user_id, sender_role_score=str(deps.highest_role_score(current_user)),
        target_level="location", path=str(location.path), audience="all_users",
        title="Sunday Worship count reminder",
        content=f"The Sunday Worship population report for {payload.occurrence_date.isoformat()} has not been received. Please submit it through the Field Utility app.",
        priority="normal", sent_at=now,
    )
    db.add(message)
    await db.commit()
    return {"status": "sent", "broadcast_id": str(message.id), "location_id": str(location.location_id), "sent_at": now}


@router.get("/review/unreported", dependencies=[Depends(deps.PermissionChecker("counts:review"))])
async def list_unreported_sunday_locations(
    occurrence_date: date = Query(...),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List uncovered locations for a Sunday so a pastor can send reminders."""
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
