"""
Approval workflow models for transfers and status changes.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
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

    from_location_id = Column(String, nullable=False, index=True)
    to_location_id = Column(String, nullable=False, index=True)

    status = Column(String, default="pending", index=True)  # pending, approved, rejected
    reason = Column(String, nullable=True)

    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
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

    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    worker = relationship("Worker")
    requester = relationship("User", foreign_keys=[requested_by])
    approver = relationship("User", foreign_keys=[approved_by])
