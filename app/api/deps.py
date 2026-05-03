"""
Dependencies for API routes — authentication, database access, and authorisation.

Changes from original
---------------------
* get_current_user now uses a 60-second in-process TTL cache keyed on user_id.
  This avoids a DB round-trip on every authenticated request while still
  picking up role / activation changes within a reasonable window.
* PermissionChecker superadmin guard now uses the correct role.score_value
  property (which reads role.score.score internally) instead of the previously
  mixed attribute access.
"""
import asyncio
import time
import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.crud.crud_user import user as crud_user
from app.db.session import get_db, inject_scope
from app.models.core import validate_path
from app.models.location import Location
from app.models.user import User
from app.schemas.user import TokenPayload

logger = logging.getLogger(__name__)

# ── OAuth2 scheme ──────────────────────────────────────────────────────────────
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login"
)

# ── In-process user identity cache ────────────────────────────────────────────
# Structure: { user_id_str: (User, expires_monotonic) }
# TTL is intentionally short (60 s) so role / activation changes propagate
# within one minute without requiring a full logout cycle.
_USER_CACHE_TTL: float = 60.0
_user_cache: dict[str, tuple[User, float]] = {}
_user_cache_lock = asyncio.Lock()


async def _get_cached_user(db: AsyncSession, user_id: str) -> Optional[User]:
    """Return a fresh-session copy of a cached User if the entry is still fresh."""
    now = time.monotonic()
    async with _user_cache_lock:
        entry = _user_cache.get(user_id)
        if entry is not None:
            cached_user, expires_at = entry
            if now < expires_at:
                return await db.merge(cached_user, load=False)
            # Expired — remove stale entry
            _user_cache.pop(user_id, None)
    return None


async def _cache_user(user_obj: User) -> None:
    """Store a User in the cache with a fresh TTL."""
    key = str(user_obj.user_id)
    expires_at = time.monotonic() + _USER_CACHE_TTL
    async with _user_cache_lock:
        _user_cache[key] = (user_obj, expires_at)


def invalidate_user_cache(user_id: str) -> None:
    """
    Evict a user from the cache immediately.
    Call this after role changes, deactivation, or approval status updates.
    """
    _user_cache.pop(str(user_id), None)


# ── Core auth dependency ───────────────────────────────────────────────────────

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2),
) -> User:
    """
    Validate the bearer token, inject the RLS scope, and return the User.

    DB lookup is skipped when a fresh cached entry exists (TTL = 60 s).
    """
    try:
        payload = security.verify_token(token)
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )

    # Try cache first
    user = await _get_cached_user(db, token_data.sub)
    if user is None:
        user = await crud_user.get(db, id=token_data.sub)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        await _cache_user(user)

    # Inject RLS scope from the token claim (avoids extra DB set_config round-trip
    # only when scope_path is already available in the JWT).
    if token_data.scope_path:
        await inject_scope(db, token_data.scope_path)

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Raise 400 if the authenticated user is inactive."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


# ── Path helpers ───────────────────────────────────────────────────────────────

def _normalize_path(path: object) -> str:
    return str(path).strip() if path is not None else ""


def path_in_scope(scope_path: object, target_path: object) -> bool:
    """True when target_path is equal to, or a descendant of, scope_path."""
    scope = _normalize_path(scope_path)
    target = _normalize_path(target_path)
    if not scope or not target:
        return False
    return target == scope or target.startswith(f"{scope}.")


def resolve_scope_path(
    current_user: User,
    requested_scope_path: Optional[str] = None,
) -> str:
    """
    Return a safe effective scope path, rejecting any escalation attempt.

    Args:
        current_user: The authenticated user (scope capped to their home path).
        requested_scope_path: Optional narrower scope requested by the caller.

    Returns:
        Resolved scope path string.

    Raises:
        HTTPException 400 if the requested path is malformed.
        HTTPException 403 if the requested path is outside the user's scope.
    """
    current_scope = _normalize_path(current_user.path)
    if not current_scope:
        raise HTTPException(status_code=403, detail="Current user has no assigned scope")

    if not requested_scope_path:
        return current_scope

    requested_scope = requested_scope_path.strip()
    if not validate_path(requested_scope):
        raise HTTPException(status_code=400, detail="Invalid scope path format")
    if not path_in_scope(current_scope, requested_scope):
        raise HTTPException(
            status_code=403,
            detail="Requested scope is outside your allowed scope",
        )
    return requested_scope


def ensure_path_in_scope(
    current_user: User,
    target_path: object,
    detail: str = "Resource outside your scope",
) -> str:
    """Validate that a resource path is reachable within the user's scope."""
    normalized_target = _normalize_path(target_path)
    if not normalized_target or not path_in_scope(current_user.path, normalized_target):
        raise HTTPException(status_code=403, detail=detail)
    return normalized_target


async def get_location_in_scope(
    db: AsyncSession,
    *,
    current_user: User,
    location_id: str,
    detail: str = "Location outside your scope",
) -> Location:
    """Fetch a location and confirm it sits within the caller's scope."""
    location = await db.get(Location, location_id)
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")
    ensure_path_in_scope(current_user, location.path, detail=detail)
    return location


def ensure_same_user(current_user: User, target_user_id: object) -> None:
    """Restrict an operation to the currently authenticated user."""
    if str(current_user.user_id) != str(target_user_id):
        raise HTTPException(
            status_code=403,
            detail="You can only manage your own recovery settings",
        )


# ── Permission checker ─────────────────────────────────────────────────────────

class PermissionChecker:
    """
    FastAPI dependency that enforces a named permission on the current user.

    Superadmin (score >= 9) is granted unconditional access.
    All other users must have the required permission string on at least one
    of their assigned roles.

    Usage:
        @router.get("/resource", dependencies=[Depends(PermissionChecker("resource:read"))])
    """

    def __init__(self, required_permission: str) -> None:
        self.required_permission = required_permission

    async def __call__(
        self,
        current_user: User = Depends(get_current_active_user),
    ) -> User:
        if current_user.roles:
            # Superadmin bypass — role.score_value is a @property on the Role
            # model that safely returns role.score.score (or 0 if not loaded).
            if any(role.score_value >= 9 for role in current_user.roles):
                return current_user

            # Permission check across all assigned roles
            for role in current_user.roles:
                for perm in role.permissions:
                    if perm.permission == self.required_permission:
                        return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation not permitted. Required permission: {self.required_permission}",
        )
