from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

# Authorization snapshots are keyed by a digest of the access token and live
# for at most 30 seconds. Account-level mutations evict related entries.
_USER_CACHE_TTL: float = 30.0
_user_cache: dict[str, tuple[Any, float]] = {}
_user_cache_lock = asyncio.Lock()
_token_user_cache: dict[str, tuple[Any, float, str]] = {}
_token_user_cache_lock = asyncio.Lock()
_token_load_locks: dict[str, asyncio.Lock] = {}
_token_load_locks_guard = asyncio.Lock()


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def get_token_cached_user(db: AsyncSession, token: str) -> Optional[Any]:
    """Return a fresh-session copy of a token's cached user and permissions."""
    key = _token_key(token)
    async with _token_user_cache_lock:
        entry = _token_user_cache.get(key)
        if entry is None:
            return None
        cached_user, expires_at, _user_id = entry
        if time.monotonic() >= expires_at:
            _token_user_cache.pop(key, None)
            return None
        return await db.merge(cached_user, load=False)


async def cache_token_user(token: str, user_obj: Any) -> None:
    """Store a bounded authorization snapshot without retaining the raw token."""
    key = _token_key(token)
    user_id = str(getattr(user_obj, "user_id", ""))
    async with _token_user_cache_lock:
        now = time.monotonic()
        expired = [item_key for item_key, (_, expires, _) in _token_user_cache.items() if expires <= now]
        for item_key in expired:
            _token_user_cache.pop(item_key, None)
        if len(_token_user_cache) >= 10_000:
            oldest = min(_token_user_cache, key=lambda item_key: _token_user_cache[item_key][1])
            _token_user_cache.pop(oldest, None)
        _token_user_cache[key] = (user_obj, now + _USER_CACHE_TTL, user_id)


async def token_user_load_lock(token: str) -> asyncio.Lock:
    """Return a per-token lock to coalesce simultaneous cold authorization reads."""
    key = _token_key(token)
    async with _token_load_locks_guard:
        lock = _token_load_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _token_load_locks[key] = lock
        return lock


async def release_token_user_load_lock(token: str, lock: asyncio.Lock) -> None:
    key = _token_key(token)
    async with _token_load_locks_guard:
        if _token_load_locks.get(key) is lock:
            _token_load_locks.pop(key, None)


async def get_cached_user(db: AsyncSession, user_id: str) -> Optional[Any]:
    """Return a fresh-session copy of a user-ID keyed compatibility entry."""
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
    key = str(getattr(user_obj, "user_id", ""))
    async with _user_cache_lock:
        _user_cache[key] = (user_obj, time.monotonic() + _USER_CACHE_TTL)


def invalidate_user_cache(user_id: str) -> None:
    """Evict all cached authorization snapshots for a changed user."""
    key = str(user_id)
    _user_cache.pop(key, None)
    for token_key, (_, _, cached_user_id) in list(_token_user_cache.items()):
        if cached_user_id == key:
            _token_user_cache.pop(token_key, None)


def clear_user_cache() -> None:
    _user_cache.clear()
    _token_user_cache.clear()
    _token_load_locks.clear()
