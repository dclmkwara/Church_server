from types import SimpleNamespace

import asyncio

from app.api.v1.routes.attendance import router as attendance_router
from app.api.v1.routes.dashboard import _get_attendance_summary
from app.api.v1.routes.sync import _attendance_roster_scope, _is_allowed_worker_attendance_program
from app.models.user import Worker
from sqlalchemy.dialects import postgresql


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


def test_local_attendance_roster_uses_same_location_key_as_utility():
    local = _attendance_roster_scope("location-uuid", "org.234.KW.ILR.ILE.003", False)
    compiled = str(local.compile(dialect=postgresql.dialect()))

    # Imported worker rows may have legacy ancestor paths. Utility presents the
    # location's workers by location_id, so local attendance must validate that
    # same roster, while combined-event checks remain hierarchy scoped.
    assert "workers.location_id" in compiled
    assert "org.234" not in compiled

    combined = _attendance_roster_scope("location-uuid", "org.234.KW.ILR", True)
    combined_sql = str(combined.compile(dialect=postgresql.dialect()))
    assert "workers.path" in combined_sql
    assert "@>" in combined_sql or "<@" in combined_sql


def test_worker_attendance_accepts_the_utility_domain_label():
    assert _is_allowed_worker_attendance_program("Weekly Programs", "Saturday Workers Meeting")
    assert _is_allowed_worker_attendance_program("weekly_programs", "Tuesday Leaders Meeting")
    assert not _is_allowed_worker_attendance_program("Weekly Programs", "Sunday Worship Service")


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
