from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import date, timedelta
from statistics import pstdev
from typing import Any

from fasthtml.common import A, Div, Form, H3, H4, Input, Label, P
from starlette.requests import Request
from starlette.exceptions import HTTPException
from starlette.responses import Response

from faststrap import Button, Icon, PlaceholderCard, Spinner

from ..backend import BackendClientError
from ..auth_context import build_context
from ..communication import ReportService
from ..communication.active_scope import active_scope_context, scope_link
from ..communication.count_aggregation import report_count_occurrences
from ..components.chartjs import sparkline_chart as _sparkline
from ..components.feedback import simple_toast_response
from ..components.shell import shell_layout
from ..components.ui import empty_state, format_naira, page_intro, page_stack, responsive_table, section_card, stat_card, status_badge
from ..mock_data import STORE
from app.services.analytics.program_config import reporting_today


REPORT_TABS = [
    ("overview", "Overview"),
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
    today = reporting_today()
    try:
        start = date.fromisoformat(request.query_params.get("start_date", "")) if request.query_params.get("start_date") else today - timedelta(days=90)
        end = date.fromisoformat(request.query_params.get("end_date", "")) if request.query_params.get("end_date") else today
    except ValueError:
        start, end = today - timedelta(days=90), today
    if start > end:
        start, end = today - timedelta(days=90), today
    return start.isoformat(), end.isoformat()


def _reports_unavailable_panel() -> Div:
    return Div(
        section_card(
            "Reports hub",
            "Reports, summaries, exports, and review queues.",
            empty_state("cloud-slash", "Reports are unavailable", "The report service could not return data for this scope. Try again when the service is available."),
        ),
        id="reports-content",
        role="alert",
    )


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
    ctx = active_scope_context(request, ctx)
    start, end = _report_window(request)
    include_pending = str(request.query_params.get("include_pending") or "").lower() in {"1", "true", "yes", "on"}
    if await ReportService.live_enabled(request):
        return await ReportService.summary_rows(request, ctx)
    rows = report_count_occurrences(STORE.list_counts(_report_scope_path(request, ctx)), include_pending=include_pending)
    rows = [row for row in rows if start <= str(row.get("date") or "") <= end]
    for row in rows:
        row["submitted_by"] = f"{row['submissions']} usher section(s)"
    return rows


async def _financial_rows(request: Request, ctx) -> list[dict[str, Any]]:
    ctx = active_scope_context(request, ctx)
    if await ReportService.live_enabled(request):
        return await ReportService.financial_rows(request, ctx)
    start, end = _report_window(request)
    return [row for row in STORE.list_finance(_report_scope_path(request, ctx)) if start <= str(row.get("date") or "")[:10] <= end][:8]


async def _attendance_rows(request: Request, ctx) -> list[dict[str, Any]]:
    ctx = active_scope_context(request, ctx)
    if await ReportService.live_enabled(request):
        return await ReportService.attendance_rows(request, ctx)
    start, end = _report_window(request)
    return [row for row in STORE.list_attendance(_report_scope_path(request, ctx)) if start <= str(row.get("date") or "")[:10] <= end][:8]


async def _counts_series(request: Request, ctx) -> list[tuple[str, int]]:
    ctx = active_scope_context(request, ctx)
    start, end = _report_window(request)
    if await ReportService.live_enabled(request):
        return await ReportService.counts_series(request, ctx)
    bucket: dict[str, int] = defaultdict(int)
    for row in STORE.list_counts(_report_scope_path(request, ctx)):
        if start <= row["date"][:10] <= end:
            bucket[row["date"][:10]] += row["total"]
    return sorted(bucket.items())


async def _finance_series(request: Request, ctx) -> list[tuple[str, int]]:
    ctx = active_scope_context(request, ctx)
    start, end = _report_window(request)
    if await ReportService.live_enabled(request):
        return await ReportService.finance_series(request, ctx)
    bucket: dict[str, int] = defaultdict(int)
    for row in STORE.list_finance(_report_scope_path(request, ctx)):
        if start <= row["date"][:10] <= end:
            bucket[row["date"][:10]] += int(row["amount"])
    return sorted(bucket.items())


async def _attendance_series(request: Request, ctx) -> list[tuple[str, int]]:
    ctx = active_scope_context(request, ctx)
    start, end = _report_window(request)
    if await ReportService.live_enabled(request):
        return await ReportService.attendance_series(request, ctx)
    bucket: dict[str, int] = defaultdict(int)
    for row in STORE.list_attendance(_report_scope_path(request, ctx)):
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
    ctx = active_scope_context(request, ctx)
    if await ReportService.live_enabled(request):
        return await ReportService.breakdown_rows(request, ctx)
    level_key = _next_level_key(ctx.current_scope_kind)
    scope_path = _report_scope_path(request, ctx)
    labels = sorted({row[level_key] for row in STORE.visible_locations(scope_path)})
    count_rows = STORE.list_counts(scope_path)
    finance_rows = STORE.list_finance(scope_path)
    attendance_rows = STORE.list_attendance(scope_path)

    breakdown = []
    for label in labels:
        counts_total = sum(row["total"] for row in count_rows if row.get(level_key) == label or row["location"] == label)
        finance_total = sum(row["amount"] for row in finance_rows if row["location"] == label or any(loc[level_key] == label and loc["location"] == row["location"] for loc in STORE.visible_locations(scope_path)))
        attendance_total = sum(
            1
            for row in attendance_rows
            if row["location"] == label or any(loc[level_key] == label and loc["location"] == row["location"] for loc in STORE.visible_locations(scope_path))
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


def _report_scope_path(request: Request, ctx) -> str:
    return active_scope_context(request, ctx).current_scope_path


async def _growth_rows(request: Request, ctx) -> list[dict[str, Any]]:
    ctx = active_scope_context(request, ctx)
    if await ReportService.live_enabled(request):
        return await ReportService.growth_rows(request, ctx)
    bucket: dict[str, int] = defaultdict(int)
    for row in STORE.list_counts(_report_scope_path(request, ctx)):
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
    ctx = active_scope_context(request, ctx)
    if await ReportService.live_enabled(request):
        return await ReportService.anomaly_rows(request, ctx)
    rows: list[dict[str, Any]] = []
    count_rows = STORE.list_counts(_report_scope_path(request, ctx))
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
    finance_rows = STORE.list_finance(_report_scope_path(request, ctx))
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
        "latest_total": int(latest.get("total") or 0) if latest else None,
        "locations_reporting": len({row.get("location_id") or row.get("location") for row in rows}),
    }

    desktop_rows = [
        [row["date"], row["location"], row["event_title"], row.get("service_id") or "main", row["total"], row.get("status", "approved"), row["submitted_by"]]
        for row in rows
    ]
    mobile_cards = [
        Div(
            H4(row["location"], cls="h6 fw-semibold mb-1"),
            P(f"{row['event_title']} - {row['date']}", cls="text-muted mb-2"),
            P(f"Service: {row.get('service_id') or 'main'} · {str(row.get('status') or 'approved').replace('_', ' ').title()}", cls="small text-muted mb-1"),
            P(f"Total recorded: {row['total']}", cls="small text-body-emphasis mb-1"),
            P(f"Submitted by {row['submitted_by']}", cls="small text-muted mb-0"),
            cls="mobile-count-card",
        )
        for row in rows
    ]

    return Div(
        P(
            "Each row is one submitted count occurrence or service; split parts are summed within that count only. Pending appears only when selected, and rejected or returned rows are excluded.",
            cls="small text-muted mb-2",
        ),
        Form(
            Input(type="hidden", name="tab", value="summary"),
            Input(type="hidden", name="profile", value=ctx.profile.key),
            Input(type="hidden", name="scope_path", value=ctx.current_scope_path),
            Input(type="hidden", name="start_date", value=_report_window(request)[0]),
            Input(type="hidden", name="end_date", value=_report_window(request)[1]),
            *[
                Input(type="hidden", name=name, value=value)
                for name, value in ctx.query_extras.items()
                if name in {"period", "weeks"} and value
            ],
            Label(
                Input(
                    type="checkbox", name="include_pending", value="true",
                    checked=str(request.query_params.get("include_pending") or "").lower() in {"1", "true", "yes", "on"},
                    onchange="this.form.requestSubmit()",
                ),
                " Include pending count reports",
                cls="form-check-label",
            ),
            action="/reports",
            method="get",
            hx_get="/reports/content",
            hx_target="#reports-content",
            hx_swap="outerHTML",
            hx_push_url="true",
            cls="form-check mb-3",
        ),
        Div(
            stat_card("Latest occurrence", str(counts_summary["latest_total"]) if counts_summary["latest_total"] is not None else "No counted report", "One latest count group; not a sum across sessions or dates", "bar-chart", tone="success"),
            stat_card("Locations reporting", str(counts_summary["locations_reporting"]), "Branches that have submitted", "geo-alt", tone="info"),
            cls="counts-stat-grid",
        ),
        section_card(
            "Daily summary",
            "This keeps the latest count records near the top so oversight remains practical.",
            responsive_table(
                ["Date", "Location", "Program", "Service/session", "Total", "Status", "Submitted By"],
                desktop_rows,
                mobile_cards,
                results_id="reports-summary-table",
            ),
        ),
    )


def _dedicated_report_link(ctx, title: str, definition: str, path: str, action: str, note: str) -> Div:
    """A Reports-tab handoff that avoids presenting a competing calculation."""
    return section_card(
        title,
        definition,
        Div(
            P(note, cls="small text-muted mb-3"),
            Button(action, variant="outline-primary", size="md", href=scope_link(ctx, path, scope_path=ctx.current_scope_path)),
            cls="d-flex flex-column align-items-start",
        ),
    )


def _overview_card(title: str, definition: str, links: list[tuple[str, str]], note: str = "") -> Div:
    actions = [
        Button(label, variant="outline-primary", size="md", href=path)
        for label, path in links
    ]
    compact_actions = Div(
        *actions,
        cls="reports-overview-actions d-flex flex-wrap gap-2",
        role="group",
        aria_label=f"{title} options",
        tabindex="0",
    )
    return section_card(
        title,
        definition,
        Div(
            P(note, cls="small text-muted mb-3") if note else None,
            compact_actions,
        ),
    )


async def _overview_tab(request: Request, ctx) -> Div:
    start_date, end_date = _report_window(request)
    weeks = "8" if request.query_params.get("weeks") == "8" else "4"
    cards: list[Div] = []

    if ctx.has_permission("counts:read"):
        weekly_links = [
            (label, scope_link(
                ctx,
                "/church-data/population-attendance",
                scope_path=ctx.current_scope_path,
                program_key=program_key,
                weeks=weeks,
                include_pending=str(request.query_params.get("include_pending") or "false").lower(),
            ))
            for label, program_key in (
                ("Sunday Worship", "sunday_worship_service"),
                ("Monday Bible Study", "monday_bible_study"),
                ("Thursday Revival", "thursday_revival_hour"),
            )
        ]
        cards.append(_overview_card(
            "Weekly attendance",
            "Separate reports for each weekly service.",
            weekly_links,
        ))

    if ctx.has_permission("programs:read"):
        cards.append(_overview_card(
            "Special events",
            "Retreat and Crusade reports.",
            [
                ("Retreat", scope_link(ctx, "/church-data/programs/analytics/retreat", scope_path=ctx.current_scope_path)),
                ("Crusade", scope_link(ctx, "/church-data/programs/analytics/crusade", scope_path=ctx.current_scope_path)),
            ],
        ))

    if ctx.has_permission("offerings:read"):
        cards.append(_overview_card(
            "Money",
            "Offerings and tithes.",
            [("Money records", scope_link(ctx, "/church-data/finance", scope_path=ctx.current_scope_path, date_from=start_date, date_to=end_date))],
        ))

    if ctx.has_permission("records:read"):
        cards.append(_overview_card(
            "New people",
            "Newcomer and convert follow-up.",
            [("Newcomers", scope_link(ctx, "/church-data/newcomers", scope_path=ctx.current_scope_path))],
        ))

    if ctx.has_permission("attendance:read"):
        cards.append(_overview_card(
            "Worker and leader meetings",
            "Separate meeting attendance reports.",
            [
                ("Saturday Workers", scope_link(ctx, "/church-data/meetings", scope_path=ctx.current_scope_path, tab="saturday")),
                ("Tuesday Leaders", scope_link(ctx, "/church-data/meetings", scope_path=ctx.current_scope_path, tab="tuesday")),
            ],
        ))

    if ctx.has_permission("reports:read"):
        cards.append(_overview_card(
            "Print a report",
            "Print or download a scoped summary.",
            [
                ("4 weeks", scope_link(ctx, "/dashboard/pastor-report", scope_path=ctx.current_scope_path, period="4w")),
                ("8 weeks", scope_link(ctx, "/dashboard/pastor-report", scope_path=ctx.current_scope_path, period="8w")),
            ],
        ))

    if not cards:
        return Div(
            empty_state("clipboard-data", "No reports available", "Your assigned role has no report sections available in this scope."),
            id="reports-overview",
        )

    return Div(*cards, cls="d-grid gap-3", id="reports-overview")


async def _financial_tab(request: Request, ctx) -> Div:
    return _dedicated_report_link(
        ctx, "Financial", "Approved offerings and tithes for the selected dates; pending and rejected submissions are excluded.",
        "/church-data/finance", "Open Finance Analytics", "Finance Analytics is the authoritative page for financial totals and their detail rows.",
    )


async def _attendance_tab(request: Request, ctx) -> Div:
    return Div(
        P("Worker meeting attendance is shown separately for each meeting type; reports are not combined into a single attendee count.", cls="small text-muted"),
        _dedicated_report_link(ctx, "Saturday Workers Meeting", "Worker attendance for Saturday meetings, using the meeting's roster snapshot.", "/church-data/meetings/workers-saturday", "Open Workers Meeting", "The meeting page is the source for its roster-based attendance figures."),
        _dedicated_report_link(ctx, "Tuesday Leaders Meeting", "Leader attendance for Tuesday meetings, kept separate from Workers Meeting.", "/church-data/meetings/leaders-tuesday", "Open Leaders Meeting", "The meeting page lists the received meeting records and leader attendance."),
        _dedicated_report_link(ctx, "Recurring program attendance", "Population counts for recurring church programs, with each program reported separately.", "/church-data/population-attendance", "Open Recurring Program Attendance", "Compare each program on its own history; no cross-program totals are created."),
        cls="d-grid gap-3",
    )


async def _timeseries_tab(request: Request, ctx) -> Div:
    return Div(
        _dedicated_report_link(ctx, "Attendance timeseries", "Weekly population history for the selected program is shown on the Dashboard and recurring program pages.", "/dashboard", "Open Dashboard", "The Dashboard uses the shared approved-only count policy and keeps separate services distinct."),
        _dedicated_report_link(ctx, "Finance timeseries", "Offering trends are shown with approved financial records on Finance Analytics.", "/church-data/finance", "Open Finance Analytics", "Pending and rejected offerings do not contribute to approved totals."),
        _dedicated_report_link(ctx, "Worker attendance timeseries", "Workers and Leaders Meeting attendance are separate and use their meeting-specific roster calculations.", "/church-data/meetings/workers-saturday", "Open Workers Meeting", "Use the separate Leaders Meeting page for Tuesday meetings."),
        cls="d-grid gap-4",
    )



async def _breakdown_tab(request: Request, ctx) -> Div:
    return _dedicated_report_link(ctx, "Breakdown by level", "Hierarchy drill-down is presented on the Dashboard, where each level opens its own scoped view.", "/dashboard", "Open Dashboard", "Child totals and coverage are shown together in the scoped dashboard view.")


async def _growth_tab(request: Request, ctx) -> Div:
    return _dedicated_report_link(ctx, "Growth", "The Dashboard trend shows average attendance per reporting location and its reporting coverage, without adding sessions or days together.", "/dashboard", "Open Dashboard", "Compare each program with its own history from the recurring program pages.")


async def _anomalies_tab(request: Request, ctx) -> Div:
    return _dedicated_report_link(ctx, "Anomalies and follow-up", "Needs attention lists missing reports, overdue reviews, returned reports, and qualifying declines using the dashboard's shared reporting rules.", "/dashboard", "Open Dashboard", "Only items in your active scope are shown; use the child links to open a lower-level view.")


async def _exports_tab(request: Request, ctx) -> Div:
    start_date, end_date = _report_window(request)
    include_pending = str(request.query_params.get("include_pending") or "").lower() in {"1", "true", "yes", "on"}
    export_cards = []
    for report_type, title in [
        ("counts", "Population count occurrences"),
        ("financial", "Approved financial summary"),
        ("attendance", "Worker attendance trend"),
    ]:
        description = {
            "counts": "One row per count group or legacy report; split parts are summed within their group only. Pending is optional; rejected and returned rows are excluded.",
            "financial": "Approved offerings and tithes only; pending and rejected entries are excluded.",
            "attendance": "Worker attendance trend records; this is not a unique-attendee count or a population count.",
        }[report_type]
        if await ReportService.live_enabled(request):
            actions = Div(
                Button("CSV", variant="outline-primary", size="md", href=ctx.url_for("/reports/export/live", report_type=report_type, export_format="csv", start_date=start_date, end_date=end_date, include_pending=str(include_pending).lower())),
                Button("Excel", variant="outline-primary", size="md", href=ctx.url_for("/reports/export/live", report_type=report_type, export_format="excel", start_date=start_date, end_date=end_date, include_pending=str(include_pending).lower())),
                Button("PDF", variant="outline-primary", size="md", href=ctx.url_for("/reports/export/live", report_type=report_type, export_format="pdf", start_date=start_date, end_date=end_date, include_pending=str(include_pending).lower())),
                cls="d-grid d-md-flex gap-2",
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
    return tab if tab in valid else "overview"


async def _report_tab_nav(ctx, active_tab: str, start_date: str, end_date: str, include_pending: bool = False) -> Div:
    return Div(
        *[
            Button(
                label,
                variant="primary" if key == active_tab else "outline-primary",
                size="md",
                type="button",
                hx_get=ctx.url_for("/reports/content", tab=key, start_date=start_date, end_date=end_date, include_pending=str(include_pending).lower()),
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
        "overview": _overview_tab,
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


async def _reports_loading_content(ctx, active_tab: str, start_date: str, end_date: str, include_pending: bool = False) -> Div:
    return Div(
        Div(
            P("Loading reports.", cls="text-muted mb-0"),
            cls="d-flex align-items-center gap-3",
        ),
        PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
        PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
        id="reports-content",
        hx_get=ctx.url_for("/reports/content", tab=active_tab, start_date=start_date, end_date=end_date, include_pending=str(include_pending).lower()),
        hx_trigger="load",
        hx_swap="outerHTML",
        cls="d-grid gap-3",
    )


async def _reports_content(request: Request, ctx, active_tab: str) -> Div:
    active_tab = _active_report_tab(active_tab)
    start_date, end_date = _report_window(request)
    include_pending = str(request.query_params.get("include_pending") or "").lower() in {"1", "true", "yes", "on"}
    tab_nav = await _report_tab_nav(ctx, active_tab, start_date, end_date, include_pending)
    tab_content = await _report_tab_content(request, ctx, active_tab)
    date_and_tab_controls = Form(
        Div(Label("From", fr="report-start-date", cls="form-label"), Input(type="date", id="report-start-date", name="start_date", value=start_date, cls="form-control"), cls="col-12 col-md-4"),
        Div(Label("To", fr="report-end-date", cls="form-label"), Input(type="date", id="report-end-date", name="end_date", value=end_date, cls="form-control"), cls="col-12 col-md-4"),
        Div(Button("Apply dates", variant="primary", size="md", type="submit"), cls="col-12 col-md-4 d-flex align-items-end"),
        Input(type="hidden", name="profile", value=ctx.profile.key),
        Input(type="hidden", name="tab", value=active_tab),
        Input(type="hidden", name="include_pending", value=str(include_pending).lower()),
        *[
            Input(type="hidden", name=name, value=value)
            for name, value in ctx.query_extras.items()
            if name not in {"start_date", "end_date", "profile", "include_pending"} and value
        ],
        tab_nav,
        action="/reports",
        method="get",
        hx_get=ctx.url_for("/reports/content", tab=active_tab, start_date=start_date, end_date=end_date, include_pending=str(include_pending).lower()),
        hx_target="#reports-content",
        hx_swap="outerHTML",
        hx_push_url="true",
        cls="row g-3 align-items-end mb-3",
    )
    if active_tab == "overview":
        return Div(
            tab_content,
            section_card(
                "More reports",
                None,
                date_and_tab_controls,
            ),
            id="reports-content",
            cls="d-grid gap-3",
        )
    return Div(
        section_card(
            "Report categories",
            "Switch between summary, financial, attendance, trends, and exports.",
            Div(date_and_tab_controls, tab_content),
        ),
        id="reports-content",
    )


def register_report_routes(app) -> None:
    @app.get("/reports")
    async def reports_page(request: Request, tab: str = "overview", start_date: str = "", end_date: str = ""):
        ctx = active_scope_context(request, build_context(request))
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
                "Choose a report.",
            ),
            _reports_loading_content(ctx, _active_report_tab(tab), *_report_window(request), str(request.query_params.get("include_pending") or "").lower() in {"1", "true", "yes", "on"}),
            Div(id="reports-refresh-feedback"),
        )
        refresh_button = Button(
            Icon("arrow-clockwise"),
            variant="primary",
            size="md",
            type="button",
            aria_label="Refresh reports",
            title="Refresh reports",
            hx_post=ctx.url_for("/reports/refresh"),
            hx_target="#reports-refresh-feedback",
            hx_swap="innerHTML",
            cls="reports-refresh-button",
        )
        if not ctx.has_permission("reports:refresh"):
            refresh_button = None
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="reports",
            title="Reports",
            subtitle="",
            primary_action=Div(
                A("Pastor’s report / export", href=scope_link(ctx, "/dashboard/pastor-report", scope_path=ctx.current_scope_path, period="4w"), cls="btn btn-outline-primary"),
                refresh_button,
                cls="d-flex flex-wrap gap-2",
            ),
            content=body,
            show_shell_intro=False,
        )

    @app.get("/reports/content")
    async def reports_content(request: Request, tab: str = "summary"):
        ctx = active_scope_context(request, build_context(request))
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
            return _reports_unavailable_panel()
        except HTTPException as exc:
            if exc.status_code == 403:
                return Div(section_card("Reports", "Report access is controlled by your assigned role and scope.", empty_state("shield-lock", "Access restricted", "Ask your level administrator to review the reports permission for your role.")), id="reports-content")
            return _reports_unavailable_panel()
        except Exception:
            return _reports_unavailable_panel()

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
