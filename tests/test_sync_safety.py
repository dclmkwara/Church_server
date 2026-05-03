import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-suite-32-chars-min")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.v1.routes import sync


def _batch(**overrides):
    base = {
        "counts": [],
        "offerings": [],
        "records": [],
        "worker_attendance": [],
        "fellowship_members": [],
        "fellowship_attendance": [],
        "fellowship_offerings": [],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_sync_batch_size_counts_all_payload_buckets():
    batch = _batch(counts=[1, 2], offerings=[1], fellowship_members=[1, 2, 3])

    assert sync._sync_batch_size(batch) == 6


def test_batch_sync_rejects_unbounded_payload_before_db_work():
    batch = _batch(counts=[object()] * (sync.MAX_SYNC_BATCH_RECORDS + 1))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(sync.batch_sync(db=None, batch=batch, current_user=SimpleNamespace(user_id="u1")))

    assert exc_info.value.status_code == 413


def test_location_scope_validation_uses_cache(monkeypatch):
    calls = 0

    async def fake_get_location_in_scope(*args, **kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(path="org.234.KW")

    monkeypatch.setattr(sync.deps, "get_location_in_scope", fake_get_location_in_scope)
    current_user = SimpleNamespace(path="org.234")
    item = SimpleNamespace(location_id="001")
    cache = {}

    asyncio.run(sync._ensure_sync_item_in_scope(None, current_user, item, cache))
    asyncio.run(sync._ensure_sync_item_in_scope(None, current_user, item, cache))

    assert calls == 1
