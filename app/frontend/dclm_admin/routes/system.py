from __future__ import annotations

import asyncio
from typing import Any

from fasthtml.common import A, Div, Form, H3, H4, Input, Option, P, Select, Textarea
from starlette.requests import Request

from faststrap import Accordion, AccordionItem, Button, PlaceholderCard, Spinner, TabPane, Tabs, ToggleGroup

from ..auth_context import build_context
from ..backend import BACKEND_ROUTE_FAMILIES, CORE_ADMIN_FAMILIES, SHARED_PLATFORM_FAMILIES, get_backend_status
from ..communication import AuthService, SystemService
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, primary_button, shell_layout
from ..components.ui import empty_state, filter_field, page_intro, page_stack, responsive_table, section_card, stat_card, status_badge
from ..mock_data import STORE, TODAY


SYSTEM_ITEMS = [
    ("overview", "Overview", "/system", 7),
    ("notifications", "Notifications", "/system/notifications", 7),
    ("public_intake", "Public Intake", "/system/public-intake", 7),
    ("versions", "App Versions", "/system/app-versions", 7),
    ("sync", "Sync Governance", "/system/sync", 7),
    ("health", "Health", "/system/health", 7),
    ("audit", "Audit Logs", "/system/audit-logs", 7),
    ("rbac", "RBAC Studio", "/system/rbac", 9),
    ("utilities", "Utilities", "/system/utilities", 9),
]

NOTIFICATION_FILTERS = [
    ("all", "All"),
    ("unread", "Unread"),
    ("read", "Read"),
]


def _system_allowed(ctx, min_level: int = 7) -> bool:
    return ctx.level >= min_level


def _system_guard(ctx, min_level: int, title: str, body_text: str) -> Div | None:
    if _system_allowed(ctx, min_level):
        return None
    return section_card(
        title,
        "This page opens only for higher-level roles.",
        empty_state("shield-lock", "Access restricted", body_text),
    )


async def _system_nav(ctx, active: str) -> Div:
    return Div(
        *[
            A(
                label,
                href=ctx.url_for(path),
                cls=f"btn {'btn-primary' if key == active else 'btn-outline-primary'} admin-inline-btn",
                **({"aria_current": "page"} if key == active else {}),
            )
            for key, label, path, min_level in SYSTEM_ITEMS
            if ctx.level >= min_level
        ],
        cls="workspace-tab-strip mb-4",
    )


async def _system_loading_section(target_id: str, *, hx_get: str, message: str) -> Div:
    return Div(
        Div(
            Spinner(variant="primary", size="sm", label="Loading"),
            P(message, cls="text-muted mb-0"),
            cls="d-flex align-items-center gap-3",
        ),
        PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
        PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
        id=target_id,
        hx_get=hx_get,
        hx_trigger="load",
        hx_swap="outerHTML",
        cls="d-grid gap-3",
    )


async def _system_overview_cards(request: Request, ctx) -> Div:
    summary = await SystemService.overview_summary(request, ctx)
    return Div(
        stat_card("Notifications", str(summary["notification_total"]), "System notification records", "bell", tone="primary"),
        stat_card("Unread", str(summary["notification_unread"]), "System items still waiting for review", "envelope", tone="warning"),
        stat_card(summary["api_label"], str(summary["api_value"]), "Backend status", "activity", tone="success"),
        stat_card(summary["support_label"], str(summary["support_value"]), "Support status", "gear", tone="info"),
        cls="counts-stat-grid",
    )


async def _integration_foundation_card(request: Request) -> Div:
    status = get_backend_status()
    auth_state = AuthService.session_snapshot(request)
    live_label = "Connected" if status["enabled"] else "Local"
    live_tone = "success" if status["enabled"] else "warning"
    return section_card(
        "Backend connection",
        "Connection status and available backend services.",
        Div(
            stat_card("Data source", live_label, "Active data source", "diagram-3", tone=live_tone),
            stat_card("Core admin families", str(status["core_admin_family_count"]), "Admin service groups", "shield-lock", tone="primary"),
            stat_card("Shared platform families", str(status["shared_platform_family_count"]), "Shared service groups", "share", tone="info"),
            stat_card("Total route families", str(status["total_family_count"]), "Available service groups", "stack", tone="success"),
            cls="counts-stat-grid",
        ),
        Div(
            Div(
                H4("API base", cls="h6 fw-semibold mb-2"),
                P(status["api_base_url"], cls="mb-0 text-muted"),
                cls="admin-info-block",
            ),
            Div(
                H4("Next target", cls="h6 fw-semibold mb-2"),
                P(str(status["next_target"]), cls="mb-0 text-muted"),
                cls="admin-info-block",
            ),
            Div(
                H4("Auth session", cls="h6 fw-semibold mb-2"),
                P(
                    auth_state["display_name"] if auth_state["authenticated"] else "No backend session is active in this browser session.",
                    cls="mb-1 text-muted",
                ),
                P(
                    f"Profile: {auth_state['profile_key']}" if auth_state["profile_key"] else f"Cookie: {status['session_cookie_name']}",
                    cls="small text-muted mb-0",
                ),
                cls="admin-info-block",
            ),
            Div(
                H4("Core admin route families", cls="h6 fw-semibold mb-2"),
                P(", ".join(name.replace("_", " ") for name in CORE_ADMIN_FAMILIES), cls="mb-0 text-muted"),
                cls="admin-info-block",
            ),
            Div(
                H4("Shared platform route families", cls="h6 fw-semibold mb-2"),
                P(", ".join(name.replace("_", " ") for name in SHARED_PLATFORM_FAMILIES), cls="mb-0 text-muted"),
                cls="admin-info-block",
            ),
            Div(
                H4("Backend-first notes", cls="h6 fw-semibold mb-2"),
                *[
                    P(f"{name.replace('_', ' ').title()}: {meta['notes']}", cls="small text-muted mb-2")
                    for name, meta in BACKEND_ROUTE_FAMILIES.items()
                    if meta["high_value"]
                ],
                cls="admin-info-block",
            ),
            cls="d-grid gap-3 mt-3",
        ),
    )


async def _notification_summary_cards(request: Request, ctx, *, oob: bool = False) -> Div:
    summary = await SystemService.notification_summary(request, ctx)
    live_mode = await SystemService.live_enabled(request)
    attrs = {"id": "system-notification-summary"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#system-notification-summary"
    return Div(
        stat_card("Total", str(summary["total"]), "Visible notification records", "bell", tone="primary"),
        stat_card(
            "Unread" if not live_mode else "Live items",
            str(summary["unread"]),
            "Items still waiting for review" if not live_mode else "Latest notification items",
            "envelope",
            tone="warning",
        ),
        stat_card("High priority", str(summary["high_priority"]), "Urgent items", "exclamation-triangle", tone="danger"),
        stat_card(
            "Health items" if not live_mode else "Operational activity",
            str(summary["health_items"]),
            "Service-related notices" if not live_mode else "Counts, finance, and fellowship items",
            "heart-pulse",
            tone="info",
        ),
        cls="counts-stat-grid",
        **attrs,
    )


def _notification_status_action(row: dict[str, Any]) -> tuple[str, str]:
    if row["status"] == "unread":
        return ("read", "Mark read")
    return ("unread", "Mark unread")


async def _notification_drawer_content(ctx, row: dict[str, Any], *, status_filter: str = "all", kind_filter: str = "all", allow_status_actions: bool = True) -> Div:
    next_status, button_label = _notification_status_action(row)
    action_block: Any = ""
    if allow_status_actions:
        action_block = Div(
            Button(
                button_label,
                variant="outline-primary",
                size="md",
                data_bs_toggle="modal",
                data_bs_target="#confirm-modal",
                hx_get=ctx.url_for(
                    f"/system/notifications/{row['notification_id']}/status",
                    action=next_status,
                    status_filter=status_filter,
                    kind_filter=kind_filter,
                ),
                hx_target="#confirm-modal-body",
                hx_swap="innerHTML",
            ),
            cls="d-grid gap-2 d-md-flex mb-3",
        )
    else:
        action_block = Div(
            P(
                "Notification status changes are not available for this item.",
                cls="small text-muted mb-0",
            ),
            cls="drawer-note-box mb-3",
        )
    return Div(
        H3(row["title"], cls="h5 fw-semibold"),
        P(f"{row['kind'].title()} notification", cls="text-muted"),
        Div(
            status_badge(row["priority"]),
            status_badge(row["status"]),
            cls="d-flex flex-wrap gap-2 mb-3",
        ),
        action_block,
        Div(H4("Details", cls="h6 fw-semibold mb-2"), P(row["body"], cls="mb-0"), cls="drawer-note-box mb-3"),
        Div(
            Div(P("Time", cls="small text-muted mb-1"), P(row["time"], cls="fw-semibold mb-0")),
            Div(P("Kind", cls="small text-muted mb-1"), P(row["kind"].title(), cls="fw-semibold mb-0")),
            cls="drawer-meta-grid",
        ),
    )


async def _notifications_workspace(request: Request, ctx, *, status: str = "all", kind: str = "all", oob: bool = False) -> Div:
    rows = await SystemService.list_notifications(request, ctx, status=status, kind=kind)
    supports_status = await SystemService.supports_notification_status(request)
    kind_options = await SystemService.notification_kind_filters(request)
    active_index = next((index for index, item in enumerate(NOTIFICATION_FILTERS) if item[0] == status), 0)
    status_toggle: Any = ""
    if supports_status:
        status_toggle = ToggleGroup(
            *[
                Button(
                    label,
                    variant="outline-primary",
                    size="md",
                    hx_get=ctx.url_for("/system/notifications/list", status=key, kind=kind),
                    hx_target="#system-notifications-workspace",
                    hx_swap="outerHTML",
                    cls="inbox-filter-chip",
                )
                for key, label in NOTIFICATION_FILTERS
            ],
            active_index=active_index,
            active_cls="active",
            cls="filter-chip-row admin-toggle-group",
        )
    filter_form = Form(
        *hidden_context_inputs(ctx),
        Input(type="hidden", name="status", value=status),
        filter_field(
            "Notification kind",
            Select(
                *[Option(label, value=key, selected=kind == key) for key, label in kind_options],
                name="kind",
                cls="form-select",
            ),
            field_id="system-notification-kind",
        ),
        hx_get=ctx.url_for("/system/notifications/list"),
        hx_target="#system-notifications-workspace",
        hx_swap="outerHTML",
        hx_trigger="change from:select",
        cls="admin-filter-grid mb-3",
    )
    note = ""
    mode_note = await SystemService.notification_mode_note(request)
    if mode_note:
        note = Div(P(mode_note, cls="small text-muted mb-0"), cls="drawer-note-box mb-3")

    if not rows:
        results = empty_state("bell", "No notification entries here", "Try another filter or switch to a wider system role.")
    else:
        desktop_rows = []
        mobile_cards = [
            Div(
                H4(row["title"], cls="h6 fw-semibold mb-1"),
                P(row["body"], cls="text-muted mb-2"),
                Div(status_badge(row["priority"]), status_badge(row["status"]), cls="d-flex flex-wrap gap-2 mb-2"),
                P(f"{row['kind'].title()} - {row['time']}", cls="small text-muted mb-3"),
                Div(
                    Button(
                        "Open",
                        variant="outline-primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#detail-drawer",
                        hx_get=ctx.url_for(
                            f"/system/notifications/{row['notification_id']}/drawer",
                            status_filter=status,
                            kind_filter=kind,
                        ),
                        hx_target="#detail-drawer-body",
                        hx_swap="innerHTML",
                        cls="w-100",
                    ),
                    *(
                        [
                            Button(
                                _notification_status_action(row)[1],
                                variant="outline-primary",
                                size="md",
                                data_bs_toggle="modal",
                                data_bs_target="#confirm-modal",
                                hx_get=ctx.url_for(
                                    f"/system/notifications/{row['notification_id']}/status",
                                    action=_notification_status_action(row)[0],
                                    status_filter=status,
                                    kind_filter=kind,
                                ),
                                hx_target="#confirm-modal-body",
                                hx_swap="innerHTML",
                                cls="w-100",
                            )
                        ]
                        if supports_status
                        else []
                    ),
                    cls="d-grid gap-2",
                ),
                cls="mobile-worker-card",
            )
            for row in rows
        ]
        for row in rows:
            desktop_rows.append(
                [
                    row["time"],
                    row["title"],
                    row["kind"].title(),
                    status_badge(row["priority"]),
                    status_badge(row["status"]),
                    Div(
                        Button(
                            "Open",
                            variant="outline-primary",
                            size="md",
                            data_bs_toggle="offcanvas",
                            data_bs_target="#detail-drawer",
                            hx_get=ctx.url_for(
                                f"/system/notifications/{row['notification_id']}/drawer",
                                status_filter=status,
                                kind_filter=kind,
                            ),
                            hx_target="#detail-drawer-body",
                            hx_swap="innerHTML",
                        ),
                        *(
                            [
                                Button(
                                    _notification_status_action(row)[1],
                                    variant="outline-primary",
                                    size="md",
                                    data_bs_toggle="modal",
                                    data_bs_target="#confirm-modal",
                                    hx_get=ctx.url_for(
                                        f"/system/notifications/{row['notification_id']}/status",
                                        action=_notification_status_action(row)[0],
                                        status_filter=status,
                                        kind_filter=kind,
                                    ),
                                    hx_target="#confirm-modal-body",
                                    hx_swap="innerHTML",
                                )
                            ]
                            if supports_status
                            else []
                        ),
                        cls="d-grid gap-2",
                    ),
                ]
            )
        results = responsive_table(
            ["Time", "Title", "Kind", "Priority", "Status", "Action"],
            desktop_rows,
            mobile_cards,
            results_id="system-notifications-results",
        )
    attrs = {"id": "system-notifications-workspace"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#system-notifications-workspace"
    return Div(status_toggle, note, filter_form, results, **attrs)


async def _app_version_drawer_content(ctx, row: dict[str, Any], *, platform_filter: str = "", status_filter: str = "all") -> Div:
    activate_button = ""
    if row["status"] != "active":
        activate_button = Button(
            "Make current version",
            variant="primary",
            size="md",
            data_bs_toggle="modal",
            data_bs_target="#confirm-modal",
            hx_get=ctx.url_for(
                f"/system/app-versions/{row['version_id']}/activate",
                platform_filter=platform_filter,
                status_filter=status_filter,
            ),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )
    return Div(
        H3(f"{row['platform']} {row['version_number']}", cls="h5 fw-semibold"),
        P(row["app_name"], cls="text-muted"),
        Div(status_badge(row["status"]), status_badge(row["force_update"]), cls="d-flex flex-wrap gap-2 mb-3"),
        Div(
            Div(P("Release date", cls="small text-muted mb-1"), P(row["release_date"], cls="fw-semibold mb-0")),
            Div(P("Minimum OS", cls="small text-muted mb-1"), P(row["min_os_version"], cls="fw-semibold mb-0")),
            cls="drawer-meta-grid mb-3",
        ),
        Div(H4("Release note", cls="h6 fw-semibold mb-2"), P(row["notes"] or "No release note added.", cls="mb-0"), cls="drawer-note-box mb-3"),
        Div(activate_button, cls="d-grid gap-2"),
    )


async def _app_versions_table(request: Request, ctx, *, platform: str = "", status: str = "", oob: bool = False) -> Div:
    rows = await SystemService.list_app_versions(request, platform=platform, status=status)
    content: Any
    attrs = {"id": "system-app-versions-table"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#system-app-versions-table"
    if not rows:
        content = empty_state("phone", "No app versions match this filter", "Try another platform or status.")
        return Div(content, **attrs)
    desktop_rows = []
    mobile_cards = []
    for row in rows:
        action_button = Button(
            "Open",
            variant="outline-primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#detail-drawer",
            hx_get=ctx.url_for(
                f"/system/app-versions/{row['version_id']}/drawer",
                platform_filter=platform,
                status_filter=status,
            ),
            hx_target="#detail-drawer-body",
            hx_swap="innerHTML",
        )
        desktop_actions = [action_button]
        mobile_actions = [action_button]
        if row["status"] != "active":
            activate_btn = Button(
                "Make current",
                variant="primary",
                size="md",
                data_bs_toggle="modal",
                data_bs_target="#confirm-modal",
                hx_get=ctx.url_for(
                    f"/system/app-versions/{row['version_id']}/activate",
                    platform_filter=platform,
                    status_filter=status,
                ),
                hx_target="#confirm-modal-body",
                hx_swap="innerHTML",
            )
            desktop_actions.append(activate_btn)
            mobile_actions.append(activate_btn)
        desktop_rows.append(
            [
                row["app_name"],
                row["platform"],
                row["version_number"],
                row["release_date"],
                status_badge(row["status"]),
                row["force_update"],
                Div(*desktop_actions, cls="d-grid gap-2"),
            ]
        )
        mobile_cards.append(
            Div(
                H4(f"{row['platform']} {row['version_number']}", cls="h6 fw-semibold mb-1"),
                P(row["notes"], cls="text-muted mb-2"),
                Div(status_badge(row["status"]), status_badge(row["force_update"]), cls="d-flex flex-wrap gap-2 mb-2"),
                P(f"Release date: {row['release_date']}", cls="small text-muted mb-3"),
                Div(*mobile_actions, cls="d-grid gap-2"),
                cls="mobile-worker-card",
            )
        )
    content = responsive_table(
        ["App", "Platform", "Version", "Release Date", "Status", "Force Update", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="system-app-versions-results",
    )
    return Div(content, **attrs)


async def _sync_summary_cards(request: Request, *, oob: bool = False) -> Div:
    summary = await SystemService.sync_conflict_summary(request)
    changes = await SystemService.sync_changes_snapshot(request)
    attrs = {"id": "system-sync-summary"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#system-sync-summary"
    return Div(
        stat_card("Total conflicts", str(summary["total"]), "Visible sync collisions currently awaiting review", "exclamation-octagon", tone="danger"),
        stat_card("Client ID duplicates", str(summary["client_id"]), "Repeated client-generated identifiers", "phone", tone="warning"),
        stat_card("Key collisions", str(summary["key"]), "Same record keys appearing more than once", "diagram-3", tone="primary"),
        stat_card("Last 24h changes", str(changes["total_changes"]), "Recent offline-to-server change volume from the sync endpoint", "arrow-repeat", tone="info"),
        cls="counts-stat-grid",
        **attrs,
    )


async def _sync_resolution_actions(ctx, row: dict[str, Any]) -> Div:
    buttons = [
        Button(
            "Keep server",
            variant="outline-primary",
            size="md",
            data_bs_toggle="modal",
            data_bs_target="#confirm-modal",
            hx_get=ctx.url_for(f"/system/sync/conflicts/{row['conflict_id']}/resolve", resolution="keep_server"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        ),
        Button(
            "Keep client",
            variant="outline-primary",
            size="md",
            data_bs_toggle="modal",
            data_bs_target="#confirm-modal",
            hx_get=ctx.url_for(f"/system/sync/conflicts/{row['conflict_id']}/resolve", resolution="keep_client"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        ),
    ]
    if row["merge_allowed"]:
        buttons.append(
            Button(
                "Merge",
                variant="primary",
                size="md",
                data_bs_toggle="modal",
                data_bs_target="#confirm-modal",
                hx_get=ctx.url_for(f"/system/sync/conflicts/{row['conflict_id']}/resolve", resolution="merge"),
                hx_target="#confirm-modal-body",
                hx_swap="innerHTML",
            )
        )
    return Div(*buttons, cls="d-grid gap-2")


async def _sync_conflict_drawer_content(ctx, row: dict[str, Any]) -> Div:
    return Div(
        H3(row["title"], cls="h5 fw-semibold"),
        P("Sync governance detail", cls="text-muted"),
        Div(
            status_badge("danger" if row["kind"] == "key" else "warning"),
            status_badge(row["model"]),
            cls="d-flex flex-wrap gap-2 mb-3",
        ),
        Div(
            Div(P("Conflict ID", cls="small text-muted mb-1"), P(row["conflict_id"], cls="fw-semibold mb-0")),
            Div(P("Duplicate count", cls="small text-muted mb-1"), P(str(row["count"]), cls="fw-semibold mb-0")),
            cls="drawer-meta-grid mb-3",
        ),
        Div(H4("Record detail", cls="h6 fw-semibold mb-2"), P(row["detail"], cls="mb-0"), cls="drawer-note-box mb-3"),
        Div(
            P(
                "Choose a resolution that matches the record truth. Merge is available only where the backend supports it safely.",
                cls="small text-muted mb-3",
            ),
            _sync_resolution_actions(ctx, row),
            cls="d-grid gap-2",
        ),
    )


async def _sync_workspace(request: Request, ctx, *, oob: bool = False) -> Div:
    note = await SystemService.sync_mode_note(request)
    attrs = {"id": "system-sync-workspace"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#system-sync-workspace"
    if note:
        return Div(
            Div(P(note, cls="small text-muted mb-0"), cls="drawer-note-box mb-3"),
            empty_state("arrow-repeat", "Backend connection required", "Sign in to review sync conflicts."),
            **attrs,
        )
    rows = await SystemService.list_sync_conflicts(request)
    if not rows:
        return Div(
            empty_state("check-circle", "No sync conflicts", "No duplicate sync records are waiting for review."),
            **attrs,
        )
    desktop_rows = []
    mobile_cards = []
    for row in rows:
        open_btn = Button(
            "Open",
            variant="outline-primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#detail-drawer",
            hx_get=ctx.url_for(f"/system/sync/conflicts/{row['conflict_id']}/drawer"),
            hx_target="#detail-drawer-body",
            hx_swap="innerHTML",
        )
        desktop_rows.append(
            [
                row["model"].replace("_", " ").title(),
                row["kind"].replace("_", " ").title(),
                row["detail"],
                str(row["count"]),
                Div(open_btn, cls="d-grid gap-2"),
            ]
        )
        mobile_cards.append(
            Div(
                H4(row["title"], cls="h6 fw-semibold mb-1"),
                P(row["detail"], cls="text-muted mb-2"),
                Div(status_badge(row["model"]), status_badge(row["kind"]), cls="d-flex flex-wrap gap-2 mb-2"),
                P(f"{row['count']} duplicate record(s) detected.", cls="small text-muted mb-3"),
                Div(open_btn, cls="d-grid gap-2"),
                cls="mobile-worker-card",
            )
        )
    return Div(
        responsive_table(
            ["Model", "Conflict", "Detail", "Count", "Action"],
            desktop_rows,
            mobile_cards,
            results_id="system-sync-results",
        ),
        **attrs,
    )


async def _health_view(request: Request) -> Div:
    health = await SystemService.health_snapshot(request)
    services = Accordion(
        *[
            AccordionItem(
                P(service["note"], cls="mb-0"),
                title=f"{service['name']} - {service['status'].title()}",
                expanded=index == 0,
            )
            for index, service in enumerate(health["services"])
        ]
    )
    live_mode = await SystemService.live_enabled(request)
    return Div(
        Div(
            stat_card("System status", health["status"].title(), "Overall health picture", "heart-pulse", tone="success"),
            stat_card(
                "API latency" if not live_mode else "API version",
                f"{health['api_latency_ms']} ms" if not live_mode else str(health.get("api_version") or "Live"),
                "Current request latency" if not live_mode else "Backend release currently responding",
                "activity",
                tone="primary",
            ),
            stat_card(
                "Queue wait" if not live_mode else "Known endpoints",
                f"{health['queue_wait_seconds']} sec" if not live_mode else str(health.get("endpoint_count") or 0),
                "Approximate background delay" if not live_mode else "Available backend endpoints",
                "hourglass-split",
                tone="warning",
            ),
            stat_card(
                "DB connections" if not live_mode else "Workers table",
                str(health["db_connections"]) if not live_mode else str(health.get("tables", {}).get("workers", 0)),
                "Current database usage" if not live_mode else "Live worker records currently stored",
                "database",
                tone="info",
            ),
            cls="counts-stat-grid",
        ),
        section_card(
            "Service health",
            "Each system area stays readable as an accordion so phone users are not overwhelmed.",
            services,
        ),
    )


async def _audit_workspace(request: Request, ctx, *, search: str = "", status: str = "all") -> Div:
    rows = await SystemService.list_audit_logs(request, ctx, search=search, status=status)
    filter_form = Form(
        *hidden_context_inputs(ctx),
        filter_field(
            "Search audit logs",
            Input(type="search", name="search", value=search, placeholder="Search actor, action, target, or scope", cls="form-control"),
            field_id="system-audit-search",
        ),
        filter_field(
            "Audit status",
            Select(
                Option("All status", value="all"),
                Option("Success", value="success", selected=status == "success"),
                Option("Warning", value="warning", selected=status == "warning"),
                Option("Info", value="info", selected=status == "info"),
                name="status",
                cls="form-select",
            ),
            field_id="system-audit-status",
        ),
        hx_get=ctx.url_for("/system/audit-logs/list"),
        hx_target="#system-audit-workspace",
        hx_swap="outerHTML",
        hx_trigger="keyup changed delay:350ms from:input, change from:select",
        cls="admin-filter-grid mb-3",
    )
    if not rows:
        results = empty_state("journal-text", "No audit logs match this view", "Try a different status or search term.")
    else:
        desktop_rows = [
            [row["time"], row["actor"], row["action"], row["target"], row["scope_label"], status_badge(row["status"])]
            for row in rows
        ]
        mobile_cards = [
            Div(
                H4(row["actor"], cls="h6 fw-semibold mb-1"),
                P(row["action"], cls="text-dark mb-1"),
                P(row["target"], cls="text-muted mb-2"),
                Div(status_badge(row["status"]), cls="mb-2"),
                P(f"{row['scope_label']} - {row['time']}", cls="small text-muted mb-0"),
                cls="mobile-worker-card",
            )
            for row in rows
        ]
        results = responsive_table(
            ["Time", "Actor", "Action", "Target", "Scope", "Status"],
            desktop_rows,
            mobile_cards,
            results_id="system-audit-results",
        )
    return Div(filter_form, results, id="system-audit-workspace")


async def _public_contact_drawer_content(ctx, row: dict[str, Any], *, status_filter: str = "all", search: str = "") -> Div:
    return Div(
        H3(row["name"], cls="h5 fw-semibold"),
        P(row["subject"], cls="text-muted"),
        Div(
            status_badge(row["status"]),
            cls="d-flex flex-wrap gap-2 mb-3",
        ),
        Div(
            Div(P("Email", cls="small text-muted mb-1"), P(row["email"] or "Not supplied", cls="fw-semibold mb-0")),
            Div(P("Phone", cls="small text-muted mb-1"), P(row["phone"] or "Not supplied", cls="fw-semibold mb-0")),
            cls="drawer-meta-grid mb-3",
        ),
        Div(H4("Message", cls="h6 fw-semibold mb-2"), P(row["message"], cls="mb-0"), cls="drawer-note-box mb-3"),
        Div(
            P(f"Submitted: {row['created_at']}", cls="small text-muted mb-1"),
            P(f"Reviewed: {row['reviewed_at'] or 'Not yet reviewed'}", cls="small text-muted mb-0"),
            cls="drawer-note-box mb-3",
        ),
        Div(
            Button(
                "Review submission",
                variant="primary",
                size="md",
                data_bs_toggle="modal",
                data_bs_target="#confirm-modal",
                hx_get=ctx.url_for(f"/system/public-intake/contact/{row['submission_id']}/review", status_filter=status_filter, search=search),
                hx_target="#confirm-modal-body",
                hx_swap="innerHTML",
            ),
            cls="d-grid gap-2",
        ),
    )


async def _public_prayer_drawer_content(ctx, row: dict[str, Any], *, status_filter: str = "all", urgent_filter: str = "all", search: str = "") -> Div:
    return Div(
        H3(row["name"], cls="h5 fw-semibold"),
        P("Public prayer request", cls="text-muted"),
        Div(
            status_badge(row["status"]),
            status_badge("urgent" if row["is_urgent"] else "regular"),
            cls="d-flex flex-wrap gap-2 mb-3",
        ),
        Div(
            Div(P("Email", cls="small text-muted mb-1"), P(row["email"] or "Not supplied", cls="fw-semibold mb-0")),
            Div(P("Phone", cls="small text-muted mb-1"), P(row["phone"] or "Not supplied", cls="fw-semibold mb-0")),
            cls="drawer-meta-grid mb-3",
        ),
        Div(H4("Prayer request", cls="h6 fw-semibold mb-2"), P(row["request"], cls="mb-0"), cls="drawer-note-box mb-3"),
        Div(
            P(f"Submitted: {row['created_at']}", cls="small text-muted mb-1"),
            P(f"Reviewed: {row['reviewed_at'] or 'Not yet reviewed'}", cls="small text-muted mb-0"),
            cls="drawer-note-box mb-3",
        ),
        Div(
            Button(
                "Review request",
                variant="primary",
                size="md",
                data_bs_toggle="modal",
                data_bs_target="#confirm-modal",
                hx_get=ctx.url_for(f"/system/public-intake/prayer/{row['submission_id']}/review", status_filter=status_filter, urgent_filter=urgent_filter, search=search),
                hx_target="#confirm-modal-body",
                hx_swap="innerHTML",
            ),
            cls="d-grid gap-2",
        ),
    )


async def _public_contact_workspace(request: Request, ctx, *, status: str = "all", search: str = "", oob: bool = False) -> Div:
    rows = await SystemService.list_public_contacts(request, status=status, search=search)
    attrs = {"id": "system-public-contact-workspace"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#system-public-contact-workspace"
    filter_form = Form(
        *hidden_context_inputs(ctx),
        filter_field(
            "Contact status",
            Select(
                Option("All status", value="all"),
                Option("New", value="new", selected=status == "new"),
                Option("Reviewed", value="reviewed", selected=status == "reviewed"),
                Option("Closed", value="closed", selected=status == "closed"),
                Option("Routed", value="routed", selected=status == "routed"),
                name="status",
                cls="form-select",
            ),
            field_id="public-contact-status",
        ),
        filter_field(
            "Search contact submissions",
            Input(type="search", name="search", value=search, placeholder="Search name, email, or subject", cls="form-control"),
            field_id="public-contact-search",
        ),
        hx_get=ctx.url_for("/system/public-intake/contact/list"),
        hx_target="#system-public-contact-workspace",
        hx_swap="outerHTML",
        hx_trigger="change from:select, keyup changed delay:350ms from:input",
        cls="admin-filter-grid mb-3",
    )
    if not rows:
        content = empty_state("envelope", "No public contact submissions", "No public contact requests are available.")
    else:
        desktop_rows = [
            [
                row["created_at"],
                row["name"],
                row["subject"],
                row["email"],
                status_badge(row["status"]),
                Div(
                    Button(
                        "Open",
                        variant="outline-primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#detail-drawer",
                        hx_get=ctx.url_for(f"/system/public-intake/contact/{row['submission_id']}/drawer", status_filter=status, search=search),
                        hx_target="#detail-drawer-body",
                        hx_swap="innerHTML",
                    ),
                    Button(
                        "Review",
                        variant="primary",
                        size="md",
                        data_bs_toggle="modal",
                        data_bs_target="#confirm-modal",
                        hx_get=ctx.url_for(f"/system/public-intake/contact/{row['submission_id']}/review", status_filter=status, search=search),
                        hx_target="#confirm-modal-body",
                        hx_swap="innerHTML",
                    ),
                    cls="d-grid gap-2",
                ),
            ]
            for row in rows
        ]
        mobile_cards = [
            Div(
                H4(row["name"], cls="h6 fw-semibold mb-1"),
                P(row["subject"], cls="text-dark mb-1"),
                P(row["email"], cls="text-muted mb-2"),
                Div(status_badge(row["status"]), cls="mb-2"),
                P(f"Submitted: {row['created_at']}", cls="small text-muted mb-3"),
                Div(
                    Button(
                        "Open",
                        variant="outline-primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#detail-drawer",
                        hx_get=ctx.url_for(f"/system/public-intake/contact/{row['submission_id']}/drawer", status_filter=status, search=search),
                        hx_target="#detail-drawer-body",
                        hx_swap="innerHTML",
                        cls="w-100",
                    ),
                    Button(
                        "Review",
                        variant="primary",
                        size="md",
                        data_bs_toggle="modal",
                        data_bs_target="#confirm-modal",
                        hx_get=ctx.url_for(f"/system/public-intake/contact/{row['submission_id']}/review", status_filter=status, search=search),
                        hx_target="#confirm-modal-body",
                        hx_swap="innerHTML",
                        cls="w-100",
                    ),
                    cls="d-grid gap-2",
                ),
                cls="mobile-worker-card",
            )
            for row in rows
        ]
        content = responsive_table(
            ["Submitted", "Name", "Subject", "Email", "Status", "Action"],
            desktop_rows,
            mobile_cards,
            results_id="system-public-contact-results",
        )
    return Div(filter_form, content, **attrs)


async def _public_prayer_workspace(request: Request, ctx, *, status: str = "all", urgent: str = "all", search: str = "", oob: bool = False) -> Div:
    rows = await SystemService.list_public_prayers(request, status=status, urgent=urgent, search=search)
    attrs = {"id": "system-public-prayer-workspace"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#system-public-prayer-workspace"
    filter_form = Form(
        *hidden_context_inputs(ctx),
        filter_field(
            "Prayer status",
            Select(
                Option("All status", value="all"),
                Option("New", value="new", selected=status == "new"),
                Option("Reviewed", value="reviewed", selected=status == "reviewed"),
                Option("Closed", value="closed", selected=status == "closed"),
                Option("Routed", value="routed", selected=status == "routed"),
                name="status",
                cls="form-select",
            ),
            field_id="public-prayer-status",
        ),
        filter_field(
            "Urgency",
            Select(
                Option("All urgency", value="all"),
                Option("Urgent", value="urgent", selected=urgent == "urgent"),
                Option("Regular", value="regular", selected=urgent == "regular"),
                name="urgent",
                cls="form-select",
            ),
            field_id="public-prayer-urgency",
        ),
        filter_field(
            "Search prayer requests",
            Input(type="search", name="search", value=search, placeholder="Search name, email, or request", cls="form-control"),
            field_id="public-prayer-search",
        ),
        hx_get=ctx.url_for("/system/public-intake/prayer/list"),
        hx_target="#system-public-prayer-workspace",
        hx_swap="outerHTML",
        hx_trigger="change from:select, keyup changed delay:350ms from:input",
        cls="admin-filter-grid mb-3",
    )
    if not rows:
        content = empty_state("heart", "No public prayer submissions", "No public prayer requests are available.")
    else:
        desktop_rows = [
            [
                row["created_at"],
                row["name"],
                "Urgent" if row["is_urgent"] else "Regular",
                row["email"] or row["phone"] or "Not supplied",
                status_badge(row["status"]),
                Div(
                    Button(
                        "Open",
                        variant="outline-primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#detail-drawer",
                        hx_get=ctx.url_for(f"/system/public-intake/prayer/{row['submission_id']}/drawer", status_filter=status, urgent_filter=urgent, search=search),
                        hx_target="#detail-drawer-body",
                        hx_swap="innerHTML",
                    ),
                    Button(
                        "Review",
                        variant="primary",
                        size="md",
                        data_bs_toggle="modal",
                        data_bs_target="#confirm-modal",
                        hx_get=ctx.url_for(f"/system/public-intake/prayer/{row['submission_id']}/review", status_filter=status, urgent_filter=urgent, search=search),
                        hx_target="#confirm-modal-body",
                        hx_swap="innerHTML",
                    ),
                    cls="d-grid gap-2",
                ),
            ]
            for row in rows
        ]
        mobile_cards = [
            Div(
                H4(row["name"], cls="h6 fw-semibold mb-1"),
                P(row["request"], cls="text-dark mb-2"),
                Div(status_badge(row["status"]), status_badge("urgent" if row["is_urgent"] else "regular"), cls="d-flex flex-wrap gap-2 mb-2"),
                P(f"Submitted: {row['created_at']}", cls="small text-muted mb-3"),
                Div(
                    Button(
                        "Open",
                        variant="outline-primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#detail-drawer",
                        hx_get=ctx.url_for(f"/system/public-intake/prayer/{row['submission_id']}/drawer", status_filter=status, urgent_filter=urgent, search=search),
                        hx_target="#detail-drawer-body",
                        hx_swap="innerHTML",
                        cls="w-100",
                    ),
                    Button(
                        "Review",
                        variant="primary",
                        size="md",
                        data_bs_toggle="modal",
                        data_bs_target="#confirm-modal",
                        hx_get=ctx.url_for(f"/system/public-intake/prayer/{row['submission_id']}/review", status_filter=status, urgent_filter=urgent, search=search),
                        hx_target="#confirm-modal-body",
                        hx_swap="innerHTML",
                        cls="w-100",
                    ),
                    cls="d-grid gap-2",
                ),
                cls="mobile-worker-card",
            )
            for row in rows
        ]
        content = responsive_table(
            ["Submitted", "Name", "Urgency", "Contact", "Status", "Action"],
            desktop_rows,
            mobile_cards,
            results_id="system-public-prayer-results",
        )
    return Div(filter_form, content, **attrs)


async def _rbac_view(request: Request, ctx, *, family: str = "all", search: str = "", oob: bool = False) -> Div:
    roles = await SystemService.list_rbac_roles(request) if await SystemService.live_enabled(request) else STORE.list_rbac_roles()
    permissions = await SystemService.list_rbac_permissions(request, family=family, search=search) if await SystemService.live_enabled(request) else STORE.list_rbac_permissions(family=family, search=search)
    roles_rows = []
    roles_cards = [
        Div(
            H4(row["name"], cls="h6 fw-semibold mb-1"),
            P(f"Level {row['level']}", cls="text-muted mb-2"),
            P(f"Permissions: {row['permission_count']}", cls="small text-dark mb-2"),
            Div(
                Button(
                    "Open",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/system/rbac/roles/{row['role_id']}/drawer", family=family, search=search),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                    cls="w-100",
                ),
                Button(
                    "Edit",
                    variant="primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#form-drawer",
                    hx_get=ctx.url_for(f"/system/rbac/roles/{row['role_id']}/edit", family=family, search=search),
                    hx_target="#form-drawer-body",
                    hx_swap="innerHTML",
                    cls="w-100",
                ),
                cls="d-grid gap-2",
            ),
            cls="mobile-worker-card",
        )
        for row in roles
    ]
    permission_filter = Form(
        *hidden_context_inputs(ctx),
        filter_field(
            "Search permissions",
            Input(type="search", name="search", value=search, placeholder="Search family or permission key", cls="form-control"),
            field_id="rbac-permission-search",
        ),
        filter_field(
            "Permission family",
            Select(
                Option("All families", value="all"),
                Option("Announcements", value="announcements", selected=family == "announcements"),
                Option("Media", value="media", selected=family == "media"),
                Option("Reports", value="reports", selected=family == "reports"),
                Option("Notifications", value="notifications", selected=family == "notifications"),
                Option("System", value="system", selected=family == "system"),
                Option("RBAC", value="rbac", selected=family == "rbac"),
                name="family",
                cls="form-select",
            ),
            field_id="rbac-permission-family",
        ),
        action=ctx.url_for("/system/rbac"),
        method="get",
        cls="admin-filter-grid mb-3",
    )
    permission_rows = []
    permission_cards = [
        Div(
            H4(row["key"], cls="h6 fw-semibold mb-1"),
            P(f"Family: {row['family'].title()}", cls="text-muted mb-1"),
            P(f"Scope: {row['scope']}", cls="small text-muted mb-2"),
            Button(
                "Open",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(f"/system/rbac/permissions/{row['permission_id']}/drawer", family=family, search=search),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="w-100",
            ),
            cls="mobile-worker-card",
        )
        for row in permissions
    ]
    for row in roles:
        roles_rows.append(
            [
                row["name"],
                f"Level {row['level']}",
                row["permission_count"],
                status_badge(row["status"]),
                Div(
                    Button(
                        "Open",
                        variant="outline-primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#detail-drawer",
                        hx_get=ctx.url_for(f"/system/rbac/roles/{row['role_id']}/drawer", family=family, search=search),
                        hx_target="#detail-drawer-body",
                        hx_swap="innerHTML",
                    ),
                    Button(
                        "Edit",
                        variant="primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#form-drawer",
                        hx_get=ctx.url_for(f"/system/rbac/roles/{row['role_id']}/edit", family=family, search=search),
                        hx_target="#form-drawer-body",
                        hx_swap="innerHTML",
                    ),
                    cls="d-grid gap-2",
                ),
            ]
        )
    for row in permissions:
        permission_rows.append(
            [
                row["family"].title(),
                row["key"],
                row["scope"],
                Div(
                    Button(
                        "Open",
                        variant="outline-primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#detail-drawer",
                        hx_get=ctx.url_for(f"/system/rbac/permissions/{row['permission_id']}/drawer", family=family, search=search),
                        hx_target="#detail-drawer-body",
                        hx_swap="innerHTML",
                    ),
                    cls="d-grid gap-2",
                ),
            ]
        )
    attrs = {"id": "system-rbac-workspace"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#system-rbac-workspace"
    return Div(
        Tabs(
            ("system-rbac-roles", "Roles", True),
            ("system-rbac-permissions", "Permissions"),
            variant="pills",
            cls="mb-3",
        ),
        Div(
            TabPane(
                responsive_table(
                    ["Role", "Level", "Permissions", "Status", "Action"],
                    roles_rows,
                    roles_cards,
                    results_id="system-rbac-roles-table",
                ),
                tab_id="system-rbac-roles",
                active=True,
            ),
            TabPane(
                Div(
                    permission_filter,
                    responsive_table(
                        ["Family", "Permission", "Scope", "Action"],
                        permission_rows,
                        permission_cards,
                        results_id="system-rbac-permissions-table",
                    ),
                ),
                tab_id="system-rbac-permissions",
            ),
            cls="tab-content",
        ),
        **attrs,
    )


async def _rbac_role_drawer_content(request: Request, ctx, role: dict[str, Any], *, family: str = "all", search: str = "") -> Div:
    permissions = role.get("permissions") if await SystemService.live_enabled(request) else STORE.list_role_permissions(role["role_id"])
    families = sorted({permission["family"].title() for permission in permissions})
    permission_preview = [P(permission["key"], cls="mb-2") for permission in permissions] or [P("No permissions are attached.", cls="text-muted mb-0")]
    return Div(
        H3(role["name"], cls="h5 fw-semibold"),
        P(f"Level {role['level']} role", cls="text-muted"),
        Div(
            status_badge(role["status"]),
            P(f"Scope: {role['scope']}", cls="small text-muted mb-0"),
            cls="d-flex flex-wrap gap-2 align-items-center mb-3",
        ),
        Div(
            Button(
                "Edit role",
                variant="primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for(f"/system/rbac/roles/{role['role_id']}/edit", family=family, search=search),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            cls="d-grid gap-2 mb-3",
        ),
        Div(H4("Description", cls="h6 fw-semibold mb-2"), P(role["description"], cls="mb-0"), cls="drawer-note-box mb-3"),
        Div(
            Div(P("Assigned permissions", cls="small text-muted mb-1"), P(str(role["permission_count"]), cls="fw-semibold mb-0")),
            Div(P("Families", cls="small text-muted mb-1"), P(", ".join(families) or "None", cls="fw-semibold mb-0")),
            cls="drawer-meta-grid mb-3",
        ),
        Div(
            H4("Permission preview", cls="h6 fw-semibold mb-2"),
            *permission_preview,
            cls="drawer-note-box",
        ),
    )


async def _rbac_permission_drawer_content(permission: dict[str, Any]) -> Div:
    return Div(
        H3(permission["key"], cls="h5 fw-semibold"),
        P(permission["family"].title(), cls="text-muted"),
        Div(status_badge(permission["scope"]), cls="mb-3"),
        Div(
            Div(P("Family", cls="small text-muted mb-1"), P(permission["family"].title(), cls="fw-semibold mb-0")),
            Div(P("Scope", cls="small text-muted mb-1"), P(permission["scope"], cls="fw-semibold mb-0")),
            cls="drawer-meta-grid mb-3",
        ),
        Div(
            H4("Backend vocabulary", cls="h6 fw-semibold mb-2"),
            P("This permission key follows the normalized backend family naming used by the API and RBAC seed scripts.", cls="mb-0"),
            cls="drawer-note-box",
        ),
    )


async def _rbac_role_form(request: Request, ctx, role: dict[str, Any], *, family: str = "all", search: str = "") -> Form:
    permissions = await SystemService.list_rbac_permissions(request) if await SystemService.live_enabled(request) else STORE.list_rbac_permissions()
    assigned = set(role.get("permission_ids", []))
    permission_fields = []
    for permission in permissions:
        permission_fields.append(
            Div(
                Input(
                    type="checkbox",
                    name=f"perm_{permission['permission_id']}",
                    checked=permission["permission_id"] in assigned,
                    cls="form-check-input mt-1",
                ),
                Div(
                    P(permission["key"], cls="fw-semibold mb-1"),
                    P(f"{permission['family'].title()} - {permission['scope']}", cls="small text-muted mb-0"),
                ),
                cls="form-check d-flex gap-3 align-items-start border rounded-3 p-3 mb-2",
            )
        )
    return Form(
        *hidden_context_inputs(ctx),
        Input(type="hidden", name="family", value=family),
        Input(type="hidden", name="search", value=search),
        H3("Edit RBAC role", cls="h5 fw-semibold"),
        P(f"Update {role['name']} using the same permission family language used by the backend.", cls="text-muted"),
        Textarea(role["description"], name="description", cls="form-control mb-3", rows="4"),
        *(
            []
            if await SystemService.live_enabled(request)
            else [
                Div(
                    Input(type="text", name="scope", value=role["scope"], cls="form-control", required=True),
                    Select(
                        Option("Active", value="active", selected=role["status"] == "active"),
                        Option("Suspended", value="suspended", selected=role["status"] == "suspended"),
                        name="status",
                        cls="form-select",
                        required=True,
                    ),
                    cls="drawer-two-up mb-3",
                )
            ]
        ),
        section_card(
            "Permission preview set",
            "Permission keys assigned to this role.",
            Div(*permission_fields, cls="d-grid gap-2"),
        ),
        Button("Save role", variant="primary", type="submit", cls="w-100"),
        hx_post=ctx.url_for(f"/system/rbac/roles/{role['role_id']}/update"),
        hx_target="#form-drawer-body",
        hx_swap="innerHTML",
    )


def register_system_routes(app) -> None:
    @app.get("/system")
    async def system_home(request: Request):
        ctx = build_context(request)
        blocked = _system_guard(ctx, 7, "System", "System tools are reserved for national-level governance roles and above.")
        if blocked is not None:
            return shell_layout(
                ctx,
                request_path=request.url.path,
                active_key="system",
                title="System",
                subtitle="Governance, audit, health, and utilities.",
                primary_action=None,
                content=page_stack(blocked),
            )

        cards = [
            {"title": label, "path": path}
            for key, label, path, min_level in SYSTEM_ITEMS
            if key != "overview" and ctx.level >= min_level
        ]
        body = page_stack(
            page_intro(
                "System",
                "System tools for releases, audit, health, and permissions.",
                scope_label=ctx.current_scope_label,
                scope_kind=ctx.current_scope_kind,
            ),
            await _system_nav(ctx, "overview"),
            section_card(
                "System overview",
                "Health, notifications, and tools available to this role.",
                await _system_overview_cards(request, ctx),
                Div(
                    *[
                        A(
                            card["title"],
                            href=ctx.url_for(card["path"]),
                            cls="quick-action",
                        )
                        for card in cards
                    ],
                    cls="quick-actions-grid",
                ),
            ),
            await _integration_foundation_card(request),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="system",
            title="System",
            subtitle="Governance, audit, health, and utilities.",
            primary_action=None,
            content=body,
        )

    @app.get("/system/notifications")
    async def system_notifications_page(request: Request, status: str = "all", kind: str = "all"):
        ctx = build_context(request)
        blocked = _system_guard(ctx, 7, "Notification Center", "Notification history opens from national-level roles upward.")
        if blocked is not None:
            body = page_stack(page_intro("System", "System notifications and governance alerts.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind), blocked)
        else:
            body = page_stack(
                page_intro("System", "Review notification history, release alerts, RBAC reminders, and health notices in one page.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind),
                _system_nav(ctx, "notifications"),
                _system_loading_section(
                    "system-notifications-content",
                    hx_get=ctx.url_for("/system/notifications/content", status=status, kind=kind),
                    message="Loading notification history.",
                ),
            )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="system",
            title="Notification Center",
            subtitle="System alerts and history.",
            primary_action=None,
            content=body,
        )

    @app.get("/system/notifications/content")
    async def system_notifications_content(request: Request, status: str = "all", kind: str = "all"):
        ctx = build_context(request)
        if not _system_allowed(ctx, 7):
            return Div(
                section_card(
                    "Notification Center",
                    "Notification history opens from national-level roles upward.",
                    empty_state("shield-lock", "Notification Center", "Notification history opens from national-level roles upward."),
                ),
                id="system-notifications-content",
            )
        summary_cards, workspace = await asyncio.gather(
            _notification_summary_cards(request, ctx),
            _notifications_workspace(request, ctx, status=status, kind=kind),
        )
        return Div(
            section_card(
                "Notification Center",
                "Notification history and status.",
                summary_cards,
                workspace,
            ),
            id="system-notifications-content",
        )

    @app.get("/system/notifications/list")
    async def system_notifications_list(request: Request, status: str = "all", kind: str = "all"):
        ctx = build_context(request)
        return await _notifications_workspace(request, ctx, status=status, kind=kind)

    @app.get("/system/notifications/{notification_id}/drawer")
    async def system_notification_drawer(request: Request, notification_id: str, status_filter: str = "all", kind_filter: str = "all"):
        ctx = build_context(request)
        row = await SystemService.get_notification(request, ctx, notification_id, status=status_filter, kind=kind_filter)
        if row is None:
            return P("Notification not found.", cls="text-muted")
        return await _notification_drawer_content(
            ctx,
            row,
            status_filter=status_filter,
            kind_filter=kind_filter,
            allow_status_actions=await SystemService.supports_notification_status(request),
        )

    @app.get("/system/notifications/{notification_id}/status")
    async def system_notification_status_confirm(
        request: Request,
        notification_id: str,
        action: str = "read",
        status_filter: str = "all",
        kind_filter: str = "all",
    ):
        ctx = build_context(request)
        if not await SystemService.supports_notification_status(request):
            return P("Notification status changes are not available.", cls="text-muted")
        row = await SystemService.get_notification(request, ctx, notification_id, status=status_filter, kind=kind_filter)
        if row is None:
            return P("Notification not found.", cls="text-muted")
        label = "Mark as read" if action == "read" else "Mark as unread"
        return Form(
            *hidden_context_inputs(ctx),
            Input(type="hidden", name="action", value=action),
            Input(type="hidden", name="status_filter", value=status_filter),
            Input(type="hidden", name="kind_filter", value=kind_filter),
            H3(label, cls="h5 fw-semibold"),
            P(row["title"], cls="text-muted"),
            P("Update this notification status.", cls="small text-muted mb-3"),
            Button(label, variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/system/notifications/{notification_id}/status"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/system/notifications/{notification_id}/status")
    async def system_notification_status_update(request: Request, notification_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        status_filter = data.get("status_filter", "all")
        kind_filter = data.get("kind_filter", "all")
        if await SystemService.live_enabled(request):
            updated = await SystemService.set_notification_status(request, notification_id, status=data.get("action", "read"))
            if updated is None:
                return P("Notification not found.", cls="text-muted")
            row = await SystemService.get_notification(request, ctx, notification_id, status=status_filter, kind=kind_filter)
            if row is None:
                return P("Notification not found.", cls="text-muted")
        else:
            row = STORE.set_system_notification_status(
                notification_id,
                status=data.get("action", "read"),
                actor_name=ctx.profile.user_name,
            )
            if row is None or row["path"] != "global" and not row["path"].startswith(ctx.current_scope_path):
                return P("Notification not found.", cls="text-muted")
        message = "Notification marked as read." if data.get("action", "read") == "read" else "Notification marked as unread."
        return simple_toast_response(
            content=(
                Div(H3("Notification updated", cls="h5 fw-semibold"), P(message, cls="mb-0")),
                await _notification_summary_cards(request, ctx, oob=True),
                await _notifications_workspace(request, ctx, status=status_filter, kind=kind_filter, oob=True),
                Div(
                    await _notification_drawer_content(ctx, row, status_filter=status_filter, kind_filter=kind_filter),
                    id="detail-drawer-body",
                    hx_swap_oob="innerHTML:#detail-drawer-body",
                ),
            ),
            message=message,
            variant="success",
        )

    @app.get("/system/public-intake")
    async def system_public_intake_page(request: Request, contact_status: str = "all", contact_search: str = "", prayer_status: str = "all", prayer_urgent: str = "all", prayer_search: str = ""):
        ctx = build_context(request)
        blocked = _system_guard(ctx, 7, "Public Intake", "Public website submissions open from national-level roles upward.")
        if blocked is not None:
            body = page_stack(page_intro("System", "Review public website submissions.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind), blocked)
        elif not await SystemService.live_enabled(request):
            body = page_stack(
                page_intro("System", "Review public website submissions.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind),
                _system_nav(ctx, "public_intake"),
                section_card(
                    "Public Intake",
                    "Backend connection required.",
                    empty_state("globe", "Backend connection required", "Public website submissions require backend access."),
                ),
            )
        else:
            contact_ws, prayer_ws = await asyncio.gather(
                _public_contact_workspace(request, ctx, status=contact_status, search=contact_search),
                _public_prayer_workspace(request, ctx, status=prayer_status, urgent=prayer_urgent, search=prayer_search),
            )
            body = page_stack(
                page_intro("System", "Review contact and prayer submissions from the public website without leaving the governance shell.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind),
                _system_nav(ctx, "public_intake"),
                section_card(
                    "Public Contact Submissions",
                    "Follow up on general enquiries sent from the public website.",
                    contact_ws,
                ),
                section_card(
                    "Public Prayer Submissions",
                    "Track and route prayer requests sent from the public website.",
                    prayer_ws,
                ),
            )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="system",
            title="Public Intake",
            subtitle="Public website submissions and review actions.",
            primary_action=None,
            content=body,
        )

    @app.get("/system/public-intake/contact/list")
    async def system_public_contact_list(request: Request, status: str = "all", search: str = ""):
        ctx = build_context(request)
        return await _public_contact_workspace(request, ctx, status=status, search=search)

    @app.get("/system/public-intake/prayer/list")
    async def system_public_prayer_list(request: Request, status: str = "all", urgent: str = "all", search: str = ""):
        ctx = build_context(request)
        return await _public_prayer_workspace(request, ctx, status=status, urgent=urgent, search=search)

    @app.get("/system/public-intake/contact/{submission_id}/drawer")
    async def system_public_contact_drawer(request: Request, submission_id: str, status_filter: str = "all", search: str = ""):
        ctx = build_context(request)
        rows = await SystemService.list_public_contacts(request, status=status_filter, search=search)
        row = next((item for item in rows if item["submission_id"] == submission_id), None)
        if row is None:
            return P("Public contact submission not found.", cls="text-muted")
        return await _public_contact_drawer_content(ctx, row, status_filter=status_filter, search=search)

    @app.get("/system/public-intake/prayer/{submission_id}/drawer")
    async def system_public_prayer_drawer(request: Request, submission_id: str, status_filter: str = "all", urgent_filter: str = "all", search: str = ""):
        ctx = build_context(request)
        rows = await SystemService.list_public_prayers(request, status=status_filter, urgent=urgent_filter, search=search)
        row = next((item for item in rows if item["submission_id"] == submission_id), None)
        if row is None:
            return P("Public prayer submission not found.", cls="text-muted")
        return await _public_prayer_drawer_content(ctx, row, status_filter=status_filter, urgent_filter=urgent_filter, search=search)

    @app.get("/system/public-intake/contact/{submission_id}/review")
    async def system_public_contact_review_form(request: Request, submission_id: str, status_filter: str = "all", search: str = ""):
        rows = await SystemService.list_public_contacts(request, status=status_filter, search=search)
        row = next((item for item in rows if item["submission_id"] == submission_id), None)
        if row is None:
            return P("Public contact submission not found.", cls="text-muted")
        ctx = build_context(request)
        return Form(
            *hidden_context_inputs(ctx),
            Input(type="hidden", name="status_filter", value=status_filter),
            Input(type="hidden", name="search", value=search),
            H3("Review contact submission", cls="h5 fw-semibold"),
            P(f"{row['name']} - {row['subject']}", cls="text-muted"),
            Select(
                Option("Reviewed", value="reviewed"),
                Option("Routed", value="routed"),
                Option("Closed", value="closed"),
                name="status",
                cls="form-select mb-3",
                required=True,
            ),
            Textarea(name="review_note", placeholder="Add a follow-up note", cls="form-control mb-3", rows="4"),
            Button("Save review", variant="primary", type="submit", cls="w-100"),
            hx_post=f"/system/public-intake/contact/{submission_id}/review",
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/system/public-intake/contact/{submission_id}/review")
    async def system_public_contact_review_submit(request: Request, submission_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        row = await SystemService.review_public_contact(request, submission_id, status=data.get("status", "reviewed"), review_note=data.get("review_note", ""))
        if row is None:
            return P("Public contact submission not found.", cls="text-muted")
        status_filter = data.get("status_filter", "all")
        search = data.get("search", "")
        return simple_toast_response(
            content=(
                Div(H3("Contact submission updated", cls="h5 fw-semibold"), P(f"{row['name']} was marked as {row['status']}.", cls="mb-0")),
                await _public_contact_workspace(request, ctx, status=status_filter, search=search, oob=True),
                Div(
                    await _public_contact_drawer_content(ctx, row, status_filter=status_filter, search=search),
                    id="detail-drawer-body",
                    hx_swap_oob="innerHTML:#detail-drawer-body",
                ),
            ),
            message="Public contact submission updated.",
            variant="success",
        )

    @app.get("/system/public-intake/prayer/{submission_id}/review")
    async def system_public_prayer_review_form(request: Request, submission_id: str, status_filter: str = "all", urgent_filter: str = "all", search: str = ""):
        rows = await SystemService.list_public_prayers(request, status=status_filter, urgent=urgent_filter, search=search)
        row = next((item for item in rows if item["submission_id"] == submission_id), None)
        if row is None:
            return P("Public prayer submission not found.", cls="text-muted")
        ctx = build_context(request)
        return Form(
            *hidden_context_inputs(ctx),
            Input(type="hidden", name="status_filter", value=status_filter),
            Input(type="hidden", name="urgent_filter", value=urgent_filter),
            Input(type="hidden", name="search", value=search),
            H3("Review prayer submission", cls="h5 fw-semibold"),
            P(row["name"], cls="text-muted"),
            Select(
                Option("Reviewed", value="reviewed"),
                Option("Routed", value="routed"),
                Option("Closed", value="closed"),
                name="status",
                cls="form-select mb-3",
                required=True,
            ),
            Textarea(name="review_note", placeholder="Add a prayer follow-up note", cls="form-control mb-3", rows="4"),
            Button("Save review", variant="primary", type="submit", cls="w-100"),
            hx_post=f"/system/public-intake/prayer/{submission_id}/review",
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/system/public-intake/prayer/{submission_id}/review")
    async def system_public_prayer_review_submit(request: Request, submission_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        row = await SystemService.review_public_prayer(request, submission_id, status=data.get("status", "reviewed"), review_note=data.get("review_note", ""))
        if row is None:
            return P("Public prayer submission not found.", cls="text-muted")
        status_filter = data.get("status_filter", "all")
        urgent_filter = data.get("urgent_filter", "all")
        search = data.get("search", "")
        return simple_toast_response(
            content=(
                Div(H3("Prayer submission updated", cls="h5 fw-semibold"), P(f"{row['name']} was marked as {row['status']}.", cls="mb-0")),
                await _public_prayer_workspace(request, ctx, status=status_filter, urgent=urgent_filter, search=search, oob=True),
                Div(
                    await _public_prayer_drawer_content(ctx, row, status_filter=status_filter, urgent_filter=urgent_filter, search=search),
                    id="detail-drawer-body",
                    hx_swap_oob="innerHTML:#detail-drawer-body",
                ),
            ),
            message="Public prayer submission updated.",
            variant="success",
        )

    @app.get("/system/sync")
    async def system_sync_page(request: Request):
        ctx = build_context(request)
        blocked = _system_guard(ctx, 7, "Sync Governance", "Sync governance opens from national-level roles upward.")
        if blocked is not None:
            body = page_stack(page_intro("System", "Review sync conflicts and recent offline activity.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind), blocked)
        else:
            body = page_stack(
                page_intro("System", "Review duplicate sync records and recent offline-to-server movement without leaving the admin shell.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind),
                _system_nav(ctx, "sync"),
                section_card(
                    "Sync Governance",
                    "Resolve duplicate sync records and review recent sync activity.",
                    Div(
                        await _sync_summary_cards(request),
                        await _sync_workspace(request, ctx),
                        cls="d-grid gap-3",
                    ),
                ),
            )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="system",
            title="Sync Governance",
            subtitle="Conflict review and offline sync oversight.",
            primary_action=None,
            content=body,
        )

    @app.get("/system/sync/list")
    async def system_sync_list(request: Request):
        ctx = build_context(request)
        return await _sync_workspace(request, ctx)

    @app.get("/system/sync/conflicts/{conflict_id}/drawer")
    async def system_sync_conflict_drawer(request: Request, conflict_id: str):
        ctx = build_context(request)
        row = await SystemService.get_sync_conflict(request, conflict_id)
        if row is None:
            return P("Sync conflict not found.", cls="text-muted")
        return await _sync_conflict_drawer_content(ctx, row)

    @app.get("/system/sync/conflicts/{conflict_id}/resolve")
    async def system_sync_conflict_resolve_confirm(request: Request, conflict_id: str, resolution: str = "keep_server"):
        ctx = build_context(request)
        row = await SystemService.get_sync_conflict(request, conflict_id)
        if row is None:
            return P("Sync conflict not found.", cls="text-muted")
        labels = {
            "keep_server": "Keep server copy",
            "keep_client": "Keep client copy",
            "merge": "Merge records",
        }
        if resolution == "merge" and not row["merge_allowed"]:
            return P("Merge is not supported for this conflict.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            H3(labels.get(resolution, "Resolve conflict"), cls="h5 fw-semibold"),
            P(row["title"], cls="text-muted"),
            P(
                "Apply the selected sync resolution.",
                cls="small text-muted mb-3",
            ),
            Input(type="hidden", name="resolution", value=resolution),
            Button(labels.get(resolution, "Resolve conflict"), variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/system/sync/conflicts/{conflict_id}/resolve"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/system/sync/conflicts/{conflict_id}/resolve")
    async def system_sync_conflict_resolve_submit(request: Request, conflict_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        resolution = data.get("resolution", "keep_server")
        result = await SystemService.resolve_sync_conflict(request, conflict_id, resolution=resolution)
        if result is None:
            return P("Live sync conflict resolution requires backend mode.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(
                    H3("Sync conflict resolved", cls="h5 fw-semibold"),
                    P(str(result.get("message") or "The sync conflict was resolved successfully."), cls="mb-0"),
                ),
                await _sync_summary_cards(request, oob=True),
                await _sync_workspace(request, ctx, oob=True),
                Div(
                    P("This conflict has been removed if the resolution completed successfully.", cls="mb-0"),
                    id="detail-drawer-body",
                    hx_swap_oob="innerHTML:#detail-drawer-body",
                ),
            ),
            message="Sync conflict resolved.",
            variant="success",
        )

    @app.get("/system/app-versions")
    async def system_app_versions_page(request: Request, platform: str = "", status: str = "all"):
        ctx = build_context(request)
        blocked = _system_guard(ctx, 7, "App Version Management", "App version management opens from national-level roles upward.")
        if blocked is not None:
            body = page_stack(page_intro("System", "Manage app release records.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind), blocked)
        else:
            rows = await SystemService.list_app_versions(request, platform=platform, status=status)
            body = page_stack(
                page_intro("System", "Track release versions, draft builds, and force-update settings without leaving the admin shell.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind),
                _system_nav(ctx, "versions"),
                section_card(
                    "App Version Management",
                    f"{len(rows)} version record(s) are available.",
                    Form(
                        *hidden_context_inputs(ctx),
                        Select(
                            Option("All platforms", value=""),
                            Option("Android", value="Android", selected=platform == "Android"),
                            Option("iOS", value="iOS", selected=platform == "iOS"),
                            name="platform",
                            cls="form-select",
                        ),
                        Select(
                            Option("All status", value="all"),
                            Option("Active", value="active", selected=status == "active"),
                            Option("Draft", value="draft", selected=status == "draft"),
                            name="status",
                            cls="form-select",
                        ),
                        action=ctx.url_for("/system/app-versions"),
                        method="get",
                        cls="admin-filter-grid mb-3",
                    ),
                    await _app_versions_table(request, ctx, platform=platform, status=status),
                ),
            )
        primary = None
        if _system_allowed(ctx, 7):
            primary = primary_button(
                "Add Version",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/system/app-versions/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="system",
            title="App Versions",
            subtitle="Release management and rollout records.",
            primary_action=primary,
            content=body,
        )

    @app.get("/system/app-versions/new")
    async def new_app_version_form(request: Request):
        ctx = build_context(request)
        if not _system_allowed(ctx, 7):
            return P("This form is not available for the current level.", cls="text-muted")
        live_mode = await SystemService.live_enabled(request)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Add app version", cls="h5 fw-semibold"),
            P(
                "Keep release records simple and easy to review on mobile."
                if not live_mode
                else "This backend-backed form stores the core release fields the server already supports.",
                cls="text-muted",
            ),
            Div(
                Input(type="text", name="app_name", value="DCLM Admin", cls="form-control", required=True),
                Select(
                    Option("Android", value="Android"),
                    Option("iOS", value="iOS"),
                    name="platform",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Input(type="text", name="version_number", placeholder="Version number", cls="form-control", required=True),
                Input(type="text", name="min_os_version", placeholder="Minimum OS version", cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Input(type="date", name="release_date", value=TODAY.isoformat(), cls="form-control", required=True),
                Select(
                    Option("Draft", value="draft"),
                    Option("Active", value="active"),
                    name="status",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            *(
                [
                    Select(
                        Option("No", value="No"),
                        Option("Yes", value="Yes"),
                        name="force_update",
                        cls="form-select mb-3",
                        required=True,
                    )
                ]
                if not live_mode
                else []
            ),
            Textarea(name="notes", placeholder="Release note", cls="form-control mb-3", rows="4"),
            Button("Save version", variant="success", size="md", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/system/app-versions/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/system/app-versions/create")
    async def create_app_version(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        if not _system_allowed(ctx, 7):
            return P("This action is not available for the current level.", cls="text-muted")
        row = await SystemService.create_app_version(request, data) if await SystemService.live_enabled(request) else STORE.add_app_version(data, actor_name=ctx.profile.user_name)
        return simple_toast_response(
            content=Div(H3("Version saved", cls="h5 fw-semibold"), P(f"{row['platform']} {row['version_number']} is now in the release list.", cls="mb-0")),
            message="App version saved.",
            variant="success",
        )

    @app.get("/system/app-versions/{version_id}/drawer")
    async def system_app_version_drawer(request: Request, version_id: str, platform_filter: str = "", status_filter: str = "all"):
        ctx = build_context(request)
        row = await SystemService.get_app_version(request, version_id)
        if row is None:
            return P("App version not found.", cls="text-muted")
        return await _app_version_drawer_content(ctx, row, platform_filter=platform_filter, status_filter=status_filter)

    @app.get("/system/app-versions/{version_id}/activate")
    async def system_activate_app_version_confirm(request: Request, version_id: str, platform_filter: str = "", status_filter: str = "all"):
        ctx = build_context(request)
        row = await SystemService.get_app_version(request, version_id)
        if row is None:
            return P("App version not found.", cls="text-muted")
        live_mode = await SystemService.live_enabled(request)
        return Form(
            *hidden_context_inputs(ctx),
            Input(type="hidden", name="platform_filter", value=platform_filter),
            Input(type="hidden", name="status_filter", value=status_filter),
            H3("Make current version", cls="h5 fw-semibold"),
            P(f"{row['platform']} {row['version_number']}", cls="text-muted"),
            P(
                "This version becomes the active release record for its platform."
                if not live_mode
                else "This will mark the selected version active and retire other active siblings for the same app and platform.",
                cls="small text-muted mb-3",
            ),
            *(
                [
                    Select(
                        Option("Keep current force update setting", value=""),
                        Option("Yes", value="Yes"),
                        Option("No", value="No"),
                        name="force_update",
                        cls="form-select mb-3",
                    )
                ]
                if not live_mode
                else []
            ),
            Button("Make current version", variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/system/app-versions/{version_id}/activate"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/system/app-versions/{version_id}/activate")
    async def system_activate_app_version(request: Request, version_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        row = (
            await SystemService.activate_app_version(request, version_id)
            if await SystemService.live_enabled(request)
            else STORE.activate_app_version(
                version_id,
                actor_name=ctx.profile.user_name,
                force_update=data.get("force_update", ""),
            )
        )
        if row is None:
            return P("App version not found.", cls="text-muted")
        platform_filter = data.get("platform_filter", "")
        status_filter = data.get("status_filter", "all")
        return simple_toast_response(
            content=(
                Div(H3("Current version updated", cls="h5 fw-semibold"), P(f"{row['platform']} {row['version_number']} is now the active release.", cls="mb-0")),
                await _app_versions_table(request, ctx, platform=platform_filter, status=status_filter, oob=True),
                Div(
                    await _app_version_drawer_content(ctx, row, platform_filter=platform_filter, status_filter=status_filter),
                    id="detail-drawer-body",
                    hx_swap_oob="innerHTML:#detail-drawer-body",
                ),
            ),
            message="Current app version updated.",
            variant="success",
        )

    @app.get("/system/health")
    async def system_health_page(request: Request):
        ctx = build_context(request)
        blocked = _system_guard(ctx, 7, "System Health", "Health monitoring opens from national-level roles upward.")
        body = page_stack(
            page_intro("System", "Review the current health picture without turning this into a dense operations console.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind),
            _system_nav(ctx, "health"),
            blocked if blocked is not None else await _health_view(request),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="system",
            title="System Health",
            subtitle="Operational health and service status.",
            primary_action=None,
            content=body,
        )

    @app.get("/system/audit-logs")
    async def system_audit_logs_page(request: Request, search: str = "", status: str = "all"):
        ctx = build_context(request)
        blocked = _system_guard(ctx, 7, "Audit Logs", "Audit logs open from national-level roles upward.")
        body = page_stack(
            page_intro("System", "Inspect governance actions and important system events in plain language.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind),
            _system_nav(ctx, "audit"),
            blocked
            if blocked is not None
            else _system_loading_section(
                "system-audit-content",
                hx_get=ctx.url_for("/system/audit-logs/content", search=search, status=status),
                message="Loading audit logs.",
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="system",
            title="Audit Logs",
            subtitle="Governance event history.",
            primary_action=None,
            content=body,
        )

    @app.get("/system/audit-logs/content")
    async def system_audit_logs_content(request: Request, search: str = "", status: str = "all"):
        ctx = build_context(request)
        if not _system_allowed(ctx, 7):
            return Div(
                section_card(
                    "Audit Logs",
                    "Audit logs open from national-level roles upward.",
                    empty_state("shield-lock", "Audit Logs", "Audit logs open from national-level roles upward."),
                ),
                id="system-audit-content",
            )
        return Div(
            section_card(
                "Audit Logs",
                "Search by actor, action, target, or scope to narrow the log list quickly.",
                await _audit_workspace(request, ctx, search=search, status=status),
            ),
            id="system-audit-content",
        )

    @app.get("/system/audit-logs/list")
    async def system_audit_logs_list(request: Request, search: str = "", status: str = "all"):
        ctx = build_context(request)
        return await _audit_workspace(request, ctx, search=search, status=status)

    @app.get("/system/rbac")
    async def system_rbac_page(request: Request, family: str = "all", search: str = ""):
        ctx = build_context(request)
        blocked = _system_guard(ctx, 9, "RBAC Studio", "RBAC Studio is restricted to the highest admin level.")
        body = page_stack(
            page_intro("System", "Read roles and permission families using the same backend vocabulary already normalized in the API.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind),
            _system_nav(ctx, "rbac"),
            blocked
            if blocked is not None
            else section_card(
                "RBAC Studio",
                "Roles and permission families.",
                await _rbac_view(request, ctx, family=family, search=search),
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="system",
            title="RBAC Studio",
            subtitle="Roles, permission families, and governance visibility.",
            primary_action=None,
            content=body,
        )

    @app.get("/system/rbac/roles/{role_id}/drawer")
    async def system_rbac_role_drawer(request: Request, role_id: str, family: str = "all", search: str = ""):
        ctx = build_context(request)
        if not _system_allowed(ctx, 9):
            return P("This detail view is not available for the current level.", cls="text-muted")
        role = await SystemService.get_rbac_role(request, role_id) if await SystemService.live_enabled(request) else STORE.get_rbac_role(role_id)
        if role is None:
            return P("Role not found.", cls="text-muted")
        return await _rbac_role_drawer_content(request, ctx, role, family=family, search=search)

    @app.get("/system/rbac/permissions/{permission_id}/drawer")
    async def system_rbac_permission_drawer(request: Request, permission_id: str):
        ctx = build_context(request)
        if not _system_allowed(ctx, 9):
            return P("This detail view is not available for the current level.", cls="text-muted")
        permission = await SystemService.get_rbac_permission(request, permission_id) if await SystemService.live_enabled(request) else STORE.get_rbac_permission(permission_id)
        if permission is None:
            return P("Permission not found.", cls="text-muted")
        return await _rbac_permission_drawer_content(permission)

    @app.get("/system/rbac/roles/{role_id}/edit")
    async def system_rbac_role_edit(request: Request, role_id: str, family: str = "all", search: str = ""):
        ctx = build_context(request)
        if not _system_allowed(ctx, 9):
            return P("This form is not available for the current level.", cls="text-muted")
        role = await SystemService.get_rbac_role(request, role_id) if await SystemService.live_enabled(request) else STORE.get_rbac_role(role_id)
        if role is None:
            return P("Role not found.", cls="text-muted")
        return await _rbac_role_form(request, ctx, role, family=family, search=search)

    @app.post("/system/rbac/roles/{role_id}/update")
    async def system_rbac_role_update(request: Request, role_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        if not _system_allowed(ctx, 9):
            return P("This action is not available for the current level.", cls="text-muted")
        if await SystemService.live_enabled(request):
            permission_ids = sorted(
                int(key.replace("perm_", ""))
                for key in data
                if key.startswith("perm_") and key.replace("perm_", "").isdigit()
            )
            role = await SystemService.update_rbac_role(
                request,
                role_id,
                description=data.get("description", ""),
                permission_ids=permission_ids,
            )
        else:
            role = STORE.update_rbac_role(role_id, data, actor_name=ctx.profile.user_name)
        if role is None:
            return P("Role not found.", cls="text-muted")
        family = data.get("family", "all")
        search = data.get("search", "")
        return simple_toast_response(
            content=(
                Div(H3("RBAC role updated", cls="h5 fw-semibold"), P(f"{role['name']} was updated in RBAC Studio.", cls="mb-0")),
                await _rbac_view(request, ctx, family=family, search=search, oob=True),
                Div(
                    await _rbac_role_drawer_content(request, ctx, role, family=family, search=search),
                    id="detail-drawer-body",
                    hx_swap_oob="innerHTML:#detail-drawer-body",
                ),
            ),
            message="RBAC role updated.",
            variant="success",
        )

    @app.get("/system/utilities")
    async def system_utilities_page(request: Request):
        ctx = build_context(request)
        blocked = _system_guard(ctx, 9, "Utilities", "Utilities are restricted to the highest admin level.")
        body = page_stack(
            page_intro("System", "Keep administrative utilities explicit and separated from day-to-day operations.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind),
            _system_nav(ctx, "utilities"),
            blocked
            if blocked is not None
            else section_card(
                "Seed & Utilities",
                "These actions stay aligned to the backend `system:seed` and related governance flows.",
                Div(
                    section_card(
                        "Program data seed",
                        "Refresh core program references used across the admin."
                        if not await SystemService.live_enabled(request)
                        else "This is the live utility already backed by the backend seed endpoint.",
                        Button(
                            "Run seed",
                            variant="outline-primary",
                            size="md",
                            type="button",
                            hx_post=ctx.url_for("/system/utilities/run", action="seed_programs"),
                            hx_target="#system-utility-feedback",
                            hx_swap="innerHTML",
                        ),
                    ),
                    section_card(
                        "Notification refresh",
                        "Refresh notification records."
                        if not await SystemService.live_enabled(request)
                        else "Notification administration is not available yet.",
                        Button(
                            "Refresh notifications",
                            variant="outline-primary",
                            size="md",
                            type="button",
                            hx_post=ctx.url_for("/system/utilities/run", action="refresh_notifications"),
                            hx_target="#system-utility-feedback",
                            hx_swap="innerHTML",
                            disabled=await SystemService.live_enabled(request),
                        ),
                    ),
                    section_card(
                        "Report rebuild",
                        "Queue a fresh report rebuild."
                        if not await SystemService.live_enabled(request)
                        else "Use Reports to refresh report data.",
                        Button(
                            "Rebuild reports",
                            variant="outline-primary",
                            size="md",
                            type="button",
                            hx_post=ctx.url_for("/system/utilities/run", action="rebuild_reports"),
                            hx_target="#system-utility-feedback",
                            hx_swap="innerHTML",
                            disabled=await SystemService.live_enabled(request),
                        ),
                    ),
                    cls="d-grid gap-3",
                ),
                Div(id="system-utility-feedback"),
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="system",
            title="Utilities",
            subtitle="Restricted system tools and seed actions.",
            primary_action=None,
            content=body,
        )

    @app.post("/system/utilities/run")
    async def run_system_utility(request: Request, action: str = ""):
        ctx = build_context(request)
        if not _system_allowed(ctx, 9):
            return P("This utility is not available for the current level.", cls="text-muted")
        result = (
            await SystemService.run_utility(request, action)
            if await SystemService.live_enabled(request)
            else STORE.run_system_utility(action, actor_name=ctx.profile.user_name)
        )
        return simple_toast_response(
            content=Div(P(result["message"], cls="mb-0"), id="system-utility-feedback"),
            message=result["message"],
            variant="success" if result.get("ok", True) else "warning",
        )
