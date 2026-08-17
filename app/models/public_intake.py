"""
Public website intake models.

These models persist submissions coming from the public website so they can be
reviewed inside the admin system instead of only being logged transiently.
"""
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.core import TimestampMixin


class PublicContactSubmission(Base, TimestampMixin):
    __tablename__ = "public_contact_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, index=True)
    phone = Column(String, nullable=True)
    subject = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="new", index=True)
    review_note = Column(Text, nullable=True)
    reviewed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    reviewed_by = relationship("User")


class PublicPrayerSubmission(Base, TimestampMixin):
    __tablename__ = "public_prayer_submissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True)
    request = Column(Text, nullable=False)
    is_urgent = Column(Boolean, nullable=False, default=False, index=True)
    status = Column(String, nullable=False, default="new", index=True)
    review_note = Column(Text, nullable=True)
    reviewed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    reviewed_by = relationship("User")
