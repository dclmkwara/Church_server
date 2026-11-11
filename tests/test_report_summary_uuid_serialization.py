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

    async def execute(self, statement, params):
        self.statement = str(statement)
        return _Mappings(self.rows)


def test_reports_summary_converts_database_uuid_values_to_public_strings():
    location_id = uuid4()
    session = _Session([{
        "day": date(2026, 11, 8),
        "event_id": None,
        "event_title": "Sunday Worship",
        "location_id": location_id,
        "location_name": "Synthetic Location",
        "path": "dcl.234.kw.ilr.ile.001",
        "total_attendance": 12,
        "total_men": 3,
        "total_women": 3,
        "total_youth_male": 2,
        "total_youth_female": 1,
        "total_boys": 2,
        "total_girls": 1,
        "record_count": 1,
    }])

    result = asyncio.run(ReportService.get_daily_counts(
        session, "dcl.234.kw", date(2026, 11, 1), date(2026, 11, 8),
    ))

    assert result[0].location_id == str(location_id)
    assert result[0].event_id == ""
    assert result[0].path == "dcl.234.kw.ilr.ile.001"
    assert "location_id::text AS location_id" in session.statement
    assert "path::text AS path" in session.statement
