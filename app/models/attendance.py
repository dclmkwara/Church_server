"""
Worker Attendance models.
"""
from sqlalchemy import Column, String, ForeignKey, Integer, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
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
    location_id = Column(String, nullable=False, index=True)
    
    # Event Link (Source of Truth for Date, Program Type, Domain)
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=False, index=True)
    
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
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    
    # Relationships
    event = relationship("ProgramEvent")
    worker = relationship("Worker")
    entered_by = relationship("User", foreign_keys=[entered_by_id])
    
    def __repr__(self):
        return f"<WorkerAttendance(worker='{self.worker_name}', status='{self.status}')>"
