"""
Church Member model.

Tracks the full congregation at a location level — separate from:
- Worker table (staff/workers only)
- FellowshipMember (fellowship small-group registry)

This allows a location pastor to maintain a complete member directory,
monitor service attendance per individual, and do follow-up on absentees.
"""
import uuid
from sqlalchemy import Column, String, Integer, Boolean, Date, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin, LtreeType


class ChurchMember(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Church Congregation Member Registry.

    Location-scoped member directory for the full congregation.
    Distinct from worker registration; this covers all members including
    those who do not serve in any official unit.

    Attributes:
        location_id: The branch this member belongs to
        fellowship_id: Their assigned House Fellowship (optional)
        is_worker: True if this member is also a registered worker
        worker_id: Optional FK to Worker table if is_worker is True
        status: active | inactive | transferred | deceased
    """
    __tablename__ = "church_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True)

    # Hierarchy Scope
    path = Column(LtreeType, nullable=False, index=True)
    location_id = Column(
        String,
        ForeignKey("locations.location_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Personal Identity
    name = Column(String, nullable=False)
    gender = Column(String, nullable=False)            # Male, Female
    phone = Column(String, nullable=True, index=True)
    email = Column(String, nullable=True)
    address = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    marital_status = Column(String, nullable=True)     # Single, Married, Widowed, Divorced
    occupation = Column(String, nullable=True)

    # Church Details
    member_since = Column(Date, nullable=True)         # Date they joined this location
    fellowship_id = Column(
        String,
        ForeignKey("fellowships.fellowship_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    unit = Column(String, nullable=True)               # Serving unit if applicable

    # Worker Link (optional — bridges to Worker table for dual-role persons)
    is_worker = Column(Boolean, default=False, nullable=False)
    worker_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workers.worker_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Status
    status = Column(String, default="active", nullable=False, index=True)
    # active | inactive | transferred | deceased
    status_note = Column(Text, nullable=True)

    # Audit
    entered_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
    )

    # Relationships
    location = relationship("Location")
    fellowship = relationship("Fellowship")
    worker = relationship("Worker", foreign_keys=[worker_id])
    entered_by = relationship("User", foreign_keys=[entered_by_id])

    def __repr__(self) -> str:
        return f"<ChurchMember(name='{self.name}', location='{self.location_id}', status='{self.status}')>"
