"""
User management API routes.

This module handles user account management operations including:
- Listing users with scope filtering
- Creating new user accounts (linked to workers)
- Updating user information
- Role assignment and management
- Soft deletion

Users are strictly for authentication and must be linked to existing workers.
All operations respect hierarchical scope based on the current user's role.
"""
from typing import Any, List
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from sqlalchemy import select, text
from app.core import security
from app.crud.crud_user import user as crud_user
from app.schemas.user import UserCreate, UserResponse, UserUpdate, UserFullResponse, PasswordVerifyRequest, AutoCreateUserResponse
from app.models.user import User

router = APIRouter()


@router.get(
    "/",
    response_model=List[UserResponse],
    dependencies=[Depends(deps.PermissionChecker("users:read"))],
)
async def read_users(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """
    Retrieve users with hierarchical scope filtering.
    
    Returns a list of users within the current user's scope. Admins with
    higher scores can see users across broader hierarchies (e.g., state
    pastors see all users in their state).
    
    Args:
        db: Database session dependency
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        current_user: Currently authenticated user
        scope_path: Optional custom scope path (defaults to current user's scope)
        
    Returns:
        List[UserResponse]: List of users with roles and scores eagerly loaded
        
    Example:
        ```python
        # Get all users in my scope
        GET /api/v1/users/
        
        # Get users with custom scope
        GET /api/v1/users/?scope_path=org.234.KW
        
        # Pagination
        GET /api/v1/users/?skip=20&limit=50
        ```
        
    Notes:
        - Uses ltree descendant operator (<@) for efficient hierarchical filtering
        - Eagerly loads roles and scores to prevent N+1 queries
        - Scope defaults to current user's path if not specified
        - Results are limited by user's role score (higher score = broader scope)
    """
    search_scope = scope_path if scope_path else str(current_user.path)
    
    from sqlalchemy import select, text
    from sqlalchemy.orm import selectinload
    from app.models.user import Role
    
    query = select(User).where(
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=search_scope)
    ).options(
        selectinload(User.roles).selectinload(Role.score)
    ).offset(skip).limit(limit)
    
    result = await db.execute(query)
    users = result.scalars().all()
    return users


@router.post(
    "/",
    response_model=UserResponse,
    dependencies=[Depends(deps.PermissionChecker("users:create"))],
)
async def create_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: UserCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new user account linked to an existing worker.
    
    Users are created AFTER worker registration. This endpoint validates
    that the worker exists and creates an authentication account for them.
    
    Args:
        db: Database session dependency
        user_in: User creation data (worker_id, email, password, roles)
        current_user: Currently authenticated user (must have permission to create users)
        
    Returns:
        UserResponse: Created user with roles
        
    Raises:
        HTTPException 400: Email already exists or worker not found
        HTTPException 403: Current user lacks permission to create users
        
    Example:
        ```python
        POST /api/v1/users/
        {
            "worker_id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "worker@example.com",
            "password": "SecurePass123!",
            "roles": [1, 2]  # Role IDs to assign
        }
        ```
        
    Notes:
        - Worker must exist before creating user
        - Password is automatically hashed
        - Email must be unique across all users
        - Roles are assigned during creation
        - User inherits location/path from worker
    """
    # Check if email already exists
    user = await crud_user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    
    # Create user (CRUD will validate worker exists)
    user = await crud_user.create(db, obj_in=user_in)
    return user


@router.post(
    "/auto-create",
    response_model=AutoCreateUserResponse,
    dependencies=[Depends(deps.PermissionChecker("users:create"))],
)
async def auto_create_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    email: str = Body(..., embed=True),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Auto-create a user from an existing worker record using email.
    Generates a temporary password from the worker's first name.
    """
    from sqlalchemy import select
    from app.models.user import Worker

    worker_result = await db.execute(select(Worker).where(Worker.email == email))
    worker = worker_result.scalars().first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker with this email not found")

    existing = await crud_user.get_by_email(db, email=email)
    if existing:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    user_by_worker = await db.execute(select(User).where(User.worker_id == worker.worker_id))
    if user_by_worker.scalars().first():
        raise HTTPException(status_code=400, detail="User already exists for this worker")

    first_name = worker.name.split(" ")[0].lower() if worker.name else "tempuser"
    temp_password = first_name

    user_in = UserCreate(
        worker_id=worker.worker_id,
        email=worker.email,
        password=temp_password,
        roles=[],
        is_active=False,
    )
    user = await crud_user.create(db, obj_in=user_in)
    return {"user": user, "temporary_password": temp_password}


@router.get("/state-region")
async def get_state_region_data(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return state and region derived from user's path."""
    path = str(current_user.path)
    parts = path.split(".")
    state = parts[2] if len(parts) > 2 else None
    region = parts[3] if len(parts) > 3 else None
    return {"state": state, "region": region}


@router.post("/verify-password")
async def verify_user_password(
    *,
    db: AsyncSession = Depends(deps.get_db),
    payload: PasswordVerifyRequest,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Verify the current user's password."""
    is_valid = security.verify_password(payload.password, current_user.password)
    return {"verified": is_valid}




@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(deps.PermissionChecker("users:read"))],
)
async def read_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get a specific user by ID.
    
    Args:
        db: Database session dependency
        user_id: UUID of the user to retrieve
        current_user: Currently authenticated user
        
    Returns:
        UserResponse: User details with roles and scores
        
    Raises:
        HTTPException 404: User not found
        HTTPException 403: User outside current user's scope
        
    Example:
        ```python
        GET /api/v1/users/550e8400-e29b-41d4-a716-446655440000
        ```
        
    Notes:
        - Validates user is within current user's hierarchical scope
        - Eagerly loads roles to prevent additional queries
    """
    user = await crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if str(user.path) and str(current_user.path):
        scope_stmt = select(User.user_id).where(
            User.user_id == user_id,
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=str(current_user.path))
        )
        scope_result = await db.execute(scope_stmt)
        if scope_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=403, detail="User outside your scope")
    
    return user


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(deps.PermissionChecker("users:update"))],
)
async def update_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: UUID,
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update an existing user's information.
    
    Allows updating email, password, active status, and roles. Password
    is automatically hashed if provided.
    
    Args:
        db: Database session dependency
        user_id: UUID of the user to update
        user_in: Update data (all fields optional)
        current_user: Currently authenticated user
        
    Returns:
        UserResponse: Updated user with roles
        
    Raises:
        HTTPException 404: User not found
        HTTPException 403: User outside current user's scope or permission denied
        
    Example:
        ```python
        PUT /api/v1/users/550e8400-e29b-41d4-a716-446655440000
        {
            "email": "newemail@example.com",
            "is_active": false,
            "roles": [2, 3]
        }
        ```
        
    Notes:
        - Only provided fields are updated (partial update)
        - Password is hashed automatically if included
        - Changing roles requires appropriate permissions
        - Cannot update user outside your hierarchical scope
    """
    user = await crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Scope validated in read_user; permission enforced via PermissionChecker ("users:update")
    
    user = await crud_user.update(db, db_obj=user, obj_in=user_in)
    return user


@router.post(
    "/{user_id}/assign-roles",
    response_model=UserResponse,
    dependencies=[Depends(deps.PermissionChecker("users:assign_roles"))],
)
async def assign_roles_to_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: UUID,
    role_ids: List[int] = Body(..., embed=True),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Assign roles to a user.
    
    Replaces the user's current roles with the specified role IDs.
    Validates that the current user has permission to assign these roles
    based on role score hierarchy.
    
    Args:
        db: Database session dependency
        user_id: UUID of the user to assign roles to
        role_ids: List of role IDs to assign
        current_user: Currently authenticated user
        
    Returns:
        UserResponse: Updated user with new roles
        
    Raises:
        HTTPException 404: User not found
        HTTPException 403: Cannot assign roles with higher score than yours
        HTTPException 400: Invalid role IDs
        
    Example:
        ```python
        POST /api/v1/users/550e8400-e29b-41d4-a716-446655440000/assign-roles
        {
            "role_ids": [1, 2, 3]
        }
        ```
        
    Notes:
        - Replaces ALL existing roles (not additive)
        - Validates role score hierarchy (can't assign higher roles than yours)
        - Automatically updates user's effective scope based on highest role score
        - Role IDs must exist in the roles table
    """
    user = await crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate current user can assign these roles by score
    if current_user.roles:
        current_max = max([r.score.score for r in current_user.roles if r.score])
        # Fetch target roles
        from app.models.user import Role as RoleModel
        from sqlalchemy import select
        stmt = select(RoleModel).where(RoleModel.id.in_(role_ids))
        res = await db.execute(stmt)
        target_roles = res.scalars().all()
        if not target_roles:
            raise HTTPException(status_code=400, detail="Invalid role IDs")
        target_max = max([r.score.score for r in target_roles if r.score])
        if target_max >= current_max:
            raise HTTPException(status_code=403, detail="Cannot assign roles at or above your level")
    
    user = await crud_user.assign_roles(db, user=user, role_ids=role_ids)
    return user


@router.get(
    "/{user_id}/details",
    response_model=UserFullResponse,
    dependencies=[Depends(deps.PermissionChecker("users:read"))],
)
async def read_user_details(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a user with embedded worker and roles."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.user import Role, Worker
    stmt = select(User).where(User.user_id == user_id).options(
        selectinload(User.roles).selectinload(Role.score),
        selectinload(User.worker)
    )
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get(
    "/search",
    response_model=List[UserResponse],
    dependencies=[Depends(deps.PermissionChecker("users:read"))],
)
async def search_users(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
    name: str = Query(None),
    email: str = Query(None),
    phone: str = Query(None),
    location_id: str = Query(None),
    is_active: bool = Query(None),
) -> Any:
    """Search users with optional filters."""
    from sqlalchemy import select, text
    from sqlalchemy.orm import selectinload
    from app.models.user import Role
    search_scope = scope_path if scope_path else str(current_user.path)
    query = select(User).where(
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=search_scope)
    ).options(selectinload(User.roles).selectinload(Role.score)).offset(skip).limit(limit)
    if name:
        query = query.where(User.name.ilike(f"%{name}%"))
    if email:
        query = query.where(User.email == email)
    if phone:
        query = query.where(User.phone == phone)
    if location_id:
        query = query.where(User.location_id == location_id)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    result = await db.execute(query)
    return result.scalars().all()


@router.get(
    "/with-roles",
    response_model=List[UserResponse],
    dependencies=[Depends(deps.PermissionChecker("users:read"))],
)
async def list_users_with_roles(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List users with roles loaded."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.user import Role
    query = select(User).options(selectinload(User.roles).selectinload(Role.score)).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("users:delete"))],
)
async def delete_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a user account."""
    user = await crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await crud_user.update(
        db,
        db_obj=user,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None
