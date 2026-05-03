"""
Pydantic schemas for ChurchMember model.
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChurchMemberBase(BaseModel):
    location_id: str
    name: str
    gender: str = Field(..., description="Male or Female")
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    marital_status: Optional[str] = None  # Single, Married, Widowed, Divorced
    occupation: Optional[str] = None

    # Church Details
    member_since: Optional[date] = None
    fellowship_id: Optional[str] = None
    unit: Optional[str] = None

    # Worker linkage
    is_worker: bool = False
    worker_id: Optional[UUID] = None

    # Status
    status: str = Field(default="active", description="active | inactive | transferred | deceased")
    status_note: Optional[str] = None

    client_id: Optional[UUID] = None


class ChurchMemberCreate(ChurchMemberBase):
    pass


class ChurchMemberUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    marital_status: Optional[str] = None
    occupation: Optional[str] = None
    member_since: Optional[date] = None
    fellowship_id: Optional[str] = None
    unit: Optional[str] = None
    is_worker: Optional[bool] = None
    worker_id: Optional[UUID] = None
    status: Optional[str] = None
    status_note: Optional[str] = None


class ChurchMemberResponse(ChurchMemberBase):
    id: UUID
    path: str
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
