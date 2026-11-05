from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.api import deps
from app.crud.crud_announcement import announcement as crud_announcement
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse
from app.models.user import User
from app.models.location import State, Region, Group, Location

router = APIRouter()


def _require_announcement_manager(current_user: User) -> int:
    score = deps.highest_role_score(current_user)
    if score < 4:
        raise HTTPException(status_code=403, detail="Regional-level access is required to manage weekly information")
    return score


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
    role_score = _require_announcement_manager(current_user)
    current_path = deps.effective_scope_path(current_user)
    model = State if role_score == 5 else Region
    result = await db.execute(select(model).where(model.path == current_path))
    node = result.scalars().first()
    node_name = getattr(node, "state_name", "") if role_score == 5 else getattr(node, "region_name", "")
    if not node:
        raise HTTPException(status_code=403, detail="Weekly information can only be managed from the caller's own region or state scope")

    actual_scope_id = node.state_id if role_score == 5 else node.region_id
    validated_input = announcement_in.model_copy(update={
        "region_id": str(actual_scope_id),
        "region_name": node_name or announcement_in.region_name,
    })
    announcement = await crud_announcement.create(db, validated_input, str(node.path))
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
    if deps.highest_role_score(current_user) == 4:
        region_result = await db.execute(select(Region).where(Region.path == scope_path))
        region = region_result.scalars().first()
        region_id = str(region.region_id) if region else None
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
    _require_announcement_manager(current_user)
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
    _require_announcement_manager(current_user)
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
    _require_announcement_manager(current_user)
    announcement = await _get_announcement_in_scope(db, announcement_id, current_user)
    await db.delete(announcement)
    await db.commit()
    return None
