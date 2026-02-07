"""
Offering submission and retrieval routes.
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_offerings import offering as crud_offering
from app.schemas.offerings import OfferingCreate, OfferingResponse, OfferingUpdate
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=OfferingResponse)
async def create_offering(
    *,
    db: AsyncSession = Depends(deps.get_db),
    offering_in: OfferingCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit a new offering/tithe record."""
    return await crud_offering.create(db, obj_in=offering_in, user_id=current_user.user_id)


@router.get("/", response_model=List[OfferingResponse])
async def read_offerings(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """Retrieve offerings with scope filtering."""
    search_scope = scope_path if scope_path else str(current_user.path)
    return await crud_offering.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )


@router.get("/{offering_id}", response_model=OfferingResponse)
async def read_offering(
    *,
    db: AsyncSession = Depends(deps.get_db),
    offering_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a specific offering by ID."""
    offering = await crud_offering.get(db, id=offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    return offering


@router.put("/{offering_id}", response_model=OfferingResponse)
async def update_offering(
    *,
    db: AsyncSession = Depends(deps.get_db),
    offering_id: UUID,
    offering_in: OfferingUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update an offering record."""
    offering = await crud_offering.get(db, id=offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    
    return await crud_offering.update(db, db_obj=offering, obj_in=offering_in)
