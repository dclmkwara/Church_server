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
    location_id = Column(UUID(as_uuid=False), nullable=False, index=True)
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=True, index=True)
    church_type = Column(String(40), nullable=True, index=True)
    program_level = Column(String(20), nullable=True, index=True)
    program_domain_id = Column(Integer, ForeignKey("program_domains.id", ondelete="RESTRICT"), nullable=True, index=True)
    program_type_id = Column(Integer, ForeignKey("program_types.id", ondelete="RESTRICT"), nullable=True, index=True)
    program_scope_path = Column(LtreeType, nullable=True, index=True)
    program_domain = Column(String(80), nullable=True, index=True)
    program_type = Column(String(120), nullable=True, index=True)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("event_assignments.id"), nullable=True, index=True)

    adult_male = Column(Integer, default=0, nullable=False)
    adult_female = Column(Integer, default=0, nullable=False)
    youth_male = Column(Integer, default=0, nullable=False)
    youth_female = Column(Integer, default=0, nullable=False)
    boys = Column(Integer, default=0, nullable=False)
    girls = Column(Integer, default=0, nullable=False)
    total = Column(Integer, default=0, nullable=False)

    status = Column(String, default="pending", index=True)
    approved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    auto_accepted = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    supersedes_id = Column(UUID(as_uuid=True), ForeignKey("counts.id", ondelete="SET NULL"), nullable=True, index=True)
    rejection_reason = Column(Text, nullable=True)
    rejected_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(Text, nullable=True)
    source_role = Column(String, nullable=False, default="regular", server_default="regular", index=True)
    campaign_code = Column(String, nullable=True, index=True)
    submission_channel = Column(String, nullable=False, default="admin_web", server_default="admin_web", index=True)

    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)

    event = relationship("ProgramEvent")
    assignment = relationship("EventAssignment")
    entered_by = relationship("User", foreign_keys=[entered_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    rejected_by = relationship("User", foreign_keys=[rejected_by_id])
    supersedes = relationship("Count", remote_side=[id], foreign_keys=[supersedes_id], uselist=False)

    def calculate_total(self):
        self.total = (
            self.adult_male + self.adult_female +
            self.youth_male + self.youth_female +
            self.boys + self.girls
        )

    def __repr__(self):
        return f"<Count(total={self.total}, status='{self.status}', source_role='{self.source_role}')>"
