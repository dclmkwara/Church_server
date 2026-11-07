from __future__ import annotations

import asyncio
from datetime import date, timedelta
from html import escape
from typing import Any

from fasthtml.common import A, Div, Form, H1, H2, H3, Input, Label, Link, Main, NotStr, P, Span, Table, Tbody, Td, Th, Thead, Tr
from faststrap import Badge, Button
from starlette.requests import Request

from ..backend import format_scope_display_id
from ..communication.api_client import get_api_client
from ..communication.async_compat import async_client
from ..communication.auth_service import AuthService
from ..communication.dashboard_service import DashboardService
from ..communication.active_scope import active_scope_context


def _integer(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _lagos_sunday(today: date | None = None) -> date:
    today = today or date.today()
    return today - timedelta(days=(today.weekday() + 1) % 7)


def _scope_level(path: str, fallback: str) -> str:
    depth = max(0, len([part for part in path.split(".") if part]) - 1)
    return {2: "State", 3: "Region", 4: "Group", 5: "Location"}.get(depth, fallback)


def _number(value: Any) -> str:
    return f"{_integer(value):,}"


def _short_date(value: date) -> str:
    return value.strftime("%d %b").lstrip("0")


def _coverage_values(payload: dict[str, Any]) -> dict[str, int]:
    coverage = payload.get("coverage") or {}
    return {
        "approved": _integer(coverage.get("approved")),
        "pending": _integer(coverage.get("pending")),
        "returned": _integer(coverage.get("returned")),
        "missing": sum(_integer(coverage.get(key)) for key in ("missing", "late", "awaiting")),
    }


def _line_chart(points: list[dict[str, Any]], selected_weeks: int) -> Any:
    shown = points[-selected_weeks:]
    width, height, left, right, top, bottom = 900, 230, 58, 18, 18, 35
    chart_w, chart_h = width - left - right, height - top - bottom
    values = [point["average"] for point in shown if point.get("average") is not None]
    maximum = max(values, default=0)
    scale_max = max(100, ((maximum + 99) // 100) * 100)
    coords: list[tuple[float, float | None, dict[str, Any]]] = []
    for index, point in enumerate(shown):
        x = left + (chart_w * index / max(len(shown) - 1, 1))
        average = point.get("average")
        y = None if average is None else top + chart_h - (chart_h * average / scale_max)
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
    grid = []
    for fraction in (0, 0.5, 1):
        y = top + chart_h * fraction
        label = round(scale_max * (1 - fraction))
        grid.append(Div(Span(_number(label), cls="analytics-chart-axis"), cls="analytics-chart-grid", style=f"top:{y / height * 100:.2f}%"))
    bars = []
    for index, (_x, _y, point) in enumerate(coords):
        share = min(100, round(100 * point["counted"] / point["expected"])) if point["expected"] else 0
        left_pct = index / max(len(coords) - 1, 1) * 100
        bars.append(Div(cls="analytics-coverage-bar", style=f"left:{left_pct:.2f}%;height:{share}%"))
    dates = [Div(point["date"][5:], cls="analytics-chart-date", style=f"left:{(left + chart_w * index / max(len(coords)-1, 1)) / width * 100:.2f}%") for index, (_, _, point) in enumerate(coords)]
    svg = f'<svg class="analytics-svg" viewBox="0 0 {width} {height}" role="img" aria-label="Average reported population by Sunday">'
    for fraction in (0, 0.5, 1):
        y = top + chart_h * fraction
        svg += f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="analytics-svg-grid" />'
        svg += f'<text x="0" y="{y+4:.1f}" class="analytics-svg-label">{round(scale_max * (1-fraction))}</text>'
    svg += "".join(f'<polyline points="{line}" class="analytics-svg-line" />' for line in polylines)
    svg += "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" class="analytics-svg-point" />' for x, y, point in coords if y is not None)
    svg += '</svg>'
    return Div(
        Div(NotStr(svg), cls="analytics-chart-plot"),
        Div(*bars, cls="analytics-chart-bars"),
        Div(*dates, cls="analytics-chart-dates"),
        P("Blue line: average population per counted location. Green bars: share of expected locations with a counted report. Gaps are not zero counts.", cls="analytics-legend small"),
        cls="analytics-chart",
        data_points=chart_paths,
        data_height=height,
    )


def _metric(label: str, value: str, note: str, badge: str) -> Any:
    return Div(
        Div(Span(label, cls="analytics-kicker"), Badge(badge, variant="light", cls="analytics-badge"), cls="analytics-card-head"),
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
    for key, label, css in (("approved", "Approved", "approved"), ("pending", "Pending review", "pending"), ("returned", "Returned", "returned"), ("missing", "Not reported", "missing")):
        count = parts[key]
        bars.append(Div(cls=f"analytics-coverage-segment {css}", style=f"width:{100 * count / total:.4f}%", title=f"{label}: {count}"))
    legend = [Span(Span(cls=f"analytics-dot {css}"), f"{label} {parts[key]}", cls="analytics-legend-item") for key, label, css in (("approved", "Approved", "approved"), ("pending", "Pending review", "pending"), ("returned", "Returned", "returned"), ("missing", "Not reported", "missing"))]
    return Div(
        Div(
                Div(Span(f"Reporting coverage · Sunday Worship · {_short_date(occurrence)}", cls="analytics-kicker"), H2(f"{received} of {n_expected} reporting units have submitted", cls="analytics-coverage-title")),
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
        label = str(child.get("name") or child.get("label") or format_scope_display_id(path) or "Reporting unit")
        link = ctx.url_for("/dashboard", scope_path=path)
        report_state = f"{received}/{expected} reported"
        latest = "No counted report" if total is None else ("Reported 0" if _integer(total) == 0 else _number(total))
        cells.append(Tr(
            Td(A(label, href=link, cls="analytics-child-link"), Span(format_scope_display_id(path), cls="analytics-muted analytics-code")),
            Td(Div(Div(cls="analytics-mini-track", style=f"--coverage:{100 * received / max(expected, 1):.2f}%"), Span(report_state, cls="analytics-muted"), cls="analytics-mini-coverage")),
            Td(latest, cls="text-end analytics-numeric"),
            Td("—" if average is None else _number(average), cls="text-end analytics-numeric"),
            Td(f"{coverage['pending']} pending" if coverage["pending"] else "", cls="text-end analytics-muted"),
            cls="analytics-row",
        ))
    if not cells:
        cells = [Tr(Td("No lower reporting units are available in this scope.", colspan="5", cls="analytics-muted"))]
    return Div(
        Div(H2(f"{child_label}s in this scope", cls="analytics-panel-title"), P("Open a row to inspect its next level. Figures use approved Sunday reports.", cls="analytics-note"), cls="analytics-panel-head"),
        Div(Table(Thead(Tr(Th(child_label), Th("Latest Sunday report"), Th("Counted population", cls="text-end"), Th("Average per location", cls="text-end"), Th("Review", cls="text-end"))), Tbody(*cells), cls="analytics-table"), cls="analytics-table-wrap"),
        cls="panel analytics-table-panel",
    )


def _location_history_table(history: list[dict[str, Any]], dates: list[date]) -> Any:
    cells = []
    for when, report in zip(reversed(dates), reversed(history)):
        coverage = _coverage_values(report)
        if coverage["approved"]:
            state = "Approved"
        elif coverage["pending"]:
            state = "Pending review"
        elif coverage["returned"]:
            state = "Returned for correction"
        else:
            state = "No report"
        total = report.get("total")
        population = "No counted report" if total is None else ("Reported 0" if _integer(total) == 0 else _number(total))
        cells.append(Tr(Td(when.strftime("%d %b %Y").lstrip("0")), Td(state), Td(population, cls="text-end analytics-numeric")))
    return Div(
        Div(H2("Recent Sunday Worship reports", cls="analytics-panel-title"), P("Each Sunday is shown separately. No report and an explicit zero are different states.", cls="analytics-note"), cls="analytics-panel-head"),
        Div(Table(Thead(Tr(Th("Sunday"), Th("Report state"), Th("Population", cls="text-end"))), Tbody(*cells), cls="analytics-table"), cls="analytics-table-wrap"),
        cls="panel analytics-table-panel",
    )


def _attention_panel(payload: dict[str, Any], queue: list[dict[str, Any]], ctx: Any) -> Any:
    coverage = _coverage_values(payload)
    items = []
    for item in queue[:5]:
        title = f"{item.get('location') or 'Reporting unit'} · {item.get('program_type') or 'Sunday Worship'}"
        age = _integer(item.get("age_hours"))
        items.append(Div(Span(cls="analytics-attention-dot pending"), Div(A(title, href=ctx.url_for("/church-data/count-review"), cls="analytics-attention-title"), P(f"{item.get('date')} · {item.get('submission_count', 1)} submission(s) · waiting {age}h", cls="analytics-muted")), cls="analytics-attention-item"))
    missing = coverage["missing"]
    if missing:
        items.append(Div(Span(cls="analytics-attention-dot missing"), Div(P(f"{missing} reporting unit(s) have no submitted report", cls="analytics-attention-title"), P("Sunday Worship · latest occurrence", cls="analytics-muted")), cls="analytics-attention-item"))
    if not items:
        items.append(P("No overdue count reviews or missing Sunday reports in the latest occurrence.", cls="analytics-muted"))
    return Div(H2("Needs attention", cls="analytics-panel-title"), P("Pending reviews and reporting gaps in this scope.", cls="analytics-note"), Div(*items, cls="analytics-attention-list"), cls="panel analytics-attention-panel")


async def render_analytics_dashboard(request: Request, ctx: Any) -> Any:
    ctx = active_scope_context(request, ctx)
    DashboardService.configure_bootstrap_sections(request, ("summary", "worker_analytics", "attendance_summary"))
    scope_path = await DashboardService.scope_path(request, ctx)
    scope_label = ctx.current_scope_label
    level = _scope_level(scope_path, ctx.current_scope_kind.title())
    weeks = int(request.query_params.get("weeks") or 4)
    if weeks not in {4, 8}:
        weeks = 4
    include_pending = str(request.query_params.get("include_pending") or "").lower() in {"true", "1"}
    latest = _lagos_sunday()
    dates = [latest - timedelta(weeks=index) for index in reversed(range(weeks))]

    client = async_client(get_api_client())
    access_token = AuthService.get_access_token(request)

    async def load_review_queue() -> list[dict[str, Any]]:
        """Keep the dashboard available when the optional review queue is down."""
        try:
            return await client.list_count_review_groups(access_token)
        except Exception:
            return []

    series, payload, queue = await asyncio.gather(
        DashboardService.sunday_worship_series(
            request, ctx, weeks=weeks, scope_path=scope_path, latest_date=latest.isoformat(),
        ),
        DashboardService.bootstrap_payload(request, ctx),
        load_review_queue(),
    )
    history = series.get("scope") if isinstance(series.get("scope"), list) else []
    history = history[-weeks:]
    current = history[-1] if history else {}
    payload = payload or {}
    children = series.get("children") if isinstance(series.get("children"), list) else []
    children = [row for row in children if row.get("path")]
    child_reports = [{"overview": (row.get("history") or [{}])[-1]} for row in children]

    worker_summary, attendance_summary = await asyncio.gather(
        DashboardService.worker_mix(request, ctx),
        DashboardService.attendance_summary(request, ctx),
    )
    queue = sorted(queue, key=lambda row: -float(row.get("age_hours") or 0))

    trend_points = []
    for when, report in zip(dates, history):
        counted = _integer(report.get("n_counted"))
        total = report.get("total")
        trend_points.append({"date": when.isoformat(), "counted": counted, "expected": _integer(report.get("n_expected")), "average": round(_integer(total) / counted) if total is not None and counted else None})
    series = trend_points[-weeks:]
    valid = [point for point in series if point["average"] is not None]
    avg = round(sum(point["average"] for point in valid) / len(valid)) if valid else None
    counted_total = _integer(current.get("total"))
    population_value = "No counted report" if current.get("total") is None else _number(counted_total)
    active_workers = _integer(worker_summary.get("active"))
    expected_attendance = _integer(attendance_summary.get("expected"))
    present_attendance = _integer(attendance_summary.get("present"))
    attendance_note = "Roster-based faithfulness rate withheld until split submissions deduplicate expected workers." if expected_attendance else "No attendance submission in this scope."
    filters = Form(
        Input(type="hidden", name="scope_path", value=scope_path),
        Input(type="hidden", name="weeks", value=str(weeks)),
        Div(Span("View as", cls="analytics-filter-label"), Span(f"{ctx.profile.role_label} (level {ctx.level})", cls="analytics-filter-persona"), cls="analytics-filter-persona-wrap"),
        Div(Span("Reporting window", cls="analytics-filter-label"), A("4 weeks", href=ctx.url_for("/dashboard", weeks="4", include_pending="true" if include_pending else None), cls="analytics-period" + (" active" if weeks == 4 else "")), A("8 weeks", href=ctx.url_for("/dashboard", weeks="8", include_pending="true" if include_pending else None), cls="analytics-period" + (" active" if weeks == 8 else "")), cls="analytics-filter-period"),
        Label(Input(type="checkbox", name="include_pending", value="true", checked=include_pending, cls="form-check-input"), "Count reports pending review", cls="analytics-pending-switch"),
        Button("Update", type="submit", variant="primary", size="sm"),
        action="/dashboard", method="get", cls="analytics-toolbar",
    )
    # The filter form submits the current jurisdiction path; scope authorization remains enforced by active_scope_context.
    return Div(
        Link(rel="stylesheet", href="/assets/css/analytics-dashboard.css?v=5"),
        Div(
            filters,
            Main(
                Div(P(f"{level.upper()} · {format_scope_display_id(scope_path)}", cls="analytics-eyebrow"), H1(scope_label, cls="analytics-title"), P(f"Sunday Worship · week of {latest.strftime('%d %b %Y').lstrip('0')} · figures from current development records", cls="analytics-subtitle"), cls="analytics-heading"),
                _coverage_panel(current, latest, include_pending),
                Div(
                    _metric("Latest Sunday population", population_value, f"{_integer(current.get('n_counted'))} reporting unit(s) counted · {_short_date(latest)}", "Adds up"),
                    _metric(f"Average per reporting location · {weeks} weeks", "—" if avg is None else _number(avg), "Recomputed from reported weeks; missing reports are omitted.", "Recomputed"),
                    _metric("Active workers", _number(active_workers), f"{_integer(worker_summary.get('total'))} workers on register in this scope.", "Snapshot"),
                    _metric("Workers’ meeting", "Rate withheld" if expected_attendance else "No report", attendance_note, "Roster check"),
                    cls="analytics-metrics",
                ),
                Div(_location_history_table(history, dates) if level == "Location" else _children_table(children, child_reports, level, ctx), _attention_panel(current, queue, ctx), cls="analytics-content-split"),
                Div(H2("Weekly trend", cls="analytics-panel-title"), P("Average population per reporting location and coverage of counted reports. Missing reports are not plotted as zero.", cls="analytics-note"), _line_chart(trend_points, weeks), cls="panel analytics-trend-panel"),
                cls="analytics-dashboard-main",
            ),
            cls="prototype-dashboard",
        ),
    )
