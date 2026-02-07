from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.crud.crud_announcement import announcement as crud_announcement
from app.schemas.announcement import AnnouncementCreate, AnnouncementUpdate, AnnouncementResponse
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=AnnouncementResponse, status_code=201)
async def create_announcement(
    announcement_in: AnnouncementCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Create a new announcement.
    Path is derived from the region_id in the request.
    """
    # For now, use user's path. In production, validate region_id and derive path from it.
    path = str(current_user.path)
    
    announcement = await crud_announcement.create(db, announcement_in, path)
    return announcement

@router.get("/", response_model=List[AnnouncementResponse])
async def list_announcements(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    List announcements filtered by user's scope.
    """
    scope_path = str(current_user.path)
    announcements = await crud_announcement.get_list(db, scope_path, is_active, skip, limit)
    return announcements

@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(
    announcement_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get announcement by ID.
    """
    announcement = await crud_announcement.get_by_id(db, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Verify user has access to this announcement's scope
    # For now, simple check - in production, use ltree operators
    # if not str(announcement.path).startswith(str(current_user.path)):
    #     raise HTTPException(status_code=403, detail="Access denied")
    
    return announcement

@router.put("/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: UUID,
    announcement_in: AnnouncementUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Update an announcement.
    """
    announcement = await crud_announcement.update(db, announcement_id, announcement_in)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return announcement

@router.post("/{announcement_id}/publish", response_model=AnnouncementResponse)
async def publish_announcement(
    announcement_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Publish an announcement (sets published_at timestamp and is_active=True).
    """
    announcement = await crud_announcement.publish(db, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return announcement
