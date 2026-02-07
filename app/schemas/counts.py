"""
Pydantic schemas for Count models.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class CountBase(BaseModel):
    event_id: UUID
    location_id: str
    
    adult_male: int = Field(0, ge=0)
    adult_female: int = Field(0, ge=0)
    youth_male: int = Field(0, ge=0)
    youth_female: int = Field(0, ge=0)
    boys: int = Field(0, ge=0)
    girls: int = Field(0, ge=0)
    
    note: Optional[str] = None
    client_id: Optional[UUID] = None # For offline sync deduplication

class CountCreate(CountBase):
    pass

class CountUpdate(BaseModel):
    adult_male: Optional[int] = Field(None, ge=0)
    adult_female: Optional[int] = Field(None, ge=0)
    youth_male: Optional[int] = Field(None, ge=0)
    youth_female: Optional[int] = Field(None, ge=0)
    boys: Optional[int] = Field(None, ge=0)
    girls: Optional[int] = Field(None, ge=0)
    note: Optional[str] = None
    status: Optional[str] = None # For admin approval

class CountResponse(CountBase):
    id: UUID
    path: str
    total: int
    status: str
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
