"""Dependency injection helpers for FastAPI routes.

Provides common dependencies such as the current user or role enforcement.
"""
import uuid

from fastapi import Depends, HTTPException, status
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .db.session import get_db
from .config import settings
from .models.user import User, Role

from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    """Retrieve the currently authenticated user from a JWT token.

    Args:
        db (AsyncSession): Database session dependency.
        token (str | None): JWT token string from request headers.

    Returns:
        User: The authenticated user object.

    Raises:
        HTTPException: If token is invalid or user does not exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user


def require_role(required_role: Role):
    """Dependency generator to enforce role-based access control (RBAC).

    Args:
        required_role (Role): Required user role for the route.

    Returns:
        Callable: Dependency that validates the current user role.

    Raises:
        HTTPException: If the user does not have the required role.
    """

    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return user

    return role_checker
