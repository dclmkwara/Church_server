from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, timedelta
from statistics import pstdev
from typing import Any

from fasthtml.common import A, Div, Form, H3, H4, Input, Label, P
from starlette.requests import Request
from starlette.responses import Response

from faststrap import Button, PlaceholderCard, Spinner

from ..backend import BackendClientError
from ..auth_context import build_context
from ..communication import ReportService
from ..communication.count_aggregation import aggregate_count_submissions
from ..components.chartjs import sparkline_chart as _sparkline
from ..components.feedback import simple_toast_response
from ..components.shell import shell_layout
from ..components.ui import empty_state, format_naira, page_intro, page_stack, responsive_table, section_card, stat_card, status_badge
from ..mock_data import STORE


REPORT_TABS = [
    ("summary", "Summary"),
    ("financial", "Financial"),
    ("attendance", "Attendance"),
    ("timeseries", "Timeseries"),
    ("breakdown", "By Level"),
    ("growth", "Growth"),
    ("anomalies", "Anomalies"),
    ("exports", "Exports"),
]


def _report_window(request: Request) -> tuple[str, str]:
    today = date.today()
    try:
        start = date.fromisoformat(request.query_params.get("start_date", "")) if request.query_params.get("start_date") else today - timedelta(days=90)
        end = date.fromisoformat(request.query_params.get("end_date", "")) if request.query_params.get("end_date") else today
    except ValueError:
        start, end = today - timedelta(days=90), today
    if start > end:
        start, end = today - timedelta(days=90), today
    return start.isoformat(), end.isoformat()


def _trend_label(points: list[tuple[str, int]]) -> str:
    if len(points) < 2:
        return "Stable"
    first = points[0][1]
    last = points[-1][1]
    if last > first:
        return "Upward"
    if last < first:
        return "Downward"
    return "Stable"


async def _summary_rows(request: Request, ctx) -> list[dict[str, Any]]:
    start, end = _report_window(request)
    if await ReportService.live_enabled(request):
        return await ReportService.summary_rows(request, ctx)
    rows = aggregate_count_submissions(STORE.list_counts(ctx.current_scope_path))
    rows = [row for row in rows if start <= str(row.get("date") or "") <= end]
    for row in rows:
        row["submitted_by"] = f"{row['submissions']} usher section(s)"
    return rows


async def _financial_rows(request: Request, ctx) -> list[dict[str, Any]]:
    if await ReportService.live_enabled(request):
        return await ReportService.financial_rows(request, ctx)
    start, end = _report_window(request)
    return [row for row in STORE.list_finance(ctx.current_scope_path) if start <= str(row.get("date") or "")[:10] <= end][:8]


async def _attendance_rows(request: Request, ctx) -> list[dict[str, Any]]:
    if await ReportService.live_enabled(request):
        return await ReportService.attendance_rows(request, ctx)
    start, end = _report_window(request)
    return [row for row in STORE.list_attendance(ctx.current_scope_path) if start <= str(row.get("date") or "")[:10] <= end][:8]


async def _counts_series(request: Request, ctx) -> list[tuple[str, int]]:
    start, end = _report_window(request)
    if await ReportService.live_enabled(request):
        return await ReportService.counts_series(request, ctx)
    bucket: dict[str, int] = defaultdict(int)
    for row in STORE.list_counts(ctx.current_scope_path):
        if start <= row["date"][:10] <= end:
            bucket[row["date"][:10]] += row["total"]
    return sorted(bucket.items())


async def _finance_series(request: Request, ctx) -> list[tuple[str, int]]:
    start, end = _report_window(request)
    if await ReportService.live_enabled(request):
        return await ReportService.finance_series(request, ctx)
    bucket: dict[str, int] = defaultdict(int)
    for row in STORE.list_finance(ctx.current_scope_path):
        if start <= row["date"][:10] <= end:
            bucket[row["date"][:10]] += int(row["amount"])
    return sorted(bucket.items())


async def _attendance_series(request: Request, ctx) -> list[tuple[str, int]]:
    start, end = _report_window(request)
    if await ReportService.live_enabled(request):
        return await ReportService.attendance_series(request, ctx)
    bucket: dict[str, int] = defaultdict(int)
    for row in STORE.list_attendance(ctx.current_scope_path):
        if start <= row["date"][:10] <= end:
            bucket[row["date"][:10]] += 1
    return sorted(bucket.items())


def _next_level_key(scope_kind: str) -> str:
    mapping = {
        "global": "continent",
        "continent": "nation",
        "nation": "state",
        "state": "region",
        "region": "group",
        "group": "location",
        "location": "location",
    }
    return mapping.get(scope_kind, "location")


async def _breakdown_rows(request: Request, ctx) -> list[dict[str, Any]]:
    if await ReportService.live_enabled(request):
        return await ReportService.breakdown_rows(request, ctx)
    level_key = _next_level_key(ctx.current_scope_kind)
    labels = sorted({row[level_key] for row in STORE.visible_locations(ctx.current_scope_path)})
    count_rows = STORE.list_counts(ctx.current_scope_path)
    finance_rows = STORE.list_finance(ctx.current_scope_path)
    attendance_rows = STORE.list_attendance(ctx.current_scope_path)

    breakdown = []
    for label in labels:
        counts_total = sum(row["total"] for row in count_rows if row.get(level_key) == label or row["location"] == label)
        finance_total = sum(row["amount"] for row in finance_rows if row["location"] == label or any(loc[level_key] == label and loc["location"] == row["location"] for loc in STORE.visible_locations(ctx.current_scope_path)))
        attendance_total = sum(
            1
            for row in attendance_rows
            if row["location"] == label or any(loc[level_key] == label and loc["location"] == row["location"] for loc in STORE.visible_locations(ctx.current_scope_path))
        )
        breakdown.append(
            {
                "label": label,
                "counts_total": counts_total,
                "finance_total": finance_total,
                "attendance_total": attendance_total,
            }
        )
    return breakdown


async def _growth_rows(request: Request, ctx) -> list[dict[str, Any]]:
    if await ReportService.live_enabled(request):
        return await ReportService.growth_rows(request, ctx)
    bucket: dict[str, int] = defaultdict(int)
    for row in STORE.list_counts(ctx.current_scope_path):
        iso = date.fromisoformat(row["date"]).isocalendar()
        bucket[f"{iso.year}-W{iso.week:02d}"] += row["total"]
    points = sorted(bucket.items())
    rows = []
    previous = None
    for label, value in points:
        growth = 0.0 if previous in {None, 0} else round(((value - previous) / previous) * 100, 1)
        rows.append({"period": label, "value": value, "growth": growth})
        previous = value
    return rows


async def _anomaly_rows(request: Request, ctx) -> list[dict[str, Any]]:
    if await ReportService.live_enabled(request):
        return await ReportService.anomaly_rows(request, ctx)
    rows: list[dict[str, Any]] = []
    count_rows = STORE.list_counts(ctx.current_scope_path)
    if count_rows:
        average = sum(row["total"] for row in count_rows) / len(count_rows)
        deviation = pstdev(row["total"] for row in count_rows)
        for row in count_rows:
            if deviation > 0 and abs(row["total"] - average) >= 2 * deviation:
                rows.append(
                    {
                        "title": f"Attendance unusual at {row['location']}",
                        "detail": f"{row['event_title']} recorded {row['total']} against an average of {average:.0f}.",
                        "status": "warning",
                    }
                )
    finance_rows = STORE.list_finance(ctx.current_scope_path)
    if finance_rows:
        average_amount = sum(row["amount"] for row in finance_rows) / len(finance_rows)
        for row in finance_rows:
            if row["amount"] >= average_amount * 1.25:
                rows.append(
                    {
                        "title": f"Large finance entry at {row['location']}",
                        "detail": f"{row['fund_type'].title()} reached {format_naira(row['amount'])}, above the visible average of {format_naira(int(average_amount))}.",
                        "status": "info",
                    }
                )
    return rows[:6]


async def _summary_tab(request: Request, ctx) -> Div:
    rows = await _summary_rows(request, ctx)
    latest = rows[0] if rows else None
    counts_summary = {
        "latest_total": int(latest.get("total") or 0) if latest else 0,
        "locations_reporting": len({row.get("location_id") or row.get("location") for row in rows}),
    }

    desktop_rows = [
        [row["date"], row["location"], row["event_title"], row["total"], row["submitted_by"]]
        for row in rows
    ]
    mobile_cards = [
        Div(
            H4(row["location"], cls="h6 fw-semibold mb-1"),
            P(f"{row['event_title']} - {row['date']}", cls="text-muted mb-2"),
            P(f"Total recorded: {row['total']}", cls="small text-body-emphasis mb-1"),
            P(f"Submitted by {row['submitted_by']}", cls="small text-muted mb-0"),
            cls="mobile-count-card",
        )
        for row in rows
    ]

    return Div(
        Div(
            stat_card("Latest total", str(counts_summary["latest_total"]), "Most recent recorded attendance", "bar-chart", tone="success"),
            stat_card("Locations reporting", str(counts_summary["locations_reporting"]), "Branches that have submitted", "geo-alt", tone="info"),
            cls="counts-stat-grid",
        ),
        section_card(
            "Daily summary",
            "This keeps the latest count records near the top so oversight remains practical.",
            responsive_table(
                ["Date", "Location", "Event", "Total", "Submitted By"],
                desktop_rows,
                mobile_cards,
                results_id="reports-summary-table",
            ),
        ),
        Div(id="reports-refresh-feedback"),
    )


async def _financial_tab(request: Request, ctx) -> Div:
    rows = await _financial_rows(request, ctx)
    total = sum(float(row.get("amount") or 0) for row in rows)
    transactions = sum(int(row.get("transaction_count") or 1) for row in rows)
    summary = {"month_total": total, "year_total": total, "average_entry": round(total / transactions, 2) if transactions else 0, "entries": transactions}
    desktop_rows = [
        [row["date"], row["location"], row["fund_type"].title(), format_naira(row["amount"]), row["method"], row["submitted_by"]]
        for row in rows
    ]
    mobile_cards = [
        Div(
            H4(format_naira(row["amount"]), cls="h6 fw-semibold mb-1"),
            P(f"{row['location']} - {row['date']}", cls="text-muted mb-2"),
            Div(status_badge(row["fund_type"]), cls="mb-2"),
            P(f"{row['method']} by {row['submitted_by']}", cls="small text-muted mb-0"),
            cls="mobile-count-card",
        )
        for row in rows
    ]
    return Div(
        Div(
            stat_card("Approved total", format_naira(summary["year_total"]), "Approved offerings and tithes within the selected dates", "cash-stack", tone="primary"),
            stat_card("Transactions", str(summary["entries"]), "Approved finance entries within the selected dates", "cash-coin", tone="success"),
            stat_card("Average entry", format_naira(summary["average_entry"]), "Helps spot unusual values quickly", "calculator", tone="warning"),
            stat_card("Entry count", str(summary["entries"]), "Recorded finance submissions", "receipt", tone="info"),
            cls="counts-stat-grid",
        ),
        section_card(
            "Financial summary",
            "Approved offering and tithe entries within the selected date window.",
            responsive_table(
                ["Date", "Location", "Type", "Amount", "Method", "Recorded By"],
                desktop_rows,
                mobile_cards,
                results_id="reports-financial-table",
            ),
        ),
    )


async def _attendance_tab(request: Request, ctx) -> Div:
    rows = await _attendance_rows(request, ctx)
    present = sum(int(row.get("worker_count") or 1) for row in rows if str(row.get("status") or "").lower() == "present")
    late = sum(int(row.get("worker_count") or 1) for row in rows if str(row.get("status") or "").lower() == "late")
    expected = sum(int(row.get("worker_count") or 1) for row in rows)
    summary = {"expected": expected, "present": present, "late": late, "rate": round(present * 100 / expected, 1) if expected else 0}
    desktop_rows = [
        [row["date"], row["worker_name"], row["unit"], row["event_title"], row["location"], status_badge(row["status"])]
        for row in rows
    ]
    mobile_cards = [
        Div(
            H4(row["worker_name"], cls="h6 fw-semibold mb-1"),
            P(f"{row['unit']} - {row['event_title']}", cls="text-muted mb-2"),
            Div(status_badge(row["status"]), cls="mb-2"),
            P(f"{row['location']} - {row['date']}", cls="small text-muted mb-0"),
            cls="mobile-worker-card",
        )
        for row in rows
    ]
    return Div(
        Div(
            stat_card("Attendance records", str(summary["expected"]), "Worker attendance records in this date window", "people", tone="primary"),
            stat_card("Present", str(summary["present"]), "Attendance marked present", "check2-circle", tone="success"),
            stat_card("Late", str(summary["late"]), "Late attendance records", "clock-history", tone="warning"),
            stat_card("Present share", f"{summary['rate']}%", "Present records as a share of attendance records", "graph-up", tone="info"),
            cls="counts-stat-grid",
        ),
        section_card(
            "Attendance summary",
            "Worker attendance records within the selected date window.",
            responsive_table(
                ["Date", "Worker", "Unit", "Event", "Location", "Status"],
                desktop_rows,
                mobile_cards,
                results_id="reports-attendance-table",
            ),
        ),
    )


async def _timeseries_tab(request: Request, ctx) -> Div:
    count_points, finance_points, attendance_points = await asyncio.gather(
        _counts_series(request, ctx),
        _finance_series(request, ctx),
        _attendance_series(request, ctx),
    )
    return Div(
        section_card(
            "Attendance count trend",
            f"Trend: {_trend_label(count_points)}",
            _sparkline(count_points, stroke="#1d4ed8", fill="#bfdbfe"),
        ),
        section_card(
            "Finance trend",
            f"Trend: {_trend_label(finance_points)}",
            _sparkline(finance_points, stroke="#059669", fill="#a7f3d0"),
        ),
        section_card(
            "Worker attendance trend",
            f"Trend: {_trend_label(attendance_points)}",
            _sparkline(attendance_points, stroke="#d97706", fill="#fde68a"),
        ),
        cls="d-grid gap-4",
    )



async def _breakdown_tab(request: Request, ctx) -> Div:
    rows = await _breakdown_rows(request, ctx)
    if not rows:
        return empty_state("diagram-3", "No breakdown rows", "No comparison rows are available.")
    desktop_rows = [
        [row["label"], row["counts_total"], format_naira(row["finance_total"]), row["attendance_total"]]
        for row in rows
    ]
    mobile_cards = [
        Div(
            H4(row["label"], cls="h6 fw-semibold mb-1"),
            P(f"Counts: {row['counts_total']}", cls="small text-body-emphasis mb-1"),
            P(f"Finance: {format_naira(row['finance_total'])}", cls="small text-body-emphasis mb-1"),
            P(f"Attendance records: {row['attendance_total']}", cls="small text-muted mb-0"),
            cls="mobile-count-card",
        )
        for row in rows
    ]
    return section_card(
        "Breakdown by level",
        f"Breakdown by {_next_level_key(ctx.current_scope_kind).replace('_', ' ')}.",
        responsive_table(
            ["Unit", "Counts", "Finance", "Attendance Records"],
            desktop_rows,
            mobile_cards,
            results_id="reports-breakdown-table",
        ),
    )


async def _growth_tab(request: Request, ctx) -> Div:
    rows = await _growth_rows(request, ctx)
    if not rows:
        return empty_state("graph-up", "Not enough history yet", "Growth becomes more useful once multiple weeks of records are available.")
    points = [(row["period"], row["value"]) for row in rows]
    desktop_rows = [[row["period"], row["value"], f"{row['growth']}%"] for row in rows]
    mobile_cards = [
        Div(
            H4(row["period"], cls="h6 fw-semibold mb-1"),
            P(f"Value: {row['value']}", cls="small text-body-emphasis mb-1"),
            P(f"Growth: {row['growth']}%", cls="small text-muted mb-0"),
            cls="mobile-count-card",
        )
        for row in rows
    ]
    return Div(
        section_card(
            "Weekly growth",
            "Weekly count totals by period.",
            _sparkline(points, stroke="#7c3aed", fill="#ddd6fe"),
        ),
        section_card(
            "Growth table",
            "Weekly count totals and week-on-week growth percentage.",
            responsive_table(
                ["Period", "Value", "Growth"],
                desktop_rows,
                mobile_cards,
                results_id="reports-growth-table",
            ),
        ),
        cls="d-grid gap-4",
    )


async def _anomalies_tab(request: Request, ctx) -> Div:
    rows = await _anomaly_rows(request, ctx)
    if not rows:
        return empty_state("exclamation-diamond", "No anomalies detected", "No unusual records were found.")
    return Div(
        *[
            section_card(
                row["title"],
                row["detail"],
                Div(status_badge(row["status"])),
            )
            for row in rows
        ],
        cls="d-grid gap-3",
    )


async def _exports_tab(request: Request, ctx) -> Div:
    start_date, end_date = _report_window(request)
    export_cards = []
    for report_type, title in [
        ("counts", "Attendance counts"),
        ("financial", "Financial summary"),
        ("attendance", "Worker attendance"),
    ]:
        if await ReportService.live_enabled(request):
            actions = Div(
                Button("CSV", variant="outline-primary", size="md", href=ctx.url_for("/reports/export/live", report_type=report_type, export_format="csv", start_date=start_date, end_date=end_date)),
                Button("Excel", variant="outline-primary", size="md", href=ctx.url_for("/reports/export/live", report_type=report_type, export_format="excel", start_date=start_date, end_date=end_date)),
                Button("PDF", variant="outline-primary", size="md", href=ctx.url_for("/reports/export/live", report_type=report_type, export_format="pdf", start_date=start_date, end_date=end_date)),
                cls="d-grid d-md-flex gap-2",
            )
            description = (
                "Downloads are proxied through the admin so backend authentication stays server-side and use the selected date range."
            )
        else:
            actions = Div(
                Button(
                    "CSV",
                    variant="outline-primary",
                    size="md",
                    type="button",
                    hx_get=ctx.url_for("/reports/export/mock", report_type=report_type, export_format="csv", start_date=start_date, end_date=end_date),
                    hx_target="#reports-export-feedback",
                    hx_swap="innerHTML",
                ),
                Button(
                    "Excel",
                    variant="outline-primary",
                    size="md",
                    type="button",
                    hx_get=ctx.url_for("/reports/export/mock", report_type=report_type, export_format="excel", start_date=start_date, end_date=end_date),
                    hx_target="#reports-export-feedback",
                    hx_swap="innerHTML",
                ),
                *(
                    [
                        Button(
                            "PDF",
                            variant="outline-primary",
                            size="md",
                            type="button",
                            hx_get=ctx.url_for("/reports/export/mock", report_type=report_type, export_format="pdf", start_date=start_date, end_date=end_date),
                            hx_target="#reports-export-feedback",
                            hx_swap="innerHTML",
                        )
                    ]
                ),
                cls="d-grid d-md-flex gap-2",
            )
            description = (
                "Mock export actions represent the selected report family and date range."
            )
        export_cards.append(
            section_card(
                title,
                description,
                actions,
            )
        )
    return Div(*export_cards, Div(id="reports-export-feedback"), cls="d-grid gap-3")


def _active_report_tab(tab: str) -> str:
    valid = {key for key, _label in REPORT_TABS}
    return tab if tab in valid else "summary"


async def _report_tab_nav(ctx, active_tab: str, start_date: str, end_date: str) -> Div:
    return Div(
        *[
            Button(
                label,
                variant="primary" if key == active_tab else "outline-primary",
                size="md",
                type="button",
                hx_get=ctx.url_for("/reports/content", tab=key, start_date=start_date, end_date=end_date),
                hx_target="#reports-content",
                hx_swap="outerHTML",
                cls="admin-inline-btn",
                **({"aria_current": "page"} if key == active_tab else {}),
            )
            for key, label in REPORT_TABS
        ],
        cls="workspace-tab-strip mb-3",
    )


async def _report_tab_content(request: Request, ctx, active_tab: str) -> Div:
    tab_views = {
        "summary": _summary_tab,
        "financial": _financial_tab,
        "attendance": _attendance_tab,
        "timeseries": _timeseries_tab,
        "breakdown": _breakdown_tab,
        "growth": _growth_tab,
        "anomalies": _anomalies_tab,
        "exports": _exports_tab,
    }
    return await tab_views[_active_report_tab(active_tab)](request, ctx)


async def _reports_loading_content(ctx, active_tab: str, start_date: str, end_date: str) -> Div:
    return Div(
        Div(
            P("Loading reports.", cls="text-muted mb-0"),
            cls="d-flex align-items-center gap-3",
        ),
        PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
        PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
        id="reports-content",
        hx_get=ctx.url_for("/reports/content", tab=active_tab, start_date=start_date, end_date=end_date),
        hx_trigger="load",
        hx_swap="outerHTML",
        cls="d-grid gap-3",
    )


async def _reports_content(request: Request, ctx, active_tab: str) -> Div:
    active_tab = _active_report_tab(active_tab)
    start_date, end_date = _report_window(request)
    tab_nav = await _report_tab_nav(ctx, active_tab, start_date, end_date)
    tab_content = await _report_tab_content(request, ctx, active_tab)
    return Div(
        section_card(
            "Report categories",
            "Switch between summary, financial, attendance, trends, and exports.",
            Div(
                Form(
                    Div(Label("From", fr="report-start-date", cls="form-label"), Input(type="date", id="report-start-date", name="start_date", value=start_date, cls="form-control"), cls="col-12 col-md-4"),
                    Div(Label("To", fr="report-end-date", cls="form-label"), Input(type="date", id="report-end-date", name="end_date", value=end_date, cls="form-control"), cls="col-12 col-md-4"),
                    Div(Button("Apply dates", variant="primary", size="md", type="submit"), cls="col-12 col-md-4 d-flex align-items-end"),
                    Input(type="hidden", name="profile", value=ctx.profile.key),
                    *[
                        Input(type="hidden", name=name, value=value)
                        for name, value in ctx.query_extras.items()
                        if name not in {"start_date", "end_date", "profile"} and value
                    ],
                    action="/reports",
                    method="get",
                    hx_get=ctx.url_for("/reports/content", tab="summary", start_date=start_date, end_date=end_date),
                    hx_target="#reports-content",
                    hx_swap="outerHTML",
                    cls="row g-3 align-items-end mb-3",
                ),
                tab_nav,
                tab_content,
            ),
        ),
        id="reports-content",
    )


def register_report_routes(app) -> None:
    @app.get("/reports")
    async def reports_page(request: Request, tab: str = "summary", start_date: str = "", end_date: str = ""):
        ctx = build_context(request)
        if ctx.level < 2 or not ctx.has_permission("reports:read"):
            body = page_stack(section_card(
                "Reports",
                "Scoped reports are available to oversight roles at Level 3 and above.",
                empty_state("clipboard-data", "Access restricted", "Your assigned role does not have reports:read permission."),
            ))
            return shell_layout(
                ctx,
                request_path=request.url.path,
                active_key="reports",
                title="Reports",
                subtitle="Scoped summaries and exports.",
                primary_action=None,
                content=body,
                show_shell_intro=False,
            )

        body = page_stack(
            page_intro(
                "Reports",
                "Keep reporting readable and scoped, with summary first and exports available without leaving the hub.",
                scope_label=ctx.current_scope_label,
                scope_kind=ctx.current_scope_kind,
            ),
            _reports_loading_content(ctx, _active_report_tab(tab), *_report_window(request)),
        )
        refresh_button = Button(
            "Refresh Reports",
            variant="primary",
            size="md",
            type="button",
            hx_post=ctx.url_for("/reports/refresh"),
            hx_target="#reports-refresh-feedback",
            hx_swap="innerHTML",
        )
        if not ctx.has_permission("reports:refresh"):
            refresh_button = None
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="reports",
            title="Reports",
            subtitle="Summary, trends, anomalies, and exports.",
            primary_action=refresh_button,
            content=body,
            show_shell_intro=False,
        )

    @app.get("/reports/content")
    async def reports_content(request: Request, tab: str = "summary"):
        ctx = build_context(request)
        if ctx.level < 2 or not ctx.has_permission("reports:read"):
            return Div(
                section_card(
                    "Reports",
                    "Scoped reports are available to oversight roles at Level 3 and above.",
                    empty_state("clipboard-data", "Access restricted", "Your assigned role does not have reports:read permission."),
                ),
                id="reports-content",
            )
        try:
            return await _reports_content(request, ctx, tab)
        except BackendClientError as exc:
            if exc.status_code == 403:
                return Div(
                    section_card(
                        "Reports",
                        "Report access is controlled by your assigned role and scope.",
                        empty_state("shield-lock", "Access restricted", "Ask your level administrator to review the reports permission for your role."),
                    ),
                    id="reports-content",
                )
            return Div(
                section_card(
                    "Reports hub",
                    "Reports, summaries, exports, and review queues.",
                    empty_state(
                        "cloud-slash",
                        "Reports are unavailable",
                        "The backend could not return reports for this scope. Check service access or try again after the report service is available.",
                    ),
                ),
                id="reports-content",
            )

    @app.post("/reports/refresh")
    async def refresh_reports(request: Request):
        ctx = build_context(request)
        if not ctx.has_permission("reports:refresh"):
            return Response("Your role does not have report refresh permission.", status_code=403, media_type="text/plain")
        if await ReportService.live_enabled(request):
            try:
                payload = await ReportService.refresh(request)
            except BackendClientError as exc:
                return simple_toast_response(
                    content=Div(P(str(exc), cls="mb-0"), id="reports-refresh-feedback"),
                    message="Report refresh failed.",
                    variant="danger",
                )
            return simple_toast_response(
                content=Div(P(str((payload or {}).get("message") or "Reports refreshed from backend."), cls="mb-0"), id="reports-refresh-feedback"),
                message="Reports refreshed.",
                variant="success",
            )
        return simple_toast_response(
            content=Div(
                P("Reports refreshed.", cls="mb-0"),
                id="reports-refresh-feedback",
            ),
            message="Reports refreshed.",
            variant="success",
        )

    @app.get("/reports/export/mock")
    async def reports_export_mock(request: Request, report_type: str = "counts", export_format: str = "csv"):
        ctx = build_context(request)
        if not ctx.has_permission("reports:read"):
            return Response("Your role does not have report read permission.", status_code=403, media_type="text/plain")
        label = report_type.replace("_", " ").title()
        export_name = export_format.upper()
        return simple_toast_response(
            content=Div(
                P(f"{label} export prepared as {export_name}.", cls="mb-0"),
                id="reports-export-feedback",
            ),
            message=f"{label} {export_name} export prepared.",
            variant="info",
        )

    @app.get("/reports/export/live")
    async def reports_export_live(request: Request, report_type: str = "counts", export_format: str = "csv"):
        ctx = build_context(request)
        if not ctx.has_permission("reports:read"):
            return Response("Your role does not have report read permission.", status_code=403, media_type="text/plain")
        try:
            payload = await ReportService.export(request, ctx, report_type=report_type, export_format=export_format)
        except BackendClientError as exc:
            return Response(str(exc), media_type="text/plain", status_code=exc.status_code or 502)
        except ValueError as exc:
            return Response(str(exc), media_type="text/plain", status_code=502)
        if payload is None:
            return Response("Live export is only available in backend mode.", media_type="text/plain", status_code=400)
        content, headers = payload
        return Response(
            content=content,
            media_type=headers.get("content-type", "application/octet-stream"),
            headers={"Content-Disposition": headers.get("content-disposition", f"attachment; filename={report_type}.{export_format}")},
        )
