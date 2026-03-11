"""
Sync Routes.

Handles batch synchronization from offline clients.
"""
from typing import Any, List, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime

from app.api import deps
from app.models.user import User
from app.schemas.sync import SyncBatchRequest, SyncBatchResponse, SyncResult

# Import CRUD modules
from app.crud.crud_counts import count as crud_count
from app.crud.crud_offerings import offering as crud_offering
from app.crud.crud_records import record as crud_record
from app.crud.crud_attendance import attendance as crud_worker_attendance
from app.crud.crud_fellowship_activities import (
    member as crud_fellowship_member,
    attendance as crud_fellowship_attendance,
    offering as crud_fellowship_offering
)

router = APIRouter()


def _parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


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
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
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


async def _counts_key_conflicts(
    db: AsyncSession,
    scope_path: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    from app.models.counts import Count
    query = select(
        Count.location_id,
        Count.date,
        Count.event_id,
        func.count(Count.id).label("count"),
    ).where(
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
    ).group_by(Count.location_id, Count.date, Count.event_id).having(func.count(Count.id) > 1).limit(limit)
    result = await db.execute(query)
    conflicts = []
    for row in result:
        event_id = row.event_id if row.event_id else "none"
        key = f"{row.location_id}|{row.date.isoformat()}|{event_id}"
        conflicts.append({
            "conflict_id": f"counts:key:{key}",
            "model": "counts",
            "kind": "key",
            "location_id": row.location_id,
            "date": str(row.date),
            "event_id": str(row.event_id) if row.event_id else None,
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
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
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
    from app.models.attendance import WorkerAttendance
    query = select(
        WorkerAttendance.worker_id,
        WorkerAttendance.event_id,
        func.count(WorkerAttendance.id).label("count"),
    ).where(
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
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
    user_id: UUID
) -> SyncResult:
    """
    Helper to process a list of items for a specific CRUD module.
    Checks idempotency implicitly via the CRUD create method (which should check client_id).
    """
    result = SyncResult()
    results_list = []
    
    for item in items:
        try:
            # Most CRUD create methods we built accept `obj_in` and `user_id` (except some maybe)
            # We need to standardize or handle exceptions.
            # Our CRUD methods currently check client_id and return existing if found.
            
            # Note: Not all CRUD create methods accept user_id (e.g. FellowshipMember).
            # We'll need a quick check or try/except, or standardizing.
            
            # Simple check for user_id requirement based on model type? 
            # Or just pass it as kwarg and let python ignore if not needed? No, that throws generic error.
            # Let's check signatures or just try/except.
            
            # Inspecting our code:
            # - Count, Offering, Record, WorkerAttendance, FellowshipAttendance, FellowshipOffering: accept user_id
            # - FellowshipMember: DOES NOT accept user_id (only obj_in)
            
            # Warning: This is a bit fragile. 
            
            if crud_module == crud_fellowship_member:
                 db_obj = await crud_module.create(db, obj_in=item)
            else:
                 # Standard logic with user_id
                 db_obj = await crud_module.create(db, obj_in=item, user_id=user_id)
            
            # How do we know if it was a duplicate?
            # Our CRUD returns the object. If created_at is old, it's a duplicate.
            # Or we can check if we just made it.
            # Ideally CRUD should return a tuple or we check `client_id` manually?
            # For now, let's just mark as synced.
            
            status = "synced"
            # If we wanted to distinguish, we'd need CRUD changes.
            # For MVP Sync, just returning the ID is sufficient for client to map.
            
            results_list.append({
                "client_id": item.client_id,
                "id": db_obj.id,
                "status": status
            })
            result.synced += 1
            
        except Exception as e:
            result.errors += 1
            results_list.append({
                "client_id": getattr(item, 'client_id', None),
                "error": str(e),
                "status": "error"
            })
            
    result.details = results_list
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
    
    # Process each list
    counts_res = await process_sync_list(db, batch.counts, crud_count, current_user.user_id)
    offerings_res = await process_sync_list(db, batch.offerings, crud_offering, current_user.user_id)
    records_res = await process_sync_list(db, batch.records, crud_record, current_user.user_id)
    worker_att_res = await process_sync_list(db, batch.worker_attendance, crud_worker_attendance, current_user.user_id)
    
    fel_mem_res = await process_sync_list(db, batch.fellowship_members, crud_fellowship_member, current_user.user_id)
    fel_att_res = await process_sync_list(db, batch.fellowship_attendance, crud_fellowship_attendance, current_user.user_id)
    fel_off_res = await process_sync_list(db, batch.fellowship_offerings, crud_fellowship_offering, current_user.user_id)
    
    return SyncBatchResponse(
        counts=counts_res,
        offerings=offerings_res,
        records=records_res,
        worker_attendance=worker_att_res,
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
    current_user: User = Depends(deps.get_current_active_user),
) -> Dict[str, Any]:
    """
    Get incremental changes since a specific timestamp.
    
    Returns only records created/updated after the given timestamp,
    filtered by user's scope. More efficient than full batch sync.
    """
    from datetime import datetime
    from app.models.counts import Count
    from app.models.offerings import Offering
    from app.models.records import Record
    from app.models.attendance import WorkerAttendance
    from sqlalchemy import and_, text
    
    try:
        since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid timestamp format. Use ISO 8601.")
    
    # Get user's scope path
    scope_path = str(current_user.path)
    
    # Query each table for changes
    counts_query = select(Count).where(
        and_(
            Count.created_at > since_dt,
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
        )
    ).limit(1000)
    
    offerings_query = select(Offering).where(
        and_(
            Offering.created_at > since_dt,
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
        )
    ).limit(1000)
    
    records_query = select(Record).where(
        and_(
            Record.created_at > since_dt,
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
        )
    ).limit(1000)
    
    # Execute queries
    counts = (await db.execute(counts_query)).scalars().all()
    offerings = (await db.execute(offerings_query)).scalars().all()
    records = (await db.execute(records_query)).scalars().all()
    
    return {
        "since": since,
        "counts": [{"id": str(c.id), "client_id": c.client_id, "date": str(c.date)} for c in counts],
        "offerings": [{"id": str(o.id), "client_id": o.client_id, "date": str(o.date)} for o in offerings],
        "records": [{"id": str(r.id), "client_id": r.client_id} for r in records],
        "total_changes": len(counts) + len(offerings) + len(records)
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
    scope_path = str(current_user.path)
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

    conflicts.extend(await _counts_key_conflicts(db, scope_path))
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

    scope_path = str(current_user.path)

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
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
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
            parts_key = key.split("|")
            if len(parts_key) != 3:
                raise HTTPException(status_code=400, detail="Invalid key format")
            location_id, date_str, event_id = parts_key
            date_val = _parse_iso_datetime(date_str)
            event_val = None if event_id in ("none", "null", "") else UUID(event_id)
            query = select(Count).where(
                Count.location_id == location_id,
                Count.date == date_val,
                Count.event_id == event_val,
                text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path),
            )
            records = (await db.execute(query)).scalars().all()
        elif model_key == "offerings":
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
                text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path),
            )
            records = (await db.execute(query)).scalars().all()
        elif model_key == "worker_attendance":
            parts_key = key.split("|")
            if len(parts_key) != 2:
                raise HTTPException(status_code=400, detail="Invalid key format")
            worker_id, event_id = parts_key
            query = select(WorkerAttendance).where(
                WorkerAttendance.worker_id == UUID(worker_id),
                WorkerAttendance.event_id == UUID(event_id),
                text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path),
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
            if model_key == "counts":
                keep.adult_male = sum(r.adult_male or 0 for r in records)
                keep.adult_female = sum(r.adult_female or 0 for r in records)
                keep.youth_male = sum(r.youth_male or 0 for r in records)
                keep.youth_female = sum(r.youth_female or 0 for r in records)
                keep.boys = sum(r.boys or 0 for r in records)
                keep.girls = sum(r.girls or 0 for r in records)
                keep.calculate_total()
                keep.operation = "UPDATE"
                keep.last_modify = datetime.utcnow()
            elif model_key == "offerings":
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

