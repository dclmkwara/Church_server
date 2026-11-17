import asyncio
from dataclasses import replace
from types import SimpleNamespace

from fasthtml.common import to_xml
from starlette.requests import Request

from app.frontend.dclm_admin import auth_context
from app.frontend.dclm_admin.auth_context import build_context
from app.frontend.dclm_admin.routes import population_analytics, programs


class RouteApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        return lambda function: self.routes.setdefault(path, function)

    def post(self, path):
        return lambda function: self.routes.setdefault(path, function)


def _request(path):
    return Request({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": b"", "headers": [],
        "server": ("testserver", 80), "client": ("testclient", 1234),
    })


def test_analytics_page_routes_enforce_statistics_permission(monkeypatch):
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    ctx = replace(build_context({"profile": "location_worker"}), permissions=frozenset({"counts:read"}))
    assert ctx.has_permission("counts:read")
    assert not ctx.has_permission("statistics:read")

    monkeypatch.setattr(population_analytics, "build_context", lambda _request: ctx)
    monkeypatch.setattr(population_analytics, "active_scope_context", lambda _request, context: context)
    population_app = RouteApp()
    population_analytics.register_population_analytics_routes(population_app)

    page = asyncio.run(population_app.routes["/church-data/population-attendance"](_request("/church-data/population-attendance")))
    content = asyncio.run(population_app.routes["/church-data/population-attendance/content"](_request("/church-data/population-attendance/content")))
    assert "Analytics access required" in to_xml(page)
    assert "Analytics access required" in to_xml(content)

    monkeypatch.setattr(programs, "active_scope_context", lambda _request, context: context)
    monkeypatch.setattr(programs, "build_context", lambda _request: ctx)
    programs_app = RouteApp()
    programs.register_program_routes(programs_app)
    retreat = asyncio.run(programs_app.routes["/church-data/programs/analytics/retreat"](_request("/church-data/programs/analytics/retreat")))
    crusade = asyncio.run(programs_app.routes["/church-data/programs/analytics/crusade"](_request("/church-data/programs/analytics/crusade")))
    assert "Analytics access required" in to_xml(retreat)
    assert "Analytics access required" in to_xml(crusade)
