"""Program and Event models."""
from sqlalchemy import Column, String, ForeignKey, Integer, DateTime, Boolean, Date, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin
from app.models.core import LtreeType


class ProgramDomain(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "program_domains"
    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)
    program_types = relationship("ProgramType", back_populates="domain")
    campaigns = relationship("ProgramCampaign", back_populates="domain")
    def __repr__(self):
        return f"<ProgramDomain(title='{self.name}', slug='{self.slug}')>"


class ProgramType(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "program_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    domain_id = Column(Integer, ForeignKey("program_domains.id"), nullable=False, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    domain = relationship("ProgramDomain", back_populates="program_types")
    def __repr__(self):
        return f"<ProgramType(name='{self.name}', domain_id={self.domain_id})>"


class ProgramCampaign(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    __tablename__ = "program_campaigns"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id = Column(Integer, ForeignKey("program_domains.id"), nullable=False, index=True)
    path = Column(LtreeType, nullable=False, index=True)
    campaign_code = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    event_mode = Column(String, nullable=False, default="special", server_default="special", index=True)
    reporting_scope = Column(String, nullable=False, default="global", server_default="global", index=True)
    status = Column(String, nullable=False, default="draft", server_default="draft", index=True)
    alpha_location_id = Column(String, nullable=True, index=True)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    collection_window_start = Column(DateTime(timezone=True), nullable=True)
    collection_window_end = Column(DateTime(timezone=True), nullable=True)
    flyer_url = Column(String, nullable=True)
    publicity_note = Column(Text, nullable=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)

    domain = relationship("ProgramDomain", back_populates="campaigns")
    created_by = relationship("User", foreign_keys=[created_by_id])
    events = relationship("ProgramEvent", back_populates="campaign")

    def __repr__(self):
        return f"<ProgramCampaign(code='{self.campaign_code}', title='{self.title}', mode='{self.event_mode}')>"


class ProgramEvent(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    __tablename__ = "program_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_type_id = Column(Integer, ForeignKey("program_types.id"), nullable=False, index=True)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("program_campaigns.id"), nullable=True, index=True)
    path = Column(LtreeType, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    title = Column(String, nullable=True)
    is_public = Column(Boolean, nullable=False, default=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    event_mode = Column(String, nullable=False, default="regular", server_default="regular", index=True)
    reporting_scope = Column(String, nullable=False, default="location", server_default="location", index=True)
    campaign_code = Column(String, nullable=True, index=True)
    alpha_location_id = Column(String, nullable=True, index=True)
    is_alpha_event = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    collection_window_start = Column(DateTime(timezone=True), nullable=True)
    collection_window_end = Column(DateTime(timezone=True), nullable=True)
    audience_segment = Column(String, nullable=True, index=True)

    program_type = relationship("ProgramType")
    campaign = relationship("ProgramCampaign", back_populates="events")
    assignments = relationship("EventAssignment", back_populates="event")

    def __repr__(self):
        return f"<ProgramEvent(date='{self.date}', type_id={self.program_type_id}, mode='{self.event_mode}')>"


class EventAssignment(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    __tablename__ = "event_assignments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=False, index=True)
    worker_id = Column(UUID(as_uuid=True), ForeignKey("workers.worker_id"), nullable=False, index=True)
    path = Column(LtreeType, nullable=False, index=True)
    assignment_label = Column(String, nullable=True, index=True)
    assignment_type = Column(String, nullable=False, default="both", server_default="both", index=True)
    source_role = Column(String, nullable=False, default="alpha", server_default="alpha", index=True)
    status = Column(String, nullable=False, default="pending", server_default="pending", index=True)
    note = Column(Text, nullable=True)
    assigned_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    approved_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    submission_completed = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    event = relationship("ProgramEvent", back_populates="assignments")
    worker = relationship("Worker", foreign_keys=[worker_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])

    __table_args__ = (UniqueConstraint("event_id", "worker_id", name="uq_event_assignment_event_worker"),)

    def __repr__(self):
        return f"<EventAssignment(event_id='{self.event_id}', worker_id='{self.worker_id}', status='{self.status}')>"
