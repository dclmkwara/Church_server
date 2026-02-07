"""
Count models for population tracking.

This module defines the models for tracking attendance counts (Men, Women, Youth, Children).
It supports offline sync via client_id and idempotency patterns.
"""
from sqlalchemy import Column, String, ForeignKey, Integer, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin
from app.models.core import LtreeType


class Count(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Population Count Record.
    
    Tracks the number of attendees in various categories for a specific program event.
    Designed for high-volume writes and offline synchronization.
    """
    __tablename__ = "counts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True) # For offline sync deduplication
    
    # Hierarchy Scope
    path = Column(LtreeType, nullable=False, index=True)
    location_id = Column(String, nullable=False, index=True)
    
    # Partitioning Key
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Event Link
    # We link to the specific scheduled event if possible, or just the type/date
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=True, index=True)
    
    # Demographics
    adult_male = Column(Integer, default=0, nullable=False)
    adult_female = Column(Integer, default=0, nullable=False)
    youth_male = Column(Integer, default=0, nullable=False)
    youth_female = Column(Integer, default=0, nullable=False)
    boys = Column(Integer, default=0, nullable=False)
    girls = Column(Integer, default=0, nullable=False)
    
    total = Column(Integer, default=0, nullable=False)
    
    # Metadata
    status = Column(String, default="pending", index=True) # pending, approved, rejected
    note = Column(Text, nullable=True)
    
    # Audit
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    
    # Relationships
    event = relationship("ProgramEvent")
    entered_by = relationship("User", foreign_keys=[entered_by_id])
    
    def calculate_total(self):
        self.total = (
            self.adult_male + self.adult_female + 
            self.youth_male + self.youth_female + 
            self.boys + self.girls
        )

    def __repr__(self):
        return f"<Count(total={self.total}, status='{self.status}')>"
