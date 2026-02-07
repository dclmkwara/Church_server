"""
Offering models for financial data tracking.

Tracks tithes and offerings with payment method details.
Aggregated per event/location, not per individual.
"""
from sqlalchemy import Column, String, ForeignKey, Integer, DateTime, Boolean, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin
from app.models.core import LtreeType


class Offering(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Offering/Tithe Record.
    
    Tracks aggregated financial contributions for a specific event and location.
    Linked to ProgramEvent for date/program context.
    """
    __tablename__ = "offerings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), nullable=True, index=True) # For offline sync
    
    # Hierarchy Scope
    path = Column(LtreeType, nullable=False, index=True)
    location_id = Column(String, nullable=False, index=True)

    # Partitioning Key
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Event Link (Source of Truth for Date, Program Type, Domain)
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=False, index=True)
    
    # Financial Data
    amount = Column(Numeric(12, 2), nullable=False) # Up to 999,999,999.99
    payment_method = Column(String, nullable=False, index=True) # cash, bank_transfer, mobile_money, check
    
    # Metadata
    status = Column(String, default="pending", index=True) # pending, approved, rejected
    note = Column(Text, nullable=True)
    
    # Audit
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    
    # Relationships
    event = relationship("ProgramEvent")
    entered_by = relationship("User", foreign_keys=[entered_by_id])
    
    def __repr__(self):
        return f"<Offering(amount={self.amount}, method='{self.payment_method}', status='{self.status}')>"
