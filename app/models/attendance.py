"""
Worker Attendance models.
"""
from sqlalchemy import Column, String, ForeignKey, Integer, Date, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin
from app.models.core import LtreeType


class WorkerAttendance(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Worker Attendance Record.
    
    Tracks attendance for workers' meetings (e.g., Monday Bible Study workers' waiting, etc.).
    Partitioned by month (conceptually, implemented via separate tables or potential future partitioning).
    Linked to ProgramEvent for date/context.
    """
    __tablename__ = "worker_attendance"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True) # For offline sync
    
    # Hierarchy Scope
    path = Column(LtreeType, nullable=False, index=True)
    location_id = Column(UUID(as_uuid=False), nullable=False, index=True)
    
    # Event Link (Source of Truth for Date, Program Type, Domain)
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=True, index=True)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("event_assignments.id"), nullable=True, index=True)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("event_assignments.id"), nullable=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    church_type = Column(String(40), nullable=True, index=True)
    program_level = Column(String(20), nullable=True, index=True)
    program_domain_id = Column(Integer, ForeignKey("program_domains.id", ondelete="RESTRICT"), nullable=True, index=True)
    program_type_id = Column(Integer, ForeignKey("program_types.id", ondelete="RESTRICT"), nullable=True, index=True)
    program_scope_path = Column(LtreeType, nullable=True, index=True)
    program_domain = Column(String(80), nullable=True, index=True)
    program_type = Column(String(120), nullable=True, index=True)
    
    # Worker Link
    worker_id = Column(UUID(as_uuid=True), ForeignKey("workers.worker_id"), nullable=False, index=True)
    
    # Denormalized Worker Details (Snapshot at time of attendance)
    # Useful if worker details change later, we know who attended exactly as they were known then.
    # Also helpful for quick reporting without complex joins.
    worker_name = Column(String, nullable=False)
    worker_phone = Column(String, nullable=False)
    worker_unit = Column(String, nullable=True)
    
    # Attendance Status
    status = Column(String, nullable=False, default="present", index=True) # present, absent, late, excused
    reason = Column(Text, nullable=True) # If absent/excused
    
    # Metadata
    note = Column(Text, nullable=True)
    submission_id = Column(UUID(as_uuid=True), ForeignKey("worker_attendance_submissions.id", ondelete="SET NULL"), nullable=True, index=True)
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    
    # Relationships
    event = relationship("ProgramEvent")
    assignment = relationship("EventAssignment")
    assignment = relationship("EventAssignment")
    worker = relationship("Worker")
    entered_by = relationship("User", foreign_keys=[entered_by_id])
    
    def __repr__(self):
        return f"<WorkerAttendance(worker='{self.worker_name}', status='{self.status}')>"


class WorkerAttendanceSubmission(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """One usher's complete roster capture for one service context."""
    __tablename__ = "worker_attendance_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=False, unique=True)
    path = Column(LtreeType, nullable=False, index=True)
    location_id = Column(UUID(as_uuid=False), ForeignKey("locations.location_id"), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=True, index=True)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("event_assignments.id"), nullable=True, index=True)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("event_assignments.id"), nullable=True, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    church_type = Column(String(40), nullable=False, index=True)
    program_level = Column(String(20), nullable=True, index=True)
    program_domain_id = Column(Integer, ForeignKey("program_domains.id", ondelete="RESTRICT"), nullable=True, index=True)
    program_type_id = Column(Integer, ForeignKey("program_types.id", ondelete="RESTRICT"), nullable=True, index=True)
    program_scope_path = Column(LtreeType, nullable=True, index=True)
    program_domain = Column(String(80), nullable=True, index=True)
    program_type = Column(String(120), nullable=False, index=True)
    expected_workers_count = Column(Integer, nullable=False)
    # Full approved roster snapshot for deduplication across multiple usher
    # submissions. Null means a legacy row where only the count was retained.
    expected_worker_ids = Column(JSONB, nullable=True)
    present_count = Column(Integer, nullable=False)
    present_workers = Column(JSONB, nullable=False)
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    submitted_by_worker_id = Column(UUID(as_uuid=True), ForeignKey("workers.worker_id"), nullable=True, index=True)
    submitted_by_name = Column(String(255), nullable=False)
    note = Column(Text, nullable=True)

    event = relationship("ProgramEvent")
    assignment = relationship("EventAssignment")
    assignment = relationship("EventAssignment")
    location = relationship("Location")
    entered_by = relationship("User", foreign_keys=[entered_by_id])
    attendance_rows = relationship("WorkerAttendance", foreign_keys="WorkerAttendance.submission_id")

    def __repr__(self):
        return f"<WorkerAttendanceSubmission(id='{self.id}', present_count={self.present_count})>"


class WorkerAbsenceNotice(Base, TimestampMixin):
    """
    Worker Absence Notice.

    Allows workers to proactively report expected absences before a meeting.
    Helps pastors anticipate worker unavailability and reduces false
    'absent without notice' marks on the attendance tracker.

    Status values:
        noted        — Submitted, not yet reviewed
        acknowledged — Pastor has seen and accepted this notice
        rejected     — Pastor has rejected/dismissed this notice
    """
    __tablename__ = "worker_absence_notices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workers.worker_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id = Column(
        UUID(as_uuid=True),
        ForeignKey("program_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason = Column(Text, nullable=False)
    expected_return = Column(Date, nullable=True)

    # Review
    status = Column(String, default="noted", nullable=False, index=True)
    acknowledged_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
        index=True,
    )
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    admin_note = Column(Text, nullable=True)

    # Relationships
    worker = relationship("Worker")
    event = relationship("ProgramEvent")
    acknowledged_by_user = relationship("User", foreign_keys=[acknowledged_by])

    def __repr__(self) -> str:
        return f"<WorkerAbsenceNotice(worker={self.worker_id}, event={self.event_id}, status='{self.status}')>"
