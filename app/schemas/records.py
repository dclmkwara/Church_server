"""Pydantic schemas for Record models."""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class RecordBase(BaseModel):
    event_id: UUID
    location_id: str
    assignment_id: Optional[UUID] = None
    record_type: str = Field(..., description="newcomer or convert")
    name: str
    gender: str = Field(..., description="Male or Female")
    phone: str = Field(..., description="Phone number (required)")
    details: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None
    client_id: Optional[UUID] = None
    source_role: str = Field(default="regular")
    campaign_code: Optional[str] = None
    submission_channel: str = Field(default="admin_web")

class RecordCreate(RecordBase):
    pass

class RecordUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    note: Optional[str] = None
    status: Optional[str] = None
    assignment_id: Optional[UUID] = None
    source_role: Optional[str] = None
    campaign_code: Optional[str] = None
    submission_channel: Optional[str] = None

class RecordResponse(RecordBase):
    id: UUID
    path: str
    status: str
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
