import asyncio

from app.core import analytics_cache


def test_cache_coalesces_concurrent_calls_and_releases_key_lock():
    async def scenario():
        analytics_cache.clear()
        calls = 0

        async def build():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return {"value": 42}

        values = await asyncio.gather(*(
            analytics_cache.get_or_set("same-key", build) for _ in range(20)
        ))
        assert values == [{"value": 42}] * 20
        assert calls == 1
        assert "same-key" not in analytics_cache._analytics_cache_locks

    asyncio.run(scenario())


def test_cache_evicts_old_entries_at_configured_capacity(monkeypatch):
    monkeypatch.setattr(analytics_cache, "_MAX_ANALYTICS_CACHE_ENTRIES", 2)

    async def scenario():
        analytics_cache.clear()

        async def build(value):
            async def factory():
                return value
            return await analytics_cache.get_or_set(value, factory)

        await build("a")
        await build("b")
        await build("c")
        assert len(analytics_cache._analytics_cache) == 2
        assert "a" not in analytics_cache._analytics_cache
        assert not analytics_cache._analytics_cache_locks

    asyncio.run(scenario())
    analytics_cache.clear()
