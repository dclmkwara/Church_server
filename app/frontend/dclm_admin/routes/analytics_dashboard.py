from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from html import escape
from typing import Any

from fasthtml.common import A, Details, Div, Form, H1, H2, H3, Input, Label, Link, Main, NotStr, P, Script, Span, Strong, Summary, Table, Tbody, Td, Th, Thead, Tr
from faststrap import Button
from starlette.requests import Request

from ..backend import format_scope_display_id
from ..communication.dashboard_service import DashboardService
from ..communication.active_scope import active_scope_context, scope_link
from ..communication.church_data_service import ChurchDataService
from app.core import dashboard_perf
from app.services.analytics.program_config import ATTENTION_DECLINE_PCT, ATTENTION_MIN_COMPARABLE_LOCATIONS, reporting_today
from ..backend.config import get_backend_config
from ..auth_context import build_context


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _pooled_decline(previous: dict[str, Any], current: dict[str, Any]) -> tuple[int, float | None]:
    """Compare pooled totals only for locations counted in both weeks."""
    previous_by_location = previous.get("location_totals") or {}
    current_by_location = current.get("location_totals") or {}
    common = set(previous_by_location) & set(current_by_location)
    previous_total = sum(_integer(previous_by_location[key]) for key in common)
    current_total = sum(_integer(current_by_location[key]) for key in common)
    if len(common) < ATTENTION_MIN_COMPARABLE_LOCATIONS or previous_total <= 0:
        return len(common), None
    return len(common), 100 * (previous_total - current_total) / previous_total


def _lagos_sunday(today: date | None = None, *, now: datetime | None = None) -> date:
    today = today or reporting_today(now)
    return today - timedelta(days=(today.weekday() + 1) % 7)


def _scope_level(path: str, fallback: str) -> str:
    depth = max(0, len([part for part in path.split(".") if part]) - 1)
    return {2: "State", 3: "Region", 4: "Group", 5: "Location"}.get(depth, fallback)


def _number(value: Any) -> str:
    return f"{_integer(value):,}"


def _period_delta(current: int | float, previous: int | float, *, previous_records: int, noun: str) -> str:
    """Describe comparable-period movement without inventing a rate from zero."""
    current_value, previous_value = float(current or 0), float(previous or 0)
    if previous_records <= 0:
        return "No prior-period records to compare" if current_value <= 0 else f"New this period · {noun}"
    if previous_value == 0:
        return f"Up from 0 · {noun}" if current_value > 0 else "No change · previous period was 0"
    change = round(100 * (current_value - previous_value) / abs(previous_value))
    if change == 0:
        return f"No change vs previous {noun}"
    direction = "Up" if change > 0 else "Down"
    return f"{direction} {abs(change)}% vs previous {noun}"


def _age_label(age_hours: Any) -> str:
    age = _integer(age_hours)
    if age < 48:
        return f"{age} hours"
    return f"{age // 24} days"


def _waiting_on_decision(summary: dict[str, Any], weeks: int) -> Any:
    pending = summary.get("pending_approvals") or []
    rows = []
    for item in pending:
        label = str(item.get("label") or "Pending item")
        count = _integer(item.get("count"))
        age = item.get("oldest_age_hours")
        age_text = "age unavailable" if age is None else f"oldest waiting {_age_label(age)}"
        rows.append(Div(Span(label), Strong(_number(count)), Span(age_text, cls="analytics-muted"), cls="analytics-decision-row"))
    body = Div(*rows, cls="analytics-decision-list") if rows else P("No requests waiting for a decision.", cls="analytics-muted")
    return Div(H2("Waiting on a decision", cls="analytics-panel-title"), P("Pending approvals in this scope, ordered by their oldest waiting item.", cls="analytics-note"), body, cls="panel analytics-decision-panel")


def _short_date(value: date) -> str:
    return value.strftime("%d %b").lstrip("0")


def _coverage_values(payload: dict[str, Any]) -> dict[str, int]:
    coverage = payload.get("coverage") or {}
    return {
        "approved": _integer(coverage.get("approved")),
        "pending": _integer(coverage.get("pending")),
        "returned": _integer(coverage.get("returned")),
        "conflict": _integer(coverage.get("conflict")),
        "missing": sum(_integer(coverage.get(key)) for key in ("missing", "late", "awaiting")),
    }


def _line_chart(points: list[dict[str, Any]], selected_weeks: int) -> Any:
    shown = points[-selected_weeks:]
    width, height, left, right = 900, 350, 58, 60
    chart_w = width - left - right
    line_top, line_bottom = 22, 180
    bars_top, bars_bottom, date_y = 226, 304, 330
    slot = chart_w / max(len(shown), 1)
    values = [point["average"] for point in shown if point.get("average") is not None]
    maximum = max(values, default=0)
    scale_max = max(100, ((maximum + 99) // 100) * 100)
    coords: list[tuple[float, float | None, dict[str, Any]]] = []
    for index, point in enumerate(shown):
        x = left + slot * (index + 0.5)
        average = point.get("average")
        y = None if average is None else line_bottom - ((line_bottom - line_top) * average / scale_max)
        coords.append((x, y, point))
    # Break the line at missing reports. A missing week must never be plotted
    # at zero, because zero is a valid reported population.
    line_segments: list[list[tuple[float, float]]] = []
    current_segment: list[tuple[float, float]] = []
    for x, y, _point in coords:
        if y is None:
            if current_segment:
                line_segments.append(current_segment)
                current_segment = []
            continue
        current_segment.append((x, y))
    if current_segment:
        line_segments.append(current_segment)
    polylines = [" ".join(f"{x:.1f},{y:.1f}" for x, y in segment) for segment in line_segments if len(segment) > 1]
    chart_paths = " | ".join(polylines)
    svg = f'<svg class="analytics-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Average reported population and reporting coverage by Sunday">'
    for fraction in (0, 0.5, 1):
        y = line_top + (line_bottom - line_top) * fraction
        svg += f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="analytics-svg-grid" />'
        svg += f'<text x="0" y="{y+4:.1f}" class="analytics-svg-label">{round(scale_max * (1-fraction))}</text>'
        bar_y = bars_top + (bars_bottom - bars_top) * fraction
        svg += f'<line x1="{left}" y1="{bar_y:.1f}" x2="{width-right}" y2="{bar_y:.1f}" class="analytics-svg-grid analytics-svg-coverage-grid" />'
        svg += f'<text x="{width-right+8}" y="{bar_y+4:.1f}" class="analytics-svg-label">{round(100 * (1-fraction))}%</text>'
    svg += "".join(f'<polyline points="{line}" class="analytics-svg-line" />' for line in polylines)
    svg += "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" class="analytics-svg-point" />' for x, y, point in coords if y is not None)
    label_stride = max(1, (len(coords) + 4) // 5)
    for index, (x, _y, point) in enumerate(coords):
        expected = _integer(point.get("expected"))
        share = min(100, max(0, 100 * _integer(point.get("counted")) / expected)) if expected else 0
        bar_height = (bars_bottom - bars_top) * share / 100
        svg += f'<rect x="{x-slot*0.25:.1f}" y="{bars_bottom-bar_height:.1f}" width="{slot*0.5:.1f}" height="{bar_height:.1f}" rx="3" class="analytics-svg-bar" data-week="{escape(str(point.get("date") or ""))}" data-share="{share:.1f}" />'
        if index == 0 or index == len(coords) - 1 or index % label_stride == 0:
            svg += f'<text x="{x:.1f}" y="{date_y}" text-anchor="middle" class="analytics-svg-label analytics-svg-date">{escape(str(point.get("date") or "")[5:])}</text>'
    svg += '</svg>'
    return Div(
        Div(NotStr(svg), cls="analytics-chart-plot"),
        P("Blue line: average population per counted location. Green bars: share of expected locations with a counted report (0–100%). A missing week leaves a gap in the line; an approved zero is plotted at zero.", cls="analytics-legend small"),
        cls="analytics-chart",
        data_points=chart_paths,
        data_height=height,
    )


_METRIC_DEFINITIONS = {
    "Adds up": "Approved reports are added across the locations in this scope.",
    "Pooled": "The percentage compares total counted population with total documented population for locations with both values.",
    "Recomputed": "This is recalculated from the weekly averages; weeks without a counted report are excluded.",
    "Snapshot": "This is the worker register at the time of this report.",
    "Roster check": "The attendance rate is withheld until the expected worker roster can be counted once per meeting.",
    "Approved only": "Only reports approved by the reviewer are included.",
    "Reports": "A report is a submitted record; it does not identify a unique person.",
}


def _metric(label: str, value: str, note: str, classification: str) -> Any:
    return Div(
        Div(
            Span(label, cls="analytics-kicker"),
            Details(
                Summary("i", aria_label=f"Definition: {label}", title="Show definition"),
                P(_METRIC_DEFINITIONS.get(classification, "This figure is calculated from the reports in the selected period.")),
                cls="analytics-info",
            ),
            cls="analytics-card-head",
        ),
        H3(value, cls="analytics-value"),
        P(note, cls="analytics-note"),
        cls="analytics-metric panel",
    )


def _coverage_panel(payload: dict[str, Any], occurrence: date, include_pending: bool) -> Any:
    n_expected = _integer(payload.get("n_expected"))
    received = _integer(payload.get("n_received"))
    parts = _coverage_values(payload)
    total = max(n_expected, 1)
    bars = []
    for key, label, css in (("approved", "Approved", "approved"), ("pending", "Pending review", "pending"), ("returned", "Returned", "returned"), ("conflict", "Conflict", "conflict"), ("missing", "Not reported", "missing")):
        count = parts[key]
        bars.append(Div(cls=f"analytics-coverage-segment {css}", style=f"width:{100 * count / total:.4f}%", title=f"{label}: {count}"))
    legend = [Span(Span(cls=f"analytics-dot {css}"), f"{label} {parts[key]}", cls="analytics-legend-item") for key, label, css in (("approved", "Approved", "approved"), ("pending", "Pending review", "pending"), ("returned", "Returned", "returned"), ("conflict", "Conflict", "conflict"), ("missing", "Not reported", "missing"))]
    return Div(
        Div(
                Div(Span(f"Reporting coverage · Sunday Worship · {_short_date(occurrence)}", cls="analytics-kicker"), H2(f"{received} of {n_expected} locations have submitted", cls="analytics-coverage-title")),
            P("Totals include pending reports." if include_pending else "Population totals use approved reports only.", cls="analytics-note analytics-align-right"),
            cls="analytics-coverage-head",
        ),
        Div(*bars, cls="analytics-coverage-track"),
        Div(*legend, cls="analytics-coverage-legend"),
        cls="panel analytics-coverage-panel",
    )


def _children_table(children: list[dict[str, Any]], rows: list[dict[str, Any]], level: str, ctx: Any) -> Any:
    child_label = {"State": "Region", "Region": "Group", "Group": "Location"}.get(level, "Location")
    cells = []
    for child, report in zip(children, rows):
        path = str(child.get("path") or "")
        overview = report.get("overview") or {}
        coverage = _coverage_values(overview)
        expected = _integer(overview.get("n_expected"))
        received = _integer(overview.get("n_received"))
        total = overview.get("total")
        counted = _integer(overview.get("n_counted"))
        average = round(_integer(total) / counted) if total is not None and counted else None
        expected_population = overview.get("expected_population_total")
        expected_pct = overview.get("expected_population_percent")
        expected_note = f"{_integer(overview.get('expected_population_counted_locations'))} counted" if expected_population is not None else "No estimate for counted reports"
        no_estimate = _integer(overview.get("expected_population_no_estimate_locations"))
        label = str(child.get("name") or child.get("label") or format_scope_display_id(path) or "Location")
        link = _scope_dashboard_link(ctx, path)
        hx_link = _scope_dashboard_link(ctx, path, fragment=True)
        report_state = f"{received}/{expected} reported"
        latest = "No counted report" if total is None else ("Reported 0" if _integer(total) == 0 else _number(total))
        cells.append(Tr(
            Td(A(label, href=link, hx_get=hx_link, hx_push_url=link, hx_target="#analytics-dashboard-body", hx_swap="outerHTML", cls="analytics-child-link"), Span(format_scope_display_id(path), cls="analytics-muted analytics-code")),
            Td(Div(Div(cls="analytics-mini-track", style=f"--coverage:{100 * received / max(expected, 1):.2f}%"), Span(report_state, cls="analytics-muted"), cls="analytics-mini-coverage")),
            Td(latest, cls="text-end analytics-numeric"),
            Td("—" if average is None else _number(average), cls="text-end analytics-numeric"),
            Td("—" if expected_population is None else f"{_number(expected_population)} expected", cls="text-end analytics-numeric", title=expected_note),
            Td("—" if expected_pct is None else f"{float(expected_pct):.1f}%", cls="text-end analytics-numeric", title=f"{expected_note}; {no_estimate} locations without an estimate"),
            Td(f"{coverage['pending']} pending" if coverage["pending"] else "", cls="text-end analytics-muted"),
            Td(
                Div(Span("Latest report", cls="analytics-mobile-key"), latest),
                Div(Span("Average per location", cls="analytics-mobile-key"), "—" if average is None else _number(average)),
                Div(Span("Documented population", cls="analytics-mobile-key"), "—" if expected_population is None else _number(expected_population)),
                Div(Span("% of documented population", cls="analytics-mobile-key"), "—" if expected_pct is None else f"{float(expected_pct):.1f}%"),
                *([Div(Span("Review", cls="analytics-mobile-key"), f"{coverage['pending']} pending")] if coverage["pending"] else []),
                cls="analytics-mobile-numbers",
            ),
            cls="analytics-row",
            data_dashboard_href=link,
        ))
    if not cells:
        cells = [Tr(Td("No lower locations are available in this scope.", colspan="7", cls="analytics-muted"))]
    return Div(
        Div(H2(f"{child_label}s in this scope", cls="analytics-panel-title"), P("Select a name to open its dashboard. Figures use approved Sunday reports.", cls="analytics-note"), cls="analytics-panel-head"),
        Div(Table(Thead(Tr(Th(child_label), Th("Latest Sunday report"), Th("Counted population", cls="text-end"), Th("Average per location", cls="text-end"), Th("Expected Sunday attendance", cls="text-end"), Th("% of expected", cls="text-end"), Th("Review", cls="text-end"))), Tbody(*cells), cls="analytics-table"), P("Swipe to see more columns", cls="analytics-scroll-hint"), cls="analytics-table-wrap analytics-child-table-wrap"),
        cls="panel analytics-table-panel",
    )


def _location_history_table(history: list[dict[str, Any]], dates: list[date], location_id: str = "") -> Any:
    cells = []
    for when, report in zip(reversed(dates), reversed(history)):
        coverage = _coverage_values(report)
        raw_coverage = report.get("coverage") or {}
        total = report.get("total")
        if coverage["approved"]:
            state = "Included in combined report" if _integer(raw_coverage.get("combined")) and total is None else "Approved"
        elif coverage["pending"]:
            state = "Pending review"
        elif coverage["conflict"]:
            state = "Conflicting split count"
        elif coverage["returned"]:
            state = "Returned for correction"
        else:
            state = "Not reported"
        if total is not None:
            population = "Reported 0" if _integer(total) == 0 else _number(total)
        elif coverage["pending"]:
            population = "Awaiting approval"
        elif coverage["approved"] and _integer(raw_coverage.get("combined")):
            population = "No separate location total"
        elif coverage["conflict"]:
            population = "Conflict; no counted result"
        elif coverage["returned"]:
            population = "Returned; no counted result"
        else:
            population = "Not reported"
        expected = (report.get("location_expected_values") or {}).get(location_id)
        expected_pct = (100 * _integer(total) / expected) if total is not None and expected else None
        cells.append(Tr(Td(when.strftime("%d %b %Y").lstrip("0")), Td(state), Td(population, cls="text-end analytics-numeric"), Td("No estimate" if expected is None else _number(expected), cls="text-end analytics-numeric"), Td("—" if expected_pct is None else f"{expected_pct:.1f}%", cls="text-end analytics-numeric")))
    return Div(
        Div(H2("Last 8 Sunday Worship records", cls="analytics-panel-title"), P("Each Sunday is shown separately. Not reported and an explicit zero are different states.", cls="analytics-note"), cls="analytics-panel-head"),
        Div(Table(Thead(Tr(Th("Sunday"), Th("Report state"), Th("Population", cls="text-end"), Th("Expected Sunday attendance", cls="text-end"), Th("% of expected", cls="text-end"))), Tbody(*cells), cls="analytics-table"), cls="analytics-table-wrap"),
        cls="panel analytics-table-panel",
    )


def _dashboard_error_panel(title: str, error: str) -> Any:
    return Div(P(title, cls="analytics-error-title"), P(error, cls="analytics-error-message"), role="alert", cls="analytics-error panel")


def _review_attention_note(level: str, *, panel_id: str | None = None) -> Div:
    approver = {"Location": "Group Pastor", "Group": "Region Pastor", "Region": "State Overseer"}.get(level)
    if level == "Location":
        message = "Reports from your location are approved by your Group Pastor."
    elif approver:
        message = f"Reports from this {level.lower()} are reviewed by the {approver}."
    else:
        message = "State-level reports are auto-accepted when submitted."
    return Div(H2("Review responsibility", cls="analytics-panel-title"), P(message, cls="analytics-note mb-0"), id=panel_id, cls="panel analytics-attention-panel" if panel_id is None else "panel analytics-attention-panel analytics-lazy-panel")


def _dashboard_loading_panel(label: str) -> Any:
    return Div(Span(cls="spinner-border spinner-border-sm me-2", role="status"), P(f"Loading {label}…", cls="mb-0"), aria_live="polite", cls="panel analytics-loading-panel")


def _dashboard_panels_url(ctx: Any, path: str, *, fragment: bool = False) -> str:
    # Panel routes return a fragment to HTMX. Keep the selected scope and both
    # dashboard filters on that request; plain page links keep their own URL.
    return scope_link(
        ctx,
        "/dashboard/panels",
        weeks=str((ctx.query_extras or {}).get("weeks") or "4"),
        include_pending=str((ctx.query_extras or {}).get("include_pending") or "false"),
    )


def _path_within(path: str, scope_path: str) -> bool:
    path = str(path or "").strip(".").lower()
    scope_path = str(scope_path or "").strip(".").lower()
    return bool(path and scope_path and (path == scope_path or path.startswith(scope_path + ".")))


def _scope_dashboard_link(ctx: Any, path: str, *, fragment: bool = False) -> str:
    full_url = scope_link(ctx, "/dashboard", scope_path=path)
    if not fragment:
        return full_url
    from urllib.parse import urlsplit, urlunsplit

    parts = urlsplit(full_url)
    return urlunsplit((parts.scheme, parts.netloc, "/dashboard/content", parts.query, parts.fragment))


def _scope_breadcrumb(ctx: Any, ancestors: list[dict[str, Any]], selected_path: str) -> Any:
    maximum = str((ctx.query_extras or {}).get("home_path") or ctx.profile.root_path or selected_path)
    selected_parts = [part for part in selected_path.split(".") if part]
    maximum_parts = [part for part in maximum.split(".") if part]
    paths = [".".join(selected_parts[:depth]) for depth in range(len(maximum_parts), len(selected_parts) + 1)]
    paths = [path for path in paths if _path_within(path, maximum)]
    if len(paths) <= 1:
        return None
    names = {str(item.get("path") or ""): str(item.get("name") or "") for item in ancestors}
    crumbs = []
    for index, path in enumerate(paths):
        if not _path_within(path, maximum):
            continue
        label = names.get(path) or (ctx.current_scope_label if path == selected_path else format_scope_display_id(path)) or path.rsplit(".", 1)[-1]
        if path == selected_path:
            crumbs.append(Span(label, aria_current="location", cls="analytics-crumb analytics-crumb-current"))
        else:
            href = _scope_dashboard_link(ctx, path)
            hx_href = _scope_dashboard_link(ctx, path, fragment=True)
            crumbs.append(A(label, href=href, hx_get=hx_href, hx_push_url=href, hx_target="#analytics-dashboard-body", hx_swap="outerHTML", cls="analytics-crumb"))
        if index < len(paths) - 1:
            crumbs.append(Span("›", aria_hidden="true", cls="analytics-crumb-separator"))
    return Div(*crumbs, role="navigation", aria_label="Dashboard scope breadcrumb", cls="analytics-scope-breadcrumb")


def _attention_panel(
    payload: dict[str, Any], queue: list[dict[str, Any]], children: list[dict[str, Any]],
    child_reports: list[dict[str, Any]], series: dict[str, Any], ctx: Any,
    occurrence: date, program_type_id: Any,
) -> Any:
    scope_path = ctx.current_scope_path
    nodes = {str(item.get("location_id") or ""): item for item in series.get("location_nodes", []) if item.get("location_id")}
    missing_nodes = {str(item.get("location_id") or ""): item for item in series.get("missing_locations", []) if item.get("location_id")}
    items: list[tuple[int, Any]] = []
    for child, report in zip(children, child_reports):
        overview = report.get("overview") or {}
        values = _coverage_values(overview)
        expected, missing = _integer(overview.get("n_expected")), values["missing"]
        label = str(child.get("name") or "Reporting scope")
        child_path = str(child.get("path") or "")
        if missing:
            text = f"{label}: {missing} of {expected} locations did not report"
            link = _scope_dashboard_link(ctx, child_path)
            hx_link = _scope_dashboard_link(ctx, child_path, fragment=True)
            title = A(text, href=link, hx_get=hx_link, hx_push_url=link, hx_target="#analytics-dashboard-body", hx_swap="outerHTML", cls="analytics-attention-title")
            missing_under_child = [
                (location_id, row) for location_id, row in missing_nodes.items()
                if _path_within(str(row.get("path") or ""), child_path)
            ]
            remind_control = None
            if ctx.has_permission("counts:remind") and missing_under_child:
                is_location = _scope_level(child_path, "") == "Location"
                remind_label = "Remind" if is_location else "Remind all"
                if is_location:
                    location_id, _row = missing_under_child[0]
                    remind_control = Form(
                        Input(type="hidden", name="location_id", value=location_id),
                        Input(type="hidden", name="program_type_id", value=str(program_type_id or "")),
                        Input(type="hidden", name="occurrence_date", value=occurrence.isoformat()),
                        Button(remind_label, type="submit", variant="outline-primary", size="sm"),
                        hx_post=scope_link(ctx, "/dashboard/remind", scope_path=scope_path),
                        hx_target="#analytics-attention-panel", hx_swap="outerHTML",
                        cls="analytics-remind-form",
                    )
                else:
                    remind_control = Form(
                        Input(type="hidden", name="child_path", value=child_path),
                        Input(type="hidden", name="program_type_id", value=str(program_type_id or "")),
                        Input(type="hidden", name="occurrence_date", value=occurrence.isoformat()),
                        Button(remind_label, type="submit", variant="outline-primary", size="sm"),
                        hx_post=scope_link(ctx, "/dashboard/remind-all", scope_path=scope_path),
                        hx_target="#analytics-attention-panel", hx_swap="outerHTML",
                        cls="analytics-remind-form",
                    )
            items.append((100, Div(Span(cls="analytics-attention-dot missing"), Div(title, Span(f"{missing} locations · Sunday Worship · {occurrence.isoformat()}", cls="analytics-muted analytics-attention-meta"), remind_control, cls="analytics-attention-copy"), cls="analytics-attention-item")))
        if values["returned"]:
            link, hx_link = _scope_dashboard_link(ctx, child_path), _scope_dashboard_link(ctx, child_path, fragment=True)
            title = A(f"{label}: {values['returned']} returned reports", href=link, hx_get=hx_link, hx_push_url=link, hx_target="#analytics-dashboard-body", hx_swap="outerHTML", cls="analytics-attention-title")
            items.append((85, Div(Span(cls="analytics-attention-dot returned"), Div(title, P("Returned for correction · Sunday Worship", cls="analytics-muted"), cls="analytics-attention-copy"), cls="analytics-attention-item")))
        histories = child.get("history") or []
        if len(histories) >= 2:
            comparable, drop_pct = _pooled_decline(histories[-2], histories[-1])
            link, hx_link = _scope_dashboard_link(ctx, child_path), _scope_dashboard_link(ctx, child_path, fragment=True)
            if drop_pct is None and comparable < ATTENTION_MIN_COMPARABLE_LOCATIONS:
                title = A(f"{label}: Too few locations to compare", href=link, hx_get=hx_link, hx_push_url=link, hx_target="#analytics-dashboard-body", hx_swap="outerHTML", cls="analytics-attention-title")
                items.append((10, Div(Span(cls="analytics-attention-dot"), Div(title, P(f"{comparable} comparable locations; at least {ATTENTION_MIN_COMPARABLE_LOCATIONS} required", cls="analytics-muted"), cls="analytics-attention-copy"), cls="analytics-attention-item")))
            elif drop_pct is not None and drop_pct >= ATTENTION_DECLINE_PCT:
                drop = round(drop_pct)
                title = A(f"{label}: Down {drop}%", href=link, hx_get=hx_link, hx_push_url=link, hx_target="#analytics-dashboard-body", hx_swap="outerHTML", cls="analytics-attention-title")
                items.append((70, Div(Span(cls="analytics-attention-dot decline"), Div(title, P(f"{comparable} locations compared · pooled attendance", cls="analytics-muted"), cls="analytics-attention-copy"), cls="analytics-attention-item")))

    pending_by_child: dict[str, dict[str, Any]] = {}
    for row in queue:
        report_path = str(row.get("program_scope_path") or "")
        location = nodes.get(str(row.get("location_id") or ""))
        if not report_path and location:
            report_path = str(location.get("path") or "")
        if report_path and not _path_within(report_path, scope_path):
            continue
        target_child = next(
            (str(child.get("path") or "") for child in children if report_path and _path_within(report_path, str(child.get("path") or ""))),
            scope_path,
        )
        bucket = pending_by_child.setdefault(target_child, {"count": 0, "age": 0, "label": ""})
        bucket["count"] += 1
        age = _integer(row.get("age_hours"))
        bucket["age"] = max(bucket["age"], age)
    for child_path, bucket in pending_by_child.items():
        child = next((item for item in children if str(item.get("path") or "") == child_path), None)
        label = str((child or {}).get("name") or ctx.current_scope_label or "Combined reports")
        href, hx_href = _scope_dashboard_link(ctx, child_path), _scope_dashboard_link(ctx, child_path, fragment=True)
        age = int(bucket["age"])
        flags = " · 24+ hours" if age >= 24 else (" · 10+ hours" if age >= 10 else "")
        title = A(f"{label}: {bucket['count']} pending count group(s)", href=href, hx_get=hx_href, hx_push_url=href, hx_target="#analytics-dashboard-body", hx_swap="outerHTML", cls="analytics-attention-title")
        items.append((95 if age >= 24 else 80 if age >= 10 else 50, Div(Span(cls="analytics-attention-dot pending"), Div(title, P(f"Oldest waiting {_age_label(age)}{flags}", cls="analytics-muted analytics-attention-meta"), cls="analytics-attention-copy"), cls="analytics-attention-item")))

    if ctx.has_permission("counts:review") and program_type_id and _scope_level(scope_path, ctx.current_scope_kind.title()) == "Location":
        for location_id, row in missing_nodes.items():
            if not _path_within(str(row.get("path") or ""), scope_path):
                continue
            href, hx_href = _scope_dashboard_link(ctx, str(row["path"])), _scope_dashboard_link(ctx, str(row["path"]), fragment=True)
            status_id = f"remind-status-{escape(location_id)}"
            reminded_at = row.get("reminded_at")
            if reminded_at is not None:
                if reminded_at.tzinfo is None:
                    reminded_at = reminded_at.replace(tzinfo=timezone.utc)
                hours_ago = max(int((datetime.now(timezone.utc) - reminded_at).total_seconds() // 3600), 0)
                elapsed_label = "less than 1h ago" if hours_ago == 0 else f"{hours_ago}h ago"
                action = P(f"Reminded {elapsed_label}", cls="small text-muted analytics-remind-form")
            elif ctx.has_permission("counts:remind"):
                action = Form(
                    Input(type="hidden", name="location_id", value=location_id),
                    Input(type="hidden", name="program_type_id", value=str(program_type_id)),
                    Input(type="hidden", name="occurrence_date", value=occurrence.isoformat()),
                    Button("Remind", type="submit", variant="outline-primary", size="sm"),
                    hx_post=scope_link(ctx, "/dashboard/remind", scope_path=scope_path), hx_target=f"#{status_id}", hx_swap="innerHTML", cls="analytics-remind-form",
                )
            else:
                action = P("Reminders are unavailable for this role.", cls="small text-muted analytics-remind-form")
            title = A(str(row.get("name") or "Location"), href=href, hx_get=hx_href, hx_push_url=href, hx_target="#analytics-dashboard-body", hx_swap="outerHTML", cls="analytics-attention-title")
            items.append((60, Div(Span(cls="analytics-attention-dot missing"), Div(title, P("No Sunday Worship report received", cls="analytics-muted"), action, Div(id=status_id, role="status", cls="analytics-remind-status"), cls="analytics-attention-copy"), cls="analytics-attention-item")))

    items.sort(key=lambda pair: pair[0], reverse=True)
    hidden_count = max(len(items) - 5, 0)
    if not items:
        rendered = P("No overdue reviews, returned reports, major declines, or missing Sunday reports in this scope.", cls="analytics-muted")
    else:
        visible = [item for _rank, item in items[:5]]
        remaining = [item for _rank, item in items[5:]]
        rendered = Div(
            Div(*visible, cls="analytics-attention-list"),
            *([Details(Summary(f"Show all ({len(items)})"), Div(*remaining, cls="analytics-attention-list"), cls="analytics-show-all")] if hidden_count else []),
        )
    return Div(H2("Needs attention", cls="analytics-panel-title"), P(f"Missing locations, pending reviews, returned reports, and declines of {ATTENTION_DECLINE_PCT}% or more.", cls="analytics-note"), rendered, id="analytics-attention", cls="panel analytics-attention-panel")


async def render_analytics_dashboard(request: Request, ctx: Any) -> Any:
    trace, trace_token = dashboard_perf.start_trace()
    render_started = time.perf_counter()
    try:
        ctx = active_scope_context(request, ctx)
    except Exception as exc:
        from starlette.exceptions import HTTPException

        if not isinstance(exc, HTTPException):
            raise
        result = Div(
            Div(P(f"Scope request refused ({exc.status_code})", cls="analytics-error-title"), P(str(exc.detail), cls="analytics-error-message"), id="analytics-dashboard-error", role="alert", cls="analytics-error panel"),
            id="analytics-dashboard-body", cls="prototype-dashboard",
        )
        dashboard_perf.finish_trace(trace, trace_token, render_ms=(time.perf_counter() - render_started) * 1000, request=request)
        return result
    DashboardService.configure_bootstrap_sections(request, ("summary", "attendance_summary"))
    scope_path = await DashboardService.scope_path(request, ctx)
    scope_label = ctx.current_scope_label
    level = _scope_level(scope_path, ctx.current_scope_kind.title())
    weeks = int(request.query_params.get("weeks") or 4)
    if weeks not in {4, 8}:
        weeks = 4
    include_pending = str(request.query_params.get("include_pending") or "").lower() in {"true", "1"}
    ctx.query_extras["include_pending"] = "true" if include_pending else "false"
    ctx.query_extras["weeks"] = str(weeks)
    latest = _lagos_sunday()
    data_weeks = 8 if level == "Location" else weeks
    dates = [latest - timedelta(weeks=index) for index in reversed(range(data_weeks))]

    queue: list[dict[str, Any]] = []

    phase_started = time.perf_counter()
    dashboard_payload = await DashboardService.sunday_worship_dashboard(
        request, ctx, weeks=data_weeks, scope_path=scope_path, latest_date=latest.isoformat(),
    )
    dashboard_perf.timed_phase(trace, "dashboard_overview_single_backend_call", phase_started)
    series = dashboard_payload.get("series") if isinstance(dashboard_payload, dict) else None
    payload = dashboard_payload.get("bootstrap") if isinstance(dashboard_payload, dict) else None
    if isinstance(dashboard_payload, dict) and dashboard_payload.get("error"):
        series = {"error": dashboard_payload["error"]}
    if isinstance(series, dict) and series.get("error"):
        message = str(series.get("error") or "The dashboard data service refused the request.")
        result = Div(
            Div(P("Dashboard data could not be loaded", cls="analytics-error-title"), P(message, cls="analytics-error-message"), id="analytics-dashboard-error", role="alert", cls="analytics-error panel"),
            id="analytics-dashboard-body", cls="prototype-dashboard",
        )
        dashboard_perf.finish_trace(trace, trace_token, render_ms=(time.perf_counter() - render_started) * 1000, request=request)
        return result
    history = series.get("scope") if isinstance(series.get("scope"), list) else []
    history = history[-data_weeks:]
    current = history[-1] if history else {}
    payload = payload or {}
    children = series.get("children") if isinstance(series.get("children"), list) else []
    children = [row for row in children if row.get("path")]
    child_reports = [{"overview": (row.get("history") or [{}])[-1]} for row in children]

    worker_summary = payload.get("worker_analytics") or {}
    attendance_summary = payload.get("attendance_summary") or {}
    summary = payload.get("summary") or {}
    offering_summary = summary.get("approved_offerings") or {}
    record_summary = summary.get("newcomer_period") or {}

    trend_points = []
    for when, report in zip(dates, history):
        counted = _integer(report.get("n_counted"))
        total = report.get("total")
        trend_points.append({"date": when.isoformat(), "counted": counted, "expected": _integer(report.get("n_expected")), "average": round(_integer(total) / counted) if total is not None and counted else None})
    selected_trend = trend_points[-weeks:]
    valid = [point for point in selected_trend if point["average"] is not None]
    avg = round(sum(point["average"] for point in valid) / len(valid)) if valid else None
    counted_total = _integer(current.get("total"))
    multiple_services = current.get("service_reports") or []
    population_value = ("See services below" if multiple_services and current.get("total") is None else "No counted report" if current.get("total") is None else _number(counted_total))
    active_workers = _integer(worker_summary.get("active"))
    awaiting_workers = _integer(worker_summary.get("pending_verification"))
    suspended_workers = _integer(worker_summary.get("suspended"))
    total_workers = _integer(worker_summary.get("total"))
    other_workers = max(total_workers - active_workers - awaiting_workers - suspended_workers, 0)
    expected_attendance = _integer(attendance_summary.get("expected"))
    present_attendance = _integer(attendance_summary.get("present"))
    attendance_note = "Not enough roster data yet." if expected_attendance else "No attendance submission in this scope."
    ancestors = series.get("ancestors") if isinstance(series.get("ancestors"), list) else []
    named_scope = next((str(item.get("name")) for item in ancestors if item.get("path") == scope_path and item.get("name")), scope_label)
    worker_note = f"{active_workers} active · {awaiting_workers} awaiting approval · {suspended_workers} suspended · {other_workers} inactive/other · {total_workers} on register."
    expected_percent = current.get("expected_population_percent")
    expected_total = current.get("expected_population_total")
    if not _integer(current.get("locations_with_estimate")):
        expected_value, expected_note = "No estimates yet", "Expected Sunday attendance has not been entered for locations in this scope."
    elif expected_percent is None:
        expected_value, expected_note = "No eligible report", "No counted location report has both an estimate and an attendance count."
    else:
        expected_value = f"{float(expected_percent):.1f}%"
        expected_note = (
            f"Pooled: {_number(current.get('expected_population_counted_total'))} counted / "
            f"{_number(expected_total)} expected across {current.get('expected_population_counted_locations', 0)} locations; "
            f"{current.get('expected_population_no_estimate_locations', 0)} counted locations have no estimate."
        )
    can_manage_expected = level == "State" and ctx.level == 5 and ctx.has_permission("population_estimates:manage")
    offerings_current = float(offering_summary.get("current_total") or 0)
    offerings_previous = float(offering_summary.get("previous_total") or 0)
    offerings_records = _integer(offering_summary.get("current_records"))
    offerings_value = f"₦{offerings_current:,.2f}" if offerings_records else "No approved reports"
    offerings_note = (
        f"{_number(offerings_records)} approved records · "
        + _period_delta(offerings_current, offerings_previous, previous_records=_integer(offering_summary.get("previous_records")), noun=f"{weeks} Sundays")
    )
    newcomers_current = _integer(record_summary.get("newcomers_current"))
    converts_current = _integer(record_summary.get("converts_current"))
    newcomers_previous = _integer(record_summary.get("newcomers_previous"))
    converts_previous = _integer(record_summary.get("converts_previous"))
    newcomers_note = _period_delta(newcomers_current, newcomers_previous, previous_records=newcomers_previous, noun=f"{weeks} Sundays")
    converts_note = _period_delta(converts_current, converts_previous, previous_records=converts_previous, noun=f"{weeks} Sundays")
    dashboard_url = "/dashboard"
    filters = Form(
        Input(type="hidden", name="profile", value=ctx.profile.key),
        Input(type="hidden", name="scope_path", value=scope_path),
        Input(type="hidden", name="weeks", value=str(weeks)),
        Input(type="hidden", name="include_pending", value="true" if include_pending else "false"),
        Div(Span("Signed in as", cls="analytics-filter-label"), Span(f"{ctx.profile.role_label} (level {ctx.level})", cls="analytics-filter-persona"), cls="analytics-filter-persona-wrap"),
        Div(Span("Reporting window", cls="analytics-filter-label"), A("4 weeks", href=scope_link(ctx, dashboard_url, weeks="4", include_pending="true" if include_pending else "false"), cls="analytics-period" + (" active" if weeks == 4 else "")), A("8 weeks", href=scope_link(ctx, dashboard_url, weeks="8", include_pending="true" if include_pending else "false"), cls="analytics-period" + (" active" if weeks == 8 else "")), cls="analytics-filter-period"),
        Label(Input(type="checkbox", checked=include_pending, cls="form-check-input", onchange="this.form.elements.include_pending.value=this.checked?'true':'false';this.form.requestSubmit()"), "Count reports pending review", cls="analytics-pending-switch"),
        action="/dashboard", method="get", cls="analytics-toolbar", id="analytics-dashboard-filters",
    )
    # The filter form submits the current jurisdiction path; scope authorization remains enforced by active_scope_context.
    result = Div(
        Script("""
        (function(){
          if (window.__dclmAnalyticsRowNavigation) return;
          window.__dclmAnalyticsRowNavigation = true;
          document.addEventListener('click', function(event){
            var row = event.target.closest('tr.analytics-row[data-dashboard-href]');
            if (!row || event.target.closest('a,button,input,select,textarea,summary')) return;
            var link = row.querySelector('a.analytics-child-link');
            if (link) link.click();
          });
        })();
        """),
        Div(
            filters,
            Main(
                _scope_breadcrumb(ctx, ancestors, scope_path),
                Div(
                    P(f"{level.upper()}", cls="analytics-eyebrow"),
                    H1(named_scope, cls="analytics-title"),
                    P(
                        f"Sunday Worship · week of {latest.strftime('%d %b %Y').lstrip('0')} · ",
                        "Including reports pending review" if include_pending else "Approved reports only",
                        Span("Demo data", cls="analytics-demo-label") if not get_backend_config().enabled else None,
                        cls="analytics-subtitle",
                    ),
                    A("Expected attendance", href="/analytics/expected-population", cls="analytics-expected-link") if can_manage_expected else None,
                    cls="analytics-heading",
                ),
                _coverage_panel(current, latest, include_pending),
                Div(
                    H2("Sunday services reported separately", cls="h6"),
                    Table(
                        Thead(Tr(Th("Location"), Th("Service / session"), Th("Population", cls="text-end"))),
                        Tbody(*(Tr(Td(item.get("location_name") or scope_label), Td(item.get("service_id") or "main"), Td("Not counted" if item.get("counted_population") is None else _number(item.get("counted_population")), cls="text-end")) for item in multiple_services)),
                        cls="analytics-table",
                    ),
                    cls="analytics-panel analytics-service-breakdown",
                ) if multiple_services else None,
                Div(
                    _metric("Latest Sunday population", population_value, "Multiple services reported separately; no daily total is defined." if multiple_services else f"{_integer(current.get('n_counted'))} locations counted · {_short_date(latest)}", "Adds up"),
                    _metric("% of expected Sunday attendance", expected_value, expected_note, "Pooled"),
                    _metric(f"Average per reporting location · {weeks} weeks", "—" if avg is None else _number(avg), "Mean of the weekly per-location averages in this period; weeks without a counted report are excluded.", "Recomputed"),
                    _metric("Active workers", _number(active_workers), worker_note, "Snapshot"),
                    _metric("Workers’ meeting attendance rate", "Rate withheld" if expected_attendance else "No report", attendance_note, "Roster check"),
                    _metric(f"Approved offerings · last {weeks} Sundays", offerings_value, offerings_note, "Approved only"),
                    _metric(f"Newcomers · last {weeks} Sundays", _number(newcomers_current), newcomers_note, "Reports"),
                    _metric(f"Converts · last {weeks} Sundays", _number(converts_current), converts_note, "Reports"),
                    cls="analytics-metrics",
                ),
                    Div(
                        Div(_dashboard_loading_panel("locations" if level == "Location" else "child scopes"), id="analytics-children-panel", hx_get=_dashboard_panels_url(ctx, "/dashboard/panels"), hx_trigger="load", hx_target="this", hx_swap="innerHTML", cls="analytics-lazy-panel", aria_busy="true"),
                        Div(_dashboard_loading_panel("Needs attention"), id="analytics-attention-panel", cls="analytics-lazy-panel", aria_busy="true") if (ctx.has_permission("counts:review") or ctx.has_permission("counts:remind")) else _review_attention_note(level, panel_id="analytics-attention-panel"),
                        _waiting_on_decision(summary, weeks),
                        cls="analytics-content-split",
                    ),
                Div(_dashboard_loading_panel("weekly trend"), id="analytics-trend-panel", cls="analytics-lazy-panel", aria_busy="true"),
                cls="analytics-dashboard-main",
            ),
            cls="prototype-dashboard",
        ),
        id="analytics-dashboard-body",
    )
    dashboard_perf.finish_trace(trace, trace_token, render_ms=(time.perf_counter() - render_started) * 1000, request=request)
    return result


async def render_analytics_dashboard_panel(request: Request, ctx: Any, panel: str) -> Any:
    """Load all deferred panels using one weekly-series request."""
    ctx = active_scope_context(request, ctx)
    scope_path = await DashboardService.scope_path(request, ctx)
    level = _scope_level(scope_path, ctx.current_scope_kind.title())
    weeks = int(request.query_params.get("weeks") or 4)
    latest = _lagos_sunday()
    data_weeks = 8 if level == "Location" else weeks
    dates = [latest - timedelta(weeks=index) for index in reversed(range(data_weeks))]
    panel_payload = await DashboardService.sunday_worship_dashboard_panels(
        request, ctx, weeks=data_weeks, scope_path=scope_path, latest_date=latest.isoformat(),
    )
    if not isinstance(panel_payload, dict) or panel_payload.get("error"):
        message = str((panel_payload or {}).get("error") or "Dashboard panels could not load.")
        error = _dashboard_error_panel("Dashboard panels could not load", message)
        return Div(error, Div(error, id="analytics-attention-panel", cls="analytics-lazy-panel", hx_swap_oob="outerHTML"), Div(error, id="analytics-trend-panel", cls="analytics-lazy-panel", hx_swap_oob="outerHTML"))
    series = panel_payload.get("series") or {}
    can_review = bool(panel_payload.get("can_review"))
    queue = panel_payload.get("review_groups") or []
    try:
        if not can_review:
            queue = []
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        error = _dashboard_error_panel("Dashboard panels could not load", message)
        return Div(error, Div(error, id="analytics-attention-panel", cls="analytics-lazy-panel", hx_swap_oob="outerHTML"), Div(error, id="analytics-trend-panel", cls="analytics-lazy-panel", hx_swap_oob="outerHTML"))
    if isinstance(series, dict) and series.get("error"):
        error = _dashboard_error_panel("Sunday Worship data could not load", str(series["error"]))
        return Div(error, Div(error, id="analytics-attention-panel", cls="analytics-lazy-panel", hx_swap_oob="outerHTML"), Div(error, id="analytics-trend-panel", cls="analytics-lazy-panel", hx_swap_oob="outerHTML"))
    history = (series.get("scope") or [])[-data_weeks:]
    children = [row for row in (series.get("children") or []) if row.get("path")]
    child_reports = [{"overview": (row.get("history") or [{}])[-1]} for row in children]
    current = history[-1] if history else {}
    if level == "Location":
        location_nodes = series.get("location_nodes") or []
        location_id = str(location_nodes[0].get("location_id") or "") if location_nodes else ""
        children_panel = _location_history_table(history, dates, location_id)
    else:
        children_panel = _children_table(children, child_reports, level, ctx)
    points = []
    for when, report in zip(dates, history):
        total, counted = report.get("total"), _integer(report.get("n_counted"))
        points.append({"date": when.isoformat(), "average": round(_integer(total) / counted) if total is not None and counted else None, "counted": counted, "expected": _integer(report.get("n_expected"))})
    trend_panel = Div(H2("Weekly trend", cls="analytics-panel-title"), P("Average population per reporting location and coverage of counted reports. Missing reports are not plotted as zero.", cls="analytics-note"), _line_chart(points, weeks), cls="panel analytics-trend-panel")
    if not can_review and not ctx.has_permission("counts:remind"):
        attention_panel = _review_attention_note(level, panel_id="analytics-attention-panel")
    else:
        attention_panel = _attention_panel(current, queue, children, child_reports, series, ctx, latest, series.get("program_type_id"))
    return Div(
        children_panel,
        Div(attention_panel, id="analytics-attention-panel", cls="analytics-lazy-panel", hx_swap_oob="outerHTML"),
        Div(trend_panel, id="analytics-trend-panel", cls="analytics-lazy-panel", hx_swap_oob="outerHTML"),
    )


def register_analytics_dashboard_panel_routes(app) -> None:
    @app.get("/dashboard/panels")
    async def analytics_dashboard_panels(request: Request):
        trace, token = dashboard_perf.start_trace()
        started = time.perf_counter()
        ctx = active_scope_context(request, build_context(request))
        try:
            return await render_analytics_dashboard_panel(request, ctx, "all")
        finally:
            dashboard_perf.finish_trace(
                trace, token,
                render_ms=(time.perf_counter() - started) * 1000,
                request=request,
            )
