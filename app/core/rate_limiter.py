"""
In-process sliding-window rate limiter — no external services required.

Design notes
------------
* Uses asyncio.Lock for thread-safety within a single process.
* Each uvicorn worker maintains its own independent window.  For multi-worker
  deployments this means the effective limit is (max_requests × workers), which
  is an acceptable trade-off without Redis.
* Timestamps older than the window are pruned on every check, so memory stays
  bounded even under sustained traffic.
* A background cleanup task is NOT needed — pruning happens inline.
"""
import asyncio
import time
from collections import defaultdict

# Store: key → list of monotonic timestamps of recent requests
_store: dict[str, list[float]] = defaultdict(list)
_lock = asyncio.Lock()


async def is_allowed(key: str, *, max_requests: int, window_seconds: float) -> bool:
    """
    Check whether the given key is within its rate limit.

    Args:
        key: Unique identifier for the rate limit bucket (e.g., IP address,
             user_id, or a combination).
        max_requests: Maximum number of requests allowed within the window.
        window_seconds: Duration of the sliding window in seconds.

    Returns:
        True  — request is within limit (caller should proceed).
        False — limit exceeded (caller should return HTTP 429).
    """
    now = time.monotonic()
    cutoff = now - window_seconds

    async with _lock:
        timestamps = _store[key]
        # Prune entries that have fallen outside the window
        _store[key] = [t for t in timestamps if t > cutoff]
        if len(_store[key]) >= max_requests:
            return False
        _store[key].append(now)
        return True


async def check_rate_limit(key: str, *, max_requests: int, window_seconds: float) -> None:
    """
    Raise HTTP 429 if the key has exceeded its rate limit.

    This is a convenience wrapper for use as an inline guard in route handlers.

    Args:
        key: Bucket key (IP address recommended for login endpoints).
        max_requests: Allowed requests per window.
        window_seconds: Window duration in seconds.

    Raises:
        fastapi.HTTPException 429 when the limit is exceeded.
    """
    from fastapi import HTTPException

    if not await is_allowed(key, max_requests=max_requests, window_seconds=window_seconds):
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many requests. You are allowed {max_requests} attempts "
                f"per {int(window_seconds)} seconds. Please try again later."
            ),
            headers={"Retry-After": str(int(window_seconds))},
        )
