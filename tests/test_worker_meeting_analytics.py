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
        type_id=1, meeting_scope="org.234.KW.R.G", worker_path="org.234.KW.R.G.L1",
        location_name="Location One", group_name="Group One", region_name="Ilorin Region",
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
    assert result["direct_child_distribution"] == [{
        "child_id": "R", "label": "Ilorin Region", "present": 1,
        "late": 1, "absent": 1, "excused": 0, "meetings": 1,
    }]
    assert result["latest_meeting"] == {
        "date": "2026-11-07", "present": 1, "late": 1, "absent": 1,
        "excused": 0, "expected": 3, "meetings": 1,
        "attendance_rate": 66.7, "has_reliable_roster": True,
    }


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
    assert result["direct_child_distribution"] == [{
        "child_id": "L1", "label": "Location One", "present": 1,
        "late": 0, "absent": 0, "excused": 0, "meetings": 1,
    }]
    assert len(db.statements) == 2


def test_each_meeting_uses_its_own_roster_snapshot():
    first = _submission([str(WORKERS[0])], count=1)
    second = _submission([str(WORKERS[1])], count=1)
    second.date = datetime(2026, 11, 14, tzinfo=timezone.utc)
    submissions = [
        (first, "saturday_workers_meeting", "Saturday Workers Meeting", 1, first.path),
        (second, "saturday_workers_meeting", "Saturday Workers Meeting", 1, second.path),
    ]
    present = [_attendance(WORKERS[0], "present")]
    present[0].date = first.date
    result = asyncio.run(worker_meeting_analytics(_Db([_Result(rows=submissions), _Result(rows=present)]), "org.234.KW"))
    meeting = result["ranking"][0]
    assert meeting["expected"] == 2
    assert meeting["present"] == 1
    assert meeting["attendance_rate"] == 50.0
    assert result["latest_meeting"]["date"] == "2026-11-14"
    assert result["latest_meeting"]["expected"] == 1
    assert result["latest_meeting"]["absent"] == 1
    assert result["latest_meeting"]["attendance_rate"] == 0.0


def test_legacy_roster_records_make_rate_unavailable():
    legacy = _submission(None, count=20)
    db = _Db([_Result(rows=[(legacy, "saturday_workers_meeting", "Saturday Workers Meeting", 1, legacy.path)]), _Result(rows=[_attendance(WORKERS[0], "present")])])
    result = asyncio.run(worker_meeting_analytics(db, "org.234.KW"))
    meeting = result["ranking"][0]
    assert meeting["expected"] == 20
    assert meeting["attendance_rate"] is None
    assert result["monthly_trend"][0]["attendance_rate"] is None
    assert result["latest_meeting"]["attendance_rate"] is None
    assert result["latest_meeting"]["has_reliable_roster"] is False


def test_snapshot_meeting_rate_remains_available_when_other_meeting_is_legacy():
    snapshot = _submission([str(worker) for worker in WORKERS])
    legacy = _submission(None, count=20)
    legacy.date = datetime(2026, 11, 14, tzinfo=timezone.utc)
    submissions = [
        (snapshot, "saturday_workers_meeting", "Saturday Workers Meeting", 1, snapshot.path),
        (legacy, "saturday_workers_meeting", "Saturday Workers Meeting", 1, legacy.path),
    ]
    attendance = [_attendance(WORKERS[0], "present")]
    attendance[0].date = snapshot.date
    result = asyncio.run(worker_meeting_analytics(_Db([_Result(rows=submissions), _Result(rows=attendance)]), "org.234.KW"))
    assert result["ranking"][0]["attendance_rate"] is None
    monthly = {row["period"]: row for row in result["monthly_trend"]}
    assert monthly["2026-11"]["attendance_rate"] is None
