import asyncio
from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException

from app.api.v1.routes.dashboard import (
    ExpectedPopulationBulkApplyRequest,
    ExpectedPopulationBulkPreviewRequest,
    _build_expected_population_bulk_preview,
    apply_expected_population_bulk,
    parse_expected_population_csv,
    preview_expected_population_bulk,
)
from app.frontend.dclm_admin.routes.expected_population import _expected_population_template_csv
from app.models.audit import AuditLog
from app.models.expected_population import LocationExpectedPopulation


class _Result:
    def __init__(self, rows=(), scalars=()):
        self._rows = list(rows)
        self._scalars = list(scalars)

    def scalars(self):
        return self

    def all(self):
        return self._rows or self._scalars


class _Session:
    def __init__(self, results):
        self.results = list(results)
        self.added = []
        self.commits = 0

    async def execute(self, _statement):
        return self.results.pop(0)

    def add_all(self, rows):
        self.added.extend(rows)

    async def commit(self):
        self.commits += 1


def _overseer():
    return SimpleNamespace(
        user_id=uuid4(), path="dclm.234.kwara",
        roles=[SimpleNamespace(role_name="State Overseer", score_value=5)],
    )


def _location(code="KW-001"):
    return SimpleNamespace(
        location_id=uuid4(), location_code=code, location_name="Sample Location",
        path="dclm.234.kwara.ilorin.group.001", is_active=True,
    )


def test_csv_parser_accepts_template_headers_and_optional_note():
    rows, errors = parse_expected_population_csv(
        "location_code,expected_attendance,effective-from,note\nKW-001,125,2026-11-01,Revised estimate\n"
    )
    assert not errors
    assert rows == [{
        "line": 2, "location_code": "KW-001", "expected_attendance_raw": "125",
        "effective_from_raw": "2026-11-01", "note": "Revised estimate",
    }]


def test_download_template_is_prefilled_and_keeps_blank_edit_fields():
    csv_text = _expected_population_template_csv({"locations": [{
        "path": "org.234.KW.EDR.DEC.D01", "location_code": "D01",
        "location_name": "Sample Location", "expected_value": 135,
    }, {
        "path": "org.234.KW.EDR.DEC.D02", "location_code": "D02",
        "location_name": "New Location", "expected_value": None,
    }]})
    rows, errors = parse_expected_population_csv(csv_text)
    assert not errors
    assert [row["location_code"] for row in rows] == [
        "org.234.KW.EDR.DEC.D01", "org.234.KW.EDR.DEC.D02",
    ]
    assert "location_display_code,location_name" in csv_text
    assert ",135,,\r\n" in csv_text
    assert "D02,New Location,,,\r\n" in csv_text


def test_unknown_codes_are_rejected_and_preview_writes_nothing():
    user = _overseer()
    db = _Session([_Result()])
    preview = asyncio.run(preview_expected_population_bulk(
        ExpectedPopulationBulkPreviewRequest(csv_text="location_code,expected_attendance,effective_from\nOUTSIDE,10,2026-11-01\n"),
        db=db, current_user=user,
    ))
    assert preview["rows"][0]["status"] == "unknown"
    assert "not in this State" in preview["rows"][0]["message"]
    assert preview["can_apply"] is False
    assert preview["summary"]["unknown_codes"] == 1
    assert db.added == [] and db.commits == 0


def test_successful_preview_is_read_only_then_apply_adds_versions_and_audits_once():
    user = _overseer()
    location = _location()
    prior = SimpleNamespace(
        id=uuid4(), location_id=location.location_id, expected_value=100,
        effective_from=date(2025, 11, 1), created_at=datetime(2025, 11, 1, tzinfo=timezone.utc),
    )
    csv_text = "location_code,expected_attendance,effective_from,note\nKW-001,125,2026-11-01,Annual review\n"
    preview_db = _Session([_Result(scalars=[location]), _Result(scalars=[prior])])
    preview = asyncio.run(preview_expected_population_bulk(
        ExpectedPopulationBulkPreviewRequest(csv_text=csv_text), db=preview_db, current_user=user,
    ))
    assert preview["can_apply"] is True
    assert preview["summary"]["matched_locations"] == 1
    assert preview["rows"][0]["old_value"] == 100
    assert preview["rows"][0]["new_value"] == 125
    assert preview_db.added == [] and preview_db.commits == 0

    apply_db = _Session([_Result(scalars=[location]), _Result(scalars=[prior]), _Result(scalars=[location]), _Result(scalars=[prior])])
    applied = asyncio.run(apply_expected_population_bulk(
        ExpectedPopulationBulkApplyRequest(preview_token=preview["preview_token"]),
        db=apply_db, current_user=user,
    ))
    versions = [item for item in apply_db.added if isinstance(item, LocationExpectedPopulation)]
    audits = [item for item in apply_db.added if isinstance(item, AuditLog)]
    assert applied == {"status": "applied", "versions_added": 1, "audit_entries": 1}
    assert len(versions) == len(audits) == 1
    assert versions[0].expected_value == 125
    assert versions[0].effective_from == date(2026, 11, 1)
    assert versions[0].note == "Annual review"
    assert audits[0].action == "BULK_SET_LOCATION_EXPECTED_POPULATION"
    assert prior.expected_value == 100
    assert prior.effective_from == date(2025, 11, 1)
    assert apply_db.commits == 1


def test_bulk_preview_accepts_full_location_path_when_local_code_repeats():
    user = _overseer()
    location = _location(code="001")
    csv_text = (
        "location_code,expected_attendance,effective_from\n"
        f"{location.path},125,2026-11-01\n"
    )
    db = _Session([_Result(scalars=[location]), _Result()])
    preview = asyncio.run(preview_expected_population_bulk(
        ExpectedPopulationBulkPreviewRequest(csv_text=csv_text), db=db, current_user=user,
    ))
    assert preview["can_apply"] is True
    assert preview["rows"][0]["location_id"] == str(location.location_id)
    assert preview["rows"][0]["path"] == location.path
    assert db.added == [] and db.commits == 0


def test_csv_with_unknown_code_cannot_be_applied():
    user = _overseer()
    db = _Session([_Result()])
    preview = asyncio.run(_build_expected_population_bulk_preview(
        db, user,
        "location_code,expected_attendance,effective_from\nOUTSIDE,10,2026-11-01\n",
    ))
    assert preview["preview_token"] is None
    assert preview["can_apply"] is False


def test_csv_preview_rejects_non_state_overseer():
    user = SimpleNamespace(
        user_id=uuid4(), path="dclm.234.kwara",
        roles=[SimpleNamespace(role_name="State Admin", score_value=5)],
    )
    try:
        asyncio.run(_build_expected_population_bulk_preview(
            _Session([]), user,
            "location_code,expected_attendance,effective_from\nKW-001,10,2026-11-01\n",
        ))
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("State Admin must not preview an estimate import")
