"""
Pydantic schemas for Worker Attendance.
"""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class WorkerAttendanceBase(BaseModel):
    event_id: Optional[UUID] = None
    assignment_id: Optional[UUID] = None
    location_id: str
    date: Optional[datetime] = None
    church_type: Optional[str] = Field(None, max_length=40)
    program_level: Optional[str] = Field(None, pattern="^(Local|Group|Region|State|National|Global)$", description="Local, Group, Region, State, National, or Global")
    program_domain: Optional[str] = Field(None, max_length=80)
    program_type: Optional[str] = Field(None, max_length=120)
    worker_id: UUID
    
    status: Literal["present", "absent", "late", "excused"] = Field(default="present", description="present, absent, late, excused")
    reason: Optional[str] = None
    note: Optional[str] = None
    client_id: Optional[UUID] = None

class WorkerAttendanceCreate(WorkerAttendanceBase):
    @model_validator(mode="after")
    def require_context_without_event(self):
        if self.event_id is None:
            if not self.date or not self.church_type or not self.program_level or not self.program_domain or not self.program_type:
                raise ValueError("Eventless attendance requires service date, church section, program level, program domain, and program type")
            if self.program_domain.lower() == "crusade":
                raise ValueError("Crusade attendance requires a scheduled event")
        return self


class AttendancePresentWorker(BaseModel):
    worker_id: UUID
    worker_name: str = Field(min_length=1, max_length=255)


class WorkerAttendanceSubmissionCreate(BaseModel):
    client_id: UUID
    location_id: str
    event_id: Optional[UUID] = None
    assignment_id: Optional[UUID] = None
    assignment_id: Optional[UUID] = None
    date: datetime
    church_type: str = Field(min_length=1, max_length=40)
    program_level: Optional[str] = Field(None, pattern="^(Local|Group|Region|State|National|Global)$", description="Local, Group, Region, State, National, or Global")
    program_domain: Optional[str] = Field(None, max_length=80)
    program_type: str = Field(min_length=1, max_length=120)
    expected_workers_count: int = Field(ge=0)
    present_workers: list[AttendancePresentWorker] = Field(min_length=1, max_length=5000)
    submitted_by_worker_id: Optional[UUID] = None
    note: Optional[str] = None

    @model_validator(mode="after")
    def validate_capture(self):
        ids = [worker.worker_id for worker in self.present_workers]
        if len(ids) != len(set(ids)):
            raise ValueError("Attendance capture cannot contain the same worker more than once")
        if self.expected_workers_count < len(ids):
            raise ValueError("Present worker count cannot exceed the expected roster count")
        if self.event_id is None and (not self.program_level or not self.program_domain or self.program_domain.lower() == "crusade"):
            raise ValueError("Attendance requires program metadata; crusade attendance requires a scheduled event")
        return self


class WorkerAttendanceSubmissionResponse(BaseModel):
    id: UUID
    client_id: UUID
    path: str
    program_scope_path: Optional[str] = None
    location_id: str
    event_id: Optional[UUID]
    assignment_id: Optional[UUID] = None
    assignment_id: Optional[UUID] = None
    date: datetime
    church_type: str
    program_level: Optional[str] = Field(None, pattern="^(Local|Group|Region|State|National|Global)$")
    program_domain: Optional[str]
    program_type: str
    expected_workers_count: int
    expected_worker_ids: Optional[list[UUID]] = None
    present_count: int
    present_workers: list[AttendancePresentWorker]
    entered_by_id: UUID
    submitted_by_worker_id: Optional[UUID]
    submitted_by_name: str
    note: Optional[str]
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class WorkerAttendanceUpdate(BaseModel):
    status: Optional[Literal["present", "absent", "late", "excused"]] = None
    reason: Optional[str] = None
    note: Optional[str] = None

class WorkerAttendanceResponse(WorkerAttendanceBase):
    id: UUID
    path: str
    program_scope_path: Optional[str] = None
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
