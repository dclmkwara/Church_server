"""Scoped, dynamically addressed messages for church app users."""

import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base
from app.models.core import LTreePathMixin, TimestampMixin


class BroadcastMessage(Base, TimestampMixin, LTreePathMixin):
    __tablename__ = "broadcast_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    sender_role_score = Column(String(2), nullable=False)
    target_level = Column(String(20), nullable=False, index=True)
    audience = Column(String(20), nullable=False, default="all_users", server_default="all_users", index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    priority = Column(String(12), nullable=False, default="normal", server_default="normal")
    sent_at = Column(DateTime(timezone=True), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
