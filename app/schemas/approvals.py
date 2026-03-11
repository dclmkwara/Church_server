"""
Schemas for transfer and status change approvals.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class TransferRequestCreate(BaseModel):
    worker_id: UUID
    to_location_id: str
    reason: Optional[str] = None


class TransferRequestResponse(BaseModel):
    id: UUID
    worker_id: UUID
    from_location_id: str
    to_location_id: str
    status: str
    reason: Optional[str] = None
    requested_by: Optional[UUID] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StatusChangeRequestCreate(BaseModel):
    worker_id: UUID
    new_status: str
    reason: Optional[str] = None


class StatusChangeRequestResponse(BaseModel):
    id: UUID
    worker_id: UUID
    old_status: Optional[str] = None
    new_status: str
    status: str
    reason: Optional[str] = None
    requested_by: Optional[UUID] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
