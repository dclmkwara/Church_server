"""Pydantic schemas for Count models."""
from datetime import datetime
from typing import Any, Optional, Literal
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
    total: Optional[int] = Field(None, ge=0, le=999999)
    adult_male: int = Field(0, ge=0)
    adult_female: int = Field(0, ge=0)
    youth_male: int = Field(0, ge=0)
    youth_female: int = Field(0, ge=0)
    boys: int = Field(0, ge=0)
    girls: int = Field(0, ge=0)
    note: Optional[str] = None
    client_id: Optional[UUID] = None
    supersedes_id: Optional[UUID] = None
    source_role: str = Field(default="regular", deprecated=True)
    campaign_code: Optional[str] = Field(None, deprecated=True)
    submission_channel: str = Field(default="admin_web")
    count_mode: Optional[Literal["single", "section"]] = None
    section_label: Optional[str] = Field(None, max_length=120)
    service_id: Optional[str] = Field(None, min_length=1, max_length=60)

class CountCreate(CountBase):
    @model_validator(mode="after")
    def require_context_without_event(self):
        # New submissions always record a mode. Null stays reserved for legacy rows.
        if self.count_mode is None:
            self.count_mode = "single"
        if self.count_mode == "section" and not (self.section_label or "").strip():
            raise ValueError("Section counts require a section label")
        if self.count_mode == "single" and self.section_label:
            raise ValueError("Single counts cannot include a section label")
        demographic_total = self.adult_male + self.adult_female + self.youth_male + self.youth_female + self.boys + self.girls
        if self.total is not None and demographic_total and self.total != demographic_total:
            raise ValueError("Total must match the demographic breakdown, or leave the breakdown empty to submit one total")
        if self.event_id is None:
            if not self.date or not self.church_type or not self.program_level or not self.program_domain or not self.program_type:
                raise ValueError("Eventless counts require service date, church section, program level, program domain, and program type")
            if self.program_domain.lower() == "crusade":
                raise ValueError("Crusade counts require a scheduled event")
        return self

class CountUpdate(BaseModel):
    total: Optional[int] = Field(None, ge=0, le=999999)
    adult_male: Optional[int] = Field(None, ge=0)
    adult_female: Optional[int] = Field(None, ge=0)
    youth_male: Optional[int] = Field(None, ge=0)
    youth_female: Optional[int] = Field(None, ge=0)
    boys: Optional[int] = Field(None, ge=0)
    girls: Optional[int] = Field(None, ge=0)
    note: Optional[str] = None
    count_mode: Optional[Literal["single", "section"]] = None
    section_label: Optional[str] = Field(None, max_length=120)


class CountEditRequest(BaseModel):
    edit_id: UUID
    base_revision: int = Field(ge=0)
    values: dict[str, Any]


class CountReturnRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=4000)


class CountGroupCloseRequest(BaseModel):
    confirm_missing_suggestions: bool = False


class CountGroupResolveRequest(BaseModel):
    action: Literal["keep_one", "replace", "relabel_both"]
    keep_count_id: Optional[UUID] = None
    replace_count_id: Optional[UUID] = None
    new_label: Optional[str] = Field(None, max_length=120)


class CountSectionSuggestionInput(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    hidden: bool = False
    previous_label: Optional[str] = Field(None, max_length=120)

class CountResponse(CountBase):
    id: UUID
    count_group_id: Optional[UUID] = None
    path: str
    program_scope_path: Optional[str] = None
    total: int
    status: str
    approved_by_id: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    auto_accepted: bool = False
    rejection_reason: Optional[str] = None
    rejected_by_id: Optional[UUID] = None
    rejected_at: Optional[datetime] = None
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)
