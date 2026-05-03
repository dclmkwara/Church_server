"""Compatibility wrapper for shared API dependencies.

Routes should import dependencies from ``app.api.deps``. This module remains so
older imports from ``app.api.v1.deps`` do not fail.
"""
from app.api.deps import (  # noqa: F401
    PermissionChecker,
    ensure_path_in_scope,
    ensure_same_user,
    get_current_active_user,
    get_current_user,
    get_db,
    get_location_in_scope,
    invalidate_user_cache,
    path_in_scope,
    resolve_scope_path,
)
