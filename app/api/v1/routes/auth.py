"""
Authentication API routes.

This module handles user authentication including:
- Login with phone/password
- Token refresh
- Current user profile retrieval

Authentication uses JWT tokens with role-based claims including:
- User ID, phone, role name
- Role score (1-9 hierarchy level)
- Home path (user's location)
- Scope path (calculated access scope based on role)

The scope path determines what data the user can access across the hierarchy.
"""
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core import security
from app.core.config import settings
from app.crud.crud_user import user as crud_user
from app.schemas.user import Token, UserResponse
from app.models.user import User

router = APIRouter()


@router.post("/login", response_model=Token)
async def login_access_token(
    db: AsyncSession = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends()
) -> Any:
    """
    OAuth2 compatible token login.
    
    Authenticates a user with phone number and password, returning JWT
    access and refresh tokens. The access token includes role-based claims
    for authorization and scope filtering.
    
    Args:
        db: Database session dependency
        form_data: OAuth2 form with username (phone) and password
        
    Returns:
        Token: Object containing access_token, refresh_token, and token_type
        
    Raises:
        HTTPException 400: Invalid credentials or inactive user
        HTTPException 401: User account pending approval
        
    Example:
        ```python
        POST /api/v1/auth/login
        Content-Type: application/x-www-form-urlencoded
        
        username=user@example.com&password=SecurePass123!
        
        Response:
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
        ```
        
    Token Claims:
        - sub: User ID (UUID)
        - email: User's email address
        - role: Role name (e.g., "GroupPastor")
        - score: Role score (1-9)
        - home_path: User's location path (e.g., "org.234.KW.ILN.ILE.001")
        - scope_path: Calculated access scope (e.g., "org.234.KW.ILN.ILE")
        
    Notes:
        - Username field expects email address (not phone number)
        - Password is verified using bcrypt
        - User must be active (is_active=True)
        - User must be approved (approval_status='approved')
        - Highest role score is used if user has multiple roles
        - Scope path is calculated based on role score
    """
    # Authenticate user
    user = await crud_user.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="Your account has been deactivated. Please contact your administrator."
        )
    
    # Check approval status
    if user.approval_status == "pending":
        raise HTTPException(
            status_code=401,
            detail="Your account is awaiting admin approval. Please contact your location pastor."
        )
    elif user.approval_status == "rejected":
        reason = user.rejection_reason or "No reason provided"
        raise HTTPException(
            status_code=401,
            detail=f"Your account was rejected. Reason: {reason}"
        )
        
    # Calculate role score and scope
    score = 0
    role_name = "Worker"
    if user.roles:
        # Use highest score role
        best_role = max(user.roles, key=lambda r: r.score.score if r.score else 0)
        if best_role.score:
            score = best_role.score.score
            role_name = best_role.role_name
            
    # Calculate scope path based on role score
    scope_path = security.create_admin_access_id(user_path=str(user.path), score=score)
    
    # Create tokens
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    access_token = security.create_access_token(
        data={
            "sub": str(user.user_id),
            "email": user.email,
            "role": role_name,
            "score": score,
            "home_path": str(user.path),
            "scope_path": str(scope_path)
        },
        expires_delta=access_token_expires,
    )
    
    refresh_token = security.create_refresh_token(user_id=str(user.user_id))
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Refresh access token using refresh token.
    
    Generates a new access token using a valid refresh token. This allows
    clients to maintain authentication without requiring the user to login
    again. The new access token includes updated role/scope information.
    
    Args:
        refresh_token: Valid JWT refresh token
        db: Database session dependency
        
    Returns:
        Token: New access token and same refresh token
        
    Raises:
        HTTPException 401: Invalid or expired refresh token
        HTTPException 404: User not found
        HTTPException 400: User inactive
        
    Example:
        ```python
        POST /api/v1/auth/refresh
        {
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
        
        Response:
        {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "token_type": "bearer"
        }
        ```
        
    Notes:
        - Refresh token must have type='refresh' in claims
        - User roles/scope are recalculated (picks up any changes)
        - Same refresh token is returned (no rotation for MVP)
        - Access token expiration is reset
        - User must still be active and approved
    """
    try:
        payload = security.verify_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        user_id = payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
        
    # Fetch user and recalculate claims
    user = await crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Recalculate role score and scope (in case they changed)
    score = 0
    role_name = "Worker"
    if user.roles:
        best_role = max(user.roles, key=lambda r: r.score.score if r.score else 0)
        if best_role.score:
            score = best_role.score.score
            role_name = best_role.role_name

    scope_path = security.create_admin_access_id(user_path=str(user.path), score=score)

    # Create new access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = security.create_access_token(
        data={
            "sub": str(user.user_id),
            "email": user.email,
            "role": role_name,
            "score": score,
            "home_path": str(user.path),
            "scope_path": str(scope_path)
        },
        expires_delta=access_token_expires,
    )
    
    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token
    }


@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get current authenticated user's profile.
    
    Returns the profile information for the currently authenticated user
    based on the JWT token. Useful for clients to fetch user details
    after login.
    
    Args:
        current_user: Currently authenticated user (from JWT token)
        
    Returns:
        UserResponse: Current user's profile with roles and scores
        
    Example:
        ```python
        GET /api/v1/auth/me
        Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        
        Response:
        {
            "user_id": "550e8400-e29b-41d4-a716-446655440000",
            "worker_id": "660e8400-e29b-41d4-a716-446655440001",
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "+2349012345678",
            "location_id": "001",
            "is_active": true,
            "approval_status": "approved",
            "roles": [
                {
                    "id": 1,
                    "role_name": "GroupPastor",
                    "score_value": 4
                }
            ],
            "path": "org.234.KW.ILN.ILE.001",
            "created_at": "2026-01-20T10:30:00Z"
        }
        ```
        
    Notes:
        - Requires valid access token in Authorization header
        - Returns user with eagerly loaded roles
        - Includes approval status and location information
        - Path shows user's position in hierarchy
    """
    return current_user
