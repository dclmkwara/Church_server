from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID

class AnnouncementItemBase(BaseModel):
    title: str
    text: str

class AnnouncementItemCreate(AnnouncementItemBase):
    pass

class AnnouncementItemResponse(AnnouncementItemBase):
    id: int
    
    class Config:
        from_attributes = True

class AnnouncementBase(BaseModel):
    region_id: str
    region_name: str
    meeting: Optional[str] = None
    date: date
    
    trets_topic: Optional[str] = None
    trets_date: Optional[date] = None
    
    sws_topic: Optional[str] = None
    sws_bible_reading: Optional[str] = None
    
    mbs_bible_reading: Optional[str] = None
    sts_study: Optional[str] = None
    
    adult_hcf_lesson: Optional[str] = None
    adult_hcf_volume: Optional[str] = None
    
    youth_hcf_lesson: Optional[str] = None
    youth_hcf_volume: Optional[str] = None
    
    children_hcf_lesson: Optional[str] = None
    children_hcf_volume: Optional[str] = None
    
    is_active: bool = True

class AnnouncementCreate(AnnouncementBase):
    items: List[AnnouncementItemCreate] = []

class AnnouncementUpdate(BaseModel):
    region_name: Optional[str] = None
    meeting: Optional[str] = None
    date: Optional[date] = None
    
    trets_topic: Optional[str] = None
    trets_date: Optional[date] = None
    
    sws_topic: Optional[str] = None
    sws_bible_reading: Optional[str] = None
    
    mbs_bible_reading: Optional[str] = None
    sts_study: Optional[str] = None
    
    adult_hcf_lesson: Optional[str] = None
    adult_hcf_volume: Optional[str] = None
    
    youth_hcf_lesson: Optional[str] = None
    youth_hcf_volume: Optional[str] = None
    
    children_hcf_lesson: Optional[str] = None
    children_hcf_volume: Optional[str] = None
    
    is_active: Optional[bool] = None
    
    items: Optional[List[AnnouncementItemCreate]] = None

class AnnouncementResponse(AnnouncementBase):
    id: UUID
    published_at: Optional[datetime] = None
    items: List[AnnouncementItemResponse] = []
    
    created_at: datetime
    last_modify: datetime

    class Config:
        from_attributes = True
