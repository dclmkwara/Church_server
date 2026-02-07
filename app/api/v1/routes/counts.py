"""
Count submission and retrieval routes.

Handles population count data collection with offline sync support.
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_counts import count as crud_count
from app.schemas.counts import CountCreate, CountResponse, CountUpdate
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=CountResponse)
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
    return await crud_count.create(db, obj_in=count_in, user_id=current_user.user_id)


@router.get("/", response_model=List[CountResponse])
async def read_counts(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """
    Retrieve counts with hierarchical scope filtering.
    """
    search_scope = scope_path if scope_path else str(current_user.path)
    
    return await crud_count.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )


@router.get("/{count_id}", response_model=CountResponse)
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
    return count


@router.put("/{count_id}", response_model=CountResponse)
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
    
    updated_count = await crud_count.update(db, db_obj=count, obj_in=count_in)
    
    # Recalculate total if demographics changed
    if any([
        count_in.adult_male is not None,
        count_in.adult_female is not None,
        count_in.youth_male is not None,
        count_in.youth_female is not None,
        count_in.boys is not None,
        count_in.girls is not None,
    ]):
        updated_count.calculate_total()
        await db.commit()
        await db.refresh(updated_count)
    
    return updated_count
