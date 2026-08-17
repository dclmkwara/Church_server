"""
Security utilities for authentication and authorisation.

datetime.utcnow() is deprecated in Python 3.12+.
All token timestamps now use datetime.now(timezone.utc).
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt as _bcrypt
from jose import JWTError, jwt

from app.core.config import settings


# ── Password hashing ───────────────────────────────────────────────────────────
# NOTE: passlib 1.7.4 is incompatible with bcrypt 4.x (it pre-hashes with sha256
# producing a 128-byte hex string that bcrypt 4.x refuses). We call bcrypt directly.

def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt (direct, no passlib wrapper)."""
    return _bcrypt.hashpw(password[:72].encode("utf-8"), _bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its bcrypt hash (direct, no passlib wrapper)."""
    try:
        return _bcrypt.checkpw(plain_password[:72].encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# ── Access token ───────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token with custom claims.

    Args:
        data: Token payload (must include 'sub', and typically includes
              role, score, home_path, scope_path).
        expires_delta: Custom expiry; defaults to ACCESS_TOKEN_EXPIRE_MINUTES.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {**data, "exp": expire, "iat": now}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ── Refresh token ──────────────────────────────────────────────────────────────
# Refresh tokens have their OWN signing path so that changes to access-token
# structure do not silently affect them.  Each token carries a unique `jti`
# (JWT ID) so it can be tracked and rotated in the database.

def create_refresh_token(user_id: str) -> tuple[str, str]:
    """
    Create a signed JWT refresh token.

    The token embeds a unique `jti` (JWT ID) that must be stored in the
    database.  On each use the old jti is revoked and a new token is issued.

    Args:
        user_id: UUID string of the authenticated user.

    Returns:
        Tuple of (encoded_token_string, jti_string).
        The caller is responsible for persisting the jti to the DB.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    jti = str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return token, jti


# ── Token verification ─────────────────────────────────────────────────────────

def verify_token(token: str) -> dict:
    """
    Verify and decode any JWT token issued by this application.

    Args:
        token: Raw JWT string.

    Returns:
        Decoded payload dict.

    Raises:
        JWTError: If the token is invalid, expired, or tampered with.
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise JWTError(f"Invalid token: {exc}") from exc


# ── Scope helpers ──────────────────────────────────────────────────────────────

def create_admin_access_id(user_path: str, score: int) -> str:
    """
    Derive a scope path from a user's home path and role score.

    Score → scope depth mapping:
        1-3  → full path (location only)
        4    → group level  (5 segments)
        5    → region level (4 segments)
        6    → state level  (3 segments)
        7    → national     (2 segments)
        8-9  → root         (1 segment, 'org')

    Args:
        user_path: e.g. 'org.234.kw.iln.ile.001'
        score: Role score 1-9.

    Returns:
        Effective scope path string.
    """
    segments = user_path.split(".")
    if score <= 3:
        return user_path
    if score == 4:
        return ".".join(segments[:5]) if len(segments) >= 5 else user_path
    if score == 5:
        return ".".join(segments[:4]) if len(segments) >= 4 else user_path
    if score == 6:
        return ".".join(segments[:3]) if len(segments) >= 3 else user_path
    if score == 7:
        return ".".join(segments[:2]) if len(segments) >= 2 else user_path
    # score >= 8
    return segments[0]


def can_assign_role(assigner_score: int, target_score: int) -> bool:
    """
    Return True when the assigner's score is strictly above the target score.
    Users may only assign roles with a lower hierarchy score than their own.
    """
    return assigner_score > target_score
