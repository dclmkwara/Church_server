from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

class MediaItemBase(BaseModel):
    file_path: str
    file_name: str
    file_type: str
    file_size: int
    caption: Optional[str] = None
    is_cover: bool = False

class MediaItemCreate(MediaItemBase):
    gallery_id: UUID
    # uploaded_by_id handled in route

class MediaItemUpdate(BaseModel):
    caption: Optional[str] = None
    is_cover: Optional[bool] = None

class MediaItemResponse(MediaItemBase):
    id: UUID
    gallery_id: UUID
    uploaded_by_id: UUID
    created_at: datetime
    
    class Config:
        orm_mode = True

class MediaGalleryBase(BaseModel):
    title: str
    description: Optional[str] = None
    event_id: Optional[UUID] = None
    slug: Optional[str] = None

class MediaGalleryCreate(MediaGalleryBase):
    location_id: str

class MediaGalleryUpdate(MediaGalleryBase):
    title: Optional[str] = None
    description: Optional[str] = None
    event_id: Optional[UUID] = None
    slug: Optional[str] = None

class MediaGalleryResponse(MediaGalleryBase):
    id: UUID
    path: str
    created_by_id: UUID
    created_at: datetime
    items: List[MediaItemResponse] = []
    
    class Config:
        orm_mode = True
