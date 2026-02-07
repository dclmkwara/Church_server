from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from pydantic import BaseModel

class PublicLocationResponse(BaseModel):
    id: str 
    name: str 
    type: str 
    address: Optional[str] = None
    
    class Config:
        orm_mode = True

class PublicEventResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    date: date
    type_name: str # Resolved name e.g. "Sunday Service"
    
    class Config:
        orm_mode = True

class PublicGalleryResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    slug: Optional[str] = None
    created_at: datetime
    # We could include a cover image URL derived from items
    
    class Config:
        orm_mode = True


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

