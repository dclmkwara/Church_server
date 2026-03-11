"""
Newcomer routes.
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
async def create_newcomer(
    *,
    db: AsyncSession = Depends(deps.get_db),
    record_in: RecordCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create a newcomer record."""
    data = record_in.model_dump()
    data["record_type"] = "newcomer"
    return await crud_record.create(db, obj_in=RecordCreate(**data), user_id=current_user.user_id)


@router.get(
    "/",
    response_model=List[RecordResponse],
    dependencies=[Depends(deps.PermissionChecker("records:read"))],
)
async def read_newcomers(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """List newcomer records with scope filtering."""
    search_scope = scope_path if scope_path else str(current_user.path)
    records = await crud_record.get_multi_by_scope(db, scope_path=search_scope, skip=skip, limit=limit)
    return [r for r in records if r.record_type == "newcomer"]


@router.put(
    "/{record_id}",
    response_model=RecordResponse,
    dependencies=[Depends(deps.PermissionChecker("records:update"))],
)
async def update_newcomer(
    *,
    db: AsyncSession = Depends(deps.get_db),
    record_id: UUID,
    record_in: RecordUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a newcomer record."""
    record = await crud_record.get(db, id=record_id)
    if not record or record.record_type != "newcomer":
        raise HTTPException(status_code=404, detail="Newcomer record not found")
    return await crud_record.update(db, db_obj=record, obj_in=record_in)


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("records:delete"))],
)
async def delete_newcomer(
    *,
    db: AsyncSession = Depends(deps.get_db),
    record_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a newcomer record."""
    record = await crud_record.get(db, id=record_id)
    if not record or record.record_type != "newcomer":
        raise HTTPException(status_code=404, detail="Newcomer record not found")
    await crud_record.update(
        db,
        db_obj=record,
        obj_in={"is_deleted": True, "operation": "DELETE"}
    )
    return None
