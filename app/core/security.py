"""
Security utilities for authentication and authorization.
"""
from datetime import datetime, timedelta
from typing import Any, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
    
    Returns:
        str: Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password
        hashed_password: Hashed password
    
    Returns:
        bool: True if password matches
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token with custom claims.
    
    Args:
        data: Token payload data (should include user info, scope_path, score, etc.)
        expires_delta: Token expiration time delta
    
    Returns:
        str: Encoded JWT token
    
    Example:
        >>> token_data = {
        ...     "sub": str(user_id),
        ...     "phone": "+2349029952120",
        ...     "role": "GroupPastor",
        ...     "score": 4,
        ...     "home_path": "org.234.kw.iln.ile.001",
        ...     "scope_path": "org.234.kw.iln.ile"
        ... }
        >>> token = create_access_token(token_data)
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )
    
    return encoded_jwt


def create_refresh_token(user_id: str) -> str:
    """
    Create JWT refresh token.
    
    Args:
        user_id: User ID
    
    Returns:
        str: Encoded JWT refresh token
    """
    data = {"sub": user_id, "type": "refresh"}
    expires_delta = timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    
    return create_access_token(data, expires_delta)


def verify_token(token: str) -> dict:
    """
    Verify and decode JWT token.
    
    Args:
        token: JWT token string
    
    Returns:
        dict: Decoded token payload
    
    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise JWTError(f"Invalid token: {str(e)}")


def create_admin_access_id(user_path: str, score: int) -> str:
    """
    Generate scope path based on user's home path and role score.
    
    This determines what data the user can access based on their role hierarchy.
    
    Args:
        user_path: User's home location path (e.g., 'org.234.kw.iln.ile.001')
        score: Role score (1-9)
    
    Returns:
        str: Scope path for data filtering
    
    Score mapping:
        1-2: Worker/Usher → org.234.kw.iln.ile.001 (location only)
        3: Location Pastor → org.234.kw.iln.ile.001 (location only)
        4: Group Pastor → org.234.kw.iln.ile (all locations in group)
        5: Regional Pastor → org.234.kw.iln (all groups in region)
        6: State Pastor → org.234.kw (all regions in state)
        7: National Admin → org.234 (all states in nation)
        8: Continental Leader → org (all nations in continent)
        9: Global Admin → org (entire organization)
    
    Example:
        >>> create_admin_access_id('org.234.kw.iln.ile.001', 4)
        'org.234.kw.iln.ile'
        >>> create_admin_access_id('org.234.kw.iln.ile.001', 6)
        'org.234.kw'
    """
    segments = user_path.split('.')
    
    if score <= 3:  # Location level (Worker, Usher, Location Pastor)
        return user_path  # Full path (location only)
    elif score == 4:  # Group level
        return '.'.join(segments[:5]) if len(segments) >= 5 else user_path
    elif score == 5:  # Regional level
        return '.'.join(segments[:4]) if len(segments) >= 4 else user_path
    elif score == 6:  # State level
        return '.'.join(segments[:3]) if len(segments) >= 3 else user_path
    elif score == 7:  # National level
        return '.'.join(segments[:2]) if len(segments) >= 2 else user_path
    elif score >= 8:  # Continental/Global level
        return segments[0]  # 'org'
    
    return user_path  # Fallback


def can_assign_role(assigner_score: int, target_score: int) -> bool:
    """
    Check if a user can assign a role based on score hierarchy.
    
    Users can only assign roles with scores lower than their own.
    
    Args:
        assigner_score: Score of user trying to assign role
        target_score: Score of role being assigned
    
    Returns:
        bool: True if assignment is allowed
    
    Example:
        >>> can_assign_role(6, 4)  # State pastor assigning group pastor
        True
        >>> can_assign_role(4, 6)  # Group pastor trying to assign state pastor
        False
    """
    return assigner_score > target_score
