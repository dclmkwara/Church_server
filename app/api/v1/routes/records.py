"""
Record (newcomer/convert) submission and retrieval routes.
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_records import record as crud_record
from app.schemas.records import RecordCreate, RecordResponse, RecordUpdate
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=RecordResponse)
async def create_record(
    *,
    db: AsyncSession = Depends(deps.get_db),
    record_in: RecordCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit a new newcomer/convert record."""
    return await crud_record.create(db, obj_in=record_in, user_id=current_user.user_id)


@router.get("/", response_model=List[RecordResponse])
async def read_records(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """Retrieve records with scope filtering."""
    search_scope = scope_path if scope_path else str(current_user.path)
    return await crud_record.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )


@router.get("/{record_id}", response_model=RecordResponse)
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
    return record


@router.put("/{record_id}", response_model=RecordResponse)
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
    
    return await crud_record.update(db, db_obj=record, obj_in=record_in)
