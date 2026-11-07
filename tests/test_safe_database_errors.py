import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

from app.db import session as db_session
from scripts import db_connect_check


class _LeakyDriverError(Exception):
    pass


class _FailingSessionContext:
    async def __aenter__(self):
        raise _LeakyDriverError("connection to postgresql://admin:VERY_SECRET@db.example.test/church failed")

    async def __aexit__(self, *_args):
        return False


def test_database_connection_failure_logs_type_without_connection_details(monkeypatch, caplog):
    monkeypatch.setattr(db_session, "AsyncSessionLocal", _FailingSessionContext)
    caplog.set_level(logging.ERROR)

    connected = asyncio.run(db_session.test_connection())

    assert connected is False
    assert "_LeakyDriverError" in caplog.text
    assert "VERY_SECRET" not in caplog.text
    assert "postgresql://" not in caplog.text
    assert "db.example.test" not in caplog.text


def test_database_check_script_redacts_driver_exception(capsys, monkeypatch):
    async def fail_connect(*_args, **_kwargs):
        raise _LeakyDriverError("postgresql://admin:VERY_SECRET@db.example.test/church failed")

    monkeypatch.setattr(db_connect_check.asyncpg, "connect", fail_connect)
    asyncio.run(db_connect_check._check(
        "postgresql://admin:VERY_SECRET@db.example.test/church", "TEST",
    ))
    output = capsys.readouterr().out
    assert "_LeakyDriverError" in output
    assert "details redacted" in output
    assert "VERY_SECRET" not in output
    assert "postgresql://" not in output
