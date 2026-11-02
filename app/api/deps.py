"""
Dependencies for API routes — authentication, database access, and authorisation.

Authorization is refreshed from the database on each request so role changes
take effect immediately. Level-8 users receive a broad ltree envelope plus a
resolved list of nation paths for their continent; route filters must apply
that nation list wherever data is queried.
"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy import String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.config import settings
from app.crud.crud_user import user as crud_user
from app.db.session import get_db, inject_auth_user, inject_continent, inject_scope
from app.db.filters import set_scope_context
from app.models.core import validate_path
from app.models.location import Location, Nation
from app.models.user import User
from app.schemas.user import TokenPayload

# ── OAuth2 scheme ──────────────────────────────────────────────────────────────
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login"
)

# ── In-process user identity cache (imported from core to prevent circular dependencies) ───
from app.core.auth_cache import (
    _user_cache,
    _user_cache_lock,
    get_cached_user as _get_cached_user,
    cache_user as _cache_user,
    invalidate_user_cache,
)


# ── Core auth dependency ───────────────────────────────────────────────────────

async def get_current_user(
    db: AsyncSession = Depends(get_db),
    token: str = Depends(reusable_oauth2),
) -> User:
    """
    Validate the bearer token, inject the RLS scope, and return the User.

    User and role data are loaded fresh so permission changes take effect
    across replicas without waiting for process-local cache expiration.
    """
    try:
        payload = security.verify_token(token)
        # Refresh tokens use the same signing key but are only valid at the
        # refresh endpoint. Reject them before loading any protected resource.
        if payload.get("type") == "refresh":
            raise JWTError("Refresh token cannot be used as an access token")
        token_data = TokenPayload(**payload)
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not token_data.sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # The verified JWT subject is the only row visible before the effective
    # hierarchy scope is recomputed from current database roles.
    await inject_auth_user(db, token_data.sub)
    user = await crud_user.get(db, id=token_data.sub)
    if not user or user.is_deleted or not user.is_active or user.approval_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive or not approved",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # JWT scope is informational only. Recompute from current roles and home
    # path so role changes take effect on the next request.
    await resolve_continental_scope(db, user)

    await inject_scope(
        db,
        effective_scope_path(user),
        role_score=highest_role_score(user),
        continent=getattr(user, "_authorized_continent", None),
        user_id=str(user.user_id),
        nation_paths=tuple(getattr(user, "_authorized_nation_paths", ()) or ()),
    )
    set_scope_context(
        highest_role_score(user),
        tuple(getattr(user, "_authorized_nation_paths", ()) or ()),
    )

    return user


async def resolve_continental_scope(db: AsyncSession, user: User) -> tuple[str, ...]:
    """Resolve level-8 Nation paths once for both auth and request scope setup."""
    if highest_role_score(user) != 8:
        user._authorized_nation_paths = ()
        user._authorized_continent = None
        return ()

    home_path = _normalize_path(user.path)
    if not validate_path(home_path) or len(home_path.split(".")) < 2:
        raise HTTPException(status_code=403, detail="Continental role must have a valid nation home path")
    nation_path = ".".join(home_path.split(".")[:2])
    home_nation_result = await db.execute(select(Nation).where(Nation.path == nation_path))
    home_nation = home_nation_result.scalar_one_or_none()
    if home_nation is None:
        raise HTTPException(status_code=403, detail="Continental role must be assigned beneath a nation")
    if not home_nation.continent or not home_nation.continent.strip():
        raise HTTPException(status_code=403, detail="Continental role has no assigned continent")
    await inject_continent(db, home_nation.continent)
    nations = await db.execute(
        select(Nation.path).where(
            func.lower(func.trim(Nation.continent)) == home_nation.continent.strip().lower()
        )
    )
    user._authorized_nation_paths = tuple(str(row[0]) for row in nations.all())
    user._authorized_continent = home_nation.continent.strip()
    return user._authorized_nation_paths


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


def highest_role_score(current_user: User) -> int:
    """Return the highest active role score currently assigned to a user."""
    return max(
        (getattr(role, "score_value", 0) for role in (getattr(current_user, "roles", None) or [])),
        default=0,
    )


def _continental_nation_paths(current_user: User) -> tuple[str, ...]:
    paths = tuple(getattr(current_user, "_authorized_nation_paths", ()) or ())
    if not paths:
        raise HTTPException(status_code=403, detail="Continental scope is not resolved")
    return paths


def scope_condition(path_column: object, current_user: User, requested_scope_path: Optional[str] = None):
    """SQL filter for effective hierarchy scope, including level-8 continent."""
    from sqlalchemy import and_, cast, func, literal
    from app.models.core import _LTREE
    from app.db.filters import scope_filter

    scope_path = resolve_scope_path(current_user, requested_scope_path)
    conditions = [scope_filter(path_column, scope_path)]
    if highest_role_score(current_user) == 8:
        raw_column = getattr(getattr(path_column, "property", None), "columns", [path_column])[0]
        nation_prefix = func.subpath(cast(raw_column, _LTREE()), literal(0), literal(2))
        conditions.append(cast(nation_prefix, String).in_(_continental_nation_paths(current_user)))
    return and_(*conditions)


def effective_scope_path(current_user: User) -> str:
    """Derive the ltree envelope from current roles and home path.

    For level 8 this is only a broad query envelope; callers must also apply
    the continent nation filter from ``nation_scope_condition``.
    """
    home_path = _normalize_path(getattr(current_user, "path", None))
    if not home_path or not validate_path(home_path):
        raise HTTPException(status_code=403, detail="Current user has no valid assigned scope")

    return security.create_admin_access_id(home_path, highest_role_score(current_user))


def nation_scope_condition(path_column: object, current_user: User):
    """SQL condition restricting level-8 records to the user's continent.

    Nation.continent is the authoritative grouping available in the current
    schema. The nation path is joined through ltree containment, so this works
    for any scoped table whose ``path`` includes ``org.<nation-id>``.
    """
    from sqlalchemy import String, cast, func, literal
    from app.models.core import _LTREE

    score = highest_role_score(current_user)
    if score >= 9:
        return literal(True)
    if score != 8:
        return literal(True)

    home_path = _normalize_path(getattr(current_user, "path", None))
    if not home_path or not validate_path(home_path):
        raise HTTPException(status_code=403, detail="Current user has no valid assigned scope")

    nation_path = func.subpath(cast(path_column, _LTREE()), literal(0), literal(2))
    return cast(nation_path, String).in_(_continental_nation_paths(current_user))


def filter_rows_in_scope(rows: list, current_user: User) -> list:
    """Fail-safe row filter for CRUD list methods with path-only interfaces.

    Use SQL scope conditions for aggregates and paginated queries. This helper
    prevents cross-continent rows from being returned by legacy CRUD methods
    while those query interfaces are migrated.
    """
    if highest_role_score(current_user) != 8:
        return rows
    allowed_nations = set(_continental_nation_paths(current_user))
    return [
        row for row in rows
        if ".".join(_normalize_path(getattr(row, "path", None)).split(".")[:2]) in allowed_nations
    ]


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
    current_scope = effective_scope_path(current_user)

    if not requested_scope_path:
        return current_scope

    requested_scope = requested_scope_path.strip()
    if not validate_path(requested_scope):
        raise HTTPException(status_code=400, detail="Invalid scope path format")
    if highest_role_score(current_user) == 8:
        if not any(path_in_scope(nation_path, requested_scope) for nation_path in _continental_nation_paths(current_user)):
            raise HTTPException(status_code=403, detail="Requested scope is outside your continental jurisdiction")
    elif not path_in_scope(current_scope, requested_scope):
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
    in_scope = bool(normalized_target) and path_in_scope(effective_scope_path(current_user), normalized_target)
    if normalized_target and highest_role_score(current_user) == 8:
        target_nation_path = ".".join(normalized_target.split(".")[:2])
        in_scope = target_nation_path in _continental_nation_paths(current_user)
    if not in_scope:
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
