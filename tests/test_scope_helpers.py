import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import deps
from app.db.filters import ltree_column, ltree_subpath, scope_filter
from app.models.attendance import WorkerAttendance
from app.models.programs import ProgramEvent
from app.schemas.user import UserResponse


def test_path_in_scope_allows_descendants():
    assert deps.path_in_scope("org.234.KW", "org.234.KW.ILR.ILE.003")
    assert deps.path_in_scope("org.234.KW", "org.234.KW")


def test_path_in_scope_rejects_siblings():
    assert not deps.path_in_scope("org.234.KW", "org.234.LA")


def test_resolve_scope_path_rejects_escalation():
    current_user = SimpleNamespace(path="org.234.KW.ILR")

    with pytest.raises(HTTPException):
        deps.resolve_scope_path(current_user, "org.234")


def test_resolve_scope_path_accepts_descendant_scope():
    current_user = SimpleNamespace(path="org.234.KW")

    resolved = deps.resolve_scope_path(current_user, "org.234.KW.ILR")

    assert resolved == "org.234.KW.ILR"


def test_user_response_serializes_uuid_location_id():
    location_id = uuid4()

    response = UserResponse.model_validate(
        {
            "email": "samuel.adebayo@admin.dclm.ng",
            "is_active": True,
            "user_id": uuid4(),
            "worker_id": uuid4(),
            "location_id": location_id,
            "name": "Pastor Samuel Adebayo",
            "phone": "09029952120",
            "created_at": "2026-05-03T12:00:00Z",
            "roles": [],
            "approval_status": "approved",
            "path": "org.234.KW.ILR.ILE.003",
        }
    )

    assert response.location_id == str(location_id)


def test_scope_filter_qualifies_path_columns_in_joins():
    stmt = (
        select(WorkerAttendance.id)
        .select_from(WorkerAttendance)
        .join(ProgramEvent, ProgramEvent.id == WorkerAttendance.event_id)
        .where(scope_filter(WorkerAttendance.path, "org.234.KW.ILR.ILE.003"))
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "worker_attendance.path" in compiled


def test_ltree_column_qualifies_grouping_columns_in_joins():
    stmt = (
        select(ltree_subpath(WorkerAttendance.path, 6))
        .select_from(WorkerAttendance)
        .join(ProgramEvent, ProgramEvent.id == WorkerAttendance.event_id)
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "worker_attendance.path" in compiled
    assert "subpath(CAST(worker_attendance.path AS LTREE), 0, 6)" in compiled
