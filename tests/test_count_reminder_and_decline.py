import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from sqlalchemy.dialects import postgresql

from app.api import deps
from app.api.v1.routes import counts as count_routes
from app.frontend.dclm_admin.routes.analytics_dashboard import _pooled_decline
from app.models.counts import CountReminderRecipient
from app.services.analytics.program_config import ATTENTION_DECLINE_PCT
from app.services.notification_service import NotificationService


def test_decline_compares_only_locations_counted_in_both_weeks():
    previous = {"location_totals": {f"loc-{i}": 100 for i in range(5)} | {"late": 100}}
    current = {"location_totals": {f"loc-{i}": 100 for i in range(5)}}

    comparable, drop = _pooled_decline(previous, current)

    assert comparable == 5
    assert drop == 0  # the late reporter is excluded from both pooled totals


def test_pooled_decline_is_not_the_mean_of_location_percentages():
    previous = {"location_totals": {"large": 900, "small": 100, "a": 0, "b": 0, "c": 0}}
    current = {"location_totals": {"large": 720, "small": 110, "a": 0, "b": 0, "c": 0}}

    comparable, drop = _pooled_decline(previous, current)

    assert comparable == 5
    assert drop == pytest.approx(17)


def test_decline_threshold_is_a_named_fifteen_percent_constant():
    assert ATTENTION_DECLINE_PCT == 15


def test_reminder_recipient_query_limits_role_and_exact_location():
    location = SimpleNamespace(path="org.234.kw.region.group.location")
    statement = count_routes._count_reminder_recipient_query(location)
    compiled = statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    sql = str(compiled)

    assert "users.path = CAST('org.234.kw.region.group.location' AS LTREE)" in sql
    assert "Location Usher" in sql and "Location Pastor" in sql
    assert "Group Pastor" not in sql and "Region Pastor" not in sql and "State Overseer" not in sql
    assert "users.is_active IS true" in sql
    assert "users.approval_status = 'approved'" in sql


def test_reminder_route_requires_review_permission():
    route = next(
        route for route in count_routes.router.routes
        if isinstance(route, APIRoute) and route.path.endswith("/review/remind")
    )
    required = {
        getattr(dependency.call, "required_permission", None)
        for dependency in route.dependant.dependencies
    }
    assert "counts:review" in required


def test_reminder_sends_and_audits_only_recipient_users(monkeypatch):
    location_id, usher_id, pastor_id, sender_id = (uuid4() for _ in range(4))
    location = SimpleNamespace(location_id=str(location_id), path="org.234.kw.region.group.location")
    program_type = SimpleNamespace(id=19, slug="sunday_worship_service")
    sunday = date(2026, 11, 1)
    started = datetime.now(timezone.utc)

    class Result:
        def __init__(self, value=None, rows=None):
            self.value, self.rows = value, rows

        def scalar_one_or_none(self):
            return self.value

        def scalars(self):
            return self

        def all(self):
            return self.rows or []

    class Session:
        def __init__(self):
            self.calls = 0
            self.added = []

        async def execute(self, statement):
            self.calls += 1
            if self.calls == 1:
                return Result(location)
            if self.calls in {2, 3, 4}:
                return Result(None)
            # Recipient SQL is restricted to the two permitted role names and
            # the exact path; the database returns only those matched users.
            sql = str(statement.compile(dialect=postgresql.dialect()))
            assert "Group Pastor" not in sql and "Region Pastor" not in sql
            return Result(rows=[usher_id, pastor_id])

        def add_all(self, rows):
            self.added.extend(rows)

        async def commit(self):
            pass

        async def get(self, model, key):
            return program_type

    session = Session()
    monkeypatch.setattr(deps, "highest_role_score", lambda user: 4)
    scoped = []
    monkeypatch.setattr(deps, "ensure_path_in_scope", lambda user, path, **_kw: scoped.append(path))

    response = asyncio.run(count_routes.remind_unreported_location(
        count_routes.CountReminder(location_id=location_id, program_type_id=19, occurrence_date=sunday),
        db=session,
        current_user=SimpleNamespace(user_id=sender_id),
    ))

    assert response["recipient_count"] == 2
    assert {row.recipient_user_id for row in session.added} == {usher_id, pastor_id}
    assert all(isinstance(row, CountReminderRecipient) for row in session.added)
    assert all(row.sent_by_id == sender_id and row.location_id == str(location_id) for row in session.added)
    assert all(row.occurrence_date == sunday and started <= row.sent_at <= datetime.now(timezone.utc) for row in session.added)
    assert scoped == [location.path]


def test_reminder_blocks_duplicate_within_twenty_four_hours(monkeypatch):
    location_id = uuid4()
    location = SimpleNamespace(location_id=str(location_id), path="org.234.kw.region.group.location")
    program_type = SimpleNamespace(id=19, slug="sunday_worship_service")
    now = datetime.now(timezone.utc)

    class Result:
        def __init__(self, value=None):
            self.value = value

        def scalar_one_or_none(self):
            return self.value

    class Session:
        calls = 0

        async def execute(self, _statement):
            self.calls += 1
            if self.calls == 1:
                return Result(location)
            if self.calls in {2, 3}:
                return Result(None)
            return Result(now - timedelta(hours=3))

        async def get(self, model, key):
            return program_type

    monkeypatch.setattr(deps, "highest_role_score", lambda user: 4)
    monkeypatch.setattr(deps, "ensure_path_in_scope", lambda *_a, **_kw: None)
    with pytest.raises(HTTPException) as error:
        asyncio.run(count_routes.remind_unreported_location(
            count_routes.CountReminder(location_id=location_id, program_type_id=19, occurrence_date=date(2026, 11, 1)),
            db=Session(), current_user=SimpleNamespace(user_id=uuid4()),
        ))
    assert error.value.status_code == 429
    assert error.value.detail == "Reminded 3h ago"


def test_reminder_refuses_out_of_scope_location(monkeypatch):
    location_id = uuid4()
    location = SimpleNamespace(location_id=str(location_id), path="org.234.kw.other")

    class Result:
        def scalar_one_or_none(self):
            return location

    class Session:
        async def execute(self, _statement):
            return Result()

    def refuse(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="Location outside your jurisdiction")

    monkeypatch.setattr(deps, "highest_role_score", lambda user: 4)
    monkeypatch.setattr(deps, "ensure_path_in_scope", refuse)
    with pytest.raises(HTTPException) as error:
        asyncio.run(count_routes.remind_unreported_location(
            count_routes.CountReminder(location_id=location_id, program_type_id=19, occurrence_date=date(2026, 11, 1)),
            db=Session(), current_user=SimpleNamespace(user_id=uuid4()),
        ))
    assert error.value.status_code == 403


def test_reminder_notification_history_is_filtered_by_recipient_user(monkeypatch):
    user_id = uuid4()
    statements = []

    class Result:
        def all(self):
            return []

        def scalars(self):
            return self

    class Session:
        async def execute(self, statement):
            statements.append(statement)
            return Result()

    monkeypatch.setattr(NotificationService, "poll_new_data", AsyncMock(return_value={}))
    asyncio.run(NotificationService.history(
        Session(), scope_path="org.234.kw", user_id=str(user_id),
        since=datetime(2026, 11, 1, tzinfo=timezone.utc),
    ))
    reminder_sql = str(statements[0].compile(dialect=postgresql.dialect()))
    assert "count_reminder_recipients.recipient_user_id" in reminder_sql
    assert str(user_id) in str(statements[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
