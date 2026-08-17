"""
Hierarchical location models for church organizational structure.

This module defines the 6-level hierarchy of the DCLM church organization:
1. Nation (root) - Countries where the church operates
2. State - Administrative divisions within nations
3. Region - Groupings of areas within states
4. Group - Collections of locations
5. Location - Physical church buildings (DLBC, DLCF, DLSO)
6. Fellowship - Small groups within locations (leaf level)

Each model includes:
- Primary key (custom ID, not auto-increment)
- Foreign key to parent level (except Nation)
- ltree path for efficient hierarchical queries
- formatted_id property for display (e.g., DCM-234-KW-ILR)
- Timestamp and audit fields via mixins

The ltree path enables efficient queries like:
- Find all descendants: WHERE path <@ 'org.234.KW'
- Find all ancestors: WHERE 'org.234.KW.ILR.ILE.003' <@ path
- Find siblings: WHERE path ~ 'org.234.KW.*{1}'

Example hierarchy:
    org.234.KW.ILR.ILE.003.F001
    └── Nation: 234 (Nigeria)
        └── State: KW (Kwara)
            └── Region: ILR (Ilorin Region)
                └── Group: ILE (Ilorin East)
                    └── Location: 003
                        └── Fellowship: F001
"""
import uuid

from sqlalchemy import Column, String, ForeignKey, Float, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.core import TimestampMixin, AuditMixin
from app.models.core import LtreeType

class Nation(Base, TimestampMixin, AuditMixin):
    """
    Nation model - Root level of church hierarchy.
    
    Represents countries where the church operates. Nations are the top-level
    organizational unit with path format: org.{nation_id}
    
    Attributes:
        nation_id (str): Primary key, unique nation identifier (e.g., "234" for Nigeria)
        continent (str): Continent name (e.g., "Africa")
        country_name (str): Full country name (e.g., "Nigeria")
        capital (str): Capital city (optional)
        address (str): Physical address (optional)
        church_hq (str): Church headquarters location (optional)
        national_pastor (str): Name of national pastor (optional)
        path (ltree): Hierarchical path (auto-generated as org.{nation_id})
        
    Relationships:
        states: One-to-many relationship with State model
        
    Properties:
        formatted_id: Display ID in format DCM-{nation_id}
        
    Example:
        ```python
        nation = Nation(
            nation_id="234",
            continent="Africa",
            country_name="Nigeria",
            capital="Abuja",
            path="org.234"
        )
        print(nation.formatted_id)  # "DCM-234"
        ```
    """
    __tablename__ = "nations"

    nation_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    nation_code = Column(String, unique=True, nullable=False, index=True)
    continent = Column(String, nullable=False)
    country_name = Column(String, nullable=False)
    capital = Column(String, nullable=True)
    address = Column(String, nullable=True)
    church_hq = Column(String, nullable=True)
    national_pastor = Column(String, nullable=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    
    # Relationships
    states = relationship("State", back_populates="nation")

    @property
    def formatted_id(self) -> str:
        """Returns standard display ID: DCM-NationID"""
        return f"DCM-{str(self.path).replace('org.', '').replace('.', '-')}"


class State(Base, TimestampMixin, AuditMixin):
    __tablename__ = "states"

    state_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    nation_id = Column(UUID(as_uuid=False), ForeignKey("nations.nation_id"), nullable=False, index=True)
    state_code = Column(String, nullable=False, index=True)
    state_name = Column(String, nullable=False) # Changed from 'state' to 'state_name' to avoid conflict/ambiguity
    city = Column(String, nullable=True)
    address = Column(String, nullable=True)
    state_hq = Column(String, nullable=True)
    state_pastor = Column(String, nullable=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    
    # Relationships
    nation = relationship("Nation", back_populates="states")
    regions = relationship("Region", back_populates="state")

    __table_args__ = (
        UniqueConstraint("nation_id", "state_code", name="uq_states_nation_code"),
    )

    @property
    def formatted_id(self) -> str:
        """Returns standard display ID: DCM-Nation-State"""
        return f"DCM-{str(self.path).replace('org.', '').replace('.', '-')}"


class Region(Base, TimestampMixin, AuditMixin):
    __tablename__ = "regions"

    region_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    state_id = Column(UUID(as_uuid=False), ForeignKey("states.state_id"), nullable=False, index=True)
    region_code = Column(String, nullable=False, index=True)
    region_name = Column(String, nullable=False)
    region_head = Column(String, nullable=True)
    regional_pastor = Column(String, nullable=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    
    # Relationships
    state = relationship("State", back_populates="regions")
    groups = relationship("Group", back_populates="region") # 'group' is SQL keyword, using 'dclm_groups' table name safely

    __table_args__ = (
        UniqueConstraint("state_id", "region_code", name="uq_regions_state_code"),
    )

    @property
    def formatted_id(self) -> str:
        """Returns standard display ID: DCM-Nation-State-Region"""
        return f"DCM-{str(self.path).replace('org.', '').replace('.', '-')}"


class Group(Base, TimestampMixin, AuditMixin):
    __tablename__ = "dclm_groups" # Avoid reserved keyword 'groups'

    group_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    region_id = Column(UUID(as_uuid=False), ForeignKey("regions.region_id"), nullable=False, index=True)
    group_code = Column(String, nullable=False, index=True)
    group_name = Column(String, nullable=False)
    group_head = Column(String, nullable=True)
    group_pastor = Column(String, nullable=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    
    # Relationships
    region = relationship("Region", back_populates="groups")
    locations = relationship("Location", back_populates="group")

    __table_args__ = (
        UniqueConstraint("region_id", "group_code", name="uq_groups_region_code"),
    )

    @property
    def formatted_id(self) -> str:
        """Returns standard display ID: DCM-Nation-State-Region-Group"""
        return f"DCM-{str(self.path).replace('org.', '').replace('.', '-')}"


class Location(Base, TimestampMixin, AuditMixin):
    __tablename__ = "locations"

    location_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(UUID(as_uuid=False), ForeignKey("dclm_groups.group_id"), nullable=False, index=True)
    location_code = Column(String, nullable=False, index=True)
    location_name = Column(String, nullable=False)
    church_type = Column(String, nullable=False) # DLBC, DLCF, DLSO
    address = Column(String, nullable=True)
    associate_cord = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    
    # Relationships
    group = relationship("Group", back_populates="locations")
    fellowships = relationship("Fellowship", back_populates="location")
    profile = relationship("LocationProfile", back_populates="location", uselist=False)

    __table_args__ = (
        UniqueConstraint("group_id", "location_code", name="uq_locations_group_code"),
    )

    @property
    def formatted_id(self) -> str:
        """Returns standard display ID: DCM-Nation-State-Region-Group-Location"""
        return f"DCM-{str(self.path).replace('org.', '').replace('.', '-')}"


class Fellowship(Base, TimestampMixin, AuditMixin):
    __tablename__ = "fellowships"

    fellowship_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    location_id = Column(UUID(as_uuid=False), ForeignKey("locations.location_id"), nullable=False, index=True)
    fellowship_code = Column(String, nullable=False, index=True)
    fellowship_name = Column(String, nullable=False)
    fellowship_address = Column(String, nullable=True)
    associate_church = Column(String, nullable=True)
    location_name = Column(String, nullable=True) # Denormalized
    church_type = Column(String, nullable=True) # Denormalized
    leader_in_charge = Column(String, nullable=True)
    leader_contact = Column(String, nullable=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    
    # Relationships
    location = relationship("Location", back_populates="fellowships")

    __table_args__ = (
        UniqueConstraint("location_id", "fellowship_code", name="uq_fellowships_location_code"),
    )

    @property
    def formatted_id(self) -> str:
        """Returns standard display ID: DCM-Nation-State-Region-Group-Location-Fellowship"""
        return f"DCM-{str(self.path).replace('org.', '').replace('.', '-')}"
