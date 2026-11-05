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
        self._results = iter((
            _Result(row=SimpleNamespace(present=30, late=0, absent=0, excused=0)),
            _Result(scalar=10),
            _Result(row=SimpleNamespace(opportunities=40, submitted_present=30)),
        ))

    async def execute(self, _statement):
        return next(self._results)


def test_attendance_stats_route_precedes_uuid_parameter_route():
    get_paths = [
        route.path
        for route in attendance_router.routes
        if "GET" in getattr(route, "methods", set())
    ]
    assert get_paths.index("/stats") < get_paths.index("/{attendance_id}")


def test_attendance_summary_uses_each_meeting_roster_snapshot():
    summary = asyncio.run(_get_attendance_summary(_AttendanceSummaryDB(), "org.234.KW"))

    assert summary["present"] == 30
    assert summary["current_roster"] == 10
    assert summary["opportunities"] == 40
    assert summary["expected"] == 40
    assert summary["rate"] == 75.0
