from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

_USER_CACHE_TTL: float = 60.0
_user_cache: dict[str, tuple[Any, float]] = {}
_user_cache_lock = asyncio.Lock()


async def get_cached_user(db: AsyncSession, user_id: str) -> Optional[Any]:
    """Return a fresh-session copy of a cached User if the entry is still fresh."""
    now = time.monotonic()
    async with _user_cache_lock:
        entry = _user_cache.get(user_id)
        if entry is not None:
            cached_user, expires_at = entry
            if now < expires_at:
                return await db.merge(cached_user, load=False)
            _user_cache.pop(user_id, None)
    return None


async def cache_user(user_obj: Any) -> None:
    """Store a User in the cache with a fresh TTL."""
    key = str(getattr(user_obj, "user_id", ""))
    expires_at = time.monotonic() + _USER_CACHE_TTL
    async with _user_cache_lock:
        _user_cache[key] = (user_obj, expires_at)


def invalidate_user_cache(user_id: str) -> None:
    """Evict a user from the cache immediately."""
    _user_cache.pop(str(user_id), None)


def clear_user_cache() -> None:
    """Clear all entries in the user cache."""
    _user_cache.clear()
