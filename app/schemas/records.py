"""
Pydantic schemas for Record models.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class RecordBase(BaseModel):
    event_id: UUID
    location_id: str
    
    record_type: str = Field(..., description="newcomer or convert")
    name: str
    gender: str = Field(..., description="Male or Female")
    phone: str = Field(..., description="Phone number (required)")
    
    # Flexible Details (JSONB)
    # Payload for all other fields: email, address, occupation, invited_by,
    # social_group, social_status, status_address, level, salvation_type
    details: Dict[str, Any] = Field(default_factory=dict)
    
    note: Optional[str] = None
    client_id: Optional[UUID] = None

class RecordCreate(RecordBase):
    pass

class RecordUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    note: Optional[str] = None
    status: Optional[str] = None

class RecordResponse(RecordBase):
    id: UUID
    path: str
    status: str
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
