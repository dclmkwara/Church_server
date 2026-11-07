import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.routes.dashboard import (
    ExpectedPopulationVersionCreate,
    _is_state_overseer,
    create_expected_population_version,
    list_expected_population,
)
from app.models.audit import AuditLog
from app.models.expected_population import LocationExpectedPopulation
from app.services.analytics.sunday_worship import _build_overview


def _estimate(value: int, effective_from: date, created_at: datetime | None = None):
    return SimpleNamespace(
        expected_value=value,
        effective_from=effective_from,
        created_at=created_at or datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _count(location_id: str, total: int, status: str = "approved"):
    return SimpleNamespace(
        id=f"count-{location_id}", event_id=None, location_id=location_id,
        status=status, total=total, adult_male=total, adult_female=0,
        youth_male=0, youth_female=0, boys=0, girls=0,
    )


def _overview(totals, estimates, *, include_pending=False):
    locations = [SimpleNamespace(location_id=key, path=f"org.234.KW.R.G.{key}") for key in totals]
    return _build_overview(
        scope_path="org.234.KW.R.G",
        occurrence_date=date(2026, 11, 1),
        now=datetime(2026, 11, 2, tzinfo=timezone.utc),
        locations=locations,
        events=[],
        count_rows=[_count(key, value) for key, value in totals.items()],
        include_pending=include_pending,
        estimates_by_location=estimates,
    )


def test_expected_population_is_pooled_not_mean_of_location_percentages():
    result = _overview(
        {"a": 80, "b": 300},
        {"a": [_estimate(100, date(2026, 1, 1))], "b": [_estimate(200, date(2026, 1, 1))]},
    )
    assert result["expected_population_counted_total"] == 380
    assert result["expected_population_total"] == 300
    assert result["expected_population_percent"] == 126.7
    assert result["expected_population_percent"] != (80 + 150) / 2


def test_expected_population_percentage_is_not_capped_above_100():
    result = _overview({"a": 300}, {"a": [_estimate(100, date(2026, 1, 1))]})
    assert result["expected_population_percent"] == 300


def test_no_estimate_locations_are_excluded_and_counted():
    result = _overview(
        {"a": 80, "b": 300, "c": 50},
        {"a": [_estimate(100, date(2026, 1, 1))], "b": [_estimate(200, date(2026, 1, 1))]},
    )
    assert result["expected_population_percent"] == 126.7
    assert result["expected_population_no_estimate_locations"] == 1
    assert result["expected_population_counted_locations"] == 2


def test_estimate_version_effective_date_is_applied_to_occurrence():
    result = _overview(
        {"a": 80},
        {"a": [
            _estimate(100, date(2026, 1, 1)),
            _estimate(200, date(2026, 12, 1)),
        ]},
    )
    assert result["location_expected_values"] == {"a": 100}
    assert result["expected_population_percent"] == 80


def test_combined_count_uses_sum_of_covered_location_estimates_once():
    locations = [
        SimpleNamespace(location_id="a", path="org.234.KW.R.G.001"),
        SimpleNamespace(location_id="b", path="org.234.KW.R.G.002"),
    ]
    event = SimpleNamespace(id="event-1", path="org.234.KW.R.G", reporting_scope="group")
    combined = _count("a", 250)
    combined.event_id = "event-1"
    result = _build_overview(
        scope_path="org.234.KW.R.G",
        occurrence_date=date(2026, 11, 1),
        now=datetime(2026, 11, 2, tzinfo=timezone.utc),
        locations=locations,
        events=[event],
        count_rows=[combined],
        include_pending=False,
        estimates_by_location={
            "a": [_estimate(100, date(2026, 1, 1))],
            "b": [_estimate(100, date(2026, 1, 1))],
        },
    )
    assert result["total"] == 250
    assert result["expected_population_counted_locations"] == 2
    assert result["expected_population_percent"] == 125


def test_only_state_overseer_role_can_manage_estimates():
    state_overseer = SimpleNamespace(roles=[SimpleNamespace(role_name="State Overseer", score_value=5)])
    state_admin = SimpleNamespace(roles=[SimpleNamespace(role_name="State Admin", score_value=5)])
    region_pastor = SimpleNamespace(roles=[SimpleNamespace(role_name="Region Pastor", score_value=4)])
    assert _is_state_overseer(state_overseer)
    assert not _is_state_overseer(state_admin)
    assert not _is_state_overseer(region_pastor)


class _FakeResult:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def scalar_one_or_none(self):
        return self.row

    def all(self):
        return self.rows


class _FakeSession:
    def __init__(self, location=None, rows=None):
        self.location = location
        self.rows = rows or []
        self.added = []
        self.commits = 0

    async def execute(self, _stmt):
        if self.rows:
            return _FakeResult(rows=self.rows)
        return _FakeResult(row=self.location)

    def add_all(self, items):
        self.added.extend(items)

    async def commit(self):
        self.commits += 1

    async def refresh(self, _item):
        return None


def test_estimate_change_appends_version_and_audit_record():
    location_id = str(uuid4())
    user_id = uuid4()
    location = SimpleNamespace(location_id=location_id, path="org.234.KW.R.G.L", is_active=True)
    user = SimpleNamespace(
        roles=[SimpleNamespace(role_name="State Overseer", score_value=5)],
        path="org.234.KW",
        user_id=user_id,
    )
    db = _FakeSession(location=location)
    payload = ExpectedPopulationVersionCreate(
        location_id=location_id, expected_value=250, effective_from=date(2026, 11, 8), note="Updated estimate",
    )
    asyncio.run(create_expected_population_version(payload, db=db, current_user=user))
    assert len([item for item in db.added if isinstance(item, LocationExpectedPopulation)]) == 1
    assert len([item for item in db.added if isinstance(item, AuditLog)]) == 1
    version = next(item for item in db.added if isinstance(item, LocationExpectedPopulation))
    assert version.expected_value == 250
    assert version.effective_from == date(2026, 11, 8)
    assert version.note == "Updated estimate"
    audit = next(item for item in db.added if isinstance(item, AuditLog))
    assert audit.action == "SET_LOCATION_EXPECTED_POPULATION"
    assert db.commits == 1


def test_estimate_change_rejects_state_admin_even_at_same_score():
    user = SimpleNamespace(
        roles=[SimpleNamespace(role_name="State Admin", score_value=5)],
        path="org.234.KW",
        user_id=uuid4(),
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(create_expected_population_version(
            ExpectedPopulationVersionCreate(location_id=uuid4(), expected_value=1, effective_from=date.today()),
            db=_FakeSession(), current_user=user,
        ))
    assert exc.value.status_code == 403


def test_history_api_preserves_all_versions_and_current_value():
    location = SimpleNamespace(location_id="loc-a", location_name="Location A", location_code="001", path="org.234.KW.R.G.L", is_active=True)
    older = SimpleNamespace(id=uuid4(), expected_value=100, effective_from=date(2026, 1, 1), set_by_id=uuid4(), note="First", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    newer = SimpleNamespace(id=uuid4(), expected_value=120, effective_from=date(2026, 6, 1), set_by_id=uuid4(), note="Revised", created_at=datetime(2026, 6, 1, tzinfo=timezone.utc))
    db = _FakeSession(rows=[(location, newer, "State Overseer"), (location, older, "State Overseer")])
    user = SimpleNamespace(roles=[SimpleNamespace(role_name="State Overseer", score_value=5)], path="org.234.KW")
    payload = asyncio.run(list_expected_population(
        as_of=date(2026, 11, 1), include_history=True, db=db, current_user=user,
    ))
    assert payload["locations"][0]["expected_value"] == 120
    assert len(payload["locations"][0]["history"]) == 2
    assert {row["expected_value"] for row in payload["locations"][0]["history"]} == {100, 120}
