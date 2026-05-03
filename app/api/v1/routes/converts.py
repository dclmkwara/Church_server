"""
Convert routes.
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_records import record as crud_record
from app.schemas.records import RecordCreate, RecordResponse, RecordUpdate
from app.models.user import User

router = APIRouter()


@router.post(
    "/",
    response_model=RecordResponse,
    dependencies=[Depends(deps.PermissionChecker("records:create"))],
)
async def create_convert(
    *,
    db: AsyncSession = Depends(deps.get_db),
    record_in: RecordCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create a convert record."""
    await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=record_in.location_id,
        detail="Convert location outside your scope",
    )
    data = record_in.model_dump()
    data["record_type"] = "convert"
    return await crud_record.create(db, obj_in=RecordCreate(**data), user_id=current_user.user_id)


@router.get(
    "/",
    response_model=List[RecordResponse],
    dependencies=[Depends(deps.PermissionChecker("records:read"))],
)
async def read_converts(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """List convert records with scope filtering."""
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    records = await crud_record.get_multi_by_scope(db, scope_path=search_scope, skip=skip, limit=limit)
    return [r for r in records if r.record_type == "convert"]


@router.put(
    "/{record_id}",
    response_model=RecordResponse,
    dependencies=[Depends(deps.PermissionChecker("records:update"))],
)
async def update_convert(
    *,
    db: AsyncSession = Depends(deps.get_db),
    record_id: UUID,
    record_in: RecordUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a convert record."""
    record = await crud_record.get(db, id=record_id)
    if not record or record.record_type != "convert":
        raise HTTPException(status_code=404, detail="Convert record not found")
    deps.ensure_path_in_scope(current_user, record.path, detail="Convert record outside your scope")
    return await crud_record.update(db, db_obj=record, obj_in=record_in)


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("records:delete"))],
)
async def delete_convert(
    *,
    db: AsyncSession = Depends(deps.get_db),
    record_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a convert record."""
    record = await crud_record.get(db, id=record_id)
    if not record or record.record_type != "convert":
        raise HTTPException(status_code=404, detail="Convert record not found")
    deps.ensure_path_in_scope(current_user, record.path, detail="Convert record outside your scope")
    await crud_record.update(
        db,
        db_obj=record,
        obj_in={"is_deleted": True, "operation": "DELETE"}
    )
    return None
