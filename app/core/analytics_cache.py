from __future__ import annotations

import asyncio
import time
from copy import deepcopy
from typing import Any, Awaitable, Callable, Hashable

_DEFAULT_ANALYTICS_CACHE_TTL = 20.0
_analytics_cache: dict[Hashable, tuple[Any, float]] = {}
_analytics_cache_locks: dict[Hashable, asyncio.Lock] = {}
_analytics_cache_guard = asyncio.Lock()


async def _get_cached_value(cache_key: Hashable) -> Any | None:
    now = time.monotonic()
    async with _analytics_cache_guard:
        entry = _analytics_cache.get(cache_key)
        if entry is None:
            return None
        value, expires_at = entry
        if now >= expires_at:
            _analytics_cache.pop(cache_key, None)
            return None
        return deepcopy(value)


async def _store_cached_value(cache_key: Hashable, value: Any, *, ttl: float) -> Any:
    cached_value = deepcopy(value)
    expires_at = time.monotonic() + ttl
    async with _analytics_cache_guard:
        _analytics_cache[cache_key] = (cached_value, expires_at)
    return deepcopy(cached_value)


async def _get_cache_lock(cache_key: Hashable) -> asyncio.Lock:
    async with _analytics_cache_guard:
        lock = _analytics_cache_locks.get(cache_key)
        if lock is None:
            lock = asyncio.Lock()
            _analytics_cache_locks[cache_key] = lock
        return lock


async def get_or_set(
    cache_key: Hashable,
    factory: Callable[[], Awaitable[Any]],
    *,
    ttl: float = _DEFAULT_ANALYTICS_CACHE_TTL,
) -> Any:
    cached = await _get_cached_value(cache_key)
    if cached is not None:
        return cached

    lock = await _get_cache_lock(cache_key)
    async with lock:
        cached = await _get_cached_value(cache_key)
        if cached is not None:
            return cached
        value = await factory()
        return await _store_cached_value(cache_key, value, ttl=ttl)


def invalidate(cache_key: Hashable) -> None:
    _analytics_cache.pop(cache_key, None)


def clear() -> None:
    _analytics_cache.clear()
