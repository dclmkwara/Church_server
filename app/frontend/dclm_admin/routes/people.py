from __future__ import annotations

from fasthtml.common import Div, Form, H3, Input, Option, P, Select, Textarea
from starlette.requests import Request

from faststrap import Button, PlaceholderCard, Spinner

from ..backend import BackendClientError
from ..auth_context import build_context
from ..communication import PeopleService, WorkflowService
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, primary_button, shell_layout
from ..components.ui import empty_state, filter_field as _filter_field, page_intro, page_stack, responsive_table, section_card, stat_card, status_badge
from ..mock_data import STORE, TODAY, UNITS


ROLE_OPTIONS = [
    "Location Worker",
    "Location Admin",
    "Choir Admin",
    "Group Admin",
    "Region Pastor",
    "State Overseer",
]

MARITAL_STATUS_OPTIONS = ["Single", "Married", "Widowed"]
MEMBER_STATUS_OPTIONS = ["active", "inactive", "transferred"]
WORKER_STATUS_REQUEST_OPTIONS = ["Active", "Inactive", "Suspended"]
OFFICIAL_ROLE_OPTIONS = [
    "Follow-up Coordinator",
    "Treasury Secretary",
    "Children Coordinator",
    "Campus Prayer Secretary",
    "Welfare Assistant",
    "Evangelism Secretary",
]


async def _loading_results(target_id: str, *, hx_get: str, message: str) -> Div:
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


async def _scope_assignment_options(request: Request, ctx):
    options = [(ctx.current_scope_label, ctx.current_scope_path)]
    if await PeopleService.live_enabled(request):
        visible_locations = [
            {"location": row["location_name"], "path": row["path"]}
            for row in await PeopleService.list_locations(request, ctx)
        ]
    else:
        visible_locations = STORE.visible_locations(ctx.current_scope_path)
    for row in visible_locations:
        pair = (row["location"], row["path"])
        if pair not in options:
            options.append(pair)
    return options


async def _official_mobile_card(ctx, appointment):
    return Div(
        H3(appointment["worker_name"], cls="fw-bold mb-0 lh-sm"),
        P(appointment["appointed_role"], cls="text-dark mb-1"),
        P(appointment["assigned_scope"], cls="text-muted small mb-2"),
        Div(status_badge(appointment["status"]), cls="d-flex flex-wrap gap-1 mb-2"),
        Div(
            Button(
                "View details",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(f"/people/officials/{appointment['appointment_id']}/drawer"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="w-100",
            ),
            cls="d-grid",
        ),
        cls="mobile-worker-card",
    )


async def _officials_table(request: Request, ctx, *, search: str = "", status: str = "", appointed_role: str = "", oob: bool = False) -> Div:
    rows = await PeopleService.list_official_appointments(request, ctx, search=search, status=status, appointed_role=appointed_role)
    if not rows:
        attrs = {"id": "officials-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#officials-results"
        return Div(empty_state("person-check", "No official appointments match this filter", "Try another role, status, or search term."), **attrs)

    desktop_rows = []
    mobile_cards = []
    for appointment in rows:
        desktop_rows.append(
            [
                appointment["worker_name"],
                appointment["appointed_role"],
                appointment["assigned_scope"],
                appointment["appointed_by"],
                appointment["appointment_date"],
                status_badge(appointment["status"]),
                Div(
                    Button(
                        "View",
                        variant="outline-primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#detail-drawer",
                        hx_get=ctx.url_for(f"/people/officials/{appointment['appointment_id']}/drawer"),
                        hx_target="#detail-drawer-body",
                        hx_swap="innerHTML",
                    ),
                    cls="d-grid",
                ),
            ]
        )
        mobile_cards.append(await _official_mobile_card(ctx, appointment))
    return responsive_table(
        ["Worker", "Role", "Assigned Scope", "Appointed By", "Date", "Status", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="officials-results",
        oob="outerHTML:#officials-results" if oob else None,
    )


async def _worker_mobile_card(ctx, worker):
    return Div(
        H3(worker["name"], cls="fw-bold mb-0 lh-sm"),
        P(f"{worker['unit']} • {worker['location']}", cls="text-muted mb-3"),
        Div(status_badge(worker["approval_status"]), status_badge(worker["status"]), cls="d-flex flex-wrap gap-1 mb-2"),
        Div(
            Button(
                "View details",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(f"/people/workers/{worker['worker_id']}/drawer"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="w-100",
            ),
            cls="d-grid",
        ),
        cls="mobile-worker-card",
    )


async def _workers_table(request: Request, ctx, *, search: str = "", status: str = "", approval: str = "", oob: bool = False) -> Div:
    rows = await PeopleService.list_workers(request, ctx, search=search, status=status, approval=approval)
    if not rows:
        attrs = {"id": "workers-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#workers-results"
        return Div(empty_state("people", "No workers match this filter", "Try a different status or search term."), **attrs)

    desktop_rows = []
    mobile_cards = []
    for worker in rows:
        desktop_rows.append(
            [
                Div(P(worker["name"], cls="fw-semibold mb-1"), P(worker.get("public_code") or worker["user_id"], cls="small text-muted mb-0")),
                worker["location"],
                worker["unit"],
                status_badge(worker["approval_status"]),
                status_badge(worker["status"]),
                Div(
                    Button(
                        "View",
                        variant="outline-primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#detail-drawer",
                        hx_get=ctx.url_for(f"/people/workers/{worker['worker_id']}/drawer"),
                        hx_target="#detail-drawer-body",
                        hx_swap="innerHTML",
                    ),
                ),
            ]
        )
        mobile_cards.append(await _worker_mobile_card(ctx, worker))
    return responsive_table(
        ["Worker", "Location", "Unit", "Approval", "Status", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="workers-results",
        oob="outerHTML:#workers-results" if oob else None,
    )


async def _worker_detail_panel(request: Request, ctx, worker):
    if await PeopleService.live_enabled(request):
        linked_user = await PeopleService.get_user_by_worker(request, ctx, worker["worker_id"])
        requests = [
            row
            for row in await WorkflowService.list_requests(request, ctx, request_type="all", status="all")
            if row.get("worker_id") == worker["worker_id"]
        ]
        visible_locations = [
            row.get("location_name") or row.get("location_id") or ""
            for row in await PeopleService.list_locations(request, ctx)
            if (row.get("location_name") or row.get("location_id") or "") != worker["location"]
        ]
    else:
        linked_user = STORE.get_user_by_worker(worker["worker_id"])
        requests = STORE.list_worker_requests(worker["worker_id"])
        visible_locations = [row["location"] for row in STORE.visible_locations(ctx.current_scope_path) if row["location"] != worker["location"]]
    account_action = (
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
        if linked_user
        else Button(
            "Create app account",
            variant="primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#form-drawer",
            hx_get=ctx.url_for(f"/people/workers/{worker['worker_id']}/account"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )
    )
    history_block = (
        Div(
            H3("Workflow history", cls="h6 fw-semibold mt-4 mb-3"),
            *[
                Div(
                    Div(
                        P(row["request_type"].replace("_", " ").title(), cls="fw-semibold mb-1"),
                        P(row["current_stage"], cls="small text-muted mb-0"),
                    ),
                    Div(
                        status_badge(row["status"]),
                        Button(
                            "Open",
                            variant="outline-primary",
                            size="md",
                            data_bs_toggle="offcanvas",
                            data_bs_target="#detail-drawer",
                            hx_get=ctx.url_for(f"/workflows/requests/{row['request_id']}/drawer"),
                            hx_target="#detail-drawer-body",
                            hx_swap="innerHTML",
                        ),
                        cls="d-grid gap-2",
                    ),
                    P(row["summary"], cls="small text-muted mb-0 mt-3"),
                    cls="drawer-note-box",
                )
                for row in requests[:3]
            ],
            cls="d-grid gap-3",
        )
        if requests
        else Div(
            H3("Workflow history", cls="h6 fw-semibold mt-4 mb-3"),
            P("No workflow requests have been raised for this worker.", cls="text-muted mb-0"),
        )
    )
    return Div(
        H3(worker["name"], cls="h5 fw-semibold"),
        P(f"{worker['unit']} - {worker['location']}", cls="text-muted"),
        Div(
            Div(P("Worker Code", cls="small text-muted mb-1"), P(worker.get("public_code") or worker["user_id"], cls="fw-semibold mb-0")),
            Div(P("Phone", cls="small text-muted mb-1"), P(worker["phone"], cls="fw-semibold mb-0")),
            Div(P("Approval", cls="small text-muted mb-1"), status_badge(worker["approval_status"])),
            Div(P("Status", cls="small text-muted mb-1"), status_badge(worker["status"])),
            Div(P("App account", cls="small text-muted mb-1"), P(linked_user["name"] if linked_user else "No account", cls="fw-semibold mb-0")),
            cls="drawer-meta-grid",
        ),
        Div(
            account_action,
            Button(
                "Suspend worker",
                variant="outline-danger",
                size="md",
                disabled=worker["status"].lower() == "suspended",
                data_bs_toggle="modal",
                data_bs_target="#confirm-modal",
                hx_get=ctx.url_for(f"/people/workers/{worker['worker_id']}/suspend"),
                hx_target="#confirm-modal-body",
                hx_swap="innerHTML",
            ),
            Button(
                "Transfer request",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for(f"/people/workers/{worker['worker_id']}/transfer"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
                disabled=not visible_locations,
            ),
            Button(
                "Status change",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for(f"/people/workers/{worker['worker_id']}/status-change"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            Button(
                "Request removal",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for(f"/people/workers/{worker['worker_id']}/removal"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            cls="d-grid gap-2 mt-3",
        ),
        history_block,
    )


async def _user_mobile_card(ctx, user):
    return Div(
        H3(user["name"], cls="fw-bold mb-0 lh-sm"),
        P(user["location"], cls="text-muted small mb-2"),
        Div(*[status_badge(role) for role in user["roles"]], cls="d-flex flex-wrap gap-1 mb-2"),
        Div(status_badge(user["approval_status"]), status_badge(user["status"]), cls="d-flex flex-wrap gap-1 mb-2"),
        Div(
            Button(
                "View details",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(f"/people/users/{user['account_id']}/drawer"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="w-100",
            ),
            cls="d-grid",
        ),
        cls="mobile-worker-card",
    )


async def _live_people_review_form(ctx, *, heading: str, subtitle: str, post_url: str, action: str, submit_label: str, require_reason: bool = False):
    fields = [
        *hidden_context_inputs(ctx),
        Input(type="hidden", name="action", value=action),
        H3(heading, cls="h5 fw-semibold"),
        P(subtitle, cls="text-muted"),
    ]
    if require_reason:
        fields.append(
            Textarea(
                name="reason",
                placeholder="Add a clear reason so the worker or pastor can understand the decision",
                cls="form-control mb-3",
                rows="4",
                minlength="10",
                required=True,
            )
        )
    fields.extend(
        [
            Button(submit_label, variant="primary" if action == "approve" else "danger", type="submit", cls="w-100"),
        ]
    )
    return Form(*fields, hx_post=post_url, hx_target="#confirm-modal-body", hx_swap="innerHTML")


async def _live_role_selects(role_rows, *, primary_name: str = "role_primary", secondary_name: str = "role_secondary", primary_value: str = "", secondary_value: str = ""):
    return Div(
        Select(
            *([Option("Select primary role", value="")] + [Option(role["role_name"], value=str(role["id"]), selected=str(role["id"]) == primary_value) for role in role_rows]),
            name=primary_name,
            cls="form-select",
            required=True,
        ),
        Select(
            *([Option("No support role", value="")] + [Option(role["role_name"], value=str(role["id"]), selected=str(role["id"]) == secondary_value) for role in role_rows]),
            name=secondary_name,
            cls="form-select",
        ),
        cls="drawer-two-up mb-3",
    )


async def _users_table(request: Request, ctx, *, search: str = "", approval: str = "", status: str = "", oob: bool = False) -> Div:
    rows = await PeopleService.list_users(request, ctx, search=search, approval=approval, status=status)
    if not rows:
        attrs = {"id": "users-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#users-results"
        return Div(empty_state("person-badge", "No users match this filter", "Try a different status or approval filter."), **attrs)

    desktop_rows = []
    mobile_cards = []
    for user in rows:
        desktop_rows.append(
            [
                Div(P(user["name"], cls="fw-semibold mb-1"), P(user.get("public_code") or user["phone"], cls="small text-muted mb-0")),
                user["location"],
                Div(*[status_badge(role) for role in user["roles"]], cls="d-flex flex-wrap gap-1"),
                status_badge(user["approval_status"]),
                status_badge(user["status"]),
                Button(
                    "View",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/people/users/{user['account_id']}/drawer"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                ),
            ]
        )
        mobile_cards.append(await _user_mobile_card(ctx, user))
    return responsive_table(
        ["User", "Location", "Roles", "Approval", "Status", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="users-results",
        oob="outerHTML:#users-results" if oob else None,
    )


async def _member_mobile_card(ctx, member):
    return Div(
        H3(member["name"], cls="fw-bold mb-0 lh-sm"),
        P(f"{member['fellowship_name'] or 'No fellowship'} • {member['location']}", cls="text-muted mb-3"),
        Div(status_badge(member["status"]), cls="d-flex flex-wrap gap-1 mb-2"),
        P(f"Joined {member['date_joined']}", cls="small text-muted mb-2"),
        Div(
            Button(
                "View details",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#detail-drawer",
                hx_get=ctx.url_for(f"/people/members/{member['member_id']}/drawer"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="w-100",
            ),
            cls="d-grid",
        ),
        cls="mobile-worker-card",
    )


async def _members_table(
    request: Request,
    ctx,
    *,
    search: str = "",
    location: str = "",
    status: str = "",
    fellowship_id: str = "",
    oob: bool = False,
) -> Div:
    rows = await PeopleService.list_members(
        request,
        ctx,
        search=search,
        location_id=location,
        status=status,
        fellowship_id=fellowship_id,
    )
    if not rows:
        attrs = {"id": "members-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#members-results"
        return Div(
            empty_state("person-vcard", "No members match this filter", "Try another location, fellowship, or search term."),
            **attrs,
        )

    desktop_rows = []
    mobile_cards = []
    for member in rows:
        desktop_rows.append(
            [
                Div(P(member["name"], cls="fw-semibold mb-1"), P(member["phone"], cls="small text-muted mb-0")),
                member["location"],
                member["fellowship_name"] or "Not assigned",
                status_badge(member["status"]),
                member["date_joined"],
                Button(
                    "View",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/people/members/{member['member_id']}/drawer"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                ),
            ]
        )
        mobile_cards.append(await _member_mobile_card(ctx, member))
    return responsive_table(
        ["Member", "Location", "Fellowship", "Status", "Joined", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="members-results",
        oob="outerHTML:#members-results" if oob else None,
    )


def register_people_routes(app) -> None:
    @app.get("/people/workers")
    async def workers_page(request: Request, search: str = "", status: str = "", approval: str = ""):
        ctx = build_context(request)
        workers_results = await _loading_results(
            "workers-results",
            hx_get=ctx.url_for("/people/workers/list", search=search, status=status, approval=approval),
            message="Loading workers.",
        )
        filter_form = Form(
            *hidden_context_inputs(ctx),
            _filter_field(
                "Search workers",
                "workers-filter-search",
                Input(
                    type="search",
                    id="workers-filter-search",
                    name="search",
                    value=search,
                    placeholder="Search workers",
                    cls="form-control",
                ),
            ),
            _filter_field(
                "Worker status",
                "workers-filter-status",
                Select(
                    Option("All status", value=""),
                    Option("Active", value="Active", selected=status == "Active"),
                    Option("Inactive", value="Inactive", selected=status == "Inactive"),
                    Option("Pending Verification", value="Pending Verification", selected=status == "Pending Verification"),
                    Option("Suspended", value="Suspended", selected=status == "Suspended"),
                    id="workers-filter-status",
                    name="status",
                    cls="form-select",
                ),
            ),
            _filter_field(
                "Approval status",
                "workers-filter-approval",
                Select(
                    Option("All approvals", value=""),
                    Option("Approved", value="approved", selected=approval == "approved"),
                    Option("Pending verification", value="pending_verification", selected=approval == "pending_verification"),
                    id="workers-filter-approval",
                    name="approval",
                    cls="form-select",
                ),
            ),
            hx_get=ctx.url_for("/people/workers/list"),
            hx_target="#workers-results",
            hx_swap="outerHTML",
            hx_trigger="keyup changed delay:350ms from:input, change from:select",
            cls="admin-filter-grid",
        )
        body = page_stack(
            page_intro(
                "Workers",
                "Keep worker management simple: register, review and open details without leaving the page.",
                scope_label=ctx.current_scope_label,
                scope_kind=ctx.current_scope_kind,
            ),
            section_card(
                "Workers directory",
                "Filter by name, unit, worker code, approval, or status.",
                filter_form,
                workers_results,
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="workers",
            title="Workers",
            subtitle="Worker records and review actions.",
            primary_action=primary_button(
                "Register Worker",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/people/workers/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            content=body,
            show_shell_intro=False,
        )

    @app.get("/people/workers/list")
    async def workers_list(request: Request, search: str = "", status: str = "", approval: str = ""):
        ctx = build_context(request)
        try:
            return await _workers_table(request, ctx, search=search, status=status, approval=approval)
        except BackendClientError as exc:
            return Div(empty_state("cloud-slash", "Live worker directory is unavailable", str(exc)), id="workers-results")

    @app.get("/people/workers/new")
    async def new_worker_drawer(request: Request):
        ctx = build_context(request)
        if await PeopleService.live_enabled(request):
            try:
                live_locations = await PeopleService.list_locations(request, ctx)
            except BackendClientError as exc:
                return P(f"Could not load worker form right now: {exc}", cls="text-muted")
            return Form(
                *hidden_context_inputs(ctx),
                H3("Register worker", cls="h5 fw-semibold"),
                P("Create a real worker record in the backend using the branch details already stored for the selected location.", cls="text-muted"),
                Input(type="text", name="name", placeholder="Full name", cls="form-control mb-3", required=True),
                Div(
                    Select(
                        Option("Select gender", value=""),
                        Option("Male", value="Male"),
                        Option("Female", value="Female"),
                        name="gender",
                        cls="form-select",
                        required=True,
                    ),
                    Select(
                        Option("Select location", value=""),
                        *[Option(row["location_name"], value=row["location_id"]) for row in live_locations],
                        name="location_id",
                        cls="form-select",
                        required=True,
                    ),
                    cls="drawer-two-up mb-3",
                ),
                Div(
                    Select(
                        *([Option("Select unit", value="")] + [Option(unit, value=unit) for unit in UNITS]),
                        name="unit",
                        cls="form-select",
                        required=True,
                    ),
                    Input(type="text", name="phone", placeholder="Phone number", cls="form-control", required=True),
                    cls="drawer-two-up mb-3",
                ),
                Div(
                    Input(type="email", name="email", placeholder="Email address", cls="form-control", required=True),
                    Select(
                        Option("Select marital status", value=""),
                        *[Option(label, value=label) for label in MARITAL_STATUS_OPTIONS],
                        name="marital_status",
                        cls="form-select",
                    ),
                    cls="drawer-two-up mb-3",
                ),
                Input(type="text", name="occupation", placeholder="Occupation", cls="form-control mb-3"),
                Textarea(name="address", placeholder="Home address", cls="form-control mb-3", rows="3"),
                Button("Save worker", variant="success", type="submit", cls="w-100"),
                hx_post=ctx.url_for("/people/workers/create"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            )
        visible_locations = [row["location"] for row in STORE.visible_locations(ctx.current_scope_path)]
        return Form(
            *hidden_context_inputs(ctx),
            H3("Register worker", cls="h5 fw-semibold"),
            P("Use plain details that a pastor can confirm quickly on phone.", cls="text-muted"),
            Input(type="text", name="name", placeholder="Full name", cls="form-control mb-3", required=True),
            Div(
                Select(
                    Option("Select gender", value=""),
                    Option("Male", value="Male"),
                    Option("Female", value="Female"),
                    name="gender",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    *([Option("Select location", value="")] + [Option(name, value=name) for name in visible_locations]),
                    name="location",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    *([Option("Select unit", value="")] + [Option(unit, value=unit) for unit in UNITS]),
                    name="unit",
                    cls="form-select",
                    required=True,
                ),
                Input(type="text", name="phone", placeholder="Phone number", cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Textarea(name="notes", placeholder="Optional pastoral note", cls="form-control mb-3", rows="3"),
            Button("Save worker", variant="success", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/people/workers/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/workers/create")
    async def create_worker(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        try:
            if await PeopleService.live_enabled(request):
                location_id = data.get("location_id", "").strip()
                if not location_id:
                    return P("Choose the worker's location before saving.", cls="text-muted")
                location_details = await PeopleService.get_location_details(request, location_id)
                if location_details is None:
                    return P("That location could not be verified right now.", cls="text-muted")
                worker = await PeopleService.create_worker(
                    request,
                    {
                        "location_id": location_details["location_id"],
                        "location_name": location_details["location_name"],
                        "church_type": location_details["church_type"],
                        "state": location_details["state_name"],
                        "region": location_details["region_name"],
                        "group": location_details["group_name"],
                        "name": data.get("name", "").strip(),
                        "gender": data.get("gender", "").strip(),
                        "phone": data.get("phone", "").strip(),
                        "email": data.get("email", "").strip(),
                        "address": data.get("address", "").strip() or None,
                        "occupation": data.get("occupation", "").strip() or None,
                        "marital_status": data.get("marital_status", "").strip() or None,
                        "unit": data.get("unit", "").strip(),
                        "status": "Active",
                    },
                )
            else:
                worker = STORE.add_worker(data)
        except BackendClientError as exc:
            return P(f"Could not save this worker right now: {exc}", cls="text-muted")
        if worker is None:
            return P("Worker could not be created.", cls="text-muted")
        refreshed = await _workers_table(request, ctx, oob=True)
        return simple_toast_response(
            content=(
                Div(
                    H3("Worker saved", cls="h5 fw-semibold"),
                    P(
                        f"{worker['name']} is now {'approved and available' if worker.get('approval_status') == 'approved' else 'waiting for approval'} in {worker['location']}.",
                        cls="mb-0",
                    ),
                ),
                refreshed,
            ),
            message="Worker registration saved.",
            variant="success",
        )

    @app.get("/people/workers/{worker_id}/drawer")
    async def worker_drawer(request: Request, worker_id: str):
        ctx = build_context(request)
        try:
            worker = await PeopleService.get_worker(request, worker_id)
        except BackendClientError as exc:
            return P(f"Could not load worker right now: {exc}", cls="text-muted")
        if worker is None:
            return P("Worker not found.", cls="text-muted")
        if await PeopleService.live_enabled(request):
            linked_user = await PeopleService.get_user_by_worker(request, ctx, worker_id)
            live_actions = []
            if worker["approval_status"] == "pending_verification":
                live_actions.extend(
                    [
                        Button(
                            "Approve worker",
                            variant="primary",
                            size="md",
                            data_bs_toggle="modal",
                            data_bs_target="#confirm-modal",
                            hx_get=ctx.url_for(f"/people/workers/{worker_id}/review?action=approve"),
                            hx_target="#confirm-modal-body",
                            hx_swap="innerHTML",
                        ),
                        Button(
                            "Reject worker",
                            variant="outline-danger",
                            size="md",
                            data_bs_toggle="modal",
                            data_bs_target="#confirm-modal",
                            hx_get=ctx.url_for(f"/people/workers/{worker_id}/review?action=reject"),
                            hx_target="#confirm-modal-body",
                            hx_swap="innerHTML",
                        ),
                    ]
                )
            elif worker["approval_status"] == "approved":
                live_actions.extend(
                    [
                        Button(
                            "Transfer request",
                            variant="outline-primary",
                            size="md",
                            data_bs_toggle="offcanvas",
                            data_bs_target="#form-drawer",
                            hx_get=ctx.url_for(f"/people/workers/{worker_id}/transfer"),
                            hx_target="#form-drawer-body",
                            hx_swap="innerHTML",
                        ),
                        Button(
                            "Status change",
                            variant="outline-primary",
                            size="md",
                            data_bs_toggle="offcanvas",
                            data_bs_target="#form-drawer",
                            hx_get=ctx.url_for(f"/people/workers/{worker_id}/status-change"),
                            hx_target="#form-drawer-body",
                            hx_swap="innerHTML",
                        ),
                        Button(
                            "Request removal",
                            variant="outline-primary",
                            size="md",
                            data_bs_toggle="offcanvas",
                            data_bs_target="#form-drawer",
                            hx_get=ctx.url_for(f"/people/workers/{worker_id}/removal"),
                            hx_target="#form-drawer-body",
                            hx_swap="innerHTML",
                        ),
                    ]
                )
            if linked_user:
                live_actions.append(
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
            elif worker["approval_status"] == "approved":
                live_actions.append(
                    Button(
                        "Create app account",
                        variant="primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#form-drawer",
                        hx_get=ctx.url_for(f"/people/workers/{worker_id}/account"),
                        hx_target="#form-drawer-body",
                        hx_swap="innerHTML",
                    )
                )
            live_note = (
                "Approve or reject this worker here, then continue the wider lifecycle in Workflows."
                if worker["approval_status"] == "pending_verification"
                else "This worker can now raise live transfer, status-change, and removal requests."
            )
            return Div(
                H3(worker["name"], cls="h5 fw-semibold"),
                P(f"{worker['unit']} - {worker['location']}", cls="text-muted"),
                Div(
                    Div(P("Worker Code", cls="small text-muted mb-1"), P(worker.get("public_code") or worker["user_id"], cls="fw-semibold mb-0")),
                    Div(P("Phone", cls="small text-muted mb-1"), P(worker["phone"], cls="fw-semibold mb-0")),
                    Div(P("Email", cls="small text-muted mb-1"), P(worker.get("email") or "Not available", cls="fw-semibold mb-0")),
                    Div(P("Approval", cls="small text-muted mb-1"), status_badge(worker["approval_status"])),
                    Div(P("Status", cls="small text-muted mb-1"), status_badge(worker["status"])),
                    Div(P("Scope path", cls="small text-muted mb-1"), P(worker.get("path") or "Not available", cls="fw-semibold mb-0")),
                    Div(P("Review note", cls="small text-muted mb-1"), P(worker.get("rejection_reason") or "No review note recorded", cls="fw-semibold mb-0")),
                    cls="drawer-meta-grid",
                ),
                Div(
                    *live_actions,
                    P(live_note, cls="small text-muted mb-0"),
                    cls="d-grid gap-2 mt-3",
                ),
            )
        return await _worker_detail_panel(request, ctx, worker)

    @app.get("/people/workers/{worker_id}/review")
    async def worker_review_confirm(request: Request, worker_id: str, action: str = "approve"):
        ctx = build_context(request)
        if not await PeopleService.live_enabled(request):
            return P("Live worker review is only available in backend mode.", cls="text-muted")
        try:
            worker = await PeopleService.get_worker(request, worker_id)
        except BackendClientError as exc:
            return P(f"Could not load worker right now: {exc}", cls="text-muted")
        if worker is None:
            return P("Worker not found.", cls="text-muted")
        if action == "reject":
            return await _live_people_review_form(
                ctx,
                heading="Reject worker",
                subtitle=f"{worker['name']} will be marked as rejected until a fresh registration is made.",
                post_url=ctx.url_for(f"/people/workers/{worker_id}/review"),
                action="reject",
                submit_label="Reject worker",
                require_reason=True,
            )
        return await _live_people_review_form(
            ctx,
            heading="Approve worker",
            subtitle=f"{worker['name']} will become an approved worker.",
            post_url=ctx.url_for(f"/people/workers/{worker_id}/review"),
            action="approve",
            submit_label="Approve worker",
        )

    @app.post("/people/workers/{worker_id}/review")
    async def worker_review_action(request: Request, worker_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        action = data.get("action", "approve")
        try:
            worker = (
                await PeopleService.reject_worker(request, worker_id, data.get("reason", "").strip())
                if action == "reject"
                else await PeopleService.approve_worker(request, worker_id)
            )
        except BackendClientError as exc:
            return P(f"Could not save this worker review right now: {exc}", cls="text-muted")
        if worker is None:
            return P("Worker not found.", cls="text-muted")
        refreshed = await _workers_table(request, ctx, oob=True)
        title = "Worker rejected" if action == "reject" else "Worker approved"
        message = "Worker review saved."
        body = (
            f"{worker['name']} is now marked as rejected."
            if action == "reject"
            else f"{worker['name']} is now approved and active."
        )
        variant = "warning" if action == "reject" else "success"
        return simple_toast_response(
            content=(Div(H3(title, cls="h5 fw-semibold"), P(body, cls="mb-0")), refreshed),
            message=message,
            variant=variant,
        )

    @app.get("/people/workers/{worker_id}/account")
    async def worker_account_drawer(request: Request, worker_id: str):
        ctx = build_context(request)
        if await PeopleService.live_enabled(request):
            try:
                worker = await PeopleService.get_worker(request, worker_id)
                live_roles = await PeopleService.list_assignable_roles(request)
                existing_user = await PeopleService.get_user_by_worker(request, ctx, worker_id)
            except BackendClientError as exc:
                return P(f"Could not load this account form right now: {exc}", cls="text-muted")
            if worker is None:
                return P("Worker not found.", cls="text-muted")
            if existing_user is not None:
                return Div(
                    H3("App account already exists", cls="h5 fw-semibold"),
                    P(f"{worker['name']} already has an app account.", cls="text-muted"),
                    Button(
                        "Open app account",
                        variant="outline-primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#detail-drawer",
                        hx_get=ctx.url_for(f"/people/users/{existing_user['account_id']}/drawer"),
                        hx_target="#detail-drawer-body",
                        hx_swap="innerHTML",
                        cls="w-100",
                    ),
                )
            return Form(
                *hidden_context_inputs(ctx),
                H3("Create app account", cls="h5 fw-semibold"),
                P(f"Create a backend user account for {worker['name']} using the worker's registered email address.", cls="text-muted"),
                Input(type="hidden", name="worker_id", value=worker["worker_id"]),
                Input(type="text", name="name", value=worker["name"], cls="form-control mb-3", readonly=True),
                Input(type="email", name="email_preview", value=worker.get("email") or "", cls="form-control mb-3", readonly=True),
                _live_role_selects(live_roles),
                Input(type="password", name="password", placeholder="Temporary password", cls="form-control mb-3", minlength="8", required=True),
                Button("Create user", variant="primary", type="submit", cls="w-100"),
                hx_post=ctx.url_for("/people/users/create"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            )
        worker = STORE.get_worker(worker_id)
        if worker is None:
            return P("Worker not found.", cls="text-muted")
        existing_user = STORE.get_user_by_worker(worker_id)
        if existing_user is not None:
            return Div(
                H3("App account already exists", cls="h5 fw-semibold"),
                P(f"{worker['name']} already has an app account.", cls="text-muted"),
                Button(
                    "Open app account",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/people/users/{existing_user['account_id']}/drawer"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                    cls="w-100",
                ),
            )
        return Form(
            *hidden_context_inputs(ctx),
            H3("Create app account", cls="h5 fw-semibold"),
            P(f"Start access from the worker record so the linked account stays easy to track for {worker['name']}.", cls="text-muted"),
            Input(type="hidden", name="worker_id", value=worker["worker_id"]),
            Input(type="text", name="name", value=worker["name"], cls="form-control mb-3", readonly=True),
            Div(
                Input(type="text", name="phone", value=worker["phone"], cls="form-control", readonly=True),
                Select(
                    *([Option("Select role", value="")] + [Option(role, value=role) for role in ROLE_OPTIONS]),
                    name="role",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Input(type="text", name="location", value=worker["location"], cls="form-control mb-3", readonly=True),
            Button("Create user", variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/people/users/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.get("/people/workers/{worker_id}/suspend")
    async def suspend_worker_confirm(request: Request, worker_id: str):
        ctx = build_context(request)
        worker = STORE.get_worker(worker_id)
        if worker is None:
            return P("Worker not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            H3("Suspend worker", cls="h5 fw-semibold"),
            P(worker["name"], cls="text-muted"),
            Textarea(name="note", placeholder="Add a short reason for the suspension record", cls="form-control mb-3", rows="4"),
            Button("Suspend worker", variant="danger", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/people/workers/{worker_id}/suspend"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/workers/{worker_id}/suspend")
    async def suspend_worker(request: Request, worker_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        worker = STORE.suspend_worker(worker_id, actor_name=ctx.profile.user_name, note=data.get("note", ""))
        if worker is None:
            return P("Worker not found.", cls="text-muted")
        refreshed = await _workers_table(request, ctx, oob=True)
        return simple_toast_response(
            content=(
                Div(H3("Worker suspended", cls="h5 fw-semibold"), P(f"{worker['name']} is now marked as suspended.", cls="mb-0")),
                refreshed,
            ),
            message="Worker suspended.",
            variant="warning",
        )

    @app.get("/people/workers/{worker_id}/removal")
    async def worker_removal_drawer(request: Request, worker_id: str):
        ctx = build_context(request)
        try:
            worker = await PeopleService.get_worker(request, worker_id) if await PeopleService.live_enabled(request) else STORE.get_worker(worker_id)
        except BackendClientError as exc:
            return P(f"Could not load worker right now: {exc}", cls="text-muted")
        if worker is None:
            return P("Worker not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            H3("Request worker removal", cls="h5 fw-semibold"),
            P(f"{worker['name']} - {worker['unit']} - {worker['location']}", cls="text-muted"),
            Input(type="hidden", name="worker_id", value=worker_id),
            Input(type="hidden", name="request_type", value="removal_request"),
            Textarea(name="reason", placeholder="State clearly why this worker should be removed", cls="form-control mb-3", rows="5", required=True),
            Button("Submit request", variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/people/workers/{worker_id}/removal"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/workers/{worker_id}/removal")
    async def create_worker_removal_request(request: Request, worker_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        try:
            request_row = (
                await WorkflowService.create_request(
                    request,
                    ctx,
                    request_type="removal_request",
                    worker_id=worker_id,
                    reason=data.get("reason", "").strip(),
                )
                if await PeopleService.live_enabled(request)
                else STORE.add_request({**data, "worker_id": worker_id, "request_type": "removal_request"}, requester_name=ctx.profile.user_name)
            )
        except BackendClientError as exc:
            return P(f"Could not submit this removal request right now: {exc}", cls="text-muted")
        return simple_toast_response(
            content=Div(H3("Removal request submitted", cls="h5 fw-semibold"), P(f"Removal request for {request_row['worker_name']} is now in the workflow queue.", cls="mb-0")),
            message="Removal request submitted.",
            variant="success",
        )

    @app.get("/people/workers/{worker_id}/transfer")
    async def worker_transfer_drawer(request: Request, worker_id: str):
        ctx = build_context(request)
        try:
            worker = await PeopleService.get_worker(request, worker_id) if await PeopleService.live_enabled(request) else STORE.get_worker(worker_id)
        except BackendClientError as exc:
            return P(f"Could not load worker right now: {exc}", cls="text-muted")
        if worker is None:
            return P("Worker not found.", cls="text-muted")
        destination_locations = (
            [row for row in await PeopleService.list_locations(request, ctx) if row["location_id"] != worker.get("location_id")]
            if await PeopleService.live_enabled(request)
            else [{"location_id": row["location"], "location_name": row["location"]} for row in STORE.visible_locations(ctx.current_scope_path) if row["location"] != worker["location"]]
        )
        if not destination_locations:
            return P("No other destination locations are available.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            H3("Create transfer request", cls="h5 fw-semibold"),
            P(f"{worker['name']} - {worker['unit']} - {worker['location']}", cls="text-muted"),
            Input(type="hidden", name="worker_id", value=worker_id),
            Input(type="hidden", name="request_type", value="transfer_request"),
            Select(
                Option("Select destination location", value=""),
                *[Option(row["location_name"], value=row["location_id"]) for row in destination_locations],
                name="destination_location",
                cls="form-select mb-3",
                required=True,
            ),
            Textarea(name="reason", placeholder="Explain why this transfer is needed", cls="form-control mb-3", rows="5", required=True),
            Button("Submit transfer", variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/people/workers/{worker_id}/transfer"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/workers/{worker_id}/transfer")
    async def create_worker_transfer_request(request: Request, worker_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        try:
            request_row = (
                await WorkflowService.create_request(
                    request,
                    ctx,
                    request_type="transfer_request",
                    worker_id=worker_id,
                    reason=data.get("reason", "").strip(),
                    destination_location_id=data.get("destination_location", "").strip(),
                )
                if await PeopleService.live_enabled(request)
                else STORE.add_request({**data, "worker_id": worker_id, "request_type": "transfer_request"}, requester_name=ctx.profile.user_name)
            )
        except BackendClientError as exc:
            return P(f"Could not submit this transfer request right now: {exc}", cls="text-muted")
        return simple_toast_response(
            content=Div(H3("Transfer request submitted", cls="h5 fw-semibold"), P(f"Transfer request for {request_row['worker_name']} is now in the workflow queue.", cls="mb-0")),
            message="Transfer request submitted.",
            variant="success",
        )

    @app.get("/people/workers/{worker_id}/status-change")
    async def worker_status_change_drawer(request: Request, worker_id: str):
        ctx = build_context(request)
        try:
            worker = await PeopleService.get_worker(request, worker_id) if await PeopleService.live_enabled(request) else STORE.get_worker(worker_id)
        except BackendClientError as exc:
            return P(f"Could not load worker right now: {exc}", cls="text-muted")
        if worker is None:
            return P("Worker not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            H3("Create status change request", cls="h5 fw-semibold"),
            P(f"{worker['name']} - {worker['unit']} - {worker['location']}", cls="text-muted"),
            Input(type="hidden", name="worker_id", value=worker_id),
            Input(type="hidden", name="request_type", value="status_change"),
            Select(
                Option("Select new status", value=""),
                *[Option(status, value=status) for status in WORKER_STATUS_REQUEST_OPTIONS if status != worker["status"]],
                name="new_status",
                cls="form-select mb-3",
                required=True,
            ),
            Textarea(name="reason", placeholder="Explain why this status should change", cls="form-control mb-3", rows="5", required=True),
            Button("Submit status change", variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/people/workers/{worker_id}/status-change"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/workers/{worker_id}/status-change")
    async def create_worker_status_change_request(request: Request, worker_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        try:
            request_row = (
                await WorkflowService.create_request(
                    request,
                    ctx,
                    request_type="status_change",
                    worker_id=worker_id,
                    reason=data.get("reason", "").strip(),
                    new_status=data.get("new_status", "").strip(),
                )
                if await PeopleService.live_enabled(request)
                else STORE.add_request({**data, "worker_id": worker_id, "request_type": "status_change"}, requester_name=ctx.profile.user_name)
            )
        except BackendClientError as exc:
            return P(f"Could not submit this status change right now: {exc}", cls="text-muted")
        return simple_toast_response(
            content=Div(H3("Status change submitted", cls="h5 fw-semibold"), P(f"Status change request for {request_row['worker_name']} is now in the workflow queue.", cls="mb-0")),
            message="Status change request submitted.",
            variant="success",
        )

    @app.get("/people/members")
    async def members_page(request: Request, search: str = "", location: str = "", status: str = "", fellowship_id: str = ""):
        ctx = build_context(request)
        locations = await PeopleService.list_locations(request, ctx) if await PeopleService.live_enabled(request) else [row["location"] for row in STORE.visible_locations(ctx.current_scope_path)]
        fellowships = await PeopleService.list_fellowships(request, location_id=location or None) if await PeopleService.live_enabled(request) else STORE.list_fellowships(ctx.current_scope_path, location=location)
        summary = await PeopleService.member_summary(request, ctx) if await PeopleService.live_enabled(request) else STORE.church_member_summary(ctx.current_scope_path)
        filter_form = Form(
            *hidden_context_inputs(ctx),
            _filter_field(
                "Search members",
                "members-filter-search",
                Input(type="search", id="members-filter-search", name="search", value=search, placeholder="Search members", cls="form-control"),
            ),
            _filter_field(
                "Location",
                "members-filter-location",
                Select(
                    *(
                        [Option("All locations", value="")]
                        + (
                            [Option(row["location_name"], value=row["location_id"], selected=row["location_id"] == location) for row in locations]
                            if await PeopleService.live_enabled(request)
                            else [Option(name, value=name, selected=name == location) for name in locations]
                        )
                    ),
                    id="members-filter-location",
                    name="location",
                    cls="form-select",
                ),
            ),
            _filter_field(
                "Fellowship",
                "members-filter-fellowship",
                Select(
                    *([Option("All fellowships", value="")] + [Option(row["name"], value=row["fellowship_id"], selected=row["fellowship_id"] == fellowship_id) for row in fellowships]),
                    id="members-filter-fellowship",
                    name="fellowship_id",
                    cls="form-select",
                ),
            ),
            _filter_field(
                "Member status",
                "members-filter-status",
                Select(
                    Option("All status", value=""),
                    *[Option(value.replace("_", " ").title(), value=value, selected=value == status) for value in MEMBER_STATUS_OPTIONS],
                    id="members-filter-status",
                    name="status",
                    cls="form-select",
                ),
            ),
            hx_get=ctx.url_for("/people/members/list"),
            hx_target="#members-results",
            hx_swap="outerHTML",
            hx_trigger="keyup changed delay:350ms from:input, change from:select",
            cls="admin-filter-grid",
        )
        body = page_stack(
            page_intro(
                "Members",
                "Manage member records and fellowship links.",
                scope_label=ctx.current_scope_label,
                scope_kind=ctx.current_scope_kind,
            ),
            section_card(
                "Member registry",
                f"{summary['total']} members, {summary['active']} active and {summary['fellowships']} fellowships represented.",
                filter_form,
                await _members_table(request, ctx, search=search, location=location, status=status, fellowship_id=fellowship_id),
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="members",
            title="Members",
            subtitle="Church member records.",
            primary_action=primary_button(
                "Add Member",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/people/members/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            content=body,
            show_shell_intro=False,
        )

    @app.get("/people/members/list")
    async def members_list(request: Request, search: str = "", location: str = "", status: str = "", fellowship_id: str = ""):
        ctx = build_context(request)
        return await _members_table(request, ctx, search=search, location=location, status=status, fellowship_id=fellowship_id)

    @app.get("/people/members/new")
    async def new_member_drawer(request: Request):
        ctx = build_context(request)
        live_mode = await PeopleService.live_enabled(request)
        visible_locations = await PeopleService.list_locations(request, ctx) if live_mode else [row["location"] for row in STORE.visible_locations(ctx.current_scope_path)]
        fellowships = await PeopleService.list_fellowships(request) if live_mode else STORE.list_fellowships(ctx.current_scope_path)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Add member", cls="h5 fw-semibold"),
            P("Capture the member first, then connect the record to the right fellowship if needed.", cls="text-muted"),
            Input(type="text", name="name", placeholder="Full name", cls="form-control mb-3", required=True),
            Div(
                Input(type="text", name="phone", placeholder="Phone number", cls="form-control", required=True),
                Input(type="date", name="date_joined", value=TODAY.isoformat(), cls="form-control"),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    Option("Select gender", value=""),
                    Option("Male", value="Male"),
                    Option("Female", value="Female"),
                    name="gender",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select marital status", value=""),
                    *[Option(label, value=label) for label in MARITAL_STATUS_OPTIONS],
                    name="marital_status",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    *(
                        [Option("Select location", value="")]
                        + (
                            [Option(row["location_name"], value=row["location_id"]) for row in visible_locations]
                            if live_mode
                            else [Option(name, value=name) for name in visible_locations]
                        )
                    ),
                    name="location_id" if live_mode else "location",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    *([Option("Assign fellowship later", value="")] + [Option(row["name"], value=row["fellowship_id"]) for row in fellowships]),
                    name="fellowship_id",
                    cls="form-select",
                ),
                cls="drawer-two-up mb-3",
            ),
            Select(
                *[Option(value.replace("_", " ").title(), value=value, selected=value == "active") for value in MEMBER_STATUS_OPTIONS],
                name="status",
                cls="form-select mb-3",
            ),
            Button("Save member", variant="success", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/people/members/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/members/create")
    async def create_member(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        member = (
            await PeopleService.create_member(
                request,
                {
                    "location_id": data.get("location_id") or "",
                    "name": data.get("name") or "",
                    "gender": data.get("gender") or "",
                    "phone": data.get("phone") or None,
                    "marital_status": data.get("marital_status") or None,
                    "member_since": data.get("date_joined") or None,
                    "fellowship_id": data.get("fellowship_id") or None,
                    "status": data.get("status") or "active",
                },
            )
            if await PeopleService.live_enabled(request)
            else STORE.add_church_member(data)
        )
        if member is None:
            return P("Could not save this member right now.", cls="text-muted")
        refreshed = await _members_table(request, ctx, oob=True)
        return simple_toast_response(
            content=(
                Div(
                    H3("Member saved", cls="h5 fw-semibold"),
                    P(f"{member['name']} is now in the member registry.", cls="mb-0"),
                ),
                refreshed,
            ),
            message="Member record saved.",
            variant="success",
        )

    @app.get("/people/members/{member_id}/drawer")
    async def member_drawer(request: Request, member_id: str):
        member = await PeopleService.get_member(request, member_id) if await PeopleService.live_enabled(request) else STORE.get_church_member(member_id)
        if member is None:
            return P("Member not found.", cls="text-muted")
        return Div(
            H3(member["name"], cls="h5 fw-semibold"),
            P(member["location"], cls="text-muted"),
            Div(
                Div(P("Phone", cls="small text-muted mb-1"), P(member["phone"], cls="fw-semibold mb-0")),
                Div(P("Gender", cls="small text-muted mb-1"), P(member["gender"], cls="fw-semibold mb-0")),
                Div(P("Marital status", cls="small text-muted mb-1"), P(member["marital_status"], cls="fw-semibold mb-0")),
                Div(P("Fellowship", cls="small text-muted mb-1"), P(member["fellowship_name"] or "Not assigned", cls="fw-semibold mb-0")),
                Div(P("Status", cls="small text-muted mb-1"), status_badge(member["status"])),
                Div(P("Joined", cls="small text-muted mb-1"), P(member["date_joined"], cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
        )

    @app.get("/people/officials")
    async def officials_page(request: Request, search: str = "", status: str = "", appointed_role: str = ""):
        ctx = build_context(request)
        if ctx.level < 4:
            body = section_card(
                "Officials",
                "Officials and appointments open from Level 4 upward.",
                empty_state("person-check", "Officials unavailable", "This role cannot appoint or revoke officials."),
            )
            return shell_layout(
                ctx,
                request_path=request.url.path,
                active_key="officials",
                title="Officials",
                subtitle="Junior official appointments within your jurisdiction.",
                primary_action=None,
                content=body,
            )

        try:
            summary = await PeopleService.official_appointment_summary(request, ctx)
        except BackendClientError as exc:
            summary = {"total": 0, "active": 0, "revoked": 0, "scopes": 0}
            results = Div(
                empty_state("cloud-slash", "Officials are unavailable", str(exc)),
                id="officials-results",
            )
        else:
            results = await _loading_results(
                "officials-results",
                hx_get=ctx.url_for("/people/officials/list", search=search, status=status, appointed_role=appointed_role),
                message="Loading official appointments.",
            )
        filter_form = Form(
            *hidden_context_inputs(ctx),
            _filter_field(
                "Search officials",
                "officials-filter-search",
                Input(type="search", id="officials-filter-search", name="search", value=search, placeholder="Search officials", cls="form-control"),
            ),
            _filter_field(
                "Appointment status",
                "officials-filter-status",
                Select(
                    Option("All status", value=""),
                    Option("Active", value="active", selected=status == "active"),
                    Option("Revoked", value="revoked", selected=status == "revoked"),
                    id="officials-filter-status",
                    name="status",
                    cls="form-select",
                ),
            ),
            _filter_field(
                "Official role",
                "officials-filter-role",
                Select(
                    Option("All roles", value=""),
                    *[Option(role, value=role, selected=appointed_role == role) for role in OFFICIAL_ROLE_OPTIONS],
                    id="officials-filter-role",
                    name="appointed_role",
                    cls="form-select",
                ),
            ),
            hx_get=ctx.url_for("/people/officials/list"),
            hx_target="#officials-results",
            hx_swap="outerHTML",
            hx_trigger="keyup changed delay:350ms from:input, change from:select",
            cls="admin-filter-grid",
        )
        body = page_stack(
            page_intro(
                "Officials",
                "Appoint and review junior officials.",
                scope_label=ctx.current_scope_label,
                scope_kind=ctx.current_scope_kind,
            ),
            section_card(
                "Officials & appointments",
                "Official appointments and assigned scopes.",
                Div(
                    stat_card("Appointments", str(summary["total"]), "Official appointments", "person-check", tone="primary"),
                    stat_card("Active", str(summary["active"]), "Current appointments in force", "check2-circle", tone="success"),
                    stat_card("Revoked", str(summary["revoked"]), "Appointments no longer active", "x-circle", tone="warning"),
                    stat_card("Scopes", str(summary["scopes"]), "Assigned scopes", "geo-alt", tone="info"),
                    cls="counts-stat-grid",
                ),
                filter_form,
                results,
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="officials",
            title="Officials",
            subtitle="Junior official appointments within your jurisdiction.",
            primary_action=primary_button(
                "Appoint Official",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/people/officials/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            content=body,
            show_shell_intro=False,
        )

    @app.get("/people/officials/list")
    async def officials_list(request: Request, search: str = "", status: str = "", appointed_role: str = ""):
        ctx = build_context(request)
        try:
            return await _officials_table(request, ctx, search=search, status=status, appointed_role=appointed_role)
        except BackendClientError as exc:
            return Div(
                empty_state(
                    "cloud-slash",
                    "Officials are unavailable",
                    str(exc),
                ),
                id="officials-results",
            )

    @app.get("/people/officials/new")
    async def new_official_drawer(request: Request):
        ctx = build_context(request)
        if ctx.level < 4:
            return P("This form is not available at the current level.", cls="text-muted")
        workers = await PeopleService.list_workers(request, ctx, approval="approved")
        scope_options = await _scope_assignment_options(request, ctx)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Appoint official", cls="h5 fw-semibold"),
            P("Choose a worker and assign the official role.", cls="text-muted"),
            Select(
                Option("Select worker", value=""),
                *[Option(f"{worker['name']} - {worker['unit']} - {worker['location']}", value=worker["worker_id"]) for worker in workers],
                name="worker_id",
                cls="form-select mb-3",
                required=True,
            ),
            Div(
                Select(
                    Option("Select appointed role", value=""),
                    *[Option(role, value=role) for role in OFFICIAL_ROLE_OPTIONS],
                    name="appointed_role",
                    cls="form-select",
                    required=True,
                ),
                Input(type="date", name="appointment_date", value=TODAY.isoformat(), cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    *[Option(label, value=label) for label, _path in scope_options],
                    name="assigned_scope",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    *[Option(label, value=path) for label, path in scope_options],
                    name="assigned_scope_path",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Select(
                Option("Active", value="active"),
                Option("Revoked", value="revoked"),
                name="status",
                cls="form-select mb-3",
                required=True,
            ),
            Button("Save appointment", variant="success", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/people/officials/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/officials/create")
    async def create_official(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        if ctx.level < 4:
            return P("This action is not available at the current level.", cls="text-muted")
        appointment = (
            await PeopleService.create_official_appointment(
                request,
                {
                    "worker_id": data.get("worker_id", ""),
                    "appointed_role": data.get("appointed_role", ""),
                    "assigned_scope_label": data.get("assigned_scope", ""),
                    "assigned_scope_path": data.get("assigned_scope_path", ""),
                    "appointment_date": data.get("appointment_date", ""),
                    "status": data.get("status", "active"),
                    "note": data.get("note") or None,
                },
            )
            if await PeopleService.live_enabled(request)
            else STORE.add_official_appointment(data, actor_name=ctx.profile.user_name)
        )
        refreshed = await _officials_table(request, ctx, oob=True)
        return simple_toast_response(
            content=(
                Div(
                    H3("Appointment saved", cls="h5 fw-semibold"),
                    P(f"{appointment['worker_name']} is now assigned as {appointment['appointed_role']}.", cls="mb-0"),
                ),
                refreshed,
            ),
            message="Official appointment saved.",
            variant="success",
        )

    @app.get("/people/officials/{appointment_id}/drawer")
    async def official_drawer(request: Request, appointment_id: str):
        ctx = build_context(request)
        appointment = await PeopleService.get_official_appointment(request, appointment_id)
        if appointment is None:
            return P("Official appointment not found.", cls="text-muted")
        return Div(
            H3(appointment["worker_name"], cls="h5 fw-semibold"),
            P(f"{appointment['appointed_role']} - {appointment['assigned_scope']}", cls="text-muted"),
            Div(
                Div(P("Location", cls="small text-muted mb-1"), P(appointment["location"], cls="fw-semibold mb-0")),
                Div(P("Appointed by", cls="small text-muted mb-1"), P(appointment["appointed_by"], cls="fw-semibold mb-0")),
                Div(P("Date", cls="small text-muted mb-1"), P(appointment["appointment_date"], cls="fw-semibold mb-0")),
                Div(P("Status", cls="small text-muted mb-1"), status_badge(appointment["status"])),
                cls="drawer-meta-grid",
            ),
            Div(
                Button(
                    "Edit appointment",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#form-drawer",
                    hx_get=ctx.url_for(f"/people/officials/{appointment_id}/edit"),
                    hx_target="#form-drawer-body",
                    hx_swap="innerHTML",
                    cls="w-100",
                ),
                Button(
                    "Revoke appointment",
                    variant="outline-danger",
                    size="md",
                    data_bs_toggle="modal",
                    data_bs_target="#confirm-modal",
                    hx_get=ctx.url_for(f"/people/officials/{appointment_id}/revoke"),
                    hx_target="#confirm-modal-body",
                    hx_swap="innerHTML",
                    cls="w-100",
                ),
                cls="d-grid gap-2 mt-3",
            ),
        )

    @app.get("/people/officials/{appointment_id}/edit")
    async def edit_official_drawer(request: Request, appointment_id: str):
        ctx = build_context(request)
        appointment = await PeopleService.get_official_appointment(request, appointment_id)
        if appointment is None:
            return P("Official appointment not found.", cls="text-muted")
        scope_options = await _scope_assignment_options(request, ctx)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Edit appointment", cls="h5 fw-semibold"),
            P("Adjust the role, scope, or status without recreating the appointment.", cls="text-muted"),
            Input(type="text", value=appointment["worker_name"], cls="form-control mb-3", disabled=True),
            Div(
                Select(
                    *[Option(role, value=role, selected=role == appointment["appointed_role"]) for role in OFFICIAL_ROLE_OPTIONS],
                    name="appointed_role",
                    cls="form-select",
                    required=True,
                ),
                Input(type="date", name="appointment_date", value=appointment["appointment_date"], cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    *[Option(label, value=label, selected=label == appointment["assigned_scope"]) for label, _path in scope_options],
                    name="assigned_scope",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    *[Option(label, value=path, selected=path == appointment["assigned_scope_path"]) for label, path in scope_options],
                    name="assigned_scope_path",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Select(
                Option("Active", value="active", selected=appointment["status"] == "active"),
                Option("Revoked", value="revoked", selected=appointment["status"] == "revoked"),
                name="status",
                cls="form-select mb-3",
                required=True,
            ),
            Button("Save changes", variant="success", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/people/officials/{appointment_id}/update"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/officials/{appointment_id}/update")
    async def update_official(request: Request, appointment_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        appointment = (
            await PeopleService.update_official_appointment(
                request,
                appointment_id,
                {
                    "appointed_role": data.get("appointed_role", ""),
                    "assigned_scope_label": data.get("assigned_scope", ""),
                    "assigned_scope_path": data.get("assigned_scope_path", ""),
                    "appointment_date": data.get("appointment_date", ""),
                    "status": data.get("status", "active"),
                    "note": data.get("note") or None,
                },
            )
            if await PeopleService.live_enabled(request)
            else STORE.update_official_appointment(appointment_id, data, actor_name=ctx.profile.user_name)
        )
        if appointment is None:
            return P("Official appointment not found.", cls="text-muted")
        refreshed = await _officials_table(request, ctx, oob=True)
        return simple_toast_response(
            content=(
                Div(H3("Appointment updated", cls="h5 fw-semibold"), P(f"{appointment['worker_name']}'s appointment was updated.", cls="mb-0")),
                refreshed,
            ),
            message="Official appointment updated.",
            variant="success",
        )

    @app.get("/people/officials/{appointment_id}/revoke")
    async def revoke_official_confirm(request: Request, appointment_id: str):
        ctx = build_context(request)
        appointment = await PeopleService.get_official_appointment(request, appointment_id)
        if appointment is None:
            return P("Official appointment not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            H3("Revoke appointment", cls="h5 fw-semibold"),
            P(f"{appointment['worker_name']} - {appointment['appointed_role']}", cls="text-muted"),
            Textarea(name="note", placeholder="Add a short reason for the record", cls="form-control mb-3", rows="4"),
            Button("Confirm revoke", variant="danger", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/people/officials/{appointment_id}/revoke"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/officials/{appointment_id}/revoke")
    async def revoke_official(request: Request, appointment_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        appointment = (
            await PeopleService.revoke_official_appointment(request, appointment_id, note=data.get("note", ""))
            if await PeopleService.live_enabled(request)
            else STORE.revoke_official_appointment(appointment_id, actor_name=ctx.profile.user_name, note=data.get("note", ""))
        )
        if appointment is None:
            return P("Official appointment not found.", cls="text-muted")
        refreshed = await _officials_table(request, ctx, oob=True)
        return simple_toast_response(
            content=(
                Div(H3("Appointment revoked", cls="h5 fw-semibold"), P(f"{appointment['worker_name']}'s appointment is now revoked.", cls="mb-0")),
                refreshed,
            ),
            message="Official appointment revoked.",
            variant="warning",
        )

    @app.get("/people/users")
    async def users_page(request: Request, search: str = "", approval: str = "", status: str = ""):
        ctx = build_context(request)
        users_results = await _loading_results(
            "users-results",
            hx_get=ctx.url_for("/people/users/list", search=search, approval=approval, status=status),
            message="Loading app users.",
        )
        filter_form = Form(
            *hidden_context_inputs(ctx),
            _filter_field(
                "Search users",
                "users-filter-search",
                Input(type="search", id="users-filter-search", name="search", value=search, placeholder="Search users", cls="form-control"),
            ),
            _filter_field(
                "Approval status",
                "users-filter-approval",
                Select(
                    Option("All approvals", value=""),
                    Option("Approved", value="approved", selected=approval == "approved"),
                    Option("Pending", value="pending", selected=approval == "pending"),
                    id="users-filter-approval",
                    name="approval",
                    cls="form-select",
                ),
            ),
            _filter_field(
                "User status",
                "users-filter-status",
                Select(
                    Option("All status", value=""),
                    Option("Active", value="active", selected=status == "active"),
                    Option("Inactive", value="inactive", selected=status == "inactive"),
                    Option("Suspended", value="suspended", selected=status == "suspended"),
                    id="users-filter-status",
                    name="status",
                    cls="form-select",
                ),
            ),
            hx_get=ctx.url_for("/people/users/list"),
            hx_target="#users-results",
            hx_swap="outerHTML",
            hx_trigger="keyup changed delay:350ms from:input, change from:select",
            cls="admin-filter-grid",
        )
        body = page_stack(
            page_intro(
                "App Users",
                "Manage user access, approvals, and roles.",
                scope_label=ctx.current_scope_label,
                scope_kind=ctx.current_scope_kind,
            ),
            section_card(
                "User accounts",
                "User account directory and access status.",
                filter_form,
                users_results,
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="users",
            title="App Users",
            subtitle="Role-aware access management for approved workers.",
            primary_action=primary_button(
                "Create User",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/people/users/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            content=body,
            show_shell_intro=False,
        )

    @app.get("/people/users/list")
    async def users_list(request: Request, search: str = "", approval: str = "", status: str = ""):
        ctx = build_context(request)
        try:
            return await _users_table(request, ctx, search=search, approval=approval, status=status)
        except BackendClientError as exc:
            return Div(empty_state("cloud-slash", "Live user directory is unavailable", str(exc)), id="users-results")

    @app.get("/people/users/new")
    async def new_user_drawer(request: Request):
        ctx = build_context(request)
        if await PeopleService.live_enabled(request):
            try:
                live_roles = await PeopleService.list_assignable_roles(request)
                live_workers = [row for row in await PeopleService.list_workers(request, ctx) if row.get("approval_status") == "approved"]
                existing_users = {row.get("worker_id") for row in await PeopleService.list_users(request, ctx) if row.get("worker_id")}
            except BackendClientError as exc:
                return P(f"Could not load user form right now: {exc}", cls="text-muted")
            worker_options = [row for row in live_workers if row["worker_id"] not in existing_users]
            if not worker_options:
                return P("No approved workers without app accounts are available.", cls="text-muted")
            return Form(
                *hidden_context_inputs(ctx),
                H3("Create user account", cls="h5 fw-semibold"),
                P("Create an app account for an approved worker and assign only roles the backend says you can grant.", cls="text-muted"),
                Select(
                    Option("Select worker", value=""),
                    *[Option(f"{worker['name']} - {worker['location']}", value=worker["worker_id"]) for worker in worker_options],
                    name="worker_id",
                    cls="form-select mb-3",
                    required=True,
                ),
                _live_role_selects(live_roles),
                Input(type="password", name="password", placeholder="Temporary password", cls="form-control mb-3", minlength="8", required=True),
                Button("Save user", variant="primary", type="submit", cls="w-100"),
                hx_post=ctx.url_for("/people/users/create"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            )
        visible_locations = [row["location"] for row in STORE.visible_locations(ctx.current_scope_path)]
        return Form(
            *hidden_context_inputs(ctx),
            H3("Create user account", cls="h5 fw-semibold"),
            P("Keep access creation simple and role-based for pastors and admins.", cls="text-muted"),
            Input(type="text", name="name", placeholder="Full name", cls="form-control mb-3", required=True),
            Div(
                Input(type="text", name="phone", placeholder="Phone number", cls="form-control", required=True),
                Select(
                    *([Option("Select role", value="")] + [Option(role, value=role) for role in ROLE_OPTIONS]),
                    name="role",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Select(
                *([Option("Select location", value="")] + [Option(name, value=name) for name in visible_locations]),
                name="location",
                cls="form-select mb-3",
                required=True,
            ),
            Button("Save user", variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/people/users/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/users/create")
    async def create_user(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        worker_id = data.get("worker_id", "").strip()
        try:
            if await PeopleService.live_enabled(request):
                if not worker_id:
                    return P("Select the linked worker before saving this app account.", cls="text-muted")
                existing_user = await PeopleService.get_user_by_worker(request, ctx, worker_id)
                if existing_user is not None:
                    return simple_toast_response(
                        content=Div(
                            H3("App account already exists", cls="h5 fw-semibold"),
                            P(f"{existing_user['name']} already has a linked app account.", cls="mb-0"),
                        ),
                        message="App account already exists.",
                        variant="info",
                    )
                worker = await PeopleService.get_worker(request, worker_id)
                if worker is None:
                    return P("The selected worker could not be found right now.", cls="text-muted")
                role_ids = []
                for raw_value in [data.get("role_primary", ""), data.get("role_secondary", "")]:
                    cleaned = raw_value.strip()
                    if cleaned and cleaned.isdigit() and int(cleaned) not in role_ids:
                        role_ids.append(int(cleaned))
                user = await PeopleService.create_user(
                    request,
                    {
                        "worker_id": worker_id,
                        "email": worker.get("email") or "",
                        "password": data.get("password", "").strip(),
                        "roles": role_ids,
                    },
                )
            else:
                if worker_id:
                    existing_user = STORE.get_user_by_worker(worker_id)
                    if existing_user is not None:
                        return simple_toast_response(
                            content=Div(
                                H3("App account already exists", cls="h5 fw-semibold"),
                                P(f"{existing_user['name']} already has a linked app account.", cls="mb-0"),
                            ),
                            message="App account already exists.",
                            variant="info",
                        )
                user = STORE.add_user(data)
        except BackendClientError as exc:
            return P(f"Could not save this user account right now: {exc}", cls="text-muted")
        if user is None:
            return P("User could not be created.", cls="text-muted")
        refreshed = await _users_table(request, ctx, oob=True)
        return simple_toast_response(
            content=(
                Div(
                    H3("User request saved", cls="h5 fw-semibold"),
                    P(f"{user['name']} is now waiting for access approval.", cls="mb-0"),
                ),
                refreshed,
            ),
            message="User account request saved.",
            variant="success",
        )

    @app.get("/people/users/{account_id}/drawer")
    async def user_drawer(request: Request, account_id: str):
        ctx = build_context(request)
        try:
            user = await PeopleService.get_user(request, account_id)
        except BackendClientError as exc:
            return P(f"Could not load user right now: {exc}", cls="text-muted")
        if user is None:
            return P("User not found.", cls="text-muted")
        worker = user.get("worker") if await PeopleService.live_enabled(request) else (STORE.get_worker(user["worker_id"]) if user.get("worker_id") else None)
        if await PeopleService.live_enabled(request):
            action_buttons = []
            if user["approval_status"] == "pending":
                action_buttons.extend(
                    [
                        Button(
                            "Approve access",
                            variant="primary",
                            size="md",
                            data_bs_toggle="modal",
                            data_bs_target="#confirm-modal",
                            hx_get=ctx.url_for(f"/people/users/{account_id}/review?action=approve"),
                            hx_target="#confirm-modal-body",
                            hx_swap="innerHTML",
                        ),
                        Button(
                            "Reject access",
                            variant="outline-danger",
                            size="md",
                            data_bs_toggle="modal",
                            data_bs_target="#confirm-modal",
                            hx_get=ctx.url_for(f"/people/users/{account_id}/review?action=reject"),
                            hx_target="#confirm-modal-body",
                            hx_swap="innerHTML",
                        ),
                    ]
                )
            elif user["approval_status"] == "approved":
                action_buttons.append(
                    Button(
                        "Assign roles",
                        variant="primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#form-drawer",
                        hx_get=ctx.url_for(f"/people/users/{account_id}/roles"),
                        hx_target="#form-drawer-body",
                        hx_swap="innerHTML",
                    )
                )
                if user["status"] == "inactive":
                    action_buttons.append(
                        Button(
                            "Reactivate account",
                            variant="outline-primary",
                            size="md",
                            data_bs_toggle="modal",
                            data_bs_target="#confirm-modal",
                            hx_get=ctx.url_for(f"/people/users/{account_id}/reactivate"),
                            hx_target="#confirm-modal-body",
                            hx_swap="innerHTML",
                        )
                    )
                else:
                    action_buttons.append(
                        Button(
                            "Deactivate account",
                            variant="outline-danger",
                            size="md",
                            data_bs_toggle="modal",
                            data_bs_target="#confirm-modal",
                            hx_get=ctx.url_for(f"/people/users/{account_id}/deactivate"),
                            hx_target="#confirm-modal-body",
                            hx_swap="innerHTML",
                        )
                    )
            note = (
                "Approve or reject this request here before the worker starts using the admin tools."
                if user["approval_status"] == "pending"
                else "Live account controls now use the backend role and approval rules."
            )
            return Div(
                H3(user["name"], cls="h5 fw-semibold"),
                P(user["location"], cls="text-muted"),
                Div(
                    Div(P("User Code", cls="small text-muted mb-1"), P(user.get("public_code") or user["phone"], cls="fw-semibold mb-0")),
                    Div(P("Phone", cls="small text-muted mb-1"), P(user["phone"], cls="fw-semibold mb-0")),
                    Div(P("Email", cls="small text-muted mb-1"), P(user.get("email") or "Not available", cls="fw-semibold mb-0")),
                    Div(P("Approval", cls="small text-muted mb-1"), status_badge(user["approval_status"])),
                    Div(P("Status", cls="small text-muted mb-1"), status_badge(user["status"])),
                    Div(P("Roles", cls="small text-muted mb-1"), Div(*[status_badge(role) for role in user["roles"]], cls="d-flex flex-wrap gap-2")),
                    Div(P("Linked worker", cls="small text-muted mb-1"), P(worker["name"] if worker else "No worker linked", cls="fw-semibold mb-0")),
                    Div(P("Review note", cls="small text-muted mb-1"), P(user.get("rejection_reason") or "No review note recorded", cls="fw-semibold mb-0")),
                    cls="drawer-meta-grid",
                ),
                Div(
                    *action_buttons,
                    P(note, cls="small text-muted mb-0"),
                    cls="d-grid gap-2 mt-3",
                ),
            )
        return Div(
            H3(user["name"], cls="h5 fw-semibold"),
            P(user["location"], cls="text-muted"),
            Div(
                Div(P("User Code", cls="small text-muted mb-1"), P(user.get("public_code") or user["phone"], cls="fw-semibold mb-0")),
                Div(P("Phone", cls="small text-muted mb-1"), P(user["phone"], cls="fw-semibold mb-0")),
                Div(P("Approval", cls="small text-muted mb-1"), status_badge(user["approval_status"])),
                Div(P("Status", cls="small text-muted mb-1"), status_badge(user["status"])),
                Div(P("Roles", cls="small text-muted mb-1"), Div(*[status_badge(role) for role in user["roles"]], cls="d-flex flex-wrap gap-2")),
                Div(P("Linked worker", cls="small text-muted mb-1"), P(worker["name"] if worker else "No worker linked", cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            Div(
                Button(
                    "Assign roles",
                    variant="primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#form-drawer",
                    hx_get=ctx.url_for(f"/people/users/{account_id}/roles"),
                    hx_target="#form-drawer-body",
                    hx_swap="innerHTML",
                ),
                Button(
                    "Deactivate account",
                    variant="outline-danger",
                    size="md",
                    data_bs_toggle="modal",
                    data_bs_target="#confirm-modal",
                    hx_get=ctx.url_for(f"/people/users/{account_id}/deactivate"),
                    hx_target="#confirm-modal-body",
                    hx_swap="innerHTML",
                ),
                cls="d-grid gap-2 mt-3",
            ),
        )

    @app.get("/people/users/{account_id}/roles")
    async def assign_user_roles_drawer(request: Request, account_id: str):
        ctx = build_context(request)
        if await PeopleService.live_enabled(request):
            try:
                user = await PeopleService.get_user(request, account_id)
                live_roles = await PeopleService.list_assignable_roles(request)
            except BackendClientError as exc:
                return P(f"Could not load role options right now: {exc}", cls="text-muted")
            if user is None:
                return P("User not found.", cls="text-muted")
            primary_role = str(user["role_ids"][0]) if user.get("role_ids") else ""
            secondary_role = str(user["role_ids"][1]) if len(user.get("role_ids") or []) > 1 else ""
            return Form(
                *hidden_context_inputs(ctx),
                H3("Assign roles", cls="h5 fw-semibold"),
                P(f"Update access for {user['name']} using available roles.", cls="text-muted"),
                Select(
                    *([Option("Select primary role", value="")] + [Option(role["role_name"], value=str(role["id"]), selected=str(role["id"]) == primary_role) for role in live_roles]),
                    name="role_primary",
                    cls="form-select mb-3",
                    required=True,
                ),
                Select(
                    *([Option("No support role", value="")] + [Option(role["role_name"], value=str(role["id"]), selected=str(role["id"]) == secondary_role) for role in live_roles]),
                    name="role_secondary",
                    cls="form-select mb-3",
                ),
                Button("Save roles", variant="primary", type="submit", cls="w-100"),
                hx_post=ctx.url_for(f"/people/users/{account_id}/roles"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            )
        user = STORE.get_user(account_id)
        if user is None:
            return P("User not found.", cls="text-muted")
        role_options = []
        for role in ROLE_OPTIONS + user["roles"]:
            if role not in role_options:
                role_options.append(role)
        primary_role = user["roles"][0] if user["roles"] else ""
        secondary_role = user["roles"][1] if len(user["roles"]) > 1 else ""
        return Form(
            *hidden_context_inputs(ctx),
            H3("Assign roles", cls="h5 fw-semibold"),
            P(f"Update access for {user['name']} and keep the role names plain and easy to understand.", cls="text-muted"),
            Select(
                *([Option("Select primary role", value="")] + [Option(role, value=role, selected=role == primary_role) for role in role_options]),
                name="role_primary",
                cls="form-select mb-3",
                required=True,
            ),
            Select(
                *([Option("No support role", value="")] + [Option(role, value=role, selected=role == secondary_role) for role in role_options]),
                name="role_secondary",
                cls="form-select mb-3",
            ),
            Button("Save roles", variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/people/users/{account_id}/roles"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/users/{account_id}/roles")
    async def assign_user_roles(request: Request, account_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        if await PeopleService.live_enabled(request):
            role_ids = []
            for raw_value in [data.get("role_primary", ""), data.get("role_secondary", "")]:
                cleaned = raw_value.strip()
                if cleaned and cleaned.isdigit() and int(cleaned) not in role_ids:
                    role_ids.append(int(cleaned))
            try:
                user = await PeopleService.update_user_roles(request, account_id, role_ids)
            except BackendClientError as exc:
                return P(f"Could not update user roles right now: {exc}", cls="text-muted")
        else:
            roles = [data.get("role_primary", ""), data.get("role_secondary", "")]
            user = STORE.update_user_roles(account_id, roles, actor_name=ctx.profile.user_name)
        if user is None:
            return P("User not found.", cls="text-muted")
        refreshed = await _users_table(request, ctx, oob=True)
        return simple_toast_response(
            content=(
                Div(
                    H3("Roles updated", cls="h5 fw-semibold"),
                    P(f"{user['name']} now has {', '.join(user['roles'])} access.", cls="mb-0"),
                ),
                refreshed,
            ),
            message="User roles updated.",
            variant="success",
        )

    @app.get("/people/users/{account_id}/review")
    async def user_review_confirm(request: Request, account_id: str, action: str = "approve"):
        ctx = build_context(request)
        if not await PeopleService.live_enabled(request):
            return P("Live user review is only available in backend mode.", cls="text-muted")
        try:
            user = await PeopleService.get_user(request, account_id)
        except BackendClientError as exc:
            return P(f"Could not load user right now: {exc}", cls="text-muted")
        if user is None:
            return P("User not found.", cls="text-muted")
        if action == "reject":
            return await _live_people_review_form(
                ctx,
                heading="Reject access request",
                subtitle=f"{user['name']} will remain without app access until a fresh request is submitted.",
                post_url=ctx.url_for(f"/people/users/{account_id}/review"),
                action="reject",
                submit_label="Reject access",
                require_reason=True,
            )
        return await _live_people_review_form(
            ctx,
            heading="Approve access request",
            subtitle=f"{user['name']} will become an approved app user immediately after this step.",
            post_url=ctx.url_for(f"/people/users/{account_id}/review"),
            action="approve",
            submit_label="Approve access",
        )

    @app.post("/people/users/{account_id}/review")
    async def user_review_action(request: Request, account_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        action = data.get("action", "approve")
        try:
            user = (
                await PeopleService.reject_user(request, account_id, data.get("reason", "").strip())
                if action == "reject"
                else await PeopleService.approve_user(request, account_id)
            )
        except BackendClientError as exc:
            return P(f"Could not save this access review right now: {exc}", cls="text-muted")
        if user is None:
            return P("User not found.", cls="text-muted")
        refreshed = await _users_table(request, ctx, oob=True)
        title = "Access request rejected" if action == "reject" else "Access approved"
        body = (
            f"{user['name']} remains without app access."
            if action == "reject"
            else f"{user['name']} can now sign in with an approved account."
        )
        variant = "warning" if action == "reject" else "success"
        return simple_toast_response(
            content=(Div(H3(title, cls="h5 fw-semibold"), P(body, cls="mb-0")), refreshed),
            message="User review saved.",
            variant=variant,
        )

    @app.get("/people/users/{account_id}/deactivate")
    async def deactivate_user_confirm(request: Request, account_id: str):
        ctx = build_context(request)
        try:
            user = await PeopleService.get_user(request, account_id) if await PeopleService.live_enabled(request) else STORE.get_user(account_id)
        except BackendClientError as exc:
            return P(f"Could not load user right now: {exc}", cls="text-muted")
        if user is None:
            return P("User not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            H3("Deactivate account", cls="h5 fw-semibold"),
            P(user["name"], cls="text-muted"),
            Textarea(name="note", placeholder="Add a short reason for the record", cls="form-control mb-3", rows="4"),
            Button("Deactivate account", variant="danger", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/people/users/{account_id}/deactivate"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/users/{account_id}/deactivate")
    async def deactivate_user(request: Request, account_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        try:
            user = (
                await PeopleService.deactivate_user(request, account_id, data.get("note", "").strip())
                if await PeopleService.live_enabled(request)
                else STORE.deactivate_user(account_id, actor_name=ctx.profile.user_name, note=data.get("note", ""))
            )
        except BackendClientError as exc:
            return P(f"Could not deactivate this account right now: {exc}", cls="text-muted")
        if user is None:
            return P("User not found.", cls="text-muted")
        refreshed = await _users_table(request, ctx, oob=True)
        return simple_toast_response(
            content=(
                Div(
                    H3("Account deactivated", cls="h5 fw-semibold"),
                    P(f"{user['name']}'s access is now inactive.", cls="mb-0"),
                ),
                refreshed,
            ),
            message="User account deactivated.",
            variant="warning",
        )

    @app.get("/people/users/{account_id}/reactivate")
    async def reactivate_user_confirm(request: Request, account_id: str):
        ctx = build_context(request)
        try:
            user = await PeopleService.get_user(request, account_id) if await PeopleService.live_enabled(request) else None
        except BackendClientError as exc:
            return P(f"Could not load user right now: {exc}", cls="text-muted")
        if user is None:
            return P("User not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            H3("Reactivate account", cls="h5 fw-semibold"),
            P(user["name"], cls="text-muted"),
            Button("Reactivate account", variant="primary", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/people/users/{account_id}/reactivate"),
            hx_target="#confirm-modal-body",
            hx_swap="innerHTML",
        )

    @app.post("/people/users/{account_id}/reactivate")
    async def reactivate_user(request: Request, account_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        try:
            user = await PeopleService.reactivate_user(request, account_id)
        except BackendClientError as exc:
            return P(f"Could not reactivate this account right now: {exc}", cls="text-muted")
        if user is None:
            return P("User not found.", cls="text-muted")
        refreshed = await _users_table(request, ctx, oob=True)
        return simple_toast_response(
            content=(
                Div(
                    H3("Account reactivated", cls="h5 fw-semibold"),
                    P(f"{user['name']}'s access is active again.", cls="mb-0"),
                ),
                refreshed,
            ),
            message="User account reactivated.",
            variant="success",
        )
