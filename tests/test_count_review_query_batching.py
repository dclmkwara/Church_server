import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.api.v1.routes.counts import list_count_review_groups
from app.models.counts import Count


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows

    def scalars(self):
        return self


class _Session:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    async def execute(self, _statement):
        self.calls += 1
        return _Result(self.rows if self.calls == 1 else [])


def _pastor():
    return SimpleNamespace(
        path="dclm.234.kw.ilr.ile",
        roles=[SimpleNamespace(score_value=3)],
    )


def test_review_queue_loads_pending_rows_metadata_and_correction_in_one_read():
    now = datetime.now(timezone.utc)
    prior = Count(
        id=uuid4(), location_id=uuid4(), date=now, program_type_id=3,
        program_type="Sunday Worship Service", program_level="location",
        program_scope_path="dclm.234.kw.ilr.ile", path="dclm.234.kw.ilr.ile.001",
        status="rejected", is_deleted=False,
    )
    row = Count(
        id=uuid4(), location_id=prior.location_id, date=now, program_type_id=3,
        program_type="Sunday Worship Service", program_level="location",
        program_scope_path="dclm.234.kw.ilr.ile", path="dclm.234.kw.ilr.ile.001",
        status="pending", created_at=now, supersedes_id=prior.id, entered_by_id=uuid4(),
        total=42, adult_male=10, adult_female=10, youth_male=10, youth_female=5,
        boys=4, girls=3, auto_accepted=False, is_deleted=False,
    )
    db = _Session([(
        row, "Sample Location", row.path, "Sunday Worship Service", None, None,
        "Sample Usher", prior,
    )])

    groups = asyncio.run(list_count_review_groups(db=db, current_user=_pastor()))

    assert db.calls == 2
    assert len(groups) == 1
    assert groups[0]["location"] == "Sample Location"
    assert groups[0]["submitters"] == ["Sample Usher"]
    assert groups[0]["correction_history"][0]["status"] == "rejected"


def test_empty_review_queue_still_uses_one_read():
    db = _Session([])
    groups = asyncio.run(list_count_review_groups(db=db, current_user=_pastor()))
    assert groups == []
    assert db.calls == 1
