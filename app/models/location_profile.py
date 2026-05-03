"""
Location Profile model.

Extends the Location model with documentary and historical information
about a specific church branch. One-to-one relationship with Location.

Used for:
- Church history and founding date
- Exact physical address with landmarks (for public website geo-search)
- Special projects tracking
- Branch cover image for public website listing
"""
from sqlalchemy import Column, String, Integer, Text, Date, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.models.core import TimestampMixin


class LocationProfile(Base, TimestampMixin):
    """
    Extended profile for a church location/branch.

    Linked one-to-one with Location. Contains documentary, historical,
    and address information not needed in every query of Location.

    Attributes:
        location_id: FK to locations table (unique — one profile per location)
        history: Free-text church history / about section
        founded_date: Date the branch was established
        founder_name: Name of the founding figure
        full_address: Complete human-readable street address
        landmark: Nearest landmark for directions (e.g. "Beside GTBank, GRA")
        google_maps_url: Optional direct Google Maps / Waze link
        special_projects: JSONB list of ongoing/completed projects
        cover_image_url: Image URL for public website branch card
    """
    __tablename__ = "location_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(
        String,
        ForeignKey("locations.location_id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Documentary
    history = Column(Text, nullable=True)
    founded_date = Column(Date, nullable=True)
    founder_name = Column(String, nullable=True)

    # Address Details (more specific than Location.address)
    full_address = Column(String, nullable=True)
    landmark = Column(String, nullable=True)
    google_maps_url = Column(String, nullable=True)

    # Projects
    # Format: [{"title": str, "description": str, "status": "ongoing"|"completed"}]
    special_projects = Column(JSONB, nullable=True, server_default="[]")

    # Media
    cover_image_url = Column(String, nullable=True)

    # Relationships
    location = relationship("Location", back_populates="profile")

    def __repr__(self) -> str:
        return f"<LocationProfile(location_id='{self.location_id}')>"
