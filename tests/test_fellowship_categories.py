from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.crud.crud_fellowship_activities import fellowship_attendance_total
from app.frontend.dclm_admin.communication import fellowship_service
from app.frontend.dclm_admin.communication.fellowship_service import FellowshipService
from app.models.fellowship_activities import FellowshipAttendance
from app.schemas.fellowship_activities import FellowshipAttendanceCreate


def test_fellowship_attendance_total_uses_six_categories_when_supplied():
    submission = FellowshipAttendanceCreate(
        fellowship_id="11111111-1111-4111-8111-111111111111",
        date=datetime(2026, 11, 8),
        adult_male=10,
        adult_female=12,
        youth_male=3,
        youth_female=4,
        boys=5,
        girls=6,
    )

    assert fellowship_attendance_total(submission) == 40
    assert all(name in FellowshipAttendance.__table__.c for name in (
        "adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls"
    ))


def test_fellowship_attendance_total_preserves_legacy_payload_meaning():
    submission = FellowshipAttendanceCreate(
        fellowship_id="11111111-1111-4111-8111-111111111111",
        date=datetime(2026, 11, 8),
        men=9,
        women=8,
        youths=7,
        children=6,
    )

    assert fellowship_attendance_total(submission) == 30


@pytest.mark.asyncio
async def test_fellowship_list_uses_one_aggregate_api_page_without_per_fellowship_fetches(monkeypatch):
    fake = SimpleNamespace(
        list_fellowships=AsyncMock(return_value=[{
            "fellowship_id": "11111111-1111-4111-8111-111111111111",
            "fellowship_name": "North Fellowship",
            "location_id": "22222222-2222-4222-8222-222222222222",
            "location_name": "North Location",
            "path": "org.kw.region.group.location.fellowship",
            "formatted_id": "F001",
            "active_member_count": 8,
            "last_attendance_total": 21,
            "latest_offering_amount": 1000,
            "open_prayer_count": 2,
        }]),
    )
    monkeypatch.setattr(fellowship_service, "get_api_client", lambda: fake)
    monkeypatch.setattr(fellowship_service, "async_client", lambda client: client)
    monkeypatch.setattr(FellowshipService, "_token", staticmethod(lambda request: "test-token"))
    fellowship_service.invalidate_ttl_prefix(("fellowship", "rows", "aggregate"))

    request = SimpleNamespace(state=SimpleNamespace())
    rows = await FellowshipService.list_fellowships(request, SimpleNamespace())

    assert len(rows) == 1
    assert rows[0]["member_count"] == 8
    assert rows[0]["last_attendance"] == 21
    assert rows[0]["last_offering"] == 1000
    assert rows[0]["open_prayers"] == 2
    fake.list_fellowships.assert_awaited_once()
