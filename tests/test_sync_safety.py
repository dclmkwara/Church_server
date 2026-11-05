import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

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
        "worker_attendance_submissions": [],
        "worker_candidates": [],
        "fellowship_members": [],
        "fellowship_attendance": [],
        "fellowship_offerings": [],
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_sync_batch_size_counts_all_payload_buckets():
    batch = _batch(counts=[1, 2], offerings=[1], fellowship_members=[1, 2, 3], worker_candidates=[1])

    assert sync._sync_batch_size(batch) == 7


def test_batch_sync_rejects_unbounded_payload_before_db_work():
    batch = _batch(counts=[object()] * (sync.MAX_SYNC_BATCH_RECORDS + 1))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(sync.batch_sync(db=None, batch=batch, current_user=SimpleNamespace(user_id="u1")))

    assert exc_info.value.status_code == 413


def test_batch_actor_snapshot_survives_shared_session_rollback_expiry():
    role = SimpleNamespace(score_value=1)
    user = SimpleNamespace(
        user_id=uuid4(), worker_id=uuid4(), location_id=uuid4(),
        name="Field worker", path="org.234.KW.ILR.ILE.003", roles=[role],
    )

    actor = sync._snapshot_sync_actor(user)
    user.roles.clear()
    user.worker_id = None

    assert sync.deps.highest_role_score(actor) == 1
    assert actor.worker_id is not None
    assert actor.path == "org.234.KW.ILR.ILE.003"


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


def test_attendance_submission_retry_recovers_canonical_row_in_scope(monkeypatch):
    client_id = uuid4()
    canonical = SimpleNamespace(id=uuid4(), path="org.234.KW")
    current_user = SimpleNamespace(path="org.234.KW")

    class Scalars:
        def first(self):
            return canonical

    class Result:
        def scalars(self):
            return Scalars()

    class FakeDB:
        async def execute(self, _query):
            return Result()

    monkeypatch.setattr(sync.deps, "ensure_path_in_scope", lambda *_a, **_kw: None)
    recovered = asyncio.run(
        sync._recover_attendance_submission_duplicate(FakeDB(), current_user, client_id)
    )

    assert recovered is canonical


def test_attendance_submission_duplicate_recovery_checks_existing_scope(monkeypatch):
    canonical = SimpleNamespace(id=uuid4(), path="org.234.KW.ILN")
    current_user = SimpleNamespace(path="org.234.KW.ILE")

    class Scalars:
        def first(self):
            return canonical

    class Result:
        def scalars(self):
            return Scalars()

    class FakeDB:
        async def execute(self, _query):
            return Result()

    def reject_scope(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="outside scope")

    monkeypatch.setattr(sync.deps, "ensure_path_in_scope", reject_scope)
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(sync._recover_attendance_submission_duplicate(FakeDB(), current_user, uuid4()))

    assert exc_info.value.status_code == 403


def test_worker_candidate_role_is_cached_and_non_field_items_are_rejected(monkeypatch):
    calls = 0

    class Scalars:
        def all(self):
            return []

    class Result:
        def scalars(self):
            return Scalars()

    class FakeDB:
        async def execute(self, _query):
            return Result()

    item_a = SimpleNamespace(client_id=uuid4())
    item_b = SimpleNamespace(client_id=uuid4())
    user = SimpleNamespace(user_id=uuid4(), worker_id=uuid4(), location_id="loc-1", roles=[SimpleNamespace(score_value=2)])

    def role_score(_user):
        nonlocal calls
        calls += 1
        return 2

    monkeypatch.setattr(sync.deps, "highest_role_score", role_score)
    result = asyncio.run(sync.process_worker_candidates(FakeDB(), [item_a, item_b], user))

    assert result.synced == 0
    assert result.errors == 2
    assert calls == 1
    assert all(detail["status"] == "error" for detail in result.details)
    assert "Level 1" in result.details[0]["error"]


def test_worker_integrity_error_extracts_asyncpg_constraint_name():
    error = IntegrityError("insert", {}, RuntimeError('duplicate key violates unique constraint "uq_worker_phone"'))

    assert sync._worker_integrity_constraint_name(error) == "uq_worker_phone"
