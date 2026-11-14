"""Shared analytics view for recurring population programs."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fasthtml.common import A, Div, Form, H1, H2, H3, Input, Label, NotStr, Option, P, Select, Span, Strong
from faststrap import Button, Card
from starlette.requests import Request

from ..auth_context import build_context
from ..backend import format_scope_display_id
from ..communication.active_scope import active_scope_context, scope_link
from ..communication.dashboard_service import DashboardService
from ..components.shell import hidden_context_inputs, shell_layout
from ..components.ui import empty_state, page_stack, section_card, stat_card
from app.services.analytics.program_config import STANDING_PROGRAMS, reporting_today


PROGRAM_KEYS = (
    "sunday_worship_service",
    "house_caring_fellowship",
    "monday_bible_study",
    "thursday_revival_hour",
)


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _fmt_number(value: Any) -> str:
    return f"{_int(value):,}"


def _category_metrics(report: dict[str, Any]) -> list[tuple[str, int | None, float | None]]:
    categories = report.get("categories") or {}
    total = report.get("total")
    if total is None or any(categories.get(key) is None for key in ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")):
        return [("Male", None, None), ("Female", None, None), ("Adults", None, None), ("Youth", None, None), ("Children", None, None)]
    values = {
        "Male": _int(categories["adult_male"]) + _int(categories["youth_male"]) + _int(categories["boys"]),
        "Female": _int(categories["adult_female"]) + _int(categories["youth_female"]) + _int(categories["girls"]),
        "Adults": _int(categories["adult_male"]) + _int(categories["adult_female"]),
        "Youth": _int(categories["youth_male"]) + _int(categories["youth_female"]),
        "Children": _int(categories["boys"]) + _int(categories["girls"]),
    }
    denominator = _int(total)
    return [(label, amount, round(amount * 100 / denominator, 1) if denominator else None) for label, amount in values.items()]


def _demographic_list(report: dict[str, Any], *, compact: bool = False) -> Any:
    metrics = _category_metrics(report)
    return Div(*[
        Div(
            Span(label, cls="program-demographic-label"),
            Strong("Not available" if amount is None else _fmt_number(amount), cls="program-demographic-value"),
            Span("" if percentage is None else f"{percentage:g}%", cls="program-demographic-percent"),
            cls="program-demographic-item",
        )
        for label, amount, percentage in metrics
    ], cls="program-demographics" + (" program-demographics-compact" if compact else ""), aria_label="Demographic counts and share of counted attendance")


def _scope_expected_percent(report: dict[str, Any]) -> tuple[str, str]:
    expected = report.get("expected_population_scope_total")
    counted = report.get("total")
    estimated_locations = _int(report.get("expected_population_scope_locations"))
    total_locations = _int(report.get("n_expected"))
    missing_estimates = max(0, total_locations - estimated_locations)
    if expected is None or _int(expected) <= 0 or counted is None:
        if counted is None:
            return "No counted attendance", "The attendance figure is unavailable until a report is counted."
        return "No expected count", "Set location estimates to compare attendance with expected population."
    percentage = round(_int(counted) * 100 / _int(expected), 1)
    note = f"{_fmt_number(counted)} counted of {_fmt_number(expected)} expected"
    if estimated_locations:
        note += f" across {estimated_locations} of {total_locations} locations with estimates"
    if missing_estimates:
        note += f" · {missing_estimates} location{'s' if missing_estimates != 1 else ''} without estimate"
    return f"{percentage:g}%", note


def _scope_depth(path: str) -> int:
    return max(0, len([part for part in path.split(".") if part]) - 1)


def _default_date(program_key: str) -> date:
    program = STANDING_PROGRAMS[program_key]
    today = reporting_today()
    return today - timedelta(days=(today.weekday() - int(program.weekday)) % 7)


def _report_label(report: dict[str, Any]) -> str:
    """Describe saved status separately from a counted value or no report."""
    total = report.get("total")
    if total is not None:
        return "Reported 0" if _int(total) == 0 else f"{_int(total):,}"
    coverage = report.get("coverage") or {}
    if _int(coverage.get("pending")):
        return "Pending review · excluded from totals"
    if _int(coverage.get("conflict")):
        return "Conflict · excluded from totals"
    if _int(coverage.get("returned")):
        return "Returned · awaiting correction"
    if _int(coverage.get("awaiting")):
        return "Awaiting report"
    if _int(coverage.get("late")):
        return "Late · no report"
    return "Not reported"


def _current_maximum_path(request: Request, ctx: Any) -> str:
    identity = getattr(request.state, "identity", None)
    return str(
        getattr(identity, "maximum_scope_path", "")
        or (getattr(ctx, "query_extras", {}) or {}).get("home_path")
        or getattr(ctx, "current_scope_path", "")
    )


def _trend(history: list[dict[str, Any]], unit_label: str) -> Any:
    if not history:
        return empty_state("graph-up", "No trend yet", "No saved reports fall in this window.")
    width, height, left, right = 720, 250, 48, 38
    top, bottom = 24, 174
    plot_width = width - left - right
    slot = plot_width / max(1, len(history))
    averages = [
        _int(row.get("total")) / _int(row.get("n_counted"))
        for row in history if row.get("total") is not None and _int(row.get("n_counted")) > 0
    ]
    scale = max(10, max(averages, default=0))
    coords = []
    svg = [f'<svg class="analytics-svg" viewBox="0 0 {width} {height}" role="img" aria-label="{unit_label.title()} attendance trend and reporting coverage">']
    for fraction in (0, .5, 1):
        y = top + (bottom - top) * fraction
        svg.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="analytics-svg-grid"/>')
        svg.append(f'<text x="0" y="{y+4:.1f}" class="analytics-svg-label">{scale*(1-fraction):.0f}</text>')
    for index, row in enumerate(history):
        x = left + slot * (index + .5)
        counted = _int(row.get("n_counted"))
        expected = _int(row.get("n_expected"))
        total = row.get("total")
        y = None if total is None or counted == 0 else bottom - (bottom-top) * ((float(total) / counted) / scale)
        coords.append((x, y))
        coverage = min(100, 100 * counted / expected) if expected else 0
        bar_height = 44 * coverage / 100
        svg.append(f'<rect x="{x-slot*.24:.1f}" y="{222-bar_height:.1f}" width="{slot*.48:.1f}" height="{bar_height:.1f}" rx="2" class="analytics-svg-bar"/>')
        svg.append(f'<text x="{x:.1f}" y="242" text-anchor="middle" class="analytics-svg-label analytics-svg-date">{str(row.get("occurrence_date") or "")[-5:]}</text>')
    segment = []
    segments = []
    for point in coords:
        if point[1] is None:
            if segment:
                segments.append(segment)
                segment = []
        else:
            segment.append(point)
    if segment:
        segments.append(segment)
    for points in segments:
        if len(points) > 1:
            svg.append('<polyline class="analytics-svg-line" points="' + " ".join(f"{x:.1f},{y:.1f}" for x, y in points) + '"/>')
        svg.extend(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" class="analytics-svg-point"/>' for x, y in points)
    svg.append("</svg>")
    return Div(
        Div(NotStr("".join(svg)), cls="analytics-chart-plot"),
        P(f"Blue line: average population per reporting {unit_label}. Green bars: share of expected {unit_label_plural(unit_label)} with a counted report. Missing reports leave a gap in the line.", cls="analytics-legend small text-muted mb-0"),
        cls="analytics-chart",
    )


def unit_label_plural(unit_label: str) -> str:
    return "fellowships" if unit_label == "fellowship" else "locations"


async def _render_content(request: Request, *, program_key: str, weeks: int, include_pending: bool, scope_path: str) -> Any:
    ctx = active_scope_context(request, build_context(request))
    program = STANDING_PROGRAMS[program_key]
    latest = _default_date(program_key)
    payload = await DashboardService.standing_program_series(
        request, ctx, program_key=program_key, weeks=weeks,
        scope_path=scope_path, latest_date=latest.isoformat(),
        include_pending=include_pending,
    )
    if payload.get("error"):
        return Div(H2("Population report could not load", cls="h5"), P(str(payload["error"]), cls="text-danger mb-0"), id="population-analytics-content", cls="alert alert-danger")

    scope_history = payload.get("scope") or []
    history = scope_history[-weeks:]
    current = history[-1] if history else {}
    children = [row for row in payload.get("children") or [] if row.get("path")]
    depth = _scope_depth(scope_path)
    unit_label = "fellowship" if program.expected_unit == "fellowship" else "location"
    unit_label_plural = "fellowships" if unit_label == "fellowship" else "locations"
    include_note = (
        "Fellowship submissions have no approval status; all saved rows are included."
        if program_key == "house_caring_fellowship"
        else ("Approved and pending reports are included." if include_pending else "Approved reports only. Pending reports are excluded.")
    )
    total = current.get("total")
    n_counted = _int(current.get("n_counted"))
    avg_values = [
        _int(report.get("total")) / _int(report.get("n_counted"))
        for report in history if report.get("total") is not None and _int(report.get("n_counted")) > 0
    ]
    average = round(sum(avg_values) / len(avg_values)) if avg_values else None
    coverage = current.get("coverage") or {}
    n_expected = _int(current.get("n_expected"))
    n_received = _int(current.get("n_received"))
    count_label = _report_label(current) if total is None else f"{_int(total):,}"

    is_sunday = program_key == "sunday_worship_service"
    if is_sunday:
        expected_value, expected_note = _scope_expected_percent(current)
        latest_card = Card(
            Div(Span("Latest Sunday Worship", cls="small text-muted"), Strong(count_label, cls="program-latest-total"), P(f"{current.get('occurrence_date') or 'No occurrence'} · {n_counted} of {n_expected} locations counted", cls="small text-muted mb-2"), cls="d-grid gap-1"),
            H3("People", cls="h6 fw-bold mb-2"), _demographic_list(current),
            Div(Strong(expected_value, cls="program-expected-value"), Span("of expected population", cls="small text-muted"), P(expected_note, cls="small text-muted mb-0"), cls="program-expected"),
            cls="card border-0 shadow-sm program-summary-card",
        )
    else:
        latest_card = stat_card(f"Latest {program.label}", count_label, f"{n_counted} {unit_label_plural} {'reported' if program_key == 'house_caring_fellowship' else 'counted'} · {current.get('occurrence_date', '')}", "people", tone="primary")

    coverage_card = stat_card(
        "Reporting coverage", f"{n_received} of {n_expected}",
        (f"{_int(coverage.get('reported'))} reported · {_int(coverage.get('missing')) + _int(coverage.get('late')) + _int(coverage.get('awaiting'))} not reported"
         if program_key == "house_caring_fellowship" else
         f"{_int(coverage.get('approved'))} approved · {_int(coverage.get('pending'))} pending · {_int(coverage.get('returned'))} returned · {_int(coverage.get('missing')) + _int(coverage.get('late')) + _int(coverage.get('awaiting'))} not reported"),
        "clipboard-check", tone="info",
    )
    metric_cards = [
        stat_card(f"{weeks}-occurrence average", f"{average:,}" if average is not None else "No counted report", f"Average per reporting {unit_label} across this window.", "graph-up", tone="success"),
        coverage_card,
    ]
    form = Form(
        *hidden_context_inputs(ctx),
        Div(
            Label("Program", cls="form-label small fw-semibold mb-1"),
            Select(*[
                Option(STANDING_PROGRAMS[key].label, value=key, selected=key == program_key)
                for key in PROGRAM_KEYS
            ], name="program_key", cls="form-select"),
            cls="program-filter-pair program-filter-program",
        ),
        Div(
            Label("Reporting window", cls="form-label small fw-semibold mb-1"),
            Select(Option("Latest 4", value="4", selected=weeks == 4), Option("Latest 8", value="8", selected=weeks == 8), name="weeks", cls="form-select"),
            cls="program-filter-pair",
        ),
        Div(Label(Input(type="checkbox", name="include_pending", value="true", checked=include_pending, disabled=program_key == "house_caring_fellowship"), " Include pending", cls="form-check-label d-flex align-items-center gap-2"), cls="program-filter-pending"),
        Input(type="hidden", name="scope_path", value=scope_path),
        Button("Apply", variant="primary", type="submit", cls="program-filter-apply"),
        method="get", action="/church-data/population-attendance/content", cls="program-attendance-filters d-flex flex-wrap align-items-end gap-3 mb-3",
    )

    maximum = _current_maximum_path(request, ctx)
    ancestors = [row for row in payload.get("ancestors") or [] if row.get("path")]
    ancestors = [row for row in ancestors if row["path"] == maximum or str(row["path"]).startswith(maximum + ".")]
    crumbs = []
    for index, ancestor in enumerate(ancestors):
        path = str(ancestor["path"])
        name = str(ancestor.get("name") or path.rsplit(".", 1)[-1])
        if index:
            crumbs.append(Span("›", cls="text-muted mx-2"))
        if path == scope_path:
            crumbs.append(Strong(name, aria_current="location"))
        else:
            target = scope_link(ctx, "/church-data/population-attendance", scope_path=path, program_key=program_key, weeks=str(weeks), include_pending=str(include_pending).lower())
            crumbs.append(A(name, href=target, cls="text-decoration-none"))
    if not crumbs:
        crumbs = [Strong(str(getattr(ctx, "current_scope_label", "Current scope")))]

    child_cards = []
    for child in children:
        child_history = child.get("history") or []
        report = child_history[-1] if child_history else {}
        child_state = _report_label(report)
        child_expected = _int(report.get("n_expected"))
        child_received = _int(report.get("n_received"))
        child_avg = [
            _int(item.get("total")) / _int(item.get("n_counted"))
            for item in child_history if item.get("total") is not None and _int(item.get("n_counted")) > 0
        ]
        latest_date = str(report.get("occurrence_date") or "")
        href = scope_link(ctx, "/church-data/population-attendance", scope_path=str(child["path"]), program_key=program_key, weeks=str(weeks), include_pending=str(include_pending).lower())
        child_cards.append(A(Card(
            Div(Div(Strong(str(child.get("name") or "Reporting unit"), cls="program-child-name"), Span(format_scope_display_id(str(child.get("path") or "")), cls="program-child-id"), cls="d-grid"), Span(child_state, cls="badge text-bg-light"), cls="d-flex align-items-start justify-content-between gap-2"),
            P(f"{latest_date or 'No occurrence'} · {child_received} of {child_expected} {unit_label_plural} reported", cls="small text-muted mb-0"),
        Div(Strong("Not reported" if report.get("total") is None else f"{_int(report.get('total')):,}", cls="program-child-count"), Div(Strong(_scope_expected_percent(report)[0] if is_sunday else "—", cls="program-child-count"), Span("of expected" if is_sunday else "attendance", cls="small text-muted"), cls="text-end"), cls="program-child-highlights"),
            _demographic_list(report, compact=True) if is_sunday else P(f"Average per reporting {unit_label}: {round(sum(child_avg)/len(child_avg)):,}" if child_avg else "Average: no counted reports", cls="small text-muted mb-0"),
            P(_scope_expected_percent(report)[1], cls="small text-muted mb-0") if is_sunday else Span(),
            cls="card h-100 program-child-card",
        ), href=href, cls="program-child-link", aria_label=f"Open {child.get('name') or 'reporting unit'} attendance detail"))
    if depth >= 5:
        # The history rows are deliberately emitted for every week; absent and zero remain distinct.
        table_rows = []
        node = next((row for row in payload.get("location_nodes") or [] if str(row.get("path")) == scope_path), None)
        node_name = str((node or {}).get("name") or getattr(ctx, "current_scope_label", "Location"))
        for report in history:
            report_total = report.get("total")
            services = report.get("service_reports") or []
            if services:
                values = Div(*(P(
                    f"{service.get('service_id') or 'Service'}: "
                    + ("No counted report" if service.get("counted_population") is None else ("Reported 0" if _int(service.get("counted_population")) == 0 else f"{_int(service.get('counted_population')):,}"))
                    + f" · {service.get('review_state') or 'not reported'}",
                    cls="small mb-0",
                ) for service in services), cls="d-grid gap-1")
                table_rows.append(Div(Strong(str(report.get("occurrence_date") or "")), P("Multiple services; no daily total is defined.", cls="small text-muted mb-1"), values, cls="border-bottom py-2"))
            else:
                label = _report_label(report)
                table_rows.append(Div(Strong(str(report.get("occurrence_date") or "")), Span(label), cls="d-flex justify-content-between border-bottom py-2"))
        records_body = Div(H3(f"{node_name} · recent occurrences", cls="h6"), *table_rows, cls="d-grid")
    else:
        records_body = Div(*child_cards, cls="program-child-grid") if child_cards else empty_state("diagram-3", "No child scopes", "No reporting units are available within this scope.")

    intro = Div(
        Div(*crumbs, cls="small mb-2"),
        H1("Program Attendance", cls="h3 fw-bold mb-1"),
        P(f"{program.label} · {current.get('occurrence_date') or 'No report date'} · {include_note}", cls="text-muted mb-0"),
        cls="mb-3",
    )
    definitions = P(
        f"Coverage counts {unit_label_plural} with a saved report; a saved zero is counted as a report. Missing reports are not converted to zero. "
        + ("House Fellowship has no review status, so all saved fellowship records are included." if program_key == "house_caring_fellowship" else "Pending reports are excluded unless the switch is selected."),
        cls="small text-muted mb-0",
    )
    return Div(
        intro,
        form,
        Div(latest_card, Div(*metric_cards, cls="program-secondary-metrics"), cls="program-overview-grid"),
        section_card(("Regions" if depth == 2 else "Groups" if depth == 3 else "Locations" if depth == 4 else "Fellowships") if depth < 5 else "Occurrence records", "Select a card to drill down. Demographic percentages are shares of counted attendance.", records_body),
        section_card("Weekly trend", f"Average attendance by reporting {unit_label}; this is the mean of weekly unit averages, not a sum across weeks.", _trend(history, unit_label)),
        section_card("How to read this page", "Reporting definitions", definitions),
        id="population-analytics-content",
        cls="d-grid gap-3",
    )


def register_population_analytics_routes(app) -> None:
    @app.get("/church-data/population-attendance")
    async def population_attendance_page(request: Request, program_key: str = "sunday_worship_service", weeks: int = 4, include_pending: bool = False):
        ctx = active_scope_context(request, build_context(request))
        if program_key not in PROGRAM_KEYS:
            program_key = "sunday_worship_service"
        weeks = 8 if weeks == 8 else 4
        target = scope_link(ctx, "/church-data/population-attendance/content", program_key=program_key, weeks=str(weeks), include_pending=str(include_pending).lower())
        body = Div(P("Loading population reports…", cls="placeholder-glow text-muted"), id="population-page-load", hx_get=target, hx_trigger="load", hx_swap="outerHTML", cls="min-vh-25")
        report_url = scope_link(ctx, "/dashboard/pastor-report", scope_path=await DashboardService.scope_path(request, ctx), period="4w", include_pending=str(include_pending).lower())
        return shell_layout(ctx, request_path=request.url.path, active_key="church", title="Program Attendance", subtitle="Latest population counts by program and area.", primary_action=A("Print / export report", href=report_url, cls="btn btn-outline-primary"), content=page_stack(body), show_shell_intro=False)

    @app.get("/church-data/population-attendance/content")
    async def population_attendance_content(request: Request, program_key: str = "sunday_worship_service", weeks: int = 4, include_pending: bool = False, scope_path: str = ""):
        ctx = active_scope_context(request, build_context(request))
        if program_key not in PROGRAM_KEYS:
            return Div(P("Choose a supported standing program.", cls="text-danger"), id="population-analytics-content")
        weeks = 8 if weeks == 8 else 4
        effective_path = str(scope_path or await DashboardService.scope_path(request, ctx))
        return await _render_content(request, program_key=program_key, weeks=weeks, include_pending=include_pending, scope_path=effective_path)
