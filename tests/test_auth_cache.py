import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import deps
from app.core.auth_cache import _token_user_cache, clear_user_cache, invalidate_user_cache


class MergeTrackingSession:
    def __init__(self):
        self.calls = []

    async def merge(self, obj, *, load):
        self.calls.append((obj, load))
        return SimpleNamespace(user_id=obj.user_id, merged=True)


def test_cached_user_is_merged_into_current_session():
    async def run():
        deps._user_cache.clear()
        cached = SimpleNamespace(user_id="user-1")
        await deps._cache_user(cached)

        db = MergeTrackingSession()
        user = await deps._get_cached_user(db, "user-1")

        assert user.merged is True
        assert db.calls == [(cached, False)]

    asyncio.run(run())


def test_expired_cached_user_is_evicted():
    async def run():
        deps._user_cache.clear()
        deps._user_cache["user-1"] = (SimpleNamespace(user_id="user-1"), 0.0)

        db = MergeTrackingSession()
        user = await deps._get_cached_user(db, "user-1")

        assert user is None
        assert "user-1" not in deps._user_cache
        assert db.calls == []

    asyncio.run(run())


def test_permission_snapshot_is_keyed_by_token_digest_and_user_invalidation_evicts_it():
    async def run():
        clear_user_cache()
        token = "signed-token-never-stored"
        cached = SimpleNamespace(user_id="user-2")
        await deps._cache_token_user(token, cached)
        assert len(_token_user_cache) == 1
        assert token not in next(iter(_token_user_cache))

        db = MergeTrackingSession()
        user = await deps._get_token_cached_user(db, token)
        assert user.merged is True
        assert db.calls == [(cached, False)]

        invalidate_user_cache("user-2")
        assert await deps._get_token_cached_user(db, token) is None

    asyncio.run(run())
