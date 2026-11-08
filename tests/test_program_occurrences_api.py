import asyncio
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.routes import analytics
from app.services.analytics.program_occurrences import get_program_occurrences
from app.frontend.dclm_admin.routes.programs import _compare_common_reporters, _pool_session_rows


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
    assert result == {"scope_path": "org.234.kw", "include_pending": False, "scope_names": {}, "occurrences": []}
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
    campaign = SimpleNamespace(title="Easter Retreat", start_date=date(2026, 4, 2), event_mode="retreat", alpha_location_id=None)
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
        path="org.234.kw.region.group.location", program_scope_path="org.234.kw.region", source_role="regular", approved_total=0,
        pending_total=0, row_count=1, approved_rows=1, pending_rows=0, returned_rows=0,
    )
    convert_row = SimpleNamespace(event_id="event-a", record_type="convert", source_role="satellite", total=2)
    db = SequencedDb([
        [(event_a, program_type, domain), (event_b, SimpleNamespace(name="Faith Clinic", slug="faith-clinic"), domain)],
        [count_row], [location_row], [convert_row], [],
    ])

    result = asyncio.run(get_program_occurrences(db, scope_path="org.234.kw", include_pending=False))
    first, second = result["occurrences"]
    assert first["day_number"] == 1
    assert first["counted_population"] == 0
    assert first["report_state"] == "counted"
    assert first["converts"] == 2
    assert second["day_number"] == 2
    assert second["report_state"] in {"late", "missing"}
    assert second["counted_population"] == 0


def test_convert_record_without_population_count_is_still_reported():
    campaign = SimpleNamespace(title="Crusade", start_date=date(2026, 4, 2), event_mode="crusade", alpha_location_id="alpha-id")
    event = SimpleNamespace(
        id="event-a", campaign_id="campaign-a", event_mode="crusade", date=date(2026, 4, 2),
        campaign=campaign, title="Crusade Evening", reporting_scope="state", path="org.234.kw",
        alpha_location_id=None, is_alpha_event=False, approval_status="approved",
    )
    program_type = SimpleNamespace(name="Crusade Evening", slug="crusade-evening")
    domain = SimpleNamespace(name="Global Crusade", slug="global-crusade")
    convert_row = SimpleNamespace(event_id="event-a", record_type="convert", source_role="satellite", total=7)
    db = SequencedDb([[(event, program_type, domain)], [], [], [convert_row], [], []])

    result = asyncio.run(get_program_occurrences(db, scope_path="org.234.kw"))
    occurrence = result["occurrences"][0]
    assert occurrence["counted_population"] == 0
    assert occurrence["converts"] == 7
    assert occurrence["record_state"] == "reported"


def test_state_retreat_day_two_bible_study_pools_regions_and_pending_switch():
    campaign = SimpleNamespace(title="Easter Retreat 2026", start_date=date(2026, 4, 2), event_mode="retreat", alpha_location_id=None)
    ptype = SimpleNamespace(name="Bible Study", slug="bible-study")
    domain = SimpleNamespace(name="Retreat", slug="retreat")
    events = []
    details = []
    aggregate_counts = []
    for idx, region in enumerate(("EDR", "ILR", "ISR", "IWR", "OOR", "OFR", "OMR")):
        event = SimpleNamespace(
            id=f"event-{idx}", campaign_id="easter-2026", event_mode="regular",
            date=date(2026, 4, 3), campaign=campaign, title="Bible Study",
            reporting_scope="region", path=f"org.234.KW.{region}", alpha_location_id=None,
            is_alpha_event=False, approval_status="approved",
        )
        events.append((event, ptype, domain))
        is_pending = idx == 1
        count_total = 100 + idx * 10
        aggregate_counts.append(SimpleNamespace(
            event_id=event.id, source_role="regular", approved_total=0 if is_pending else count_total,
            pending_total=count_total if is_pending else 0, returned_rows=0,
            approved_rows=0 if is_pending else 1, pending_rows=1 if is_pending else 0,
            counted_total=count_total if not is_pending else 0, row_count=1,
        ))
        details.append(SimpleNamespace(
            event_id=event.id, location_id=f"location-{idx}", location_name=f"Camp {region}",
            path=f"org.234.KW.{region}.GRP.LOC", program_scope_path=f"org.234.KW.{region}",
            source_role="regular", approved_total=0 if is_pending else count_total,
            pending_total=count_total if is_pending else 0, row_count=1,
            approved_rows=0 if is_pending else 1, pending_rows=1 if is_pending else 0, returned_rows=0,
        ))
    db = SequencedDb([events, aggregate_counts, details, [], [(f"Camp {r}", f"org.234.KW.{r}") for r in ("EDR", "ILR", "ISR", "IWR", "OOR", "OFR", "OMR")]])
    excluded = asyncio.run(get_program_occurrences(db, scope_path="org.234.KW", include_pending=False))
    target = excluded["occurrences"][0]
    assert target["day_number"] == 2
    assert target["program_type"] == "Bible Study"
    assert target["counted_population"] == 100
    assert target["coverage"]["label"] == "Regions reporting"
    assert target["coverage"]["reported"] == 1
    assert target["coverage"]["expected"] == 1

    db_including = SequencedDb([events, aggregate_counts, details, [], [(f"Camp {r}", f"org.234.KW.{r}") for r in ("EDR", "ILR", "ISR", "IWR", "OOR", "OFR", "OMR")]])
    included = asyncio.run(get_program_occurrences(db_including, scope_path="org.234.KW", include_pending=True))
    day_two_bible = [row for row in excluded["occurrences"] if row["day_number"] == 2 and row["program_type_slug"] == "bible-study"]
    included_day_two_bible = [row for row in included["occurrences"] if row["day_number"] == 2 and row["program_type_slug"] == "bible-study"]
    assert sum(row["counted_population"] for row in day_two_bible) == 800
    assert sum(row["counted_population"] for row in included_day_two_bible) == 910
    pending_event = next(row for row in included["occurrences"] if row["event_id"] == "event-1")
    assert pending_event["counted_population"] == 110
    assert pending_event["report_state"] == "counted"


def test_crusade_alpha_data_is_removed_below_state_scope():
    campaign = SimpleNamespace(title="Crusade", start_date=date(2026, 10, 14), event_mode="crusade", alpha_location_id="alpha")
    event = SimpleNamespace(
        id="event-a", campaign_id="campaign-a", event_mode="crusade", date=date(2026, 10, 14),
        campaign=campaign, title="Crusade Evening", reporting_scope="state", path="org.234.KW",
        alpha_location_id="alpha", is_alpha_event=False, approval_status="approved",
    )
    ptype = SimpleNamespace(name="Crusade Evening", slug="crusade-evening")
    domain = SimpleNamespace(name="Global Crusade", slug="global_crusade")
    aggregate = [
        SimpleNamespace(event_id="event-a", source_role="alpha", approved_total=900, pending_total=0, returned_rows=0, approved_rows=1, pending_rows=0, counted_total=900, row_count=1),
        SimpleNamespace(event_id="event-a", source_role="satellite", approved_total=100, pending_total=0, returned_rows=0, approved_rows=1, pending_rows=0, counted_total=100, row_count=1),
    ]
    details = [
        SimpleNamespace(event_id="event-a", location_id="alpha", location_name="Alpha", path="org.234.KW.R.G.A", program_scope_path="org.234.KW", source_role="alpha", approved_total=900, pending_total=0, row_count=1, approved_rows=1, pending_rows=0, returned_rows=0),
        SimpleNamespace(event_id="event-a", location_id="satellite", location_name="Satellite", path="org.234.KW.R.G.S", program_scope_path="org.234.KW.R.G.S", source_role="satellite", approved_total=100, pending_total=0, row_count=1, approved_rows=1, pending_rows=0, returned_rows=0),
    ]
    locations = [
        SimpleNamespace(location_id="alpha", location_name="Alpha", path="org.234.KW.R.G.A", is_active=True, opened_on=None, closed_on=None),
        SimpleNamespace(location_id="satellite", location_name="Satellite", path="org.234.KW.R.G.S", is_active=True, opened_on=None, closed_on=None),
    ]
    db = SequencedDb([[(event, ptype, domain)], aggregate, details, [], locations, [("Alpha", "org.234.KW.R.G.A"), ("Satellite", "org.234.KW.R.G.S")]])
    result = asyncio.run(get_program_occurrences(db, scope_path="org.234.KW.R.G"))
    row = result["occurrences"][0]
    assert row["counted_population"] == 100
    assert "alpha" not in row["sources"]
    assert all(item["source_role"] != "alpha" for item in row["location_reports"])


def test_retreat_state_matrix_pools_reporters_and_compares_common_regions():
    current = [
        {"scope_path": f"org.234.KW.R{i}", "report_state": "counted", "counted_population": value}
        for i, value in enumerate([100, 200, 300, 400, 500, 600, 700])
    ]
    prior = [
        {"scope_path": f"org.234.KW.R{i}", "report_state": "counted", "counted_population": value}
        for i, value in enumerate([90, 180, 270, 360, 450, 540, 630])
    ]
    assert _pool_session_rows(current, metric="attendance") == (2800, 7, 7)
    common = {row["scope_path"] for row in current}.intersection(row["scope_path"] for row in prior)
    assert sum(row["counted_population"] for row in current if row["scope_path"] in common) == 2800
    assert sum(row["counted_population"] for row in prior if row["scope_path"] in common) == 2520


def test_retreat_comparison_uses_only_common_counted_regions_but_keeps_full_cell_total():
    current = [
        {"scope_path": "org.234.KW.R1", "report_state": "counted", "counted_population": 100},
        {"scope_path": "org.234.KW.R2", "report_state": "counted", "counted_population": 200},
        {"scope_path": "org.234.KW.R3", "report_state": "counted", "counted_population": 300},
        {"scope_path": "org.234.KW.R4", "report_state": "counted", "counted_population": 900},
    ]
    prior = [
        {"scope_path": "org.234.KW.R1", "report_state": "counted", "counted_population": 90},
        {"scope_path": "org.234.KW.R2", "report_state": "counted", "counted_population": 180},
        {"scope_path": "org.234.KW.R3", "report_state": "pending", "counted_population": 0},
    ]
    assert _compare_common_reporters(current, prior, metric="attendance") == (1500, 300, 270, 2)
