from __future__ import annotations

from fasthtml.common import Div, Form, H3, H4, Input, P, Textarea
from starlette.requests import Request

from faststrap import Button, PlaceholderCard, Spinner, ToggleGroup

from ..auth_context import build_context
from ..backend import BackendClientError
from ..communication import PeopleService, WorkflowService
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, primary_button, shell_layout
from ..components.ui import approval_card, empty_state, page_intro, page_stack, section_card, status_badge
from ..mock_data import STORE


INBOX_FILTERS = [
    ("all", "All items"),
    ("worker_registration", "Workers"),
    ("user_approval", "User access"),
    ("removal_request", "Removal"),
    ("transfer_request", "Transfers"),
    ("status_change", "Status change"),
]


async def _inbox_list(request: Request, ctx, kind: str, *, oob: bool = False) -> Div:
    rows = await WorkflowService.list_inbox(request, ctx, kind=kind)
    cards = [
        approval_card(
            row,
            detail_url=ctx.url_for(f"/inbox/items/{row['item_id']}/drawer", kind=kind),
            confirm_url=ctx.url_for(f"/inbox/items/{row['item_id']}/confirm", kind=kind),
        )
        for row in rows
    ]
    content = cards or [
        empty_state(
            "check2-circle",
            "Nothing is waiting right now",
            "Your current inbox is clear for this filter.",
        )
    ]
    attrs = {"id": "inbox-results", "cls": "d-grid gap-3"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#inbox-results"
    return Div(*content, **attrs)


async def _linked_actions(ctx, item: dict, worker: dict | None, account: dict | None, linked_request: dict | None, kind: str) -> Div:
    actions = []
    if worker is not None:
        actions.append(
            Button(
                "Open worker record",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(f"/people/workers/{worker['worker_id']}/drawer"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
            )
        )
    if account is not None:
        actions.append(
            Button(
                "Open app account",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(f"/people/users/{account['account_id']}/drawer"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
            )
        )
    if linked_request is not None:
        actions.append(
            Button(
                "Open workflow request",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(f"/workflows/requests/{linked_request['request_id']}/drawer"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
            )
        )
    if not actions:
        actions.append(P("No linked record is attached.", cls="small text-muted mb-0"))
    return Div(*actions, cls="d-grid gap-2")


async def _inbox_loading_results(ctx, kind: str) -> Div:
    return Div(
        Div(
            Spinner(variant="primary", size="sm", label="Loading inbox"),
            P("Loading inbox items.", cls="text-muted mb-0"),
            cls="d-flex align-items-center gap-3",
        ),
        PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
        PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
        id="inbox-results",
        hx_get=ctx.url_for("/inbox/list", kind=kind),
        hx_trigger="load",
        hx_swap="outerHTML",
        cls="d-grid gap-3",
    )


def register_inbox_routes(app) -> None:
    @app.get("/inbox")
    async def inbox(request: Request, kind: str = "all"):
        ctx = build_context(request)
        results = await _inbox_loading_results(ctx, kind)
        active_index = next((index for index, row in enumerate(INBOX_FILTERS) if row[0] == kind), 0)
        filter_buttons = ToggleGroup(
            *[
                Button(
                    row_label,
                    variant="outline-primary",
                    size="md",
                    hx_get=ctx.url_for("/inbox/list", kind=row_key),
                    hx_target="#inbox-results",
                    hx_swap="outerHTML",
                    cls="inbox-filter-chip",
                )
                for row_key, row_label in INBOX_FILTERS
            ],
            active_index=active_index,
            active_cls="active",
            cls="filter-chip-row admin-toggle-group",
        )
        body = page_stack(
            page_intro(
                "Inbox",
                "Pending registrations, access approvals, and request reviews — all in one place.",
                scope_label=ctx.current_scope_label,
                scope_kind=ctx.current_scope_kind,
            ),
            section_card(
                "What needs your attention",
                "Filter by type to prioritise what needs action first.",
                filter_buttons,
                results,
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="inbox",
            title="Inbox",
            subtitle="Action-first review space for approvals and requests.",
            primary_action=primary_button("Review Workers", href=ctx.url_for("/inbox", kind="worker_registration")),
            content=body,
            show_shell_intro=False,
        )

    @app.get("/inbox/list")
    async def inbox_list(request: Request, kind: str = "all"):
        ctx = build_context(request)
        try:
            return await _inbox_list(request, ctx, kind)
        except BackendClientError as exc:
            return Div(empty_state("cloud-slash", "Live inbox is unavailable", str(exc)), id="inbox-results")

    @app.get("/inbox/items/{item_id}/drawer")
    async def inbox_item_drawer(request: Request, item_id: str, kind: str = "all"):
        ctx = build_context(request)
        try:
            resolved = await WorkflowService.resolve_inbox_item(request, ctx, item_id)
        except BackendClientError as exc:
            return empty_state("cloud-slash", "Inbox item unavailable", str(exc))
        if resolved is None:
            return empty_state("x-circle", "Item not found", "This inbox item is no longer available.")
        item = resolved["item"]
        worker = resolved["worker"]
        account = resolved["account"]
        linked_request = resolved["request"]
        linked_meta = []
        if worker is not None:
            linked_meta.extend(
                [
                    Div(P("Worker unit", cls="small text-muted mb-1"), P(worker["unit"], cls="fw-semibold mb-0")),
                    Div(P("Worker status", cls="small text-muted mb-1"), status_badge(worker["status"])),
                    Div(P("Worker approval", cls="small text-muted mb-1"), status_badge(worker["approval_status"])),
                ]
            )
        if account is not None:
            linked_meta.extend(
                [
                    Div(P("Account status", cls="small text-muted mb-1"), status_badge(account["status"])),
                    Div(P("Access approval", cls="small text-muted mb-1"), status_badge(account["approval_status"])),
                    Div(P("Assigned role", cls="small text-muted mb-1"), P(", ".join(account["roles"]), cls="fw-semibold mb-0")),
                ]
            )
        if linked_request is not None:
            linked_meta.extend(
                [
                    Div(P("Request type", cls="small text-muted mb-1"), P(linked_request["request_type"].replace("_", " ").title(), cls="fw-semibold mb-0")),
                    Div(P("Requested by", cls="small text-muted mb-1"), P(linked_request["requested_by"], cls="fw-semibold mb-0")),
                    Div(P("Workflow status", cls="small text-muted mb-1"), status_badge(linked_request["status"])),
                ]
            )
        return Div(
            H3(item["subject"], cls="h5 fw-semibold"),
            P(item["title"], cls="text-muted"),
            Div(
                Div(P("Current stage", cls="small text-muted mb-1"), P(item["current_stage"], cls="fw-semibold mb-0")),
                Div(P("Location", cls="small text-muted mb-1"), P(item["location"], cls="fw-semibold mb-0")),
                Div(P("Submitted", cls="small text-muted mb-1"), P(item["submitted_at"], cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            Div(
                P("Summary", cls="small text-muted mb-2"),
                P(item["summary"], cls="mb-0"),
                cls="drawer-note-box mb-3",
            ),
            Div(
                H4("Linked record", cls="h6 fw-semibold mb-2"),
                _linked_actions(ctx, item, worker, account, linked_request, kind),
                cls="drawer-note-box mb-3",
            ),
            Div(
                H4("More context", cls="h6 fw-semibold mb-2"),
                Div(*linked_meta, cls="drawer-meta-grid") if linked_meta else P("No extra context is attached to this inbox item.", cls="text-muted mb-0"),
                cls="drawer-note-box",
            ),
        )

    @app.get("/inbox/items/{item_id}/confirm")
    async def inbox_confirm(request: Request, item_id: str, action: str = "approve", kind: str = "all"):
        ctx = build_context(request)
        try:
            resolved = await WorkflowService.resolve_inbox_item(request, ctx, item_id)
            item = resolved["item"] if resolved else None
        except BackendClientError as exc:
            return P(str(exc), cls="text-muted")
        if item is None:
            return P("This item has already been cleared.", cls="text-muted")
        labels = {
            "approve": "Approve this item",
            "reject": "Reject this item",
            "escalate": "Escalate this item",
        }
        return Form(
            *hidden_context_inputs(ctx),
            Input(type="hidden", name="kind", value=kind),
            Input(type="hidden", name="action", value=action),
            H3(labels.get(action, "Confirm action"), cls="h5 fw-semibold"),
            P(f"{item['subject']} • {item['location']}", cls="text-muted"),
            Textarea(
                name="notes",
                placeholder="Add a short note for the record",
                cls="form-control mb-3",
                rows="4",
            ),
            Div(
                Button(
                    labels.get(action, "Continue"),
                    variant="success" if action == "approve" else "danger" if action == "reject" else "info",
                    type="submit",
                    cls="w-100",
                ),
                cls="d-grid",
            ),
            hx_post=ctx.url_for(f"/inbox/items/{item_id}/act"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/inbox/items/{item_id}/act")
    async def inbox_act(request: Request, item_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        action = data.get("action", "approve")
        kind = data.get("kind", "all")
        notes = data.get("notes", "")
        try:
            await WorkflowService.act_inbox_item(request, ctx, item_id, action, notes)
        except BackendClientError as exc:
            return P(str(exc), cls="text-muted")

        refreshed = await _inbox_list(request, ctx, kind, oob=True)
        message = {
            "approve": "Inbox item approved successfully.",
            "reject": "Inbox item rejected.",
            "escalate": "Inbox item escalated to the next level.",
        }[action]
        variant = "success" if action == "approve" else "danger" if action == "reject" else "warning"
        return simple_toast_response(
            content=(
                Div(H3("Action recorded", cls="h5 fw-semibold"), P(message, cls="mb-0")),
                refreshed,
            ),
            message=message,
            variant=variant,
        )
