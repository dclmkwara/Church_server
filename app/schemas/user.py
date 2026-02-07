"""
Pydantic schemas for Worker and User models.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, validator


# --- Role & Permission Schemas ---

class PermissionBase(BaseModel):
    permission: str
    name: str
    description: Optional[str] = None


class PermissionCreate(PermissionBase):
    pass


class PermissionResponse(PermissionBase):
    id: int
    
    class Config:
        from_attributes = True


class RoleBase(BaseModel):
    role_name: str
    description: Optional[str] = None
    score_id: int


class RoleCreate(RoleBase):
    pass


class RoleResponse(RoleBase):
    id: int
    score_value: Optional[int] = None  # Helper to show actual score
    
    class Config:
        from_attributes = True


# --- Worker Schemas ---

class WorkerBase(BaseModel):
    location_id: str
    location_name: str
    church_type: str
    state: str
    region: str
    group: str
    name: str
    gender: str
    phone: str
    email: EmailStr
    address: Optional[str] = None
    occupation: Optional[str] = None
    marital_status: Optional[str] = None
    unit: str
    status: Optional[str] = "Active"


class WorkerCreate(WorkerBase):
    pass


class WorkerUpdate(BaseModel):
    name: Optional[str] = None
    location_id: Optional[str] = None
    location_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    occupation: Optional[str] = None
    marital_status: Optional[str] = None
    unit: Optional[str] = None
    status: Optional[str] = None


class WorkerResponse(WorkerBase):
    id: int
    worker_id: UUID
    path: Optional[str] = None  # Use string representation of ltree
    created_at: datetime
    
    class Config:
        from_attributes = True
    
    @validator('path', pre=True)
    def path_to_str(cls, v):
        """Convert ltree object to string if needed."""
        return str(v) if v is not None else None


# --- User Schemas ---

class UserBase(BaseModel):
    email: EmailStr
    is_active: Optional[bool] = True


class UserCreate(UserBase):
    worker_id: UUID
    password: str
    roles: Optional[List[int]] = []  # List of Role IDs


class UserUpdate(UserBase):
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    roles: Optional[List[int]] = None


class UserResponse(UserBase):
    user_id: UUID
    worker_id: UUID
    location_id: str
    name: str
    phone: str
    created_at: datetime
    roles: List[RoleResponse] = []
    path: Optional[str] = None
    
    # Approval workflow fields
    approval_status: str  # pending, approved, rejected
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    class Config:
        from_attributes = True
        
    @validator('path', pre=True)
    def path_to_str(cls, v):
        """Convert ltree object to string if needed."""
        return str(v) if v is not None else None


# --- Approval Workflow Schemas ---

class UserApprovalRequest(BaseModel):
    """Schema for approving/rejecting user accounts."""
    reason: Optional[str] = None  # Required for rejection


class BulkApprovalRequest(BaseModel):
    """Schema for bulk user approval operations."""
    user_ids: List[str]


# --- Auth Schemas ---

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str


class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None
    score: Optional[int] = None
    scope_path: Optional[str] = None
