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
- formatted_id property for display (e.g., DCM-234-KW-ILN)
- Timestamp and audit fields via mixins

The ltree path enables efficient queries like:
- Find all descendants: WHERE path <@ 'org.234.KW'
- Find all ancestors: WHERE 'org.234.KW.ILN.ILE.001' <@ path
- Find siblings: WHERE path ~ 'org.234.KW.*{1}'

Example hierarchy:
    org.234.KW.ILN.ILE.001.F001
    └── Nation: 234 (Nigeria)
        └── State: KW (Kwara)
            └── Region: ILN (Ilorin North)
                └── Group: ILE (Ilorin East)
                    └── Location: 001
                        └── Fellowship: F001
"""
from typing import Optional, List
from sqlalchemy import Column, String, ForeignKey, Integer, Text, Boolean, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base import Base
from app.models.core import TimestampMixin, AuditMixin, SoftDeleteMixin, LTreePathMixin
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

    nation_id = Column(String, primary_key=True, index=True)
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
        return f"DCM-{self.nation_id}"


class State(Base, TimestampMixin, AuditMixin):
    __tablename__ = "states"

    state_id = Column(String, primary_key=True, index=True)
    nation_id = Column(String, ForeignKey("nations.nation_id"), nullable=False)
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

    @property
    def formatted_id(self) -> str:
        """Returns standard display ID: DCM-Nation-State"""
        return f"DCM-{str(self.path).replace('org.', '').replace('.', '-')}"


class Region(Base, TimestampMixin, AuditMixin):
    __tablename__ = "regions"

    region_id = Column(String, primary_key=True, index=True)
    state_id = Column(String, ForeignKey("states.state_id"), nullable=False)
    region_name = Column(String, nullable=False)
    region_head = Column(String, nullable=True)
    regional_pastor = Column(String, nullable=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    
    # Relationships
    state = relationship("State", back_populates="regions")
    groups = relationship("Group", back_populates="region") # 'group' is SQL keyword, using 'dclm_groups' table name safely

    @property
    def formatted_id(self) -> str:
        """Returns standard display ID: DCM-Nation-State-Region"""
        return f"DCM-{str(self.path).replace('org.', '').replace('.', '-')}"


class Group(Base, TimestampMixin, AuditMixin):
    __tablename__ = "dclm_groups" # Avoid reserved keyword 'groups'

    group_id = Column(String, primary_key=True, index=True)
    region_id = Column(String, ForeignKey("regions.region_id"), nullable=False)
    group_name = Column(String, nullable=False)
    group_head = Column(String, nullable=True)
    group_pastor = Column(String, nullable=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    
    # Relationships
    region = relationship("Region", back_populates="groups")
    locations = relationship("Location", back_populates="group")

    @property
    def formatted_id(self) -> str:
        """Returns standard display ID: DCM-Nation-State-Region-Group"""
        return f"DCM-{str(self.path).replace('org.', '').replace('.', '-')}"


class Location(Base, TimestampMixin, AuditMixin):
    __tablename__ = "locations"

    location_id = Column(String, primary_key=True, index=True)
    group_id = Column(String, ForeignKey("dclm_groups.group_id"), nullable=False)
    location_name = Column(String, nullable=False)
    church_type = Column(String, nullable=False) # DLBC, DLCF, DLSO
    address = Column(String, nullable=True)
    associate_cord = Column(String, nullable=True)
    
    # Hierarchy
    path = Column(LtreeType, nullable=False, index=True)
    
    # Relationships
    group = relationship("Group", back_populates="locations")
    fellowships = relationship("Fellowship", back_populates="location")

    @property
    def formatted_id(self) -> str:
        """Returns standard display ID: DCM-Nation-State-Region-Group-Location"""
        return f"DCM-{str(self.path).replace('org.', '').replace('.', '-')}"


class Fellowship(Base, TimestampMixin, AuditMixin):
    __tablename__ = "fellowships"

    fellowship_id = Column(String, primary_key=True, index=True)
    location_id = Column(String, ForeignKey("locations.location_id"), nullable=False)
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

    @property
    def formatted_id(self) -> str:
        """Returns standard display ID: DCM-Nation-State-Region-Group-Location-Fellowship"""
        return f"DCM-{str(self.path).replace('org.', '').replace('.', '-')}"
