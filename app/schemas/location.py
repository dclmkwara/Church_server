"""
Pydantic schemas for hierarchy locations.
"""
from typing import Optional, List
from pydantic import BaseModel, validator
from datetime import datetime

# --- Shared Base Classes ---
class HierarchyCreateBase(BaseModel):
    """Base schema for creating hierarchy nodes - NO path field (auto-generated)."""
    pass

class HierarchyResponseBase(BaseModel):
    """Base schema for hierarchy responses - includes auto-generated path."""
    path: str
    
    @validator('path', pre=True)
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
    nation_id: str  # Creating explicitly requires ID for now, or we gen it? Usually explicit "234"

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
    nation_id: str
    path: str
    formatted_id: str
    created_at: datetime
    # states: List['StateResponse'] = [] # Avoid circularity or heavy loading default

    class Config:
        from_attributes = True


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
    state_id: str # e.g. "KW"
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
    state_id: str
    nation_id: str
    path: str
    formatted_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Region Schemas ---
class RegionBase(BaseModel):
    """Base fields for Region."""
    region_name: str
    region_head: Optional[str] = None
    regional_pastor: Optional[str] = None

class RegionCreate(RegionBase):
    """Schema for creating a Region."""
    region_id: str # e.g. "ILN"
    state_id: str

class RegionUpdate(BaseModel):
    """Schema for updating a Region."""
    region_name: Optional[str] = None
    region_head: Optional[str] = None
    regional_pastor: Optional[str] = None

class RegionResponse(RegionBase):
    """Schema for Region response."""
    region_id: str
    state_id: str
    path: str
    formatted_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Group Schemas ---
class GroupBase(BaseModel):
    """Base fields for Group."""
    group_name: str
    group_head: Optional[str] = None
    group_pastor: Optional[str] = None

class GroupCreate(GroupBase):
    """Schema for creating a Group."""
    group_id: str # e.g. "ILE"
    region_id: str

class GroupUpdate(BaseModel):
    """Schema for updating a Group."""
    group_name: Optional[str] = None
    group_head: Optional[str] = None
    group_pastor: Optional[str] = None

class GroupResponse(GroupBase):
    """Schema for Group response."""
    group_id: str
    region_id: str
    path: str
    formatted_id: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Location Schemas ---
class LocationBase(BaseModel):
    """Base fields for Location."""
    location_name: str
    church_type: str # DLBC, DLCF...
    address: Optional[str] = None
    associate_cord: Optional[str] = None

class LocationCreate(LocationBase):
    """Schema for creating a Location."""
    location_id: str # e.g. "001"
    group_id: str

class LocationUpdate(BaseModel):
    """Schema for updating a Location."""
    location_name: Optional[str] = None
    church_type: Optional[str] = None
    address: Optional[str] = None
    associate_cord: Optional[str] = None

class LocationResponse(LocationBase):
    """Schema for Location response."""
    location_id: str
    group_id: str
    path: str
    formatted_id: str
    created_at: datetime

    class Config:
        from_attributes = True


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
    fellowship_id: str # e.g. "F001"
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
    fellowship_id: str
    location_id: str
    location_name: Optional[str] = None
    church_type: Optional[str] = None
    path: str
    formatted_id: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Tree View Schema ---
class TreeNode(BaseModel):
    """Recursive schema for hierarchy tree view."""
    id: str
    name: str
    type: str # 'nation', 'state', etc.
    path: str
    formatted_id: str
    children: List['TreeNode'] = []

    class Config:
        from_attributes = True

TreeNode.update_forward_refs()
