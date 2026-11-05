import os
from pathlib import Path
import sys
import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db")
os.environ.setdefault("FASTSTRAP_BACKEND_ENABLED", "false")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.frontend.dclm_admin.auth_context import (
    AdminContext,
    ProfileConfig,
    VISIBLE_MODULES,
    build_context,
)
from app.frontend.dclm_admin.components.shell import _sidebar, shell_layout, primary_button
from app.frontend.dclm_admin.routes.dashboard import (
    _dashboard_loading_content,
    _dashboard_profile,
    _bootstrap_keys_for_profile,
)


def test_visible_modules_all_levels():
    """Ensure every level from 1 to 9 (plus future/higher levels) resolves safely without KeyError."""
    for lvl in range(1, 12):
        ctx = AdminContext(
            profile=ProfileConfig(
                key="test_profile",
                level=lvl,
                user_name="Test User",
                role_label="Role",
                mode_label="Oversight Mode",
                root_kind="global",
                root_label="Global",
                root_path="org",
                selector_fields=(),
            ),
            selected={},
            options={},
            current_scope_kind="global",
            current_scope_label="Global",
            current_scope_path="org",
            permissions=frozenset({"reports:read"}) if lvl >= 3 else frozenset(),
        )
        modules = ctx.visible_modules
        assert isinstance(modules, list)
        if lvl <= 5:
            assert "dashboard" in modules
        else:
            assert modules == []
        if 1 <= lvl <= 5:
            assert "inbox" in modules
        if 2 <= lvl <= 5:
            assert "system" in modules
        if lvl > 5:
            assert "system" not in modules


def test_higher_level_client_is_not_exposed_in_levels_two_to_five_console():
    base = dict(
        profile=ProfileConfig(key="admin", level=6, user_name="Admin", role_label="Admin", mode_label="Oversight", root_kind="state", root_label="State", root_path="org.st", selector_fields=()),
        selected={}, options={}, current_scope_kind="state", current_scope_label="State", current_scope_path="org.st",
    )
    assert "reports" not in AdminContext(**base).visible_modules
    assert AdminContext(**base, permissions=frozenset({"reports:read"})).visible_modules == []


def test_global_admin_dashboard_profile_and_keys():
    """Global admin role maps to the global governance dashboard view."""
    ctx = AdminContext(
        profile=ProfileConfig(
            key="state_overseer",
            level=9,
            user_name="Meshell Eva",
            role_label="Global Admin",
            mode_label="Oversight Mode",
            root_kind="global",
            root_label="Global",
            root_path="org",
            selector_fields=(),
        ),
        selected={},
        options={},
        current_scope_kind="global",
        current_scope_label="Global",
        current_scope_path="org",
    )
    profile_type = _dashboard_profile(ctx)
    assert profile_type == "governance"

    bootstrap_keys = _bootstrap_keys_for_profile(profile_type)
    assert "summary" in bootstrap_keys
    assert "church_statistics" in bootstrap_keys


def test_population_statistics_are_loaded_by_default_for_levels_two_to_five():
    """Local and state dashboards should show population mix without a manual load click."""
    for profile_type in ("local", "state"):
        bootstrap_keys = _bootstrap_keys_for_profile(profile_type)
        assert "population_statistics" in bootstrap_keys


def test_global_admin_shell_layout_renders():
    """Ensure shell layout renders without errors for Level 9 Global Admin."""
    ctx = AdminContext(
        profile=ProfileConfig(
            key="state_overseer",
            level=9,
            user_name="Meshell Eva",
            role_label="Global Admin",
            mode_label="Oversight Mode",
            root_kind="global",
            root_label="Global",
            root_path="org",
            selector_fields=(),
        ),
        selected={},
        options={},
        current_scope_kind="global",
        current_scope_label="Global",
        current_scope_path="org",
    )
    content = _dashboard_loading_content(ctx)
    # content must be a concrete element, not an unawaited coroutine
    assert not hasattr(content, "__await__")

    rendered = shell_layout(
        ctx,
        request_path="/dashboard",
        active_key="dashboard",
        title="Dashboard",
        subtitle="Overview",
        primary_action=primary_button("Inbox", href=ctx.url_for("/inbox")),
        content=content,
    )
    assert rendered is not None
