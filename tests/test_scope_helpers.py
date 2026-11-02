import os
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api import deps
from app.db.filters import (
    ltree_column,
    ltree_subpath,
    reset_scope_context,
    scope_filter,
    scope_or_ancestor_filter,
    set_scope_context,
)
from app.models.attendance import WorkerAttendance
from app.models.programs import ProgramEvent
from app.schemas.user import UserResponse


def test_path_in_scope_allows_descendants():
    assert deps.path_in_scope("org.234.KW", "org.234.KW.ILR.ILE.003")
    assert deps.path_in_scope("org.234.KW", "org.234.KW")


def test_path_in_scope_rejects_siblings():
    assert not deps.path_in_scope("org.234.KW", "org.234.LA")


def test_resolve_scope_path_rejects_escalation():
    current_user = SimpleNamespace(path="org.234.KW.ILR", roles=[])

    with pytest.raises(HTTPException):
        deps.resolve_scope_path(current_user, "org.234")


def test_resolve_scope_path_accepts_descendant_scope():
    current_user = SimpleNamespace(path="org.234.KW", roles=[])

    resolved = deps.resolve_scope_path(current_user, "org.234.KW.ILR")

    assert resolved == "org.234.KW.ILR"


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1, "org.234.KW.ILR.ILE.003"),
        (3, "org.234.KW.ILR.ILE.003"),
        (4, "org.234.KW.ILR.ILE"),
        (5, "org.234.KW.ILR"),
        (6, "org.234.KW"),
        (7, "org.234"),
        (8, "org"),  # Current schema has no continent node; remains a known limitation.
        (9, "org"),
    ],
)
def test_effective_scope_uses_highest_role_and_home_path(score, expected):
    current_user = SimpleNamespace(
        path="org.234.KW.ILR.ILE.003",
        roles=[SimpleNamespace(score_value=2), SimpleNamespace(score_value=score)],
    )

    assert deps.effective_scope_path(current_user) == expected


def test_effective_scope_rejects_invalid_home_path():
    current_user = SimpleNamespace(path="org.234.KW;drop", roles=[])

    with pytest.raises(HTTPException) as exc_info:
        deps.effective_scope_path(current_user)

    assert exc_info.value.status_code == 403


def test_ensure_path_in_scope_uses_role_scope_not_home_path():
    current_user = SimpleNamespace(
        path="org.234.KW.ILR.ILE.003",
        roles=[SimpleNamespace(score_value=4)],
    )

    deps.ensure_path_in_scope(current_user, "org.234.KW.ILR.ILE.009")

    with pytest.raises(HTTPException):
        deps.ensure_path_in_scope(current_user, "org.234.KW.ILR.ILE2.009")


def test_level_eight_object_scope_is_limited_to_authorized_nations():
    current_user = SimpleNamespace(
        path="org.AFR1.KW.ILR.ILE.003",
        roles=[SimpleNamespace(score_value=8)],
        _authorized_nation_paths=("org.AFR1", "org.AFR2"),
    )

    deps.ensure_path_in_scope(current_user, "org.AFR2.LA.REG.GRP.LOC.001")
    with pytest.raises(HTTPException):
        deps.ensure_path_in_scope(current_user, "org.EUR1.FR.PAR.GRP.LOC.001")


def test_level_eight_scope_condition_compiles_continent_filter():
    current_user = SimpleNamespace(
        path="org.AFR1.KW.ILR.ILE.003",
        roles=[SimpleNamespace(score_value=8)],
        _authorized_nation_paths=("org.AFR1", "org.AFR2"),
    )

    stmt = select(WorkerAttendance.id).where(
        deps.scope_condition(WorkerAttendance.path, current_user)
    )
    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "subpath(CAST(worker_attendance.path AS LTREE)" in compiled
    assert " IN (__[POSTCOMPILE_" in compiled
    scope_values = stmt.compile(dialect=postgresql.dialect()).params.values()
    assert ["org.AFR1", "org.AFR2"] in scope_values


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


def test_level_eight_scope_filter_applies_continent_nations_and_fails_closed():
    token = set_scope_context(8, ("org.AFR1", "org.AFR2"))
    try:
        statement = select(WorkerAttendance.id).where(
            scope_filter(WorkerAttendance.path, "org")
        )
        compiled = statement.compile(dialect=postgresql.dialect())
        assert "subpath(CAST(worker_attendance.path AS LTREE)" in str(compiled)
        assert "org.AFR1" in repr(compiled.params.values())
        assert "org.AFR2" in repr(compiled.params.values())
    finally:
        reset_scope_context(token)


def test_level_eight_campaign_scope_does_not_expand_to_global_ancestors():
    token = set_scope_context(8, ("org.AFR1",))
    try:
        compiled = select(WorkerAttendance.id).where(
            scope_or_ancestor_filter(WorkerAttendance.path, "org")
        ).compile(dialect=postgresql.dialect())
        sql = str(compiled).lower()
        assert " or " not in sql
        assert "subpath" in sql
    finally:
        reset_scope_context(token)

    token = set_scope_context(8, ())
    try:
        compiled = select(WorkerAttendance.id).where(
            scope_filter(WorkerAttendance.path, "org")
        ).compile(dialect=postgresql.dialect())
        assert False in compiled.params.values()
    finally:
        reset_scope_context(token)


def test_ltree_column_qualifies_grouping_columns_in_joins():
    stmt = (
        select(ltree_subpath(WorkerAttendance.path, 6))
        .select_from(WorkerAttendance)
        .join(ProgramEvent, ProgramEvent.id == WorkerAttendance.event_id)
    )

    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "worker_attendance.path" in compiled
    assert "subpath(CAST(worker_attendance.path AS LTREE), 0, 6)" in compiled
