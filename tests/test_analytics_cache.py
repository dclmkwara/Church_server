import asyncio
import os
from pathlib import Path
import sys

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import analytics_cache


def test_cached_result_is_copied_before_returning():
    async def run():
        analytics_cache.clear()
        calls = 0

        async def factory():
            nonlocal calls
            calls += 1
            return {"items": [1, 2, 3]}

        first = await analytics_cache.get_or_set(("demo", "copy"), factory, ttl=30.0)
        first["items"].append(4)

        second = await analytics_cache.get_or_set(("demo", "copy"), factory, ttl=30.0)

        assert calls == 1
        assert second == {"items": [1, 2, 3]}

    asyncio.run(run())


def test_concurrent_requests_share_one_factory_run():
    async def run():
        analytics_cache.clear()
        calls = 0

        async def factory():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return {"value": calls}

        first, second = await asyncio.gather(
            analytics_cache.get_or_set(("demo", "lock"), factory, ttl=30.0),
            analytics_cache.get_or_set(("demo", "lock"), factory, ttl=30.0),
        )

        assert calls == 1
        assert first == {"value": 1}
        assert second == {"value": 1}

    asyncio.run(run())
