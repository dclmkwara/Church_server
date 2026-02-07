"""
Sync Routes.

Handles batch synchronization from offline clients.
"""
from typing import Any, List, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession

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


@router.post("/batch", response_model=SyncBatchResponse)
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


@router.get("/changes")
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
    from app.models.data_collection import Count, Offering, Record, WorkerAttendance
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


@router.get("/conflicts")
async def get_sync_conflicts(
    *,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Dict[str, Any]:
    """
    Get unresolved sync conflicts.
    
    Returns records that have potential conflicts (e.g., duplicate client_ids,
    same date/location combinations, etc.)
    
    Note: This is a placeholder. Full conflict detection requires
    additional tracking tables or status fields.
    """
    # In a full implementation, you'd have a conflicts table
    # For now, return empty list as conflicts are handled during sync
    
    return {
        "conflicts": [],
        "message": "Conflict detection is handled during batch sync. Duplicates are automatically ignored."
    }


@router.post("/resolve")
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
    
    Note: This is a placeholder. Full conflict resolution requires
    additional conflict tracking infrastructure.
    """
    # In a full implementation, you'd:
    # 1. Fetch the conflict record
    # 2. Apply the resolution strategy
    # 3. Update both client and server records
    # 4. Mark conflict as resolved
    
    return {
        "success": True,
        "message": f"Conflict {conflict_id} resolved using strategy: {resolution}",
        "note": "Full conflict resolution will be implemented in Phase 2"
    }

