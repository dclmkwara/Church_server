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
from app.models.location import State, Region
from app.models.announcement import Announcement
from sqlalchemy import select

router = APIRouter()


async def _get_information_in_scope(
    db: AsyncSession, information_id: UUID, current_user: User
):
    entry = await crud_announcement.get_by_id(db, information_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Information not found")
    deps.ensure_path_in_scope(current_user, entry.path, detail="Information outside your scope")
    return entry


def _require_information_manager(current_user: User) -> int:
    score = deps.highest_role_score(current_user)
    if score < 4:
        raise HTTPException(status_code=403, detail="Regional-level access is required to manage weekly information")
    return score


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
    """Create a weekly information sheet for the caller's region or state."""
    score = _require_information_manager(current_user)
    model = State if score == 5 else Region
    result = await db.execute(select(model).where(model.path == deps.effective_scope_path(current_user)))
    node = result.scalars().first()
    if node is None:
        raise HTTPException(status_code=403, detail="Weekly information can only be managed from the caller's own region or state scope")
    payload = information_in.model_copy(update={
        "region_id": str(node.state_id if score == 5 else node.region_id),
        "region_name": getattr(node, "state_name", None) or getattr(node, "region_name", None) or "Church scope",
    })
    return await crud_announcement.create(db, payload, str(node.path))


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
    if deps.highest_role_score(current_user) == 4:
        region_result = await db.execute(select(Region).where(Region.path == scope_path))
        region = region_result.scalars().first()
        region_id = str(region.region_id) if region else None
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
    "/latest",
    response_model=AnnouncementResponse,
    dependencies=[Depends(deps.PermissionChecker("announcements:read"))],
)
async def latest_information(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Return the latest published sheet whose region/state contains this user."""
    from app.db.filters import scope_or_ancestor_filter
    result = await db.execute(
        select(Announcement)
        .where(
            scope_or_ancestor_filter(Announcement.path, deps.effective_scope_path(current_user)),
            Announcement.is_active.is_(True),
            Announcement.published_at.is_not(None),
        )
        .order_by(Announcement.date.desc(), Announcement.published_at.desc())
        .limit(1)
    )
    entry = result.scalars().first()
    if not entry:
        raise HTTPException(status_code=404, detail="No published information sheet is available for your scope")
    return entry


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
    _require_information_manager(current_user)
    entry = await _get_information_in_scope(db, information_id, current_user)
    entry = await crud_announcement.update(db, information_id, information_in)
    return entry


@router.post(
    "/{information_id}/publish",
    response_model=AnnouncementResponse,
    dependencies=[Depends(deps.PermissionChecker("announcements:manage"))],
)
async def publish_information(
    information_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Publish the prepared sheet within the caller's jurisdiction."""
    _require_information_manager(current_user)
    await _get_information_in_scope(db, information_id, current_user)
    return await crud_announcement.publish(db, information_id)


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
    _require_information_manager(current_user)
    entry = await _get_information_in_scope(db, information_id, current_user)
    await db.delete(entry)
    await db.commit()
    return None
