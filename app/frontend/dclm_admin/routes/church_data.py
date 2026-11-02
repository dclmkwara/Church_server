from __future__ import annotations

import asyncio
import datetime

from fasthtml.common import Div, Form, H3, H4, Input, Option, P, Select, Textarea
from decimal import Decimal, InvalidOperation
from starlette.requests import Request

from faststrap import Badge, Button, PlaceholderCard, Spinner, TabPane, Tabs

from ..backend import BackendClientError
from ..auth_context import build_context
from ..communication import ChurchDataService, PeopleService
from ..communication.count_aggregation import aggregate_count_submissions
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, shell_layout
from ..components.ui import empty_state, filter_field, format_naira, page_intro, page_stack, responsive_table, section_card, stat_card, status_badge
from ..mock_data import STORE, UNITS
from ..source_intake import reject_source_submission, source_intake_notice


FUND_TYPES = ["offering", "tithe"]
PAYMENT_METHODS = ["Cash", "Bank Transfer", "Mobile Money"]
RECORD_STATUSES = ["follow_up_pending", "contacted", "integrated"]
RECORD_GENDERS = ["Male", "Female"]
ATTENDANCE_STATUSES = ["present", "late", "absent", "excused"]

PAYMENT_METHOD_VALUES = {
    "Cash": "cash",
    "Bank Transfer": "bank_transfer",
    "Mobile Money": "mobile_money",
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
        Div(
            Div(
                H3(section_title, cls="h5 fw-semibold mb-1"),
                P(section_note, cls="text-muted mb-0"),
                cls="d-grid gap-1",
            ),
            Div(P(section_note, cls="text-muted mb-0"), cls="d-flex align-items-center gap-2"),
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
        events = await ChurchDataService.list_events(request, ctx)
        if events:
            return [{"value": row["event_id"], "label": row["title"]} for row in events]
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
    sections = row.get("sections") or [row.get("usher_section") or row.get("assignment_id") or "Not specified"]
    return Div(
        H3(row["event_title"], cls="h6 fw-semibold mb-1"),
        P(f"{row['location']} - {row['date']}", cls="text-muted mb-3"),
        P(f"Sections: {', '.join(sections)}", cls="small text-muted mb-2"),
        Div(
            Div(P("Total", cls="small text-muted mb-1"), P(str(row["total"]), cls="fw-semibold mb-0")),
            Div(P("Usher submissions", cls="small text-muted mb-1"), P(str(row.get("submissions", 1)), cls="fw-semibold mb-0")),
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
    summary = await ChurchDataService.count_summary(request, ctx)
    _month = datetime.date.today().strftime("%B")
    _year = datetime.date.today().year
    return _summary_grid(
        [
            ("Latest service attendance", str(summary["latest_total"]), "Sum of all usher sections for the latest event, date, and location", "bar-chart"),
            (f"{_month} attendance", str(summary["monthly_total"]), f"Service totals in {_month} after combining usher sections", "calendar3"),
            ("Locations reporting", str(summary["locations_reporting"]), "Locations with service counts this month", "geo-alt"),
            ("Average service", str(summary["average_total"]), "Average total per event, date, and location", "calculator"),
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

    rows = aggregate_count_submissions(rows)
    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["event_title"],
                row["date"],
                row["location"],
                row["total"],
                Div(P(f"{row['submissions']} usher section(s)", cls="fw-semibold mb-1"), P(", ".join(row["sections"]) or "Section not specified", cls="small text-muted mb-0")),
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
        ["Event", "Date", "Location", "Combined Total", "Sections", "Action"],
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
            status_badge(row.get("status") or "unknown"),
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
            ("Approved this month", format_naira(summary["month_total"]), f"{_month} {_year} · {summary.get('month_approved_count', 0)} entries · event date", "cash-coin"),
            ("Approved this year", format_naira(summary["year_total"]), f"Jan–{_month} {_year} · {summary.get('approved_count', 0)} entries", "piggy-bank"),
            ("Awaiting review", format_naira(summary.get("pending_total", 0)), f"{summary.get('pending_count', 0)} new · {summary.get('corrected_count', 0)} corrected · excluded from approved totals", "hourglass-split"),
            ("Rejected", str(summary.get("rejected_count", 0)), "Rejected entries are excluded from approved totals", "x-circle"),
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
                Div(P(format_naira(row["amount"]), cls="fw-semibold mb-1"), _fund_badge(row["fund_type"]), status_badge(row.get("status") or "unknown")),
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
        ["Event date", "Event", "Location", "Amount / Status", "Method", "Entered By", "Action"],
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
            subtitle="Review service attendance from the data-sourcing app.",
            section_title="Count overview",
            section_note="Recent attendance totals and count records.",
            target_url=ctx.url_for("/church-data/counts/content", location=location, event_title=event_title),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="counts",
            title="Program Counts",
            subtitle="Combined service attendance records.",
            primary_action=None,
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
            source_intake_notice("Service attendance counts"),
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
        return source_intake_notice("Service attendance counts")

    @app.post("/church-data/counts/create")
    async def create_count(request: Request):
        return reject_source_submission()

    @app.get("/church-data/counts/{count_id}/drawer")
    async def count_drawer(request: Request, count_id: str):
        ctx = build_context(request)
        source_rows = await ChurchDataService.list_counts(request, ctx) if await ChurchDataService.live_enabled(request) else STORE.list_counts(ctx.current_scope_path)
        row = next((entry for entry in source_rows if entry["count_id"] == count_id), None)
        if row is None:
            return P("Count not found.", cls="text-muted")
        service_rows = [
            entry for entry in source_rows
            if (entry["event_id"], entry["date"], entry["location_id"])
            == (row["event_id"], row["date"], row["location_id"])
        ]
        category_fields = ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")
        combined = {field: sum(int(entry.get(field) or 0) for entry in service_rows) for field in category_fields}
        return Div(
            H3(row["event_title"], cls="h5 fw-semibold"),
            P(f"{row['location']} - {row['date']}", cls="text-muted"),
            P(f"Combined from {len(service_rows)} usher submission(s)", cls="small text-muted"),
            Div(
                Div(P("Adult male", cls="small text-muted mb-1"), P(str(combined["adult_male"]), cls="fw-semibold mb-0")),
                Div(P("Adult female", cls="small text-muted mb-1"), P(str(combined["adult_female"]), cls="fw-semibold mb-0")),
                Div(P("Youth male", cls="small text-muted mb-1"), P(str(combined["youth_male"]), cls="fw-semibold mb-0")),
                Div(P("Youth female", cls="small text-muted mb-1"), P(str(combined["youth_female"]), cls="fw-semibold mb-0")),
                Div(P("Boys", cls="small text-muted mb-1"), P(str(combined["boys"]), cls="fw-semibold mb-0")),
                Div(P("Girls", cls="small text-muted mb-1"), P(str(combined["girls"]), cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            Div(P("Combined total", cls="small text-muted mb-1"), P(str(sum(combined.values())), cls="display-6 fw-semibold mb-0"), cls="drawer-note-box mt-3"),
            H4("Submissions", cls="h6 fw-semibold mt-4"),
            *[
                Div(
                    P(f"{entry.get('usher_section') or 'Section not specified'} - {entry.get('submitted_by') or 'Submitter unavailable'}", cls="fw-semibold mb-1"),
                    P(f"{entry.get('total', 0)} people | Assignment: {entry.get('assignment_id') or 'Not linked'}", cls="small text-muted mb-1"),
                    P(entry.get("note") or "", cls="small mb-0") if entry.get("note") else "",
                    cls="border rounded p-3 mb-2",
                )
                for entry in service_rows
            ],
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
            primary_action=None,
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
            source_intake_notice("Tithe and offering entries"),
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
        return source_intake_notice("Tithe and offering entries")

    @app.post("/church-data/finance/create")
    async def create_finance(request: Request):
        return reject_source_submission()

    async def _render_finance_drawer(request: Request, entry_id: str):
        ctx = build_context(request)
        try:
            row = await ChurchDataService.get_finance_entry(request, ctx, entry_id)
        except BackendClientError as exc:
            return P(f"Could not load this finance entry right now: {exc}", cls="text-muted")
        if row is None:
            return P("Finance entry not found.", cls="text-muted")
        audit = []
        if ctx.has_permission("offerings:read") and await ChurchDataService.live_enabled(request):
            try:
                audit = await ChurchDataService.finance_audit_history(request, entry_id)
            except BackendClientError as exc:
                return P(f"Finance details loaded, but audit history could not be loaded: {exc}", cls="text-muted")
        review_form = ""
        if row.get("status") in {"pending", "corrected"} and ctx.has_permission("offerings:review"):
            review_form = Form(
                P("A rejection requires a reason of at least 20 characters. The submitter cannot review their own entry.", cls="small text-muted"),
                Textarea(name="note", placeholder="Review note (required for rejection)", cls="form-control", rows="3"),
                Div(
                    Button("Approve", type="submit", name="decision", value="approved", variant="success", size="md"),
                    Button("Reject", type="submit", name="decision", value="rejected", variant="outline-danger", size="md"),
                    cls="d-flex gap-2 mt-2",
                ),
                hx_post=ctx.url_for(f"/church-data/finance/{entry_id}/review"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="border rounded p-3 mt-3",
            )
        correction_form = ""
        if row.get("status") != "reversed" and ctx.has_permission("offerings:update"):
            correction_form = Form(
                H4("Correct entry", cls="h6 fw-semibold"),
                P("Corrections require a reason and return the entry to pending review.", cls="small text-muted"),
                Input(type="number", name="amount", min="0.01", step="0.01", placeholder=f"Amount (current {row['amount']:.2f})", cls="form-control mb-2"),
                Select(Option("Keep fund type", value=""), Option("Offering", value="offering"), Option("Tithe", value="tithe"), cls="form-select mb-2", name="fund_type"),
                Select(Option("Keep payment method", value=""), *[Option(label, value=value) for value, label in (("cash", "Cash"), ("bank_transfer", "Bank Transfer"), ("mobile_money", "Mobile Money"), ("check", "Check"))], cls="form-select mb-2", name="payment_method"),
                Textarea(name="note", placeholder="Replacement submitter note (optional)", cls="form-control mb-2", rows="2"),
                Textarea(name="reason", placeholder="Correction reason (minimum 20 characters)", cls="form-control", rows="3", required=True),
                Button("Submit correction", type="submit", variant="outline-primary", size="md", cls="mt-2"),
                hx_post=ctx.url_for(f"/church-data/finance/{entry_id}/correction"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="border rounded p-3 mt-3",
            )
        reversal_form = ""
        if row.get("status") == "approved" and ctx.has_permission("offerings:update"):
            reversal_form = Form(
                H4("Reverse approved entry", cls="h6 fw-semibold"),
                P("Reversal removes this amount from approved totals and is permanently recorded in the audit history. The original entry is retained.", cls="small text-muted"),
                Textarea(name="reason", placeholder="Reversal reason (minimum 20 characters)", cls="form-control", rows="3", required=True),
                Button("Reverse entry", type="submit", variant="outline-danger", size="md", cls="mt-2"),
                hx_post=ctx.url_for(f"/church-data/finance/{entry_id}/reverse"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="border border-danger-subtle rounded p-3 mt-3",
            )
        return Div(
            H3(row["event_title"], cls="h5 fw-semibold"),
            P(f"{row['location']} - event date {row.get('entry_date') or row['date']}", cls="text-muted"),
            Div(
                P(format_naira(row["amount"]), cls="display-6 fw-semibold mb-2"),
                Div(_fund_badge(row["fund_type"]), _method_badge(row["method"]), status_badge(row.get("status") or "unknown"), cls="d-flex flex-wrap gap-2"),
                cls="drawer-note-box mb-3",
            ),
            Div(
                Div(P("Entered by", cls="small text-muted mb-1"), P(row["submitted_by"], cls="fw-semibold mb-0")),
                Div(P("Entry date / created", cls="small text-muted mb-1"), P(f"{row.get('entry_date') or '—'} / {row.get('created_at') or '—'}", cls="fw-semibold mb-0")),
                Div(P("Reviewed by / at", cls="small text-muted mb-1"), P(f"{row.get('reviewed_by_id') or 'Not reviewed'} / {row.get('reviewed_at') or '—'}", cls="fw-semibold mb-0")),
                Div(P("Review note", cls="small text-muted mb-1"), P(row.get("review_note") or "No review note.", cls="fw-semibold mb-0")),
                Div(P("Submitter note", cls="small text-muted mb-1"), P(row.get("notes") or "No note added.", cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            review_form,
            correction_form,
            reversal_form,
            Div(
                H4("Review and correction history", cls="h6 fw-semibold mt-4"),
                *[
                    Div(
                        P(f"{str(item.get('action') or 'action').replace('_', ' ').title()} · {item.get('created_at') or ''}", cls="fw-semibold mb-1"),
                        P(item.get("reason") or "No reason supplied.", cls="small mb-1"),
                        P(f"Actor: {item.get('actor_id') or 'Unknown'}", cls="small text-muted mb-0"),
                        cls="border rounded p-2 mb-2",
                    )
                    for item in audit
                ] or [P("No review or correction history.", cls="small text-muted")],
            ) if ctx.has_permission("offerings:read") else "",
        )

    @app.get("/church-data/finance/{entry_id}/drawer")
    async def finance_drawer(request: Request, entry_id: str):
        return await _render_finance_drawer(request, entry_id)

    @app.post("/church-data/finance/{entry_id}/review")
    async def finance_review_action(request: Request, entry_id: str):
        ctx = build_context(request)
        if not ctx.has_permission("offerings:review"):
            return P("You do not have permission to review finance entries.", cls="text-danger")
        form = await request.form()
        decision = str(form.get("decision") or "")
        note = str(form.get("note") or "").strip()
        if decision not in {"approved", "rejected"}:
            return P("Choose approve or reject.", cls="text-danger")
        if decision == "rejected" and len(note) < 20:
            return P("A rejection reason must contain at least 20 characters.", cls="text-danger")
        try:
            await ChurchDataService.review_finance(request, entry_id, decision=decision, note=note)
            drawer = await _render_finance_drawer(request, entry_id)
            return simple_toast_response(
                (drawer, await _finance_stats(request, ctx, oob=True), await _finance_table(request, ctx, oob=True)),
                f"Finance entry {decision}.", title="Finance review saved",
            )
        except BackendClientError as exc:
            return P(f"Finance review was not saved: {exc}", cls="text-danger")

    @app.post("/church-data/finance/{entry_id}/correction")
    async def finance_correction_action(request: Request, entry_id: str):
        ctx = build_context(request)
        if not ctx.has_permission("offerings:update"):
            return P("You do not have permission to correct finance entries.", cls="text-danger")
        form = await request.form()
        reason = str(form.get("reason") or "").strip()
        if len(reason) < 20:
            return P("A correction reason must contain at least 20 characters.", cls="text-danger")
        payload = {"reason": reason}
        for field in ("fund_type", "payment_method"):
            value = str(form.get(field) or "").strip()
            if value:
                payload[field] = value
        amount = str(form.get("amount") or "").strip()
        if amount:
            try:
                parsed_amount = Decimal(amount)
            except InvalidOperation:
                return P("Enter a valid amount with no more than two decimal places.", cls="text-danger")
            if parsed_amount <= 0 or parsed_amount.quantize(Decimal("0.01")) != parsed_amount:
                return P("Enter a positive amount with no more than two decimal places.", cls="text-danger")
            payload["amount"] = str(parsed_amount)
        note = str(form.get("note") or "").strip()
        if note:
            payload["note"] = note
        if len(payload) == 1:
            return P("Change at least one finance field before submitting a correction.", cls="text-danger")
        try:
            await ChurchDataService.correct_finance(request, entry_id, payload)
            drawer = await _render_finance_drawer(request, entry_id)
            return simple_toast_response(
                (drawer, await _finance_stats(request, ctx, oob=True), await _finance_table(request, ctx, oob=True)),
                "The corrected entry is pending review.", title="Finance correction saved", variant="warning",
            )
        except BackendClientError as exc:
            return P(f"Finance correction was not saved: {exc}", cls="text-danger")

    @app.post("/church-data/finance/{entry_id}/reverse")
    async def finance_reversal_action(request: Request, entry_id: str):
        ctx = build_context(request)
        if not ctx.has_permission("offerings:update"):
            return P("You do not have permission to reverse finance entries.", cls="text-danger")
        form = await request.form()
        reason = str(form.get("reason") or "").strip()
        if len(reason) < 20:
            return P("A reversal reason must contain at least 20 characters.", cls="text-danger")
        try:
            await ChurchDataService.reverse_finance(request, entry_id, reason)
            drawer = await _render_finance_drawer(request, entry_id)
            return simple_toast_response(
                (drawer, await _finance_stats(request, ctx, oob=True), await _finance_table(request, ctx, oob=True)),
                "The approved amount has been reversed and removed from approved totals.",
                title="Finance entry reversed", variant="warning",
            )
        except BackendClientError as exc:
            return P(f"Finance reversal was not saved: {exc}", cls="text-danger")

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
            primary_action=None,
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
            source_intake_notice("Newcomer and convert registrations"),
            filter_form,
            workspace,
        )

    @app.get("/church-data/newcomers/list")
    async def newcomers_list(request: Request, search: str = "", status: str = "", location: str = "", gender: str = ""):
        ctx = build_context(request)
        return await _records_workspace(request, ctx, search=search, status=status, location=location, gender=gender)

    @app.get("/church-data/newcomers/new")
    async def new_record_form(request: Request):
        return source_intake_notice("Newcomer and convert registrations")

    @app.post("/church-data/newcomers/create")
    async def create_record(request: Request):
        return reject_source_submission()

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
            primary_action=None,
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
            source_intake_notice("Worker and leader attendance"),
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
        return source_intake_notice("Worker and leader attendance")

    @app.post("/church-data/attendance/create")
    async def create_attendance(request: Request):
        return reject_source_submission()

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
