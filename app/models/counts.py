"""
Count models for population tracking.
"""
from sqlalchemy import Column, String, ForeignKey, Integer, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin
from app.models.core import LtreeType


class Count(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    __tablename__ = "counts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    path = Column(LtreeType, nullable=False, index=True)
    location_id = Column(String, nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=True, index=True)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("event_assignments.id"), nullable=True, index=True)

    adult_male = Column(Integer, default=0, nullable=False)
    adult_female = Column(Integer, default=0, nullable=False)
    youth_male = Column(Integer, default=0, nullable=False)
    youth_female = Column(Integer, default=0, nullable=False)
    boys = Column(Integer, default=0, nullable=False)
    girls = Column(Integer, default=0, nullable=False)
    total = Column(Integer, default=0, nullable=False)

    status = Column(String, default="pending", index=True)
    note = Column(Text, nullable=True)
    source_role = Column(String, nullable=False, default="regular", server_default="regular", index=True)
    campaign_code = Column(String, nullable=True, index=True)
    submission_channel = Column(String, nullable=False, default="admin_web", server_default="admin_web", index=True)

    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)

    event = relationship("ProgramEvent")
    assignment = relationship("EventAssignment")
    entered_by = relationship("User", foreign_keys=[entered_by_id])

    def calculate_total(self):
        self.total = (
            self.adult_male + self.adult_female +
            self.youth_male + self.youth_female +
            self.boys + self.girls
        )

    def __repr__(self):
        return f"<Count(total={self.total}, status='{self.status}', source_role='{self.source_role}')>"
