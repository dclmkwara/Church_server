"""
Worker Transfer models.

Manages the formal transfer workflow when a worker moves from one branch
to another. Generates a PDF transfer/reference letter on final approval.

Workflow:
  Request created →
  Origin pastor approves (confirms service record) →
  Destination pastor approves (accepts the worker) →
  System updates Worker.location_id and generates PDF letter →
  Status: completed

Rejection at any stage ends the workflow with status: rejected.
"""
import uuid
from sqlalchemy import Column, String, Integer, Boolean, Date, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin


class WorkerTransfer(Base, TimestampMixin, SoftDeleteMixin):
    """
    Worker Transfer Request & Approval Record.

    Tracks a formal request to move a worker from one location to another.
    Both origin and destination pastors must approve before the transfer
    is executed. A PDF reference letter is generated on completion.

    Workflow states:
        pending             → Initial request created
        approved_by_origin  → Origin pastor has approved/released
        approved_by_dest    → Destination pastor has accepted
        completed           → Worker relocated, letter generated
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
        UUID(as_uuid=True),
        ForeignKey("workers.worker_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Transfer Locations
    from_location_id = Column(
        String,
        ForeignKey("locations.location_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    to_location_id = Column(
        String,
        ForeignKey("locations.location_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Transfer Details
    transfer_reason = Column(Text, nullable=False)
    effective_date = Column(Date, nullable=False)

    # Workflow Status
    status = Column(String, default="pending", nullable=False, index=True)
    # pending | approved_by_origin | approved_by_dest | completed | rejected

    # Request
    requested_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
    )

    # Origin Approval
    origin_approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    origin_approved_at = Column(DateTime(timezone=True), nullable=True)
    origin_note = Column(Text, nullable=True)

    # Destination Approval
    destination_approved_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )
    destination_approved_at = Column(DateTime(timezone=True), nullable=True)
    destination_note = Column(Text, nullable=True)

    # Rejection
    rejected_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
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
