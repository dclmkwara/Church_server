import asyncio
import os
from pathlib import Path
import sys
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError


class _UniqueViolation:
    class diag:
        constraint_name = "uq_counts_client_id"

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.crud.idempotency import commit_idempotent
from app.schemas.counts import CountCreate
from app.schemas.sync import SyncBatchRequest
from app.schemas.user import WorkerCandidateCreate


def _count_submission(client_id):
    return {
        "event_id": uuid4(),
        "location_id": "location-1",
        "client_id": client_id,
        "adult_male": 10,
        "adult_female": 12,
    }


def test_sync_batch_requires_client_ids_for_retry_safety():
    with pytest.raises(ValidationError, match="require client_id"):
        SyncBatchRequest(counts=[_count_submission(None)])


def test_distinct_usher_submissions_for_same_location_are_valid():
    event_id = uuid4()
    location_id = "location-1"
    first = CountCreate(**{**_count_submission(uuid4()), "event_id": event_id, "location_id": location_id})
    second = CountCreate(**{**_count_submission(uuid4()), "event_id": event_id, "location_id": location_id})

    batch = SyncBatchRequest(counts=[first, second])

    assert len(batch.counts) == 2
    assert batch.counts[0].client_id != batch.counts[1].client_id
    assert batch.counts[0].event_id == batch.counts[1].event_id
    assert batch.counts[0].location_id == batch.counts[1].location_id


def test_worker_candidate_payload_requires_stable_client_id_and_candidate_details():
    candidate = WorkerCandidateCreate(
        client_id=uuid4(), name="Test Candidate", gender="Female", phone="+2348012345678",
        email="candidate@example.org", unit="Ushering",
    )
    batch = SyncBatchRequest(worker_candidates=[candidate])
    assert batch.worker_candidates[0].client_id == candidate.client_id

    with pytest.raises(ValidationError):
        WorkerCandidateCreate(name="Missing ID", gender="Male", phone="+2348012345678",
                              email="missing@example.org", unit="Choir")


def test_concurrent_duplicate_insert_returns_canonical_record():
    client_id = uuid4()
    canonical = type("Submission", (), {"id": uuid4(), "client_id": client_id})()
    candidate = type("Submission", (), {"id": uuid4(), "client_id": client_id})()
    candidate.__table__ = type("Table", (), {"name": "counts"})()

    class FakeSession:
        rolled_back = False

        async def commit(self):
            raise IntegrityError("insert", {}, _UniqueViolation())

        async def rollback(self):
            self.rolled_back = True

    async def lookup(session, requested_client_id):
        assert requested_client_id == client_id
        return canonical

    result = asyncio.run(
        commit_idempotent(FakeSession(), candidate, client_id=client_id, lookup=lookup)
    )

    assert result is canonical
    assert result._was_duplicate_submission is True
