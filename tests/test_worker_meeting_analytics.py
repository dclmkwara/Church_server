import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from app.services.worker_meeting_analytics import worker_meeting_analytics


WORKERS = [UUID(int=value) for value in range(1, 4)]


class _Result:
    def __init__(self, rows=(), scalars=()):
        self._rows = rows
        self._scalars = scalars

    def all(self):
        return self._rows

    def scalars(self):
        return _ScalarResult(self._scalars)

    def __iter__(self):
        return iter(self._scalars)


class _ScalarResult:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


class _Db:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return next(self.responses)


def _submission(expected_ids, count=3):
    return SimpleNamespace(
        event_id=UUID(int=50), date=datetime(2026, 11, 7, tzinfo=timezone.utc),
        expected_worker_ids=expected_ids, expected_workers_count=count,
        program_type="Saturday Workers Meeting", program_scope_path="org.234.KW.R.G",
        path="org.234.KW.R.G", program_type_id=1,
    )


def _attendance(worker_id, status):
    return SimpleNamespace(
        worker_id=worker_id, event_id=UUID(int=50), date=datetime(2026, 11, 7, tzinfo=timezone.utc),
        status=status, type_slug="saturday_workers_meeting", type_name="Saturday Workers Meeting",
        type_id=1, meeting_scope="org.234.KW.R.G",
    )


def test_multiple_ushers_count_roster_and_workers_once_per_meeting():
    duplicate_submissions = [
        (_submission([str(worker) for worker in WORKERS]), "saturday_workers_meeting", "Saturday Workers Meeting", 1, "org.234.KW.R.G"),
        (_submission([str(worker) for worker in WORKERS]), "saturday_workers_meeting", "Saturday Workers Meeting", 1, "org.234.KW.R.G"),
    ]
    rows = [
        _attendance(WORKERS[0], "present"),
        _attendance(WORKERS[0], "present"),
        _attendance(WORKERS[1], "late"),
        _attendance(WORKERS[2], "absent"),
    ]
    db = _Db([_Result(rows=duplicate_submissions), _Result(rows=rows)])

    result = asyncio.run(worker_meeting_analytics(db, "org.234.KW"))
    meeting = result["ranking"][0]
    assert meeting["expected"] == 3
    assert meeting["present"] == 1
    assert meeting["late"] == 1
    assert meeting["absent"] == 1
    assert meeting["meetings"] == 1
    assert meeting["attendance_rate"] == 66.7
    assert result["monthly_trend"][0]["expected"] == 3


def test_legacy_roster_count_is_used_once_and_marked():
    legacy = _submission(None, count=20)
    duplicates = [
        (legacy, "saturday_workers_meeting", "Saturday Workers Meeting", 1, "org.234.KW.R.G"),
        (legacy, "saturday_workers_meeting", "Saturday Workers Meeting", 1, "org.234.KW.R.G"),
    ]
    db = _Db([_Result(rows=duplicates), _Result(rows=[_attendance(WORKERS[0], "present")])])

    result = asyncio.run(worker_meeting_analytics(db, "org.234.KW"))
    meeting = result["ranking"][0]
    assert meeting["expected"] == 20
    assert meeting["present"] == 1
    assert meeting["legacy_roster_meetings"] == 1


def test_location_meeting_roster_uses_captured_ids_not_stale_ltree_path():
    submission = _submission([str(worker) for worker in WORKERS])
    submission.program_scope_path = "org.234.KW.R.G.L"
    submission.path = "org.234.KW.R.G.L"
    db = _Db([
        _Result(rows=[(submission, "saturday_workers_meeting", "Saturday Workers Meeting", 1, "org.234.KW.R.G.L")]),
        _Result(rows=[_attendance(WORKERS[0], "present")]),
    ])

    result = asyncio.run(worker_meeting_analytics(db, "org.234.KW.R.G.L", location_id="location-1"))

    assert result["ranking"][0]["expected"] == 3
    assert result["ranking"][0]["attendance_rate"] == 33.3
    assert len(db.statements) == 2


def test_historical_roster_snapshot_survives_current_worker_path_change():
    submission = _submission([str(worker) for worker in WORKERS])
    submission.program_scope_path = "org.234.KW.R.G.L"
    submission.path = "org.234.KW.R.G.L"
    duplicate = (submission, "saturday_workers_meeting", "Saturday Workers Meeting", 1, submission.path)
    db = _Db([
        _Result(rows=[duplicate]),
        _Result(rows=[_attendance(WORKERS[0], "present")]),
    ])

    result = asyncio.run(worker_meeting_analytics(db, "org.234.KW.R.G"))

    assert result["ranking"][0]["expected"] == 3
    assert result["ranking"][0]["attendance_rate"] == 33.3
    assert len(db.statements) == 2
