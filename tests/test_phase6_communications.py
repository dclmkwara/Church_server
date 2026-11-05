import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.v1.routes import broadcasts, information


class _Scalars:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class _Result:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return _Scalars(self.value)


class _Db:
    def __init__(self, target):
        self.target = target
        self.added = None

    async def execute(self, _statement):
        return _Result(self.target)

    def add(self, row):
        self.added = row

    async def commit(self):
        pass

    async def refresh(self, _row):
        pass


def _user(score: int, path: str):
    return SimpleNamespace(
        user_id="user-1",
        path=path,
        roles=[SimpleNamespace(score_value=score)],
    )


def test_weekly_information_management_requires_region_or_state_role():
    with pytest.raises(HTTPException) as exc_info:
        information._require_information_manager(_user(3, "org.234.KW.ILR.ILE"))
    assert exc_info.value.status_code == 403
    assert information._require_information_manager(_user(4, "org.234.KW.ILR")) == 4


def test_group_broadcast_rejects_target_outside_jurisdiction():
    user = _user(3, "org.234.KW.ILR.ILE")
    db = _Db(SimpleNamespace(path="org.234.KW.OSR.GRP"))
    payload = broadcasts.BroadcastCreate(
        target_level="group",
        target_path="org.234.KW.OSR.GRP",
        title="Test",
        content="Test message",
    )
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(broadcasts.create_broadcast(payload, db, user))
    assert exc_info.value.status_code == 403
    assert db.added is None


def test_group_broadcast_can_target_its_own_group():
    path = "org.234.KW.ILR.ILE"
    user = _user(3, path)
    target = SimpleNamespace(path=path)
    db = _Db(target)
    payload = broadcasts.BroadcastCreate(
        target_level="group",
        target_path=path,
        audience="pastors",
        title="Workers meeting",
        content="Meeting at 4pm",
    )
    result = asyncio.run(broadcasts.create_broadcast(payload, db, user))
    assert result.path == path
    assert result.audience == "pastors"
    assert db.added is result


def test_broadcast_response_serializes_model_path_as_target_path():
    row = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        target_level="group",
        path="org.234.KW.ILR.ILE",
        audience="all_users",
        title="Notice",
        content="Text",
        priority="normal",
        sender_role_score="3",
        sent_at="2026-11-05T10:00:00Z",
        recipient_count=None,
    )
    model = broadcasts.BroadcastResponse.model_validate(row)
    assert model.target_path == row.path
