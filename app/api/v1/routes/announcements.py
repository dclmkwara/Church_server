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


async def _get_announcement_in_scope(db: AsyncSession, announcement_id: UUID, current_user: User):
    announcement = await crud_announcement.get_by_id(db, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    deps.ensure_path_in_scope(current_user, announcement.path, detail="Announcement outside your scope")
    return announcement

@router.post(
    "/",
    response_model=AnnouncementResponse,
    status_code=201,
    dependencies=[Depends(deps.PermissionChecker("announcements:manage"))],
)
async def create_announcement(
    announcement_in: AnnouncementCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Create a new announcement.
    Resolve the region from the database and derive the announcement scope
    from that region, rather than trusting a caller-supplied name or path.
    """
    try:
        region = await db.get(Region, announcement_in.region_id)
    except (TypeError, ValueError):
        region = None
    if not region:
        raise HTTPException(status_code=404, detail="Region not found")
    deps.ensure_path_in_scope(current_user, region.path, detail="Region outside your scope")

    validated_input = announcement_in.model_copy(update={"region_name": region.region_name})
    announcement = await crud_announcement.create(db, validated_input, str(region.path))
    return announcement

@router.get(
    "/",
    response_model=List[AnnouncementResponse],
    dependencies=[Depends(deps.PermissionChecker("announcements:read"))],
)
async def list_announcements(
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
    """
    List announcements filtered by user's scope.
    """
    scope_path = deps.effective_scope_path(current_user)
    announcements = await crud_announcement.get_list(
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
    return deps.filter_rows_in_scope(announcements, current_user)

@router.get(
    "/{announcement_id}",
    response_model=AnnouncementResponse,
    dependencies=[Depends(deps.PermissionChecker("announcements:read"))],
)
async def get_announcement(
    announcement_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get announcement by ID.
    """
    return await _get_announcement_in_scope(db, announcement_id, current_user)

@router.put(
    "/{announcement_id}",
    response_model=AnnouncementResponse,
    dependencies=[Depends(deps.PermissionChecker("announcements:manage"))],
)
async def update_announcement(
    announcement_id: UUID,
    announcement_in: AnnouncementUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Update an announcement.
    """
    await _get_announcement_in_scope(db, announcement_id, current_user)
    return await crud_announcement.update(db, announcement_id, announcement_in)

@router.post(
    "/{announcement_id}/publish",
    response_model=AnnouncementResponse,
    dependencies=[Depends(deps.PermissionChecker("announcements:manage"))],
)
async def publish_announcement(
    announcement_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Publish an announcement (sets published_at timestamp and is_active=True).
    """
    await _get_announcement_in_scope(db, announcement_id, current_user)
    return await crud_announcement.publish(db, announcement_id)


@router.delete(
    "/{announcement_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("announcements:manage"))],
)
async def delete_announcement(
    announcement_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Delete announcement."""
    announcement = await _get_announcement_in_scope(db, announcement_id, current_user)
    await db.delete(announcement)
    await db.commit()
    return None
