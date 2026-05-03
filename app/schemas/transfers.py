"""
Pydantic schemas for WorkerTransfer and WorkerAbsenceNotice.
"""
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────
# Worker Transfer
# ─────────────────────────────────────────────

class WorkerTransferCreate(BaseModel):
    worker_id: UUID
    from_location_id: str
    to_location_id: str
    transfer_reason: str
    effective_date: date


class WorkerTransferApproveOrigin(BaseModel):
    """Payload for the origin pastor to approve/release the transfer."""
    note: Optional[str] = None


class WorkerTransferApproveDestination(BaseModel):
    """Payload for the receiving pastor to accept the worker."""
    note: Optional[str] = None


class WorkerTransferReject(BaseModel):
    """Payload for rejection at either stage."""
    rejection_reason: str


class WorkerTransferResponse(BaseModel):
    id: UUID
    worker_id: UUID
    from_location_id: str
    to_location_id: str
    transfer_reason: str
    effective_date: date
    status: str
    reference_number: Optional[str] = None
    letter_generated: bool
    letter_url: Optional[str] = None
    requested_by_id: UUID
    origin_approved_by: Optional[UUID] = None
    origin_approved_at: Optional[datetime] = None
    origin_note: Optional[str] = None
    destination_approved_by: Optional[UUID] = None
    destination_approved_at: Optional[datetime] = None
    destination_note: Optional[str] = None
    rejected_by: Optional[UUID] = None
    rejected_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────
# Worker Absence Notice
# ─────────────────────────────────────────────

class WorkerAbsenceNoticeCreate(BaseModel):
    event_id: UUID
    reason: str
    expected_return: Optional[date] = None


class WorkerAbsenceNoticeAcknowledge(BaseModel):
    """Payload for pastor to acknowledge or reject the notice."""
    status: str = Field(..., description="acknowledged or rejected")
    admin_note: Optional[str] = None


class WorkerAbsenceNoticeResponse(BaseModel):
    id: int
    worker_id: UUID
    event_id: UUID
    reason: str
    expected_return: Optional[date] = None
    status: str
    acknowledged_by: Optional[UUID] = None
    acknowledged_at: Optional[datetime] = None
    admin_note: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
