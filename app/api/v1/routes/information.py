"""
Weekly information routes (alias to announcements).
"""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.crud.crud_announcement import announcement as crud_announcement
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse
from app.models.user import User

router = APIRouter()


@router.post(
    "/",
    response_model=AnnouncementResponse,
    status_code=201,
    dependencies=[Depends(deps.PermissionChecker("announcements:manage"))],
)
async def create_information(
    information_in: AnnouncementCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Create a new weekly information entry."""
    path = str(current_user.path)
    return await crud_announcement.create(db, information_in, path)


@router.get(
    "/",
    response_model=List[AnnouncementResponse],
    dependencies=[Depends(deps.PermissionChecker("announcements:read"))],
)
async def list_information(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    region_id: Optional[str] = Query(None, description="Filter by region id"),
    meeting: Optional[str] = Query(None, description="Filter by meeting type"),
    start_date: Optional[date] = Query(None, description="Filter start date"),
    end_date: Optional[date] = Query(None, description="Filter end date"),
    get_last: Optional[bool] = Query(None, description="Return most recent 100 records"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """List weekly information entries within scope."""
    scope_path = str(current_user.path)
    return await crud_announcement.get_list(
        db,
        scope_path,
        is_active,
        region_id,
        meeting,
        start_date,
        end_date,
        get_last,
        skip,
        limit,
    )


@router.get(
    "/{information_id}",
    response_model=AnnouncementResponse,
    dependencies=[Depends(deps.PermissionChecker("announcements:read"))],
)
async def get_information(
    information_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Get weekly information entry by ID."""
    entry = await crud_announcement.get_by_id(db, information_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Information not found")
    return entry


@router.put(
    "/{information_id}",
    response_model=AnnouncementResponse,
    dependencies=[Depends(deps.PermissionChecker("announcements:manage"))],
)
async def update_information(
    information_id: UUID,
    information_in: AnnouncementUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Update a weekly information entry."""
    entry = await crud_announcement.update(db, information_id, information_in)
    if not entry:
        raise HTTPException(status_code=404, detail="Information not found")
    return entry


@router.delete(
    "/{information_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("announcements:manage"))],
)
async def delete_information(
    information_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Delete weekly information entry."""
    entry = await crud_announcement.get_by_id(db, information_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Information not found")
    await db.delete(entry)
    await db.commit()
    return None
