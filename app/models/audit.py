"""
Audit and Sync Models.

This module contains models for:
1. IdempotencyKey: Prevents duplicate processing of offline-synced records.
2. AuditLog: Tracks significant system actions for security and debugging.
3. ClientSyncQueue: Manages batch synchronization status (optional/advanced).
"""
from sqlalchemy import Column, String, ForeignKey, Integer, DateTime, Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from app.db.base import Base
from app.models.core import TimestampMixin

class IdempotencyKey(Base):
    """
    Idempotency Key for offline synchronization.
    
    When a mobile client creates a record offline, it generates a UUID (client_id).
    Upon sync, if this client_id exists in this table, the server returns the existing 
    record instead of creating a new one (duplicate prevention).
    """
    __tablename__ = "idempotency_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), unique=True, index=True, nullable=False)
    
    resource_type = Column(String, nullable=False, index=True) # e.g., 'count', 'offering'
    resource_id = Column(UUID(as_uuid=True), nullable=False) # The server-side generated ID
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True) # Optional TTL
    
    def __repr__(self):
        return f"<IdempotencyKey(client_id='{self.client_id}', resource='{self.resource_type}')>"


class NotificationReadState(Base, TimestampMixin):
    """
    Per-user read state for aggregated notification items.

    Notification items are derived from domain records like counts, offerings,
    prayer requests, approvals, and fellowship activity. This table keeps the
    user's read/unread decision without duplicating the underlying notification
    source record.
    """

    __tablename__ = "notification_read_states"
    __table_args__ = (
        UniqueConstraint("user_id", "notification_key", name="uq_notification_read_state_user_key"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    notification_key = Column(String, nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True, index=True)

    user = relationship("User")


class AuditLog(Base):
    """
    System Audit Log.
    
    Tracks important actions like user creation, role changes, and batch syncs.
    Immutable log (no update/delete permissions usually).
    """
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    action = Column(String, nullable=False, index=True) # e.g., 'CREATE_USER', 'SYNC_BATCH'
    resource_type = Column(String, nullable=True) # e.g., 'user', 'sync'
    resource_id = Column(String, nullable=True) # Can be UUID or other ID type
    
    changes = Column(JSONB, nullable=True) # specific changes made
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User")
