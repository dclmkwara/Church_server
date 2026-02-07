from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_rbac import role, permission, role_score
from app.schemas.rbac import (
    RoleCreate, RoleUpdate, RoleResponse,
    PermissionCreate, PermissionUpdate, PermissionResponse,
    RoleScoreResponse
)
from app.models.user import User

router = APIRouter()

# ==========================================
# Permissions Endpoints
# ==========================================
@router.get("/permissions", response_model=List[PermissionResponse])
async def read_permissions(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List all permissions."""
    # TODO: Check if user is superadmin
    return await permission.get_multi(db, skip=skip, limit=limit)

@router.post("/permissions", response_model=PermissionResponse)
async def create_permission(
    *,
    db: AsyncSession = Depends(deps.get_db),
    permission_in: PermissionCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create new permission."""
    # TODO: Check if user is superadmin
    return await permission.create(db, obj_in=permission_in)

# ==========================================
# Roles Endpoints
# ==========================================
@router.get("/roles", response_model=List[RoleResponse])
async def read_roles(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List all roles."""
    return await role.get_multi(db, skip=skip, limit=limit)

@router.post("/roles", response_model=RoleResponse)
async def create_role(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_in: RoleCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create new role with permissions."""
    return await role.create_with_permissions(db, obj_in=role_in)

@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_id: int,
    role_in: RoleUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update role and permissions."""
    db_role = await role.get(db, id=role_id)
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    return await role.update_with_permissions(db, db_obj=db_role, obj_in=role_in)

# ==========================================
# Scores Endpoints
# ==========================================
@router.get("/scores", response_model=List[RoleScoreResponse])
async def read_scores(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List all role scores."""
    return await role_score.get_multi(db, skip=skip, limit=limit)
