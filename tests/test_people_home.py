import asyncio
import os
from dataclasses import replace
from pathlib import Path
import sys
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fasthtml.common import to_xml

from app.frontend.dclm_admin.auth_context import build_context
from app.frontend.dclm_admin.routes import people


class FakeApp:
    def __init__(self):
        self.routes = {}

    def get(self, path):
        def register(handler):
            self.routes[("GET", path)] = handler
            return handler
        return register

    def post(self, path):
        def register(handler):
            self.routes[("POST", path)] = handler
            return handler
        return register


def test_people_home_only_shows_destinations_for_current_permissions(monkeypatch):
    app = FakeApp()
    people.register_people_routes(app)
    ctx = build_context({"profile": "location_admin"})
    ctx = replace(ctx, permissions=frozenset({"workers:read", "records:read"}))
    monkeypatch.setattr(people, "build_context", lambda _request: ctx)
    monkeypatch.setattr(people, "active_scope_context", lambda _request, context: context)
    request = SimpleNamespace(
        url=SimpleNamespace(path="/people"),
        query_params={},
        state=SimpleNamespace(),
    )

    rendered = to_xml(asyncio.run(app.routes[("GET", "/people")](request)))

    assert 'href="/people/workers?' in rendered
    assert 'href="/people/members?' in rendered
    assert 'href="/church-data/newcomers?' in rendered
    assert 'href="/fellowship?' not in rendered
    assert 'href="/organization?' not in rendered
    assert 'href="/people/users?' not in rendered
    assert 'href="/people/officials?' not in rendered
    assert "Choose a people task." in rendered


def test_people_home_hides_app_users_from_field_roles_with_forged_permission(monkeypatch):
    app = FakeApp()
    people.register_people_routes(app)
    ctx = build_context({"profile": "location_worker"})
    ctx = replace(ctx, permissions=ctx.permissions | {"users:read"})
    monkeypatch.setattr(people, "build_context", lambda _request: ctx)
    monkeypatch.setattr(people, "active_scope_context", lambda _request, context: context)
    request = SimpleNamespace(
        url=SimpleNamespace(path="/people"),
        query_params={},
        state=SimpleNamespace(),
    )

    rendered = to_xml(asyncio.run(app.routes[("GET", "/people")](request)))

    assert "App users" not in rendered
    assert "/people/users" not in rendered
