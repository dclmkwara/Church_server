from __future__ import annotations

from typing import Any

from fasthtml.common import A, Button, Div, Form, H2, Img, Input, Link, Main, Option, P, Script, Select, Span, Title

from faststrap import Badge, BottomNav, BottomNavItem, Drawer, Fx, Icon, Modal, ThemeToggle

from ..auth_context import AdminContext, PROFILE_CONFIGS
from ..backend.config import get_backend_config
from .feedback import toast_stack


NAV_GROUPS = [
    {
        "label": "Core",
        "module": "dashboard",
        "items": [
            {"label": "Dashboard", "icon": "grid", "href": "/dashboard", "key": "dashboard"},
            {"label": "Inbox", "icon": "inbox", "href": "/inbox", "key": "inbox"},
        ],
    },
    {
        "label": "People",
        "module": "people",
        "items": [
            {"label": "Workers", "icon": "people", "href": "/people/workers", "key": "workers"},
            {"label": "Members", "icon": "person-vcard", "href": "/people/members", "key": "members"},
            {"label": "App Users", "icon": "person-badge", "href": "/people/users", "key": "users"},
            {"label": "Officials", "icon": "person-check", "href": "/people/officials", "key": "officials", "min_level": 4},
        ],
    },
    {
        "label": "Church Data",
        "module": "church-data",
        "items": [
            {"label": "Programs", "icon": "calendar-event", "href": "/church-data/programs", "key": "programs"},
            {"label": "Program Counts", "icon": "bar-chart", "href": "/church-data/counts", "key": "counts"},
            {"label": "Offerings & Tithes", "icon": "cash-stack", "href": "/church-data/finance", "key": "finance"},
            {"label": "Newcomers", "icon": "person-hearts", "href": "/church-data/newcomers", "key": "newcomers"},
            {"label": "Attendance", "icon": "clipboard-check", "href": "/church-data/attendance", "key": "attendance"},
        ],
    },
    {
        "label": "More",
        "module": "workflows",
        "items": [
            {"label": "Workflows", "icon": "diagram-3", "href": "/workflows", "key": "workflows"},
            {"label": "Fellowship", "icon": "house-heart", "href": "/fellowship", "key": "fellowship"},
            {"label": "Organization", "icon": "geo-alt", "href": "/organization", "key": "organization"},
            {"label": "Communication", "icon": "megaphone", "href": "/communication", "key": "communication", "module": "communication"},
            {"label": "Reports", "icon": "clipboard-data", "href": "/reports", "key": "reports", "module": "reports"},
            {"label": "System", "icon": "shield-lock", "href": "/system", "key": "system", "module": "system"},
        ],
    },
]


def hidden_context_inputs(ctx: AdminContext) -> list[Any]:
    return [Input(type="hidden", name=key, value=value) for key, value in ctx.query_dict().items()]


def primary_button(label: str, **attrs: Any) -> Any:
    return A(label, cls=f"btn btn-primary admin-primary-btn {Fx.base} {Fx.hover_lift}", **attrs)


def _demo_profile_switcher(ctx: AdminContext, request_path: str) -> Any:
    if get_backend_config().enabled:
        return Div(
            P("Signed-in session", cls="small text-muted mb-1"),
            Div(
                Badge("Live Session", variant="light", cls="scope-chip text-primary-emphasis"),
                Span("Permissions control available views.", cls="small text-muted"),
                cls="d-flex align-items-center gap-2 flex-wrap",
            ),
            cls="scope-static-card",
        )
    profile_options = sorted(PROFILE_CONFIGS.values(), key=lambda row: row.level)
    return Form(
        P("Role view", cls="small text-muted mb-1"),
        Div(
            Select(
                *[
                    Option(
                        f"Level {profile.level} - {profile.role_label}",
                        value=profile.key,
                        selected=profile.key == ctx.profile.key,
                    )
                    for profile in profile_options
                ],
                name="profile",
                cls="form-select admin-select",
            ),
            Button("Switch", cls="btn btn-outline-primary admin-inline-btn"),
            cls="d-grid d-sm-flex gap-2",
        ),
        action=request_path,
        method="get",
        cls="role-profile-form",
    )


def _scope_selector(ctx: AdminContext, request_path: str) -> Any:
    if ctx.level < 4:
        return Div(
            P("Scope", cls="small text-muted mb-1"),
            Div(
                Badge("My Scope", variant="light", cls="scope-chip text-primary-emphasis"),
                Span(ctx.current_scope_label, cls="fw-semibold text-dark"),
                cls="d-flex align-items-center gap-2 flex-wrap",
            ),
            cls="scope-static-card",
        )

    controls = []
    for field in ctx.profile.selector_fields:
        options = ctx.options.get(field, [])
        current_value = ctx.selected.get(field, "")
        controls.append(
            Div(
                P(field.replace("_", " ").title(), cls="small text-muted mb-1"),
                Select(
                    *[Option(option, value=option, selected=option == current_value) for option in options],
                    name=field,
                    cls="form-select admin-select",
                ),
                cls="scope-select-block",
            )
        )

    return Form(
        *hidden_context_inputs(ctx),
        *controls,
        Button("Apply", cls="btn btn-outline-primary admin-inline-btn"),
        action=request_path,
        method="get",
        cls="scope-form",
    )


def _scope_drawer_content(ctx: AdminContext, request_path: str) -> Any:
    backend_mode = get_backend_config().enabled
    return Div(
        Div(
            Badge(f"Level {ctx.level}", variant="light", cls="scope-chip text-primary-emphasis"),
            Span(ctx.current_scope_kind.replace("_", " ").title(), cls="small fw-semibold text-uppercase text-primary"),
            cls="d-flex flex-wrap gap-2 align-items-center mb-2",
        ),
        Div(
            P("View", cls="small text-muted mb-1"),
            P(ctx.profile.role_label, cls="fw-semibold text-dark mb-1"),
            P(ctx.current_scope_label, cls="small text-muted mb-0"),
            cls="scope-summary-card",
        ),
        Div(
            Div(
                P("Session view" if backend_mode else "Role view", cls="small text-uppercase fw-semibold text-muted mb-2"),
                _demo_profile_switcher(ctx, request_path),
                cls="scope-drawer-section",
            ),
            Div(
                P("Hierarchy scope", cls="small text-uppercase fw-semibold text-muted mb-2"),
                _scope_selector(ctx, request_path),
                cls="scope-drawer-section",
            ),
            Div(
                P("Theme & Appearance", cls="small text-uppercase fw-semibold text-muted mb-2"),
                Div(
                    ThemeToggle(toggle_id="theme-toggle-drawer", current_theme="auto", show_label=True, label_text="Dark Mode"),
                    cls="p-2 border rounded-3 bg-body-tertiary d-flex align-items-center justify-content-between",
                ),
                cls="scope-drawer-section",
            ),
            cls="d-grid gap-3",
        ),
        cls="scope-drawer-stack",
    )


def _user_menu(ctx: AdminContext) -> Any:
    initials = "".join(part[0] for part in ctx.profile.user_name.split()[:2]).upper()
    config = get_backend_config()
    profile_links = []
    if not config.enabled:
        profile_links = [
            A(
                f"Level {profile.level} - {profile.role_label}",
                href=ctx.url_for("/dashboard", profile=profile.key),
                cls="dropdown-item",
            )
            for profile in sorted(PROFILE_CONFIGS.values(), key=lambda row: row.level)
        ]
    return Div(
        Button(
            Span(initials, cls="avatar-pill"),
            cls=f"btn btn-light border admin-user-toggle topbar-avatar-btn {Fx.base} {Fx.hover_lift}",
            data_bs_toggle="dropdown",
            aria_expanded="false",
            aria_label=f"Open account menu for {ctx.profile.user_name}",
            type="button",
        ),
        Div(
            Div(
                Span(initials, cls="avatar-pill"),
                Div(
                    P(ctx.profile.user_name, cls="fw-semibold text-dark mb-1"),
                    P(f"{ctx.profile.role_label} • Level {ctx.level}", cls="small text-muted mb-0"),
                    cls="dropdown-user-copy",
                ),
                cls="dropdown-user-summary d-flex align-items-center gap-3 px-3 py-2",
            ),
            Div(cls="dropdown-divider"),
            Button(
                Span(Icon("sliders", cls="fs-6"), cls="d-inline-flex"),
                Span("Change view / Theme", cls="fw-semibold"),
                cls="dropdown-item d-flex align-items-center gap-2",
                data_bs_toggle="offcanvas",
                data_bs_target="#scope-drawer",
                type="button",
            ),
            Div(cls="dropdown-divider"),
            *profile_links,
            Div(cls="dropdown-divider") if profile_links else "",
            A("Logout", href="/logout", cls="dropdown-item text-danger"),
            cls="dropdown-menu dropdown-menu-end shadow border-0",
        ),
        cls="dropdown",
    )


def _sidebar(ctx: AdminContext, active_key: str) -> Any:
    backend_mode = get_backend_config().enabled
    unsupported_live_keys = {"officials"}
    initials = "".join(part[0] for part in ctx.profile.user_name.split()[:2]).upper()
    groups = []
    for group in NAV_GROUPS:
        items = []
        for item in group["items"]:
            module = item.get("module", group["module"])
            if module not in ctx.visible_modules:
                continue
            if ctx.level < item.get("min_level", 0):
                continue
            if backend_mode and item["key"] in unsupported_live_keys:
                continue
            items.append(
                A(
                    Span(Icon(item["icon"], cls="me-3")),
                    Span(item["label"]),
                    Span(cls="spinner-border spinner-border-sm sidebar-nav-spinner"),
                    href=ctx.url_for(item["href"]),
                    cls=f"sidebar-link {Fx.base} {'active' if active_key == item['key'] else ''}",
                )
            )
        if items:
            groups.append(
                Div(
                    P(group["label"], cls="sidebar-section-label"),
                    Div(*items, cls="d-grid gap-2"),
                    cls="mb-4",
                )
            )

    return Div(
        Div(
            Div(
                Img(
                    src="/assets/img/dclm-logo.png",
                    alt="Deeper Life Bible Church",
                    width="42",
                    height="42",
                    cls="rounded-circle shadow-sm bg-white p-1",
                ),
                Div(
                    Badge("DCLM Admin", variant="light", cls="text-primary-emphasis border-0 px-2 py-1 small"),
                    cls="d-flex align-items-center",
                ),
                cls="d-flex align-items-center gap-2 mb-3",
            ),
            Div(
                Span(initials, cls="sidebar-profile__avatar"),
                P(ctx.profile.user_name, cls="text-white fw-semibold mb-1"),
                P(f"{ctx.profile.role_label} • Level {ctx.level}", cls="text-white-50 small mb-0"),
                P(ctx.current_scope_label, cls="text-white-50 small mb-0"),
                cls="sidebar-profile",
            ),
            cls="mb-4",
        ),
        *groups,
        Div(
            A(Icon("download", cls="me-2"), "Install App", href="#", data_install_trigger="sidebar", cls="btn btn-outline-light btn-sm sidebar-install-btn d-none"),
            A("Help & Docs", href="/docs" if get_backend_config().enabled else "#", cls="sidebar-footer-link"),
            cls="mt-auto d-grid gap-2",
        ),
        cls="admin-sidebar-inner d-flex flex-column h-100",
    )


def _mobile_bottom_nav(ctx: AdminContext, active_key: str) -> Any:
    """Persistent bottom navigation bar shown on mobile (< lg breakpoint)."""
    nav_items = [
        ("Home", "house", "/dashboard", "dashboard"),
        ("People", "people", "/people/workers", "workers"),
        ("Church", "calendar-event", "/church-data/programs", "programs"),
    ]
    items = [
        BottomNavItem(
            label,
            href=ctx.url_for(href),
            icon=icon,
            active=(active_key == key),
        )
        for label, icon, href, key in nav_items
    ]
    # Menu button — triggers the mobile side-nav offcanvas (no page navigation)
    items.append(
        A(
            Icon("list", cls="bottom-nav-icon"),
            Span("Menu", cls="bottom-nav-label"),
            href="#",
            data_bs_toggle="offcanvas",
            data_bs_target="#mobile-nav",
            aria_label="Open navigation menu",
            cls="bottom-nav-item",
        )
    )
    return BottomNav(*items, cls="d-lg-none admin-bottom-nav")


def shell_layout(
    ctx: AdminContext,
    *,
    request_path: str,
    active_key: str,
    title: str,
    subtitle: str,
    primary_action: Any | None,
    content: Any,
    show_shell_intro: bool = True,
) -> Any:
    sidebar = _sidebar(ctx, active_key)
    page_title = title or "DCLM Admin"
    return (
        Title(f"{page_title} | DCLM Admin"),
        Link(rel="icon", type="image/png", sizes="32x32", href="/assets/favicon.png"),
        Link(rel="shortcut icon", type="image/x-icon", href="/favicon.ico"),
        Link(rel="apple-touch-icon", sizes="180x180", href="/assets/apple-touch-icon.png"),
        Link(rel="manifest", href="/manifest.json"),
        Link(rel="stylesheet", href="/assets/css/admin.css"),
        Script("""
(function(){
  try {
    var saved = localStorage.getItem("dclm-admin-theme") || (document.cookie.match(/theme=(dark|light)/) || [])[1] || "light";
    document.documentElement.setAttribute("data-bs-theme", saved);
  } catch(e){}
})();
"""),
        Script(src="/assets/js/chart.umd.min.js", defer=True),
        Script(src="/assets/js/admin-charts.js", defer=True),
        Script(src="/assets/js/admin-interactions.js", defer=True),
        Div(id="admin-loading-bar", cls="admin-loading-bar"),


        Div(
            Div(sidebar, cls="admin-sidebar-shell d-none d-lg-flex"),
            Drawer(sidebar, drawer_id="mobile-nav", title="DCLM Admin", placement="start", body_cls="p-0"),
            Div(
                Div(
                    # Left side: search box (hidden on small mobile, shown md+)
                    Form(
                        *hidden_context_inputs(ctx),
                        Input(
                            type="search",
                            name="q",
                            placeholder="Search people, counts, or locations...",
                            cls="form-control admin-search-input",
                        ),
                        cls="admin-search-form d-none d-md-flex",
                    ),
                    # Right side: notification + user avatar grouped together
                    Div(
                        Button(
                            Icon("bell", cls="fs-5"),
                            Span(cls="spinner-border spinner-border-sm htmx-indicator topbar-notify-indicator", style="width:.8rem;height:.8rem;", aria_hidden="true"),
                            cls=f"btn btn-light border position-relative topbar-icon-btn topbar-icon-btn--notify {Fx.base} {Fx.hover_lift}",
                            data_bs_toggle="offcanvas",
                            data_bs_target="#notification-drawer",
                            hx_get=ctx.url_for("/partials/notifications"),
                            hx_target="#notification-drawer-body",
                            hx_swap="innerHTML",
                            hx_indicator="this",
                            aria_label="Open notifications",
                            type="button",
                        ),
                        _user_menu(ctx),
                        cls="d-flex align-items-center gap-2 gap-md-3 topbar-action-row",
                    ),
                    cls="admin-topbar admin-page-frame",
                ),
                Main(
                    Div(
                        Div(
                            Div(
                                Div(
                                    H2(title, cls="h3 fw-semibold text-dark mb-1") if title else "",
                                    P(subtitle, cls="text-muted mb-0") if subtitle else "",
                                    cls="d-flex flex-column gap-1",
                                ) if show_shell_intro else "",
                                Div(primary_action, cls="ms-auto flex-shrink-0") if primary_action else "",
                                cls="d-flex flex-column flex-lg-row justify-content-between gap-3 mb-4",
                            ) if show_shell_intro or primary_action else "",
                            content,
                            cls="admin-page-body",
                        ),
                        cls="container-fluid px-3 px-lg-4 py-4 py-lg-5 admin-page-frame",
                    ),
                    cls="admin-main",
                ),
                # Persistent mobile bottom navigation (replaces scattered mobile-action-bar)
                _mobile_bottom_nav(ctx, active_key),
                cls="admin-content-shell",
            ),
            Drawer(Div(P("Select any item from the list to view its details here.", cls="text-muted"), id="detail-drawer-body"), drawer_id="detail-drawer", title="Details", body_cls="admin-drawer-body"),
            Drawer(Div(P("Use page actions to open forms in this panel.", cls="text-muted"), id="form-drawer-body"), drawer_id="form-drawer", title="Form", body_cls="admin-drawer-body"),
            Drawer(Div(P("You have no new notifications right now.", cls="text-muted"), id="notification-drawer-body"), drawer_id="notification-drawer", title="Notifications", body_cls="admin-drawer-body"),
            Drawer(_scope_drawer_content(ctx, request_path), drawer_id="scope-drawer", title="View settings", placement="end", body_cls="admin-drawer-body scope-drawer-body"),
            Modal(Div(P("Select an action above to continue.", cls="text-muted"), id="confirm-modal-body"), modal_id="confirm-modal", title="Confirm action"),
            toast_stack(),
            cls="admin-shell",
        ),
    )
