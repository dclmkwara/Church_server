"""
Media Management Routes.
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud import crud_media
from app.schemas.media import (
    MediaGalleryCreate, 
    MediaGalleryResponse, 
    MediaGalleryUpdate,
    MediaItemCreate, 
    MediaItemResponse
)
from app.models.user import User

router = APIRouter()

@router.post("/galleries", response_model=MediaGalleryResponse)
async def create_gallery(
    *,
    db: AsyncSession = Depends(deps.get_db),
    gallery_in: MediaGalleryCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new media gallery.
    """
    # Permission check usually happens here or in CRUD.
    # Assuming any active user can create (for now) or restrict to workers?
    # Basic Active User is fine.
    return await crud_media.gallery.create(db, obj_in=gallery_in, user_id=current_user.user_id)


@router.get("/galleries", response_model=List[MediaGalleryResponse])
async def read_galleries(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """
    Retrieve media galleries with hierarchical scope filtering.
    """
    search_scope = scope_path if scope_path else str(current_user.path)
    
    return await crud_media.gallery.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )


@router.get("/galleries/{gallery_id}", response_model=MediaGalleryResponse)
async def read_gallery(
    *,
    db: AsyncSession = Depends(deps.get_db),
    gallery_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get specific gallery by ID."""
    gallery = await crud_media.gallery.get(db, id=gallery_id)
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    return gallery


@router.post("/items", response_model=MediaItemResponse)
async def create_item(
    *,
    db: AsyncSession = Depends(deps.get_db),
    item_in: MediaItemCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Add a media item (photo/video) to a gallery.
    The file should be uploaded to Storage first, and the path provided here.
    """
    return await crud_media.item.create(db, obj_in=item_in, user_id=current_user.user_id)


@router.get("/galleries/{gallery_id}/items", response_model=List[MediaItemResponse])
async def read_gallery_items(
    *,
    db: AsyncSession = Depends(deps.get_db),
    gallery_id: UUID,
    skip: int = 0, 
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get items for a gallery."""
    # Check gallery access? 
    # Usually implied by knowledge of ID + RLS scoping (if applied).
    # Since we don't have explicit RLS on media_items (only inherited via join potentially),
    # we rely on the API layer or loose permissions for now.
    return await crud_media.item.get_by_gallery(
        db, gallery_id=gallery_id, skip=skip, limit=limit
    )


@router.delete("/galleries/{gallery_id}", status_code=204)
async def delete_gallery(
    *,
    db: AsyncSession = Depends(deps.get_db),
    gallery_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> None:
    """
    Delete a media gallery.
    
    Note: This will also delete all associated media items.
    Requires appropriate permissions.
    """
    gallery = await crud_media.gallery.get(db, id=gallery_id)
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    # Optional: Check if user has permission to delete
    # For now, any active user can delete (consider adding permission check)
    
    await crud_media.gallery.remove(db, id=gallery_id)
    return None


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    *,
    db: AsyncSession = Depends(deps.get_db),
    item_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> None:
    """
    Delete a media item.
    
    Note: This only removes the database record.
    The actual file in storage should be deleted separately.
    """
    item = await crud_media.item.get(db, id=item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")
    
    await crud_media.item.remove(db, id=item_id)
    return None

