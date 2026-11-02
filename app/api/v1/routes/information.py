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
from app.models.location import Region

router = APIRouter()


async def _get_information_in_scope(
    db: AsyncSession, information_id: UUID, current_user: User
):
    entry = await crud_announcement.get_by_id(db, information_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Information not found")
    deps.ensure_path_in_scope(current_user, entry.path, detail="Information outside your scope")
    return entry


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
    try:
        region_id = int(information_in.region_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="A valid region_id is required")
    region = await db.get(Region, region_id)
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    deps.ensure_path_in_scope(current_user, region.path, detail="Region outside your scope")
    payload = information_in.model_copy(update={"region_name": region.region_name})
    return await crud_announcement.create(db, payload, str(region.path))


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
    scope_path = deps.effective_scope_path(current_user)
    entries = await crud_announcement.get_list(
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
    return deps.filter_rows_in_scope(entries, current_user)


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
    return await _get_information_in_scope(db, information_id, current_user)


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
    entry = await _get_information_in_scope(db, information_id, current_user)
    if information_in.region_id is not None:
        try:
            region_id = int(information_in.region_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="A valid region_id is required")
        region = await db.get(Region, region_id)
        if region is None:
            raise HTTPException(status_code=404, detail="Region not found")
        deps.ensure_path_in_scope(current_user, region.path, detail="Region outside your scope")
        information_in = information_in.model_copy(update={"region_name": region.region_name})
    entry = await crud_announcement.update(db, information_id, information_in)
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
    entry = await _get_information_in_scope(db, information_id, current_user)
    await db.delete(entry)
    await db.commit()
    return None
