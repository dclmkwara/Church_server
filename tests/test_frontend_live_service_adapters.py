from __future__ import annotations

import asyncio
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.frontend.dclm_admin.communication import church_data_service, communication_service, people_service
from app.frontend.dclm_admin.communication.church_data_service import ChurchDataService
from app.frontend.dclm_admin.communication.dashboard_service import DashboardService
from app.frontend.dclm_admin.communication.communication_service import CommunicationService
from app.frontend.dclm_admin.communication.people_service import PeopleService
from app.frontend.dclm_admin.communication.program_service import ProgramService
from app.frontend.dclm_admin.communication.report_service import ReportService
from app.frontend.dclm_admin.communication.system_service import SystemService
from app.frontend.dclm_admin.communication.workflow_service import WorkflowService
from app.frontend.dclm_admin.communication.api_client import APIClient


class _FakeRequest:
    def __init__(self):
        self.state = SimpleNamespace()


def test_api_client_forwards_offering_page_offset_to_backend():
    backend = SimpleNamespace(list_offerings=AsyncMock(return_value=[]))
    client = object.__new__(APIClient)
    client._backend_client = backend

    asyncio.run(client.list_offerings("token", scope_path="org.234.KW", skip=500, limit=500))

    backend.list_offerings.assert_awaited_once_with(
        "token", scope_path="org.234.KW", fund_type=None, location_id=None, skip=500, limit=500,
    )


def test_offering_normalization_uses_service_date_not_creation_date_and_keeps_lagos_day():
    normalized = church_data_service._normalize_offering(
        {
            "id": "offering-1",
            "date": "2057-02-03T23:00:00Z",
            "created_at": "2026-11-11T11:09:53Z",
            "amount": "100.00",
            "status": "pending",
        },
        event_map={},
        location_map={},
    )

    assert normalized["date"] == "2057-02-04"
    assert normalized["entry_date"] == "2057-02-04"


def test_count_normalization_keeps_lagos_occurrence_day():
    normalized = church_data_service._normalize_count(
        {"id": "count-1", "date": "2057-02-03T23:00:00Z", "total": 1},
        event_map={},
        location_map={},
    )

    assert normalized["date"] == "2057-02-04"


def test_people_service_exposes_location_details_for_fellowship_view(monkeypatch):
    backend = SimpleNamespace(get_location_details=AsyncMock(return_value={
        "location_id": "location-1", "location_name": "Sample Location",
        "group_name": "Sample Group", "region_name": "Sample Region",
    }))
    monkeypatch.setattr(people_service.PeopleService, "use_mock", AsyncMock(return_value=False))
    monkeypatch.setattr(people_service, "async_client", lambda _client: backend)
    monkeypatch.setattr(people_service, "get_api_client", lambda: object())
    monkeypatch.setattr(people_service.AuthService, "get_access_token", lambda _request: "token")

    result = people_service.PeopleService.get_location_details(_FakeRequest(), "location-1")

    assert result["location_name"] == "Sample Location"
    assert result["group_name"] == "Sample Group"
    backend.get_location_details.assert_awaited_once_with("token", "location-1")


def test_dashboard_attendance_adapter_preserves_decimal_rate_and_zero_report(monkeypatch):
    monkeypatch.setattr(
        DashboardService,
        "_bootstrap_section",
        AsyncMock(return_value={"expected": 26, "present": 8, "absent": 18, "late": 0, "excused": 0, "rate": 30.8, "opportunities": 26}),
    )

    result = DashboardService.attendance_summary_section(_FakeRequest(), SimpleNamespace())

    assert result["rate"] == 30.8
    assert result["present"] == 8
    assert result["opportunities"] == 26


def test_dashboard_attendance_adapter_keeps_no_submission_distinct(monkeypatch):
    monkeypatch.setattr(
        DashboardService,
        "_bootstrap_section",
        AsyncMock(return_value={"expected": 0, "present": 0, "absent": 0, "late": 0, "excused": 0, "rate": 0, "opportunities": 0}),
    )

    result = DashboardService.attendance_summary_section(_FakeRequest(), SimpleNamespace())

    assert result["opportunities"] == 0
    assert result["present"] == 0


def test_sunday_worship_dashboard_adapter_forwards_selected_occurrence_date():
    from app.frontend.dclm_admin.backend.client import BackendClient

    client = BackendClient()
    client._request = AsyncMock(return_value={"occurrence_date": "2026-10-25"})

    result = asyncio.run(client.get_dashboard_sunday_worship(
        "token",
        scope_path="org.234.KW",
        occurrence_date="2026-10-25",
    ))

    assert result["occurrence_date"] == "2026-10-25"
    client._request.assert_awaited_once_with(
        "GET",
        "/dashboard/sunday-worship",
        access_token="token",
        params={"include_pending": False, "scope_path": "org.234.KW", "occurrence_date": "2026-10-25"},
    )


def test_standing_program_series_adapter_keeps_scope_period_and_pending_filter():
    from app.frontend.dclm_admin.backend.client import BackendClient

    client = BackendClient()
    client._request = AsyncMock(return_value={"program_type": "monday_bible_study"})
    result = asyncio.run(client.get_standing_program_series(
        "token", scope_path="org.234.KW.R1", program_key="monday_bible_study",
        weeks=8, latest_date="2026-11-02", include_pending=True,
    ))

    assert result["program_type"] == "monday_bible_study"
    client._request.assert_awaited_once_with(
        "GET", "/analytics/standing-programs/series", access_token="token",
        params={"scope_path": "org.234.KW.R1", "program_key": "monday_bible_study", "weeks": 8, "include_pending": True, "latest_date": "2026-11-02"},
    )


def test_finance_window_excludes_pending_by_default_and_never_counts_rejected():
    from app.frontend.dclm_admin.routes.church_data import _finance_rows_in_view, _finance_summary_for_rows

    rows = [
        {"date": "2026-11-01", "status": "approved"},
        {"date": "2026-11-02", "status": "pending"},
        {"date": "2026-11-03", "status": "rejected"},
        {"date": "2026-10-01", "status": "approved"},
    ]
    official = _finance_rows_in_view(rows, date_from="2026-11-01", date_to="2026-11-08")
    inclusive = _finance_rows_in_view(rows, date_from="2026-11-01", date_to="2026-11-08", include_pending=True)
    assert [row["status"] for row in official] == ["approved"]
    assert [row["status"] for row in inclusive] == ["approved", "pending"]
    summary = _finance_summary_for_rows(rows, date_from="2026-11-01", date_to="2026-11-08")
    assert summary["approved_total"] == 0
    assert summary["approved_count"] == 1
    assert summary["pending_count"] == 1
    assert summary["rejected_count"] == 1


def test_newcomer_person_details_are_hidden_at_state_and_region_but_available_at_group_and_location(monkeypatch):
    from starlette.requests import Request
    from fasthtml.common import Div
    from app.frontend.dclm_admin.app_factory import app as frontend_app
    from app.frontend.dclm_admin.routes import church_data as church_data_routes
    from app.frontend.dclm_admin.backend.config import get_backend_config

    monkeypatch.setenv("DCLM_ADMIN_DATA_MODE", "mock")
    get_backend_config.cache_clear()
    monkeypatch.setattr(DashboardService, "newcomer_analytics", staticmethod(AsyncMock(return_value={"newcomers_total": 4, "converts_total": 2, "male": 3, "female": 3})))
    monkeypatch.setattr(church_data_routes, "_scope_locations", AsyncMock(return_value=[]))
    monkeypatch.setattr(church_data_routes, "_records_workspace", AsyncMock(return_value=Div("PRIVATE PERSON 09123456789")))
    route = next(route for route in frontend_app.routes if getattr(route, "path", None) == "/church-data/newcomers/content")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    outputs = {}
    for persona in ("state_overseer", "region_pastor", "group_pastor", "location_pastor"):
        request = Request({
            "type": "http", "method": "GET", "path": "/church-data/newcomers/content",
            "headers": [], "query_string": f"profile={persona}".encode(), "path_params": {}, "app": frontend_app,
        }, receive)
        response = asyncio.run(route.endpoint(request))
        outputs[persona] = response.body.decode()

    for persona in ("state_overseer", "region_pastor"):
        assert "PRIVATE PERSON" not in outputs[persona]
        assert "person-level names and contact details" in outputs[persona].lower()
    for persona in ("group_pastor", "location_pastor"):
        assert "PRIVATE PERSON" in outputs[persona]


def test_sunday_worship_series_adapter_uses_one_grouped_endpoint():
    from app.frontend.dclm_admin.backend.client import BackendClient

    client = BackendClient()
    client._request = AsyncMock(return_value={"scope": [], "children": []})
    result = asyncio.run(client.get_dashboard_sunday_worship_series(
        "token", scope_path="org.234.KW", weeks=8, latest_date="2026-11-01",
    ))

    assert result == {"scope": [], "children": []}
    client._request.assert_awaited_once_with(
        "GET", "/dashboard/sunday-worship/series", access_token="token",
        params={"weeks": 8, "include_pending": False, "scope_path": "org.234.KW", "latest_date": "2026-11-01"},
    )


def _event_location_maps(monkeypatch):
    async def maps(_request, _ctx):
        return ({"evt-1": {"event_id": "evt-1", "title": "Sunday Service", "date": "2026-11-01"}},
                {"loc-1": {"location_id": "loc-1", "location_name": "Central Location"}})

    monkeypatch.setattr(church_data_service, "_event_and_location_maps", maps)


def _setup_client(monkeypatch, module, client):
    monkeypatch.setattr(module, "get_api_client", lambda: client)
    monkeypatch.setattr(module.AuthService, "get_access_token", lambda _request: "test-token")


def test_worker_create_and_account_state_transitions_call_matching_backend_operations(monkeypatch):
    worker = {"worker_id": "worker-1", "name": "Test Worker", "location_id": "loc-1", "status": "Active", "approval_status": "approved"}
    user = {"user_id": "user-1", "worker_id": "worker-1", "name": "Test User", "is_active": True, "roles": []}
    client = SimpleNamespace(
        approve_worker=AsyncMock(return_value=worker),
        reject_worker=AsyncMock(return_value=worker), approve_user=AsyncMock(return_value=user),
        reject_user=AsyncMock(return_value=user), deactivate_user=AsyncMock(return_value=user),
        reactivate_user=AsyncMock(return_value=user),
    )
    _setup_client(monkeypatch, people_service, client)
    monkeypatch.setattr(PeopleService, "use_mock", AsyncMock(return_value=False))

    async def run():
        await PeopleService.approve_worker(_FakeRequest(), "worker-1")
        await PeopleService.reject_worker(_FakeRequest(), "worker-1", "duplicate")
        await PeopleService.approve_user(_FakeRequest(), "user-1")
        await PeopleService.reject_user(_FakeRequest(), "user-1", "unverified")
        await PeopleService.deactivate_user(_FakeRequest(), "user-1", "left role")
        await PeopleService.reactivate_user(_FakeRequest(), "user-1")

    asyncio.run(run())

    client.approve_worker.assert_awaited_once_with("test-token", "worker-1")
    client.reject_worker.assert_awaited_once_with("test-token", "worker-1", "duplicate")
    client.approve_user.assert_awaited_once_with("test-token", "user-1")
    client.reject_user.assert_awaited_once_with("test-token", "user-1", "unverified")
    client.deactivate_user.assert_awaited_once_with("test-token", "user-1", "left role")
    client.reactivate_user.assert_awaited_once_with("test-token", "user-1")


def test_media_gallery_and_item_delete_use_correct_client_methods(monkeypatch):
    gallery = {"id": "gallery-1", "title": "Retreat", "path": "A0001", "is_public": False, "items": []}
    item = {"id": "item-1", "gallery_id": "gallery-1", "file_name": "photo.jpg", "file_type": "image/jpeg"}
    client = SimpleNamespace(get_media_gallery=AsyncMock(return_value=gallery), delete_media_gallery=AsyncMock(return_value=None),
                             delete_media_item=AsyncMock(return_value=None), list_media_galleries=AsyncMock(return_value=[gallery]))
    _setup_client(monkeypatch, communication_service, client)
    monkeypatch.setattr(CommunicationService, "use_mock", AsyncMock(return_value="test-token"))
    monkeypatch.setattr(CommunicationService, "list_media_items", AsyncMock(return_value=[{
        "item_id": "item-1", "gallery_id": "gallery-1", "title": "photo.jpg", "media_type": "photo",
        "caption": "", "file_label": "photo.jpg", "gallery_title": "Retreat", "gallery_visibility": "scope_only",
        "uploaded_at": "", "uploaded_by": "", "path": "A0001",
    }]))

    async def run():
        await CommunicationService.delete_gallery(_FakeRequest(), SimpleNamespace(current_scope_path="A0001"), "gallery-1")
        await CommunicationService.delete_media_item(_FakeRequest(), SimpleNamespace(current_scope_path="A0001"), "item-1")

    asyncio.run(run())

    client.delete_media_gallery.assert_awaited_once_with("test-token", "gallery-1")
    client.delete_media_item.assert_awaited_once_with("test-token", "item-1")


def test_live_service_signatures_match_route_operations():
    import inspect

    assert list(inspect.signature(ChurchDataService.list_records).parameters)[:2] == ["request", "ctx"]
    assert list(inspect.signature(PeopleService.create_user_account).parameters) == ["request", "payload"]
    assert list(inspect.signature(ProgramService.create_assignment).parameters) == ["request", "ctx", "event_id", "payload"]
    assert list(inspect.signature(CommunicationService.create_gallery).parameters) == ["request", "ctx", "payload"]
    assert list(inspect.signature(WorkflowService.list_requests).parameters) == ["request", "ctx", "request_type", "status", "mine_only", "review_only"]
    assert list(inspect.signature(WorkflowService.get_request).parameters) == ["request", "ctx", "request_token"]
    assert list(inspect.signature(WorkflowService.act_request).parameters) == ["request", "ctx", "request_token", "action", "notes"]
    assert list(inspect.signature(WorkflowService.list_inbox).parameters) == ["request", "ctx", "kind"]
    assert list(inspect.signature(WorkflowService.pending_item_count).parameters) == ["request", "ctx"]
    assert list(inspect.signature(WorkflowService.resolve_inbox_item).parameters) == ["request", "ctx", "item_id"]
    assert list(inspect.signature(WorkflowService.act_inbox_item).parameters) == ["request", "ctx", "item_id", "action", "notes"]


def test_count_summary_combines_usher_sections_but_preserves_source_rows(monkeypatch):
    rows = [
        {"event_id": "evt-1", "event_title": "Sunday Service", "date": "2026-11-01", "location_id": "loc-1", "location": "Central", "total": 40},
        {"event_id": "evt-1", "event_title": "Sunday Service", "date": "2026-11-01", "location_id": "loc-1", "location": "Central", "total": 35},
        {"event_id": "evt-2", "event_title": "Monday Service", "date": "2026-11-02", "location_id": "loc-1", "location": "Central", "total": 20},
    ]
    monkeypatch.setattr(church_data_service, "_list_count_submissions_public", AsyncMock(return_value=rows))
    monkeypatch.setattr(ChurchDataService, "use_mock", AsyncMock(return_value=False))

    summary = asyncio.run(church_data_service._count_summary_public(_FakeRequest(), SimpleNamespace()))

    assert summary == {"latest_total": 20, "monthly_total": 95, "locations_reporting": 1, "average_total": 48}
    assert len(rows) == 3


def test_finance_summary_excludes_pending_and_rejected_from_approved_totals(monkeypatch):
    from app.frontend.dclm_admin.communication import church_data_service

    today = date.today().isoformat()
    current_month = today[:7]
    rows = [
        {"amount": 120.5, "status": "approved", "entry_date": f"{current_month}-01", "date": f"{current_month}-01"},
        {"amount": 70, "status": "pending", "entry_date": today, "date": today},
        {"amount": 15, "status": "corrected", "entry_date": today, "date": today},
        {"amount": 900, "status": "rejected", "entry_date": today, "date": today},
        {"amount": 45, "status": "approved", "entry_date": "2020-01-01", "date": "2020-01-01"},
    ]
    monkeypatch.setattr(church_data_service, "_list_finance_public", AsyncMock(return_value=rows))
    monkeypatch.setattr(ChurchDataService, "use_mock", AsyncMock(return_value=False))

    summary = asyncio.run(church_data_service._finance_summary_public(_FakeRequest(), SimpleNamespace()))

    assert summary["month_total"] == 120.5
    assert summary["year_total"] == 120.5
    assert summary["pending_total"] == 85
    assert summary["pending_count"] == 1
    assert summary["corrected_count"] == 1
    assert summary["rejected_count"] == 1
    assert summary["approved_count"] == 2
    assert summary["month_approved_count"] == 1


def test_money_format_preserves_cents_without_changing_whole_amounts():
    from decimal import Decimal

    from app.frontend.dclm_admin.components.ui import format_naira

    assert format_naira(Decimal("120.50")) == "N120.50"
    assert format_naira(120) == "N120"


def test_finance_mutations_invalidate_report_and_dashboard_caches(monkeypatch):
    from app.frontend.dclm_admin.communication import church_data_service

    reviewed = {"id": "offering-1", "amount": "25.00", "status": "approved"}
    client = SimpleNamespace(
        review_offering=AsyncMock(return_value=reviewed),
        correct_offering=AsyncMock(return_value=reviewed),
        reverse_offering=AsyncMock(return_value=reviewed),
    )
    invalidated = []
    monkeypatch.setattr(church_data_service, "get_api_client", lambda: client)
    monkeypatch.setattr(church_data_service.AuthService, "get_access_token", lambda _request: "token")
    monkeypatch.setattr(ChurchDataService, "use_mock", AsyncMock(return_value=False))
    monkeypatch.setattr(church_data_service, "invalidate_ttl_prefix", invalidated.append)

    async def run():
        request = _FakeRequest()
        await ChurchDataService.review_finance(request, "offering-1", decision="approved")
        await ChurchDataService.correct_finance(request, "offering-1", {"reason": "A valid correction reason for this entry."})
        await ChurchDataService.reverse_finance(request, "offering-1", "A valid reversal reason for this entry.")

    asyncio.run(run())

    assert invalidated == [
        ("reports",), ("dashboard", "bootstrap"),
        ("reports",), ("dashboard", "bootstrap"),
        ("reports",), ("dashboard", "bootstrap"),
    ]


def test_announcement_ttl_cache_isolated_by_user_and_effective_scope(monkeypatch):
    from app.frontend.dclm_admin.communication import communication_service
    from app.frontend.dclm_admin.communication.ttl_cache import invalidate_ttl_prefix

    invalidate_ttl_prefix(("communication", "announcements"))
    client = SimpleNamespace(list_announcements=AsyncMock(side_effect=[
        [{"id": "state-item", "region_name": "State", "meeting": "special_notice", "date": "2026-11-02", "items": [{"title": "State notice", "text": "State only"}]}],
        [{"id": "region-item", "region_name": "Region", "meeting": "special_notice", "date": "2026-11-02", "items": [{"title": "Region notice", "text": "Region only"}]}],
    ]))
    _setup_client(monkeypatch, communication_service, client)
    monkeypatch.setattr(CommunicationService, "use_mock", AsyncMock(side_effect=lambda request: request.state.identity.user_id))
    monkeypatch.setattr(communication_service.AuthService, "get_identity", lambda request: request.state.identity)
    first_request, second_request = _FakeRequest(), _FakeRequest()
    first_request.state.identity = SimpleNamespace(user_id="user-state", scope_path="church.nigeria.state")
    second_request.state.identity = SimpleNamespace(user_id="user-region", scope_path="church.nigeria.state.region")

    async def run():
        first = await CommunicationService.list_announcements(first_request, SimpleNamespace(current_scope_path=""))
        second = await CommunicationService.list_announcements(second_request, SimpleNamespace(current_scope_path=""))
        return first, second

    first, second = asyncio.run(run())

    assert first[0]["title"] == "State notice"
    assert second[0]["title"] == "Region notice"
    assert client.list_announcements.await_count == 2
    invalidate_ttl_prefix(("communication", "announcements"))


def test_finance_list_fetches_all_backend_pages(monkeypatch):
    from app.frontend.dclm_admin.communication import church_data_service

    pages = [[{"id": str(index), "status": "pending", "amount": "1.00"} for index in range(500)], [{"id": "last", "status": "approved", "amount": "2.00"}]]
    client = SimpleNamespace(list_offerings=AsyncMock(side_effect=pages))
    _setup_client(monkeypatch, church_data_service, client)
    monkeypatch.setattr(ChurchDataService, "use_mock", AsyncMock(return_value=False))
    monkeypatch.setattr(church_data_service, "_church_data_scope_path", AsyncMock(return_value="dcl.234"))
    monkeypatch.setattr(church_data_service, "_event_and_location_maps", AsyncMock(return_value=({}, {})))

    rows = asyncio.run(church_data_service._list_finance_public(_FakeRequest(), SimpleNamespace(current_scope_path="dcl.234")))

    assert len(rows) == 501
    assert client.list_offerings.await_args_list[0].kwargs == {"scope_path": "dcl.234", "skip": 0, "limit": 500}
    assert client.list_offerings.await_args_list[1].kwargs == {"scope_path": "dcl.234", "skip": 500, "limit": 500}


def test_pagination_helper_fetches_all_pages_and_propagates_page_errors():
    from app.frontend.dclm_admin.communication.pagination import fetch_all_pages
    from app.frontend.dclm_admin.backend import BackendClientError

    calls = []
    async def fetch(skip, limit):
        calls.append((skip, limit))
        if skip == 0:
            return [{"id": str(i)} for i in range(limit)]
        return [{"id": "last"}]

    async def run():
        rows = await fetch_all_pages(fetch, page_size=3)
        assert [row["id"] for row in rows] == ["0", "1", "2", "last"]
        assert calls == [(0, 3), (3, 3)]

        async def broken(skip, limit):
            if skip:
                raise BackendClientError("second page unavailable")
            return [{"id": str(i)} for i in range(limit)]
        try:
            await fetch_all_pages(broken, page_size=2)
        except BackendClientError as exc:
            assert "second page" in str(exc)
        else:
            raise AssertionError("page failures must not be represented as a complete result")

    asyncio.run(run())


def test_finance_drawer_exposes_actions_only_for_granted_finance_permissions(monkeypatch):
    from starlette.requests import Request

    from app.frontend.dclm_admin.routes import church_data as church_data_routes
    from app.frontend.dclm_admin.app_factory import app as frontend_app

    permission_set = {"offerings:read", "offerings:review", "offerings:update"}
    monkeypatch.setattr(church_data_routes, "build_context", lambda _request: SimpleNamespace(
        has_permission=lambda permission: permission in permission_set,
        url_for=lambda path: path,
    ))
    monkeypatch.setattr(ChurchDataService, "live_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(ChurchDataService, "get_finance_entry", AsyncMock(return_value={
        "entry_id": "offering-1", "event_title": "Sunday Service", "location": "Central",
        "date": date.today().isoformat(), "entry_date": date.today().isoformat(), "amount": 50.0,
        "fund_type": "offering", "method": "Cash", "status": "pending", "submitted_by": "user-2",
        "entered_by_id": "user-2", "reviewed_by_id": "", "reviewed_at": "", "review_note": "",
        "notes": "", "created_at": "",
    }))
    monkeypatch.setattr(ChurchDataService, "finance_audit_history", AsyncMock(return_value=[]))
    route = next(route for route in frontend_app.routes if getattr(route, "path", None) == "/church-data/finance/{entry_id}/drawer")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request({"type": "http", "method": "GET", "path": "/church-data/finance/offering-1/drawer", "headers": [], "query_string": b"", "path_params": {"entry_id": "offering-1"}, "app": frontend_app}, receive)
    rendered = asyncio.run(route.endpoint(request)).body.decode()
    assert "Approve" in rendered and "Reject" in rendered
    assert "Correct entry" in rendered
    assert "Reverse approved entry" not in rendered

    permission_set.clear()
    rendered_without_permissions = asyncio.run(route.endpoint(request)).body.decode()
    assert "Approve" not in rendered_without_permissions
    assert "Correct entry" not in rendered_without_permissions


def test_count_aggregates_keep_event_date_and_location_grain():
    from app.frontend.dclm_admin.communication.count_aggregation import aggregate_count_submissions

    source = [
        {"count_id": "a", "event_id": "event-a", "event_title": "Sunday Service", "date": "2026-11-01", "location_id": "loc-1", "location": "Central", "total": 40, "usher_section": "North"},
        {"count_id": "b", "event_id": "event-a", "event_title": "Sunday Service", "date": "2026-11-01", "location_id": "loc-1", "location": "Central", "total": 35, "usher_section": "South"},
        {"count_id": "c", "event_id": "event-b", "event_title": "Evening Service", "date": "2026-11-01", "location_id": "loc-1", "location": "Central", "total": 12, "usher_section": "Main"},
        {"count_id": "d", "event_id": "event-a", "event_title": "Sunday Service", "date": "2026-11-01", "location_id": "loc-2", "location": "North", "total": 15, "usher_section": "Main"},
    ]
    groups = aggregate_count_submissions(source)
    assert {(row["event_id"], row["date"], row["location_id"], row["total"], row["submissions"]) for row in groups} == {
        ("event-a", "2026-11-01", "loc-1", 75, 2),
        ("event-b", "2026-11-01", "loc-1", 12, 1),
        ("event-a", "2026-11-01", "loc-2", 15, 1),
    }
    assert len(groups[0]["source_rows"]) == 1
    assert sum(len(group["source_rows"]) for group in groups) == len(source)


def test_rbac_read_and_update_adapters_call_matching_backend_methods(monkeypatch):
    role = {"id": 7, "role_name": "Test Role", "score_id": 3, "score_value": 3, "permissions": [{"id": 2, "permission": "reports:read", "name": "Read Reports"}]}
    permission = {"id": 2, "permission": "reports:read", "name": "Read Reports"}
    client = SimpleNamespace(
        list_rbac_roles=AsyncMock(return_value=[role]),
        list_rbac_permissions=AsyncMock(return_value=[permission]),
        get_rbac_role=AsyncMock(return_value=role),
        get_rbac_permission=AsyncMock(return_value=permission),
        update_rbac_role=AsyncMock(return_value=role),
    )
    from app.frontend.dclm_admin.communication import system_service

    _setup_client(monkeypatch, system_service, client)
    monkeypatch.setattr(SystemService, "live_enabled", AsyncMock(return_value=True))

    async def run():
        roles = await SystemService.list_rbac_roles(_FakeRequest())
        permissions = await SystemService.list_rbac_permissions(_FakeRequest(), family="reports")
        found_role = await SystemService.get_rbac_role(_FakeRequest(), "7")
        found_permission = await SystemService.get_rbac_permission(_FakeRequest(), "2")
        updated = await SystemService.update_rbac_role(_FakeRequest(), "7", description="Updated", permission_ids=[2])
        return roles, permissions, found_role, found_permission, updated

    roles, permissions, found_role, found_permission, updated = asyncio.run(run())
    assert roles[0]["name"] == "Test Role"
    assert permissions[0]["key"] == "reports:read"
    assert found_role["role_id"] == "7"
    assert found_permission["permission_id"] == "2"
    assert updated is None
    client.list_rbac_roles.assert_awaited_once()
    client.list_rbac_permissions.assert_awaited_once()
    assert client.get_rbac_role.await_count == 1
    client.get_rbac_role.assert_any_await("test-token", "7")
    client.get_rbac_permission.assert_awaited_once_with("test-token", "2")
    client.update_rbac_role.assert_not_awaited()


def test_workflow_adapters_call_their_named_backend_operations(monkeypatch):
    from app.frontend.dclm_admin.communication import workflow_service

    client = SimpleNamespace(
        list_transfer_requests=AsyncMock(return_value=[]),
        list_status_change_requests=AsyncMock(return_value=[]),
        list_removal_requests=AsyncMock(return_value=[]),
        list_pending_workers=AsyncMock(return_value=[]),
        list_pending_users=AsyncMock(return_value=[]),
    )
    _setup_client(monkeypatch, workflow_service, client)
    monkeypatch.setattr(WorkflowService, "use_mock", AsyncMock(return_value=False))
    monkeypatch.setattr(WorkflowService, "live_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(PeopleService, "effective_scope_path", AsyncMock(return_value="dcl.234.kw.ilr"))
    monkeypatch.setattr(workflow_service, "_worker_maps", AsyncMock(return_value=({}, {})))

    async def run():
        ctx = SimpleNamespace(current_scope_path="dcl.234.kw.ilr", profile=SimpleNamespace(user_name="Pastor"))
        request = _FakeRequest()
        await WorkflowService.list_requests(request, ctx)
        await WorkflowService.list_inbox(_FakeRequest(), ctx)
        await WorkflowService.pending_item_count(_FakeRequest(), ctx)

    asyncio.run(run())
    for method in (client.list_transfer_requests, client.list_status_change_requests, client.list_removal_requests):
        assert method.await_count >= 1
    assert client.list_pending_workers.await_count == 2
    assert client.list_pending_users.await_count == 2


def test_report_adapters_bind_each_view_to_the_matching_backend_endpoint(monkeypatch):
    from app.frontend.dclm_admin.communication import report_service

    client = SimpleNamespace(
        get_report_summary=AsyncMock(return_value=[{"day": "2026-11-01", "event_id": "evt-1", "event_title": "Sunday Service", "location_id": "loc-1", "total_attendance": 75, "record_count": 2}]),
        get_report_financial=AsyncMock(return_value=[{"month": "2026-11-01T00:00:00", "location_id": "loc-1", "total_amount": "300.00", "transaction_count": 2}]),
        get_report_attendance=AsyncMock(return_value=[{"week": "2026-11-02T00:00:00", "location_id": "loc-1", "status": "present", "worker_count": 12}]),
        get_report_timeseries=AsyncMock(return_value={"data": [{"date": "2026-11-01", "value": 75}]}),
        get_report_breakdown=AsyncMock(return_value={"breakdown": [{"path": "dcl.234.kw.ilr.ile", "total": 75}]}),
        get_report_growth=AsyncMock(return_value={"data": [{"period": "2026-W44", "value": 75, "growth_rate": 4.5}]}),
        get_report_anomalies=AsyncMock(return_value={"anomalies": [{"date": "2026-11-01", "location": "Central", "value": 75}]}),
        refresh_reports=AsyncMock(return_value={"message": "refreshed"}),
        export_report_csv=AsyncMock(return_value=(b"csv", {"content-type": "text/csv", "content-disposition": "attachment; filename=test.csv"})),
        export_report_excel=AsyncMock(return_value=(b"xlsx", {"content-type": "application/octet-stream", "content-disposition": "attachment; filename=test.xlsx"})),
        export_report_pdf=AsyncMock(return_value=(b"pdf", {"content-type": "application/pdf", "content-disposition": "attachment; filename=test.pdf"})),
    )
    _setup_client(monkeypatch, report_service, client)
    monkeypatch.setattr(ReportService, "live_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(ReportService, "use_mock", AsyncMock(return_value=False))
    ctx = SimpleNamespace(current_scope_path="dcl.234.kw.ilr", current_scope_kind="region")

    async def run():
        request = _FakeRequest()
        summary = await ReportService.summary_rows(request, ctx)
        finance = await ReportService.financial_rows(request, ctx)
        attendance = await ReportService.attendance_rows(request, ctx)
        counts = await ReportService.counts_series(request, ctx)
        offerings = await ReportService.finance_series(request, ctx)
        worker_attendance = await ReportService.attendance_series(request, ctx)
        breakdown = await ReportService.breakdown_rows(request, ctx)
        growth = await ReportService.growth_rows(request, ctx)
        anomalies = await ReportService.anomaly_rows(request, ctx)
        refreshed = await ReportService.refresh(request)
        exported = await ReportService.export(request, ctx, report_type="counts", export_format="csv")
        return summary, finance, attendance, counts, offerings, worker_attendance, breakdown, growth, anomalies, refreshed, exported

    summary, finance, attendance, counts, offerings, worker_attendance, breakdown, growth, anomalies, refreshed, exported = asyncio.run(run())
    assert summary[0]["event_title"] == "Sunday Service" and summary[0]["record_count"] == 2
    assert finance[0]["transaction_count"] == 2
    assert attendance[0]["worker_count"] == 12
    assert counts == offerings == worker_attendance == [("2026-11-01", 75)]
    assert len(breakdown) == 1 and len(growth) == 1 and len(anomalies) == 1
    assert refreshed["message"] == "refreshed"
    assert exported[0] == b"csv"
    client.get_report_timeseries.assert_any_await("test-token", metric="counts", scope_path=ctx.current_scope_path, start_date=(date.today() - timedelta(days=90)).isoformat(), end_date=date.today().isoformat())
    client.get_report_timeseries.assert_any_await("test-token", metric="offerings", scope_path=ctx.current_scope_path, start_date=(date.today() - timedelta(days=90)).isoformat(), end_date=date.today().isoformat())
    client.get_report_timeseries.assert_any_await("test-token", metric="attendance", scope_path=ctx.current_scope_path, start_date=(date.today() - timedelta(days=90)).isoformat(), end_date=date.today().isoformat())
    client.get_report_breakdown.assert_any_await("test-token", metric="counts", level="group", scope_path=ctx.current_scope_path, start_date=(date.today() - timedelta(days=90)).isoformat(), end_date=date.today().isoformat())
    client.get_report_growth.assert_awaited_once_with("test-token", metric="counts", period="weekly", scope_path=ctx.current_scope_path, start_date=(date.today() - timedelta(days=90)).isoformat(), end_date=date.today().isoformat())
    client.get_report_anomalies.assert_awaited_once_with("test-token", metric="counts", scope_path=ctx.current_scope_path, start_date=(date.today() - timedelta(days=90)).isoformat(), end_date=date.today().isoformat())
    client.refresh_reports.assert_awaited_once_with("test-token")
    client.export_report_csv.assert_awaited_once()


def test_count_overview_groups_complementary_usher_rows_for_one_service(monkeypatch):
    from fasthtml.common import to_xml

    from app.frontend.dclm_admin.routes.church_data import _counts_table

    rows = [
        {
            "count_id": "count-north", "event_id": "evt-1", "event_title": "Sunday Service",
            "date": "2026-11-01", "location_id": "loc-1", "location": "Central",
            "total": 40, "usher_section": "North aisle", "submitted_by": "Usher One",
        },
        {
            "count_id": "count-south", "event_id": "evt-1", "event_title": "Sunday Service",
            "date": "2026-11-01", "location_id": "loc-1", "location": "Central",
            "total": 35, "usher_section": "South aisle", "submitted_by": "Usher Two",
        },
    ]
    monkeypatch.setattr(ChurchDataService, "live_enabled", AsyncMock(return_value=True))
    monkeypatch.setattr(ChurchDataService, "list_counts", AsyncMock(return_value=rows))
    ctx = SimpleNamespace(url_for=lambda path, **_kwargs: path)

    rendered = asyncio.run(_counts_table(_FakeRequest(), ctx))
    markup = to_xml(rendered)

    assert "Approved total" in markup
    assert "75" in markup
    assert "2 submission(s)" in markup
    assert "North aisle" in markup
    assert "South aisle" in markup
    assert len(rows) == 2


def test_admin_frontend_source_submission_routes_are_closed_before_service_calls():
    from starlette.requests import Request

    from app.frontend.dclm_admin.app_factory import app as frontend_app

    post_paths = [
        "/church-data/counts/create",
        "/church-data/finance/create",
        "/church-data/newcomers/create",
        "/church-data/attendance/create",
        "/people/workers/create",
        "/people/members/create",
        "/people/workers/import/preview",
        "/people/workers/import/commit",
        "/fellowship/{fellowship_id}/members/create",
        "/fellowship/{fellowship_id}/offerings/create",
        "/fellowship/{fellowship_id}/testimonies/create",
        "/fellowship/{fellowship_id}/prayers/create",
    ]

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    for route_path in post_paths:
        route = next(route for route in frontend_app.routes if getattr(route, "path", None) == route_path)
        actual_path = route_path.format(fellowship_id="test-fellowship")
        path_params = {"fellowship_id": "test-fellowship"} if "{fellowship_id}" in route_path else {}
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": actual_path,
                "headers": [],
                "query_string": b"",
                "path_params": path_params,
            },
            receive,
        )

        response = asyncio.run(route.endpoint(request))

        assert response.status_code == 403, route_path
        assert b"Data Sourcing app" in response.body, route_path


def test_admin_pages_keep_source_data_read_only_and_show_no_intake_actions(monkeypatch):
    from starlette.requests import Request

    from app.frontend.dclm_admin.app_factory import app as frontend_app
    from app.frontend.dclm_admin.backend.config import get_backend_config

    monkeypatch.setenv("DCLM_ADMIN_DATA_MODE", "mock")
    get_backend_config.cache_clear()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    page_paths = [
        "/church-data/counts",
        "/church-data/finance",
        "/church-data/newcomers",
        "/church-data/attendance",
        "/people/workers",
        "/people/members",
    ]
    notice_paths = [
        "/church-data/counts/content",
        "/church-data/finance/content",
        "/church-data/newcomers/content",
        "/church-data/attendance/content",
        "/people/workers",
        "/people/members",
    ]
    form_paths = [
        "/church-data/counts/new",
        "/church-data/finance/new",
        "/church-data/newcomers/new",
        "/church-data/attendance/new",
        "/people/workers/new",
        "/people/members/new",
        "/people/workers/import",
        "/fellowship/{fellowship_id}/members/new",
        "/fellowship/{fellowship_id}/offerings/new",
        "/fellowship/{fellowship_id}/testimonies/new",
        "/fellowship/{fellowship_id}/prayers/new",
    ]
    forbidden_actions = (
        "Submit Count",
        "Record Entry",
        "Add Record",
        "Mark Attendance",
        "Register Worker",
        "Add Member",
    )
    try:
        for route_path in page_paths:
            route = next(route for route in frontend_app.routes if getattr(route, "path", None) == route_path)
            request = Request(
                {
                    "type": "http",
                    "method": "GET",
                    "path": route_path,
                    "headers": [],
                    "query_string": b"profile=location_pastor",
                    "path_params": {},
                    "app": frontend_app,
                },
                receive,
            )
            response = asyncio.run(route.endpoint(request))
            body = response.body.decode()
            assert response.status_code == 200, route_path
            assert not any(action in body for action in forbidden_actions), route_path
        for route_path in notice_paths:
            route = next(route for route in frontend_app.routes if getattr(route, "path", None) == route_path)
            request = Request(
                {
                    "type": "http",
                    "method": "GET",
                    "path": route_path,
                    "headers": [],
                    "query_string": b"profile=location_pastor",
                    "path_params": {},
                    "app": frontend_app,
                },
                receive,
            )
            response = asyncio.run(route.endpoint(request))
            assert "Level 1-2 Data Sourcing app" in response.body.decode(), route_path

        for route_path in form_paths:
            route = next(route for route in frontend_app.routes if getattr(route, "path", None) == route_path)
            actual_path = route_path.format(fellowship_id="test-fellowship")
            path_params = {"fellowship_id": "test-fellowship"} if "{fellowship_id}" in route_path else {}
            request = Request(
                {
                    "type": "http",
                    "method": "GET",
                    "path": actual_path,
                    "headers": [],
                    "query_string": b"profile=location_pastor",
                    "path_params": path_params,
                    "app": frontend_app,
                },
                receive,
            )
            response = asyncio.run(route.endpoint(request))
            body = response.body.decode()
            assert "Level 1-2 Data Sourcing app" in body, route_path
            assert "<form" not in body.lower(), route_path
    finally:
        get_backend_config.cache_clear()


def test_scoped_reports_are_available_to_levels_three_to_five(monkeypatch):
    from starlette.requests import Request

    from app.frontend.dclm_admin.app_factory import app as frontend_app
    from app.frontend.dclm_admin.backend.config import get_backend_config

    monkeypatch.setenv("DCLM_ADMIN_DATA_MODE", "mock")
    get_backend_config.cache_clear()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    route = next(route for route in frontend_app.routes if getattr(route, "path", None) == "/reports")
    try:
        for profile in ("location_pastor", "group_pastor", "region_pastor"):
            request = Request(
                {
                    "type": "http",
                    "method": "GET",
                    "path": "/reports",
                    "headers": [],
                    "query_string": f"profile={profile}".encode(),
                    "path_params": {},
                    "app": frontend_app,
                },
                receive,
            )
            response = asyncio.run(route.endpoint(request))
            assert response.status_code == 200
            body = response.body.decode()
            assert "Reports unlock from Level 6" not in body
            assert "reports" in body.lower()
    finally:
        get_backend_config.cache_clear()


def test_reports_navigation_and_routes_follow_permission_not_role_score(monkeypatch):
    from starlette.requests import Request

    from app.frontend.dclm_admin.app_factory import app as frontend_app
    from app.frontend.dclm_admin.auth_context import build_context
    from app.frontend.dclm_admin.backend.config import get_backend_config

    monkeypatch.setenv("DCLM_ADMIN_DATA_MODE", "mock")
    get_backend_config.cache_clear()
    pastor = build_context({"profile": "location_pastor"})
    administrator = build_context({"profile": "location_admin"})
    assert pastor.level == administrator.level == 2
    assert "reports" in pastor.visible_modules
    assert "reports" in administrator.visible_modules

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    content_route = next(route for route in frontend_app.routes if getattr(route, "path", None) == "/reports/content")
    refresh_route = next(route for route in frontend_app.routes if getattr(route, "path", None) == "/reports/refresh")
    request = Request(
        {"type": "http", "method": "GET", "path": "/reports/content", "headers": [], "query_string": b"profile=location_admin", "path_params": {}, "app": frontend_app},
        receive,
    )
    try:
        response = asyncio.run(content_route.endpoint(request))
        assert "reports:read permission" not in response.body.decode()
        refresh_request = Request(
            {"type": "http", "method": "POST", "path": "/reports/refresh", "headers": [], "query_string": b"profile=location_admin", "path_params": {}, "app": frontend_app},
            receive,
        )
        assert asyncio.run(refresh_route.endpoint(refresh_request)).status_code == 403
    finally:
        get_backend_config.cache_clear()


def test_backend_identity_scope_and_permissions_override_browser_query(monkeypatch):
    from starlette.requests import Request

    from app.frontend.dclm_admin import auth_context

    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=True))
    identity = SimpleNamespace(
        scope_path="dcl.234.kw.ilr",
        home_path="dcl.234.kw.ilr",
        profile_key="region_pastor",
        role_score=5,
        role_name="Region Pastor",
        display_name="Test Pastor",
        permissions=frozenset({"reports:read"}),
    )
    monkeypatch.setattr(auth_context.AuthService, "get_identity", lambda _request: identity)

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/reports",
            "headers": [],
            "query_string": b"scope_path=dcl.234.kw.off&scope_kind=global&role_score=9",
            "path_params": {},
        },
        lambda: None,
    )
    context = auth_context.build_context(request)
    assert context.current_scope_path == "dcl.234.kw.ilr"
    assert context.level == 5
    assert context.has_permission("reports:read")
    assert not context.has_permission("reports:refresh")
    assert context.current_scope_kind == "region"
    assert context.current_scope_label != "global"


def test_auth_me_returns_union_of_assigned_permissions():
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.api.v1.routes.auth import read_users_me

    role_a = SimpleNamespace(id=1, role_name="Pastor", description="", score_id=3, score_value=3, permissions=[SimpleNamespace(permission="reports:read")])
    role_b = SimpleNamespace(id=2, role_name="Technical Admin", description="", score_id=3, score_value=3, permissions=[SimpleNamespace(permission="users:read")])
    user = SimpleNamespace(
        email="test@example.invalid",
        is_active=True,
        user_id=uuid4(),
        worker_id=uuid4(),
        location_id="location-1",
        name="Test User",
        phone="000",
        created_at=datetime.now(timezone.utc),
        roles=[role_a, role_b],
        path="dcl.234.kw.ilr",
        approval_status="approved",
        approved_by=None,
        approved_at=None,
        rejection_reason=None,
    )
    response = asyncio.run(read_users_me(user))
    assert response.permissions == ["reports:read", "users:read"]


def test_frontend_identity_preserves_backend_permissions_in_httponly_session_cookie(monkeypatch):
    from starlette.requests import Request
    from starlette.responses import Response

    from app.frontend.dclm_admin.backend.config import get_backend_config
    from app.frontend.dclm_admin.communication.auth_service import AuthIdentity, AuthService

    monkeypatch.setenv("DCLM_ADMIN_DATA_MODE", "backend")
    get_backend_config.cache_clear()
    identity = AuthIdentity(
        user_id="user-1", access_token="access", refresh_token="refresh",
        user={"name": "Pastor", "email": "pastor@example.invalid", "path": "dcl.234.kw.ilr", "permissions": ["reports:read", "reports:refresh"]},
        profile_key="region_pastor", role_score=5, role_name="Region Pastor",
        scope_path="dcl.234.kw.ilr", home_path="dcl.234.kw.ilr",
    )
    response = Response()
    asyncio.run(AuthService.persist_identity(response, identity))
    permission_cookie = next(cookie for cookie in response.raw_headers if cookie[0].lower() == b"set-cookie" and cookie[1].startswith(b"dclm_admin_permissions="))
    assert b"httponly" in permission_cookie[1].lower()
    cookie_value = permission_cookie[1].split(b";", 1)[0].split(b"=", 1)[1].decode()
    config = get_backend_config()
    cookies = {
        config.user_id_cookie_name: "user-1",
        config.access_cookie_name: "access",
        config.refresh_cookie_name: "refresh",
        config.profile_cookie_name: "region_pastor",
        "dclm_admin_permissions": cookie_value,
    }
    cookie_header = "; ".join(f"{key}={value}" for key, value in cookies.items()).encode()
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"cookie", cookie_header)], "query_string": b"", "path_params": {}})
    restored = AuthService.get_identity(request)
    assert restored is not None
    assert restored.permissions == frozenset({"reports:read", "reports:refresh"})
    get_backend_config.cache_clear()


def test_report_permission_denial_is_shown_as_restricted_not_empty(monkeypatch):
    from starlette.requests import Request

    from app.frontend.dclm_admin.app_factory import app as frontend_app
    from app.frontend.dclm_admin.backend import BackendClientError
    from app.frontend.dclm_admin.backend.config import get_backend_config
    from app.frontend.dclm_admin.routes import reports

    monkeypatch.setenv("DCLM_ADMIN_DATA_MODE", "mock")
    get_backend_config.cache_clear()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def denied(*args, **kwargs):
        raise BackendClientError("Forbidden", status_code=403)

    monkeypatch.setattr(reports, "_reports_content", denied)
    route = next(route for route in frontend_app.routes if getattr(route, "path", None) == "/reports/content")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/reports/content",
            "headers": [],
            "query_string": b"profile=location_pastor",
            "path_params": {},
            "app": frontend_app,
        },
        receive,
    )
    try:
        response = asyncio.run(route.endpoint(request))
        body = response.body.decode()
        assert "Access restricted" in body
        assert "permission" in body.lower()
        assert "no data" not in body.lower()
    finally:
        get_backend_config.cache_clear()


def test_level_two_cannot_refresh_or_export_reports(monkeypatch):
    from starlette.requests import Request

    from app.frontend.dclm_admin.app_factory import app as frontend_app
    from app.frontend.dclm_admin.backend.config import get_backend_config

    monkeypatch.setenv("DCLM_ADMIN_DATA_MODE", "mock")
    get_backend_config.cache_clear()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    routes = {
        route.path: route
        for route in frontend_app.routes
        if getattr(route, "path", None) in {
            "/reports/refresh",
            "/reports/export/mock",
            "/reports/export/live",
        }
    }
    try:
        for path, route in routes.items():
            request = Request(
                {
                    "type": "http",
                    "method": "POST" if path.endswith("refresh") else "GET",
                    "path": path,
                    "headers": [],
                    "query_string": b"profile=location_worker",
                    "path_params": {},
                    "app": frontend_app,
                },
                receive,
            )
            response = asyncio.run(route.endpoint(request))
            assert response.status_code == 403, path
    finally:
        get_backend_config.cache_clear()
