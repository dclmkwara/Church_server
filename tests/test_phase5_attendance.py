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

    def scalar_one(self):
        return self._scalar


class _AttendanceSummaryDB:
    def __init__(self):
        self.calls = 0

    async def execute(self, _statement):
        self.calls += 1
        return _Result(scalar=10)


def test_attendance_stats_route_precedes_uuid_parameter_route():
    get_paths = [
        route.path
        for route in attendance_router.routes
        if "GET" in getattr(route, "methods", set())
    ]
    assert get_paths.index("/stats") < get_paths.index("/{attendance_id}")


def test_attendance_summary_uses_deduplicated_meeting_totals(monkeypatch):
    async def fake_meetings(*_args, **_kwargs):
        return {"ranking": [{
            "expected": 20, "present": 12, "late": 2, "absent": 6,
            "excused": 0, "meetings": 2, "legacy_roster_meetings": 0,
        }]}

    import app.api.v1.routes.dashboard as dashboard_routes
    monkeypatch.setattr(dashboard_routes, "worker_meeting_analytics", fake_meetings)
    db = _AttendanceSummaryDB()
    summary = asyncio.run(_get_attendance_summary(db, "org.234.KW"))

    assert summary["present"] == 12
    assert summary["late"] == 2
    assert summary["current_roster"] == 10
    assert summary["opportunities"] == 20
    assert summary["expected"] == 20
    assert summary["rate"] == 70.0
    assert summary["meetings_reported"] == 2
    assert db.calls == 1
