from __future__ import annotations

from typing import Any

from fasthtml.common import A, Div, H2, H3, H4, Label, P, Span

from faststrap import Badge, BsTable, BsTBody, BsTCell, BsTHead, BsTRow, Button, Card, EmptyState, Fx, Icon


def format_naira(amount: int) -> str:
    return f"N{amount:,.0f}"


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


def priority_badge(label: str) -> Any:
    return status_badge(label)


def section_card(title: str, subtitle: str | None, *children: Any, action: Any | None = None, cls: str = "") -> Any:
    header = Div(
        Div(
            H3(title, cls="h5 fw-semibold mb-1 text-dark section-card__title"),
            P(subtitle, cls="text-muted mb-0 small section-card__subtitle") if subtitle else "",
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


def stat_card(title: str, value: str, note: str, icon: str, tone: str = "success") -> Any:
    return Card(
        Div(
            Div(Icon(icon, cls=f"fs-4 text-{tone}"), cls=f"metric-icon bg-{tone}-subtle"),
            Div(
                P(title, cls="metric-label"),
                H3(value, cls="metric-value"),
                P(note, cls="metric-note mb-0"),
            ),
            cls="metric-card__inner d-flex gap-3 align-items-start",
        ),
        cls=f"metric-card {Fx.base} {Fx.hover_lift} {Fx.shadow_soft}",
    )


def page_intro(title: str, subtitle: str, *, scope_label: str, scope_kind: str, scope_id: str = "") -> Any:
    return Div(
        Div(
            Badge(f"{scope_kind.title()} View", variant="light", cls="scope-chip text-primary-emphasis"),
            Span(scope_label, cls="fw-semibold text-dark"),
            Badge(scope_id, variant="light", cls="border text-secondary-emphasis") if scope_id else "",
            cls="page-intro__meta d-flex flex-wrap align-items-center gap-2 mb-3",
        ),
        H2(title, cls="display-6 fw-semibold text-dark mb-2 page-intro__title"),
        P(subtitle, cls="text-muted fs-6 mb-0 page-intro__subtitle"),
        cls="page-intro",
    )


def quick_actions(actions: list[dict[str, Any]]) -> Any:
    return Div(
        *[
            A(
                Div(
                    Icon(action["icon"], cls="fs-4 text-primary"),
                    Div(
                        Span(action["label"], cls="fw-semibold text-dark d-block"),
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
                    P(item["message"], cls="fw-semibold mb-1 text-dark"),
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
            Span(item["location"], cls="small fw-semibold text-dark"),
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

