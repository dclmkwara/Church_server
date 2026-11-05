from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api import deps
from app.crud.crud_rbac import role, permission, role_score
from app.schemas.rbac import (
    RoleCreate, RoleUpdate, RoleResponse,
    PermissionCreate, PermissionUpdate, PermissionResponse,
    RoleScoreCreate, RoleScoreUpdate, RoleScoreResponse
)
from app.models.user import Role as RoleModel, RoleScore, User

router = APIRouter()

# ==========================================
# Permissions Endpoints
# ==========================================
@router.get(
    "/permissions",
    response_model=List[PermissionResponse],
    dependencies=[Depends(deps.PermissionChecker("rbac:read"))],
)
async def read_permissions(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List all permissions."""
    return await permission.get_multi(db, skip=skip, limit=limit)

@router.get(
    "/permissions/{permission_id}",
    response_model=PermissionResponse,
    dependencies=[Depends(deps.PermissionChecker("rbac:read"))],
)
async def read_permission(
    permission_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a single permission."""
    perm = await permission.get(db, id=permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    return perm

@router.post(
    "/permissions",
    response_model=PermissionResponse,
    dependencies=[Depends(deps.PermissionChecker("rbac:manage"))],
)
async def create_permission(
    *,
    db: AsyncSession = Depends(deps.get_db),
    permission_in: PermissionCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create new permission."""
    raise HTTPException(status_code=403, detail="Permission catalog is migration-managed")

@router.put(
    "/permissions/{permission_id}",
    response_model=PermissionResponse,
    dependencies=[Depends(deps.PermissionChecker("rbac:manage"))],
)
async def update_permission(
    *,
    db: AsyncSession = Depends(deps.get_db),
    permission_id: int,
    permission_in: PermissionUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update permission."""
    perm = await permission.get(db, id=permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    raise HTTPException(status_code=403, detail="Permission catalog is migration-managed")

@router.delete(
    "/permissions/{permission_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("rbac:manage"))],
)
async def delete_permission(
    *,
    db: AsyncSession = Depends(deps.get_db),
    permission_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete permission."""
    perm = await permission.get(db, id=permission_id)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    raise HTTPException(status_code=403, detail="Permission catalog is migration-managed")

# ==========================================
# Roles Endpoints
# ==========================================
@router.get(
    "/roles",
    response_model=List[RoleResponse],
    dependencies=[Depends(deps.PermissionChecker("rbac:read"))],
)
async def read_roles(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List all roles."""
    stmt = select(RoleModel).options(selectinload(RoleModel.score), selectinload(RoleModel.permissions))
    result = await db.execute(stmt.order_by(RoleModel.id).offset(skip).limit(limit))
    return result.scalars().all()


@router.get("/roles/available", response_model=List[RoleResponse])
async def read_available_roles(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    List roles that the current user is allowed to assign.
    Uses role score hierarchy (can only assign roles lower than your own).
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.user import Role as RoleModel, RoleScore

    # Determine max score of current user
    if not current_user.roles:
        return []
    max_score = max([r.score.score for r in current_user.roles if r.score]) if current_user.roles else None
    if max_score is None:
        return []
    if max_score < 2:
        return []

    # Pastoral users may assign worker-level roles in their scope as part of
    # registering an approved worker; pastoral roles remain strictly lower.
    stmt = (
        select(RoleModel)
        .options(selectinload(RoleModel.score))
        .join(RoleScore, RoleScore.id == RoleModel.score_id)
        .where(
            (RoleScore.score == 1)
            | ((RoleScore.score < max_score) & (RoleScore.score >= 2))
        )
        .order_by(RoleScore.score.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get(
    "/roles/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(deps.PermissionChecker("rbac:read"))],
)
async def read_role(
    role_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a single role."""
    stmt = select(RoleModel).where(RoleModel.id == role_id).options(selectinload(RoleModel.permissions))
    result = await db.execute(stmt)
    db_role = result.scalars().first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    return db_role

@router.post(
    "/roles",
    response_model=RoleResponse,
    dependencies=[Depends(deps.PermissionChecker("rbac:manage"))],
)
async def create_role(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_in: RoleCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create new role with permissions."""
    score = await db.get(RoleScore, role_in.score_id)
    if score is None or not 2 <= score.score <= 5:
        raise HTTPException(status_code=403, detail="This application only manages roles at levels 2 through 5")
    return await role.create_with_permissions(db, obj_in=role_in)

@router.put(
    "/roles/{role_id}",
    response_model=RoleResponse,
    dependencies=[Depends(deps.PermissionChecker("rbac:manage"))],
)
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
    if db_role.role_name in {"Zonal Coordinator", "National Admin", "National Overseer", "Continental Admin", "Continental Overseer", "Global Admin"}:
        raise HTTPException(status_code=403, detail="Reserved enterprise roles cannot be managed in this application")
    score = await db.get(RoleScore, role_in.score_id) if role_in.score_id is not None else None
    if role_in.score_id is not None and (score is None or not 2 <= score.score <= 5):
        raise HTTPException(status_code=403, detail="This application only manages roles at levels 2 through 5")
    if role_in.permission_ids is not None:
        raise HTTPException(status_code=403, detail="Role permission changes require an approved governance workflow")
    if set(role_in.model_dump(exclude_unset=True)) - {"role_name"}:
        raise HTTPException(status_code=403, detail="Role definitions are fixed; permission changes require an approved governance workflow")
    return await role.update_with_permissions(db, db_obj=db_role, obj_in=role_in)

@router.delete(
    "/roles/{role_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("rbac:manage"))],
)
async def delete_role(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete role."""
    db_role = await role.get(db, id=role_id)
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    if db_role.score_value < 2 or db_role.score_value > 5:
        raise HTTPException(status_code=403, detail="This application only manages role definitions at levels 2 through 5")
    if db_role.role_name in {"House Fellowship Leader", "Location Worker", "Location Usher", "Group Usher", "Region Usher", "State Usher", "Zonal Coordinator", "National Admin", "National Overseer", "Continental Admin", "Continental Overseer", "Global Admin"}:
        raise HTTPException(status_code=403, detail="System, worker, and reserved enterprise roles cannot be deleted here")
    await role.remove(db, id=role_id)
    return None

@router.post(
    "/roles/{role_id}/permissions",
    response_model=RoleResponse,
    dependencies=[Depends(deps.PermissionChecker("rbac:manage"))],
)
async def set_role_permissions(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_id: int,
    permission_ids: List[int] = Body(..., embed=True),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Replace role permissions with provided list."""
    db_role = await role.get(db, id=role_id)
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    if db_role.role_name in {"Zonal Coordinator", "National Admin", "National Overseer", "Continental Admin", "Continental Overseer", "Global Admin"}:
        raise HTTPException(status_code=403, detail="This role is reserved or event-scoped and cannot be edited here")
    if db_role.score_value < 2 or db_role.score_value > 5:
        raise HTTPException(status_code=403, detail="This application only manages role definitions at levels 2 through 5")
    return await role.update_with_permissions(db, db_obj=db_role, obj_in={"permission_ids": permission_ids})

@router.delete(
    "/roles/{role_id}/permissions/{permission_id}",
    response_model=RoleResponse,
    dependencies=[Depends(deps.PermissionChecker("rbac:manage"))],
)
async def remove_role_permission(
    *,
    db: AsyncSession = Depends(deps.get_db),
    role_id: int,
    permission_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Remove a single permission from a role."""
    stmt = select(RoleModel).where(RoleModel.id == role_id).options(selectinload(RoleModel.permissions))
    result = await db.execute(stmt)
    db_role = result.scalars().first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Role not found")
    if db_role.role_name in {"House Fellowship Leader", "Location Worker", "Location Usher", "Group Usher", "Region Usher", "State Usher", "Zonal Coordinator", "National Admin", "National Overseer", "Continental Admin", "Continental Overseer", "Global Admin"}:
        raise HTTPException(status_code=403, detail="System, worker, and reserved enterprise roles cannot be edited here")
    db_role.permissions = [p for p in db_role.permissions if p.id != permission_id]
    await db.commit()
    role_with_permissions = await role.get_with_permissions(db, role_id)
    return role_with_permissions or db_role

# ==========================================
# Scores Endpoints
# ==========================================
@router.get(
    "/scores",
    response_model=List[RoleScoreResponse],
    dependencies=[Depends(deps.PermissionChecker("rbac:read"))],
)
async def read_scores(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List all role scores."""
    return await role_score.get_multi(db, skip=skip, limit=limit)

@router.get(
    "/scores/{score_id}",
    response_model=RoleScoreResponse,
    dependencies=[Depends(deps.PermissionChecker("rbac:read"))],
)
async def read_score(
    score_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a single role score."""
    db_score = await role_score.get(db, id=score_id)
    if not db_score:
        raise HTTPException(status_code=404, detail="Role score not found")
    return db_score

@router.post(
    "/scores",
    response_model=RoleScoreResponse,
    dependencies=[Depends(deps.PermissionChecker("rbac:manage"))],
)
async def create_score(
    *,
    db: AsyncSession = Depends(deps.get_db),
    score_in: RoleScoreCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create role score."""
    raise HTTPException(status_code=403, detail="Role scores are fixed by the canonical church hierarchy")

@router.put(
    "/scores/{score_id}",
    response_model=RoleScoreResponse,
    dependencies=[Depends(deps.PermissionChecker("rbac:manage"))],
)
async def update_score(
    *,
    db: AsyncSession = Depends(deps.get_db),
    score_id: int,
    score_in: RoleScoreUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update role score."""
    db_score = await role_score.get(db, id=score_id)
    if not db_score:
        raise HTTPException(status_code=404, detail="Role score not found")
    raise HTTPException(status_code=403, detail="Role scores are fixed by the canonical church hierarchy")

@router.delete(
    "/scores/{score_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("rbac:manage"))],
)
async def delete_score(
    *,
    db: AsyncSession = Depends(deps.get_db),
    score_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete role score."""
    db_score = await role_score.get(db, id=score_id)
    if not db_score:
        raise HTTPException(status_code=404, detail="Role score not found")
    raise HTTPException(status_code=403, detail="Role scores are fixed by the canonical church hierarchy")
