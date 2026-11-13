from __future__ import annotations

from decimal import Decimal
from typing import Any

from fasthtml.common import A, Div, H1, H2, H3, H4, Label, P, Span

from faststrap import Badge, BsTable, BsTBody, BsTCell, BsTHead, BsTRow, Button, Card, EmptyState, Fx, Icon

from ..backend import format_scope_display_id


def format_naira(amount: int | float | Decimal) -> str:
    value = Decimal(str(amount or 0))
    return f"N{value:,.2f}" if value != value.to_integral_value() else f"N{value:,.0f}"


def status_badge(label: str) -> Any:
    palette = {
        "approved": "success",
        "pending_verification": "warning",
        "pending": "warning",
        "rejected": "danger",
        "escalated": "info",
        "suspended": "secondary",
        "active": "success",
        "inactive": "secondary",
        "follow_up_pending": "warning",
        "contacted": "info",
        "integrated": "success",
        "present": "success",
        "late": "warning",
        "absent": "danger",
        "excused": "info",
        "scheduled": "info",
        "completed": "success",
        "cancelled": "danger",
        "draft": "secondary",
        "published": "success",
        "archived": "secondary",
        "convert": "info",
        "newcomer": "primary",
        "high": "danger",
        "medium": "warning",
        "low": "info",
        "unread": "warning",
        "read": "secondary",
        "transferred": "info",
        "deceased": "secondary",
        "shared": "success",
        "new": "warning",
        "ongoing": "warning",
        "answered": "success",
        "scope_only": "secondary",
        "national_share": "success",
        "private_review": "warning",
        "photo": "info",
        "video": "primary",
        "revoked": "secondary",
    }
    key = label.lower().replace(" ", "_")
    text = label.replace("_", " ").title()
    return Badge(text, variant=palette.get(key, "secondary"), cls="text-uppercase fw-semibold px-3 py-2")


def active_scope_breadcrumb(path: str) -> Any:
    """Show one scope ID and open the hierarchy selector from the same control."""
    parts = [part for part in str(path or "").split(".") if part]
    scope_id = format_scope_display_id(str(path or "")) or (parts[-1] if parts else "Current scope")
    return Div(
        Button(
            Span("Scope:", cls="text-secondary"),
            Span(scope_id, cls="fw-semibold"),
            Icon("chevron-down", cls="small text-secondary"),
            type="button",
            data_bs_toggle="offcanvas",
            data_bs_target="#scope-drawer",
            aria_label=f"Change scope. Current scope: {scope_id}",
            cls="btn btn-link active-scope-control px-0 py-1 text-decoration-none d-inline-flex align-items-center gap-2",
        ),
        cls="active-scope-breadcrumb mb-3",
    )


def priority_badge(label: str) -> Any:
    return status_badge(label)


def section_card(title: str, subtitle: str | None, *children: Any, action: Any | None = None, cls: str = "") -> Any:
    header = Div(
        Div(
            H3(title, cls="h6 fw-bold mb-1 text-body-emphasis section-card__title"),
            P(subtitle, cls="text-secondary mb-0 small section-card__subtitle") if subtitle else "",
            cls="section-card__heading",
        ),
        action or "",
        cls="section-card__header d-flex flex-column flex-lg-row gap-3 align-items-lg-center justify-content-between mb-3",
    )
    return Card(
        header,
        Div(*children, cls="section-card__body"),
        cls=f"section-card {Fx.base} {cls}".strip(),
    )


def filter_field(label: str, *args: Any, field_id: str | None = None, cls: str = "") -> Any:
    if len(args) == 2:
        field_id = str(args[0])
        control = args[1]
    elif len(args) == 1:
        control = args[0]
    else:
        raise TypeError("filter_field expects a control, or a field_id and control")
    if field_id:
        try:
            control.attrs["id"] = field_id
        except (AttributeError, TypeError):
            pass
    return Div(
        Label(label, fr=field_id, cls="visually-hidden"),
        control,
        cls=f"filter-field {cls}".strip(),
    )


def page_stack(*children: Any, cls: str = "", gap: str = "gap-4", **attrs: Any) -> Any:
    return Div(*children, cls=f"d-grid {gap} {cls}".strip(), **attrs)


def stat_card(title: str, value: str, note: str, icon: str, tone: str = "primary") -> Any:
    tone_colors = {
        "primary": ("#1d4ed8", "rgba(29, 78, 216, 0.1)"),
        "success": ("#059669", "rgba(5, 150, 105, 0.1)"),
        "warning": ("#d97706", "rgba(217, 119, 6, 0.1)"),
        "danger": ("#dc2626", "rgba(220, 38, 38, 0.1)"),
        "info": ("#0284c7", "rgba(2, 132, 199, 0.1)"),
    }
    accent_color, accent_bg = tone_colors.get(tone, tone_colors["primary"])
    return Card(
        Div(
            Div(
                P(title, cls="metric-label text-secondary small fw-semibold text-uppercase tracking-wider mb-1", style="font-size:0.75rem; letter-spacing:0.04em;"),
                H3(value, cls="metric-value h4 fw-bold text-body-emphasis mb-1 tracking-tight"),
                P(note, cls="metric-note text-secondary small mb-0"),
                cls="d-flex flex-column",
            ),
            Div(
                Icon(icon, cls=f"fs-5 text-{tone}"),
                cls="metric-icon-wrap rounded-3 d-flex align-items-center justify-content-center flex-shrink-0",
                style=f"width: 2.4rem; height: 2.4rem; background: {accent_bg};",
            ),
            cls="metric-card__inner d-flex justify-content-between align-items-start gap-2",
        ),
        cls=f"metric-card {Fx.base} {Fx.hover_lift} border-0 shadow-sm",
        style=f"border-top: 3px solid {accent_color} !important;",
    )


def page_intro(
    title: str,
    subtitle: str,
    *,
    scope_label: str = "",
    scope_kind: str = "",
    scope_id: str = "",
    show_scope_label: bool = False,
) -> Any:
    meta = []
    if show_scope_label and scope_label:
        meta.append(Span(scope_label, cls="badge bg-primary-subtle text-primary-emphasis border border-primary-subtle px-2 py-1 small"))
    return Div(
        H1(title, cls="h5 fw-bold text-body-emphasis mb-1 page-intro__title"),
        P(subtitle, cls="text-secondary small mb-0 page-intro__subtitle") if subtitle else "",
        Div(*meta, cls="d-flex align-items-center gap-2 mt-2") if meta else "",
        cls="page-intro mb-3",
    )


def quick_actions(actions: list[dict[str, Any]]) -> Any:
    return Div(
        *[
            A(
                Div(
                    Icon(action["icon"], cls="fs-4 text-primary"),
                    Div(
                        Span(action["label"], cls="fw-semibold text-body-emphasis d-block"),
                        Span(action["hint"], cls="small text-muted"),
                    ),
                    cls="quick-action__inner d-flex gap-3 align-items-start",
                ),
                href=action.get("href", "#"),
                cls=f"quick-action {Fx.base} {Fx.hover_lift}",
                **action.get("attrs", {}),
            )
            for action in actions
        ],
        cls="quick-actions-grid",
    )


def activity_feed(items: list[dict[str, str]]) -> Any:
    if not items:
        return empty_state("clock-history", "No recent activity", "No new submissions are available.")
    return Div(
        *[
            Div(
                Span(cls=f"feed-dot bg-{item['tone']}"),
                Div( 
                    P(item["message"], cls="fw-semibold mb-1 text-body-emphasis"),
                    P(item["meta"], cls="small text-muted mb-0"),
                ),
                cls="feed-item",
            )
            for item in items
        ],
        cls="activity-feed",
    )


def approval_card(item: dict[str, Any], *, detail_url: str, confirm_url: str) -> Any:
    review_button = Button(
        "Review",
        variant="outline-primary",
        size="md",
        data_bs_toggle="offcanvas",
        data_bs_target="#detail-drawer",
        hx_get=detail_url,
        hx_target="#detail-drawer-body",
        hx_swap="innerHTML",
        hx_disabled_elt="this",
        cls="w-100 w-sm-auto",
    )
    actions = Div(
        Button(
            "Approve",
            variant="success",
            size="md",
            data_bs_toggle="modal",
            data_bs_target="#confirm-modal",
            hx_get=f"{confirm_url}&action=approve",
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
            hx_disabled_elt="this",
            cls="w-100 w-sm-auto",
        ),
        Button(
            "Reject",
            variant="outline-danger",
            size="md",
            data_bs_toggle="modal",
            data_bs_target="#confirm-modal",
            hx_get=f"{confirm_url}&action=reject",
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
            hx_disabled_elt="this",
            cls="w-100 w-sm-auto",
        ),
        Button(
            "Escalate",
            variant="outline-info",
            size="md",
            data_bs_toggle="modal",
            data_bs_target="#confirm-modal",
            hx_get=f"{confirm_url}&action=escalate",
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
            hx_disabled_elt="this",
            cls="w-100 w-sm-auto",
        ),
        cls="d-grid d-sm-flex gap-2",
    )
    return Card(
        Div(
            Div(
                H4(item["subject"], cls="h6 fw-semibold mb-1"),
                P(item["title"], cls="text-muted mb-0"),
            ),
            priority_badge(item["priority"]),
            cls="approval-card__header d-flex align-items-start justify-content-between gap-3",
        ),
        Div(
            Span(item["location"], cls="small fw-semibold text-body-emphasis"),
            Span("|", cls="text-muted"),
            Span(item["submitted_at"], cls="small text-muted"),
            cls="d-flex flex-wrap gap-2 align-items-center mt-2",
        ),
        P(item["summary"], cls="approval-card__summary text-muted mt-3 mb-3"),
        Div(
            Badge(item["current_stage"], variant="light", cls="text-primary-emphasis border px-3 py-2"),
            review_button,
            cls="approval-card__stage d-flex flex-column flex-lg-row gap-2 justify-content-between align-items-lg-center mb-3",
        ),
        actions,
        cls=f"approval-card {Fx.base} {Fx.hover_lift}",
    )


def empty_state(icon: str, title: str, body: str, action: Any | None = None) -> Any:
    return EmptyState(
        icon=Icon(icon, cls="fs-1 text-primary"),
        title=title,
        description=body,
        action=action,
        centered=True,
        cls="py-5",
    )


def responsive_table(
    columns: list[str],
    rows: list[list[Any]],
    mobile_cards: list[Any],
    *,
    results_id: str,
    oob: str | None = None,
) -> Any:
    desktop = Div(
        BsTable(
            BsTHead(BsTRow(*[BsTCell(column, header=True, scope="col", cls="table-head-cell") for column in columns])),
            BsTBody(*[BsTRow(*[BsTCell(cell) for cell in cells]) for cells in rows]),
            striped=True,
            hover=True,
            responsive=True,
            cls="admin-table align-middle mb-0",
        ),
        cls="table-responsive d-none d-md-block admin-responsive-table-desktop",
    )
    mobile = Div(*mobile_cards, cls="d-grid gap-3 d-md-none admin-responsive-table-mobile")
    attrs = {"id": results_id, "role": "region", "aria_label": "Results"}
    if oob:
        attrs["hx_swap_oob"] = oob
    return Div(desktop, mobile, **attrs)


def mobile_entity_card(title: str, subtitle: str, meta: list[Any], actions: list[Any]) -> Any:
    return Card(
        Div(
            H4(title, cls="h6 fw-semibold mb-1"),
            P(subtitle, cls="text-muted mb-3"),
            Div(*meta, cls="d-flex flex-wrap gap-2 mb-3"),
            Div(*actions, cls="d-grid gap-2"),
            cls="p-2",
        ),
        cls=f"mobile-entity-card {Fx.base} {Fx.hover_lift} shadow-sm border-0",
    )

