"""
Pydantic schemas for Worker Attendance.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class WorkerAttendanceBase(BaseModel):
    event_id: UUID
    location_id: str
    worker_id: UUID
    
    status: str = Field(default="present", description="present, absent, late, excused")
    reason: Optional[str] = None
    note: Optional[str] = None
    client_id: Optional[UUID] = None

class WorkerAttendanceCreate(WorkerAttendanceBase):
    pass

class WorkerAttendanceUpdate(BaseModel):
    status: Optional[str] = None
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
