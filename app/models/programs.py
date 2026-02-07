"""
Program and Event models.

This module defines the models for church programs and scheduled events.
These serve as the metadata foundation for all data collection (counts, offerings, etc.).
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, String, ForeignKey, Integer, DateTime, Boolean, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import TimestampMixin, SoftDeleteMixin, LTreePathMixin
from app.models.core import LtreeType


class ProgramDomain(Base, TimestampMixin, SoftDeleteMixin):
    """
    Program Domain (Category).
    
    Examples:
        - Regular Service
        - Retreat
        - Conference
        - Crusade
    """
    __tablename__ = "program_domains"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String, unique=True, nullable=False, index=True) # e.g. regular_service
    name = Column(String, unique=True, nullable=False) # e.g. "Regular Service"
    description = Column(String, nullable=True)
    
    # Relationships
    program_types = relationship("ProgramType", back_populates="domain")
    
    def __repr__(self):
        return f"<ProgramDomain(title='{self.name}', slug='{self.slug}')>"


class ProgramType(Base, TimestampMixin, SoftDeleteMixin):
    """
    Program Type (Specific Service Type).
    
    Examples:
        - Sunday Worship Service (under Regular Service)
        - Monday Bible Study (under Regular Service)
        - Thursday Revival Hour (under Regular Service)
        - December Retreat (under Retreat)
    """
    __tablename__ = "program_types"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    domain_id = Column(Integer, ForeignKey("program_domains.id"), nullable=False, index=True)
    slug = Column(String, unique=True, nullable=False, index=True) # e.g. sunday_worship
    name = Column(String, nullable=False) # e.g. "Sunday Worship Service"
    description = Column(String, nullable=True)
    
    # Relationships
    domain = relationship("ProgramDomain", back_populates="program_types")
    # events = relationship("ProgramEvent", back_populates="program_type") # Forward ref issues?
    
    def __repr__(self):
        return f"<ProgramType(name='{self.name}', domain_id={self.domain_id})>"


class ProgramEvent(Base, TimestampMixin, SoftDeleteMixin, LTreePathMixin):
    """
    Scheduled Program Event.
    
    Represents a specific instance of a program type scheduled at a specific time/location.
    This is what Counts and Offerings are linked to.
    """
    __tablename__ = "program_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Link to Metadata
    program_type_id = Column(Integer, ForeignKey("program_types.id"), nullable=False, index=True)
    
    # Scope/Level
    # Events can be global (e.g. Easter Retreat) or local (e.g. Special Revival)
    # We use path to determine scope. If path is "org.234", it's national.
    # If path is "org.234.KW.ILN.ILE.001", it's location-specific.
    path = Column(LtreeType, nullable=False, index=True)
    
    date = Column(Date, nullable=False, index=True)
    title = Column(String, nullable=True) # Optional override title
    
    # Relationships
    program_type = relationship("ProgramType")
    
    def __repr__(self):
        return f"<ProgramEvent(date='{self.date}', type_id={self.program_type_id})>"
