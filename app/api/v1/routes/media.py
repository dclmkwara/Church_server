"""
Media Management Routes.
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
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

@router.post(
    "/galleries",
    response_model=MediaGalleryResponse,
    dependencies=[Depends(deps.PermissionChecker("media:create_gallery"))],
)
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
    await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=gallery_in.location_id,
        detail="Media gallery location outside your scope",
    )
    return await crud_media.gallery.create(db, obj_in=gallery_in, user_id=current_user.user_id)


@router.get(
    "/galleries",
    response_model=List[MediaGalleryResponse],
    dependencies=[Depends(deps.PermissionChecker("media:read"))],
)
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
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    
    return await crud_media.gallery.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )


@router.get(
    "/galleries/{gallery_id}",
    response_model=MediaGalleryResponse,
    dependencies=[Depends(deps.PermissionChecker("media:read"))],
)
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
    deps.ensure_path_in_scope(current_user, gallery.path, detail="Gallery outside your scope")
    return gallery


@router.post(
    "/items",
    response_model=MediaItemResponse,
    dependencies=[Depends(deps.PermissionChecker("media:create_item"))],
)
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
    gallery = await crud_media.gallery.get(db, id=item_in.gallery_id)
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    deps.ensure_path_in_scope(current_user, gallery.path, detail="Gallery outside your scope")
    return await crud_media.item.create(db, obj_in=item_in, user_id=current_user.user_id)


@router.get(
    "/galleries/{gallery_id}/items",
    response_model=List[MediaItemResponse],
    dependencies=[Depends(deps.PermissionChecker("media:read"))],
)
async def read_gallery_items(
    *,
    db: AsyncSession = Depends(deps.get_db),
    gallery_id: UUID,
    skip: int = 0, 
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get items for a gallery."""
    gallery = await crud_media.gallery.get(db, id=gallery_id)
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    deps.ensure_path_in_scope(current_user, gallery.path, detail="Gallery outside your scope")
    return await crud_media.item.get_by_gallery(
        db, gallery_id=gallery_id, skip=skip, limit=limit
    )


@router.delete(
    "/galleries/{gallery_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("media:delete_gallery"))],
)
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
    deps.ensure_path_in_scope(current_user, gallery.path, detail="Gallery outside your scope")
    
    await crud_media.gallery.remove(db, id=gallery_id)
    return None


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("media:delete_item"))],
)
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
    gallery = await crud_media.gallery.get(db, id=item.gallery_id)
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    deps.ensure_path_in_scope(current_user, gallery.path, detail="Media item outside your scope")
    
    await crud_media.item.remove(db, id=item_id)
    return None

