from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field

class PublicLocationResponse(BaseModel):
    id: str 
    name: str 
    type: str 
    address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class PublicEventResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    date: date
    type_name: str # Resolved name e.g. "Sunday Service"

    model_config = ConfigDict(from_attributes=True)

class PublicGalleryResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    slug: Optional[str] = None
    created_at: datetime
    # We could include a cover image URL derived from items

    model_config = ConfigDict(from_attributes=True)


class PublicGalleryItemResponse(BaseModel):
    id: UUID
    file_path: str
    file_name: str
    file_type: str
    file_size: int
    caption: Optional[str] = None
    is_cover: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PublicGalleryDetailResponse(PublicGalleryResponse):
    items: List[PublicGalleryItemResponse] = Field(default_factory=list)


class PublicAnnouncementResponse(BaseModel):
    id: UUID
    region_name: str
    meeting: Optional[str] = None
    date: date
    sws_topic: Optional[str] = None
    trets_topic: Optional[str] = None
    mbs_bible_reading: Optional[str] = None
    sts_study: Optional[str] = None
    published_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Public Form Schemas
class PublicWorkerRegistration(BaseModel):
    """Public worker registration form (from website)"""
    name: str
    phone: str
    email: str
    gender: str  # Male, Female
    location_id: str
    unit: str  # Ushering, Choir, etc.
    address: Optional[str] = None
    occupation: Optional[str] = None
    marital_status: Optional[str] = None


class PublicContactForm(BaseModel):
    """Public contact form submission"""
    name: str
    email: str
    phone: Optional[str] = None
    subject: str
    message: str


class PublicPrayerRequest(BaseModel):
    """Public prayer request submission"""
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    request: str
    is_urgent: bool = False


class PublicFormResponse(BaseModel):
    """Generic response for public form submissions"""
    success: bool
    message: str
    reference_id: Optional[str] = None

