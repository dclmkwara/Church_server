"""
Pydantic schemas for Worker and User models.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# --- Role & Permission Schemas ---

class PermissionBase(BaseModel):
    permission: str
    name: str
    description: Optional[str] = None


class PermissionCreate(PermissionBase):
    pass


class PermissionResponse(PermissionBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class RoleBase(BaseModel):
    role_name: str
    description: Optional[str] = None
    score_id: int


class RoleCreate(RoleBase):
    pass


class RoleResponse(RoleBase):
    id: int
    score_value: Optional[int] = None  # Helper to show actual score

    model_config = ConfigDict(from_attributes=True)


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

    @field_validator("location_id", mode="before")
    @classmethod
    def location_id_to_str(cls, v):
        """Location primary keys may be UUID objects from asyncpg; API payloads expose strings."""
        return str(v) if v is not None else v


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
    email: str
    id: int
    worker_id: UUID
    path: Optional[str] = None  # Use string representation of ltree
    created_at: datetime
    approval_status: Optional[str] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

    @field_validator("path", mode="before")
    @classmethod
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
    roles: Optional[List[int]] = Field(default_factory=list)  # List of Role IDs


class UserSelfRegistrationRequest(BaseModel):
    worker_id: UUID
    password: str = Field(..., min_length=8)


class UserUpdate(UserBase):
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    roles: Optional[List[int]] = None


class UserResponse(UserBase):
    email: str
    user_id: UUID
    worker_id: UUID
    location_id: str
    name: str
    phone: str
    created_at: datetime
    roles: List[RoleResponse] = Field(default_factory=list)
    path: Optional[str] = None
    
    # Approval workflow fields
    approval_status: str  # pending, approved, rejected
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("path", mode="before")
    @classmethod
    def path_to_str(cls, v):
        """Convert ltree object to string if needed."""
        return str(v) if v is not None else None

    @field_validator("location_id", mode="before")
    @classmethod
    def location_id_to_str(cls, v):
        """Convert UUID location primary keys to API-safe strings."""
        return str(v) if v is not None else v


class UserFullResponse(UserResponse):
    """User response with embedded worker details."""
    worker: Optional[WorkerResponse] = None


# --- Approval Workflow Schemas ---

class UserApprovalRequest(BaseModel):
    """Schema for approving/rejecting user accounts."""
    reason: Optional[str] = None  # Required for rejection


class BulkApprovalRequest(BaseModel):
    """Schema for bulk user approval operations."""
    user_ids: List[str]


class PasswordVerifyRequest(BaseModel):
    """Schema for verifying a user's password."""
    password: str


class AutoCreateUserResponse(BaseModel):
    """Response for auto-created user accounts."""
    user: UserResponse
    temporary_password: str




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
