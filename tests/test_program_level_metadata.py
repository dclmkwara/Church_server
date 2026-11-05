from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from fastapi import HTTPException

from app.schemas.attendance import WorkerAttendanceCreate, WorkerAttendanceResponse, WorkerAttendanceSubmissionCreate
from app.schemas.counts import CountCreate, CountResponse
from app.schemas.offerings import OfferingCreate, OfferingResponse
from app.schemas.records import RecordCreate, RecordResponse
from app.crud.workflow_rules import resolve_program_level


def _routine_context(**extra):
    return {
        "location_id": "00000000-0000-0000-0000-000000000001",
        "date": datetime(2026, 11, 4, tzinfo=timezone.utc),
        "church_type": "DCLM",
        "program_domain": "Weekly",
        "program_type": "Workers Meeting",
        **extra,
    }


@pytest.mark.parametrize("schema", [CountCreate, RecordCreate, OfferingCreate, WorkerAttendanceCreate])
def test_eventless_program_data_requires_program_level(schema):
    values = _routine_context()
    if schema is RecordCreate:
        values.update(record_type="convert", name="Test Person", gender="Female", phone="000")
    elif schema is OfferingCreate:
        values.update(amount="10.00", payment_method="cash")
    elif schema is WorkerAttendanceCreate:
        values.update(worker_id=uuid4())

    with pytest.raises(ValidationError, match="program level"):
        schema(**values)


def test_program_level_is_persistable_for_eventless_count():
    count = CountCreate(**_routine_context(program_level="Group"))
    assert count.program_level == "Group"


@pytest.mark.parametrize(
    ("schema", "specific"),
    [
        (CountResponse, {"total": 10}),
        (RecordResponse, {"record_type": "convert", "name": "Test Person", "gender": "Female", "phone": "000"}),
        (OfferingResponse, {"amount": "10.00", "payment_method": "cash"}),
        (WorkerAttendanceResponse, {"worker_id": uuid4(), "worker_name": "Test Worker", "worker_phone": "000"}),
    ],
)
def test_legacy_eventless_responses_allow_missing_new_program_metadata(schema, specific):
    values = {
        "id": uuid4(),
        "location_id": "00000000-0000-0000-0000-000000000001",
        "path": "org.234.KW.ILR.ILE.003",
        "event_id": None,
        "date": None,
        "church_type": None,
        "program_level": None,
        "program_domain": None,
        "program_type": None,
        "status": "approved",
        "entered_by_id": uuid4(),
        **specific,
    }
    if schema is WorkerAttendanceResponse:
        values.update(status="present", worker_name="Test Worker", worker_phone="000", worker_unit=None)
    schema.model_validate(values)


def test_program_level_rejects_unknown_value():
    with pytest.raises(ValidationError):
        CountCreate(**_routine_context(program_level="Pastor"))


def test_aggregate_attendance_requires_program_level_for_eventless_capture():
    values = _routine_context(client_id=uuid4(), expected_workers_count=1,
        present_workers=[{"worker_id": uuid4(), "worker_name": "Test Worker"}])
    with pytest.raises(ValidationError, match="program metadata"):
        WorkerAttendanceSubmissionCreate(**values)
    capture = WorkerAttendanceSubmissionCreate(**values, program_level="Local")
    assert capture.program_level == "Local"


@pytest.mark.parametrize(("scope", "expected"), [
    ("location", "Local"), ("group", "Group"), ("region", "Region"),
    ("state", "State"), ("national", "National"), ("global", "Global"),
])
def test_scheduled_event_scope_is_the_program_level_authority(scope, expected):
    event = type("Event", (), {"reporting_scope": scope})()
    assert resolve_program_level(event=event) == expected


def test_mismatched_level_is_rejected_for_scheduled_event():
    event = type("Event", (), {"reporting_scope": "group"})()
    with pytest.raises(HTTPException, match="match the scheduled program reporting scope"):
        resolve_program_level(event=event, program_level="Local")
