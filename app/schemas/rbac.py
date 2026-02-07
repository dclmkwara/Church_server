from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID

# Permission Schemas
class PermissionBase(BaseModel):
    permission: str
    name: str
    description: Optional[str] = None

class PermissionCreate(PermissionBase):
    pass

class PermissionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class PermissionResponse(PermissionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)



# Role Score Schemas
class RoleScoreBase(BaseModel):
    score: int
    score_name: str
    description: Optional[str] = None

class RoleScoreCreate(RoleScoreBase):
    pass

class RoleScoreUpdate(BaseModel):
    score_name: Optional[str] = None
    description: Optional[str] = None

class RoleScoreResponse(RoleScoreBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


# Role Schemas
class RoleBase(BaseModel):
    role_name: str
    description: Optional[str] = None
    score_id: int

class RoleCreate(RoleBase):
    permission_ids: Optional[List[int]] = []

class RoleUpdate(BaseModel):
    role_name: Optional[str] = None
    description: Optional[str] = None
    score_id: Optional[int] = None
    permission_ids: Optional[List[int]] = None

class RoleResponse(RoleBase):
    id: int
    score_value: int
    permissions: List[PermissionResponse] = []
    
    model_config = ConfigDict(from_attributes=True)
