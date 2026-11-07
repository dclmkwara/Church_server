import asyncio
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes import analytics
from app.services.analytics.program_occurrences import get_program_occurrences


class EmptyResult:
    def all(self):
        return []


class EmptyDb:
    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return EmptyResult()


def test_occurrence_endpoint_rejects_reversed_date_range(monkeypatch):
    monkeypatch.setattr(analytics.deps, "resolve_scope_path", lambda user, requested: "org.234.kw")
    with pytest.raises(HTTPException) as error:
        asyncio.run(analytics.read_program_occurrences(
            scope_path=None, domain=None, program_type=None, program_level=None,
            event_id=None, campaign_id=None, date_from=date(2026, 11, 2),
            date_to=date(2026, 11, 1), include_pending=False,
            db=EmptyDb(), current_user=SimpleNamespace(),
        ))
    assert error.value.status_code == 400
    assert "date_from" in error.value.detail


def test_occurrence_endpoint_validates_program_level_before_query(monkeypatch):
    monkeypatch.setattr(analytics.deps, "resolve_scope_path", lambda user, requested: "org.234.kw")
    db = EmptyDb()
    with pytest.raises(HTTPException) as error:
        asyncio.run(analytics.read_program_occurrences(
            scope_path=None, domain=None, program_type=None, program_level="country",
            event_id=None, campaign_id=None, date_from=None, date_to=None,
            include_pending=True, db=db, current_user=SimpleNamespace(),
        ))
    assert error.value.status_code == 400
    assert db.statements == []


def test_occurrence_endpoint_returns_empty_as_no_occurrence_not_zero_population(monkeypatch):
    monkeypatch.setattr(analytics.deps, "resolve_scope_path", lambda user, requested: "org.234.kw")
    db = EmptyDb()
    result = asyncio.run(analytics.read_program_occurrences(
        scope_path=None, domain="retreat", program_type=None, program_level="region",
        event_id=None, campaign_id=None, date_from=None, date_to=None,
        include_pending=False, db=db, current_user=SimpleNamespace(),
    ))
    assert result == {"scope_path": "org.234.kw", "include_pending": False, "occurrences": []}
    assert len(db.statements) == 1


class RowsResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class SequencedDb:
    def __init__(self, results):
        self.results = iter(results)

    async def execute(self, _statement):
        return RowsResult(next(self.results))


def test_occurrences_keep_each_session_separate_and_preserve_reported_zero():
    campaign = SimpleNamespace(title="Easter Retreat", start_date=date(2026, 4, 2), event_mode="retreat")
    event_a = SimpleNamespace(
        id="event-a", campaign_id="campaign-a", event_mode="retreat", date=date(2026, 4, 2),
        campaign=campaign, title="Bible Study", reporting_scope="region", path="org.234.kw.region",
        alpha_location_id=None, is_alpha_event=False, approval_status="approved",
    )
    event_b = SimpleNamespace(
        id="event-b", campaign_id="campaign-a", event_mode="retreat", date=date(2026, 4, 3),
        campaign=campaign, title="Faith Clinic", reporting_scope="region", path="org.234.kw.region",
        alpha_location_id=None, is_alpha_event=False, approval_status="approved",
    )
    program_type = SimpleNamespace(name="Bible Study", slug="bible-study")
    domain = SimpleNamespace(name="Retreat", slug="retreat")
    count_row = SimpleNamespace(
        event_id="event-a", source_role="regular", approved_total=0, pending_total=0,
        returned_rows=0, approved_rows=1, pending_rows=0, counted_total=0, row_count=1,
    )
    location_row = SimpleNamespace(
        event_id="event-a", location_id="location-a", location_name="Test Location",
        path="org.234.kw.region.group.location", source_role="regular", approved_total=0,
        pending_total=0, row_count=1,
    )
    convert_row = SimpleNamespace(event_id="event-a", record_type="convert", source_role="satellite", total=2)
    db = SequencedDb([
        [(event_a, program_type, domain), (event_b, SimpleNamespace(name="Faith Clinic", slug="faith-clinic"), domain)],
        [count_row], [location_row], [convert_row],
    ])

    result = asyncio.run(get_program_occurrences(db, scope_path="org.234.kw", include_pending=False))
    first, second = result["occurrences"]
    assert first["day_number"] == 1
    assert first["counted_population"] == 0
    assert first["report_state"] == "counted"
    assert first["converts"] == 2
    assert second["day_number"] == 2
    assert second["report_state"] == "no_report"
    assert second["counted_population"] == 0


def test_convert_record_without_population_count_is_still_reported():
    campaign = SimpleNamespace(title="Crusade", start_date=date(2026, 4, 2), event_mode="crusade")
    event = SimpleNamespace(
        id="event-a", campaign_id="campaign-a", event_mode="crusade", date=date(2026, 4, 2),
        campaign=campaign, title="Crusade Evening", reporting_scope="state", path="org.234.kw",
        alpha_location_id=None, is_alpha_event=False, approval_status="approved",
    )
    program_type = SimpleNamespace(name="Crusade Evening", slug="crusade-evening")
    domain = SimpleNamespace(name="Global Crusade", slug="global-crusade")
    convert_row = SimpleNamespace(event_id="event-a", record_type="convert", source_role="satellite", total=7)
    db = SequencedDb([[(event, program_type, domain)], [], [], [convert_row]])

    result = asyncio.run(get_program_occurrences(db, scope_path="org.234.kw"))
    occurrence = result["occurrences"][0]
    assert occurrence["counted_population"] == 0
    assert occurrence["converts"] == 7
    assert occurrence["record_state"] == "reported"
