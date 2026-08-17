"""
Approval workflow models for transfers, status changes, and worker removal requests.
"""
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text
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

    status = Column(String, default="pending", index=True)  # pending, approved, rejected
    reason = Column(String, nullable=True)

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
      Level 3 (Location Pastor) submits → status=pending, current_level=3
      Level 4 (Group Pastor) reviews   → approve (executes removal) OR reject OR escalate to level 5
      Level 5 (Region Pastor) reviews  → approve OR reject OR escalate to level 6
      Level 6 (State Overseer) reviews → approve OR reject (final)

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

    # Which governance level currently holds this request (3=Location, 4=Group, 5=Region, 6=State)
    current_level = Column(Integer, default=3, nullable=False)

    # Initial reason given by Location Pastor
    reason = Column(Text, nullable=False)

    # Full escalation / review audit trail stored as JSONB array
    reviews = Column(JSONB, default=list)

    # Who submitted the original request (Level 3 user)
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
