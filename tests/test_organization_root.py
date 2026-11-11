from types import SimpleNamespace
from http.cookies import SimpleCookie
import asyncio

from starlette.requests import Request
from starlette.responses import Response

from app.frontend.dclm_admin.communication.auth_service import AuthIdentity, AuthService
from app.frontend.dclm_admin.routes import organization
from app.frontend.dclm_admin.routes.organization import _location_home_id


def test_location_organization_root_uses_location_uuid_not_path_segment():
    ctx = SimpleNamespace(level=2, current_scope_path="org.234.KW.ILR.ILE.003")
    identity = SimpleNamespace(user={"location_id": "9fcb3ead-014c-4f6f-8a92-27293fcbd31f"})

    assert _location_home_id(ctx, identity) == "9fcb3ead-014c-4f6f-8a92-27293fcbd31f"
    assert _location_home_id(ctx, identity) != ctx.current_scope_path.split(".")[-1]


def test_organization_root_fails_closed_when_location_id_is_missing():
    ctx = SimpleNamespace(level=2, current_scope_path="org.234.KW.ILR.ILE.003")

    assert _location_home_id(ctx, SimpleNamespace(user={})) == ""


def test_location_id_survives_auth_cookie_round_trip_for_organization_home():
    location_id = "9fcb3ead-014c-4f6f-8a92-27293fcbd31f"
    identity = AuthIdentity(
        user_id="user-1", access_token="access", refresh_token="refresh",
        user={"name": "Location Pastor", "email": "pastor@example.test", "path": "dcl.234.kw.ilr.ile.003", "location_id": location_id, "permissions": []},
        profile_key="location_pastor", role_score=2, role_name="Location Pastor",
        scope_path="dcl.234.kw.ilr.ile.003", home_path="dcl.234.kw.ilr.ile.003",
    )
    response = Response()
    asyncio.run(AuthService.persist_identity(response, identity))
    cookie = SimpleCookie()
    for header in response.headers.getlist("set-cookie"):
        cookie.load(header)
    cookie_header = "; ".join(f"{name}={morsel.value}" for name, morsel in cookie.items())
    request = Request({
        "type": "http", "method": "GET", "path": "/organization", "headers": [
            (b"cookie", cookie_header.encode("latin-1")),
        ], "query_string": b"", "server": ("testserver", 80), "scheme": "http",
    })

    restored = AuthService.get_identity(request)
    ctx = SimpleNamespace(level=2, current_scope_path="dcl.234.kw.ilr.ile.003")
    assert restored is not None
    assert _location_home_id(ctx, restored) == location_id


def test_location_organization_root_returns_clean_403_without_profile_id(monkeypatch):
    handlers = {}

    class AppStub:
        def get(self, path):
            return lambda fn: handlers.setdefault(path, fn)

        def post(self, path):
            return lambda fn: handlers.setdefault(path, fn)

    organization.register_organization_routes(AppStub())
    monkeypatch.setattr(organization, "build_context", lambda request: SimpleNamespace(
        level=2, current_scope_path="dcl.234.kw.ilr.ile.003", url_for=lambda path, **params: path,
    ))
    monkeypatch.setattr(organization.AuthService, "get_identity", lambda request: None)
    request = Request({
        "type": "http", "method": "GET", "path": "/organization", "headers": [],
        "query_string": b"", "server": ("testserver", 80), "scheme": "http",
    })

    response = asyncio.run(handlers["/organization"](request))
    assert response.status_code == 403
    assert "unavailable" in response.body.decode().lower()
