"""Pydantic schemas for Record models."""
from datetime import datetime
from typing import Literal, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

class RecordBase(BaseModel):
    event_id: Optional[UUID] = None
    location_id: str
    date: Optional[datetime] = None
    church_type: Optional[str] = Field(None, max_length=40)
    program_domain: Optional[str] = Field(None, max_length=80)
    program_type: Optional[str] = Field(None, max_length=120)
    assignment_id: Optional[UUID] = None
    record_type: Literal["newcomer", "convert"] = Field(..., description="newcomer or convert")
    name: str
    gender: str = Field(..., description="Male or Female")
    phone: str = Field(..., description="Phone number (required)")
    details: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = None
    client_id: Optional[UUID] = None
    source_role: str = Field(default="regular")
    campaign_code: Optional[str] = None
    submission_channel: str = Field(default="admin_web")

    @model_validator(mode="after")
    def require_context_without_event(self):
        if self.event_id is None:
            if not self.date or not self.church_type or not self.program_domain or not self.program_type:
                raise ValueError("Eventless registrations require service date, church section, program domain, and program type")
            if self.program_domain.lower() == "crusade":
                raise ValueError("Crusade registrations require a scheduled event")
        return self

class RecordCreate(RecordBase):
    pass

class RecordUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    note: Optional[str] = None

class RecordResponse(RecordBase):
    id: UUID
    path: str
    status: str
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
