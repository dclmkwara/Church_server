import asyncio
from dataclasses import replace
from types import SimpleNamespace
from urllib.parse import urlencode

from fasthtml.common import to_xml
from starlette.requests import Request

from app.frontend.dclm_admin import auth_context
from app.frontend.dclm_admin.auth_context import build_context
from app.frontend.dclm_admin.communication import workflow_service
from app.frontend.dclm_admin.communication.workflow_service import WorkflowService
from app.frontend.dclm_admin.routes.inbox import _contextual_review_links
from app.frontend.dclm_admin.routes import pastor_report


def _context(permissions):
    return SimpleNamespace(
        current_scope_path="dcl.234.kw.ilr",
        query_extras={"period": "4w", "include_pending": "false"},
        has_permission=lambda permission: permission in permissions,
        url_for=lambda path, **kwargs: path + ("?" + urlencode(kwargs) if kwargs else ""),
    )


def test_contextual_reviews_show_only_routes_granted_by_current_permissions():
    rendered = to_xml(_contextual_review_links(_context({"counts:review", "programs:approve_events"})))

    assert "Other reviews in your scope" in rendered
    assert "Open Count Review" in rendered
    assert "Open Programs" in rendered
    assert "Open Finance" not in rendered
    assert "Open Reports" not in rendered
    assert "/church-data/count-review?scope_path=dcl.234.kw.ilr&amp;period=4w&amp;include_pending=false" in rendered
    assert "/church-data/programs?scope_path=dcl.234.kw.ilr&amp;period=4w&amp;include_pending=false" in rendered


def test_contextual_reviews_are_absent_when_no_review_permissions_exist():
    assert _contextual_review_links(_context(set())) is None


def test_inbox_categories_respect_permission_and_minimum_review_level(monkeypatch):
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    ctx = build_context({"profile": "location_pastor"})
    ctx = replace(ctx, permissions=ctx.permissions | {"users:approve"})
    assert WorkflowService.inbox_kinds(ctx) == ["all", "transfer_request", "user_approval"]

    rows = [
        {"item_id": "w--1", "kind": "worker_registration"},
        {"item_id": "u--2", "kind": "user_approval"},
        {"item_id": "t--3", "kind": "transfer_request"},
        {"item_id": "s--4", "kind": "status_change"},
        {"item_id": "r--5", "kind": "removal_request"},
    ]
    monkeypatch.setattr(WorkflowService, "use_mock", lambda _request: asyncio.sleep(0, result=True))
    monkeypatch.setattr(workflow_service.STORE, "list_inbox", lambda *_args, **_kwargs: rows)

    async def load_visible():
        return await WorkflowService.list_inbox(SimpleNamespace(), ctx)

    visible = asyncio.run(load_visible())

    assert [row["kind"] for row in visible] == ["user_approval", "transfer_request"]


def test_pastor_report_page_and_exports_require_reports_read(monkeypatch):
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    ctx = build_context({"profile": "location_worker"})
    assert not ctx.has_permission("reports:read")
    monkeypatch.setattr(pastor_report, "build_context", lambda _request: ctx)

    class RouteApp:
        def __init__(self):
            self.routes = {}

        def get(self, path):
            return lambda function: self.routes.setdefault(path, function)

    route_app = RouteApp()
    pastor_report.register_pastor_report_routes(route_app)

    def request_for(path):
        return Request({
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "scheme": "http", "path": path,
            "raw_path": path.encode(), "query_string": b"", "headers": [],
            "server": ("testserver", 80), "client": ("testclient", 1234),
        })

    page = asyncio.run(route_app.routes["/dashboard/pastor-report"](request_for("/dashboard/pastor-report")))
    assert "Access restricted" in to_xml(page)

    for endpoint in ("export.xlsx", "export.csv", "export.pdf", "record-print"):
        path = f"/dashboard/pastor-report/{endpoint}"
        response = asyncio.run(route_app.routes[path](request_for(path)))
        assert response.status_code == 403, endpoint
        assert "report read permission" in response.body.decode(), endpoint
