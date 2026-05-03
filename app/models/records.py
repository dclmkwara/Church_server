"""
Record models for newcomer and convert registration.
"""
from sqlalchemy import Column, String, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin
from app.models.core import LtreeType


class Record(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    __tablename__ = "records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    path = Column(LtreeType, nullable=False, index=True)
    location_id = Column(String, nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=True, index=True)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("event_assignments.id"), nullable=True, index=True)
    record_type = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    gender = Column(String, nullable=False)
    phone = Column(String, nullable=False, index=True)
    details = Column(JSONB, nullable=True, server_default='{}')
    status = Column(String, default="pending", index=True)
    note = Column(Text, nullable=True)
    source_role = Column(String, nullable=False, default="regular", server_default="regular", index=True)
    campaign_code = Column(String, nullable=True, index=True)
    submission_channel = Column(String, nullable=False, default="admin_web", server_default="admin_web", index=True)
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)

    event = relationship("ProgramEvent")
    assignment = relationship("EventAssignment")
    entered_by = relationship("User", foreign_keys=[entered_by_id])

    def __repr__(self):
        return f"<Record(name='{self.name}', type='{self.record_type}', phone='{self.phone}', source_role='{self.source_role}')>"
