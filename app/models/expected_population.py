"""Versioned Sunday congregation attendance estimates by location."""
from sqlalchemy import Column, Date, DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from app.db.base import Base
from app.models.core import LtreeType


class LocationExpectedPopulation(Base):
    """An immutable estimate version; newest effective version applies by date."""

    __tablename__ = "location_expected_population"
    __table_args__ = (
        Index("ix_location_expected_population_location_effective", "location_id", "effective_from", "created_at"),
        Index("ix_location_expected_population_path_gist", "path", postgresql_using="gist"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    location_id = Column(UUID(as_uuid=False), ForeignKey("locations.location_id", ondelete="RESTRICT"), nullable=False)
    path = Column(LtreeType, nullable=False)
    expected_value = Column(Integer, nullable=False)
    effective_from = Column(Date, nullable=False)
    set_by_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    location = relationship("Location")
    set_by = relationship("User", foreign_keys=[set_by_id])
