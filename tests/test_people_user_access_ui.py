import os
import asyncio
from dataclasses import replace
from pathlib import Path
import sys
from types import SimpleNamespace

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.frontend.dclm_admin.auth_context import DEMO_ROLE_PERMISSIONS, build_context
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


def request(path="/people/users"):
    async def unexpected_form():
        raise AssertionError("a refused mutation must be rejected before reading its form")

    return SimpleNamespace(url=SimpleNamespace(path=path), query_params={}, state=SimpleNamespace(), form=unexpected_form)


def render_text(node):
    if isinstance(node, (tuple, list)):
        return " ".join(render_text(child) for child in node)
    if hasattr(node, "children"):
        return render_text(node.children)
    return str(node)


def test_users_page_refuses_field_role_without_loading_directory(monkeypatch):
    app = FakeApp()
    people.register_people_routes(app)
    ctx = build_context({"profile": "location_pastor"})
    ctx = replace(
        ctx,
        profile=replace(ctx.profile, role_label="Location Worker / Usher"),
        permissions=frozenset({"users:read", "users:create", "users:assign_roles", "users:approve", "users:deactivate"}),
    )
    monkeypatch.setattr(people, "build_context", lambda _request: ctx)
    monkeypatch.setattr(people, "active_scope_context", lambda _request, context: context)

    async def unexpected_access(*args, **kwargs):
        raise AssertionError("field role reached user-account data or mutation service")

    monkeypatch.setattr(people, "_loading_results", unexpected_access)
    monkeypatch.setattr(people, "_users_table", unexpected_access)
    monkeypatch.setattr(people.PeopleService, "get_user", unexpected_access)
    monkeypatch.setattr(people.PeopleService, "list_users", unexpected_access)
    paths = [
        ("GET", "/people/users"),
        ("GET", "/people/users/list"),
        ("GET", "/people/users/new"),
        ("GET", "/people/users/{account_id}/drawer"),
        ("GET", "/people/users/{account_id}/roles"),
        ("POST", "/people/users/create"),
        ("POST", "/people/users/{account_id}/roles"),
        ("GET", "/people/users/{account_id}/review"),
        ("POST", "/people/users/{account_id}/review"),
        ("GET", "/people/users/{account_id}/deactivate"),
        ("POST", "/people/users/{account_id}/deactivate"),
        ("GET", "/people/users/{account_id}/reactivate"),
        ("POST", "/people/users/{account_id}/reactivate"),
    ]
    for method, path in paths:
        kwargs = {"account_id": "test-account"} if "{account_id}" in path else {}
        if method == "GET" and path.endswith("/review"):
            kwargs["action"] = "approve"
        result = asyncio.run(app.routes[(method, path)](request(path), **kwargs))
        rendered = render_text(result)
        assert "User management not available" in rendered, (method, path)
        assert "restricted to administrative staff" in rendered, (method, path)


def test_users_page_allows_admin_to_reach_directory(monkeypatch):
    app = FakeApp()
    people.register_people_routes(app)
    ctx = build_context({"profile": "state_admin"})
    ctx = ctx.__class__(**{**ctx.__dict__, "permissions": DEMO_ROLE_PERMISSIONS["state_admin"]})
    monkeypatch.setattr(people, "build_context", lambda _request: ctx)

    async def loading_results(*args, **kwargs):
        return "USER_DIRECTORY_SENTINEL"

    monkeypatch.setattr(people, "_loading_results", loading_results)
    result = asyncio.run(app.routes[("GET", "/people/users")](request()))
    rendered = str(result)

    assert "App Users" in rendered
    assert "USER_DIRECTORY_SENTINEL" in rendered
