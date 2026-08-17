"""
Pydantic schemas for hierarchy locations.
"""
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime

# --- Shared Base Classes ---
class HierarchyCreateBase(BaseModel):
    """Base schema for creating hierarchy nodes - NO path field (auto-generated)."""
    pass

class HierarchyResponseBase(BaseModel):
    """Base schema for hierarchy responses - includes auto-generated path."""
    path: str

    @field_validator("path", mode="before")
    @classmethod
    def path_to_str(cls, v):
        """Convert ltree object to string if needed."""
        return str(v) if v is not None else None


# --- Nation Schemas ---
class NationBase(BaseModel):
    """Base fields for Nation."""
    continent: str
    country_name: str
    capital: Optional[str] = None
    address: Optional[str] = None
    church_hq: Optional[str] = None
    national_pastor: Optional[str] = None

class NationCreate(NationBase):
    """Schema for creating a Nation."""
    nation_code: str  # e.g. "234"

class NationUpdate(BaseModel):
    """Schema for updating a Nation."""
    continent: Optional[str] = None
    country_name: Optional[str] = None
    capital: Optional[str] = None
    address: Optional[str] = None
    church_hq: Optional[str] = None
    national_pastor: Optional[str] = None

class NationResponse(NationBase):
    """Schema for Nation response."""
    model_config = ConfigDict(from_attributes=True)

    nation_id: str
    nation_code: str
    path: str
    formatted_id: str
    created_at: datetime
    # states: List['StateResponse'] = [] # Avoid circularity or heavy loading default


# --- State Schemas ---
class StateBase(BaseModel):
    """Base fields for State."""
    state_name: str
    city: Optional[str] = None
    address: Optional[str] = None
    state_hq: Optional[str] = None
    state_pastor: Optional[str] = None

class StateCreate(StateBase):
    """Schema for creating a State."""
    state_code: str # e.g. "KW"
    nation_id: str

class StateUpdate(BaseModel):
    """Schema for updating a State."""
    state_name: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    state_hq: Optional[str] = None
    state_pastor: Optional[str] = None

class StateResponse(StateBase):
    """Schema for State response."""
    model_config = ConfigDict(from_attributes=True)

    state_id: str
    state_code: str
    nation_id: str
    path: str
    formatted_id: str
    created_at: datetime


# --- Region Schemas ---
class RegionBase(BaseModel):
    """Base fields for Region."""
    region_name: str
    region_head: Optional[str] = None
    regional_pastor: Optional[str] = None

class RegionCreate(RegionBase):
    """Schema for creating a Region."""
    region_code: str # e.g. "ILR"
    state_id: str

class RegionUpdate(BaseModel):
    """Schema for updating a Region."""
    region_name: Optional[str] = None
    region_head: Optional[str] = None
    regional_pastor: Optional[str] = None

class RegionResponse(RegionBase):
    """Schema for Region response."""
    model_config = ConfigDict(from_attributes=True)

    region_id: str
    region_code: str
    state_id: str
    path: str
    formatted_id: str
    created_at: datetime


# --- Group Schemas ---
class GroupBase(BaseModel):
    """Base fields for Group."""
    group_name: str
    group_head: Optional[str] = None
    group_pastor: Optional[str] = None

class GroupCreate(GroupBase):
    """Schema for creating a Group."""
    group_code: str # e.g. "ILE"
    region_id: str

class GroupUpdate(BaseModel):
    """Schema for updating a Group."""
    group_name: Optional[str] = None
    group_head: Optional[str] = None
    group_pastor: Optional[str] = None

class GroupResponse(GroupBase):
    """Schema for Group response."""
    model_config = ConfigDict(from_attributes=True)

    group_id: str
    group_code: str
    region_id: str
    path: str
    formatted_id: str
    created_at: datetime


# --- Location Schemas ---
class LocationBase(BaseModel):
    """Base fields for Location."""
    location_name: str
    church_type: str # DLBC, DLCF, YPF...
    address: Optional[str] = None
    associate_cord: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class LocationCreate(LocationBase):
    """Schema for creating a Location."""
    location_code: Optional[str] = None # e.g. "001"; auto-generated within group when omitted
    group_id: str

class LocationUpdate(BaseModel):
    """Schema for updating a Location."""
    location_name: Optional[str] = None
    church_type: Optional[str] = None
    address: Optional[str] = None
    associate_cord: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class LocationResponse(LocationBase):
    """Schema for Location response."""
    model_config = ConfigDict(from_attributes=True)

    location_id: str
    location_code: str
    group_id: str
    path: str
    formatted_id: str
    created_at: datetime


class LocationDetailResponse(BaseModel):
    """Schema for detailed location info with hierarchy names."""
    model_config = ConfigDict(from_attributes=True)

    location_id: str
    location_code: str
    location_name: str
    church_type: str
    group_id: str
    group_code: str
    group_name: str
    region_id: str
    region_code: str
    region_name: str
    state_id: str
    state_code: str
    state_name: str


# --- Fellowship Schemas ---
class FellowshipBase(BaseModel):
    """Base fields for Fellowship."""
    fellowship_name: str
    fellowship_address: Optional[str] = None
    associate_church: Optional[str] = None
    leader_in_charge: Optional[str] = None
    leader_contact: Optional[str] = None

class FellowshipCreate(FellowshipBase):
    """Schema for creating a Fellowship."""
    fellowship_code: str # e.g. "F001"
    location_id: str

class FellowshipUpdate(BaseModel):
    """Schema for updating a Fellowship."""
    fellowship_name: Optional[str] = None
    fellowship_address: Optional[str] = None
    associate_church: Optional[str] = None
    leader_in_charge: Optional[str] = None
    leader_contact: Optional[str] = None

class FellowshipResponse(FellowshipBase):
    """Schema for Fellowship response."""
    model_config = ConfigDict(from_attributes=True)

    fellowship_id: str
    fellowship_code: str
    location_id: str
    location_name: Optional[str] = None
    church_type: Optional[str] = None
    path: str
    formatted_id: str
    created_at: datetime

# --- Tree View Schema ---
class TreeNode(BaseModel):
    """Recursive schema for hierarchy tree view."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: Optional[str] = None
    name: str
    type: str # 'nation', 'state', etc.
    path: str
    formatted_id: str
    children: List['TreeNode'] = Field(default_factory=list)

TreeNode.model_rebuild()
