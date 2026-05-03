"""
Pydantic schemas for LocationProfile model.
"""
from datetime import date
from typing import Optional, List, Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class SpecialProject(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "ongoing"  # ongoing | completed


class LocationProfileBase(BaseModel):
    history: Optional[str] = None
    founded_date: Optional[date] = None
    founder_name: Optional[str] = None

    full_address: Optional[str] = None
    landmark: Optional[str] = None
    google_maps_url: Optional[str] = None

    special_projects: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    cover_image_url: Optional[str] = None


class LocationProfileCreate(LocationProfileBase):
    pass


class LocationProfileUpdate(LocationProfileBase):
    pass


class LocationProfileResponse(LocationProfileBase):
    id: int
    location_id: str

    model_config = ConfigDict(from_attributes=True)
