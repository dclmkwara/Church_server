"""
Pydantic schemas for Program models.
"""
from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --- Program Domain Schemas ---

class ProgramDomainBase(BaseModel):
    name: str = Field(..., description="Program Domain Name (e.g. Regular Service)")
    slug: str = Field(..., description="Unique slug (e.g. regular_service)")
    description: Optional[str] = None

class ProgramDomainCreate(ProgramDomainBase):
    pass

class ProgramDomainUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None

class ProgramDomainResponse(ProgramDomainBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# --- Program Type Schemas ---

class ProgramTypeBase(BaseModel):
    name: str = Field(..., description="Program Type Name (e.g. Sunday Worship)")
    slug: str = Field(..., description="Unique slug (e.g. sunday_worship)")
    domain_id: int
    description: Optional[str] = None

class ProgramTypeCreate(ProgramTypeBase):
    pass

class ProgramTypeUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    domain_id: Optional[int] = None
    description: Optional[str] = None

class ProgramTypeResponse(ProgramTypeBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# --- Program Event Schemas ---

class ProgramEventBase(BaseModel):
    program_type_id: int
    date: date
    path: str = Field(..., description="Scope of the event (ltree path)")
    title: Optional[str] = None

class ProgramEventCreate(ProgramEventBase):
    pass

class ProgramEventUpdate(BaseModel):
    program_type_id: Optional[int] = None
    date: Optional[date] = None
    path: Optional[str] = None
    title: Optional[str] = None

class ProgramEventResponse(ProgramEventBase):
    id: UUID
    program_type: Optional[ProgramTypeResponse] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
