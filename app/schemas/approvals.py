"""
Schemas for transfer, status change, and worker removal approvals.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ──────────────────────────────────────────────────────────────
# Worker Removal Request Schemas
# ──────────────────────────────────────────────────────────────

class RemovalRequestCreate(BaseModel):
    """Submitted by Level 3 (Location Pastor)."""
    worker_id: UUID
    reason: str  # Minimum 20 chars enforced in route


class RemovalActionPayload(BaseModel):
    """Body for approve / reject / escalate actions."""
    notes: Optional[str] = None  # Required for escalate, optional for approve/reject


class RemovalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    worker_id: UUID
    status: str                          # pending | approved | rejected | escalated
    current_level: int                   # 3=Group, 4=Region, 5=State
    reason: str
    reviews: List[Dict[str, Any]] = Field(default_factory=list)   # Full escalation audit trail
    requested_by: UUID
    decided_by: Optional[UUID] = None
    decided_at: Optional[datetime] = None
    escalated_by: Optional[UUID] = None
    escalated_at: Optional[datetime] = None
    escalation_notes: Optional[str] = None
    created_at: Optional[datetime] = None



class TransferRequestCreate(BaseModel):
    worker_id: UUID
    to_location_id: str
    reason: Optional[str] = None


class TransferRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    worker_id: UUID
    from_location_id: str
    to_location_id: str
    status: str
    current_level: int = 3
    workflow_stage: str = "origin_group"
    reason: Optional[str] = None
    rejection_reason: Optional[str] = None
    requested_by: Optional[UUID] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    group_approved_by: Optional[UUID] = None
    group_approved_at: Optional[datetime] = None
    group_note: Optional[str] = None
    region_approved_by: Optional[UUID] = None
    region_approved_at: Optional[datetime] = None
    region_note: Optional[str] = None
    receiving_location_approved_by: Optional[UUID] = None
    receiving_location_approved_at: Optional[datetime] = None
    receiving_location_note: Optional[str] = None
    receiving_group_approved_by: Optional[UUID] = None
    receiving_group_approved_at: Optional[datetime] = None
    receiving_group_note: Optional[str] = None
    reviews: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class StatusChangeRequestCreate(BaseModel):
    worker_id: UUID
    new_status: str
    reason: Optional[str] = None


class StatusChangeRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
