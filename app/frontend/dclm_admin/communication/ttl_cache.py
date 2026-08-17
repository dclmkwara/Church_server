from __future__ import annotations

import asyncio
from inspect import isawaitable
from threading import RLock
from time import monotonic
from typing import Awaitable, Callable, TypeVar


T = TypeVar("T")

_LOCK = RLock()
_CACHE: dict[tuple[object, ...], tuple[float, object]] = {}


async def _store_awaited_value(key: tuple[object, ...], ttl_seconds: float, value: Awaitable[T]) -> T:
    try:
        resolved = await value
    except Exception:
        invalidate_ttl_prefix(key)
        raise
    with _LOCK:
        _CACHE[key] = (monotonic() + ttl_seconds, resolved)
    return resolved


def ttl_cached(key: tuple[object, ...], ttl_seconds: float, factory: Callable[[], T]) -> T:
    """Return a cached value or call factory() to populate the cache.

    Async factories are stored as in-flight tasks, then replaced with the
    resolved value. This avoids repeated backend calls during HTMX bursts.
    """
    now = monotonic()
    with _LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            expires_at, value = cached
            if expires_at > now:
                return value  # type: ignore[return-value]

        value = factory()
        if isawaitable(value):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                resolved = asyncio.run(value)  # type: ignore[arg-type]
                _CACHE[key] = (monotonic() + ttl_seconds, resolved)
                return resolved
            task = loop.create_task(_store_awaited_value(key, ttl_seconds, value))  # type: ignore[arg-type]
            _CACHE[key] = (now + ttl_seconds, task)
            return task  # type: ignore[return-value]

        _CACHE[key] = (now + ttl_seconds, value)
        return value


def invalidate_ttl_prefix(prefix: tuple[object, ...]) -> None:
    with _LOCK:
        stale_keys = [key for key in _CACHE if key[: len(prefix)] == prefix]
        for key in stale_keys:
            _CACHE.pop(key, None)


__all__ = ["invalidate_ttl_prefix", "ttl_cached"]
