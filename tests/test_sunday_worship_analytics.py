"""Regression checks for date windows and the first Sunday Worship analytics slice."""

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.services.analytics.program_config import STANDING_PROGRAMS
from app.services.analytics.sunday_worship import (
    SundayWorshipAnalytics,
    _build_overview,
    latest_sunday,
    receipt_state,
)


def test_standing_program_config_keeps_leaders_and_workers_meetings_separate():
    """Leaders Meeting has no expected-unit coverage; Workers Meeting is location-based."""
    leaders = STANDING_PROGRAMS["tuesday_leaders_meeting"]
    workers = STANDING_PROGRAMS["saturday_workers_meeting"]
    assert leaders.expected_unit is None
    assert workers.expected_unit == "location"
    assert leaders.key != workers.key
    assert leaders.weekday != workers.weekday


def test_latest_sunday_uses_local_calendar_date():
    """The most recent occurrence remains Sunday when the current day is later in week."""
    assert latest_sunday(date(2026, 11, 6)) == date(2026, 11, 1)
    assert latest_sunday(date(2026, 11, 1)) == date(2026, 11, 1)


def test_receipt_state_uses_africa_lagos_end_of_day_thresholds():
    """Missing reports change from awaiting to late to missing at policy boundaries."""
    sunday = date(2026, 11, 1)
    zone = ZoneInfo("Africa/Lagos")
    occurrence_end = datetime(2026, 11, 2, 0, 0, tzinfo=zone)
    assert receipt_state(sunday, occurrence_end + timedelta(hours=10), received=False) == "awaiting"
    assert receipt_state(sunday, occurrence_end + timedelta(hours=10, seconds=1), received=False) == "late"
    assert receipt_state(sunday, occurrence_end + timedelta(hours=24), received=False) == "late"
    assert receipt_state(sunday, occurrence_end + timedelta(hours=24, seconds=1), received=False) == "missing"
    assert receipt_state(sunday, occurrence_end, received=True) == "received"


def test_reported_zero_is_counted_and_missing_unit_is_not_zero():
    """One approved zero remains a value while an unreported sibling stays missing."""
    locations = [
        SimpleNamespace(location_id="l1", path="org.234.kw.r.g.001"),
        SimpleNamespace(location_id="l2", path="org.234.kw.r.g.002"),
    ]
    zero_count = SimpleNamespace(
        id="c1", event_id=None, location_id="l1", status="approved", total=0,
        adult_male=0, adult_female=0, youth_male=0, youth_female=0, boys=0, girls=0,
    )
    result = _build_overview(
        scope_path="org.234.kw.r.g",
        occurrence_date=date(2026, 11, 1),
        now=datetime(2026, 11, 4, tzinfo=ZoneInfo("Africa/Lagos")),
        locations=locations,
        events=[],
        count_rows=[zero_count],
        include_pending=False,
    )
    assert result["total"] == 0
    assert result["n_expected"] == 2
    assert result["n_received"] == 1
    assert result["n_counted"] == 1
    assert result["coverage"]["approved"] == 1
    assert result["coverage"]["missing"] == 1


def test_pending_zero_is_received_but_not_counted_by_default():
    """Pending count rows do not enter official totals unless explicitly included."""
    locations = [SimpleNamespace(location_id="l1", path="org.234.kw.r.g.001")]
    pending_zero = SimpleNamespace(
        id="c1", event_id=None, location_id="l1", status="pending", total=0,
        adult_male=0, adult_female=0, youth_male=0, youth_female=0, boys=0, girls=0,
    )
    shared = dict(
        scope_path="org.234.kw.r.g",
        occurrence_date=date(2026, 11, 1),
        now=datetime(2026, 11, 2, tzinfo=ZoneInfo("Africa/Lagos")),
        locations=locations,
        events=[],
        count_rows=[pending_zero],
    )
    official = _build_overview(**shared, include_pending=False)
    inclusive = _build_overview(**shared, include_pending=True)
    assert official["n_received"] == 1
    assert official["n_counted"] == 0
    assert official["total"] is None
    assert official["coverage"]["pending"] == 1
    assert inclusive["n_counted"] == 1
    assert inclusive["total"] == 0


def test_series_load_count_does_not_grow_with_weeks_or_direct_children():
    """The combined scope/week payload uses a fixed four database reads."""
    locations = [
            SimpleNamespace(location_id=f"l{index}", location_name=f"Location {index}", path=f"org.234.kw.r{index}.g.001", is_active=True, opened_on=None, closed_on=None)
        for index in range(1, 3)
    ]
    regions = [
        SimpleNamespace(path=f"org.234.kw.r{index}", region_name=f"Region {index}")
        for index in range(1, 3)
    ]

    class Scalars:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

        def unique(self):
            return self

    class Result:
        def __init__(self, rows=None, scalar=None):
            self.rows = rows or []
            self.scalar = scalar

        def scalar_one_or_none(self):
            return self.scalar

        def scalars(self):
            return Scalars(self.rows)

        def all(self):
            return self.rows

    class Session:
        def __init__(self):
            self.calls = 0

        async def execute(self, _statement):
            self.calls += 1
            result = {
                1: Result(rows=[(row, None) for row in locations]),
                2: Result(rows=[
                    SimpleNamespace(path=row.path, name=row.region_name, location_id="", node_type="child")
                    for row in regions
                ] + [SimpleNamespace(path="org.234.kw", name="Kwara State", location_id="", node_type="ancestor")]),
                3: Result(rows=[]),
                4: Result(rows=[]),
            }[self.calls]
            return result

    session = Session()
    dates = [date(2026, 10, 18), date(2026, 10, 25), date(2026, 11, 1), date(2026, 11, 8)]
    result = __import__("asyncio").run(SundayWorshipAnalytics.series(
        session, "org.234.kw", occurrence_dates=dates,
    ))

    assert session.calls == 4  # locations, hierarchy, type/event, counts
    assert len(result["scope"]) == len(dates)
    assert len(result["children"]) == 2
    assert all(len(child["history"]) == len(dates) for child in result["children"])


def test_combined_event_is_counted_once_and_supersedes_local_report():
    """A group-level Sunday count replaces local rows and is not duplicated per location."""
    locations = [
        SimpleNamespace(location_id="l1", path="org.234.kw.r.g.001"),
        SimpleNamespace(location_id="l2", path="org.234.kw.r.g.002"),
    ]
    event = SimpleNamespace(id="e1", path="org.234.kw.r.g", reporting_scope="group")
    combined = SimpleNamespace(
        id="c1", event_id="e1", location_id="l1", status="approved", total=250,
        adult_male=70, adult_female=80, youth_male=30, youth_female=35, boys=20, girls=15,
    )
    superseded_local = SimpleNamespace(
        id="c2", event_id=None, location_id="l2", status="approved", total=90,
        adult_male=25, adult_female=30, youth_male=10, youth_female=12, boys=7, girls=6,
    )
    result = _build_overview(
        scope_path="org.234.kw.r.g",
        occurrence_date=date(2026, 11, 1),
        now=datetime(2026, 11, 4, tzinfo=ZoneInfo("Africa/Lagos")),
        locations=locations,
        events=[event],
        count_rows=[combined, superseded_local],
        include_pending=False,
    )
    assert result["total"] == 250
    assert result["n_expected"] == 2
    assert result["n_received"] == 2
    assert result["n_counted"] == 2
    assert result["coverage"]["combined"] == 2
    assert result["coverage"]["superseded"] == 1


def test_combined_event_without_report_still_expires_into_missing_coverage():
    """A scheduled combined meeting does not hide a missing report for its scope."""
    locations = [
        SimpleNamespace(location_id="l1", path="org.234.kw.r.g.001"),
        SimpleNamespace(location_id="l2", path="org.234.kw.r.g.002"),
    ]
    event = SimpleNamespace(id="e1", path="org.234.kw.r.g", reporting_scope="group")
    result = _build_overview(
        scope_path="org.234.kw.r.g",
        occurrence_date=date(2026, 11, 1),
        now=datetime(2026, 11, 4, tzinfo=ZoneInfo("Africa/Lagos")),
        locations=locations,
        events=[event],
        count_rows=[],
        include_pending=False,
    )
    assert result["coverage"]["combined"] == 2
    assert result["coverage"]["missing"] == 2
    assert result["n_received"] == 0
    assert result["total"] is None


def test_eventless_combined_sunday_report_replaces_local_reports_at_group_region_and_state():
    """A combined report is a coverage trigger even when it has no ProgramEvent."""
    levels = [
        ("Group", "org.234.kw.r.g", "org.234.kw.r.g.001"),
        ("Region", "org.234.kw.r", "org.234.kw.r.g.001"),
        ("State", "org.234.kw", "org.234.kw.r.g.001"),
    ]
    for index, (level, report_scope, venue_path) in enumerate(levels):
        locations = [
            SimpleNamespace(location_id="l1", path="org.234.kw.r.g.001"),
            SimpleNamespace(location_id="l2", path="org.234.kw.r.g.002"),
        ]
        combined = SimpleNamespace(
            id=f"combined-{index}", event_id=None, location_id="l1", path=venue_path,
            program_level=level, program_scope_path=report_scope, status="approved", total=250,
            adult_male=70, adult_female=80, youth_male=30, youth_female=35, boys=20, girls=15,
        )
        local = SimpleNamespace(
            id=f"local-{index}", event_id=None, location_id="l2", status="approved", total=90,
            adult_male=25, adult_female=30, youth_male=10, youth_female=12, boys=7, girls=6,
        )
        result = _build_overview(
            scope_path=report_scope,
            occurrence_date=date(2026, 11, 1),
            now=datetime(2026, 11, 4, tzinfo=ZoneInfo("Africa/Lagos")),
            locations=locations,
            events=[],
            count_rows=[combined, local],
            include_pending=False,
        )
        assert result["total"] == 250
        assert result["n_expected"] == 2
        assert result["n_counted"] == 2
        assert result["coverage"]["combined"] == 2
        assert result["coverage"]["superseded"] == 1


def test_rejected_sunday_report_is_excluded_and_linked_approved_correction_counts():
    locations = [SimpleNamespace(location_id="l1", path="org.234.kw.r.g.001")]
    rejected = SimpleNamespace(
        id="old", event_id=None, location_id="l1", status="rejected", total=90,
        adult_male=25, adult_female=30, youth_male=10, youth_female=12, boys=7, girls=6,
    )
    correction = SimpleNamespace(
        id="new", supersedes_id="old", event_id=None, location_id="l1", status="approved", total=80,
        adult_male=20, adult_female=28, youth_male=10, youth_female=10, boys=6, girls=6,
    )
    result = _build_overview(
        scope_path="org.234.kw.r.g", occurrence_date=date(2026, 11, 1),
        now=datetime(2026, 11, 4, tzinfo=ZoneInfo("Africa/Lagos")), locations=locations,
        events=[], count_rows=[rejected, correction], include_pending=False,
    )
    assert result["total"] == 80
    assert result["coverage"]["approved"] == 1
    assert result["coverage"]["returned"] == 0


def test_location_event_report_is_counted_once_for_its_location():
    """Scheduled local-event rows share the same location coverage as unscheduled rows."""
    locations = [SimpleNamespace(location_id="l1", path="org.234.kw.r.g.001")]
    event = SimpleNamespace(id="e1", path="org.234.kw.r.g.001", reporting_scope="location")
    count = SimpleNamespace(
        id="c1", event_id="e1", location_id="l1", status="approved", total=12,
        adult_male=4, adult_female=4, youth_male=2, youth_female=1, boys=1, girls=0,
    )
    result = _build_overview(
        scope_path="org.234.kw.r.g",
        occurrence_date=date(2026, 11, 1),
        now=datetime(2026, 11, 4, tzinfo=ZoneInfo("Africa/Lagos")),
        locations=locations,
        events=[event],
        count_rows=[count],
        include_pending=False,
    )
    assert result["total"] == 12
    assert result["coverage"]["approved"] == 1
    assert result["n_received"] == 1
