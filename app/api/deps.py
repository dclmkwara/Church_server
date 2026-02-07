"""
Dependencies for API routes, primarily for authentication and database access.
"""
from typing import AsyncGenerator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.crud.crud_user import user as crud_user
from app.db.session import get_db, inject_scope
from app.models.user import User
from app.schemas.user import TokenPayload
from app.models.user import User
from app.schemas.user import TokenPayload
# PermissionChecker moved here to avoid circular import

# OAuth2 scheme
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login"
)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2)
) -> User:
    """
    Get current user from JWT token.
    Validates token, extracts user ID, and fetches user from DB.
    Also injects RLS scope into the session.
    """
    try:
        payload = security.verify_token(token)
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
        
    user = await crud_user.get(db, id=token_data.sub)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Inject RLS scope if available in token
    if token_data.scope_path:
        await inject_scope(db, token_data.scope_path)
        
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active user.
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


class PermissionChecker:
    """
    Dependency to check if the current user has a specific permission.
    Moved from app.core.permissions to avoid circular import.
    """
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        # Superadmin override (Score 9)
        if current_user.roles:
            for role in current_user.roles:
                if role.score_value >= 9:
                    return current_user
                
        # Check permissions
        has_permission = False
        if current_user.roles:
            for role in current_user.roles:
                for permission in role.permissions:
                    if permission.permission == self.required_permission:
                        has_permission = True
                        break
                if has_permission:
                    break
                
        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail=f"Operation not permitted. Required: {self.required_permission}"
            )
            
        return current_user
