"""
Sync Routes.

Handles batch synchronization from offline clients.
"""
from typing import Any, List, Dict, Tuple
from uuid import UUID, uuid5

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select, func, tuple_
from datetime import datetime, timezone
import logging

from app.api import deps
from app.models.location import Fellowship
from app.models.user import User, Worker
from app.models.attendance import WorkerAttendance, WorkerAttendanceSubmission
from app.models.location import Location
from app.models.programs import ProgramEvent
from app.schemas.sync import SyncBatchRequest, SyncBatchResponse, SyncResult
from app.db.filters import scope_filter

# Import CRUD modules
from app.crud.crud_counts import count as crud_count
from app.crud.crud_offerings import offering as crud_offering
from app.crud.crud_records import record as crud_record
from app.crud.crud_attendance import attendance as crud_worker_attendance
from app.crud.workflow_rules import ensure_collection_open, load_event_campaign, require_approved_worker_user
from app.crud.crud_fellowship_activities import (
    member as crud_fellowship_member,
    attendance as crud_fellowship_attendance,
    offering as crud_fellowship_offering
)

router = APIRouter()
logger = logging.getLogger(__name__)
MAX_SYNC_BATCH_RECORDS = 500


def _parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _sync_batch_size(batch: SyncBatchRequest) -> int:
    return (
        len(batch.counts)
        + len(batch.offerings)
        + len(batch.records)
        + len(batch.worker_attendance)
        + len(batch.worker_attendance_submissions)
        + len(batch.fellowship_members)
        + len(batch.fellowship_attendance)
        + len(batch.fellowship_offerings)
    )


async def _ensure_sync_item_in_scope(
    db: AsyncSession,
    current_user: User,
    item: Any,
    scope_cache: Dict[str, bool],
) -> None:
    location_id = getattr(item, "location_id", None)
    if location_id:
        cache_key = f"location:{location_id}"
        if cache_key not in scope_cache:
            await deps.get_location_in_scope(
                db,
                current_user=current_user,
                location_id=location_id,
                detail="Sync item location outside your scope",
            )
            scope_cache[cache_key] = True
        return

    fellowship_id = getattr(item, "fellowship_id", None)
    if fellowship_id:
        cache_key = f"fellowship:{fellowship_id}"
        if cache_key not in scope_cache:
            fellowship = await db.get(Fellowship, fellowship_id)
            if not fellowship:
                raise HTTPException(status_code=404, detail="Fellowship not found")
            deps.ensure_path_in_scope(
                current_user,
                fellowship.path,
                detail="Sync item fellowship outside your scope",
            )
            scope_cache[cache_key] = True


def _scope_filter(model: Any, scope_path: str):
    return scope_filter(model.path, scope_path)


def _changed_since_filter(model: Any, since_dt: datetime, scope_path: str):
    return and_(
        or_(model.created_at > since_dt, model.last_modify > since_dt),
        _scope_filter(model, scope_path),
    )


async def _fetch_changes(
    db: AsyncSession,
    model: Any,
    since_dt: datetime,
    current_user: User,
    limit: int,
    *,
    as_of: datetime,
    position: Dict[str, str] | None = None,
) -> Tuple[List[Any], bool, Dict[str, str] | None]:
    changed_at = func.coalesce(model.last_modify, model.created_at)
    conditions = [
        or_(model.created_at > since_dt, model.last_modify > since_dt),
        changed_at <= as_of,
        deps.scope_condition(model.path, current_user),
    ]
    if position:
        try:
            cursor_time = _parse_iso_datetime(position["changed_at"])
            cursor_id = UUID(position["id"])
        except (KeyError, ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid incremental sync cursor")
        conditions.append(tuple_(changed_at, model.id) > tuple_(cursor_time, cursor_id))
    result = await db.execute(
        select(model)
        .where(*conditions)
        .order_by(changed_at.asc(), model.id.asc())
        .limit(limit + 1)
    )
    rows = result.scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_position = None
    if rows:
        last = rows[-1]
        stamp = last.last_modify or last.created_at
        next_position = {"changed_at": stamp.isoformat(), "id": str(last.id)}
    return rows, has_more, next_position


def _sync_payload(obj: Any, **extra: Any) -> Dict[str, Any]:
    payload = {
        "id": str(obj.id),
        "client_id": str(obj.client_id) if getattr(obj, "client_id", None) else None,
        "operation": getattr(obj, "operation", None),
        "is_deleted": bool(getattr(obj, "is_deleted", False)),
        "last_modify": obj.last_modify.isoformat() if getattr(obj, "last_modify", None) else None,
    }
    payload.update(extra)
    return payload


async def _client_id_conflicts(
    db: AsyncSession,
    model: Any,
    model_key: str,
    scope_path: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    query = select(
        model.client_id.label("client_id"),
        func.count(model.id).label("count")
    ).where(
        model.client_id.isnot(None),
        _scope_filter(model, scope_path)
    ).group_by(model.client_id).having(func.count(model.id) > 1).limit(limit)
    result = await db.execute(query)
    conflicts = []
    for row in result:
        conflicts.append({
            "conflict_id": f"{model_key}:client_id:{row.client_id}",
            "model": model_key,
            "kind": "client_id",
            "client_id": str(row.client_id),
            "count": row.count,
        })
    return conflicts


async def _offerings_key_conflicts(
    db: AsyncSession,
    scope_path: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    from app.models.offerings import Offering
    query = select(
        Offering.location_id,
        Offering.date,
        Offering.event_id,
        Offering.fund_type,
        func.count(Offering.id).label("count"),
    ).where(
        _scope_filter(Offering, scope_path)
    ).group_by(Offering.location_id, Offering.date, Offering.event_id, Offering.fund_type).having(func.count(Offering.id) > 1).limit(limit)
    result = await db.execute(query)
    conflicts = []
    for row in result:
        event_id = row.event_id if row.event_id else "none"
        key = f"{row.location_id}|{row.date.isoformat()}|{event_id}|{row.fund_type}"
        conflicts.append({
            "conflict_id": f"offerings:key:{key}",
            "model": "offerings",
            "kind": "key",
            "location_id": row.location_id,
            "date": str(row.date),
            "event_id": str(row.event_id) if row.event_id else None,
            "fund_type": row.fund_type,
            "count": row.count,
        })
    return conflicts


async def _attendance_key_conflicts(
    db: AsyncSession,
    scope_path: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    from app.models.attendance import WorkerAttendance, WorkerAttendanceSubmission
    query = select(
        WorkerAttendance.worker_id,
        WorkerAttendance.event_id,
        func.count(WorkerAttendance.id).label("count"),
    ).where(
        _scope_filter(WorkerAttendance, scope_path)
    ).group_by(WorkerAttendance.worker_id, WorkerAttendance.event_id).having(func.count(WorkerAttendance.id) > 1).limit(limit)
    result = await db.execute(query)
    conflicts = []
    for row in result:
        key = f"{row.worker_id}|{row.event_id}"
        conflicts.append({
            "conflict_id": f"worker_attendance:key:{key}",
            "model": "worker_attendance",
            "kind": "key",
            "worker_id": str(row.worker_id),
            "event_id": str(row.event_id),
            "count": row.count,
        })
    return conflicts

async def process_sync_list(
    db: AsyncSession, 
    items: List[Any], 
    crud_module: Any, 
    current_user: User,
    scope_cache: Dict[str, bool],
) -> SyncResult:
    """
    Helper to process a list of items for a specific CRUD module.
    Checks idempotency implicitly via the CRUD create method (which should check client_id).
    """
    result = SyncResult()
    results_list = []
    
    for item in items:
        try:
            await _ensure_sync_item_in_scope(db, current_user, item, scope_cache)

            client_id = getattr(item, "client_id", None)
            if client_id is not None:
                existing = (await db.execute(
                    select(crud_module.model).where(crud_module.model.client_id == client_id)
                )).scalars().first()
                if existing is not None:
                    deps.ensure_path_in_scope(
                        current_user, getattr(existing, "path", None),
                        detail="Existing sync record is outside your scope",
                    )
                    result.duplicates += 1
                    results_list.append({
                        "client_id": str(client_id),
                        "id": str(existing.id),
                        "status": "duplicate",
                    })
                    continue

            db_obj = await crud_module.create(
                db, obj_in=item, user_id=current_user.user_id
            )
            
            # How do we know if it was a duplicate?
            # Our CRUD returns the object. If created_at is old, it's a duplicate.
            # Or we can check if we just made it.
            # Ideally CRUD should return a tuple or we check `client_id` manually?
            # For now, let's just mark as synced.
            
            is_duplicate = bool(getattr(db_obj, "_was_duplicate_submission", False))
            if is_duplicate:
                deps.ensure_path_in_scope(
                    current_user, getattr(db_obj, "path", None),
                    detail="Existing sync record is outside your scope",
                )
                result.duplicates += 1
            else:
                result.synced += 1
            
            results_list.append({
                "client_id": item.client_id,
                "id": db_obj.id,
                "status": "duplicate" if is_duplicate else "synced",
                "outcome": "duplicate" if is_duplicate else "created",
            })
            
        except Exception as e:
            await db.rollback()
            result.errors += 1
            if isinstance(e, HTTPException):
                error_detail = str(e.detail)
            else:
                logger.exception("Sync item processing failed")
                error_detail = "Unable to process this sync item"
            results_list.append({
                "client_id": getattr(item, 'client_id', None),
                "error": error_detail,
                "status": "error",
                "outcome": "error",
            })
            
    result.details = results_list
    return result


async def process_attendance_submissions(
    db: AsyncSession,
    items: list[Any],
    current_user: User,
    scope_cache: Dict[str, bool],
) -> SyncResult:
    """Atomically persist one aggregate capture and its report-friendly worker rows."""
    from fastapi import HTTPException

    result = SyncResult()
    details = []
    for item in items:
        try:
            await _ensure_sync_item_in_scope(db, current_user, item, scope_cache)
            existing = (await db.execute(
                select(WorkerAttendanceSubmission).where(
                    WorkerAttendanceSubmission.client_id == item.client_id
                )
            )).scalars().first()
            if existing:
                deps.ensure_path_in_scope(current_user, existing.path, detail="Existing attendance submission is outside your scope")
                result.duplicates += 1
                details.append({"client_id": str(item.client_id), "id": str(existing.id), "status": "duplicate"})
                continue

            await require_approved_worker_user(db, current_user.user_id)
            if item.submitted_by_worker_id and item.submitted_by_worker_id != current_user.worker_id:
                raise HTTPException(status_code=403, detail="Attendance submitter must match the signed-in worker")
            location = await db.get(Location, item.location_id)
            if not location:
                raise HTTPException(status_code=404, detail="Location not found")
            if item.church_type.strip().lower() != location.church_type.strip().lower():
                raise HTTPException(status_code=422, detail="Church section does not match this location")
            if str(item.program_domain or "").lower() not in {"weekly", "retreat", "conference"} or not any(
                token in item.program_type.lower() for token in ("worker", "leader", "leadership", "overseer")
            ):
                raise HTTPException(status_code=422, detail="Worker attendance is only accepted for worker or leader meetings, conferences, and retreats")
            event = await db.get(ProgramEvent, item.event_id) if item.event_id else None
            if item.event_id and (not event or event.is_deleted):
                raise HTTPException(status_code=404, detail="Scheduled program was not found")
            if event:
                campaign = await load_event_campaign(db, event)
                ensure_collection_open(event, campaign, kind="attendance")
                if str(location.path) != str(event.path) and not str(location.path).startswith(f"{event.path}."):
                    raise HTTPException(status_code=400, detail="Location must fall within the selected program scope")
                if event.date != item.date.date():
                    raise HTTPException(status_code=400, detail="Attendance date must match the scheduled program date")

            worker_ids = [worker.worker_id for worker in item.present_workers]
            worker_result = await db.execute(select(Worker).where(
                Worker.worker_id.in_(worker_ids),
                Worker.location_id == item.location_id,
                Worker.is_deleted.is_(False),
                Worker.approval_status == "approved",
            ))
            workers = {worker.worker_id: worker for worker in worker_result.scalars().all()}
            missing_ids = set(worker_ids) - set(workers)
            if missing_ids:
                raise HTTPException(status_code=422, detail="One or more selected workers are no longer approved at this location. Refresh the roster and try again.")

            roster_count_result = await db.execute(select(func.count(Worker.worker_id)).where(
                Worker.location_id == item.location_id,
                Worker.is_deleted.is_(False),
                Worker.approval_status == "approved",
            ))
            actual_roster_count = int(roster_count_result.scalar_one())
            if item.expected_workers_count != actual_roster_count:
                raise HTTPException(status_code=409, detail="The approved worker roster changed. Refresh the roster before submitting attendance.")

            duplicate_query = select(WorkerAttendance.worker_id).where(
                WorkerAttendance.location_id == item.location_id,
                WorkerAttendance.worker_id.in_(worker_ids),
                WorkerAttendance.is_deleted.is_(False),
                WorkerAttendance.event_id == item.event_id if item.event_id else (
                    WorkerAttendance.event_id.is_(None) & (WorkerAttendance.date == item.date)
                ),
            ).limit(1)
            if (await db.execute(duplicate_query)).scalar_one_or_none() is not None:
                raise HTTPException(status_code=409, detail="At least one selected worker is already recorded for this service. Refresh attendance to avoid duplicate counts.")

            path = str(location.path)
            submission = WorkerAttendanceSubmission(
                client_id=item.client_id, path=path, location_id=item.location_id,
                event_id=item.event_id, date=item.date,
                church_type=item.church_type or location.church_type,
                program_domain=item.program_domain, program_type=item.program_type,
                expected_workers_count=actual_roster_count,
                present_count=len(workers),
                present_workers=[{
                    "worker_id": str(workers[worker_id].worker_id),
                    "worker_name": workers[worker_id].name,
                } for worker_id in worker_ids],
                entered_by_id=current_user.user_id,
                submitted_by_worker_id=current_user.worker_id,
                submitted_by_name=current_user.name,
                note=item.note,
            )
            db.add(submission)
            await db.flush()
            for worker_id in worker_ids:
                worker = workers[worker_id]
                db.add(WorkerAttendance(
                    submission_id=submission.id,
                    client_id=uuid5(item.client_id, str(worker_id)),
                    path=path, location_id=item.location_id, event_id=item.event_id,
                    date=item.date,
                    church_type=item.church_type or location.church_type,
                    program_domain=item.program_domain, program_type=item.program_type,
                    worker_id=worker.worker_id, worker_name=worker.name,
                    worker_phone=worker.phone, worker_unit=worker.unit,
                    status="present", entered_by_id=current_user.user_id,
                ))
            await db.commit()
            result.synced += 1
            details.append({"client_id": str(item.client_id), "id": str(submission.id), "status": "synced", "present_count": len(workers)})
        except Exception as exc:
            await db.rollback()
            result.errors += 1
            message = str(exc.detail) if isinstance(exc, HTTPException) else "Unable to process this attendance submission"
            if not isinstance(exc, HTTPException):
                logger.exception("Aggregate attendance sync failed")
            details.append({"client_id": str(item.client_id), "status": "error", "error": message})
    result.details = details
    return result


@router.post(
    "/batch",
    response_model=SyncBatchResponse,
    dependencies=[Depends(deps.PermissionChecker("sync:batch"))],
)
async def batch_sync(
    *,
    db: AsyncSession = Depends(deps.get_db),
    batch: SyncBatchRequest,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Batch upload synchronization.
    Accepts lists of records, processes them (preventing duplicates), and returns status.
    """
    total_records = _sync_batch_size(batch)
    if total_records > MAX_SYNC_BATCH_RECORDS:
        raise HTTPException(
            status_code=413,
            detail=f"Batch contains {total_records} records; maximum is {MAX_SYNC_BATCH_RECORDS}.",
        )
    scope_cache: Dict[str, bool] = {}
    
    # Process each list
    counts_res = await process_sync_list(db, batch.counts, crud_count, current_user, scope_cache)
    offerings_res = await process_sync_list(db, batch.offerings, crud_offering, current_user, scope_cache)
    records_res = await process_sync_list(db, batch.records, crud_record, current_user, scope_cache)
    worker_att_res = await process_sync_list(db, batch.worker_attendance, crud_worker_attendance, current_user, scope_cache)
    worker_att_submissions_res = await process_attendance_submissions(
        db, batch.worker_attendance_submissions, current_user, scope_cache
    )
    
    fel_mem_res = await process_sync_list(db, batch.fellowship_members, crud_fellowship_member, current_user, scope_cache)
    fel_att_res = await process_sync_list(db, batch.fellowship_attendance, crud_fellowship_attendance, current_user, scope_cache)
    fel_off_res = await process_sync_list(db, batch.fellowship_offerings, crud_fellowship_offering, current_user, scope_cache)
    
    return SyncBatchResponse(
        counts=counts_res,
        offerings=offerings_res,
        records=records_res,
        worker_attendance=worker_att_res,
        worker_attendance_submissions=worker_att_submissions_res,
        fellowship_members=fel_mem_res,
        fellowship_attendance=fel_att_res,
        fellowship_offerings=fel_off_res
    )


@router.get(
    "/changes",
    dependencies=[Depends(deps.PermissionChecker("sync:read_changes"))],
)
async def get_incremental_changes(
    *,
    db: AsyncSession = Depends(deps.get_db),
    since: str = Query(..., description="ISO timestamp of last sync"),
    limit: int = Query(500, ge=1, le=1000, description="Maximum changed records per bucket"),
    cursor: str | None = Query(None, description="Opaque continuation cursor returned by the previous page"),
    current_user: User = Depends(deps.get_current_active_user),
) -> Dict[str, Any]:
    """
    Get incremental changes since a specific timestamp.

    On the first request omit `cursor`. If `sync.has_more` is true, send the
    returned `sync.next_cursor` with the same `since` value until the server
    returns `has_more=false`; then start the next cycle with `sync.next_since`.
    The existing resource arrays remain unchanged for older clients.
    """
    from app.models.counts import Count
    from app.models.offerings import Offering
    from app.models.records import Record
    from app.models.attendance import WorkerAttendance
    from app.models.fellowship_activities import FellowshipMember, FellowshipAttendance, FellowshipOffering
    
    import json
    try:
        since_dt = _parse_iso_datetime(since)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format. Use ISO 8601.")

    try:
        cursor_data = json.loads(cursor) if cursor else {}
        if not isinstance(cursor_data, dict):
            raise ValueError
        as_of = _parse_iso_datetime(cursor_data.get("as_of", datetime.now(timezone.utc).isoformat()))
        positions = cursor_data.get("positions", {})
        if not isinstance(positions, dict):
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid incremental sync cursor")
    
    # Get user's scope path
    bucket_models = {
        "counts": Count,
        "offerings": Offering,
        "records": Record,
        "worker_attendance": WorkerAttendance,
        "worker_attendance_submissions": WorkerAttendanceSubmission,
        "fellowship_members": FellowshipMember,
        "fellowship_attendance": FellowshipAttendance,
        "fellowship_offerings": FellowshipOffering,
    }
    pages = {}
    next_positions = {}
    has_more = {}
    for name, model in bucket_models.items():
        rows, more, next_position = await _fetch_changes(
            db, model, since_dt, current_user, limit,
            as_of=as_of,
            position=positions.get(name),
        )
        pages[name] = rows
        has_more[name] = more
        if next_position:
            next_positions[name] = next_position
        elif name in positions:
            next_positions[name] = positions[name]

    counts = pages["counts"]
    offerings = pages["offerings"]
    records = pages["records"]
    worker_attendance = pages["worker_attendance"]
    worker_attendance_submissions = pages["worker_attendance_submissions"]
    fellowship_members = pages["fellowship_members"]
    fellowship_attendance = pages["fellowship_attendance"]
    fellowship_offerings = pages["fellowship_offerings"]
    more_changes = any(has_more.values())
    
    return {
        "since": since,
        "counts": [_sync_payload(c, date=str(c.date), location_id=c.location_id) for c in counts],
        "offerings": [_sync_payload(o, date=str(o.date), location_id=o.location_id) for o in offerings],
        "records": [_sync_payload(r, location_id=r.location_id, record_type=r.record_type) for r in records],
        "worker_attendance": [
            _sync_payload(a, location_id=a.location_id, worker_id=str(a.worker_id), event_id=str(a.event_id))
            for a in worker_attendance
        ],
        "worker_attendance_submissions": [
            _sync_payload(
                submission,
                location_id=submission.location_id,
                event_id=str(submission.event_id) if submission.event_id else None,
                date=submission.date.isoformat(),
                present_count=submission.present_count,
                expected_workers_count=submission.expected_workers_count,
                present_workers=submission.present_workers,
                entered_by_id=str(submission.entered_by_id),
                submitted_by_worker_id=str(submission.submitted_by_worker_id) if submission.submitted_by_worker_id else None,
                submitted_by_name=submission.submitted_by_name,
            )
            for submission in worker_attendance_submissions
        ],
        "fellowship_members": [
            _sync_payload(m, fellowship_id=m.fellowship_id)
            for m in fellowship_members
        ],
        "fellowship_attendance": [
            _sync_payload(a, fellowship_id=a.fellowship_id, date=str(a.date))
            for a in fellowship_attendance
        ],
        "fellowship_offerings": [
            _sync_payload(o, fellowship_id=o.fellowship_id, date=str(o.date))
            for o in fellowship_offerings
        ],
        "total_changes": (
            len(counts)
            + len(offerings)
            + len(records)
            + len(worker_attendance)
            + len(worker_attendance_submissions)
            + len(fellowship_members)
            + len(fellowship_attendance)
            + len(fellowship_offerings)
        ),
        "sync": {
            "has_more": more_changes,
            "as_of": as_of.isoformat(),
            "next_since": None if more_changes else as_of.isoformat(),
            "next_cursor": json.dumps({"as_of": as_of.isoformat(), "positions": next_positions}) if more_changes else None,
            "buckets": {
                name: {"has_more": has_more[name], "count": len(pages[name])}
                for name in bucket_models
            },
        },
    }


@router.get(
    "/conflicts",
    dependencies=[Depends(deps.PermissionChecker("sync:conflicts"))],
)
async def get_sync_conflicts(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Dict[str, Any]:
    """
    Get unresolved sync conflicts.
    
    Returns records that have potential conflicts (e.g., duplicate client_ids,
    same date/location combinations, etc.)
    """
    scope_path = deps.effective_scope_path(current_user)
    conflicts: List[Dict[str, Any]] = []

    from app.models.counts import Count
    from app.models.offerings import Offering
    from app.models.records import Record
    from app.models.attendance import WorkerAttendance
    from app.models.fellowship_activities import FellowshipMember, FellowshipAttendance, FellowshipOffering

    conflicts.extend(await _client_id_conflicts(db, Count, "counts", scope_path))
    conflicts.extend(await _client_id_conflicts(db, Offering, "offerings", scope_path))
    conflicts.extend(await _client_id_conflicts(db, Record, "records", scope_path))
    conflicts.extend(await _client_id_conflicts(db, WorkerAttendance, "worker_attendance", scope_path))
    conflicts.extend(await _client_id_conflicts(db, FellowshipMember, "fellowship_members", scope_path))
    conflicts.extend(await _client_id_conflicts(db, FellowshipAttendance, "fellowship_attendance", scope_path))
    conflicts.extend(await _client_id_conflicts(db, FellowshipOffering, "fellowship_offerings", scope_path))

    conflicts.extend(await _offerings_key_conflicts(db, scope_path))
    conflicts.extend(await _attendance_key_conflicts(db, scope_path))

    return {
        "conflicts": conflicts,
        "total": len(conflicts),
    }


@router.post(
    "/resolve",
    dependencies=[Depends(deps.PermissionChecker("sync:resolve"))],
)
async def resolve_conflict(
    *,
    db: AsyncSession = Depends(deps.get_db),
    conflict_id: str = Body(..., embed=True),
    resolution: str = Body(..., embed=True),  # "keep_server" | "keep_client" | "merge"
    current_user: User = Depends(deps.get_current_active_user),
) -> Dict[str, Any]:
    """
    Resolve a sync conflict.
    
    Applies the chosen resolution strategy to a conflicted record.
    """
    parts = conflict_id.split(":", 2)
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="Invalid conflict_id format")
    model_key, kind, key = parts

    scope_path = deps.effective_scope_path(current_user)

    model_map = {
        "counts": "Count",
        "offerings": "Offering",
        "records": "Record",
        "worker_attendance": "WorkerAttendance",
        "fellowship_members": "FellowshipMember",
        "fellowship_attendance": "FellowshipAttendance",
        "fellowship_offerings": "FellowshipOffering",
    }
    if model_key not in model_map:
        raise HTTPException(status_code=400, detail="Unknown model key")

    from app.models.counts import Count
    from app.models.offerings import Offering
    from app.models.records import Record
    from app.models.attendance import WorkerAttendance
    from app.models.fellowship_activities import FellowshipMember, FellowshipAttendance, FellowshipOffering

    model_lookup = {
        "counts": Count,
        "offerings": Offering,
        "records": Record,
        "worker_attendance": WorkerAttendance,
        "fellowship_members": FellowshipMember,
        "fellowship_attendance": FellowshipAttendance,
        "fellowship_offerings": FellowshipOffering,
    }
    model = model_lookup[model_key]

    records = []
    if kind == "client_id":
        try:
            client_uuid = UUID(key)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid client_id format")
        query = select(model).where(
            model.client_id == client_uuid,
            _scope_filter(model, scope_path)
        )
        records = (await db.execute(query)).scalars().all()
        if len(records) < 2:
            return {"success": True, "message": "No conflict to resolve"}
        records.sort(key=lambda r: r.created_at or datetime.min)
        if resolution == "keep_client":
            keep = records[0]
            delete = records[1:]
        elif resolution == "keep_server":
            keep = records[-1]
            delete = records[:-1]
        elif resolution == "merge":
            raise HTTPException(status_code=400, detail="Merge not supported for client_id conflicts")
        else:
            raise HTTPException(status_code=400, detail="Invalid resolution strategy")
    elif kind == "key":
        if model_key == "counts":
            raise HTTPException(
                status_code=400,
                detail="Population counts are independent submissions; event/location is not a duplicate key",
            )
        elif model_key == "offerings":
            raise HTTPException(
                status_code=409,
                detail="Offering key collisions require financial reconciliation; automatic resolution is disabled",
            )
            parts_key = key.split("|")
            if len(parts_key) != 4:
                raise HTTPException(status_code=400, detail="Invalid key format")
            location_id, date_str, event_id, fund_type = parts_key
            date_val = _parse_iso_datetime(date_str)
            event_val = None if event_id in ("none", "null", "") else UUID(event_id)
            query = select(Offering).where(
                Offering.location_id == location_id,
                Offering.date == date_val,
                Offering.event_id == event_val,
                Offering.fund_type == fund_type,
                _scope_filter(Offering, scope_path),
            )
            records = (await db.execute(query)).scalars().all()
        elif model_key == "worker_attendance":
            raise HTTPException(
                status_code=409,
                detail="Attendance key collisions require review; automatic resolution is disabled",
            )
            parts_key = key.split("|")
            if len(parts_key) != 2:
                raise HTTPException(status_code=400, detail="Invalid key format")
            worker_id, event_id = parts_key
            query = select(WorkerAttendance).where(
                WorkerAttendance.worker_id == UUID(worker_id),
                WorkerAttendance.event_id == UUID(event_id),
                _scope_filter(WorkerAttendance, scope_path),
            )
            records = (await db.execute(query)).scalars().all()
        else:
            raise HTTPException(status_code=400, detail="Key conflicts not supported for this model")

        if len(records) < 2:
            return {"success": True, "message": "No conflict to resolve"}
        records.sort(key=lambda r: r.created_at or datetime.min)
        if resolution == "keep_client":
            keep = records[0]
            delete = records[1:]
        elif resolution == "keep_server":
            keep = records[-1]
            delete = records[:-1]
        elif resolution == "merge":
            keep = records[-1]
            delete = [r for r in records if r is not keep]
            if model_key == "offerings":
                keep.amount = sum(r.amount or 0 for r in records)
                keep.operation = "UPDATE"
                keep.last_modify = datetime.utcnow()
            elif model_key == "worker_attendance":
                raise HTTPException(status_code=400, detail="Merge not supported for attendance conflicts")
        else:
            raise HTTPException(status_code=400, detail="Invalid resolution strategy")
    else:
        raise HTTPException(status_code=400, detail="Invalid conflict kind")

    for obj in delete:
        if hasattr(obj, "is_deleted"):
            obj.is_deleted = True
            obj.operation = "DELETE"
            obj.last_modify = datetime.utcnow()
        db.add(obj)
    db.add(keep)
    await db.commit()

    return {
        "success": True,
        "message": f"Conflict {conflict_id} resolved using strategy: {resolution}",
        "kept_id": str(keep.id),
        "deleted_count": len(delete),
    }

