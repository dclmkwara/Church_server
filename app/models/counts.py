"""
Count models for population tracking.
"""
from sqlalchemy import Column, String, ForeignKey, Integer, DateTime, Boolean, Text, Date, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
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

    # Null values identify legacy submissions; do not infer split semantics for them.
    count_mode = Column(String(12), nullable=True)
    section_label = Column(String(120), nullable=True)
    count_group_id = Column(UUID(as_uuid=True), ForeignKey("count_groups.id", ondelete="SET NULL"), nullable=True, index=True)

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
    count_group = relationship("CountGroup", foreign_keys=[count_group_id])
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


class CountGroup(Base, TimestampMixin):
    __tablename__ = "count_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_key = Column(String(400), nullable=False, unique=True, index=True)
    location_id = Column(UUID(as_uuid=False), nullable=False, index=True)
    program_type_key = Column(String(120), nullable=False)
    occurrence_date = Column(Date, nullable=False, index=True)
    reporting_scope_path = Column(String, nullable=True)
    service_id = Column(String(60), nullable=False, default="main", server_default="main")
    count_mode = Column(String(12), nullable=True)
    lead_usher_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    state = Column(String(12), nullable=False, default="open", server_default="open", index=True)
    finalized_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    finalized_at = Column(DateTime(timezone=True), nullable=True)
    close_reason = Column(Text, nullable=True)
    auto_closed_at = Column(DateTime(timezone=True), nullable=True)


class CountSectionSuggestion(Base, TimestampMixin):
    __tablename__ = "count_section_suggestions"
    __table_args__ = (UniqueConstraint("location_id", "label_key", name="uq_count_section_suggestion_location_label"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location_id = Column(UUID(as_uuid=False), ForeignKey("locations.location_id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(120), nullable=False)
    label_key = Column(String(120), nullable=False)
    is_hidden = Column(Boolean, nullable=False, default=False, server_default="false")
    updated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)


class SubmissionEditRevision(Base):
    """Append-only edit and return audit for submitted field records."""
    __tablename__ = "submission_edit_revisions"
    __table_args__ = (
        UniqueConstraint("submission_type", "submission_id", "edit_id", name="uq_submission_edit_id"),
        UniqueConstraint("submission_type", "submission_id", "revision_no", name="uq_submission_revision_no"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    submission_type = Column(String(40), nullable=False, index=True)
    submission_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    edit_id = Column(UUID(as_uuid=True), nullable=False)
    revision_no = Column(Integer, nullable=False)
    action = Column(String(20), nullable=False, index=True)
    editor_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    before_values = Column(JSONB, nullable=False)
    after_values = Column(JSONB, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default="now()", index=True)

class CountReminderRecipient(Base):
    """Auditable direct reminder delivery to a specific location usher/pastor."""
    __tablename__ = "count_reminder_recipients"
    __table_args__ = (
        Index("ix_count_reminder_location_day_sent", "location_id", "occurrence_date", "sent_at"),
        Index("ix_count_reminder_recipient_sent", "recipient_user_id", "sent_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reminder_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    recipient_user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    sent_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    location_id = Column(UUID(as_uuid=False), ForeignKey("locations.location_id", ondelete="RESTRICT"), nullable=False)
    occurrence_date = Column(Date, nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=False)
