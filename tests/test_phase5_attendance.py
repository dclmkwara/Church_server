from types import SimpleNamespace

import asyncio

from app.api.v1.routes.attendance import router as attendance_router
from app.api.v1.routes.dashboard import _get_attendance_summary


class _Result:
    def __init__(self, *, row=None, scalar=None):
        self._row = row
        self._scalar = scalar

    def one(self):
        return self._row

    def scalar(self):
        return self._scalar


class _AttendanceSummaryDB:
    def __init__(self):
        self.calls = 0

    async def execute(self, _statement):
        self.calls += 1
        return _Result(row=SimpleNamespace(
            present=30, late=0, absent=0, excused=0,
            current_roster=10, opportunities=40, submitted_present=30,
        ))


def test_attendance_stats_route_precedes_uuid_parameter_route():
    get_paths = [
        route.path
        for route in attendance_router.routes
        if "GET" in getattr(route, "methods", set())
    ]
    assert get_paths.index("/stats") < get_paths.index("/{attendance_id}")


def test_attendance_summary_uses_each_meeting_roster_snapshot_in_one_query():
    db = _AttendanceSummaryDB()
    summary = asyncio.run(_get_attendance_summary(db, "org.234.KW"))

    assert summary["present"] == 30
    assert summary["current_roster"] == 10
    assert summary["opportunities"] == 40
    assert summary["expected"] == 40
    assert summary["rate"] == 75.0
    assert db.calls == 1
