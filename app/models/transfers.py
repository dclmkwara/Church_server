"""
Worker Transfer models.

Manages the formal transfer workflow when a worker moves from one branch
to another. Generates a PDF transfer/reference letter on final approval.

Workflow:
  Origin Location Pastor initiates → origin Group Pastor approves →
  receiving Location Pastor accepts → receiving Group Pastor approves →
  Region Pastor (or State Overseer) confirms → system updates worker/user scope.

Rejection at any stage ends the workflow with status: rejected.
"""
import uuid
from sqlalchemy import Column, String, Integer, Boolean, Date, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin


class WorkerTransfer(Base, TimestampMixin, SoftDeleteMixin):
    """
    Worker Transfer Request & Approval Record.

    Tracks a formal request to move a worker from one location to another.
    Origin and receiving location/group leaders approve before regional
    confirmation. A PDF reference letter is available after completion.

    Workflow states:
        pending             → Initial request created
        pending_receiving_location → Origin group approved
        pending_receiving_group    → Receiving location accepted
        pending_region      → Receiving group approved
        completed           → Region/state confirmed; worker relocated
        rejected            → Rejected at any stage

    Attributes:
        worker_id: The worker being transferred
        from_location_id: Current (origin) location
        to_location_id: Target (destination) location
        transfer_reason: Why the transfer is happening
        effective_date: When the transfer takes effect
        letter_generated: True once the PDF letter has been created
        letter_url: Storage path/URL of the generated PDF
    """
    __tablename__ = "worker_transfers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Worker Being Transferred
    worker_id = Column(
        UUID(as_uuid=False),
        ForeignKey("workers.worker_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Transfer Locations
    from_location_id = Column(
        UUID(as_uuid=False),
        ForeignKey("locations.location_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    to_location_id = Column(
        UUID(as_uuid=True),
        ForeignKey("locations.location_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Transfer Details
    transfer_reason = Column(Text, nullable=False)
    effective_date = Column(Date, nullable=False)

    # Workflow Status: pending_group -> pending_region -> completed | rejected
    status = Column(String, default="pending", nullable=False, index=True)
    current_level = Column(Integer, nullable=False, default=3, server_default="3", index=True)
    workflow_stage = Column(String, nullable=False, default="origin_group", server_default="origin_group", index=True)
    reviews = Column(JSONB, nullable=False, default=list)

    # Request
    requested_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
        index=True,
    )

    # Group approval (legacy origin_approved fields remain for compatibility).
    origin_approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
        index=True,
    )
    origin_approved_at = Column(DateTime(timezone=True), nullable=True)
    origin_note = Column(Text, nullable=True)

    group_approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    group_approved_at = Column(DateTime(timezone=True), nullable=True)
    group_note = Column(Text, nullable=True)

    # Regional approval (legacy destination_approved fields remain for compatibility).
    destination_approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
        index=True,
    )
    destination_approved_at = Column(DateTime(timezone=True), nullable=True)
    destination_note = Column(Text, nullable=True)

    region_approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    region_approved_at = Column(DateTime(timezone=True), nullable=True)
    region_note = Column(Text, nullable=True)

    receiving_location_approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    receiving_location_approved_at = Column(DateTime(timezone=True), nullable=True)
    receiving_location_note = Column(Text, nullable=True)
    receiving_group_approved_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    receiving_group_approved_at = Column(DateTime(timezone=True), nullable=True)
    receiving_group_note = Column(Text, nullable=True)

    # Rejection
    rejected_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
        index=True,
    )
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Generated Letter
    letter_generated = Column(Boolean, default=False, nullable=False)
    letter_url = Column(String, nullable=True)   # Supabase Storage path / URL
    reference_number = Column(String, unique=True, nullable=True, index=True)
    # Format: TRF-{YEAR}-{NNNN}  e.g. TRF-2026-0001

    # Relationships
    worker = relationship("Worker")
    from_location = relationship("Location", foreign_keys=[from_location_id])
    to_location = relationship("Location", foreign_keys=[to_location_id])
    requested_by = relationship("User", foreign_keys=[requested_by_id])
    origin_approver = relationship("User", foreign_keys=[origin_approved_by])
    destination_approver = relationship("User", foreign_keys=[destination_approved_by])
    rejector = relationship("User", foreign_keys=[rejected_by])

    def __repr__(self) -> str:
        return (
            f"<WorkerTransfer(worker={self.worker_id}, "
            f"from='{self.from_location_id}', to='{self.to_location_id}', "
            f"status='{self.status}')>"
        )
