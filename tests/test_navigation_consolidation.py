from __future__ import annotations

from html import escape
from types import SimpleNamespace

from fasthtml.common import to_xml

from app.frontend.dclm_admin.auth_context import build_context
from app.frontend.dclm_admin import auth_context
from app.frontend.dclm_admin.components import shell
from app.frontend.dclm_admin.components.shell import NAV_GROUPS, _mobile_bottom_nav, _nav_item_visible, _sidebar


PERSONAS = (
    "location_pastor", "location_admin", "group_pastor", "group_admin",
    "region_pastor", "region_admin", "state_overseer", "state_admin",
)


def test_menu_items_are_permission_and_level_filtered_for_all_eight_personas(monkeypatch):
    monkeypatch.setattr(shell, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    for key in PERSONAS:
        ctx = build_context({"profile": key})
        rendered = to_xml(_sidebar(ctx, "dashboard"))
        visible = {
            item["label"]
            for group in NAV_GROUPS
            for item in group["items"]
            if _nav_item_visible(ctx, {"module": group["module"], **item}, backend_mode=False)
        }
        for label in visible:
            assert escape(label) in rendered, f"{key} is missing visible menu item {label}"
        assert "Officials" not in rendered  # live support remains intentionally disabled
        if "counts:review" not in ctx.permissions:
            assert "Count Review" not in visible
        if "population_estimates:manage" not in ctx.permissions or ctx.level != 5:
            assert "Expected Attendance" not in visible
        if "system:read_audit_logs" not in ctx.permissions:
            assert "Audit Log" not in visible
        if "rbac:read" not in ctx.permissions or ctx.level != 5:
            assert "Roles and Permissions" not in visible
        if ctx.level < 3:
            assert "Organization" not in visible
        if ctx.level < 4:
            assert "Communication" not in visible


def test_all_eight_persona_menus_keep_work_pages_and_hide_decisions_from_admins(monkeypatch):
    # Use the demo persona grants as fixtures while applying live-mode menu
    # rules (notably the intentional Officials suppression).
    monkeypatch.setattr(shell, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    for key in PERSONAS:
        ctx = build_context({"profile": key})
        visible = {
            item["label"]
            for group in NAV_GROUPS
            for item in group["items"]
            if _nav_item_visible(ctx, {"module": group["module"], **item}, backend_mode=True)
        }
        assert {"Dashboard", "Programs", "Workers", "Inbox", "Offerings and Tithes"} <= visible
        is_pastor = key.endswith("pastor") or key == "state_overseer"
        assert ("Count Review" in visible) == is_pastor
        assert ("Audit Log" in visible) == is_pastor
        assert "Officials" not in visible
        if key in {"state_admin", "state_overseer"}:
            assert "Documented Population" in visible
        else:
            assert "Documented Population" not in visible


def test_current_page_urls_remain_registered_without_breaking_existing_bookmarks():
    from app.frontend.dclm_admin.app_factory import app

    registered = {getattr(route, "path", "") for route in app.routes}
    legacy_page_urls = {
        "/dashboard", "/dashboard/pastor-report", "/reports", "/inbox",
        "/people", "/people/workers", "/people/members", "/people/users", "/fellowship",
        "/organization", "/church-data/programs", "/church-data/counts",
        "/church-data/count-review", "/church-data/meetings/workers-saturday",
        "/church-data/meetings/leaders-tuesday", "/church-data/finance",
        "/church-data/newcomers", "/church-data/attendance",
        "/church-data/population-attendance", "/church-data/programs/analytics/retreat",
        "/church-data/programs/analytics/crusade", "/analytics/expected-population",
        "/system/audit-logs", "/system/rbac",
    }
    assert legacy_page_urls <= registered


def test_finance_analytics_menu_link_selects_the_existing_financial_report_tab():
    finance_link = next(
        item["href"]
        for group in NAV_GROUPS
        for item in group["items"]
        if item["label"] == "Finance Analytics"
    )
    assert finance_link == "/reports?tab=financial"


def test_every_visible_menu_destination_has_a_registered_route(monkeypatch):
    from urllib.parse import urlsplit
    from app.frontend.dclm_admin.app_factory import app

    monkeypatch.setattr(shell, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    registered = {getattr(route, "path", "") for route in app.routes}
    for persona in PERSONAS:
        ctx = build_context({"profile": persona})
        for group in NAV_GROUPS:
            for item in group["items"]:
                if not _nav_item_visible(ctx, {"module": group["module"], **item}, backend_mode=True):
                    continue
                path = urlsplit(item["href"]).path
                assert path in registered, f"{persona} sees {item['label']} pointing to unregistered {path}"


def test_mobile_shortcuts_follow_the_same_read_permissions(monkeypatch):
    monkeypatch.setattr(shell, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    for persona in PERSONAS:
        ctx = build_context({"profile": persona})
        rendered = to_xml(_mobile_bottom_nav(ctx, "dashboard"))
        assert "Home" in rendered and "Menu" in rendered
        assert "People" in rendered
        is_pastor = persona.endswith("pastor") or persona == "state_overseer"
        assert ("Church" in rendered) == (ctx.has_permission("programs:read") and not is_pastor)
        assert ("Finance" in rendered) == (ctx.has_permission("offerings:read") and not is_pastor)


def test_sidebar_has_no_dead_docs_link_or_nonfunctional_global_search(monkeypatch):
    monkeypatch.setattr(shell, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    monkeypatch.setattr(auth_context, "get_backend_config", lambda: SimpleNamespace(enabled=False))
    ctx = build_context({"profile": "state_overseer"})
    rendered = to_xml(_sidebar(ctx, "dashboard"))
    assert "/docs" not in rendered
    assert "Global search" not in rendered
    assert 'placeholder="Search workers, members, or locations"' not in rendered
