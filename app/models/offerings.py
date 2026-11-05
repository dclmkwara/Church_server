"""
Offering models for financial data tracking.

Tracks tithes and offerings with payment method details.
Aggregated per event/location, not per individual.
"""
from sqlalchemy import Column, String, ForeignKey, Integer, DateTime, Boolean, Text, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin
from app.models.core import LtreeType
from app.models.core import TimestampMixin


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
    location_id = Column(UUID(as_uuid=False), nullable=False, index=True)

    # Partitioning Key
    date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Event Link (Source of Truth for Date, Program Type, Domain)
    event_id = Column(UUID(as_uuid=True), ForeignKey("program_events.id"), nullable=True, index=True)
    church_type = Column(String(40), nullable=True, index=True)
    program_level = Column(String(20), nullable=True, index=True)
    program_domain_id = Column(Integer, ForeignKey("program_domains.id", ondelete="RESTRICT"), nullable=True, index=True)
    program_type_id = Column(Integer, ForeignKey("program_types.id", ondelete="RESTRICT"), nullable=True, index=True)
    program_scope_path = Column(LtreeType, nullable=True, index=True)
    program_domain = Column(String(80), nullable=True, index=True)
    program_type = Column(String(120), nullable=True, index=True)
    
    # Financial Data
    amount = Column(Numeric(12, 2), nullable=False) # Up to 999,999,999.99
    payment_method = Column(String, nullable=False, index=True) # cash, bank_transfer, mobile_money, check
    fund_type = Column(String, nullable=False, index=True, default="offering") # offering, tithe, seed, etc.
    
    # Metadata
    status = Column(String, nullable=False, default="pending", server_default="pending", index=True) # pending, corrected, approved, rejected, reversed
    note = Column(Text, nullable=True)
    
    # Audit
    entered_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    reviewed_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True, index=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_note = Column(Text, nullable=True)
    
    # Relationships
    event = relationship("ProgramEvent")
    entered_by = relationship("User", foreign_keys=[entered_by_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])
    
    def __repr__(self):
        return f"<Offering(amount={self.amount}, method='{self.payment_method}', status='{self.status}')>"


class OfferingAudit(Base, TimestampMixin):
    """Append-only record of financial review and correction actions."""
    __tablename__ = "offering_audits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    offering_id = Column(UUID(as_uuid=True), ForeignKey("offerings.id"), nullable=False, index=True)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)  # corrected, approved, rejected, deleted
    reason = Column(Text, nullable=False)
    before_values = Column(JSONB, nullable=False)
    after_values = Column(JSONB, nullable=False)

    offering = relationship("Offering")
    actor = relationship("User")
