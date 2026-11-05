"""
Approval workflow models for transfers, status changes, and worker removal requests.
"""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from app.db.base import Base
from app.models.core import TimestampMixin, LTreePathMixin


class TransferRequest(Base, TimestampMixin, LTreePathMixin):
    """
    Worker transfer request between locations.
    """
    __tablename__ = "transfer_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(UUID(as_uuid=True), ForeignKey("workers.worker_id"), nullable=False, index=True)

    from_location_id = Column(UUID(as_uuid=False), nullable=False, index=True)
    to_location_id = Column(UUID(as_uuid=False), nullable=False, index=True)

    status = Column(String, default="pending", index=True)  # pending, pending_region, approved, rejected
    reason = Column(String, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Pastoral transfer review: group approval followed by regional approval.
    current_level = Column(Integer, nullable=False, default=3, server_default="3", index=True)
    workflow_stage = Column(String, nullable=False, default="origin_group", server_default="origin_group", index=True)
    group_approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    group_approved_at = Column(DateTime(timezone=True), nullable=True)
    group_note = Column(Text, nullable=True)
    region_approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    region_approved_at = Column(DateTime(timezone=True), nullable=True)
    region_note = Column(Text, nullable=True)
    receiving_location_approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    receiving_location_approved_at = Column(DateTime(timezone=True), nullable=True)
    receiving_location_note = Column(Text, nullable=True)
    receiving_group_approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    receiving_group_approved_at = Column(DateTime(timezone=True), nullable=True)
    receiving_group_note = Column(Text, nullable=True)
    reviews = Column(JSONB, nullable=False, default=list)

    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    worker = relationship("Worker")
    requester = relationship("User", foreign_keys=[requested_by])
    approver = relationship("User", foreign_keys=[approved_by])


class StatusChangeRequest(Base, TimestampMixin, LTreePathMixin):
    """
    Worker status change request (active, inactive, suspended).
    """
    __tablename__ = "status_change_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(UUID(as_uuid=True), ForeignKey("workers.worker_id"), nullable=False, index=True)

    old_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)

    status = Column(String, default="pending", index=True)  # pending, approved, rejected
    reason = Column(String, nullable=True)

    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    worker = relationship("Worker")
    requester = relationship("User", foreign_keys=[requested_by])
    approver = relationship("User", foreign_keys=[approved_by])


class WorkerRemovalRequest(Base, TimestampMixin, LTreePathMixin):
    """
    Worker removal request with multi-level escalation.

    Flow:
      Score 2 (Location Pastor) submits → status=pending, current_level=3
      Score 3 (Group Pastor) reviews → approve, reject, or escalate to score 4
      Score 4 (Region Pastor) reviews → approve, reject, or escalate to score 5
      Score 5 (State Overseer) reviews → approve or reject (final)

    The `reviews` JSONB column stores the full audit trail:
      [
        {"level": 4, "reviewer_id": "...", "action": "escalate", "notes": "...", "at": "2026-..."},
        {"level": 5, "reviewer_id": "...", "action": "approve",  "notes": "...", "at": "2026-..."},
      ]
    """
    __tablename__ = "worker_removal_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_id = Column(UUID(as_uuid=True), ForeignKey("workers.worker_id"), nullable=False, index=True)

    # Status: pending | approved | rejected | escalated
    status = Column(String, default="pending", index=True)

    # Score currently holding this request (3=Group, 4=Region, 5=State).
    current_level = Column(Integer, default=3, nullable=False)

    # Initial reason given by Location Pastor
    reason = Column(Text, nullable=False)

    # Snapshot prior to the automatic suspension when removal is requested.
    worker_status_before_request = Column(String, nullable=True)
    user_was_active_before_request = Column(Boolean, nullable=True)

    # Full escalation / review audit trail stored as JSONB array
    reviews = Column(JSONB, default=list)

    # Who submitted the original request (Score 2 user)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)

    # Who took the final action (approve / reject)
    decided_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)

    # Populated when escalated — who escalated and when
    escalated_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    escalated_at = Column(DateTime(timezone=True), nullable=True)
    escalation_notes = Column(Text, nullable=True)

    worker = relationship("Worker")
    requester = relationship("User", foreign_keys=[requested_by])
    decider = relationship("User", foreign_keys=[decided_by])
    escalator = relationship("User", foreign_keys=[escalated_by])
