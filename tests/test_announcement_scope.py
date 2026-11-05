import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.v1.routes import announcements


def _user(score=5):
    return SimpleNamespace(
        path="org.234.KW.ILR.ILE.003",
        roles=[SimpleNamespace(score_value=score)],
    )


def test_announcement_lookup_rejects_resource_outside_effective_scope(monkeypatch):
    announcement_id = uuid4()
    announcement = SimpleNamespace(path="org.234.KW.OSR.GRP.LOC.001")

    async def fake_get_by_id(db, requested_id):
        assert requested_id == announcement_id
        return announcement

    monkeypatch.setattr(announcements.crud_announcement, "get_by_id", fake_get_by_id)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            announcements._get_announcement_in_scope(
                object(), announcement_id, _user(score=4)
            )
        )

    assert exc_info.value.status_code == 403


def test_announcement_lookup_allows_resource_in_role_scope(monkeypatch):
    announcement_id = uuid4()
    announcement = SimpleNamespace(path="org.234.KW.ILR.ILE.003")

    async def fake_get_by_id(db, requested_id):
        return announcement

    monkeypatch.setattr(announcements.crud_announcement, "get_by_id", fake_get_by_id)

    result = asyncio.run(
        announcements._get_announcement_in_scope(
            object(), announcement_id, _user(score=5)
        )
    )

    assert result is announcement
