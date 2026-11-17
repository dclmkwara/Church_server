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
from app.frontend.dclm_admin.routes import church_data, people


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


def test_workers_directory_summary_uses_recorded_units_and_active_approval(monkeypatch):
    ctx = build_context({"profile": "state_admin"})
    workers = [
        {"worker_id": "1", "user_id": "W1", "name": "A", "unit": "Media", "location": "A", "approval_status": "approved", "status": "Active"},
        {"worker_id": "2", "user_id": "W2", "name": "B", "unit": "Media", "location": "B", "approval_status": "approved", "status": "Inactive"},
        {"worker_id": "3", "user_id": "W3", "name": "C", "unit": "", "location": "C", "approval_status": "pending_verification", "status": "Active"},
        {"worker_id": "4", "user_id": "W4", "name": "D", "unit": "New unit", "location": "D", "approval_status": "approved", "status": "Active"},
    ]
    monkeypatch.setattr(people, "active_scope_context", lambda _request, context: context)

    async def list_workers(*args, **kwargs):
        return workers

    async def worker_card(_ctx, worker):
        return Div(worker["name"])

    from fasthtml.common import Div

    monkeypatch.setattr(people.PeopleService, "list_workers", list_workers)
    monkeypatch.setattr(people, "_worker_mobile_card", worker_card)
    request = SimpleNamespace()
    rendered = to_xml(asyncio.run(people._workers_table(request, ctx)))

    assert "Workers shown" in rendered
    assert "Active and approved" in rendered
    assert "Workers awaiting verification" in rendered
    assert "Unit distribution" in rendered
    assert "Media" in rendered and "New unit" in rendered and "Unit not recorded" in rendered
    assert "admin-metric-grid" not in rendered
    assert rendered.count('id="workers-results"') == 1


def test_app_user_summary_is_about_accounts_not_workers(monkeypatch):
    ctx = replace(build_context({"profile": "state_admin"}), current_scope_path="dcl.234.kw")
    users = [
        {"account_id": "1", "name": "Active", "public_code": "A1", "location_display": "A", "roles": ["Pastor"], "approval_status": "approved", "status": "active", "path": "dcl.234.kw.reg1.g1.loc1", "region": "Region 1"},
        {"account_id": "2", "name": "Pending", "public_code": "A2", "location_display": "B", "roles": ["Admin"], "approval_status": "pending", "status": "inactive", "path": "dcl.234.kw.reg1.g2.loc2", "region": "Region 1"},
    ]

    async def list_users(*args, **kwargs):
        return users

    async def user_card(_ctx, user):
        from fasthtml.common import Div
        return Div(user["name"])

    monkeypatch.setattr(people.PeopleService, "list_users", list_users)
    monkeypatch.setattr(people, "_user_mobile_card", user_card)
    request = SimpleNamespace()
    rendered = to_xml(asyncio.run(people._users_table(request, ctx)))

    assert "Accounts shown" in rendered
    assert "Active accounts" in rendered
    assert "Pending approval" in rendered
    assert "App accounts matching these filters" in rendered
    assert "App users shown by direct child" in rendered
    assert "Region 1" in rendered
    assert "Active and approved" not in rendered
    assert rendered.count('id="users-results"') == 1


def test_meeting_unit_filter_uses_units_found_in_attendance_records():
    assert church_data._attendance_unit_options(
        [{"unit": "Youth Choir"}, {"unit": "Ushering"}, {"unit": ""}],
        "Legacy Unit",
    ) == ["Legacy Unit", "Ushering", "Youth Choir"]
