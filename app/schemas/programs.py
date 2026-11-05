"""Pydantic schemas for Program models."""
from datetime import date as date_type, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ProgramDomainBase(BaseModel):
    name: str = Field(..., description="Program Domain Name")
    slug: str = Field(..., description="Unique slug")
    description: Optional[str] = None

class ProgramDomainCreate(ProgramDomainBase):
    pass

class ProgramDomainUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None

class ProgramDomainResponse(ProgramDomainBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class ProgramTypeBase(BaseModel):
    name: str
    slug: str
    domain_id: int
    description: Optional[str] = None

class ProgramTypeCreate(ProgramTypeBase):
    pass

class ProgramTypeUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    domain_id: Optional[int] = None
    description: Optional[str] = None

class ProgramTypeResponse(ProgramTypeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class ProgramCampaignBase(BaseModel):
    domain_id: int
    path: str
    campaign_code: str
    title: str
    description: Optional[str] = None
    event_mode: str = Field(default="special", description="crusade, retreat, special, or regular")
    reporting_scope: str = Field(default="global")
    status: str = Field(default="draft")
    alpha_location_id: Optional[str] = None
    start_date: date_type
    end_date: date_type
    collection_window_start: Optional[datetime] = None
    collection_window_end: Optional[datetime] = None
    flyer_url: Optional[str] = None
    publicity_note: Optional[str] = None

class ProgramCampaignCreate(ProgramCampaignBase):
    @model_validator(mode="after")
    def validate_windows(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        if (self.collection_window_start and self.collection_window_end
                and self.collection_window_start > self.collection_window_end):
            raise ValueError("collection_window_start must be on or before collection_window_end")
        return self

class ProgramCampaignUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    reporting_scope: Optional[str] = None
    status: Optional[str] = None
    alpha_location_id: Optional[str] = None
    start_date: Optional[date_type] = None
    end_date: Optional[date_type] = None
    collection_window_start: Optional[datetime] = None
    collection_window_end: Optional[datetime] = None
    flyer_url: Optional[str] = None
    publicity_note: Optional[str] = None

class ProgramCampaignResponse(ProgramCampaignBase):
    id: UUID
    created_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class ProgramEventBase(BaseModel):
    program_type_id: int
    campaign_id: Optional[UUID] = None
    date: date_type
    path: str
    title: Optional[str] = None
    is_public: bool = False
    published_at: Optional[datetime] = None
    event_mode: str = Field(default="regular")
    reporting_scope: str = Field(default="location")
    campaign_code: Optional[str] = None
    alpha_location_id: Optional[str] = None
    is_alpha_event: bool = False
    collection_window_start: Optional[datetime] = None
    collection_window_end: Optional[datetime] = None
    audience_segment: Optional[str] = None

class ProgramEventCreate(ProgramEventBase):
    @model_validator(mode="after")
    def validate_windows(self):
        if (self.collection_window_start and self.collection_window_end
                and self.collection_window_start > self.collection_window_end):
            raise ValueError("collection_window_start must be on or before collection_window_end")
        return self

class ProgramEventUpdate(BaseModel):
    program_type_id: Optional[int] = None
    campaign_id: Optional[UUID] = None
    date: Optional[date_type] = None
    path: Optional[str] = None
    title: Optional[str] = None
    is_public: Optional[bool] = None
    published_at: Optional[datetime] = None
    event_mode: Optional[str] = None
    reporting_scope: Optional[str] = None
    campaign_code: Optional[str] = None
    alpha_location_id: Optional[str] = None
    is_alpha_event: Optional[bool] = None
    collection_window_start: Optional[datetime] = None
    collection_window_end: Optional[datetime] = None
    audience_segment: Optional[str] = None

class ProgramEventResponse(ProgramEventBase):
    id: UUID
    approval_status: str = "pending"
    created_by_id: Optional[UUID] = None
    approved_by_id: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    approval_note: Optional[str] = None
    program_type: Optional[ProgramTypeResponse] = None
    campaign: Optional[ProgramCampaignResponse] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class EventAssignmentBase(BaseModel):
    worker_id: UUID
    assignment_label: Optional[str] = None
    assignment_type: str = Field(default="both", description="count, convert, attendance, both (count and convert), or all")
    source_role: str = Field(default="alpha", description="alpha, satellite, or regular")
    note: Optional[str] = None

class EventAssignmentCreate(EventAssignmentBase):
    pass

class EventAssignmentUpdate(BaseModel):
    assignment_label: Optional[str] = None
    assignment_type: Optional[str] = None
    source_role: Optional[str] = None
    note: Optional[str] = None
    status: Optional[str] = None
    submission_completed: Optional[bool] = None

class EventAssignmentResponse(EventAssignmentBase):
    id: UUID
    event_id: UUID
    path: str
    status: str
    assigned_by_id: UUID
    approved_by_id: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    submission_completed: bool
    submitted_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
