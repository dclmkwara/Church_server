import asyncio
from datetime import date
from uuid import uuid4

from app.services.report_service import ReportService


class _Mappings:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self._rows


class _Session:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None
        self.params = None

    async def execute(self, statement, params):
        self.statement = str(statement)
        self.params = params
        return _Mappings(self.rows)


def _row(location_id, *, count_id, total, status="approved", group_id=None, service="main", group_state="open", day=date(2026, 11, 8), adult_male=None):
    adult_male = total if adult_male is None else adult_male
    return {
        "count_id": str(count_id), "count_group_id": str(group_id) if group_id else None,
        "group_state": group_state, "service_id": service, "day": day,
        "event_id": None, "event_title": "Sunday Worship", "program_type": "Sunday Worship",
        "status": status, "count_mode": "section" if group_id else None,
        "location_id": str(location_id), "location_name": "Synthetic Location",
        "path": "dcl.234.kw.ilr.ile.001", "total": total,
        "adult_male": adult_male, "adult_female": 0, "youth_male": 0,
        "youth_female": 0, "boys": 0, "girls": 0,
    }


def test_reports_summary_excludes_pending_and_rejected_by_default_and_keeps_sessions_distinct():
    location_id = uuid4()
    rows = [
        _row(location_id, count_id="approved-main", total=20, service="main"),
        _row(location_id, count_id="approved-evening", total=7, service="evening"),
        _row(location_id, count_id="pending", total=100, status="pending"),
        _row(location_id, count_id="rejected", total=200, status="rejected"),
    ]
    session = _Session(rows)

    result = asyncio.run(ReportService.get_count_summary_rows(
        session, "dcl.234.kw", date(2026, 11, 1), date(2026, 11, 8),
    ))

    assert [row.total_attendance for row in result] == [20, 7]
    assert {row.service_id for row in result} == {"main", "evening"}
    assert "FROM counts c" in session.statement
    assert "mv_daily_counts_by_location" not in session.statement
    assert all(row.location_id == str(location_id) for row in result)


def test_reports_summary_pending_requires_explicit_include_option():
    location_id = uuid4()
    rows = [
        _row(location_id, count_id="approved", total=20),
        _row(location_id, count_id="pending", total=10, status="pending"),
        _row(location_id, count_id="returned", total=50, status="returned"),
        _row(location_id, count_id="rejected", total=100, status="rejected"),
    ]
    session = _Session(rows)

    result = asyncio.run(ReportService.get_count_summary_rows(
        session, "dcl.234.kw", date(2026, 11, 1), date(2026, 11, 8), include_pending=True,
    ))

    assert {row.total_attendance for row in result} == {20, 10}
    # The query intentionally loads every review state so the shared policy
    # can decide visibility after validating the whole occurrence group.
    assert "c.status" in session.statement


def test_reports_summary_sums_only_parts_linked_to_the_same_count_group():
    location_id, group_id = uuid4(), uuid4()
    rows = [
        _row(location_id, count_id="part-a", group_id=group_id, total=10, adult_male=6),
        _row(location_id, count_id="part-b", group_id=group_id, total=12, adult_male=8),
        _row(location_id, count_id="other-service", total=5, service="second"),
    ]
    result = asyncio.run(ReportService.get_count_summary_rows(
        _Session(rows), "dcl.234.kw", date(2026, 11, 1), date(2026, 11, 8),
    ))

    by_total = {row.total_attendance: row for row in result}
    assert set(by_total) == {22, 5}
    assert by_total[22].total_men == 14
    assert by_total[22].record_count == 2


def test_reports_summary_omits_conflicted_count_groups():
    location_id, group_id = uuid4(), uuid4()
    rows = [
        _row(location_id, count_id="part-a", group_id=group_id, total=10, group_state="conflict"),
    ]
    result = asyncio.run(ReportService.get_count_summary_rows(
        _Session(rows), "dcl.234.kw", date(2026, 11, 1), date(2026, 11, 8),
    ))
    assert result == []


def test_reports_summary_never_counts_a_mixed_status_group_as_complete():
    location_id, group_id = uuid4(), uuid4()
    rows = [
        _row(location_id, count_id="approved-part", group_id=group_id, total=11, status="approved"),
        _row(location_id, count_id="pending-part", group_id=group_id, total=17, status="pending"),
    ]
    excluded = asyncio.run(ReportService.get_count_summary_rows(
        _Session(rows), "dcl.234.kw", date(2026, 11, 1), date(2026, 11, 8),
    ))
    included = asyncio.run(ReportService.get_count_summary_rows(
        _Session(rows), "dcl.234.kw", date(2026, 11, 1), date(2026, 11, 8), include_pending=True,
    ))
    assert excluded == []
    # A group with inconsistent part states is never presented as complete,
    # even when pending rows are requested.
    assert included == []
