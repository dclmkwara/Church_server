from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

from app.services.statistics_service import StatisticsService
from app.api.v1.routes.dashboard import _period_start


class _Result:
    def one_or_none(self):
        return SimpleNamespace(
            adult_male=40,
            adult_female=30,
            youth_male=20,
            youth_female=10,
            boys=8,
            girls=12,
            total=120,
            program_count=2,
        )


class _DB:
    statement = None

    async def execute(self, statement):
        self.statement = statement
        return _Result()


@pytest.mark.asyncio
async def test_population_statistics_group_location_rows_by_dated_occurrence():
    db = _DB()

    result = await StatisticsService.get_population_statistics(
        db,
        "org.234.KW.ILR",
        date_filter=date(2026, 10, 7),
    )

    compiled = db.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled).lower()
    assert "group by date(counts.date)" in sql
    assert "counts.event_id" in sql
    assert "counts.program_level" in sql
    assert "counts.date >=" in sql
    assert date(2026, 10, 7) in compiled.params.values()
    assert result["total"] == 60
    assert result["average_men"] == 34
    assert result["average_women"] == 26


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("recent", date(2026, 10, 7)),
        ("month", date(2026, 11, 1)),
        ("quarter", date(2026, 10, 1)),
        ("year", date(2026, 1, 1)),
    ],
)
def test_population_period_start(period, expected):
    assert _period_start(period, date(2026, 11, 5)) == expected
