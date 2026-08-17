from __future__ import annotations

import asyncio

from fasthtml.common import A, Div, Form, H3, H4, Input, Option, P, Select, Textarea
from starlette.requests import Request
from faststrap import Button, PlaceholderCard, Spinner

from ..auth_context import build_context
from ..communication import FellowshipService
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, primary_button, shell_layout
from ..components.ui import empty_state, filter_field, format_naira, page_intro, page_stack, responsive_table, section_card, stat_card, status_badge
from ..mock_data import STORE, TODAY, in_scope


WORKSPACE_TABS = [
    ("overview", "Overview"),
    ("members", "Members"),
    ("attendance", "Attendance"),
    ("offerings", "Offerings"),
    ("testimonies", "Testimonies"),
    ("prayers", "Prayer Requests"),
    ("summary", "Attendance Summary"),
]


async def _fellowship_cards(request: Request, ctx, *, search: str = "", location: str = "", status: str = "", oob: bool = False):
    rows = await FellowshipService.list_fellowships(request, ctx, search=search, location=location, status=status) if await FellowshipService.live_enabled(request) else STORE.list_fellowships(ctx.current_scope_path, search=search, location=location, status=status)
    attrs = {"id": "fellowship-results", "cls": "fellowship-grid"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#fellowship-results"
    if not rows:
        return Div(
            empty_state("house-heart", "No fellowships match this filter", "Try another location or clear the search."),
            **attrs,
        )
    cards = []
    for row in rows:
        cards.append(
            A(
                Div(
                    Div(
                        Div(
                            H3(row["name"], cls="h6 fw-semibold mb-1"),
                            P(f"{row['location']} • {row['meeting_day']} {row['meeting_time']}", cls="text-muted mb-0"),
                        ),
                        status_badge(row["status"]),
                        cls="d-flex justify-content-between align-items-start gap-3 mb-3",
                    ),
                    Div(
                        P(f"Leader: {row['leader_name']}", cls="small text-dark mb-1"),
                        P(f"Members: {row['member_count']} active • Last attendance: {row['last_attendance']}", cls="small text-muted mb-1"),
                        P(f"Open prayers: {row['open_prayers']} • Last offering: {format_naira(row['last_offering'])}", cls="small text-muted mb-0"),
                        cls="mb-3",
                    ),
                    P(row["description"], cls="text-muted mb-0"),
                ),
                href=ctx.url_for(f"/fellowship/{row['fellowship_id']}"),
                cls="quick-action h-100",
            )
        )
    return Div(*cards, **attrs)


async def _workspace_tabs(ctx, fellowship_id: str, active_tab: str):
    return Div(
        *[
            A(
                label,
                href=ctx.url_for(f"/fellowship/{fellowship_id}", tab=key),
                cls=f"btn {'btn-primary' if key == active_tab else 'btn-outline-primary'} admin-inline-btn",
                **({"aria_current": "page"} if key == active_tab else {}),
            )
            for key, label in WORKSPACE_TABS
        ],
        cls="workspace-tab-strip mb-4",
    )


async def _member_rows(request: Request, ctx, fellowship_id: str):
    rows = await FellowshipService.list_members(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.list_fellowship_members(fellowship_id)
    if not rows:
        return empty_state("person-vcard", "No members", "No members are connected to this fellowship.")
    desktop_rows = []
    mobile_cards = []
    for member in rows:
        desktop_rows.append(
            [
                Div(P(member["name"], cls="fw-semibold mb-1"), P(member["phone"], cls="small text-muted mb-0")),
                member["gender"],
                member["marital_status"],
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
        mobile_cards.append(
            Div(
                H4(member["name"], cls="h6 fw-semibold mb-1"),
                P(f"{member['phone']} • Joined {member['date_joined']}", cls="text-muted mb-3"),
                Div(status_badge(member["status"]), cls="d-flex flex-wrap gap-2 mb-3"),
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
                cls="mobile-worker-card",
            )
        )
    return responsive_table(
        ["Member", "Gender", "Marital", "Status", "Joined", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="fellowship-panel-table",
    )


async def _attendance_rows(request: Request, fellowship_id: str):
    rows = await FellowshipService.list_attendance(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.list_fellowship_attendance(fellowship_id)
    if not rows:
        return empty_state("clipboard-check", "No attendance records", "No fellowship attendance has been recorded.")
    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["date"],
                row["men"],
                row["women"],
                row["youths"],
                row["children"],
                row["total"],
                row["submitted_by"],
            ]
        )
        mobile_cards.append(
            Div(
                H4(row["date"], cls="h6 fw-semibold mb-1"),
                P(f"Submitted by {row['submitted_by']}", cls="text-muted mb-3"),
                Div(
                    P(f"Men: {row['men']}", cls="small mb-1"),
                    P(f"Women: {row['women']}", cls="small mb-1"),
                    P(f"Youths: {row['youths']}", cls="small mb-1"),
                    P(f"Children: {row['children']}", cls="small mb-1"),
                    P(f"Total: {row['total']}", cls="fw-semibold mb-0"),
                ),
                cls="mobile-worker-card",
            )
        )
    return responsive_table(
        ["Date", "Men", "Women", "Youths", "Children", "Total", "Submitted By"],
        desktop_rows,
        mobile_cards,
        results_id="fellowship-panel-table",
    )


async def _offering_rows(request: Request, fellowship_id: str):
    rows = await FellowshipService.list_offerings(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.list_fellowship_offerings(fellowship_id)
    if not rows:
        return empty_state("cash-stack", "No offerings recorded", "No fellowship offering has been recorded.")
    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["date"],
                format_naira(row["amount"]),
                row["method"],
                row["submitted_by"],
                row["notes"] or "-",
            ]
        )
        mobile_cards.append(
            Div(
                H4(format_naira(row["amount"]), cls="h6 fw-semibold mb-1"),
                P(f"{row['date']} • {row['method']}", cls="text-muted mb-2"),
                P(f"Recorded by {row['submitted_by']}", cls="small text-muted mb-2"),
                P(row["notes"] or "No note added.", cls="small mb-0"),
                cls="mobile-worker-card",
            )
        )
    return responsive_table(
        ["Date", "Amount", "Method", "Submitted By", "Notes"],
        desktop_rows,
        mobile_cards,
        results_id="fellowship-panel-table",
    )


async def _testimony_cards(request: Request, fellowship_id: str):
    rows = await FellowshipService.list_testimonies(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.list_fellowship_testimonies(fellowship_id)
    if not rows:
        return empty_state("chat-heart", "No testimonies recorded", "No fellowship testimony has been recorded.")
    return Div(
        *[
            Div(
                Div(
                    H4(row["member_name"], cls="h6 fw-semibold mb-1"),
                    status_badge(row["status"]),
                    cls="d-flex justify-content-between align-items-start gap-3",
                ),
                P(row["date"], cls="small text-muted mt-2 mb-2"),
                P(row["summary"], cls="mb-0"),
                cls="approval-card",
            )
            for row in rows
        ],
        cls="d-grid gap-3",
    )


async def _prayer_cards(request: Request, fellowship_id: str):
    rows = await FellowshipService.list_prayers(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.list_fellowship_prayers(fellowship_id)
    if not rows:
        return empty_state("heart", "No prayer requests", "No fellowship prayer request has been recorded.")
    return Div(
        *[
            Div(
                Div(
                    H4(row["requester_name"], cls="h6 fw-semibold mb-1"),
                    status_badge(row["status"]),
                    cls="d-flex justify-content-between align-items-start gap-3",
                ),
                P(row["date"], cls="small text-muted mt-2 mb-2"),
                P(row["summary"], cls="mb-0"),
                cls="approval-card",
            )
            for row in rows
        ],
        cls="d-grid gap-3",
    )


async def _summary_rows(request: Request, fellowship_id: str):
    rows = await FellowshipService.list_summaries(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.list_fellowship_summaries(fellowship_id)
    if not rows:
        return empty_state("bar-chart", "No weekly summary", "No fellowship summary has been submitted.")
    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["week_of"],
                row["average_attendance"],
                row["homes_visited"],
                row["newcomers"],
                row["converts"],
                row["submitted_by"],
            ]
        )
        mobile_cards.append(
            Div(
                H4(f"Week of {row['week_of']}", cls="h6 fw-semibold mb-1"),
                P(row["remarks"], cls="text-muted mb-3"),
                P(f"Average attendance: {row['average_attendance']}", cls="small mb-1"),
                P(f"Homes visited: {row['homes_visited']}", cls="small mb-1"),
                P(f"Newcomers: {row['newcomers']} • Converts: {row['converts']}", cls="small mb-1"),
                P(f"Submitted by {row['submitted_by']}", cls="small text-muted mb-0"),
                cls="mobile-worker-card",
            )
        )
    return responsive_table(
        ["Week Of", "Average Attendance", "Homes Visited", "Newcomers", "Converts", "Submitted By"],
        desktop_rows,
        mobile_cards,
        results_id="fellowship-panel-table",
    )


async def _overview_panel(request: Request, ctx, fellowship_id: str, fellowship):
    summary = await FellowshipService.fellowship_detail_summary(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.fellowship_detail_summary(fellowship_id)
    latest_summary = summary["latest_summary"]
    return Div(
        Div(
            stat_card("Members", str(summary["member_count"]), "Connected to this fellowship", "people", tone="primary"),
            stat_card("Last Attendance", str(summary["last_attendance"]), "Most recent meeting total", "clipboard-check", tone="success"),
            stat_card("Last Offering", format_naira(summary["last_offering"]), "Latest recorded fellowship offering", "cash-stack", tone="warning"),
            stat_card("Open Prayers", str(summary["open_prayers"]), "Requests still waiting for follow-up", "heart", tone="danger"),
            cls="counts-stat-grid",
        ),
        section_card(
            "Fellowship leaders",
            "Keep leadership and meeting details simple and visible.",
            Div(
                Div(P("Leader", cls="small text-muted mb-1"), P(fellowship["leader_name"], cls="fw-semibold mb-0")),
                Div(P("Assistant", cls="small text-muted mb-1"), P(fellowship["assistant_name"], cls="fw-semibold mb-0")),
                Div(P("Meeting", cls="small text-muted mb-1"), P(f"{fellowship['meeting_day']} • {fellowship['meeting_time']}", cls="fw-semibold mb-0")),
                Div(P("Next meeting", cls="small text-muted mb-1"), P(fellowship["next_meeting"], cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
        ),
        section_card(
            "Latest weekly note",
            "Simple overview from the most recent fellowship summary.",
            (
                Div(
                    P(f"Week of {latest_summary['week_of']}", cls="small text-muted mb-2"),
                    P(latest_summary["remarks"], cls="mb-2"),
                    P(f"Submitted by {latest_summary['submitted_by']}", cls="small text-muted mb-0"),
                )
                if latest_summary
                else empty_state("bar-chart", "No weekly note", "No weekly summary is available.")
            ),
            action=A("Open member registry", href=ctx.url_for("/people/members"), cls="btn btn-outline-primary admin-inline-btn"),
        ),
    )


async def _workspace_panel(request: Request, ctx, fellowship_id: str, tab: str, *, oob: bool = False):
    fellowship = await FellowshipService.get_fellowship(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.get_fellowship(fellowship_id)
    attrs = {"id": "fellowship-panel"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#fellowship-panel"
    if fellowship is None or (not await FellowshipService.live_enabled(request) and not in_scope(fellowship["path"], ctx.current_scope_path)):
        return Div(empty_state("house-heart", "Fellowship not found", "This fellowship is not available."), **attrs)

    current_tab = next((key for key, _ in WORKSPACE_TABS if key == tab), "overview")
    if current_tab == "overview":
        content = await _overview_panel(request, ctx, fellowship_id, fellowship)
    elif current_tab == "members":
        content = await _member_rows(request, ctx, fellowship_id)
    elif current_tab == "attendance":
        content = await _attendance_rows(request, fellowship_id)
    elif current_tab == "offerings":
        content = await _offering_rows(request, fellowship_id)
    elif current_tab == "testimonies":
        content = await _testimony_cards(request, fellowship_id)
    elif current_tab == "prayers":
        content = await _prayer_cards(request, fellowship_id)
    else:
        content = await _summary_rows(request, fellowship_id)
    return Div(content, **attrs)


def _workspace_primary_action(ctx, fellowship_id: str, tab: str):
    actions = {
        "members": ("Add Member", f"/fellowship/{fellowship_id}/members/new"),
        "offerings": ("Record Offering", f"/fellowship/{fellowship_id}/offerings/new"),
        "testimonies": ("Add Testimony", f"/fellowship/{fellowship_id}/testimonies/new"),
        "prayers": ("Add Prayer Request", f"/fellowship/{fellowship_id}/prayers/new"),
    }
    if tab not in actions:
        return None
    label, path = actions[tab]
    return primary_button(
        label,
        href="#",
        data_bs_toggle="offcanvas",
        data_bs_target="#form-drawer",
        hx_get=ctx.url_for(path, tab=tab),
        hx_target="#form-drawer-body",
        hx_swap="innerHTML",
    )


async def _fellowship_loading_shell(ctx, *, heading: str, message: str, target_path: str, **params: str) -> Div:
    return Div(
        Div(
            H3(heading, cls="h5 fw-semibold mb-3"),
            Div(
                Spinner(variant="primary", size="md", label="Loading fellowship"),
                P(message, cls="text-muted mb-0"),
                cls="d-flex align-items-center gap-3 py-2",
            ),
        ),
        Div(PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"), cls="mb-4"),
        Div(PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"), cls="mb-4"),
        id="fellowship-content",
        hx_get=ctx.url_for(target_path, **params),
        hx_trigger="load",
        hx_swap="innerHTML",
    )


async def _fellowship_page_content(request: Request, ctx, *, search: str = "", location: str = "", status: str = "") -> Div:
    live = await FellowshipService.live_enabled(request)
    locations_coro = FellowshipService.list_fellowships(request, ctx) if live else None
    summary_coro = FellowshipService.fellowship_summary(request, ctx) if live else None
    cards_coro = _fellowship_cards(request, ctx, search=search, location=location, status=status)

    if live:
        raw_locations, summary, cards = await asyncio.gather(locations_coro, summary_coro, cards_coro)
        locations = [row["location_name"] for row in raw_locations]
    else:
        cards = await cards_coro
        locations = [row["location"] for row in STORE.visible_locations(ctx.current_scope_path)]
        summary = STORE.fellowship_summary(ctx.current_scope_path)
    filter_form = Form(
        *hidden_context_inputs(ctx),
        filter_field(
            "Search fellowships",
            Input(type="search", name="search", value=search, placeholder="Search fellowship, leader, or location", cls="form-control"),
            field_id="fellowship-search",
        ),
        filter_field(
            "Location",
            Select(
                *([Option("All locations", value="")] + [Option(name, value=name, selected=name == location) for name in locations]),
                name="location",
                cls="form-select",
            ),
            field_id="fellowship-location",
        ),
        filter_field(
            "Status",
            Select(
                Option("All status", value=""),
                Option("Active", value="active", selected=status == "active"),
                Option("Inactive", value="inactive", selected=status == "inactive"),
                name="status",
                cls="form-select",
            ),
            field_id="fellowship-status",
        ),
        hx_get=ctx.url_for("/fellowship/list"),
        hx_target="#fellowship-results",
        hx_swap="outerHTML",
        hx_trigger="keyup changed delay:350ms from:input, change from:select",
        cls="admin-filter-grid",
    )
    return page_stack(
        page_intro(
            "Fellowship",
            "Fellowship units, members, attendance, offerings, and follow-up.",
            scope_label=ctx.current_scope_label,
            scope_kind=ctx.current_scope_kind,
        ),
        Div(
            stat_card("Fellowships", str(summary["total"]), "Fellowship units in current view", "house-heart", tone="primary"),
            stat_card("Members", str(summary["members"]), "Members connected to fellowships", "people", tone="success"),
            stat_card("Average Attendance", str(summary["average_attendance"]), "Recent fellowship attendance average", "clipboard-check", tone="warning"),
            stat_card("Open Prayers", str(summary["open_prayers"]), "Requests still waiting on follow-up", "heart", tone="danger"),
            cls="counts-stat-grid mb-4",
        ),
        section_card(
            "Fellowships overview",
            "Fellowship units and recent activity.",
            filter_form,
            cards,
        ),
    )


async def _fellowship_workspace_content(request: Request, ctx, fellowship_id: str, tab: str) -> Div:
    fellowship = await FellowshipService.get_fellowship(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.get_fellowship(fellowship_id)
    if fellowship is None or (not await FellowshipService.live_enabled(request) and not in_scope(fellowship["path"], ctx.current_scope_path)):
        return Div(
            A("Back to fellowships", href=ctx.url_for("/fellowship"), cls="btn btn-outline-primary admin-inline-btn mb-3"),
            empty_state("house-heart", "Fellowship not found", "This fellowship is not available."),
        )
    current_tab = next((key for key, _ in WORKSPACE_TABS if key == tab), "overview")
    return page_stack(
        A("Back to fellowships", href=ctx.url_for("/fellowship"), cls="btn btn-outline-primary admin-inline-btn mb-3"),
        page_intro(
            fellowship["name"],
            f"{fellowship['location']} • Led by {fellowship['leader_name']}.",
            scope_label=ctx.current_scope_label,
            scope_kind=ctx.current_scope_kind,
        ),
        _workspace_tabs(ctx, fellowship_id, current_tab),
        await _workspace_panel(request, ctx, fellowship_id, current_tab),
    )


def register_fellowship_routes(app) -> None:
    @app.get("/fellowship")
    async def fellowship_page(request: Request, search: str = "", location: str = "", status: str = ""):
        ctx = build_context(request)
        if await FellowshipService.live_enabled(request):
            body = await _fellowship_loading_shell(
                ctx,
                heading="Fellowships overview",
                message="Loading fellowship records.",
                target_path="/fellowship/content",
                search=search,
                location=location,
                status=status,
            )
        else:
            body = await _fellowship_page_content(request, ctx, search=search, location=location, status=status)
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="fellowship",
            title="Fellowship",
            subtitle="Fellowship records and activity.",
            primary_action=None,
            content=body,
        )

    @app.get("/fellowship/content")
    async def fellowship_content(request: Request, search: str = "", location: str = "", status: str = ""):
        ctx = build_context(request)
        return await _fellowship_page_content(request, ctx, search=search, location=location, status=status)

    @app.get("/fellowship/list")
    async def fellowship_list(request: Request, search: str = "", location: str = "", status: str = ""):
        ctx = build_context(request)
        return await _fellowship_cards(request, ctx, search=search, location=location, status=status)

    @app.get("/fellowship/{fellowship_id}")
    async def fellowship_workspace(request: Request, fellowship_id: str, tab: str = "overview"):
        ctx = build_context(request)
        current_tab = next((key for key, _ in WORKSPACE_TABS if key == tab), "overview")
        fellowship = await FellowshipService.get_fellowship(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.get_fellowship(fellowship_id)
        if fellowship is None or (not await FellowshipService.live_enabled(request) and not in_scope(fellowship["path"], ctx.current_scope_path)):
            return await _fellowship_page_content(request, ctx)
        if await FellowshipService.live_enabled(request):
            body = await _fellowship_loading_shell(
                ctx,
                heading="Fellowship",
                message="Loading fellowship records.",
                target_path=f"/fellowship/{fellowship_id}/content",
                tab=current_tab,
            )
            title = "Fellowship"
        else:
            body = await _fellowship_workspace_content(request, ctx, fellowship_id, current_tab)
            title = fellowship["name"]
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="fellowship",
            title=title,
            subtitle="One selected fellowship with simple internal work areas.",
            primary_action=_workspace_primary_action(ctx, fellowship_id, current_tab),
            content=body,
        )

    @app.get("/fellowship/{fellowship_id}/content")
    async def fellowship_workspace_content(request: Request, fellowship_id: str, tab: str = "overview"):
        ctx = build_context(request)
        return await _fellowship_workspace_content(request, ctx, fellowship_id, tab)

    @app.get("/fellowship/{fellowship_id}/members/new")
    async def new_fellowship_member_form(request: Request, fellowship_id: str, tab: str = "members"):
        ctx = build_context(request)
        fellowship = await FellowshipService.get_fellowship(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.get_fellowship(fellowship_id)
        if fellowship is None:
            return P("Fellowship not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            Input(type="hidden", name="fellowship_id", value=fellowship_id),
            Input(type="hidden", name="location", value=fellowship["location"]),
            H3("Add fellowship member", cls="h5 fw-semibold"),
            P(f"Add a member directly into {fellowship['name']}.", cls="text-muted"),
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
                    Option("Single", value="Single"),
                    Option("Married", value="Married"),
                    Option("Widowed", value="Widowed"),
                    name="marital_status",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Button("Save member", variant="success", type="submit", cls="w-100"),
            hx_post=f"/fellowship/{fellowship_id}/members/create",
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/fellowship/{fellowship_id}/members/create")
    async def create_fellowship_member(request: Request, fellowship_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        member = await FellowshipService.create_member(request, fellowship_id, data) if await FellowshipService.live_enabled(request) else STORE.add_church_member(data)
        return simple_toast_response(
            content=(
                Div(H3("Member saved", cls="h5 fw-semibold"), P(f"{member['name']} has been added to the fellowship.", cls="mb-0")),
                _workspace_panel(request, ctx, fellowship_id, "members", oob=True),
            ),
            message="Fellowship member saved.",
            variant="success",
        )

    @app.get("/fellowship/{fellowship_id}/offerings/new")
    async def new_fellowship_offering_form(request: Request, fellowship_id: str, tab: str = "offerings"):
        ctx = build_context(request)
        fellowship = await FellowshipService.get_fellowship(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.get_fellowship(fellowship_id)
        if fellowship is None:
            return P("Fellowship not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            Input(type="hidden", name="fellowship_id", value=fellowship_id),
            H3("Record fellowship offering", cls="h5 fw-semibold"),
            P(f"Save the latest offering for {fellowship['name']}.", cls="text-muted"),
            Div(
                Input(type="date", name="date", value=TODAY.isoformat(), cls="form-control"),
                Input(type="number", name="amount", placeholder="Amount", cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    Option("Cash", value="Cash"),
                    Option("Transfer", value="Transfer"),
                    name="method",
                    cls="form-select",
                ),
                Input(type="text", name="submitted_by", placeholder="Submitted by", cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Textarea(name="notes", placeholder="Short note", cls="form-control mb-3", rows="3"),
            Button("Save offering", variant="success", type="submit", cls="w-100"),
            hx_post=f"/fellowship/{fellowship_id}/offerings/create",
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/fellowship/{fellowship_id}/offerings/create")
    async def create_fellowship_offering(request: Request, fellowship_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        row = await FellowshipService.create_offering(request, fellowship_id, data) if await FellowshipService.live_enabled(request) else STORE.add_fellowship_offering(data)
        return simple_toast_response(
            content=(
                Div(H3("Offering saved", cls="h5 fw-semibold"), P(f"{format_naira(row['amount'])} has been recorded.", cls="mb-0")),
                _workspace_panel(request, ctx, fellowship_id, "offerings", oob=True),
            ),
            message="Fellowship offering saved.",
            variant="success",
        )

    @app.get("/fellowship/{fellowship_id}/testimonies/new")
    async def new_fellowship_testimony_form(request: Request, fellowship_id: str, tab: str = "testimonies"):
        ctx = build_context(request)
        fellowship = await FellowshipService.get_fellowship(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.get_fellowship(fellowship_id)
        if fellowship is None:
            return P("Fellowship not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            Input(type="hidden", name="fellowship_id", value=fellowship_id),
            H3("Add testimony", cls="h5 fw-semibold"),
            P(f"Record a testimony shared in {fellowship['name']}.", cls="text-muted"),
            Input(type="text", name="member_name", placeholder="Member name", cls="form-control mb-3", required=True),
            Input(type="date", name="date", value=TODAY.isoformat(), cls="form-control mb-3"),
            Textarea(name="summary", placeholder="Short testimony summary", cls="form-control mb-3", rows="4", required=True),
            Button("Save testimony", variant="success", type="submit", cls="w-100"),
            hx_post=f"/fellowship/{fellowship_id}/testimonies/create",
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/fellowship/{fellowship_id}/testimonies/create")
    async def create_fellowship_testimony(request: Request, fellowship_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        row = await FellowshipService.create_testimony(request, fellowship_id, data) if await FellowshipService.live_enabled(request) else STORE.add_fellowship_testimony(data)
        return simple_toast_response(
            content=(
                Div(H3("Testimony saved", cls="h5 fw-semibold"), P(f"Testimony from {row['member_name']} has been added.", cls="mb-0")),
                _workspace_panel(request, ctx, fellowship_id, "testimonies", oob=True),
            ),
            message="Fellowship testimony saved.",
            variant="success",
        )

    @app.get("/fellowship/{fellowship_id}/prayers/new")
    async def new_fellowship_prayer_form(request: Request, fellowship_id: str, tab: str = "prayers"):
        ctx = build_context(request)
        fellowship = await FellowshipService.get_fellowship(request, fellowship_id) if await FellowshipService.live_enabled(request) else STORE.get_fellowship(fellowship_id)
        if fellowship is None:
            return P("Fellowship not found.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            Input(type="hidden", name="fellowship_id", value=fellowship_id),
            H3("Add prayer request", cls="h5 fw-semibold"),
            P(f"Record a prayer burden from {fellowship['name']}.", cls="text-muted"),
            Input(type="text", name="requester_name", placeholder="Requester name", cls="form-control mb-3", required=True),
            Input(type="date", name="date", value=TODAY.isoformat(), cls="form-control mb-3"),
            Textarea(name="summary", placeholder="Prayer request summary", cls="form-control mb-3", rows="4", required=True),
            Button("Save prayer request", variant="success", type="submit", cls="w-100"),
            hx_post=f"/fellowship/{fellowship_id}/prayers/create",
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/fellowship/{fellowship_id}/prayers/create")
    async def create_fellowship_prayer(request: Request, fellowship_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        row = await FellowshipService.create_prayer(request, fellowship_id, data) if await FellowshipService.live_enabled(request) else STORE.add_fellowship_prayer(data)
        return simple_toast_response(
            content=(
                Div(H3("Prayer request saved", cls="h5 fw-semibold"), P(f"Prayer request from {row['requester_name']} has been added.", cls="mb-0")),
                _workspace_panel(request, ctx, fellowship_id, "prayers", oob=True),
            ),
            message="Fellowship prayer request saved.",
            variant="success",
        )
