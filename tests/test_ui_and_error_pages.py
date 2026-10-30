from starlette.testclient import TestClient
from starlette.requests import Request
from starlette.responses import HTMLResponse
import pytest

from app.frontend.dclm_admin.app_factory import app as frontend_app
from app.frontend.dclm_admin.components.error_pages import not_found_response, server_error_response


def test_custom_error_pages_direct():
    from starlette.datastructures import Headers

    class FakeRequest:
        method = "GET"
        url = type("URL", (), {"path": "/some-nonexistent-page"})()
        headers = Headers({})

    req = FakeRequest()
    r404 = not_found_response(req)
    assert r404.status_code == 404
    body404 = r404.body.decode("utf-8")
    assert "404" in body404
    assert "Page Not Found" in body404
    assert "Return to Dashboard" in body404

    r500 = server_error_response(req, ValueError("Something crashed"))
    assert r500.status_code == 500
    body500 = r500.body.decode("utf-8")
    assert "500" in body500
    assert "Something Went Wrong" in body500
    assert "Return to Dashboard" in body500


def test_custom_error_pages_htmx():
    from starlette.datastructures import Headers

    class FakeHtmxRequest:
        method = "GET"
        url = type("URL", (), {"path": "/partials/something"})()
        headers = Headers({"HX-Request": "true"})

    req = FakeHtmxRequest()
    r404 = not_found_response(req)
    assert r404.status_code == 404
    assert "alert" in r404.body.decode("utf-8").lower()

    r500 = server_error_response(req, RuntimeError("Database down"))
    assert r500.status_code == 500
    assert "alert" in r500.body.decode("utf-8").lower()


def test_shell_mobile_nav_items():
    from app.frontend.dclm_admin.auth_context import AdminContext, ProfileConfig
    from app.frontend.dclm_admin.components.shell import _mobile_bottom_nav
    from fasthtml.common import to_xml

    ctx = AdminContext(
        profile=ProfileConfig(
            key="test_profile",
            level=9,
            user_name="Test Admin",
            role_label="Administrator",
            mode_label="State Mode",
            root_kind="state",
            root_label="Kwara",
            root_path="org.kwara",
            selector_fields=(),
        ),
        selected={},
        options={},
        current_scope_kind="state",
        current_scope_label="Kwara",
        current_scope_path="org.kwara",
    )
    nav = _mobile_bottom_nav(ctx, "dashboard")
    xml = to_xml(nav)
    # Check that 5 items exist
    assert "Home" in xml
    assert "People" in xml
    assert "Inbox" in xml
    assert "Church" in xml
    assert "Menu" in xml
    assert "/inbox" in xml


def test_shell_topbar_no_duplicate_menu_button():
    from app.frontend.dclm_admin.auth_context import AdminContext, ProfileConfig
    from app.frontend.dclm_admin.components.shell import shell_layout
    from fasthtml.common import Div, to_xml

    ctx = AdminContext(
        profile=ProfileConfig(
            key="test_profile",
            level=9,
            user_name="Test Admin",
            role_label="Administrator",
            mode_label="State Mode",
            root_kind="state",
            root_label="Kwara",
            root_path="org.kwara",
            selector_fields=(),
        ),
        selected={},
        options={},
        current_scope_kind="state",
        current_scope_label="Kwara",
        current_scope_path="org.kwara",
    )
    layout = shell_layout(
        ctx,
        request_path="/dashboard",
        active_key="dashboard",
        title="Dashboard",
        subtitle="Overview",
        primary_action=None,
        content=Div("Content"),
    )
    xml = to_xml(layout)
    # Topbar mobile menu button was removed to avoid duplication
    assert "topbar-mobile-menu-btn" not in xml
    # Mobile brand is present
    assert "topbar-mobile-brand" in xml
