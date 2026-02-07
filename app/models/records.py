"""
Record models for newcomer and convert registration.
"""
from sqlalchemy import Column, String, ForeignKey, Integer, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin
from app.models.core import LtreeType


class Record(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Newcomer/Convert Record.
    
    Tracks new visitors and new converts.
    Uses JSONB for flexible demographic data (occupation, school properties, etc.)
    to avoid sparse columns.
    """
    __tablename__ = "records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True) # For offline sync
    
    # Hierarchy Scope
    path = Column(LtreeType, nullable=False, index=True)
    location_id = Column(String, nullable=False, index=True)
    
    # Event Link (Source of Truth for Date, Program Type, Domain)
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=True, index=True)
    
    # Core Identity (Always Required/Present)
    record_type = Column(String, nullable=False, index=True) # newcomer, convert
    name = Column(String, nullable=False)
    gender = Column(String, nullable=False) # Male, Female
    phone = Column(String, nullable=False, index=True) # REQUIRED per user spec
    
    # Flexible Details (JSONB)
    # Stores: email, address, marital_status, occupation, invited_by, 
    # social_group, social_status, status_address, level, salvation_type, etc.
    details = Column(JSONB, nullable=True, server_default='{}')
    
    # Metadata
    status = Column(String, default="pending", index=True) # pending, contacted, followed_up
    note = Column(Text, nullable=True)
    
    # Audit
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    
    # Relationships
    event = relationship("ProgramEvent")
    entered_by = relationship("User", foreign_keys=[entered_by_id])
    
    def __repr__(self):
        return f"<Record(name='{self.name}', type='{self.record_type}', phone='{self.phone}')>"
