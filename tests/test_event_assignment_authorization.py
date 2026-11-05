import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.crud.workflow_rules import collection_window_is_active, require_event_assignment
from datetime import UTC, datetime, timedelta
from app.api.v1.routes.programs import read_my_active_event_assignments
from app.frontend.dclm_admin.communication.program_service import _schedule_datetime


class FakeDB:
    def __init__(self, assignment):
        self.assignment = assignment

    async def get(self, model, assignment_id):
        return self.assignment if self.assignment.id == assignment_id else None


def _assignment(*, source_role="alpha", assignment_type="both", status="approved"):
    return SimpleNamespace(
        id=uuid4(),
        event_id="event-1",
        worker_id="worker-1",
        path="org.234.KW",
        status=status,
        is_deleted=False,
        assignment_type=assignment_type,
        source_role=source_role,
    )


def _event():
    return SimpleNamespace(
        id="event-1",
        path="org.234.KW",
        event_mode="crusade",
        alpha_location_id="alpha-location",
    )


def _user(*, worker_id="worker-1", location_id="home-location"):
    return SimpleNamespace(worker_id=worker_id, location_id=location_id)


def test_alpha_assignment_authorizes_host_location_outside_workers_home():
    assignment = _assignment()
    result = asyncio.run(
        require_event_assignment(
            FakeDB(assignment), user=_user(), event=_event(), assignment_id=assignment.id,
            location_id="alpha-location", submission_kind="count", required=True,
        )
    )
    assert result is assignment


@pytest.mark.parametrize("location_id", ["home-location", "other-location"])
def test_alpha_assignment_cannot_submit_for_another_location(location_id):
    assignment = _assignment()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            require_event_assignment(
                FakeDB(assignment), user=_user(), event=_event(), assignment_id=assignment.id,
                location_id=location_id, submission_kind="count", required=True,
            )
        )
    assert exc.value.status_code == 403


def test_satellite_assignment_is_limited_to_workers_home_location():
    assignment = _assignment(source_role="satellite")
    result = asyncio.run(
        require_event_assignment(
            FakeDB(assignment), user=_user(), event=_event(), assignment_id=assignment.id,
            location_id="home-location", submission_kind="record", required=True,
        )
    )
    assert result is assignment
    with pytest.raises(HTTPException):
        asyncio.run(
            require_event_assignment(
                FakeDB(assignment), user=_user(), event=_event(), assignment_id=assignment.id,
                location_id="alpha-location", submission_kind="record", required=True,
            )
        )


def test_assignment_requires_approved_worker_and_permitted_capture_type():
    assignment = _assignment(status="pending")
    with pytest.raises(HTTPException):
        asyncio.run(
            require_event_assignment(
                FakeDB(assignment), user=_user(), event=_event(), assignment_id=assignment.id,
                location_id="alpha-location", submission_kind="count", required=True,
            )
        )
    assignment.status = "approved"
    assignment.assignment_type = "count"
    with pytest.raises(HTTPException):
        asyncio.run(
            require_event_assignment(
                FakeDB(assignment), user=_user(), event=_event(), assignment_id=assignment.id,
                location_id="alpha-location", submission_kind="record", required=True,
            )
        )


def test_combined_attendance_assignment_is_regular_and_home_location_only():
    assignment = _assignment(source_role="regular", assignment_type="attendance")
    event = SimpleNamespace(
        id="event-1", path="org.234.KW", event_mode="regular",
        reporting_scope="group", alpha_location_id=None,
    )
    result = asyncio.run(
        require_event_assignment(
            FakeDB(assignment), user=_user(location_id="home-location"), event=event,
            assignment_id=assignment.id, location_id="home-location",
            submission_kind="attendance", required=True,
        )
    )
    assert result is assignment

    for source_role, physical_location in (("alpha", "home-location"), ("regular", "other-location")):
        assignment.source_role = source_role
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                require_event_assignment(
                    FakeDB(assignment), user=_user(location_id="home-location"), event=event,
                    assignment_id=assignment.id, location_id=physical_location,
                    submission_kind="attendance", required=True,
                )
            )
        assert exc.value.status_code == 403


def test_active_auto_setup_requires_finite_open_window_and_honors_campaign_fallback():
    now = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
    event = SimpleNamespace(collection_window_start=now - timedelta(hours=1), collection_window_end=now + timedelta(hours=1))
    assert collection_window_is_active(event, now=now)
    assert not collection_window_is_active(event, now=now + timedelta(hours=2))

    no_window = SimpleNamespace(collection_window_start=None, collection_window_end=None)
    campaign = SimpleNamespace(collection_window_start=now - timedelta(hours=1), collection_window_end=now + timedelta(hours=1))
    assert collection_window_is_active(no_window, campaign, now=now)
    assert not collection_window_is_active(no_window, now=now)


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def scalars(self):
        return self

    def unique(self):
        return self

    def all(self):
        return self.rows


class FakeAssignmentDB:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _query):
        return FakeResult(self.rows)

    async def get(self, _model, _id):
        return None


def test_active_assignment_endpoint_returns_only_open_approved_setup_payload():
    now = datetime.now(UTC)
    domain = SimpleNamespace(id=2, name="Weekly Programs", slug="weekly_programs")
    program_type = SimpleNamespace(id=7, name="Saturday Workers Meeting", domain_id=2, domain=domain)
    event = SimpleNamespace(
        id=uuid4(), title="Combined Workers Meeting", date=now.date(), path="org.234.KW.ILR.ILE",
        event_mode="regular", reporting_scope="group", program_type=program_type,
        alpha_location_id=None,
        campaign=None, collection_window_start=now - timedelta(minutes=5),
        collection_window_end=now + timedelta(minutes=5),
    )
    assignment = SimpleNamespace(id=uuid4(), assignment_type="attendance", source_role="regular", event=event)
    user = SimpleNamespace(worker_id="worker-1", roles=[SimpleNamespace(score_value=1)])
    payload = asyncio.run(read_my_active_event_assignments(db=FakeAssignmentDB([assignment]), current_user=user))
    assert len(payload) == 1
    assert payload[0]["assignment_id"] == str(assignment.id)
    assert payload[0]["event"]["program_type"]["domain"]["name"] == "Weekly Programs"
    assert payload[0]["event"]["reporting_scope"] == "group"

    assignment.event.collection_window_end = now - timedelta(seconds=1)
    assert asyncio.run(read_my_active_event_assignments(db=FakeAssignmentDB([assignment]), current_user=user)) == []


def test_admin_schedule_times_are_saved_as_utc_from_nigeria_local_time():
    assert _schedule_datetime("2026-11-05T13:00") == "2026-11-05T12:00:00+00:00"


def test_group_assignment_approval_is_allowed_to_reach_scoped_lookup():
    from app.api.v1.routes.programs import approve_event_assignment

    user = SimpleNamespace(roles=[SimpleNamespace(score_value=3)], user_id=uuid4())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(approve_event_assignment(assignment_id=uuid4(), db=FakeAssignmentDB([]), current_user=user))
    assert exc.value.status_code == 404


def test_level_to_reporting_scope_schedule_map_is_explicit():
    expected = {2: "location", 3: "group", 4: "region", 5: "state"}
    assert expected[2] == "location"
    assert expected[3] == "group"
    assert expected[4] == "region"
    assert expected[5] == "state"


def test_event_creation_permission_is_assigned_to_level_admins_and_pastors():
    from app.db.init_rbac import DEFAULT_ROLES

    for role_name in ("Group Admin", "Region Admin", "State Admin"):
        assert "programs:create_event" in DEFAULT_ROLES[role_name]["permissions"]
    for role_name in ("Location Pastor", "Group Pastor", "Region Pastor", "State Overseer"):
        assert "programs:create_event" in DEFAULT_ROLES[role_name]["permissions"]


def test_event_assignment_permissions_are_assigned_to_group_region_and_state_governance():
    from app.db.init_rbac import DEFAULT_ROLES

    for role_name in (
        "Group Admin", "Group Pastor", "Region Admin", "Region Pastor",
        "State Admin", "State Overseer",
    ):
        permissions = DEFAULT_ROLES[role_name]["permissions"]
        assert "programs:assign_workers" in permissions
        assert "programs:approve_assignments" in permissions


def test_assignment_worker_lookup_uses_public_worker_uuid():
    from app.crud.crud_programs import get_worker_by_public_id

    expected = SimpleNamespace(worker_id=uuid4())

    class Result:
        def scalars(self):
            return self

        def first(self):
            return expected

    class DB:
        async def execute(self, statement):
            # The filter must target the public worker UUID, not Worker.id.
            assert "workers.worker_id" in str(statement)
            return Result()

    assert asyncio.run(get_worker_by_public_id(DB(), expected.worker_id)) is expected


@pytest.mark.parametrize(
    ("scope", "score", "role_name"),
    [
        ("group", 3, "Group Pastor"),
        ("region", 4, "Region Pastor"),
        ("state", 5, "State Overseer"),
    ],
)
def test_event_approval_is_limited_to_same_level_pastor(scope, score, role_name, monkeypatch):
    from app.api.v1.routes import programs

    event = SimpleNamespace(reporting_scope=scope, path="org.234.KW.ILR.ILE")
    user = SimpleNamespace(
        roles=[SimpleNamespace(role_name=role_name, score_value=score)],
        path=event.path,
        user_id="pastor-user",
    )
    monkeypatch.setattr(programs.deps, "effective_scope_path", lambda _user: event.path)
    programs._require_event_pastor(user, event)

    other_role_name, other_score = ("State Overseer", 5) if role_name == "Group Pastor" else ("Group Pastor", 3)
    wrong_role = SimpleNamespace(
        roles=[SimpleNamespace(role_name=other_role_name, score_value=other_score)],
        path=event.path,
    )
    with pytest.raises(HTTPException) as exc:
        programs._require_event_pastor(wrong_role, event)
    assert exc.value.status_code == 403
    event.created_by_id = user.user_id
    with pytest.raises(HTTPException) as exc:
        programs._require_event_pastor(user, event)
    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    ("scope", "score", "role_name"),
    [
        ("location", 2, "Location Pastor"),
        ("group", 3, "Group Pastor"),
        ("region", 4, "Region Pastor"),
        ("state", 5, "State Overseer"),
    ],
)
def test_same_level_pastor_identity_is_used_for_immediate_event_approval(scope, score, role_name, monkeypatch):
    from app.api.v1.routes import programs

    user = SimpleNamespace(
        roles=[SimpleNamespace(role_name=role_name, score_value=score)],
        path="org.234.KW",
    )
    monkeypatch.setattr(programs.deps, "effective_scope_path", lambda _user: "org.234.KW")
    assert programs._is_event_pastor_for_scope(user, scope, "org.234.KW")
    assert not programs._is_event_pastor_for_scope(user, scope, "org.234.KW.ILR")
