"""
Pydantic schemas for Worker Attendance.
"""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class WorkerAttendanceBase(BaseModel):
    event_id: Optional[UUID] = None
    location_id: str
    date: Optional[datetime] = None
    church_type: Optional[str] = Field(None, max_length=40)
    program_domain: Optional[str] = Field(None, max_length=80)
    program_type: Optional[str] = Field(None, max_length=120)
    worker_id: UUID
    
    status: Literal["present", "absent", "late", "excused"] = Field(default="present", description="present, absent, late, excused")
    reason: Optional[str] = None
    note: Optional[str] = None
    client_id: Optional[UUID] = None

    @model_validator(mode="after")
    def require_context_without_event(self):
        if self.event_id is None:
            if not self.date or not self.church_type or not self.program_domain or not self.program_type:
                raise ValueError("Eventless attendance requires service date, church section, program domain, and program type")
            if self.program_domain.lower() == "crusade":
                raise ValueError("Crusade attendance requires a scheduled event")
        return self

class WorkerAttendanceCreate(WorkerAttendanceBase):
    pass

class WorkerAttendanceUpdate(BaseModel):
    status: Optional[Literal["present", "absent", "late", "excused"]] = None
    reason: Optional[str] = None
    note: Optional[str] = None

class WorkerAttendanceResponse(WorkerAttendanceBase):
    id: UUID
    path: str
    worker_name: str
    worker_phone: str
    worker_unit: Optional[str]
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class WorkerLookupResponse(BaseModel):
    """Compact worker card for attendance lookup."""
    worker_id: UUID
    user_id: str
    name: str
    unit: Optional[str] = None
    phone: str
    location_id: str
    location_name: str
    church_type: str
    path: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("path", mode="before")
    @classmethod
    def path_to_str(cls, v):
        return str(v) if v is not None else None
