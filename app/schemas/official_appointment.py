"""Schemas for official appointments."""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OfficialAppointmentBase(BaseModel):
    appointed_role: str
    assigned_scope_label: str
    appointment_date: date
    status: str = "active"
    note: Optional[str] = None


class OfficialAppointmentCreate(OfficialAppointmentBase):
    worker_id: UUID
    assigned_scope_path: str


class OfficialAppointmentUpdate(BaseModel):
    appointed_role: Optional[str] = None
    assigned_scope_label: Optional[str] = None
    assigned_scope_path: Optional[str] = None
    appointment_date: Optional[date] = None
    status: Optional[str] = None
    note: Optional[str] = None


class OfficialAppointmentRevoke(BaseModel):
    note: Optional[str] = None


class OfficialAppointmentResponse(OfficialAppointmentBase):
    model_config = ConfigDict(from_attributes=True)

    appointment_id: UUID
    worker_id: UUID
    worker_name: str
    location_id: str
    location_name: str
    appointed_by_id: UUID
    appointed_by_name: str
    revoked_at: Optional[datetime] = None
    revoked_by_id: Optional[UUID] = None
    revoked_note: Optional[str] = None
    path: str
    created_at: datetime
    last_modify: datetime
