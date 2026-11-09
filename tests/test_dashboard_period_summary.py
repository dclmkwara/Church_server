import asyncio
from datetime import date, timedelta
from sqlalchemy.dialects import postgresql

from app.services.dashboard_service import DashboardService


class _SummaryRow:
    def __init__(self, **values):
        self.values = values

    def __getattr__(self, name):
        if name in self.values:
            return self.values[name]
        return None if name.endswith("_at") else 0


class _Result:
    def __init__(self, row):
        self.row = row

    def one(self):
        return self.row


class _Database:
    def __init__(self, row):
        self.row = row
        self.statements = []

    async def execute(self, statement):
        compiled = statement.compile(dialect=postgresql.dialect())
        self.statements.append((str(compiled), list(compiled.params.values())))
        return _Result(self.row)


def test_period_metrics_and_pending_ages_are_part_of_one_scoped_summary_statement(monkeypatch):
    async def no_meetings(*_args, **_kwargs):
        return {"ranking": []}

    monkeypatch.setattr("app.services.dashboard_service.worker_meeting_analytics", no_meetings)
    from app.services.analytics.program_config import reporting_now
    now = reporting_now()
    row = _SummaryRow(
        offerings_current_total=10550.25, offerings_current_records=2,
        offerings_previous_total=10000, offerings_previous_records=1,
        newcomers_current=5, newcomers_previous=4, converts_current=2, converts_previous=0,
        records_current=7, records_previous=4,
        pending_count_reports=3,
        oldest_pending_count_at=now - timedelta(hours=26, minutes=10),
    )
    db = _Database(row)
    summary = asyncio.run(DashboardService.get_summary(
        db, "dclm.234.kw", weeks=4, latest_date=date(2026, 11, 8),
    ))

    assert len(db.statements) == 1
    sql, params = db.statements[0]
    assert "offerings.status" in sql
    assert "offerings.amount" in sql
    assert "records.record_type" in sql
    assert "worker_removal_requests.created_at" in sql
    local_period_starts = [
        value for value in params
        if getattr(value, "tzinfo", None) and value.date() in {date(2026, 9, 20), date(2026, 10, 18), date(2026, 11, 9)}
    ]
    assert local_period_starts
    assert summary["approved_offerings"] == {
        "current_total": 10550.25, "current_records": 2,
        "previous_total": 10000.0, "previous_records": 1,
    }
    assert summary["newcomer_period"]["newcomers_current"] == 5
    assert summary["pending_approvals"] == [{"label": "Count groups", "count": 3, "oldest_age_hours": 26}]
