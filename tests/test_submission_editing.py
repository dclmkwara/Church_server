import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.counts import SubmissionEditRevision
from app.services.submission_editing import edit_count_submission


class _Result:
    def __init__(self, rows=None, scalar=None):
        self.rows = rows or []
        self.scalar = scalar

    def scalar_one_or_none(self):
        return self.scalar

    def scalars(self):
        return self

    def all(self):
        return self.rows


class _Session:
    def __init__(self, row, revisions=None):
        self.row = row
        self.revisions = revisions or []
        self.calls = 0
        self.added = []
        self.committed = False

    async def get(self, _model, _id):
        return self.row

    async def execute(self, _statement):
        self.calls += 1
        if self.calls == 1:
            return _Result(scalar=self.row)
        if self.calls == 2:
            return _Result(scalar=None)
        return _Result(rows=self.revisions)

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.committed = True


def _context(*, status="pending", owner=None, created_at=None):
    user_id = owner or uuid4()
    row = SimpleNamespace(
        id=uuid4(), is_deleted=False, path="dclm.234.kw.region.group.location",
        entered_by_id=user_id, status=status, created_at=created_at or datetime.now(timezone.utc) - timedelta(hours=2),
        adult_male=5, adult_female=0, youth_male=0, youth_female=0, boys=0, girls=0,
        note=None, count_mode="single", section_label=None, total=5,
    )
    row.calculate_total = lambda: setattr(row, "total", row.adult_male + row.adult_female + row.youth_male + row.youth_female + row.boys + row.girls)
    actor = SimpleNamespace(user_id=user_id, path="dclm.234.kw.region.group", roles=[SimpleNamespace(score_value=1)])
    return row, actor


def test_original_submitter_can_edit_and_revision_is_written():
    row, actor = _context()
    db = _Session(row)
    result = asyncio.run(edit_count_submission(
        db, count_id=row.id, edit_id=uuid4(), base_revision=0,
        values={"adult_male": 9}, actor=actor,
    ))
    assert result["revision"] == 1
    assert row.total == 9
    assert db.committed is True
    assert len(db.added) == 1
    assert isinstance(db.added[0], SubmissionEditRevision)


def test_only_original_submitter_can_edit():
    owner, _ = _context()
    _row, other_actor = _context(owner=uuid4())
    db = _Session(owner)
    with pytest.raises(HTTPException) as error:
        asyncio.run(edit_count_submission(
            db, count_id=owner.id, edit_id=uuid4(), base_revision=0,
            values={"adult_male": 9}, actor=other_actor,
        ))
    assert error.value.status_code == 403


def test_approved_or_expired_count_cannot_be_edited():
    approved, actor = _context(status="approved")
    with pytest.raises(HTTPException) as locked:
        asyncio.run(edit_count_submission(
            _Session(approved), count_id=approved.id, edit_id=uuid4(), base_revision=0,
            values={"adult_male": 9}, actor=actor,
        ))
    assert locked.value.status_code == 409
    expired, actor = _context(created_at=datetime.now(timezone.utc) - timedelta(hours=25))
    with pytest.raises(HTTPException) as closed:
        asyncio.run(edit_count_submission(
            _Session(expired), count_id=expired.id, edit_id=uuid4(), base_revision=0,
            values={"adult_male": 9}, actor=actor,
        ))
    assert closed.value.status_code == 409


def test_edit_is_refused_one_second_after_exact_24_hour_window(monkeypatch):
    import app.services.submission_editing as editing

    fixed_now = datetime(2026, 11, 8, 12, 0, 1, tzinfo=timezone.utc)
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz else fixed_now.replace(tzinfo=None)
    monkeypatch.setattr(editing, "datetime", FrozenDateTime)
    row, actor = _context(created_at=fixed_now - timedelta(hours=24, seconds=1))
    with pytest.raises(HTTPException) as expired:
        asyncio.run(editing.edit_count_submission(
            _Session(row), count_id=row.id, edit_id=uuid4(), base_revision=0,
            values={"adult_male": 9}, actor=actor,
        ))
    assert expired.value.status_code == 409


def test_edit_limit_and_returned_correction_allowance_are_server_enforced():
    row, actor = _context()
    now = datetime.now(timezone.utc)
    three_edits = [SimpleNamespace(revision_no=i, action="edit", created_at=now - timedelta(minutes=4-i)) for i in range(1, 4)]
    with pytest.raises(HTTPException) as capped:
        asyncio.run(edit_count_submission(
            _Session(row, three_edits), count_id=row.id, edit_id=uuid4(), base_revision=3,
            values={"adult_male": 9}, actor=actor,
        ))
    assert capped.value.status_code == 409

    returned, actor = _context(status="returned")
    return_revision = SimpleNamespace(revision_no=1, action="returned", created_at=now - timedelta(minutes=5))
    result = asyncio.run(edit_count_submission(
        _Session(returned, [return_revision]), count_id=returned.id, edit_id=uuid4(), base_revision=1,
        values={"adult_male": 7}, actor=actor,
    ))
    assert result["revision"] == 2
    assert returned.status == "pending"
