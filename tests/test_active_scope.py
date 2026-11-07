from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.exceptions import HTTPException
from starlette.requests import Request

from app.frontend.dclm_admin import auth_context
from app.frontend.dclm_admin.communication.active_scope import resolve_active_scope, scope_link


def _request(query: bytes) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/reports",
            "headers": [],
            "query_string": query,
            "path_params": {},
        },
        lambda: None,
    )


def test_active_scope_accepts_descendant_and_normalizes_case(monkeypatch):
    identity = SimpleNamespace(home_path="dcl.234.kw.ilr", scope_path="dcl.234.kw.ilr", profile_key="region_pastor", role_score=4, role_name="Region Pastor", display_name="Test Pastor", permissions=frozenset())
    request = _request(b"scope_path=DCL.234.KW.ILR.ILE&period=quarter&include_pending=true")
    ctx = SimpleNamespace(current_scope_path=identity.scope_path)
    monkeypatch.setattr(auth_context.AuthService, "get_identity", staticmethod(lambda _request: identity))

    scope = resolve_active_scope(request, ctx)

    assert scope.maximum_path == "dcl.234.kw.ilr"
    assert scope.path == "DCL.234.KW.ILR.ILE"
    assert scope.period == "quarter"
    assert scope.include_pending is True


def test_active_scope_rejects_sibling_scope(monkeypatch):
    identity = SimpleNamespace(home_path="dcl.234.kw.ilr", scope_path="dcl.234.kw.ilr")
    request = _request(b"scope_path=dcl.234.kw.off")
    ctx = SimpleNamespace(current_scope_path=identity.scope_path)
    monkeypatch.setattr(auth_context.AuthService, "get_identity", staticmethod(lambda _request: identity))

    with pytest.raises(HTTPException) as error:
        resolve_active_scope(request, ctx)

    assert error.value.status_code == 403


def test_scope_link_retains_active_scope_and_period(monkeypatch):
    identity = SimpleNamespace(home_path="dcl.234.kw.ilr", scope_path="dcl.234.kw.ilr")
    request = _request(b"scope_path=dcl.234.kw.ilr.ile&period=year&include_pending=false&weeks=8")
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=True))
    monkeypatch.setattr(auth_context.AuthService, "get_identity", staticmethod(lambda _request: identity))
    ctx = auth_context._backend_context(request)
    from app.frontend.dclm_admin.communication.active_scope import active_scope_context
    ctx = active_scope_context(request, ctx)

    query = parse_qs(urlsplit(scope_link(ctx, "/people/workers")).query)

    assert query["scope_path"] == ["dcl.234.kw.ilr.ile"]
    assert query["period"] == ["year"]
    assert query["include_pending"] == ["false"]
    assert query["weeks"] == ["8"]


def test_active_scope_rejects_ancestor_above_signed_in_maximum(monkeypatch):
    identity = SimpleNamespace(home_path="dcl.234.kw.ilr", maximum_scope_path="dcl.234.kw.ilr", scope_path="dcl.234.kw.ilr")
    request = _request(b"scope_path=dcl.234.kw")
    ctx = SimpleNamespace(current_scope_path=identity.scope_path)
    monkeypatch.setattr(auth_context.AuthService, "get_identity", staticmethod(lambda _request: identity))

    with pytest.raises(HTTPException) as error:
        resolve_active_scope(request, ctx)

    assert error.value.status_code == 403
