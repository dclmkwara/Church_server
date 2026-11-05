"""Pydantic schemas for Count models."""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

class CountBase(BaseModel):
    event_id: Optional[UUID] = None
    location_id: str
    date: Optional[datetime] = None
    church_type: Optional[str] = Field(None, max_length=40)
    program_level: Optional[str] = Field(None, pattern="^(Local|Group|Region|State|National|Global)$", description="Local, Group, Region, State, National, or Global")
    program_domain: Optional[str] = Field(None, max_length=80)
    program_type: Optional[str] = Field(None, max_length=120)
    assignment_id: Optional[UUID] = None
    adult_male: int = Field(0, ge=0)
    adult_female: int = Field(0, ge=0)
    youth_male: int = Field(0, ge=0)
    youth_female: int = Field(0, ge=0)
    boys: int = Field(0, ge=0)
    girls: int = Field(0, ge=0)
    note: Optional[str] = None
    client_id: Optional[UUID] = None
    source_role: str = Field(default="regular", deprecated=True)
    campaign_code: Optional[str] = Field(None, deprecated=True)
    submission_channel: str = Field(default="admin_web")

class CountCreate(CountBase):
    @model_validator(mode="after")
    def require_context_without_event(self):
        if self.event_id is None:
            if not self.date or not self.church_type or not self.program_level or not self.program_domain or not self.program_type:
                raise ValueError("Eventless counts require service date, church section, program level, program domain, and program type")
            if self.program_domain.lower() == "crusade":
                raise ValueError("Crusade counts require a scheduled event")
        return self

class CountUpdate(BaseModel):
    adult_male: Optional[int] = Field(None, ge=0)
    adult_female: Optional[int] = Field(None, ge=0)
    youth_male: Optional[int] = Field(None, ge=0)
    youth_female: Optional[int] = Field(None, ge=0)
    boys: Optional[int] = Field(None, ge=0)
    girls: Optional[int] = Field(None, ge=0)
    note: Optional[str] = None

class CountResponse(CountBase):
    id: UUID
    path: str
    program_scope_path: Optional[str] = None
    total: int
    status: str
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
