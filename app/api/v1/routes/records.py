"""
Record (newcomer/convert) submission and retrieval routes.
"""
from typing import Any, List
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_records import record as crud_record
from app.schemas.records import RecordCreate, RecordResponse, RecordUpdate
from app.schemas.sync import SyncResult
from app.models.user import User

router = APIRouter()


@router.post(
    "/",
    response_model=RecordResponse,
    dependencies=[Depends(deps.PermissionChecker("records:create"))],
)
async def create_record(
    *,
    db: AsyncSession = Depends(deps.get_db),
    record_in: RecordCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit a new newcomer/convert record."""
    await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=record_in.location_id,
        detail="Record location outside your scope",
    )
    return await crud_record.create(db, obj_in=record_in, user_id=current_user.user_id)


@router.get(
    "/",
    response_model=List[RecordResponse],
    dependencies=[Depends(deps.PermissionChecker("records:read"))],
)
async def read_records(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """Retrieve records with scope filtering."""
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    return await crud_record.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )


@router.get(
    "/{record_id}",
    response_model=RecordResponse,
    dependencies=[Depends(deps.PermissionChecker("records:read"))],
)
async def read_record(
    *,
    db: AsyncSession = Depends(deps.get_db),
    record_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a specific record by ID."""
    record = await crud_record.get(db, id=record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    deps.ensure_path_in_scope(current_user, record.path, detail="Record outside your scope")
    return record


@router.put(
    "/{record_id}",
    response_model=RecordResponse,
    dependencies=[Depends(deps.PermissionChecker("records:update"))],
)
async def update_record(
    *,
    db: AsyncSession = Depends(deps.get_db),
    record_id: UUID,
    record_in: RecordUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a record."""
    record = await crud_record.get(db, id=record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    deps.ensure_path_in_scope(current_user, record.path, detail="Record outside your scope")
    
    return await crud_record.update(db, db_obj=record, obj_in=record_in)


@router.post(
    "/batch",
    response_model=SyncResult,
    dependencies=[Depends(deps.PermissionChecker("records:create"))],
)
async def batch_create_records(
    *,
    db: AsyncSession = Depends(deps.get_db),
    items: List[RecordCreate],
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Batch submit records (offline sync convenience)."""
    result = SyncResult()
    details = []
    for item in items:
        try:
            existing = None
            if item.client_id:
                existing = await crud_record.get_by_client_id(db, client_id=item.client_id)
            if existing:
                result.duplicates += 1
                details.append({"client_id": item.client_id, "id": existing.id, "status": "duplicate"})
                continue
            await deps.get_location_in_scope(
                db,
                current_user=current_user,
                location_id=item.location_id,
                detail="Record location outside your scope",
            )
            created = await crud_record.create(db, obj_in=item, user_id=current_user.user_id)
            result.synced += 1
            details.append({"client_id": item.client_id, "id": created.id, "status": "synced"})
        except Exception as e:
            await db.rollback()
            result.errors += 1
            details.append({"client_id": item.client_id, "error": str(e), "status": "error"})
    result.details = details
    return result


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("records:delete"))],
)
async def delete_record(
    *,
    db: AsyncSession = Depends(deps.get_db),
    record_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a record."""
    record = await crud_record.get(db, id=record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    deps.ensure_path_in_scope(current_user, record.path, detail="Record outside your scope")
    
    await crud_record.update(
        db,
        db_obj=record,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None
