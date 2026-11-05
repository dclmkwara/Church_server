from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError

from app.schemas.attendance import WorkerAttendanceCreate
from app.schemas.offerings import OfferingCorrection, OfferingCreate, OfferingUpdate, OfferingReversal
from app.schemas.programs import ProgramCampaignCreate, ProgramEventCreate
from app.schemas.records import RecordCreate
from app.crud.workflow_rules import validate_campaign_transition
from fastapi import HTTPException


def test_campaign_rejects_end_date_before_start_date():
    with pytest.raises(ValidationError):
        ProgramCampaignCreate(
            domain_id=1, path="church.nigeria.state", campaign_code="CRUSADE-1",
            title="Monthly Crusade", start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 1),
        )


def test_campaign_rejects_reversed_collection_window():
    with pytest.raises(ValidationError):
        ProgramCampaignCreate(
            domain_id=1, path="church.nigeria.state", campaign_code="CRUSADE-2",
            title="Monthly Crusade", start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 2),
            collection_window_start=datetime(2026, 11, 2, tzinfo=timezone.utc),
            collection_window_end=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )


def test_event_rejects_reversed_collection_window():
    with pytest.raises(ValidationError):
        ProgramEventCreate(
            program_type_id=1, date=date(2026, 11, 1), path="church.nigeria.state",
            collection_window_start=datetime(2026, 11, 2, tzinfo=timezone.utc),
            collection_window_end=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )


def test_crusade_event_requires_campaign_and_alpha_location():
    from app.api.v1.routes.programs import create_program_event
    from app.schemas.programs import ProgramEventCreate

    user = SimpleNamespace(roles=[SimpleNamespace(score_value=5, role_name="State Overseer")], user_id="u", path="org.234.KW")
    event = ProgramEventCreate(
        program_type_id=1, date=date(2026, 11, 5), path="org.234.KW",
        event_mode="crusade", reporting_scope="state",
    )

    class ScopeDB:
        async def execute(self, query):
            from sqlalchemy.dialects import postgresql
            rendered = str(query.compile(dialect=postgresql.dialect()))
            value = 3 if "nlevel" in rendered else True
            return SimpleNamespace(scalar=lambda: value)

        async def scalar(self, query):
            return 3

    with pytest.raises(HTTPException) as exc:
        __import__("asyncio").run(create_program_event(db=ScopeDB(), event_in=event, current_user=user))
    assert exc.value.status_code == 422
    assert "campaign" in exc.value.detail.lower()


def test_attendance_status_is_restricted_to_supported_values():
    with pytest.raises(ValidationError):
        WorkerAttendanceCreate(
            event_id="00000000-0000-0000-0000-000000000001",
            location_id="00000000-0000-0000-0000-000000000002",
            worker_id="00000000-0000-0000-0000-000000000003",
            status="unknown",
        )


def test_record_type_is_restricted_to_newcomer_or_convert():
    with pytest.raises(ValidationError):
        RecordCreate(
            event_id="00000000-0000-0000-0000-000000000001",
            location_id="00000000-0000-0000-0000-000000000002",
            record_type="visitor-ish", name="Person", gender="Female", phone="123",
        )


def test_offering_correction_requires_meaningful_reason():
    with pytest.raises(ValidationError):
        OfferingCorrection(amount="10.00", reason="too low")


def test_generic_offering_update_cannot_change_financial_amount():
    update = OfferingUpdate.model_validate({"amount": "1.00", "note": "memo"})
    assert update.model_dump(exclude_unset=True) == {"note": "memo"}


def test_offering_create_rejects_precision_database_would_round():
    with pytest.raises(ValidationError):
        OfferingCreate(
            event_id="00000000-0000-0000-0000-000000000001",
            location_id="00000000-0000-0000-0000-000000000002",
            amount="1.239", payment_method="cash",
        )


def test_offering_reversal_requires_meaningful_reason():
    with pytest.raises(ValidationError):
        OfferingReversal(reason="mistake")


def test_offering_reversal_normalizes_reason():
    reversal = OfferingReversal(reason="  Duplicate approved entry; bank confirmed once.  ")
    assert reversal.reason == "Duplicate approved entry; bank confirmed once."


def test_offering_reversal_is_audited_and_removes_entry_from_approved_status():
    from app.crud.crud_offerings import CRUDOffering

    entry_id, actor_id, submitter_id = uuid4(), uuid4(), uuid4()
    row = SimpleNamespace(
        id=entry_id, is_deleted=False, path="church.nigeria.state.location", status="approved",
        entered_by_id=submitter_id, amount="150.00", payment_method="cash", fund_type="offering",
        note=None, reviewed_by_id=submitter_id, reviewed_at=datetime.now(timezone.utc), review_note=None,
    )
    result = SimpleNamespace(scalar_one_or_none=lambda: row)
    db = SimpleNamespace(
        execute=AsyncMock(return_value=result), add=Mock(), commit=AsyncMock(), refresh=AsyncMock(),
    )
    crud = CRUDOffering(None)

    reversed_row = __import__("asyncio").run(crud.reverse(
        db, offering_id=entry_id, actor_id=actor_id, scope_path="church.nigeria.state",
        reason="Duplicate entry confirmed against the bank statement.",
    ))

    assert reversed_row.status == "reversed"
    db.commit.assert_awaited_once()
    audit = db.add.call_args.args[0]
    assert audit.action == "reversed"
    assert audit.before_values["status"] == "approved"
    assert audit.after_values["status"] == "reversed"


def test_offering_correction_has_distinct_state_and_audit_record():
    from app.crud.crud_offerings import CRUDOffering

    row = SimpleNamespace(
        id=uuid4(), is_deleted=False, path="church.nigeria.state.location", status="approved",
        amount="100.00", payment_method="cash", fund_type="offering", note=None,
        reviewed_by_id=uuid4(), reviewed_at=datetime.now(timezone.utc), review_note="Checked",
    )
    result = SimpleNamespace(scalar_one_or_none=lambda: row)
    db = SimpleNamespace(execute=AsyncMock(return_value=result), add=Mock(), commit=AsyncMock(), refresh=AsyncMock())

    corrected = __import__("asyncio").run(CRUDOffering(None).correct(
        db, offering_id=row.id, actor_id=uuid4(), scope_path="church.nigeria.state",
        correction=OfferingCorrection(amount="120.00", reason="Correction from signed treasurer ledger."),
    ))

    assert corrected.status == "corrected"
    audit = db.add.call_args.args[0]
    assert audit.action == "corrected"
    assert audit.before_values["status"] == "approved"
    assert audit.after_values["status"] == "corrected"


def test_only_approved_finance_entries_can_be_reversed():
    from app.crud.crud_offerings import CRUDOffering

    row = SimpleNamespace(id=uuid4(), is_deleted=False, path="church.nigeria.state", status="pending")
    result = SimpleNamespace(scalar_one_or_none=lambda: row)
    db = SimpleNamespace(execute=AsyncMock(return_value=result))

    with pytest.raises(HTTPException) as exc:
        __import__("asyncio").run(CRUDOffering(None).reverse(
            db, offering_id=row.id, actor_id=uuid4(), scope_path="church.nigeria.state",
            reason="Duplicate entry confirmed against the bank statement.",
        ))

    assert exc.value.status_code == 409


def test_reversed_finance_entry_is_terminal_for_corrections():
    from app.crud.crud_offerings import CRUDOffering

    row = SimpleNamespace(id=uuid4(), is_deleted=False, path="church.nigeria.state", status="reversed")
    result = SimpleNamespace(scalar_one_or_none=lambda: row)
    db = SimpleNamespace(execute=AsyncMock(return_value=result), add=Mock(), commit=AsyncMock())

    with pytest.raises(HTTPException) as exc:
        __import__("asyncio").run(CRUDOffering(None).correct(
            db, offering_id=row.id, actor_id=uuid4(), scope_path="church.nigeria.state",
            correction=OfferingCorrection(amount="12.00", reason="Corrected after checking the official bank statement."),
        ))

    assert exc.value.status_code == 409
    db.commit.assert_not_awaited()


def test_campaign_cannot_be_reopened_after_close():
    with pytest.raises(HTTPException):
        validate_campaign_transition("closed", "active")


def test_archived_campaign_is_terminal():
    with pytest.raises(HTTPException):
        validate_campaign_transition("archived", "active")
