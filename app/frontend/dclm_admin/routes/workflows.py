from __future__ import annotations

from fasthtml.common import A, Div, Form, H3, H4, Input, Option, P, Select, Textarea
from starlette.requests import Request
from starlette.responses import RedirectResponse

from faststrap import Button

from ..backend import BackendClientError
from ..auth_context import build_context
from ..communication import PeopleService, WorkflowService
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, primary_button, shell_layout
from ..components.ui import empty_state, filter_field, page_intro, page_stack, section_card, status_badge
from ..mock_data import STORE


REQUEST_TYPES = [
    ("all", "All requests"),
    ("transfer_request", "Transfers"),
    ("status_change", "Status changes"),
    ("removal_request", "Removal"),
]

REQUEST_STATUSES = [
    ("all", "All status"),
    ("pending", "Pending"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
    ("escalated", "Escalated"),
]

STATUS_CHANGE_OPTIONS = ["Active", "Inactive", "Suspended"]


async def _workflows_nav(ctx, active: str):
    links = [
        ("my-requests", "My Requests", "/workflows/my-requests"),
        ("review-queue", "Review Queue", "/workflows/review-queue"),
    ]
    return Div(
        *[
            A(
                label,
                href=ctx.url_for(path),
                cls=f"btn {'btn-primary' if key == active else 'btn-outline-primary'} admin-inline-btn",
                **({"aria_current": "page"} if key == active else {}),
            )
            for key, label, path in links
        ],
        cls="workspace-tab-strip mb-4",
    )


async def _request_timeline(row):
    return Div(
        *[
            Div(
                Div(P(step["label"], cls="fw-semibold mb-1"), P(step["note"], cls="small text-muted mb-0")),
                cls=f"drawer-note-box {'admin-border-primary' if step['state'] == 'current' else ''}",
            )
            for step in row["timeline"]
        ],
        cls="d-grid gap-2",
    )


async def _request_history(row):
    if not row["review_history"]:
        return P("No review history.", cls="text-muted mb-0")
    return Div(
        *[
            Div(
                P(f"{entry['reviewer']} - {entry['action'].replace('_', ' ').title()}", cls="fw-semibold mb-1"),
                P(entry["note"], cls="small text-muted mb-1"),
                P(entry["time"], cls="small text-muted mb-0"),
                cls="drawer-note-box",
            )
            for entry in row["review_history"]
        ],
        cls="d-grid gap-2",
    )


async def _request_card(ctx, row, *, review_mode: bool):
    action_row = Div(
        Button(
            "Review",
            variant="outline-primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#detail-drawer",
            hx_get=ctx.url_for(f"/workflows/requests/{row['request_id']}/drawer"),
            hx_target="#detail-drawer-body",
            hx_swap="innerHTML",
            cls="w-100 w-sm-auto",
        ),
        cls="d-grid d-sm-flex gap-2",
    )
    if review_mode:
        review_actions = [
            Button(
                "Review",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(f"/workflows/requests/{row['request_id']}/drawer"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="w-100 w-sm-auto",
            ),
            Button(
                "Approve",
                variant="success",
                size="md",
                data_bs_toggle="modal",
                data_bs_target="#confirm-modal",
                hx_get=ctx.url_for(f"/workflows/requests/{row['request_id']}/confirm", action="approve"),
                hx_target="#confirm-modal-body",
                hx_swap="innerHTML",
                cls="w-100 w-sm-auto",
            ),
            Button(
                "Reject",
                variant="outline-danger",
                size="md",
                data_bs_toggle="modal",
                data_bs_target="#confirm-modal",
                hx_get=ctx.url_for(f"/workflows/requests/{row['request_id']}/confirm", action="reject"),
                hx_target="#confirm-modal-body",
                hx_swap="innerHTML",
                cls="w-100 w-sm-auto",
            ),
        ]
        if row.get("allow_escalate", True):
            review_actions.append(
                Button(
                    "Escalate",
                    variant="outline-info",
                    size="md",
                    data_bs_toggle="modal",
                    data_bs_target="#confirm-modal",
                    hx_get=ctx.url_for(f"/workflows/requests/{row['request_id']}/confirm", action="escalate"),
                    hx_target="#confirm-modal-body",
                    hx_swap="innerHTML",
                    cls="w-100 w-sm-auto",
                )
            )
        primary_actions = review_actions[1:3]
        secondary_actions = [review_actions[0], *review_actions[3:]]
        action_row = Div(
            Div(*primary_actions, cls="d-grid d-sm-flex gap-2"),
            Div(*secondary_actions, cls="d-grid d-sm-flex gap-2"),
            cls="d-grid gap-2",
        )

    return Div(
        Div(
            Div(
                H4(row["worker_name"], cls="h6 fw-semibold mb-1"),
                P(row["request_type"].replace("_", " ").title(), cls="text-muted mb-0"),
            ),
            status_badge(row["status"]),
            cls="d-flex align-items-start justify-content-between gap-3",
        ),
        Div(
            P(row["origin_location"], cls="small fw-semibold text-dark mb-0"),
            P(row["submitted_at"], cls="small text-muted mb-0"),
            cls="d-flex flex-wrap justify-content-between gap-2 mt-2",
        ),
        P(row["summary"], cls="approval-card__summary text-muted mt-3 mb-3"),
        Div(
            P(f"Current stage: {row['current_stage']}", cls="small text-muted mb-0"),
            P(f"Requested by: {row['requested_by']}", cls="small text-muted mb-0"),
            cls="d-flex flex-column gap-1 mb-3",
        ),
        action_row,
        cls="approval-card",
    )


async def _requests_list(request: Request, ctx, *, view: str, request_type: str = "all", status: str = "all", oob: bool = False):
    if view == "review" and ctx.level < 4:
        attrs = {"id": "review-queue-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#review-queue-results"
        return Div(
            empty_state(
                "shield-lock",
                "Review queue opens from Level 4",
                "Create and review worker requests.",
            ),
            **attrs,
        )

    rows = await WorkflowService.list_requests(
        request,
        ctx,
        request_type=request_type,
        status=status,
        mine_only=view == "mine",
        review_only=view == "review",
    )
    results_id = "my-requests-results" if view == "mine" else "review-queue-results"
    if not rows:
        attrs = {"id": results_id}
        if oob:
            attrs["hx_swap_oob"] = f"outerHTML:#{results_id}"
        return Div(
            empty_state(
                "diagram-3",
                "No workflow items here yet",
                "Requests you create or need to review will show here.",
            ),
            **attrs,
        )
    attrs = {"id": results_id, "cls": "d-grid gap-3"}
    if oob:
        attrs["hx_swap_oob"] = f"outerHTML:#{results_id}"
    return Div(*[_request_card(ctx, row, review_mode=view == "review") for row in rows], **attrs)


async def _request_form(ctx, *, error: str = ""):
    workers = STORE.list_workers(ctx.current_scope_path)
    locations = [row["location"] for row in STORE.visible_locations(ctx.current_scope_path)]
    return Form(
        *hidden_context_inputs(ctx),
        H3("Create request", cls="h5 fw-semibold"),
        P("Use one simple drawer for transfer, status change, or removal requests.", cls="text-muted"),
        P(error, cls="text-danger small mb-3") if error else "",
        Select(
            Option("Select request type", value=""),
            Option("Transfer request", value="transfer_request"),
            Option("Status change", value="status_change"),
            Option("Removal request", value="removal_request"),
            name="request_type",
            cls="form-select mb-3",
            required=True,
        ),
        Select(
            Option("Select worker", value=""),
            *[Option(f"{worker['name']} - {worker['location']}", value=worker["worker_id"]) for worker in workers],
            name="worker_id",
            cls="form-select mb-3",
            required=True,
        ),
        Div(
            Select(
                Option("Destination for transfer", value=""),
                *[Option(name, value=name) for name in locations],
                name="destination_location",
                cls="form-select",
            ),
            Select(
                Option("New status if changing", value=""),
                *[Option(name, value=name) for name in STATUS_CHANGE_OPTIONS],
                name="new_status",
                cls="form-select",
            ),
            cls="drawer-two-up mb-3",
        ),
        Textarea(
            name="reason",
            placeholder="Reason for this request",
            cls="form-control mb-3",
            rows="4",
            required=True,
        ),
        Button("Save request", variant="success", size="md", type="submit", cls="w-100"),
        hx_post=ctx.url_for("/workflows/requests/create"),
        hx_target="#form-drawer-body",
        hx_swap="innerHTML",
    )


async def _live_request_form(request: Request, ctx, *, error: str = "", preset_worker_id: str = "", preset_request_type: str = ""):
    workers = [row for row in await PeopleService.list_workers(request, ctx) if row.get("approval_status") == "approved"]
    locations = await PeopleService.list_locations(request, ctx)
    return Form(
        *hidden_context_inputs(ctx),
        H3("Create request", cls="h5 fw-semibold"),
        P("Submit transfer, status change, or removal requests.", cls="text-muted"),
        P(error, cls="text-danger small mb-3") if error else "",
        Select(
            Option("Select request type", value=""),
            Option("Transfer request", value="transfer_request", selected=preset_request_type == "transfer_request"),
            Option("Status change", value="status_change", selected=preset_request_type == "status_change"),
            Option("Removal request", value="removal_request", selected=preset_request_type == "removal_request"),
            name="request_type",
            cls="form-select mb-3",
            required=True,
        ),
        Select(
            Option("Select worker", value=""),
            *[
                Option(
                    f"{worker['name']} - {worker['location']}",
                    value=worker["worker_id"],
                    selected=worker["worker_id"] == preset_worker_id,
                )
                for worker in workers
            ],
            name="worker_id",
            cls="form-select mb-3",
            required=True,
        ),
        Div(
            Select(
                Option("Destination for transfer", value=""),
                *[Option(row["location_name"], value=row["location_id"]) for row in locations],
                name="destination_location",
                cls="form-select",
            ),
            Select(
                Option("New status if changing", value=""),
                *[Option(name, value=name) for name in STATUS_CHANGE_OPTIONS],
                name="new_status",
                cls="form-select",
            ),
            cls="drawer-two-up mb-3",
        ),
        Textarea(
            name="reason",
            placeholder="Reason for this request",
            cls="form-control mb-3",
            rows="4",
            required=True,
        ),
        Button("Save request", variant="success", size="md", type="submit", cls="w-100"),
        hx_post=ctx.url_for("/workflows/requests/create"),
        hx_target="#form-drawer-body",
        hx_swap="innerHTML",
    )


def register_workflow_routes(app) -> None:
    @app.get("/workflows")
    async def workflows_root(request: Request):
        ctx = build_context(request)
        return RedirectResponse(ctx.url_for("/workflows/my-requests"))

    @app.get("/workflows/my-requests")
    async def my_requests_page(request: Request, request_type: str = "all", status: str = "all"):
        ctx = build_context(request)
        try:
            results = await _requests_list(request, ctx, view="mine", request_type=request_type, status=status)
        except BackendClientError as exc:
            results = Div(empty_state("cloud-slash", "Live workflow list is unavailable", str(exc)), id="my-requests-results")
        filter_form = Form(
            *hidden_context_inputs(ctx),
            filter_field(
                "Request type",
                Select(
                    *[Option(label, value=value, selected=request_type == value) for value, label in REQUEST_TYPES],
                    name="request_type",
                    cls="form-select",
                ),
                field_id="my-requests-type",
            ),
            filter_field(
                "Status",
                Select(
                    *[Option(label, value=value, selected=status == value) for value, label in REQUEST_STATUSES],
                    name="status",
                    cls="form-select",
                ),
                field_id="my-requests-status",
            ),
            hx_get=ctx.url_for("/workflows/my-requests/list"),
            hx_target="#my-requests-results",
            hx_swap="outerHTML",
            hx_trigger="change from:select",
            cls="admin-filter-grid",
        )
        body = page_stack(
            page_intro(
                "Workflows",
                "Track requests you submitted and keep review work separate from your own request history.",
                scope_label=ctx.current_scope_label,
                scope_kind=ctx.current_scope_kind,
            ),
            _workflows_nav(ctx, "my-requests"),
            section_card(
                "My requests",
                "Removal, transfer, and status-change requests you created in the current scope.",
                filter_form,
                results,
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="workflows",
            title="My Requests",
            subtitle="Requests created by you or from your immediate working scope.",
            primary_action=primary_button(
                "Create Request",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/workflows/requests/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            content=body,
            show_shell_intro=False,
        )

    @app.get("/workflows/review-queue")
    async def review_queue_page(request: Request, request_type: str = "all", status: str = "all"):
        ctx = build_context(request)
        try:
            results = await _requests_list(request, ctx, view="review", request_type=request_type, status=status)
        except BackendClientError as exc:
            results = Div(empty_state("cloud-slash", "Live review queue is unavailable", str(exc)), id="review-queue-results")
        filter_form = Form(
            *hidden_context_inputs(ctx),
            filter_field(
                "Request type",
                Select(
                    *[Option(label, value=value, selected=request_type == value) for value, label in REQUEST_TYPES],
                    name="request_type",
                    cls="form-select",
                ),
                field_id="review-queue-type",
            ),
            filter_field(
                "Status",
                Select(
                    *[Option(label, value=value, selected=status == value) for value, label in REQUEST_STATUSES],
                    name="status",
                    cls="form-select",
                ),
                field_id="review-queue-status",
            ),
            hx_get=ctx.url_for("/workflows/review-queue/list"),
            hx_target="#review-queue-results",
            hx_swap="outerHTML",
            hx_trigger="change from:select",
            cls="admin-filter-grid",
        )
        body = page_stack(
            page_intro(
                "Workflows",
                "Review submitted requests and decisions in one place.",
                scope_label=ctx.current_scope_label,
                scope_kind=ctx.current_scope_kind,
            ),
            _workflows_nav(ctx, "review-queue"),
            section_card(
                "Review queue",
                "Decision center for Levels 4 to 9, with approval, rejection, escalation, and review history.",
                filter_form,
                results,
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="workflows",
            title="Review Queue",
            subtitle="Requests waiting for your decision in the current scope.",
            primary_action=None,
            content=body,
            show_shell_intro=False,
        )

    @app.get("/workflows/my-requests/list")
    async def my_requests_list(request: Request, request_type: str = "all", status: str = "all"):
        ctx = build_context(request)
        try:
            return await _requests_list(request, ctx, view="mine", request_type=request_type, status=status)
        except BackendClientError as exc:
            return Div(empty_state("cloud-slash", "Live workflow list is unavailable", str(exc)), id="my-requests-results")

    @app.get("/workflows/review-queue/list")
    async def review_queue_list(request: Request, request_type: str = "all", status: str = "all"):
        ctx = build_context(request)
        try:
            return await _requests_list(request, ctx, view="review", request_type=request_type, status=status)
        except BackendClientError as exc:
            return Div(empty_state("cloud-slash", "Live review queue is unavailable", str(exc)), id="review-queue-results")

    @app.get("/workflows/requests/new")
    async def new_request_form(request: Request):
        ctx = build_context(request)
        if await WorkflowService.live_enabled(request):
            try:
                return await _live_request_form(request, ctx)
            except BackendClientError as exc:
                return P(f"Could not load request form right now: {exc}", cls="text-muted")
        return _request_form(ctx)

    @app.post("/workflows/requests/create")
    async def create_request(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        request_type = data.get("request_type", "").strip()
        worker_id = data.get("worker_id", "").strip()
        reason = data.get("reason", "").strip()
        if not request_type or not worker_id or not reason:
            return (
                await _live_request_form(request, ctx, error="Choose the request type, worker, and reason before saving.")
                if await WorkflowService.live_enabled(request)
                else _request_form(ctx, error="Choose the request type, worker, and reason before saving.")
            )
        if request_type == "transfer_request" and not data.get("destination_location", "").strip():
            return await _live_request_form(request, ctx, error="Choose the destination location for this transfer request.") if await WorkflowService.live_enabled(request) else _request_form(ctx, error="Choose the destination location for this transfer request.")
        if request_type == "status_change" and not data.get("new_status", "").strip():
            return await _live_request_form(request, ctx, error="Choose the new worker status for this status-change request.") if await WorkflowService.live_enabled(request) else _request_form(ctx, error="Choose the new worker status for this status-change request.")
        try:
            if await WorkflowService.live_enabled(request):
                row = await WorkflowService.create_request(
                    request,
                    ctx,
                    request_type=request_type,
                    worker_id=worker_id,
                    reason=reason,
                    destination_location_id=data.get("destination_location", "").strip(),
                    new_status=data.get("new_status", "").strip(),
                )
            else:
                row = STORE.add_request(data, ctx.profile.user_name)
        except KeyError:
            return _request_form(ctx, error="The selected worker is no longer available. Please reopen the form.")
        except BackendClientError as exc:
            return await _live_request_form(request, ctx, error=str(exc)) if await WorkflowService.live_enabled(request) else _request_form(ctx, error=str(exc))
        return simple_toast_response(
            content=(
                Div(
                    H3("Request saved", cls="h5 fw-semibold"),
                    P(f"{row['request_type'].replace('_', ' ').title()} for {row['worker_name']} has entered review.", cls="mb-0"),
                ),
                await _requests_list(request, ctx, view="mine", oob=True),
            ),
            message="Workflow request saved.",
            variant="success",
        )

    @app.get("/workflows/requests/{request_id}/drawer")
    async def request_drawer(request: Request, request_id: str):
        ctx = build_context(request)
        try:
            row = await WorkflowService.get_request(request, ctx, request_id)
        except BackendClientError as exc:
            return P(f"Could not load this request right now: {exc}", cls="text-muted")
        if row is None:
            return P("Request not found.", cls="text-muted")
        try:
            worker = await PeopleService.get_worker(request, row["worker_id"]) if row.get("worker_id") else None
            linked_user = await PeopleService.get_user_by_worker(request, ctx, row["worker_id"]) if row.get("worker_id") else None
        except BackendClientError as exc:
            return P(f"Could not load linked records right now: {exc}", cls="text-muted")
        follow_up_actions = []
        if worker is not None:
            follow_up_actions.append(
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
        if linked_user is not None:
            follow_up_actions.append(
                Button(
                    "Open app account",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/people/users/{linked_user['account_id']}/drawer"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                )
            )
        return Div(
            H3(row["worker_name"], cls="h5 fw-semibold"),
            P(row["request_type"].replace("_", " ").title(), cls="text-muted"),
            Div(
                Div(P("Status", cls="small text-muted mb-1"), status_badge(row["status"])),
                Div(P("Current stage", cls="small text-muted mb-1"), P(row["current_stage"], cls="fw-semibold mb-0")),
                Div(P("Origin", cls="small text-muted mb-1"), P(row["origin_location"], cls="fw-semibold mb-0")),
                Div(P("Destination", cls="small text-muted mb-1"), P(row["destination_location"] or "-", cls="fw-semibold mb-0")),
                Div(P("Requested by", cls="small text-muted mb-1"), P(row["requested_by"], cls="fw-semibold mb-0")),
                Div(P("Submitted", cls="small text-muted mb-1"), P(row["submitted_at"], cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            Div(
                H4("Affected records", cls="h6 fw-semibold mb-2 mt-3"),
                Div(
                    Div(P("Worker status", cls="small text-muted mb-1"), status_badge(worker["status"]) if worker else P("Not found.", cls="fw-semibold mb-0")),
                    Div(P("Worker location", cls="small text-muted mb-1"), P(worker["location"] if worker else "-", cls="fw-semibold mb-0")),
                    Div(P("App account", cls="small text-muted mb-1"), status_badge(linked_user["status"]) if linked_user else P("No linked account", cls="fw-semibold mb-0")),
                    cls="drawer-meta-grid",
                ),
                cls="drawer-note-box mt-3",
            ),
            Div(H4("Summary", cls="h6 fw-semibold mb-2"), P(row["summary"], cls="mb-0"), cls="drawer-note-box mt-3"),
            Div(H4("Timeline", cls="h6 fw-semibold mb-2 mt-3"), _request_timeline(row)),
            Div(H4("Review history", cls="h6 fw-semibold mb-2 mt-3"), _request_history(row)),
            Div(H4("Open related records", cls="h6 fw-semibold mb-2 mt-3"), Div(*follow_up_actions, cls="d-grid gap-2") if follow_up_actions else P("No linked records available.", cls="text-muted mb-0")),
        )

    @app.get("/workflows/requests/{request_id}/confirm")
    async def request_confirm(request: Request, request_id: str, action: str = "approve"):
        ctx = build_context(request)
        try:
            row = await WorkflowService.get_request(request, ctx, request_id)
        except BackendClientError as exc:
            return P(f"Could not load this request right now: {exc}", cls="text-muted")
        if row is None:
            return P("Request not found.", cls="text-muted")
        if action == "escalate" and not row.get("allow_escalate", True):
            return P("This request type cannot be escalated from the live review flow.", cls="text-muted")
        labels = {
            "approve": "Approve request",
            "reject": "Reject request",
            "escalate": "Escalate request",
        }
        return Form(
            *hidden_context_inputs(ctx),
            Input(type="hidden", name="action", value=action),
            H3(labels.get(action, "Confirm action"), cls="h5 fw-semibold"),
            P(f"{row['worker_name']} - {row['request_type'].replace('_', ' ').title()}", cls="text-muted"),
            Textarea(name="notes", placeholder="Add reviewer notes", cls="form-control mb-3", rows="4"),
            Button(
                labels.get(action, "Continue"),
                variant="success" if action == "approve" else "danger" if action == "reject" else "info",
                size="md",
                type="submit",
                cls="w-100",
            ),
            hx_post=ctx.url_for(f"/workflows/requests/{request_id}/act"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/workflows/requests/{request_id}/act")
    async def act_request(request: Request, request_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        action = data.get("action", "approve")
        try:
            row = await WorkflowService.act_request(request, ctx, request_id, action, data.get("notes", ""))
        except BackendClientError as exc:
            return P(str(exc), cls="text-muted")
        if row is None:
            return P("Request not found.", cls="text-muted")
        message = {
            "approve": "Request approved.",
            "reject": "Request rejected.",
            "escalate": "Request escalated.",
        }[action]
        variant = "success" if action == "approve" else "danger" if action == "reject" else "warning"
        return simple_toast_response(
            content=(
                Div(H3("Decision recorded", cls="h5 fw-semibold"), P(message, cls="mb-0")),
                await _requests_list(request, ctx, view="review", oob=True),
            ),
            message=message,
            variant=variant,
        )
