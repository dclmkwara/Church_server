"""
CRUD operations for Media Gallery and Items.
"""
from typing import List, Optional, Any
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.models.media import MediaGallery, MediaItem
from app.schemas.media import MediaGalleryCreate, MediaGalleryUpdate, MediaItemCreate, MediaItemUpdate

class CRUDMediaGallery(CRUDBase[MediaGallery, MediaGalleryCreate, MediaGalleryUpdate]):
    async def create(self, db: AsyncSession, *, obj_in: MediaGalleryCreate, user_id: UUID) -> MediaGallery:
        """Create a new media gallery."""
        # Get location to derive path
        from app.crud.crud_location import location
        # crud_location uses 'get' for UUID, maybe 'get_by_location_id' exists?
        # Assuming location.get_by_location_id exists or we query manually.
        # Let's verify location crud in memory or query manually.
        
        # Safe fallback: Query Location by location_id (string ID like "DCM-...")
        # Actually in models location_id is display format.
        
        # We need the model location.
        from app.models.location import Location
        query = select(Location).where(Location.location_id == obj_in.location_id)
        result = await db.execute(query)
        loc = result.scalars().first()
        
        if not loc:
             raise HTTPException(status_code=404, detail=f"Location {obj_in.location_id} not found")
        
        db_obj = MediaGallery(
             title=obj_in.title,
             description=obj_in.description,
             event_id=obj_in.event_id,
             slug=obj_in.slug,
             path=str(loc.path),
             created_by_id=user_id
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_multi_by_scope(
        self, 
        db: AsyncSession, 
        *, 
        scope_path: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[MediaGallery]:
        """Get galleries within scope."""
        query = select(MediaGallery).where(
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
        ).offset(skip).limit(limit).order_by(MediaGallery.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()


class CRUDMediaItem(CRUDBase[MediaItem, MediaItemCreate, MediaItemUpdate]):
    async def create(self, db: AsyncSession, *, obj_in: MediaItemCreate, user_id: UUID) -> MediaItem:
        """Create a media item record."""
        # Verify gallery exists
        gallery_obj = await gallery.get(db, id=obj_in.gallery_id)
        if not gallery_obj:
            raise HTTPException(status_code=404, detail="Gallery not found")

        db_obj = MediaItem(
            gallery_id=obj_in.gallery_id,
            file_path=obj_in.file_path,
            file_name=obj_in.file_name,
            file_type=obj_in.file_type,
            file_size=obj_in.file_size,
            caption=obj_in.caption,
            is_cover=obj_in.is_cover,
            uploaded_by_id=user_id
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_by_gallery(
        self, 
        db: AsyncSession, 
        *, 
        gallery_id: UUID,
        skip: int = 0, 
        limit: int = 100
    ) -> List[MediaItem]:
        """Get items for a specific gallery."""
        query = select(MediaItem).where(
            MediaItem.gallery_id == gallery_id
        ).offset(skip).limit(limit).order_by(MediaItem.is_cover.desc(), MediaItem.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()


gallery = CRUDMediaGallery(MediaGallery)
item = CRUDMediaItem(MediaItem)
