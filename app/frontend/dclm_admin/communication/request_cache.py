from __future__ import annotations

import asyncio
from inspect import isawaitable
from typing import Any, Callable, TypeVar


T = TypeVar("T")


async def request_cached(request: Any, key: tuple[Any, ...], factory: Callable[[], T]) -> T:
    """Return a cached value for this request, calling factory() on the first miss.

    Supports both sync and async factories — if factory() returns a coroutine it is awaited.
    """
    state = getattr(request, "state", None)
    if state is None:
        result = factory()
        if isawaitable(result):
            return await result
        return result
    bucket = getattr(state, "_dclm_request_cache", None)
    if bucket is None:
        bucket = {}
        setattr(state, "_dclm_request_cache", bucket)
    if key not in bucket:
        result = factory()
        if asyncio.iscoroutine(result):
            result = asyncio.create_task(result)
        bucket[key] = result
    result = bucket[key]
    if isinstance(result, asyncio.Task):
        try:
            value = await result
        except Exception:
            bucket.pop(key, None)
            raise
        bucket[key] = value
        return value
    if isawaitable(result):
        try:
            value = await result
        except Exception:
            bucket.pop(key, None)
            raise
        bucket[key] = value
        return value
    return bucket[key]


__all__ = ["request_cached"]
