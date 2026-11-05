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
    if not record_in.assignment_id:
        await deps.get_location_in_scope(
            db,
            current_user=current_user,
            location_id=record_in.location_id,
            detail="Record location outside your scope",
        )
    created = await crud_record.create(
        db,
        obj_in=record_in,
        user_id=current_user.user_id,
        require_assignment=deps.highest_role_score(current_user) == 1,
    )
    if not record_in.assignment_id:
        deps.ensure_path_in_scope(current_user, created.path, detail="Existing record is outside your scope")
    return created


@router.get(
    "/",
    response_model=List[RecordResponse],
    dependencies=[Depends(deps.PermissionChecker("records:read"))],
)
async def read_records(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """Retrieve records with scope filtering."""
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    rows = await crud_record.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )
    return deps.filter_rows_in_scope(rows, current_user)


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
    if any(item.client_id is None for item in items):
        raise HTTPException(status_code=422, detail="Every record batch item requires a stable client_id")
    result = SyncResult()
    details = []
    for item in items:
        try:
            await deps.get_location_in_scope(
                db, current_user=current_user, location_id=item.location_id,
                detail="Record location outside your scope",
            )
            existing = None
            if item.client_id:
                existing = await crud_record.get_by_client_id(db, client_id=item.client_id)
            if existing:
                deps.ensure_path_in_scope(current_user, existing.path, detail="Existing record is outside your scope")
                result.duplicates += 1
                details.append({"client_id": item.client_id, "id": existing.id, "status": "duplicate"})
                continue
            created = await crud_record.create(db, obj_in=item, user_id=current_user.user_id)
            is_duplicate = bool(getattr(created, "_was_duplicate_submission", False))
            deps.ensure_path_in_scope(current_user, created.path, detail="Existing record is outside your scope")
            result.duplicates += int(is_duplicate)
            result.synced += int(not is_duplicate)
            details.append({"client_id": item.client_id, "id": created.id, "status": "duplicate" if is_duplicate else "synced"})
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
