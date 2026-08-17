from __future__ import annotations

import asyncio
import datetime

from fasthtml.common import Div, Form, H3, H4, Input, Option, P, Select, Textarea
from starlette.requests import Request

from faststrap import Badge, Button, PlaceholderCard, Spinner, TabPane, Tabs

from ..backend import BackendClientError
from ..auth_context import build_context
from ..communication import ChurchDataService, PeopleService
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, primary_button, shell_layout
from ..components.ui import empty_state, filter_field, format_naira, page_intro, page_stack, responsive_table, section_card, stat_card, status_badge
from ..mock_data import STORE, TODAY, UNITS


FUND_TYPES = ["offering", "tithe"]
PAYMENT_METHODS = ["Cash", "Bank Transfer", "Mobile Money", "Check"]
RECORD_STATUSES = ["follow_up_pending", "contacted", "integrated"]
RECORD_GENDERS = ["Male", "Female"]
ATTENDANCE_STATUSES = ["present", "late", "absent", "excused"]

PAYMENT_METHOD_VALUES = {
    "Cash": "cash",
    "Bank Transfer": "bank_transfer",
    "Mobile Money": "mobile_money",
    "Check": "check",
}


async def _summary_grid(items, *, grid_id: str, grid_cls: str, oob: bool = False) -> Div:
    attrs = {"id": grid_id, "cls": grid_cls}
    if oob:
        attrs["hx_swap_oob"] = f"outerHTML:#{grid_id}"
    tones = ("primary", "success", "warning", "info", "danger")
    cards = []
    for index, item in enumerate(items):
        label, value, note = item[0], item[1], item[2]
        icon = item[3] if len(item) > 3 else "bar-chart"
        cards.append(stat_card(label, value, note or "", icon, tone=tones[index % len(tones)]))
    return Div(*cards, **attrs)


async def _church_data_loading_shell(
    request: Request,
    ctx,
    *,
    title: str,
    subtitle: str,
    section_title: str,
    section_note: str,
    target_url: str,
) -> Div:
    return page_stack(
        page_intro(
            title,
            subtitle,
            scope_label=ctx.current_scope_label,
            scope_kind=ctx.current_scope_kind,
        ),
        Div(
            Div(
                H3(section_title, cls="h5 fw-semibold mb-1"),
                P(section_note, cls="text-muted mb-0"),
                cls="d-grid gap-1",
            ),
            Div(Spinner(size="sm"), P(section_note, cls="text-muted mb-0"), cls="d-flex align-items-center gap-2"),
            PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
            PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
            id="church-data-page-content",
            hx_get=target_url,
            hx_trigger="load",
            hx_swap="innerHTML",
            cls="d-grid gap-3",
        ),
    )


async def _scope_locations(request: Request, ctx) -> list[dict[str, str]]:
    if await ChurchDataService.live_enabled(request):
        return [{"value": row["location_id"], "label": row["location_name"]} for row in await PeopleService.list_locations(request, ctx)]
    return [{"value": row["location"], "label": row["location"]} for row in STORE.visible_locations(ctx.current_scope_path)]


async def _scope_events(request: Request, ctx) -> list[dict[str, str]]:
    if await ChurchDataService.live_enabled(request):
        return [{"value": row["event_id"], "label": row["title"]} for row in await ChurchDataService.list_events(request, ctx)]
    return [{"value": event["title"], "label": event["title"]} for event in STORE.list_program_events(ctx.current_scope_path)]


async def _fund_badge(fund_type: str):
    return Badge(
        fund_type.replace("_", " ").title(),
        variant="primary" if fund_type == "offering" else "info",
        cls="text-uppercase fw-semibold px-3 py-2",
    )


async def _method_badge(method: str):
    variants = {"Cash": "warning", "Transfer": "success", "POS": "secondary"}
    return Badge(method, variant=variants.get(method, "secondary"), cls="fw-semibold px-3 py-2")


async def _count_mobile_card(ctx, row):
    return Div(
        H3(row["event_title"], cls="h6 fw-semibold mb-1"),
        P(f"{row['location']} - {row['date']}", cls="text-muted mb-3"),
        Div(
            Div(P("Total", cls="small text-muted mb-1"), P(str(row["total"]), cls="fw-semibold mb-0")),
            Div(P("Submitted by", cls="small text-muted mb-1"), P(row["submitted_by"], cls="fw-semibold mb-0")),
            cls="drawer-two-up mb-3",
        ),
        Button(
            "View details",
            variant="outline-primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#detail-drawer",
            hx_get=ctx.url_for(f"/church-data/counts/{row['count_id']}/drawer"),
            hx_target="#detail-drawer-body",
            hx_swap="innerHTML",
            cls="w-100",
        ),
        cls="mobile-count-card",
    )


async def _count_stats(request: Request, ctx, *, oob: bool = False) -> Div:
    summary = await ChurchDataService.count_summary(request, ctx) if await ChurchDataService.live_enabled(request) else STORE.counts_summary(ctx.current_scope_path)
    _month = datetime.date.today().strftime("%B")
    _year = datetime.date.today().year
    return _summary_grid(
        [
            ("Latest total", str(summary["latest_total"]), "Most recent attendance count", "bar-chart"),
            (f"{_month} total", str(summary["monthly_total"]), f"Total records for {_month}", "calendar3"),
            ("Locations reporting", str(summary["locations_reporting"]), "Branches that have submitted", "geo-alt"),
            ("Average record", str(summary["average_total"]), "Typical attendance size", "calculator"),
        ],
        grid_id="counts-stats",
        grid_cls="counts-stat-grid",
        oob=oob,
    )


async def _counts_table(request: Request, ctx, *, location: str = "", event_title: str = "", oob: bool = False) -> Div:
    rows = await ChurchDataService.list_counts(request, ctx, location=location, event_id=event_title) if await ChurchDataService.live_enabled(request) else STORE.list_counts(ctx.current_scope_path, location=location, event_title=event_title)
    if not rows:
        attrs = {"id": "counts-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#counts-results"
        return Div(empty_state("bar-chart", "No count records", "No attendance counts are available."), **attrs)

    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["event_title"],
                row["date"],
                row["location"],
                row["total"],
                row["submitted_by"],
                Button(
                    "View",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/church-data/counts/{row['count_id']}/drawer"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                ),
            ]
        )
        mobile_cards.append(await _count_mobile_card(ctx, row))
    return responsive_table(
        ["Event", "Date", "Location", "Total", "Submitted By", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="counts-results",
        oob="outerHTML:#counts-results" if oob else None,
    )


async def _finance_mobile_card(ctx, row):
    return Div(
        Div(
            H3(format_naira(row["amount"]), cls="h5 fw-semibold mb-1"),
            _fund_badge(row["fund_type"]),
            cls="d-flex align-items-start justify-content-between gap-3 mb-2",
        ),
        P(f"{row['event_title']} - {row['location']}", cls="text-muted mb-2"),
        Div(_method_badge(row["method"]), P(row["date"], cls="small text-muted mb-0"), cls="d-flex flex-wrap gap-2 align-items-center mb-3"),
        Button(
            "View details",
            variant="outline-primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#detail-drawer",
            hx_get=ctx.url_for(f"/church-data/finance/{row['entry_id']}/drawer"),
            hx_target="#detail-drawer-body",
            hx_swap="innerHTML",
            cls="w-100",
        ),
        cls="mobile-count-card",
    )


async def _finance_stats(request: Request, ctx, *, oob: bool = False) -> Div:
    summary = await ChurchDataService.finance_summary(request, ctx) if await ChurchDataService.live_enabled(request) else STORE.finance_summary(ctx.current_scope_path)
    _month = datetime.date.today().strftime("%B")
    _year = datetime.date.today().year
    return _summary_grid(
        [
            ("This month", format_naira(summary["month_total"]), f"Recorded finance entries for {_month}", "cash-coin"),
            ("This year", format_naira(summary["year_total"]), f"All entries in {_year}", "piggy-bank"),
            ("Average entry", format_naira(summary["average_entry"]), "Helps pastors spot unusual values", "calculator"),
            ("Entry count", str(summary["entries"]), "Offerings and tithes combined", "receipt"),
        ],
        grid_id="finance-stats",
        grid_cls="counts-stat-grid",
        oob=oob,
    )


async def _finance_table(request: Request, ctx, *, fund_type: str = "", location: str = "", method: str = "", oob: bool = False) -> Div:
    rows = await ChurchDataService.list_finance(request, ctx, fund_type=fund_type, location=location, method=method) if await ChurchDataService.live_enabled(request) else STORE.list_finance(ctx.current_scope_path, fund_type=fund_type, location=location, method=method)
    if not rows:
        attrs = {"id": "finance-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#finance-results"
        return Div(
            empty_state("cash-stack", "No finance entries", "No offering or tithe records are available."),
            **attrs,
        )

    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["date"],
                row["event_title"],
                row["location"],
                Div(P(format_naira(row["amount"]), cls="fw-semibold mb-1"), _fund_badge(row["fund_type"])),
                _method_badge(row["method"]),
                row["submitted_by"],
                Button(
                    "View",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/church-data/finance/{row['entry_id']}/drawer"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                ),
            ]
        )
        mobile_cards.append(await _finance_mobile_card(ctx, row))
    return responsive_table(
        ["Date", "Event", "Location", "Amount", "Method", "Entered By", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="finance-results",
        oob="outerHTML:#finance-results" if oob else None,
    )


async def _record_mobile_card(ctx, row):
    return Div(
        H3(row["name"], cls="h6 fw-semibold mb-1"),
        P(f"{row['service']} - {row['location']}", cls="text-muted mb-2"),
        Div(status_badge(row["record_type"]), status_badge(row["status"]), cls="d-flex flex-wrap gap-2 mb-2"),
        Div(P(row["phone"], cls="small text-muted mb-0"), P(row["date"], cls="small text-muted mb-0"), cls="d-flex justify-content-between gap-2 mb-3"),
        Button(
            "View details",
            variant="outline-primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#detail-drawer",
            hx_get=ctx.url_for(f"/church-data/newcomers/{row['record_id']}/drawer"),
            hx_target="#detail-drawer-body",
            hx_swap="innerHTML",
            cls="w-100",
        ),
        cls="mobile-worker-card",
    )


async def _record_rows(ctx, rows, *, suffix: str):
    if not rows:
        return empty_state("person-hearts", "No follow-up records here", "Adjust the filters or add a new newcomer record.")

    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["name"],
                row["phone"],
                status_badge(row["record_type"]),
                row.get("gender", "-"),
                row["service"],
                row["location"],
                status_badge(row["status"]),
                row["date"],
                Button(
                    "View",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/church-data/newcomers/{row['record_id']}/drawer"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                ),
            ]
        )
        mobile_cards.append(await _record_mobile_card(ctx, row))
    return responsive_table(
        ["Person", "Phone", "Type", "Gender", "Service", "Location", "Follow-up", "Date", "Action"],
        desktop_rows,
        mobile_cards,
        results_id=f"records-{suffix}",
    )


async def _records_workspace(request: Request, ctx, *, search: str = "", status: str = "", location: str = "", gender: str = "", oob: bool = False):
    all_rows = await ChurchDataService.list_records(
        request,
        ctx,
        search=search,
        status=status,
        location=location,
        gender=gender,
    ) if await ChurchDataService.live_enabled(request) else STORE.list_records(
        ctx.current_scope_path,
        search=search,
        status=status,
        location=location,
        gender=gender,
    )
    newcomer_rows = [row for row in all_rows if row["record_type"] == "newcomer"]
    convert_rows = [row for row in all_rows if row["record_type"] == "convert"]
    attrs = {"id": "records-results"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#records-results"
    return Div(
        Tabs(
            ("records-all", "All", True),
            ("records-newcomers", "Newcomers"),
            ("records-converts", "New Converts"),
            variant="pills",
            cls="mb-3",
        ),
        Div(
            TabPane(_record_rows(ctx, all_rows, suffix="all"), tab_id="records-all", active=True),
            TabPane(_record_rows(ctx, newcomer_rows, suffix="newcomers"), tab_id="records-newcomers"),
            TabPane(_record_rows(ctx, convert_rows, suffix="converts"), tab_id="records-converts"),
            cls="tab-content",
        ),
        **attrs,
    )


async def _attendance_mobile_card(ctx, row):
    return Div(
        H3(row["worker_name"], cls="h6 fw-semibold mb-1"),
        P(f"{row['unit']} - {row['event_title']}", cls="text-muted mb-2"),
        Div(status_badge(row["status"]), P(row["location"], cls="small text-muted mb-0"), cls="d-flex flex-wrap gap-2 align-items-center mb-2"),
        P(row.get("reason") or "No reason added.", cls="small text-muted mb-3"),
        Button(
            "View details",
            variant="outline-primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#detail-drawer",
            hx_get=ctx.url_for(f"/church-data/attendance/{row['attendance_id']}/drawer"),
            hx_target="#detail-drawer-body",
            hx_swap="innerHTML",
            cls="w-100",
        ),
        cls="mobile-worker-card",
    )


async def _attendance_stats(request: Request, ctx, *, oob: bool = False) -> Div:
    summary = await ChurchDataService.attendance_summary(request, ctx) if await ChurchDataService.live_enabled(request) else STORE.attendance_summary(ctx.current_scope_path)
    return _summary_grid(
        [
            ("Expected workers", str(summary["expected"]), "Workers expected for attendance"),
            ("Present", str(summary["present"]), "Marked present for current records"),
            ("Absent", str(summary["absent"]), "Includes confirmed absences"),
            ("Late", str(summary["late"]), "Arrived after duty start"),
            ("Attendance rate", f"{summary['rate']}%", "Present divided by expected workers"),
        ],
        grid_id="attendance-stats",
        grid_cls="counts-stat-grid",
        oob=oob,
    )


async def _attendance_table(
    request: Request,
    ctx,
    *,
    status: str = "",
    location: str = "",
    unit: str = "",
    event_title: str = "",
    oob: bool = False,
) -> Div:
    rows = await ChurchDataService.list_attendance(request, ctx, status=status, location=location, unit=unit, event_id=event_title) if await ChurchDataService.live_enabled(request) else STORE.list_attendance(
        ctx.current_scope_path,
        status=status,
        location=location,
        unit=unit,
        event_title=event_title,
    )
    if not rows:
        attrs = {"id": "attendance-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#attendance-results"
        return Div(
            empty_state("clipboard-check", "No attendance records", "No worker attendance records are available."),
            **attrs,
        )

    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["worker_name"],
                row["unit"],
                Div(P(row["event_title"], cls="fw-semibold mb-1"), P(row["date"], cls="small text-muted mb-0")),
                status_badge(row["status"]),
                row.get("reason") or "-",
                Button(
                    "View",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/church-data/attendance/{row['attendance_id']}/drawer"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                ),
            ]
        )
        mobile_cards.append(await _attendance_mobile_card(ctx, row))
    return responsive_table(
        ["Worker", "Unit", "Date / Event", "Status", "Reason", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="attendance-results",
        oob="outerHTML:#attendance-results" if oob else None,
    )


def register_church_data_routes(app) -> None:
    @app.get("/church-data/counts")
    async def counts_page(request: Request, location: str = "", event_title: str = ""):
        ctx = build_context(request)
        body = await _church_data_loading_shell(
            request,
            ctx,
            title="Program Counts",
            subtitle="Record and review service attendance.",
            section_title="Count overview",
            section_note="Recent attendance totals and count records.",
            target_url=ctx.url_for("/church-data/counts/content", location=location, event_title=event_title),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="counts",
            title="Program Counts",
            subtitle="Service attendance records.",
            primary_action=primary_button(
                "Submit Count",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/church-data/counts/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            content=body,
            show_shell_intro=False,
        )

    @app.get("/church-data/counts/content")
    async def counts_content(request: Request, location: str = "", event_title: str = ""):
        ctx = build_context(request)
        locations, events, stats_div, table_div = await asyncio.gather(
            _scope_locations(request, ctx),
            _scope_events(request, ctx),
            _count_stats(request, ctx),
            _counts_table(request, ctx, location=location, event_title=event_title),
        )
        filter_form = Form(
            *hidden_context_inputs(ctx),
            filter_field(
                "Location",
                Select(
                    Option("All locations", value=""),
                    *[Option(row["label"], value=row["value"], selected=location == row["value"]) for row in locations],
                    name="location",
                    cls="form-select",
                ),
                field_id="counts-location",
            ),
            filter_field(
                "Event",
                Select(
                    Option("All events", value=""),
                    *[Option(row["label"], value=row["value"], selected=event_title == row["value"]) for row in events],
                    name="event_title",
                    cls="form-select",
                ),
                field_id="counts-event",
            ),
            hx_get=ctx.url_for("/church-data/counts/list"),
            hx_target="#counts-results",
            hx_swap="outerHTML",
            hx_trigger="change from:select",
            cls="admin-filter-grid",
        )
        return section_card(
            "Count overview",
            "Recent attendance totals and count records.",
            stats_div,
            filter_form,
            table_div,
        )

    @app.get("/church-data/counts/list")
    async def counts_list(request: Request, location: str = "", event_title: str = ""):
        ctx = build_context(request)
        return await _counts_table(request, ctx, location=location, event_title=event_title)

    @app.get("/church-data/counts/new")
    async def new_count_form(request: Request):
        ctx = build_context(request)
        events = await _scope_events(request, ctx)
        locations = await _scope_locations(request, ctx)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Submit count", cls="h5 fw-semibold"),
            P("Enter the attendance figures for the selected event.", cls="text-muted"),
            Div(
                Select(
                    Option("Select event", value=""),
                    *[Option(row["label"], value=row["value"]) for row in events],
                    name="event_title",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select location", value=""),
                    *[Option(row["label"], value=row["value"]) for row in locations],
                    name="location",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Input(type="date", name="date", value=TODAY.isoformat(), cls="form-control", required=True),
                Input(type="text", name="submitted_by", placeholder="Submitted by", cls="form-control", required=not await ChurchDataService.live_enabled(request), disabled=await ChurchDataService.live_enabled(request)),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Input(type="number", min="0", name="adult_male", placeholder="Adult male", cls="form-control", required=True),
                Input(type="number", min="0", name="adult_female", placeholder="Adult female", cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Input(type="number", min="0", name="youth_male", placeholder="Youth male", cls="form-control", required=True),
                Input(type="number", min="0", name="youth_female", placeholder="Youth female", cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Input(type="number", min="0", name="boys", placeholder="Boys", cls="form-control", required=True),
                Input(type="number", min="0", name="girls", placeholder="Girls", cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Button("Save count", variant="success", size="md", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/church-data/counts/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/church-data/counts/create")
    async def create_count(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        try:
            row = (
                await ChurchDataService.create_count(
                    request,
                    {
                        "event_id": data.get("event_title", "").strip(),
                        "location_id": data.get("location", "").strip(),
                        "adult_male": int(data.get("adult_male", "0") or 0),
                        "adult_female": int(data.get("adult_female", "0") or 0),
                        "youth_male": int(data.get("youth_male", "0") or 0),
                        "youth_female": int(data.get("youth_female", "0") or 0),
                        "boys": int(data.get("boys", "0") or 0),
                        "girls": int(data.get("girls", "0") or 0),
                        "note": data.get("note", "").strip() or None,
                    },
                )
                if await ChurchDataService.live_enabled(request)
                else STORE.add_count(data)
            )
        except BackendClientError as exc:
            return P(f"Could not submit this count right now: {exc}", cls="text-muted")
        if row is None:
            return P("Count could not be submitted.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(
                    H3("Count submitted", cls="h5 fw-semibold"),
                    P(f"{row['event_title']} for {row['location']} now shows a total of {row['total']}.", cls="mb-0"),
                ),
                await _counts_table(request, ctx, oob=True),
                _count_stats(request, ctx, oob=True),
            ),
            message="Count submitted successfully.",
            variant="success",
        )

    @app.get("/church-data/counts/{count_id}/drawer")
    async def count_drawer(request: Request, count_id: str):
        ctx = build_context(request)
        row = next((entry for entry in await ChurchDataService.list_counts(request, ctx) if entry["count_id"] == count_id), None) if await ChurchDataService.live_enabled(request) else STORE.get_count(count_id)
        if row is None:
            return P("Count not found.", cls="text-muted")
        return Div(
            H3(row["event_title"], cls="h5 fw-semibold"),
            P(f"{row['location']} - {row['date']}", cls="text-muted"),
            Div(
                Div(P("Adult male", cls="small text-muted mb-1"), P(str(row["adult_male"]), cls="fw-semibold mb-0")),
                Div(P("Adult female", cls="small text-muted mb-1"), P(str(row["adult_female"]), cls="fw-semibold mb-0")),
                Div(P("Youth male", cls="small text-muted mb-1"), P(str(row["youth_male"]), cls="fw-semibold mb-0")),
                Div(P("Youth female", cls="small text-muted mb-1"), P(str(row["youth_female"]), cls="fw-semibold mb-0")),
                Div(P("Boys", cls="small text-muted mb-1"), P(str(row["boys"]), cls="fw-semibold mb-0")),
                Div(P("Girls", cls="small text-muted mb-1"), P(str(row["girls"]), cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            Div(P("Total", cls="small text-muted mb-1"), P(str(row["total"]), cls="display-6 fw-semibold mb-0"), cls="drawer-note-box mt-3"),
        )

    @app.get("/church-data/finance")
    async def finance_page(request: Request, fund_type: str = "", location: str = "", method: str = ""):
        ctx = build_context(request)
        body = await _church_data_loading_shell(
            request,
            ctx,
            title="Offerings and Tithes",
            subtitle="Record and review finance entries.",
            section_title="Finance overview",
            section_note="Offering, tithe, and payment records.",
            target_url=ctx.url_for("/church-data/finance/content", fund_type=fund_type, location=location, method=method),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="finance",
            title="Offerings and Tithes",
            subtitle="Offering, tithe, and payment records.",
            primary_action=primary_button(
                "Record Entry",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/church-data/finance/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            content=body,
            show_shell_intro=False,
        )

    @app.get("/church-data/finance/content")
    async def finance_content(request: Request, fund_type: str = "", location: str = "", method: str = ""):
        ctx = build_context(request)
        locations, stats, table = await asyncio.gather(
            _scope_locations(request, ctx),
            _finance_stats(request, ctx),
            _finance_table(request, ctx, fund_type=fund_type, location=location, method=method),
        )
        filter_form = Form(
            *hidden_context_inputs(ctx),
            filter_field(
                "Fund type",
                Select(
                    Option("All fund types", value=""),
                    *[Option(name.title(), value=name, selected=fund_type == name) for name in FUND_TYPES],
                    name="fund_type",
                    cls="form-select",
                ),
                field_id="finance-fund-type",
            ),
            filter_field(
                "Payment method",
                Select(
                    Option("All payment methods", value=""),
                    *[Option(name, value=name, selected=method == name) for name in PAYMENT_METHODS],
                    name="method",
                    cls="form-select",
                ),
                field_id="finance-method",
            ),
            filter_field(
                "Location",
                Select(
                    Option("All locations", value=""),
                    *[Option(row["label"], value=row["value"], selected=location == row["value"]) for row in locations],
                    name="location",
                    cls="form-select",
                ),
                field_id="finance-location",
            ),
            hx_get=ctx.url_for("/church-data/finance/list"),
            hx_target="#finance-results",
            hx_swap="outerHTML",
            hx_trigger="change from:select",
            cls="admin-filter-grid",
        )
        return section_card(
            "Finance overview",
            "Offering, tithe, and payment records.",
            stats,
            filter_form,
            table,
        )

    @app.get("/church-data/finance/list")
    async def finance_list(request: Request, fund_type: str = "", location: str = "", method: str = ""):
        ctx = build_context(request)
        return await _finance_table(request, ctx, fund_type=fund_type, location=location, method=method)

    @app.get("/church-data/finance/new")
    async def new_finance_form(request: Request):
        ctx = build_context(request)
        events = await _scope_events(request, ctx)
        locations = await _scope_locations(request, ctx)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Record finance entry", cls="h5 fw-semibold"),
            P("Enter the amount, fund type, and payment details.", cls="text-muted"),
            Div(
                Select(
                    Option("Select fund type", value=""),
                    *[Option(name.title(), value=name) for name in FUND_TYPES],
                    name="fund_type",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select payment method", value=""),
                    *[Option(name, value=name) for name in PAYMENT_METHODS],
                    name="method",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    Option("Select event", value=""),
                    *[Option(row["label"], value=row["value"]) for row in events],
                    name="event_title",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select location", value=""),
                    *[Option(row["label"], value=row["value"]) for row in locations],
                    name="location",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Input(type="date", name="date", value=TODAY.isoformat(), cls="form-control", required=True),
                Input(type="number", min="0", name="amount", placeholder="Amount in naira", cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Input(type="text", name="submitted_by", placeholder="Recorded by", cls="form-control mb-3", required=not await ChurchDataService.live_enabled(request), disabled=await ChurchDataService.live_enabled(request)),
            Textarea(name="notes", placeholder="Optional note for treasury review", cls="form-control mb-3", rows="3"),
            Button("Save entry", variant="success", size="md", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/church-data/finance/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/church-data/finance/create")
    async def create_finance(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        try:
            row = (
                await ChurchDataService.create_finance(
                    request,
                    {
                        "event_id": data.get("event_title", "").strip(),
                        "location_id": data.get("location", "").strip(),
                        "amount": data.get("amount", "").strip(),
                        "payment_method": PAYMENT_METHOD_VALUES.get(data.get("method", "").strip(), "cash"),
                        "fund_type": data.get("fund_type", "").strip() or "offering",
                        "note": data.get("notes", "").strip() or None,
                    },
                )
                if await ChurchDataService.live_enabled(request)
                else STORE.add_finance(data)
            )
        except BackendClientError as exc:
            return P(f"Could not save this finance entry right now: {exc}", cls="text-muted")
        if row is None:
            return P("Finance entry could not be saved.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(
                    H3("Finance entry saved", cls="h5 fw-semibold"),
                    P(
                        f"{row['fund_type'].title()} for {row['location']} was recorded as {format_naira(row['amount'])}.",
                        cls="mb-0",
                    ),
                ),
                await _finance_table(request, ctx, oob=True),
                _finance_stats(request, ctx, oob=True),
            ),
            message="Finance entry saved.",
            variant="success",
        )

    @app.get("/church-data/finance/{entry_id}/drawer")
    async def finance_drawer(request: Request, entry_id: str):
        ctx = build_context(request)
        row = next((entry for entry in await ChurchDataService.list_finance(request, ctx) if entry["entry_id"] == entry_id), None) if await ChurchDataService.live_enabled(request) else STORE.get_finance_entry(entry_id)
        if row is None:
            return P("Finance entry not found.", cls="text-muted")
        return Div(
            H3(row["event_title"], cls="h5 fw-semibold"),
            P(f"{row['location']} - {row['date']}", cls="text-muted"),
            Div(
                P(format_naira(row["amount"]), cls="display-6 fw-semibold mb-2"),
                Div(_fund_badge(row["fund_type"]), _method_badge(row["method"]), cls="d-flex flex-wrap gap-2"),
                cls="drawer-note-box mb-3",
            ),
            Div(
                Div(P("Entered by", cls="small text-muted mb-1"), P(row["submitted_by"], cls="fw-semibold mb-0")),
                Div(P("Notes", cls="small text-muted mb-1"), P(row.get("notes") or "No note added.", cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
        )

    @app.get("/church-data/newcomers")
    async def newcomers_page(request: Request, search: str = "", status: str = "", location: str = "", gender: str = ""):
        ctx = build_context(request)
        body = await _church_data_loading_shell(
            request,
            ctx,
            title="Newcomers and Converts",
            subtitle="Track newcomer and convert follow-up.",
            section_title="Follow-up records",
            section_note="Newcomer and convert records.",
            target_url=ctx.url_for("/church-data/newcomers/content", search=search, status=status, location=location, gender=gender),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="newcomers",
            title="Newcomers and Converts",
            subtitle="Follow-up tracking for people newly attending or newly converted.",
            primary_action=primary_button(
                "Add Record",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/church-data/newcomers/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            content=body,
            show_shell_intro=False,
        )

    @app.get("/church-data/newcomers/content")
    async def newcomers_content(request: Request, search: str = "", status: str = "", location: str = "", gender: str = ""):
        ctx = build_context(request)
        locations, workspace = await asyncio.gather(
            _scope_locations(request, ctx),
            _records_workspace(request, ctx, search=search, status=status, location=location, gender=gender),
        )
        filter_form = Form(
            *hidden_context_inputs(ctx),
            filter_field(
                "Search records",
                Input(
                    type="search",
                    name="search",
                    value=search,
                    placeholder="Search person, phone, service or location",
                    cls="form-control",
                ),
                field_id="records-search",
            ),
            filter_field(
                "Follow-up status",
                Select(
                    Option("All follow-up status", value=""),
                    *[
                        Option(name.replace("_", " ").title(), value=name, selected=status == name)
                        for name in RECORD_STATUSES
                    ],
                    name="status",
                    cls="form-select",
                ),
                field_id="records-status",
            ),
            filter_field(
                "Gender",
                Select(
                    Option("All gender", value=""),
                    *[Option(name, value=name, selected=gender == name) for name in RECORD_GENDERS],
                    name="gender",
                    cls="form-select",
                ),
                field_id="records-gender",
            ),
            filter_field(
                "Location",
                Select(
                    Option("All locations", value=""),
                    *[Option(row["label"], value=row["value"], selected=location == row["value"]) for row in locations],
                    name="location",
                    cls="form-select",
                ),
                field_id="records-location",
            ),
            hx_get=ctx.url_for("/church-data/newcomers/list"),
            hx_target="#records-results",
            hx_swap="outerHTML",
            hx_trigger="keyup changed delay:350ms from:input, change from:select",
            cls="admin-filter-grid",
        )
        return section_card(
            "Follow-up records",
            "Newcomer and convert records.",
            filter_form,
            workspace,
        )

    @app.get("/church-data/newcomers/list")
    async def newcomers_list(request: Request, search: str = "", status: str = "", location: str = "", gender: str = ""):
        ctx = build_context(request)
        return await _records_workspace(request, ctx, search=search, status=status, location=location, gender=gender)

    @app.get("/church-data/newcomers/new")
    async def new_record_form(request: Request):
        ctx = build_context(request)
        events = await _scope_events(request, ctx)
        locations = await _scope_locations(request, ctx)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Add follow-up record", cls="h5 fw-semibold"),
            P("Add the person and follow-up assignment.", cls="text-muted"),
            Div(
                Select(
                    Option("Select type", value=""),
                    Option("Newcomer", value="newcomer"),
                    Option("Convert", value="convert"),
                    name="record_type",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select gender", value=""),
                    *[Option(name, value=name) for name in RECORD_GENDERS],
                    name="gender",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Input(type="text", name="name", placeholder="Full name", cls="form-control", required=True),
                Input(type="text", name="phone", placeholder="Phone number", cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    Option("Select service", value=""),
                    *[Option(row["label"], value=row["value"]) for row in events],
                    name="service",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select location", value=""),
                    *[Option(row["label"], value=row["value"]) for row in locations],
                    name="location",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    Option("Follow-up status", value=""),
                    *[Option(name.replace("_", " ").title(), value=name) for name in RECORD_STATUSES],
                    name="status",
                    cls="form-select",
                    required=True,
                ),
                Input(type="date", name="date", value=TODAY.isoformat(), cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Input(type="text", name="assigned_to", placeholder="Assigned follow-up worker", cls="form-control mb-3", required=True),
            Textarea(name="notes", placeholder="Pastoral note or follow-up plan", cls="form-control mb-3", rows="3"),
            Button("Save record", variant="success", size="md", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/church-data/newcomers/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/church-data/newcomers/create")
    async def create_record(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        if await ChurchDataService.live_enabled(request):
            payload = {
                "event_id": data["service"],
                "location_id": data["location"],
                "record_type": data["record_type"],
                "name": data["name"],
                "gender": data["gender"],
                "phone": data["phone"],
                "details": {
                    "assigned_to": data.get("assigned_to", ""),
                    "follow_up_date": data.get("date", ""),
                },
                "note": data.get("notes", ""),
            }
            row = await ChurchDataService.create_record(request, payload)
        else:
            row = STORE.add_record(data)
        return simple_toast_response(
            content=(
                Div(
                    H3("Follow-up record saved", cls="h5 fw-semibold"),
                    P(f"{row['name']} was added to {row['record_type'].replace('_', ' ')} follow-up.", cls="mb-0"),
                ),
                _records_workspace(request, ctx, oob=True),
            ),
            message="Follow-up record saved.",
            variant="success",
        )

    @app.get("/church-data/newcomers/{record_id}/drawer")
    async def record_drawer(request: Request, record_id: str):
        ctx = build_context(request)
        row = await ChurchDataService.get_record(request, ctx, record_id) if await ChurchDataService.live_enabled(request) else STORE.get_record(record_id)
        if row is None:
            return P("Record not found.", cls="text-muted")
        return Div(
            H3(row["name"], cls="h5 fw-semibold"),
            P(f"{row['service']} - {row['location']}", cls="text-muted"),
            Div(
                Div(P("Phone", cls="small text-muted mb-1"), P(row["phone"], cls="fw-semibold mb-0")),
                Div(P("Type", cls="small text-muted mb-1"), status_badge(row["record_type"])),
                Div(P("Gender", cls="small text-muted mb-1"), P(row.get("gender", "-"), cls="fw-semibold mb-0")),
                Div(P("Follow-up", cls="small text-muted mb-1"), status_badge(row["status"])),
                Div(P("Assigned to", cls="small text-muted mb-1"), P(row["assigned_to"], cls="fw-semibold mb-0")),
                Div(P("Date added", cls="small text-muted mb-1"), P(row["date"], cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            Div(
                H4("Notes", cls="h6 fw-semibold mb-2"),
                P(row.get("notes") or "No note added.", cls="mb-0"),
                cls="drawer-note-box mt-3",
            ),
        )

    @app.get("/church-data/attendance")
    async def attendance_page(
        request: Request,
        status: str = "",
        location: str = "",
        unit: str = "",
        event_title: str = "",
    ):
        ctx = build_context(request)
        body = await _church_data_loading_shell(
            request,
            ctx,
            title="Worker Attendance",
            subtitle="Record and review worker attendance.",
            section_title="Attendance overview",
            section_note="Attendance totals, filters, and records.",
            target_url=ctx.url_for("/church-data/attendance/content", status=status, location=location, unit=unit, event_title=event_title),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="attendance",
            title="Worker Attendance",
            subtitle="Record and review worker attendance by service and location.",
            primary_action=primary_button(
                "Mark Attendance",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/church-data/attendance/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            content=body,
            show_shell_intro=False,
        )

    @app.get("/church-data/attendance/content")
    async def attendance_content(
        request: Request,
        status: str = "",
        location: str = "",
        unit: str = "",
        event_title: str = "",
    ):
        ctx = build_context(request)
        events, locations, stats_div, table_div = await asyncio.gather(
            _scope_events(request, ctx),
            _scope_locations(request, ctx),
            _attendance_stats(request, ctx),
            _attendance_table(request, ctx, status=status, location=location, unit=unit, event_title=event_title),
        )
        filter_form = Form(
            *hidden_context_inputs(ctx),
            filter_field(
                "Attendance status",
                Select(
                    Option("All status", value=""),
                    *[Option(name.title(), value=name, selected=status == name) for name in ATTENDANCE_STATUSES],
                    name="status",
                    cls="form-select",
                ),
                field_id="attendance-status",
            ),
            filter_field(
                "Unit",
                Select(
                    Option("All units", value=""),
                    *[Option(name, value=name, selected=unit == name) for name in UNITS],
                    name="unit",
                    cls="form-select",
                ),
                field_id="attendance-unit",
            ),
            filter_field(
                "Event",
                Select(
                    Option("All events", value=""),
                    *[Option(row["label"], value=row["value"], selected=event_title == row["value"]) for row in events],
                    name="event_title",
                    cls="form-select",
                ),
                field_id="attendance-event",
            ),
            filter_field(
                "Location",
                Select(
                    Option("All locations", value=""),
                    *[Option(row["label"], value=row["value"], selected=location == row["value"]) for row in locations],
                    name="location",
                    cls="form-select",
                ),
                field_id="attendance-location",
            ),
            hx_get=ctx.url_for("/church-data/attendance/list"),
            hx_target="#attendance-results",
            hx_swap="outerHTML",
            hx_trigger="change from:select",
            cls="admin-filter-grid",
        )
        return section_card(
            "Attendance overview",
            "Attendance totals, filters, and records.",
            stats_div,
            filter_form,
            table_div,
        )

    @app.get("/church-data/attendance/list")
    async def attendance_list(
        request: Request,
        status: str = "",
        location: str = "",
        unit: str = "",
        event_title: str = "",
    ):
        ctx = build_context(request)
        return await _attendance_table(request, ctx, status=status, location=location, unit=unit, event_title=event_title)

    @app.get("/church-data/attendance/new")
    async def new_attendance_form(request: Request):
        ctx = build_context(request)
        workers = await PeopleService.list_workers(request, ctx) if await ChurchDataService.live_enabled(request) else STORE.list_workers(ctx.current_scope_path)
        events = await _scope_events(request, ctx)
        locations = await _scope_locations(request, ctx)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Mark attendance", cls="h5 fw-semibold"),
            P("Select the event, worker, and attendance status.", cls="text-muted"),
            Div(
                Select(
                    Option("Select event", value=""),
                    *[Option(row["label"], value=row["value"]) for row in events],
                    name="event_title",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select location", value=""),
                    *[Option(row["label"], value=row["value"]) for row in locations],
                    name="location",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    Option("Select worker", value=""),
                    *[
                        Option(f"{worker['name']} - {worker.get('unit', 'General')}", value=worker["worker_id"])
                        for worker in workers
                    ],
                    name="worker_id",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select status", value=""),
                    *[Option(name.title(), value=name) for name in ATTENDANCE_STATUSES],
                    name="status",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            (
                Div(
                    Input(type="date", name="date", value=TODAY.isoformat(), cls="form-control", required=True),
                    Input(type="text", name="recorded_by", placeholder="Recorded by", cls="form-control", required=True),
                    cls="drawer-two-up mb-3",
                )
                if not await ChurchDataService.live_enabled(request)
                else P("Recorded by the signed-in backend user automatically.", cls="small text-muted mb-3")
            ),
            Textarea(name="reason", placeholder="Reason or quick note", cls="form-control mb-3", rows="3"),
            Button("Save attendance", variant="success", size="md", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/church-data/attendance/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/church-data/attendance/create")
    async def create_attendance(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        if await ChurchDataService.live_enabled(request):
            payload = {
                "event_id": data["event_title"],
                "location_id": data["location"],
                "worker_id": data["worker_id"],
                "status": data["status"],
                "reason": data.get("reason") or None,
                "note": data.get("reason") or None,
            }
            row = await ChurchDataService.create_attendance(request, payload)
        else:
            row = STORE.add_attendance(data)
        return simple_toast_response(
            content=(
                Div(
                    H3("Attendance saved", cls="h5 fw-semibold"),
                    P(f"{row['worker_name']} was marked {row['status']} for {row['event_title']}.", cls="mb-0"),
                ),
                await _attendance_table(request, ctx, oob=True),
                _attendance_stats(request, ctx, oob=True),
            ),
            message="Attendance saved.",
            variant="success",
        )

    @app.get("/church-data/attendance/{attendance_id}/drawer")
    async def attendance_drawer(request: Request, attendance_id: str):
        ctx = build_context(request)
        row = await ChurchDataService.get_attendance_entry(request, ctx, attendance_id) if await ChurchDataService.live_enabled(request) else STORE.get_attendance_entry(attendance_id)
        if row is None:
            return P("Attendance record not found.", cls="text-muted")
        return Div(
            H3(row["worker_name"], cls="h5 fw-semibold"),
            P(f"{row['event_title']} - {row['location']}", cls="text-muted"),
            Div(
                Div(P("Unit", cls="small text-muted mb-1"), P(row["unit"], cls="fw-semibold mb-0")),
                Div(P("Status", cls="small text-muted mb-1"), status_badge(row["status"])),
                Div(P("Date", cls="small text-muted mb-1"), P(row["date"], cls="fw-semibold mb-0")),
                Div(P("Recorded by", cls="small text-muted mb-1"), P(row["recorded_by"], cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            Div(
                H4("Reason", cls="h6 fw-semibold mb-2"),
                P(row.get("reason") or "No reason added.", cls="mb-0"),
                cls="drawer-note-box mt-3",
            ),
        )
