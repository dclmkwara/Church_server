from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from fasthtml.common import A, Button as HtmlButton, Div, Form, H3, H4, Input, Label, Li, Option, P, Select, Span, Textarea, Ul
from starlette.requests import Request

from faststrap import Button, Icon, Input as FsInput, Select as FsSelect, PlaceholderCard, Spinner, TabPane, Tabs, ToggleGroup

from ..auth_context import build_context
from ..backend import BackendClientError
from ..communication import PeopleService, ProgramService
from ..communication.dashboard_service import DashboardService
from ..communication.active_scope import active_scope_context
from ..communication.active_scope import scope_link
from ..communication.organization_service import OrganizationService
from ..components.chartjs import bar_chart as _bar_chart
from ..components.chartjs import donut_chart as _donut_chart
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, primary_button, shell_layout
from ..components.ui import empty_state, filter_field, page_intro, page_stack, responsive_table, section_card, stat_card, status_badge
from app.services.analytics.program_config import reporting_today
from app.core.program_page_perf import program_page_trace


EVENT_STATUSES = ["scheduled", "completed", "cancelled", "draft"]
CAMPAIGN_STATUSES = ["draft", "active", "closed", "archived"]
CAMPAIGN_MODES = ["crusade", "retreat", "special", "regular"]
ASSIGNMENT_TYPES = ["both", "count", "convert", "attendance", "all"]
ASSIGNMENT_SOURCE_ROLES = ["alpha", "satellite", "regular"]
AUDIENCE_SEGMENTS = ["adult", "campus", "youth", "children"]


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _pool_session_rows(rows: list[dict[str, Any]], *, metric: str) -> tuple[int, int, int]:
    """Return pooled current, prior and common counted reporter values."""
    current_reporters = {str(row.get("scope_path")): row for row in rows if row.get("scope_path")}
    current_counted = [row for row in rows if (row.get("report_state") == "counted" if metric == "attendance" else row.get("record_state") == "reported")]
    current_total = sum(_safe_int(row.get("counted_population")) if metric == "attendance" else _safe_int(row.get("converts")) for row in current_counted)
    return current_total, len(current_reporters), len(current_counted)


def _compare_common_reporters(current_rows: list[dict[str, Any]], prior_rows: list[dict[str, Any]], *, metric: str) -> tuple[int, int, int, int]:
    """Return full current cell, current/prior totals for common counted reporters, and n."""
    is_counted = lambda row: (row.get("report_state") == "counted") if metric == "attendance" else (row.get("record_state") == "reported")
    value = lambda row: _safe_int(row.get("counted_population")) if metric == "attendance" else _safe_int(row.get("converts"))
    current_by_path = {str(row.get("scope_path")): row for row in current_rows if row.get("scope_path")}
    prior_by_path = {str(row.get("scope_path")): row for row in prior_rows if row.get("scope_path")}
    full_current = sum(value(row) for row in current_rows if is_counted(row))
    common = set(current_by_path).intersection(prior_by_path)
    comparable = [path for path in common if is_counted(current_by_path[path]) and is_counted(prior_by_path[path])]
    return (
        full_current,
        sum(value(current_by_path[path]) for path in comparable),
        sum(value(prior_by_path[path]) for path in comparable),
        len(comparable),
    )


def _segment_label(value: str) -> str:
    return value.replace("_", " ").title() if value else "General"


def _chart_legend(rows: list[dict[str, Any]]) -> Any:
    return Div(
        *[
            Div(
                Div(cls="report-legend-swatch", style=f"background:{row['color']};"),
                Span(str(row["label"]), cls="small text-muted"),
                Span(str(row.get("display") or row.get("value") or ""), cls="small fw-semibold text-body-emphasis"),
                cls="report-legend-item",
            )
            for row in rows
        ],
        cls="report-legend mt-3",
    )


def _campaign_report_toggle(ctx, campaign_id: str, current_view: str) -> Any:
    target = "#campaign-report-panel"
    active_index = 0 if current_view != "summary" else 1
    return ToggleGroup(
        Button(
            "Chart",
            variant="outline-primary",
            size="sm",
            hx_get=ctx.url_for(f"/church-data/programs/campaigns/{campaign_id}/report-panel", view="chart"),
            hx_target=target,
            hx_swap="outerHTML",
            cls="inbox-filter-chip",
        ),
        Button(
            "Summary",
            variant="outline-primary",
            size="sm",
            hx_get=ctx.url_for(f"/church-data/programs/campaigns/{campaign_id}/report-panel", view="summary"),
            hx_target=target,
            hx_swap="outerHTML",
            cls="inbox-filter-chip",
        ),
        active_index=active_index,
        active_cls="active",
        cls="admin-toggle-group dashboard-view-toggle",
    )


def _occurrence_status(row: dict[str, Any], *, metric: str, mode: str, can_view_alpha: bool = False) -> Any:
    state = (row.get("record_state") or "no_report") if metric == "converts" else (row.get("report_state") or "no_report")
    if state == "no_report":
        return Span("No report", cls="small text-muted")
    if state == "pending":
        return Span("Pending review", cls="small text-warning-emphasis")
    if state == "returned":
        return Span("Returned", cls="small text-danger")
    if state == "conflict":
        return Span("Conflicting split count", cls="small text-danger fw-semibold")
    if metric == "converts":
        sources = row.get("record_sources") or {}
        alpha, satellite = _safe_int(sources.get("alpha")), _safe_int(sources.get("satellite"))
        total = _safe_int(row.get("converts"))
        if mode == "crusade" and not can_view_alpha:
            return Div(P(f"Satellite: {satellite:,} converts", cls="small mb-1"), P(f"Satellite participation: {satellite:,}", cls="fw-semibold mb-0"))
        return Div(
            P(f"Alpha: {alpha:,} · Satellites: {satellite:,}", cls="small mb-1"),
            P(f"Total participation: {total:,} converts", cls="fw-semibold mb-0"),
        )
    sources = row.get("sources") or {}
    if mode == "crusade":
        alpha, satellite = _safe_int(sources.get("alpha")), _safe_int(sources.get("satellite"))
        if not can_view_alpha:
            return Div(P(f"Satellite: {satellite:,}", cls="small mb-1"), P(f"Satellite participation: {satellite:,}", cls="fw-semibold mb-0"))
        return Div(
            P(f"Alpha: {alpha:,} · Satellites: {satellite:,}", cls="small mb-1"),
            P(f"Total participation: {_safe_int(row.get('counted_population')):,}", cls="fw-semibold mb-0"),
        )
    return P(f"{_safe_int(row.get('counted_population')):,}", cls="fw-semibold mb-0")


async def _render_event_matrix_page(request: Request, ctx, *, mode: str, campaign_id: str = "", event_id: str = "", metric: str = "attendance", include_pending: bool = False):
    domain_slug = "retreat" if mode == "retreat" else "global_crusade"
    campaigns = await ProgramService.list_analytics_campaigns(request, ctx, domain_slug=domain_slug, event_mode=mode)
    campaign_ids = {str(row.get("campaign_id")) for row in campaigns}
    today = reporting_today().isoformat()
    campaigns = sorted(campaigns, key=lambda row: str(row.get("start_date") or ""))
    if campaign_id not in campaign_ids:
        past = [row for row in campaigns if str(row.get("end_date") or row.get("start_date") or "") <= today]
        # Retreat landing is explicitly the most recent Easter retreat when
        # one exists; December remains available through the selector.
        if mode == "retreat":
            easter = [row for row in past if "easter" in str(row.get("title") or "").casefold()]
            if easter:
                past = easter
        selected = past[-1] if past else (campaigns[0] if campaigns else None)
        campaign_id = str(selected.get("campaign_id") or "") if selected else ""
    selected_campaign = next((row for row in campaigns if str(row.get("campaign_id")) == campaign_id), None)
    same_kind = [row for row in campaigns if row.get("event_mode") == mode and str(row.get("campaign_id")) != campaign_id]
    previous_campaign = max((row for row in same_kind if str(row.get("start_date") or "") < str((selected_campaign or {}).get("start_date") or "")), key=lambda row: str(row.get("start_date") or ""), default=None)
    compare_campaign_id = str(request.query_params.get("compare_campaign_id") or (previous_campaign or {}).get("campaign_id") or "")
    if compare_campaign_id not in {str(row.get("campaign_id")) for row in same_kind}:
        compare_campaign_id = ""
    occurrences_result = await ProgramService.occurrences(
        request, ctx, domain=domain_slug, campaign_id=campaign_id or None, compare_campaign_id=compare_campaign_id or None,
        include_pending=include_pending,
    )
    all_occurrences = occurrences_result.get("occurrences") or []
    occurrences = [row for row in all_occurrences if str(row.get("campaign_id")) == campaign_id]
    comparison = [row for row in all_occurrences if str(row.get("campaign_id")) == compare_campaign_id]
    by_id = {str(row["event_id"]): row for row in occurrences}
    can_view_alpha = len(str(getattr(ctx, "current_scope_path", "") or "").split(".")) == 3
    requested_type = str(request.query_params.get("program_type") or "")
    requested_day = str(request.query_params.get("date_from") or "")
    detail = by_id.get(event_id) or next((row for row in occurrences if requested_type and row.get("program_type_slug") == requested_type and row.get("date") == requested_day), None)
    if detail is None and mode == "retreat" and not requested_type and not requested_day:
        detail = next((row for row in occurrences if row.get("day_number") == 2 and "bible" in str(row.get("program_type_slug") or "").casefold()), None)
    days = sorted({str(row["date"]) for row in occurrences})
    types = sorted({(str(row["program_type_slug"]), str(row["program_type"])) for row in occurrences}, key=lambda item: item[1].casefold())
    matrix_rows = []
    scope_path = str(getattr(ctx, "current_scope_path", "") or "")
    scope_parts = scope_path.split(".")
    scope_depth = len(scope_parts)
    can_view_alpha = scope_depth == 3
    max_path = str((getattr(ctx, "query_extras", {}) or {}).get("home_path") or scope_path)
    max_depth = len(max_path.split("."))
    name_by_path = occurrences_result.get("scope_names") or {}
    crumb_paths = [".".join(scope_parts[:i]) for i in range(max_depth, scope_depth + 1)]
    crumbs = []
    for path in crumb_paths:
        if not path.startswith(max_path):
            continue
        name = name_by_path.get(path) or (ctx.current_scope_label if path == scope_path else path.rsplit(".", 1)[-1])
        if path == scope_path:
            crumbs.append(Span(name, cls="text-body-emphasis fw-semibold", aria_current="location"))
        else:
            target = scope_link(ctx, f"/church-data/programs/analytics/{mode}", scope_path=path, campaign_id=campaign_id, compare_campaign_id=compare_campaign_id, metric=metric, include_pending=str(include_pending).lower())
            crumbs.append(A(name, href=target, hx_get=target, hx_push_url=target, hx_target="#program-analytics-content", hx_swap="outerHTML", cls="link-primary text-decoration-none"))
        if path != crumb_paths[-1]:
            crumbs.append(Span(" › ", cls="text-muted"))
    for type_slug, type_name in types if not (mode == "retreat" and scope_depth > 4) else []:
        cells = [type_name]
        for day in days:
            matches = [row for row in occurrences if row["program_type_slug"] == type_slug and row["date"] == day]
            current = matches[0] if matches else None
            previous_matches = [row for row in comparison if row["program_type_slug"] == type_slug and current and row.get("day_number") == current.get("day_number")]
            if matches:
                current_counted = [r for r in matches if (r.get("report_state") == "counted" if metric == "attendance" else r.get("record_state") == "reported")]
                current_value = sum(_safe_int(r.get("counted_population")) if metric == "attendance" else _safe_int(r.get("converts")) for r in current_counted)
                comparison_current_value = current_value
                prior_value = 0
                compared_reporter_count = 0
                if mode != "crusade" and previous_matches and matches:
                    current_value, comparison_current_value, prior_value, compared_reporter_count = _compare_common_reporters(matches, previous_matches, metric=metric)
                if mode == "crusade" and previous_matches and matches:
                    def crusade_reporters(rows):
                        reporters = {}
                        for row in rows:
                            source_rows = row.get("location_reports") or [] if metric == "attendance" else row.get("record_reports") or []
                            for source_row in source_rows:
                                if metric == "converts" and source_row.get("record_type") != "convert":
                                    continue
                                location_id = str(source_row.get("location_id") or "")
                                status = str(source_row.get("status") or "")
                                present = bool(source_row.get("approved_rows") or (include_pending and source_row.get("pending_rows"))) if metric == "attendance" else status == "approved" or (include_pending and status == "pending")
                                if not location_id or not present:
                                    continue
                                value = (_safe_int(source_row.get("approved_population")) + (_safe_int(source_row.get("pending_population")) if include_pending else 0)) if metric == "attendance" else _safe_int(source_row.get("count"))
                                reporters[location_id] = reporters.get(location_id, 0) + value
                        return reporters
                    current_by_reporter = crusade_reporters(matches)
                    previous_by_reporter = crusade_reporters(previous_matches)
                    common_reporters = set(current_by_reporter).intersection(previous_by_reporter)
                    comparison_current_value = sum(current_by_reporter[key] for key in common_reporters)
                    prior_value = sum(previous_by_reporter[key] for key in common_reporters)
                    compared_reporter_count = len(common_reporters)
                counted_current = bool(current_counted)
                counted_prior = bool(compared_reporter_count)
                if mode == "crusade" and previous_matches and matches:
                    counted_current = bool(current_by_reporter)
                    counted_prior = bool(previous_by_reporter)
                if counted_current:
                    value_label = "Reported 0" if current_value == 0 else f"{current_value:,}"
                else:
                    current_state = current.get("report_state") if metric == "attendance" else current.get("record_state")
                    value_label = {"no_report": "No report", "upcoming": "Upcoming", "awaiting": "Awaiting report", "late": "Late", "missing": "Missing", "returned": "Returned", "pending": "Pending review"}.get(current_state, "No counted report")
                delta_label = "No comparison" if not counted_prior or not counted_current or not compared_reporter_count else f"{comparison_current_value - (prior_value or 0):+,} vs previous ({compared_reporter_count} reporters)"
                coverages = [r.get("coverage") or {} for r in matches]
                coverage = coverages[0] if coverages else {}
                coverage_label = f"{coverage.get('label', 'Reports')}: {sum(_safe_int(c.get('reported')) for c in coverages)} of {sum(_safe_int(c.get('expected')) for c in coverages)}"
                if mode == "crusade" and can_view_alpha and coverage.get("alpha_expected"):
                    coverage_label += f" · Alpha: {coverage.get('alpha_reported', 0)} of 1"
                target = scope_link(ctx, f"/church-data/programs/analytics/{mode}", campaign_id=campaign_id, compare_campaign_id=compare_campaign_id, program_type=type_slug, event_id=current["event_id"], date_from=day, date_to=day, metric=metric, include_pending=str(include_pending).lower())
                if mode == "crusade" and metric == "attendance" and counted_current:
                    alpha_total = sum(_safe_int((r.get("sources") or {}).get("alpha")) for r in matches)
                    satellite_total = sum(_safe_int((r.get("sources") or {}).get("satellite")) for r in matches)
                    total_label = "Reported 0" if current_value == 0 else f"{current_value:,}"
                    if can_view_alpha:
                        value_content = Div(P(f"Alpha: {alpha_total:,} · Satellites: {satellite_total:,}", cls="small mb-0"),
                                            P(f"Total participation: {total_label}", cls="fw-semibold mb-0"))
                    else:
                        satellite_label = "Reported 0" if satellite_total == 0 else f"{satellite_total:,}"
                        value_content = P(f"Satellite: {satellite_label}", cls="fw-semibold mb-0")
                    link = A(value_content, href=target, hx_get=target, hx_push_url=target, hx_target="#program-analytics-content", hx_swap="outerHTML", cls="text-decoration-none")
                else:
                    link = A(value_label, href=target, hx_get=target, hx_push_url=target, hx_target="#program-analytics-content", hx_swap="outerHTML", cls="fw-semibold text-decoration-none")
                cells.append(Div(link, P(coverage_label, cls="small text-muted mb-0"), P(delta_label, cls="small text-muted mb-0"), cls="d-grid gap-1"))
            else:
                cells.append(Span("Session not scheduled", cls="small text-muted"))
        matrix_rows.append(cells)
    headers = ["Program type"] + [
        (f"Day {next((r.get('day_number') for r in occurrences if r['date'] == day and r.get('day_number')), '—')} · {day}" if mode == "retreat" else day)
        for day in days
    ]
    selector = Form(
        Select(Option("Select event", value=""), *[
            Option(f"{row.get('title') or row.get('campaign_code')} · {row.get('start_date')}", value=row.get("campaign_id"), selected=str(row.get("campaign_id")) == campaign_id)
            for row in campaigns
        ], name="campaign_id", cls="form-select"),
        Select(Option("Compare with", value=""), *[
            Option(f"{row.get('title') or row.get('campaign_code')} · {row.get('start_date')}", value=row.get("campaign_id"), selected=str(row.get("campaign_id")) == compare_campaign_id)
            for row in same_kind
        ], name="compare_campaign_id", cls="form-select") if same_kind else Input(type="hidden", name="compare_campaign_id", value=""),
        Select(Option("Attendance", value="attendance", selected=metric == "attendance"), Option("Converts", value="converts", selected=metric == "converts"), name="metric", cls="form-select") if mode == "crusade" else Input(type="hidden", name="metric", value=metric),
        Label(Input(type="checkbox", name="include_pending", value="true", checked=include_pending), " Include pending reports", cls="form-check-label d-flex align-items-center gap-2 px-2"),
        Button("Apply", variant="primary", size="md", type="submit"),
        method="get", action=ctx.url_for(f"/church-data/programs/analytics/{mode}"),
        cls="d-flex flex-wrap gap-2 align-items-end mb-3",
    )
    if detail:
        detail_rows = [row for row in occurrences if row.get("program_type_slug") == detail.get("program_type_slug") and row.get("date") == detail.get("date")]
        if mode == "retreat" and scope_depth >= 4:
            detail_rows = []
        child_rows_by_path = {}
        for detail_row in detail_rows:
            for child in detail_row.get("children") or []:
                key = str(child.get("path") or child.get("name") or "")
                if key not in child_rows_by_path:
                    child_rows_by_path[key] = dict(child)
                else:
                    existing = child_rows_by_path[key]
                    for field in ("expected", "reported", "pending", "returned", "population"):
                        if child.get(field) is not None:
                            existing[field] = _safe_int(existing.get(field)) + _safe_int(child.get(field))
        child_rows = list(child_rows_by_path.values())
        report_rows = []
        for child in child_rows:
            path = str(child.get("path") or "")
            if mode == "retreat" and scope_depth >= 4:
                continue
            can_drill = mode == "crusade" and scope_depth < 6 or mode == "retreat" and scope_depth == 3
            target = scope_link(ctx, f"/church-data/programs/analytics/{mode}", scope_path=path, campaign_id=campaign_id, compare_campaign_id=compare_campaign_id, program_type=str(request.query_params.get("program_type") or ""), event_id=detail["event_id"], date_from=detail["date"], date_to=detail["date"], metric=metric, include_pending=str(include_pending).lower())
            label = A(str(child.get("name") or "Reporting unit"), href=target, hx_get=target, hx_push_url=target, hx_target="#program-analytics-content", hx_swap="outerHTML") if can_drill else str(child.get("name") or "Reporting unit")
            reported = int(child.get("reported") or 0)
            expected = int(child.get("expected") or 0)
            population = child.get("population")
            state_label = "Reported 0" if child.get("state") == "reported" and population == 0 else (f"{population:,}" if population is not None else str(child.get("state") or "No report").replace("_", " ").title())
            report_rows.append([label, f"{reported} of {expected}", state_label])
        if mode == "crusade" and can_view_alpha and detail.get("alpha_location_id"):
            alpha_reports = [r for detail_row in detail_rows for r in detail_row.get("location_reports", []) if r.get("source_role") == "alpha"]
            alpha_report = alpha_reports[0] if alpha_reports else None
            report_rows.insert(0, ["Alpha location", "1 of 1" if alpha_report else "0 of 1", "Reported 0" if alpha_report and alpha_report.get("approved_population") == 0 else f"{_safe_int(alpha_report.get('approved_population')):,}" if alpha_report else "No report"])
        detail_panel = section_card(
            f"{detail['program_type']} · {detail['date']}",
            f"{detail.get('campaign_title') or mode.title()} · day {detail.get('day_number') or '—'}. " + ("Retreat is reported at region level." if mode == "retreat" else ("Alpha and satellite reporting remain separate." if can_view_alpha else "Satellite reporting is scoped to participating locations.")),
            responsive_table(["Reporting unit", "Coverage", "Counted result"], report_rows, [], results_id="program-event-details") if report_rows else empty_state("clipboard-data", "No report rows", "This scheduled session has no counted submissions in the selected scope."),
        )
    else:
        detail_panel = Div()
    if mode == "retreat" and scope_depth > 4:
        table = empty_state("info-circle", "Retreat is reported at region level", "Retreat reporting drills from State to Region and stops there.")
    else:
        table = responsive_table(headers, matrix_rows, [], results_id=f"{mode}-occurrence-matrix") if matrix_rows else empty_state("calendar3", f"No {mode} sessions reported", "No dated program events are recorded for this campaign. Missing events are not represented as zero attendance.")
    no_campaign = P("No campaign is available in this scope yet.", cls="text-muted") if not campaigns else None
    cell_groups = {}
    for row in occurrences:
        key = (row.get("program_type_slug"), row.get("day_number"), row.get("date"))
        cell_groups.setdefault(key, []).append(row)
    counted_cells = []
    for rows in cell_groups.values():
        counted_rows = [row for row in rows if row.get("report_state") == "counted"]
        if counted_rows:
            counted_cells.append(sum(_safe_int(row.get("counted_population")) for row in counted_rows))
    scheduled_count = len(occurrences)
    reported_count = sum(1 for row in occurrences if row.get("report_state") == "counted")
    peak_value = max(counted_cells, default=0)
    average_day = (sum(counted_cells) / len(counted_cells)) if counted_cells else None
    convert_total = sum(_safe_int(row.get("converts")) for row in occurrences)
    def summary_card(title: str, value: str, explanation: str):
        return Div(stat_card(title, value, explanation, "calendar-check", "primary"), cls="col-6 col-xl-3")
    peak_label = "Peak program/day"
    average_label = "Average counted program/day"
    peak_explanation = "Highest pooled program-and-day cell; values are not added across days."
    average_explanation = "Mean of counted program-and-day cells; missing cells are excluded."
    if mode == "crusade" and metric == "attendance":
        if can_view_alpha:
            peak_label, average_label = "Peak total participation", "Average total participation per session"
            peak_explanation = "Highest session total, with Alpha and satellite counts combined and labelled in the session detail."
            average_explanation = "Mean of counted session totals, with Alpha and satellite participation included."
        else:
            peak_label, average_label = "Peak satellite participation", "Average satellite participation per session"
            peak_explanation = "Highest counted satellite session total within this scope."
            average_explanation = "Mean of counted satellite session totals within this scope."
    summary_cards = Div(
        summary_card(peak_label, f"{peak_value:,}" if counted_cells else "No counted report", peak_explanation),
        summary_card(average_label, f"{average_day:,.1f}" if average_day is not None else "No counted report", average_explanation),
        summary_card("Sessions reported", f"{reported_count} of {scheduled_count} scheduled", "Approved scheduled sessions with a counted report; pending is controlled above."),
        summary_card("Converts", f"{convert_total:,}" if mode == "crusade" else "—", "Convert records across the selected campaign; records are additive."),
        cls="row g-3",
    )
    if mode == "retreat" and scope_depth > 4:
        summary_cards = empty_state("info-circle", "Retreat is reported at region level", "Retreat reporting drills from State to Region and stops there.")
    content = page_stack(
        page_intro(
            "Retreat reporting" if mode == "retreat" else "Global Crusade reporting",
            "One cell represents one scheduled program type on one day. Attendance is never added across sessions."
            if mode == "retreat" else ("One cell represents one scheduled session. Alpha and satellite values stay labelled separately; attendance is never added across sessions." if can_view_alpha else "One cell represents one scheduled satellite session. Attendance is never added across sessions."),
            scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind,
        ),
        Div(*crumbs, cls="d-flex flex-wrap align-items-center gap-1 mb-2", role="navigation", aria_label="Scope breadcrumb"),
        selector,
        summary_cards,
        P("Scheduled sessions are approved ProgramEvent rows in the selected campaign.", cls="small text-muted mb-0"),
        P("Locations reporting uses every active location in scope for each scheduled Crusade session.", cls="small text-muted mb-0") if mode == "crusade" else P("Retreat expected reporters are the regions holding each scheduled session.", cls="small text-muted mb-0"),
        section_card(("Population by program and day" if mode == "retreat" else ("Total participation by program and day" if can_view_alpha else "Satellite participation by program and day")) if metric == "attendance" else "Converts by program and day", "Select a scheduled cell to inspect reporting units for that day and program. A reported zero is distinct from a missing report.", table),
        detail_panel,
        no_campaign,
    )
    report_mode = "retreat" if mode == "retreat" else "crusade"
    report_url = scope_link(ctx, "/dashboard/pastor-report", scope_path=await DashboardService.scope_path(request, ctx), period="event", event_mode=report_mode, campaign_id=campaign_id, include_pending=str(include_pending).lower())
    return shell_layout(ctx, request_path=request.url.path, active_key="programs", title="Retreat" if mode == "retreat" else "Crusade", subtitle="Event reporting", primary_action=A("Print / export report", href=report_url, cls="btn btn-outline-primary"), content=Div(content, id="program-analytics-content"), show_shell_intro=False, show_scope_breadcrumb=False)


async def _event_matrix_page(request: Request, ctx, *, mode: str, campaign_id: str = "", event_id: str = "", metric: str = "attendance", include_pending: bool = False):
    with program_page_trace(mode, str(getattr(ctx, "current_scope_path", "") or "")):
        return await _render_event_matrix_page(
            request, ctx, mode=mode, campaign_id=campaign_id, event_id=event_id,
            metric=metric, include_pending=include_pending,
        )


async def _scope_locations(request: Request, ctx) -> list[str]:
    ctx = active_scope_context(request, ctx)
    rows = await PeopleService.list_locations(request, ctx)
    options = []
    for row in rows:
        location = row.get("location_name") or row.get("location_id") or ""
        if location and location not in options:
            options.append(location)
    return options


async def _program_summary(request: Request, ctx, *, oob: bool = False) -> Div:
    ctx = active_scope_context(request, ctx)
    summary = await ProgramService.summary(request, ctx)
    cards_data = [
        ("Domains", str(summary["domains"]), "Top-level categories", "collection", "primary"),
        ("Types", str(summary["types"]), "Program categories", "tags", "info"),
        ("Events", str(summary["campaigns"]), "Church event cycles", "calendar-check", "success"),
        ("Sessions", str(summary["events"]), "Meeting sessions", "calendar-event", "primary"),
        ("Scheduled", str(summary["scheduled"]), "Ready / upcoming", "clock-history", "warning"),
    ]
    cards = [
        Div(
            stat_card(title, value, note, icon, tone),
            cls="col-6 col-sm-4 col-xl",
        )
        for title, value, note, icon, tone in cards_data
    ]
    attrs = {"id": "program-summary-cards", "cls": "row g-2 g-md-3 mb-4 mx-0"}
    if oob:
        attrs["hx_swap_oob"] = "outerHTML:#program-summary-cards"
    return Div(*cards, **attrs)


async def _domain_mobile_card(ctx, row):
    return Div(
        H3(row["name"], cls="h6 fw-semibold mb-1"),
        P(row.get("description") or "No description added.", cls="text-muted mb-2"),
        P(f"{row['event_count']} event(s) currently use this domain.", cls="small text-muted mb-3"),
        Button(
            "View details",
            variant="outline-primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#detail-drawer",
            hx_get=ctx.url_for(f"/church-data/programs/domains/{row['domain_id']}/drawer"),
            hx_target="#detail-drawer-body",
            hx_swap="innerHTML",
            cls="w-100",
        ),
        cls="mobile-worker-card",
    )


async def _domains_table(request: Request, ctx, *, oob: bool = False):
    ctx = active_scope_context(request, ctx)
    rows = await ProgramService.list_domains(request, ctx)
    if not rows:
        attrs = {"id": "program-domains-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#program-domains-results"
        return Div(empty_state("collection", "No domains", "No program domains are available."), **attrs)

    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["name"],
                row.get("description") or "-",
                row["event_count"],
                Button(
                    "View",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/church-data/programs/domains/{row['domain_id']}/drawer"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                ),
            ]
        )
        mobile_cards.append(await _domain_mobile_card(ctx, row))
    return responsive_table(
        ["Domain", "Description", "Events", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="program-domains-results",
        oob="outerHTML:#program-domains-results" if oob else None,
    )


async def _type_mobile_card(ctx, row):
    return Div(
        H3(row["name"], cls="h6 fw-semibold mb-1"),
        P(row["domain_name"], cls="text-muted mb-2"),
        P(row.get("description") or "No description added.", cls="small text-muted mb-2"),
        P(f"{row['event_count']} event(s) currently use this type.", cls="small text-muted mb-3"),
        Button(
            "View details",
            variant="outline-primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#detail-drawer",
            hx_get=ctx.url_for(f"/church-data/programs/types/{row['type_id']}/drawer"),
            hx_target="#detail-drawer-body",
            hx_swap="innerHTML",
            cls="w-100",
        ),
        cls="mobile-worker-card",
    )


async def _types_table(request: Request, ctx, *, domain_id: str = "", oob: bool = False):
    ctx = active_scope_context(request, ctx)
    rows = await ProgramService.list_types(request, ctx, domain_id=domain_id)
    if not rows:
        attrs = {"id": "program-types-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#program-types-results"
        return Div(empty_state("tag", "No program types", "No program types are available."), **attrs)

    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["name"],
                row["domain_name"],
                row.get("description") or "-",
                row["event_count"],
                Button(
                    "View",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/church-data/programs/types/{row['type_id']}/drawer"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                ),
            ]
        )
        mobile_cards.append(await _type_mobile_card(ctx, row))
    return responsive_table(
        ["Type", "Domain", "Description", "Events", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="program-types-results",
        oob="outerHTML:#program-types-results" if oob else None,
    )


def _campaign_domain_slug(domains: list[dict[str, str]], domain_id: str) -> str:
    for row in domains:
        if row["domain_id"] == str(domain_id):
            return row.get("slug") or ""
    return ""


async def _campaign_mobile_card(ctx, row):
    return Div(
        Div(H3(row["title"], cls="h6 fw-semibold mb-1"), status_badge(row["status"]), cls="d-flex justify-content-between gap-3 mb-1"),
        P(f"{row['domain_name']} - {row['event_mode'].title()}", cls="text-muted mb-2"),
        P(row["campaign_code"], cls="small text-muted mb-2"),
        Div(P(row["start_date"], cls="small text-muted mb-0"), P(row["end_date"], cls="small text-muted mb-0"), cls="d-flex justify-content-between gap-2 mb-3"),
        Button(
            "View details",
            variant="outline-primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#detail-drawer",
            hx_get=ctx.url_for(f"/church-data/programs/campaigns/{row['campaign_id']}/drawer"),
            hx_target="#detail-drawer-body",
            hx_swap="innerHTML",
            cls="w-100",
        ),
        Button(
            "Open report",
            variant="outline-secondary",
            size="md",
            href=ctx.url_for(f"/church-data/programs/campaigns/{row['campaign_id']}/report"),
            cls="w-100 mt-2",
        ),
        cls="mobile-worker-card",
    )


async def _campaigns_table(
    request: Request,
    ctx,
    *,
    domains: list[dict[str, str]],
    domain_id: str = "",
    event_mode: str = "",
    status_value: str = "",
    oob: bool = False,
):
    ctx = active_scope_context(request, ctx)
    rows = await ProgramService.list_campaigns(
        request,
        ctx,
        domain_slug=_campaign_domain_slug(domains, domain_id),
        event_mode=event_mode,
        status_value=status_value,
    )
    if not rows:
        attrs = {"id": "program-campaigns-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#program-campaigns-results"
        return Div(empty_state("calendar-range", "No campaigns", "No campaign records are available."), **attrs)

    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["title"],
                row["campaign_code"],
                row["domain_name"],
                row["event_mode"].title(),
                f"{row['start_date']} to {row['end_date']}",
                status_badge(row["status"]),
                Div(
                    Button(
                        "View",
                        variant="outline-primary",
                        size="md",
                        data_bs_toggle="offcanvas",
                        data_bs_target="#detail-drawer",
                        hx_get=ctx.url_for(f"/church-data/programs/campaigns/{row['campaign_id']}/drawer"),
                        hx_target="#detail-drawer-body",
                        hx_swap="innerHTML",
                    ),
                    Button(
                        "Report",
                        variant="outline-secondary",
                        size="md",
                        href=ctx.url_for(f"/church-data/programs/campaigns/{row['campaign_id']}/report"),
                    ),
                    cls="d-grid d-md-flex gap-2",
                ),
            ]
        )
        mobile_cards.append(await _campaign_mobile_card(ctx, row))
    return responsive_table(
        ["Title", "Code", "Domain", "Mode", "Dates", "Status", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="program-campaigns-results",
        oob="outerHTML:#program-campaigns-results" if oob else None,
    )


async def _event_mobile_card(ctx, row):
    return Div(
        Div(
            H3(row["title"], cls="h6 fw-semibold mb-1"),
            status_badge(row["status"]),
            cls="d-flex justify-content-between gap-3 mb-1",
        ),
        P(f"{row['program_type']} - {row['domain_name']}", cls="text-muted mb-2"),
        Div(P(row["location"], cls="small text-muted mb-0"), P(row["date"], cls="small text-muted mb-0"), cls="d-flex justify-content-between gap-2 mb-1"),
        P(f"{row.get('reporting_scope', 'location').title()} scope · Expires {row.get('collection_window_end') or 'not configured'}", cls="small text-muted mb-3"),
        Button(
            "View details",
            variant="outline-primary",
            size="md",
            data_bs_toggle="offcanvas",
            data_bs_target="#detail-drawer",
            hx_get=ctx.url_for(f"/church-data/programs/events/{row['event_id']}/drawer"),
            hx_target="#detail-drawer-body",
            hx_swap="innerHTML",
            cls="w-100",
        ),
        cls="mobile-worker-card",
    )


async def _events_table(
    request: Request,
    ctx,
    *,
    search: str = "",
    domain_id: str = "",
    type_id: str = "",
    status: str = "",
    location: str = "",
    oob: bool = False,
):
    ctx = active_scope_context(request, ctx)
    rows = await ProgramService.list_events(
        request,
        ctx,
        search=search,
        domain_id=domain_id,
        type_id=type_id,
        status=status,
        location=location,
    )
    if not rows:
        attrs = {"id": "program-events-results"}
        if oob:
            attrs["hx_swap_oob"] = "outerHTML:#program-events-results"
        return Div(empty_state("calendar-event", "No events match this view", "Adjust the filters or create a new event."), **attrs)

    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["title"],
                row["program_type"],
                row["domain_name"],
                row["location"],
                row["date"],
                f"{row.get('reporting_scope', 'location').title()} · {row.get('collection_window_end') or 'No expiry'}",
                status_badge(row["status"]),
                Button(
                    "View",
                    variant="outline-primary",
                    size="md",
                    data_bs_toggle="offcanvas",
                    data_bs_target="#detail-drawer",
                    hx_get=ctx.url_for(f"/church-data/programs/events/{row['event_id']}/drawer"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                ),
            ]
        )
        mobile_cards.append(await _event_mobile_card(ctx, row))
    return responsive_table(
        ["Title", "Type", "Domain", "Location", "Date", "Scope / expiry", "Status", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="program-events-results",
        oob="outerHTML:#program-events-results" if oob else None,
    )


def _campaign_activity_summary(activity: dict[str, object]) -> Div:
    return Div(
        Div(P("Events", cls="small text-muted mb-1"), H4(str(activity["event_count"]), cls="h6 fw-semibold mb-0")),
        Div(P("Records submitted", cls="small text-muted mb-1"), H4(str(activity.get("records_submitted", 0)), cls="h6 fw-semibold mb-0")),
        Div(P("Assignments", cls="small text-muted mb-1"), H4(str(activity.get("assignments_total") or 0), cls="h6 fw-semibold mb-0")),
        Div(P("Submitted", cls="small text-muted mb-1"), H4(str(activity.get("assignments_submitted") or 0), cls="h6 fw-semibold mb-0")),
        cls="counts-stat-grid mt-4",
    )


def _campaign_activity_table(activity: dict[str, object]) -> Div:
    rows = activity.get("events") or []
    if not rows:
        return Div(empty_state("calendar-range", "No linked events", "No events are linked to this campaign."), cls="mt-4")

    desktop_rows = []
    mobile_cards = []
    for row in rows:
        desktop_rows.append(
            [
                row["title"],
                row["location"],
                row["date"],
                _segment_label(str(row.get("audience_segment") or "")),
                row["population"],
                row["alpha_population"],
                row["satellite_population"],
                row["converts"],
                row["newcomers"],
                f"{row.get('assignment_submitted', 0)}/{row.get('assignment_total', 0)}",
            ]
        )
        mobile_cards.append(
            Div(
                H4(row["title"], cls="h6 fw-semibold mb-1"),
                P(f"{row['location']} - {row['date']}", cls="text-muted mb-2"),
                Div(
                    P(f"Segment: {_segment_label(str(row.get('audience_segment') or ''))}", cls="small text-body-emphasis mb-1"),
                    P(f"Session population: {row['population']}", cls="small text-body-emphasis mb-1"),
                    P(f"Alpha: {row['alpha_population']}", cls="small text-body-emphasis mb-1"),
                    P(f"Satellite: {row['satellite_population']}", cls="small text-body-emphasis mb-1"),
                    P(f"Converts: {row['converts']}", cls="small text-body-emphasis mb-1"),
                    P(f"Newcomers: {row['newcomers']}", cls="small text-body-emphasis mb-1"),
                    P(f"Assignments submitted: {row.get('assignment_submitted', 0)}/{row.get('assignment_total', 0)}", cls="small text-body-emphasis mb-0"),
                ),
                cls="mobile-worker-card",
            )
        )
    return responsive_table(
        ["Event", "Location", "Date", "Segment", "Session population", "Alpha", "Satellite", "Converts", "Newcomers", "Assignments"],
        desktop_rows,
        mobile_cards,
        results_id="campaign-activity-results",
    )


async def _campaign_report_panel(ctx, campaign: dict[str, Any], activity: dict[str, Any], *, view: str) -> Div:
    source_rows = [
        {"label": "Alpha records", "value": 0, "display": "Session details below", "color": "#0f766e"},
        {"label": "Satellite records", "value": 0, "display": "Session details below", "color": "#2563eb"},
    ]
    follow_up_rows = [
        {"label": "Convert records", "value": 0, "display": "Session details below", "color": "#7c3aed"},
        {"label": "Newcomer records", "value": 0, "display": "Session details below", "color": "#ea580c"},
    ]
    trend_rows = [
        {
            "label": str(row.get("date") or row.get("title") or "Event"),
            "value": _safe_int(row.get("population")),
            "display": f"{_safe_int(row.get('population')):,} for this event",
            "color": "#1d4ed8",
        }
        for row in reversed(activity.get("events") or [])
    ]
    assignment_rows = [
        {
            "label": "Submitted",
            "value": _safe_int(activity.get("assignments_submitted")),
            "display": str(activity.get("assignments_submitted") or 0),
            "color": "#0f766e",
        },
        {
            "label": "Approved Pending",
            "value": _safe_int(activity.get("assignments_pending_submission")),
            "display": str(activity.get("assignments_pending_submission") or 0),
            "color": "#f59e0b",
        },
        {
            "label": "Pending Approval",
            "value": _safe_int(activity.get("assignments_pending_approval")),
            "display": str(activity.get("assignments_pending_approval") or 0),
            "color": "#2563eb",
        },
        {
            "label": "Rejected",
            "value": _safe_int(activity.get("assignments_rejected")),
            "display": str(activity.get("assignments_rejected") or 0),
            "color": "#dc2626",
        },
    ]
    if view == "summary":
        body = Div(
            _campaign_activity_summary(activity),
            section_card(
                "Assignment readiness",
                "Track how many officiating workers have been approved and how many have actually submitted.",
                Div(
                    Div(P("Approved", cls="small text-muted mb-1"), H4(str(activity.get("assignments_approved") or 0), cls="h6 fw-semibold mb-0")),
                    Div(P("Pending approval", cls="small text-muted mb-1"), H4(str(activity.get("assignments_pending_approval") or 0), cls="h6 fw-semibold mb-0")),
                    Div(P("Pending submission", cls="small text-muted mb-1"), H4(str(activity.get("assignments_pending_submission") or 0), cls="h6 fw-semibold mb-0")),
                    Div(P("Rejected", cls="small text-muted mb-1"), H4(str(activity.get("assignments_rejected") or 0), cls="h6 fw-semibold mb-0")),
                    cls="counts-stat-grid mt-4",
                ),
            ),
            section_card(
                "Retreat segments",
                "Segment totals across multiple sessions are not combined. Use the per-event rows below.",
                empty_state("pie-chart", "No campaign-wide segment total", "Population remains attached to each dated event."),
            ) if campaign["event_mode"] == "retreat" else Div(),
            section_card(
                "Event movement",
                "Every event already linked to this campaign is shown below with its live population and follow-up totals.",
                _campaign_activity_table(activity),
            ),
        )
    else:
        body = Div(
            Div(
                section_card(
                    "Source split",
                    f"{campaign['title']} currently separates alpha-ground and satellite population clearly.",
                    P("Alpha and satellite counts are shown per event in the rows below; this page does not add population across sessions.", cls="text-muted mb-0"),
                ),
                section_card(
                    "Follow-up split",
                    "Crusade and retreat follow-up reporting.",
                    P("Convert and newcomer records are shown for each event below.", cls="text-muted mb-0"),
                ),
                cls="dashboard-grid dashboard-grid--two",
            ),
            Div(
                section_card(
                    "Assignment completion",
                    "Use this to spot which approved officiating workers have still not submitted.",
                    _donut_chart(assignment_rows, label="Assignment completion", total_label="Assignments"),
                    _chart_legend(assignment_rows),
                ),
                section_card(
                    "Retreat segments",
                    "Adult, campus, youth, and children reporting is broken out here for retreat cycles.",
                    P("Audience segments are not totalled across events.", cls="text-muted mb-0"),
                ) if campaign["event_mode"] == "retreat" else section_card(
                    "Submission guidance",
                    "Use the assignment completion chart to spot workers who still need follow-up before the reporting window closes.",
                    Div(
                        P("Submitted workers are counted once they finish their assigned alpha-ground or linked event submission.", cls="text-muted mb-0"),
                        cls="py-3",
                    ),
                ),
                cls="dashboard-grid dashboard-grid--two",
            ),
            section_card(
                "Population trend by event",
                "This chart compares turnout across the campaign events already recorded in this cycle.",
                _bar_chart(trend_rows, label="Campaign population trend"),
                _chart_legend(trend_rows),
            ),
        )
    return Div(body, id="campaign-report-panel")


async def _assignments_section(request: Request, ctx, event_id: str) -> Div:
    rows = await ProgramService.list_assignments(request, ctx, event_id) if await ProgramService.live_enabled(request) else []
    event = await ProgramService.get_event(request, ctx, event_id) if await ProgramService.live_enabled(request) else None
    action = (
        primary_button(
            "Assign Worker",
            href="#",
            data_bs_toggle="offcanvas",
            data_bs_target="#form-drawer",
            hx_get=ctx.url_for(f"/church-data/programs/events/{event_id}/assignments/new"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )
        if await ProgramService.live_enabled(request)
        else None
    )
    if not rows:
        return section_card(
            "Assigned field workers",
            "Approved workers receive this session automatically in Utility while its collection window is open.",
            empty_state("person-check", "No assignments", "No workers are assigned to this event."),
            action or Div(),
            body_id="program-assignment-results",
        )

    desktop_rows = []
    mobile_cards = []
    for row in rows:
        actions = []
        if row["status"] == "pending":
            actions.append(
                Button(
                    "Approve",
                    variant="success",
                    size="md",
                    hx_post=ctx.url_for(f"/church-data/programs/assignments/{row['assignment_id']}/approve"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                )
            )
            actions.append(
                Button(
                    "Reject",
                    variant="outline-danger",
                    size="md",
                    hx_post=ctx.url_for(f"/church-data/programs/assignments/{row['assignment_id']}/reject"),
                    hx_target="#detail-drawer-body",
                    hx_swap="innerHTML",
                )
            )
        desktop_rows.append(
            [
                row["worker_name"],
                row["worker_public_code"] or "-",
                row["assignment_label"] or "-",
                row["assignment_type"].title(),
                row["source_role"].title(),
                status_badge(row["status"]),
                "Yes" if row["submission_completed"] else "No",
                row["submitted_at"] or "-",
                Div(*actions, cls="d-grid d-md-flex gap-2") if actions else P("Up to date", cls="small text-muted mb-0"),
            ]
        )
        mobile_cards.append(
            Div(
                H4(row["worker_name"], cls="h6 fw-semibold mb-1"),
                P(row["worker_public_code"] or "No worker code", cls="text-muted mb-2"),
                P(f"{row['assignment_type'].title()} - {row['source_role'].title()}", cls="small text-body-emphasis mb-1"),
                P(row["assignment_label"] or "No block/label set", cls="small text-body-emphasis mb-2"),
                P(f"Submitted at: {row['submitted_at'] or 'Not yet'}", cls="small text-body-emphasis mb-2"),
                status_badge(row["status"]),
                Div(*actions, cls="d-grid gap-2 mt-3") if actions else P("Assignment already reviewed.", cls="small text-muted mt-3 mb-0"),
                cls="mobile-worker-card",
            )
        )

    table = responsive_table(
        ["Worker", "Code", "Label", "Type", "Source", "Status", "Submitted", "Submitted At", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="program-assignment-results",
    )
    return section_card(
        "Officiating workers",
        "Assignments let state-level teams prepare event workers before approval and live submission.",
        table,
        action or Div(),
    )


async def _programs_workspace(
    request: Request,
    ctx,
    *,
    event_search: str = "",
    domain_id: str = "",
    type_id: str = "",
    status: str = "",
    location: str = "",
    types_domain_id: str = "",
    campaign_domain_id: str = "",
    campaign_event_mode: str = "",
    campaign_status: str = "",
) -> Div:
    (
        domains,
        types,
        locations,
        summary_card,
        domains_tbl,
        types_tbl,
        events_tbl,
    ) = await asyncio.gather(
        ProgramService.list_domains(request, ctx),
        ProgramService.list_types(request, ctx, domain_id=domain_id),
        _scope_locations(request, ctx),
        _program_summary(request, ctx),
        _domains_table(request, ctx),
        _types_table(request, ctx, domain_id=types_domain_id),
        _events_table(request, ctx, search=event_search, domain_id=domain_id, type_id=type_id, status=status, location=location),
    )
    campaigns_tbl = await _campaigns_table(
        request,
        ctx,
        domains=domains,
        domain_id=campaign_domain_id,
        event_mode=campaign_event_mode,
        status_value=campaign_status,
    )
    event_filter_form = Form(
        *hidden_context_inputs(ctx),
        filter_field(
            "Search events",
            Input(type="search", name="event_search", value=event_search, placeholder="Search title, type, domain or location", cls="form-control"),
            field_id="program-event-search",
        ),
        filter_field(
            "Domain",
            Select(
                Option("All domains", value=""),
                *[Option(row["name"], value=row["domain_id"], selected=domain_id == row["domain_id"]) for row in domains],
                name="domain_id",
                cls="form-select",
            ),
            field_id="program-event-domain",
        ),
        filter_field(
            "Program type",
            Select(
                Option("All types", value=""),
                *[
                    Option(row["name"], value=row["type_id"], selected=type_id == row["type_id"])
                    for row in types
                ],
                name="type_id",
                cls="form-select",
            ),
            field_id="program-event-type",
        ),
        filter_field(
            "Status",
            Select(
                Option("All status", value=""),
                *[Option(name.title(), value=name, selected=status == name) for name in EVENT_STATUSES],
                name="status",
                cls="form-select",
            ),
            field_id="program-event-status",
        ),
        filter_field(
            "Location",
            Select(
                Option("All locations", value=""),
                *[Option(name, value=name, selected=location == name) for name in locations],
                name="location",
                cls="form-select",
            ),
            field_id="program-event-location",
        ),
        hx_get=ctx.url_for("/church-data/programs/events/list"),
        hx_target="#program-events-results",
        hx_swap="outerHTML",
        hx_trigger="keyup changed delay:350ms from:input, change from:select",
        cls="admin-filter-grid",
    )
    type_filter_form = Form(
        *hidden_context_inputs(ctx),
        filter_field(
            "Domain",
            Select(
                Option("All domains", value=""),
                *[Option(row["name"], value=row["domain_id"], selected=types_domain_id == row["domain_id"]) for row in domains],
                name="types_domain_id",
                cls="form-select",
            ),
            field_id="program-types-domain",
        ),
        hx_get=ctx.url_for("/church-data/programs/types/list"),
        hx_target="#program-types-results",
        hx_swap="outerHTML",
        hx_trigger="change from:select",
        cls="admin-filter-grid mb-3",
    )
    campaign_filter_form = Form(
        *hidden_context_inputs(ctx),
        filter_field(
            "Domain",
            Select(
                Option("All domains", value=""),
                *[Option(row["name"], value=row["domain_id"], selected=campaign_domain_id == row["domain_id"]) for row in domains],
                name="campaign_domain_id",
                cls="form-select",
            ),
            field_id="program-campaign-domain",
        ),
        filter_field(
            "Campaign mode",
            Select(
                Option("All modes", value=""),
                *[Option(name.title(), value=name, selected=campaign_event_mode == name) for name in CAMPAIGN_MODES],
                name="campaign_event_mode",
                cls="form-select",
            ),
            field_id="program-campaign-mode",
        ),
        filter_field(
            "Campaign status",
            Select(
                Option("All status", value=""),
                *[Option(name.title(), value=name, selected=campaign_status == name) for name in CAMPAIGN_STATUSES],
                name="campaign_status",
                cls="form-select",
            ),
            field_id="program-campaign-status",
        ),
        hx_get=ctx.url_for("/church-data/programs/campaigns/list"),
        hx_target="#program-campaigns-results",
        hx_swap="outerHTML",
        hx_trigger="change from:select",
        cls="admin-filter-grid mb-3",
    )
    tab_items = [
        ("program-domains", "Domains", True),
        ("program-types", "Types", False),
        ("program-campaigns", "Events", False),
        ("program-events", "Sessions", False),
    ]
    tabs_nav = Ul(
        *[
            Li(
                HtmlButton(
                    label,
                    type="button",
                    role="tab",
                    aria_controls=tab_id,
                    aria_selected="true" if active else "false",
                    data_bs_toggle="tab",
                    data_bs_target=f"#{tab_id}",
                    id=f"{tab_id}-tab",
                    cls=f"nav-link {'active' if active else ''}",
                ),
                cls="nav-item flex-shrink-0",
                role="presentation",
            )
            for tab_id, label, active in tab_items
        ],
        role="tablist",
        cls="nav nav-pills d-flex flex-nowrap overflow-x-auto gap-2 pb-2 mb-3 admin-nav-pills",
    )
    workspace = Div(
        tabs_nav,
        Div(
            TabPane(
                Div(
                    Div(
                        H4("Program Domains", cls="h6 fw-semibold mb-1"),
                        P("Domains are the top-level categories pastors understand first.", cls="text-muted mb-0"),
                        cls="mb-3",
                    ),
                    domains_tbl,
                ),
                tab_id="program-domains",
                active=True,
            ),
            TabPane(
                Div(
                    Div(
                        H4("Program Types", cls="h6 fw-semibold mb-1"),
                        P("Types sit under domains and make event creation consistent.", cls="text-muted mb-0"),
                        cls="mb-3",
                    ),
                    type_filter_form,
                    types_tbl,
                ),
                tab_id="program-types",
            ),
            TabPane(
                Div(
                    Div(
                        H4("Church Events", cls="h6 fw-semibold mb-1"),
                        P("Crusades, retreats, and special program cycles begin here before session-level recording starts.", cls="text-muted mb-0"),
                        cls="mb-3",
                    ),
                    campaign_filter_form,
                    campaigns_tbl,
                ),
                tab_id="program-campaigns",
            ),
            TabPane(
                Div(
                    Div(
                        Div(
                            H4("Event Sessions", cls="h6 fw-semibold mb-1"),
                            P("Sessions are the actual meetings that counts, finance, and attendance attach to.", cls="text-muted mb-0"),
                        ),
                        Button(
                            Icon("calendar-plus", cls="me-1"),
                            "Schedule Service",
                            variant="primary",
                            size="sm",
                            data_bs_toggle="offcanvas",
                            data_bs_target="#form-drawer",
                            hx_get=ctx.url_for("/church-data/programs/events/new"),
                            hx_target="#form-drawer-body",
                            hx_swap="innerHTML",
                        ) if ctx.has_permission("programs:create_event") else None,
                        cls="d-flex justify-content-between align-items-center mb-3",
                    ),
                    event_filter_form,
                    events_tbl,
                ),
                tab_id="program-events",
            ),
            cls="tab-content",
        ),
    )
    return Div(
        summary_card,
        Div(
            Button(
                Icon("calendar-plus", cls="me-1"),
                "Schedule Service",
                variant="primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/church-data/programs/events/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ) if ctx.has_permission("programs:create_event") else None,
            Button(
                Icon("plus-circle", cls="me-1"),
                "Add Domain",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/church-data/programs/domains/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            Button(
                Icon("plus-circle", cls="me-1"),
                "Add Type",
                variant="outline-primary",
                size="md",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/church-data/programs/types/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            cls="d-flex align-items-center gap-2 mb-3 flex-wrap",
        ),
        workspace,
        cls="programs-workspace overflow-hidden",
    )


async def _programs_loading_shell(ctx, **params: str) -> Div:
    return Div(
        Div(PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"), cls="mb-4"),
        Div(PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"), cls="mb-4"),
        id="programs-content",
        hx_get=ctx.url_for("/church-data/programs/content", **params),
        hx_trigger="load",
        hx_swap="innerHTML",
    )


def register_program_routes(app) -> None:
    @app.get("/church-data/programs")
    async def programs_page(
        request: Request,
        event_search: str = "",
        domain_id: str = "",
        type_id: str = "",
        status: str = "",
        location: str = "",
        types_domain_id: str = "",
        campaign_domain_id: str = "",
        campaign_event_mode: str = "",
        campaign_status: str = "",
    ):
        ctx = active_scope_context(request, build_context(request))
        body = page_stack(
            Div(
                primary_button("Retreat reporting", href=ctx.url_for("/church-data/programs/analytics/retreat")),
                primary_button("Crusade reporting", href=ctx.url_for("/church-data/programs/analytics/crusade")),
                cls="d-flex flex-wrap gap-2 mb-3",
            ),
            _programs_loading_shell(
                ctx,
                event_search=event_search,
                domain_id=domain_id,
                type_id=type_id,
                status=status,
                location=location,
                types_domain_id=types_domain_id,
                campaign_domain_id=campaign_domain_id,
                campaign_event_mode=campaign_event_mode,
                campaign_status=campaign_status,
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="programs",
            title="Programs",
            subtitle="Domains, types, and event definitions.",
            primary_action=primary_button(
                "Create Event", href="#", data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer", hx_get=ctx.url_for("/church-data/programs/campaigns/new"),
                hx_target="#form-drawer-body", hx_swap="innerHTML",
            ),
            content=body,
        )

    @app.get("/church-data/programs/analytics/retreat")
    async def retreat_analytics_page(request: Request, campaign_id: str = "", event_id: str = "", metric: str = "attendance", include_pending: bool = False):
        ctx = active_scope_context(request, build_context(request))
        return await _event_matrix_page(request, ctx, mode="retreat", campaign_id=campaign_id, event_id=event_id, metric=metric, include_pending=include_pending)

    @app.get("/church-data/programs/analytics/crusade")
    async def crusade_analytics_page(request: Request, campaign_id: str = "", event_id: str = "", metric: str = "attendance", include_pending: bool = False):
        ctx = active_scope_context(request, build_context(request))
        return await _event_matrix_page(request, ctx, mode="crusade", campaign_id=campaign_id, event_id=event_id, metric=metric, include_pending=include_pending)
    @app.get("/church-data/programs/content")
    async def programs_content(
        request: Request,
        event_search: str = "",
        domain_id: str = "",
        type_id: str = "",
        status: str = "",
        location: str = "",
        types_domain_id: str = "",
        campaign_domain_id: str = "",
        campaign_event_mode: str = "",
        campaign_status: str = "",
    ):
        ctx = active_scope_context(request, build_context(request))
        try:
            return await _programs_workspace(
                request,
                ctx,
                event_search=event_search,
                domain_id=domain_id,
                type_id=type_id,
                status=status,
                location=location,
                types_domain_id=types_domain_id,
                campaign_domain_id=campaign_domain_id,
                campaign_event_mode=campaign_event_mode,
                campaign_status=campaign_status,
            )
        except BackendClientError as exc:
            login_path = await AuthService.login_redirect_path(request)
            if request.headers.get("HX-Request"):
                return Response(status_code=200, headers={"HX-Redirect": login_path})
            return RedirectResponse(login_path, status_code=303)

    @app.get("/church-data/programs/types/list")
    async def types_list(request: Request, types_domain_id: str = ""):
        ctx = active_scope_context(request, build_context(request))
        return await _types_table(request, ctx, domain_id=types_domain_id)

    @app.get("/church-data/programs/campaigns/list")
    async def campaigns_list(
        request: Request,
        campaign_domain_id: str = "",
        campaign_event_mode: str = "",
        campaign_status: str = "",
    ):
        ctx = active_scope_context(request, build_context(request))
        domains = await ProgramService.list_domains(request, ctx)
        return await _campaigns_table(
            request,
            ctx,
            domains=domains,
            domain_id=campaign_domain_id,
            event_mode=campaign_event_mode,
            status_value=campaign_status,
        )

    @app.get("/church-data/programs/events/list")
    async def events_list(
        request: Request,
        event_search: str = "",
        domain_id: str = "",
        type_id: str = "",
        status: str = "",
        location: str = "",
    ):
        ctx = active_scope_context(request, build_context(request))
        return await _events_table(request, ctx, search=event_search, domain_id=domain_id, type_id=type_id, status=status, location=location)

    @app.get("/church-data/programs/campaigns/new")
    async def new_campaign_form(request: Request):
        ctx = build_context(request)
        domains, locations = await asyncio.gather(
            ProgramService.list_domains(request, ctx),
            PeopleService.list_locations(request, ctx),
        )
        import random
        default_code = f"EVT-{reporting_today().year}-{random.randint(101, 999)}"
        return Form(
            *hidden_context_inputs(ctx),
            H3("Create Event", cls="h5 fw-semibold"),
            P("Create the crusade, retreat, or special church event cycle first. Sessions and reporting will sit under it.", cls="text-muted"),
            Input(type="text", name="title", placeholder="Event title", cls="form-control mb-3", required=True),
            Div(
                Label("Event Code (flexible and reusable)", cls="form-label small text-muted mb-1"),
                Input(type="text", name="campaign_code", value=default_code, placeholder="Event code (e.g. EVT-2026-412)", cls="form-control mb-3", required=True),
            ),
            Div(
                Select(
                    Option("Select domain", value=""),
                    *[Option(row["name"], value=row["domain_id"]) for row in domains],
                    name="domain_id",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select mode", value=""),
                    *[Option(name.title(), value=name) for name in CAMPAIGN_MODES],
                    name="event_mode",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    Option("Select reporting scope", value="global"),
                    Option("Global", value="global"),
                    Option("Nation", value="nation"),
                    Option("State", value="state"),
                    Option("Region", value="region"),
                    Option("Group", value="group"),
                    name="reporting_scope",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select status", value="draft"),
                    *[Option(name.title(), value=name) for name in CAMPAIGN_STATUSES],
                    name="status",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Input(type="date", name="start_date", value=reporting_today().isoformat(), cls="form-control", required=True),
                Input(type="date", name="end_date", value=reporting_today().isoformat(), cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Input(type="datetime-local", name="collection_window_start", cls="form-control"),
                Input(type="datetime-local", name="collection_window_end", cls="form-control"),
                cls="drawer-two-up mb-3",
            ),
            Select(
                Option("No alpha location", value=""),
                *[Option(row["location_name"], value=row["location_id"]) for row in locations if row.get("location_id")],
                name="alpha_location_id",
                cls="form-select mb-3",
            ),
            Input(type="url", name="flyer_url", placeholder="Flyer or publicity URL", cls="form-control mb-3"),
            Textarea(name="description", placeholder="Short event description", cls="form-control mb-3", rows="3"),
            Textarea(name="publicity_note", placeholder="Publicity note", cls="form-control mb-3", rows="2"),
            Button("Save Event", variant="success", size="md", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/church-data/programs/campaigns/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/church-data/programs/campaigns/create")
    async def create_campaign(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        payload = {**data, "path": ctx.current_scope_path}
        row = await ProgramService.create_campaign(request, payload) if await ProgramService.live_enabled(request) else None
        if row is None:
            return P("Could not save this event right now.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(
                    H3("Event saved", cls="h5 fw-semibold text-success"),
                    P(f"'{row['title']}' is now ready for event planning and submissions.", cls="text-muted mb-3"),
                    Button("Done", variant="primary", size="md", cls="w-100", data_bs_dismiss="offcanvas"),
                ),
                await _campaigns_table(request, ctx, domains=await ProgramService.list_domains(request, ctx), oob=True),
                await _program_summary(request, ctx, oob=True),
            ),
            message="Event saved successfully.",
            variant="success",
        )

    @app.get("/church-data/programs/campaigns/{campaign_id}/drawer")
    async def campaign_drawer(request: Request, campaign_id: str):
        ctx = build_context(request)
        row = await ProgramService.get_campaign(request, ctx, campaign_id)
        if row is None:
            return P("Program campaign not found.", cls="text-muted")
        activity = await ProgramService.campaign_activity(request, ctx, campaign_id)
        return Div(
            H3(row["title"], cls="h5 fw-semibold"),
            P(f"{row['campaign_code']} - {row['domain_name']}", cls="text-muted"),
            Div(
                Div(P("Mode", cls="small text-muted mb-1"), P(row["event_mode"].title(), cls="fw-semibold mb-0")),
                Div(P("Status", cls="small text-muted mb-1"), status_badge(row["status"])),
                Div(P("Scope ID", cls="small text-muted mb-1"), P(row["scope_id"] or "-", cls="fw-semibold mb-0")),
                Div(P("Dates", cls="small text-muted mb-1"), P(f"{row['start_date']} to {row['end_date']}", cls="fw-semibold mb-0")),
                Div(P("Alpha location", cls="small text-muted mb-1"), P(row["alpha_location_id"] or "Not set", cls="fw-semibold mb-0")),
                Div(P("Reporting scope", cls="small text-muted mb-1"), P(row["reporting_scope"].title(), cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            P(row["description"] or "No description added.", cls="mb-2"),
            P(row["publicity_note"] or "No publicity note added.", cls="text-muted mb-0"),
            primary_button("Open campaign report", ctx.url_for(f"/church-data/programs/campaigns/{campaign_id}/report")),
            _campaign_activity_summary(activity),
            section_card(
                "Campaign reporting",
                "These live totals combine the events already linked to this campaign.",
                _campaign_activity_table(activity),
            ),
        )

    @app.get("/church-data/programs/domains/new")
    async def new_domain_form(request: Request):
        ctx = build_context(request)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Add program domain", cls="h5 fw-semibold"),
            P("Use broad categories that pastors can understand immediately.", cls="text-muted"),
            Input(type="text", name="name", placeholder="Domain name", cls="form-control mb-3", required=True),
            Textarea(name="description", placeholder="Short description", cls="form-control mb-3", rows="3"),
            Button("Save domain", variant="success", size="md", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/church-data/programs/domains/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/church-data/programs/domains/create")
    async def create_domain(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        row = await ProgramService.create_domain(request, data) if await ProgramService.live_enabled(request) else None
        if row is None:
            return P("Could not save this program domain right now.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(
                    H3("Domain saved", cls="h5 fw-semibold text-success"),
                    P(f"'{row['name']}' is now available for program types.", cls="text-muted mb-3"),
                    Button("Done", variant="primary", size="md", cls="w-100", data_bs_dismiss="offcanvas"),
                ),
                await _domains_table(request, ctx, oob=True),
                await _program_summary(request, ctx, oob=True),
            ),
            message="Program domain saved.",
            variant="success",
        )

    @app.get("/church-data/programs/domains/{domain_id}/drawer")
    async def domain_drawer(request: Request, domain_id: str):
        ctx = build_context(request)
        row = await ProgramService.get_domain(request, ctx, domain_id)
        if row is None:
            return P("Program domain not found.", cls="text-muted")
        type_count = len(await ProgramService.list_types(request, ctx, domain_id=domain_id))
        return Div(
            H3(row["name"], cls="h5 fw-semibold"),
            P(row.get("description") or "No description added.", cls="text-muted"),
            Div(
                Div(P("Types", cls="small text-muted mb-1"), P(str(type_count), cls="fw-semibold mb-0")),
                Div(P("Events", cls="small text-muted mb-1"), P(str(row["event_count"]), cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
        )

    @app.get("/church-data/programs/types/new")
    async def new_type_form(request: Request):
        ctx = build_context(request)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Add program type", cls="h5 fw-semibold"),
            P("Each type should sit under one clear domain.", cls="text-muted"),
            Select(
                Option("Select domain", value=""),
                *[Option(row["name"], value=row["domain_id"]) for row in await ProgramService.list_domains(request, ctx)],
                name="domain_id",
                cls="form-select mb-3",
                required=True,
            ),
            Input(type="text", name="name", placeholder="Type name", cls="form-control mb-3", required=True),
            Textarea(name="description", placeholder="Short description", cls="form-control mb-3", rows="3"),
            Button("Save type", variant="success", size="md", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/church-data/programs/types/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/church-data/programs/types/create")
    async def create_type(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        row = await ProgramService.create_type(request, data) if await ProgramService.live_enabled(request) else None
        if row is None:
            return P("Could not save this program type right now.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(
                    H3("Type saved", cls="h5 fw-semibold text-success"),
                    P(f"'{row['name']}' is now ready for event creation.", cls="text-muted mb-3"),
                    Button("Done", variant="primary", size="md", cls="w-100", data_bs_dismiss="offcanvas"),
                ),
                await _types_table(request, ctx, oob=True),
                await _program_summary(request, ctx, oob=True),
            ),
            message="Program type saved.",
            variant="success",
        )

    @app.get("/church-data/programs/types/{type_id}/drawer")
    async def type_drawer(request: Request, type_id: str):
        ctx = build_context(request)
        row = await ProgramService.get_type(request, ctx, type_id)
        if row is None:
            return P("Program type not found.", cls="text-muted")
        return Div(
            H3(row["name"], cls="h5 fw-semibold"),
            P(row["domain_name"], cls="text-muted"),
            Div(
                Div(P("Description", cls="small text-muted mb-1"), P(row.get("description") or "No description added.", cls="fw-semibold mb-0")),
                Div(P("Events", cls="small text-muted mb-1"), P(str(row["event_count"]), cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
        )

    @app.get("/church-data/programs/events/new")
    async def new_event_form(request: Request):
        ctx = build_context(request)
        if not ctx.has_permission("programs:create_event"):
            return P("Your role is not permitted to create program events.", cls="text-muted")
        domains = await ProgramService.list_domains(request, ctx)
        campaigns = await ProgramService.list_campaigns(request, ctx)
        locations = await PeopleService.list_locations(request, ctx)
        scope_path = str(ctx.current_scope_path or "")
        scope_depth = len([part for part in scope_path.split(".") if part])
        scope_for_depth = {3: "state", 4: "region", 5: "group", 6: "location"}
        reporting_scope = scope_for_depth.get(scope_depth)
        if reporting_scope not in {"location", "group", "region", "state"}:
            reporting_scope = {2: "location", 3: "group", 4: "region", 5: "state"}.get(ctx.level, "")
        if not reporting_scope:
            return P("Your account does not have a schedulable location, group, region, or state scope.", cls="text-muted")
        return Form(
            *hidden_context_inputs(ctx),
            H3("Create event", cls="h5 fw-semibold"),
            P("Schedule a program session for your jurisdiction. Admin-created schedules await this level's pastor; a pastor-created schedule is approved immediately.", cls="text-muted"),
            Input(type="hidden", name="path", value=scope_path),
            FsInput("title", input_type="text", label="Program session name", placeholder="For example: Combined Workers Meeting", required=True, cls="mb-3"),
            Div(
                FsSelect("domain_id", ("", "Select domain"), *[(row["domain_id"], row["name"]) for row in domains], label="Program domain", required=True),
                FsSelect("type_id", ("", "Select program type"), *[(row["type_id"], row["name"]) for row in await ProgramService.list_types(request, ctx)], label="Program type", required=True),
                cls="drawer-two-up mb-3",
            ),
            Div(
            FsSelect("campaign_id", ("", "No campaign link"), *[(row["campaign_id"], f"{row['title']} ({row['campaign_code']})") for row in campaigns], label="Campaign / series"),
                FsInput("date", input_type="date", label="Session date", value=reporting_today().isoformat(), required=True),
                cls="drawer-two-up mb-3",
            ),
            Div(
                FsSelect("event_mode", *[(name, name.title(), name == "regular") for name in CAMPAIGN_MODES], label="Program workflow", required=True),
                FsSelect("reporting_scope", (reporting_scope, reporting_scope.title(), True), label="Reporting jurisdiction", required=True),
                cls="drawer-two-up mb-3",
            ),
            FsSelect("alpha_location_id", ("", "No Alpha Location"), *[
            (str(row.get("location_id") or ""), str(row.get("location_name") or row.get("location_code") or "Church location"))
                for row in locations if row.get("location_id")
            ], label="Alpha Location (crusades only)"),
            P(f"Crusade and Retreat sessions require a campaign with its own collection window. All other sessions use this session's window. Scheduled scope: {reporting_scope} ({scope_path}).", cls="small text-muted mb-3"),
            Div(
                FsInput("collection_window_start", input_type="datetime-local", label="Collection opens", required=True),
                FsInput("collection_window_end", input_type="datetime-local", label="Collection expires", required=True),
                cls="drawer-two-up mb-3",
            ),
            FsSelect("audience_segment", ("", "General audience"), *[(name, _segment_label(name)) for name in AUDIENCE_SEGMENTS], label="Audience segment"),
            Button("Schedule program", variant="success", size="md", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/church-data/programs/events/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/church-data/programs/events/create")
    async def create_event(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        if not ctx.has_permission("programs:create_event"):
            return P("Your role is not permitted to create program events.", cls="text-muted")
        payload = {**data, "path": ctx.current_scope_path}
        row = await ProgramService.create_event(request, payload) if await ProgramService.live_enabled(request) else None
        if row is None:
            return P("Could not save this event right now.", cls="text-muted")
        approved = row.get("approval_status") == "approved"
        approval_heading = "Event created and approved" if approved else "Submitted for pastor approval"
        approval_message = (
            f"'{row['title']}' is approved and can be assigned to workers."
            if approved
            else f"'{row['title']}' was submitted for approval by the pastor at this level. It will become available to assigned workers after approval."
        )
        return simple_toast_response(
            content=(
                Div(
                    H3(approval_heading, cls="h5 fw-semibold text-success"),
                    P(approval_message, cls="text-muted mb-3"),
                    Button("Done", variant="primary", size="md", cls="w-100", data_bs_dismiss="offcanvas"),
                ),
                await _events_table(request, ctx, oob=True),
                await _program_summary(request, ctx, oob=True),
            ),
            message="Program created and approved." if approved else "Program submitted for pastor approval.",
            variant="success" if approved else "warning",
        )

    @app.get("/church-data/programs/events/{event_id}/drawer")
    async def event_drawer(request: Request, event_id: str):
        ctx = build_context(request)
        row = await ProgramService.get_event(request, ctx, event_id)
        if row is None:
            return P("Program event not found.", cls="text-muted")
        can_approve_event = row.get("approval_status") == "pending" and ctx.has_permission("programs:approve_events")
        event_approval = Div(
            P("Awaiting approval from the pastor at this level.", cls="small text-warning mb-2"),
            Button(
                "Approve schedule", variant="success", size="md",
                hx_post=ctx.url_for(f"/church-data/programs/events/{event_id}/approve"),
                hx_target="#detail-drawer-body", hx_swap="innerHTML", cls="w-100 mb-2",
            ),
            Form(
                Textarea(name="note", placeholder="Reason for rejection (required)", cls="form-control mb-2", rows="2", required=True),
                Button("Reject schedule", variant="outline-danger", size="md", type="submit", cls="w-100"),
                hx_post=ctx.url_for(f"/church-data/programs/events/{event_id}/reject"),
                hx_target="#detail-drawer-body", hx_swap="innerHTML",
            ),
            cls="border rounded p-3 mb-3",
        ) if can_approve_event else Div(
            P(f"Approval: {str(row.get('approval_status') or 'approved').replace('_', ' ').title()}", cls="small text-muted mb-3")
        )
        return Div(
            H3(row["title"], cls="h5 fw-semibold"),
            P(f"{row['program_type']} - {row['domain_name']}", cls="text-muted"),
            Div(
                Div(P("Status", cls="small text-muted mb-1"), status_badge(row["status"])),
                Div(P("Date", cls="small text-muted mb-1"), P(row["date"], cls="fw-semibold mb-0")),
                Div(P("Location", cls="small text-muted mb-1"), P(row["location"], cls="fw-semibold mb-0")),
                Div(P("Collection window", cls="small text-muted mb-1"), P(f"{row.get('collection_window_start') or 'Not set'} → {row.get('collection_window_end') or 'Not set'}", cls="fw-semibold mb-0")),
                Div(P("Audience", cls="small text-muted mb-1"), P(_segment_label(str(row.get("audience_segment") or "")), cls="fw-semibold mb-0")),
                Div(P("Campaign", cls="small text-muted mb-1"), P(row["campaign_title"] or row["campaign_code"] or "Not linked", cls="fw-semibold mb-0")),
                Div(P("Created by", cls="small text-muted mb-1"), P(row["created_by"], cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            event_approval,
            Button(
                "End data collection now",
                variant="outline-danger",
                size="md",
                hx_post=ctx.url_for(f"/church-data/programs/events/{event_id}/close-collection"),
                hx_target="#detail-drawer-body",
                hx_swap="innerHTML",
                cls="w-100 mt-3",
            ),
            _assignments_section(request, ctx, event_id),
        )

    @app.post("/church-data/programs/events/{event_id}/approve")
    async def approve_event(request: Request, event_id: str):
        ctx = build_context(request)
        try:
            updated = await ProgramService.approve_program_event(request, ctx, event_id) if await ProgramService.live_enabled(request) else None
        except BackendClientError as exc:
            return P(f"Could not approve this schedule: {exc}", cls="text-muted")
        if updated is None:
            return P("Could not approve this schedule right now.", cls="text-muted")
        return simple_toast_response(
            content=Div(event_drawer(request, event_id), id="detail-drawer-body", hx_swap_oob="innerHTML:#detail-drawer-body"),
            message="Program schedule approved. Assigned workers can now receive its Utility setup.",
            variant="success",
        )

    @app.post("/church-data/programs/events/{event_id}/reject")
    async def reject_event(request: Request, event_id: str):
        form = await request.form()
        note = str(form.get("note") or "Schedule needs correction before approval.")
        ctx = build_context(request)
        try:
            updated = await ProgramService.reject_program_event(request, ctx, event_id, note) if await ProgramService.live_enabled(request) else None
        except BackendClientError as exc:
            return P(f"Could not reject this schedule: {exc}", cls="text-muted")
        if updated is None:
            return P("Could not reject this schedule right now.", cls="text-muted")
        return simple_toast_response(
            content=Div(event_drawer(request, event_id), id="detail-drawer-body", hx_swap_oob="innerHTML:#detail-drawer-body"),
            message="Program schedule rejected with an approval note.",
            variant="warning",
        )

    @app.post("/church-data/programs/events/{event_id}/close-collection")
    async def close_event_collection(request: Request, event_id: str):
        ctx = build_context(request)
        try:
            updated = await ProgramService.close_event_collection(request, ctx, event_id) if await ProgramService.live_enabled(request) else None
        except BackendClientError as exc:
            return P(f"Could not close collection: {exc}", cls="text-muted")
        if updated is None:
            return P("Could not close collection right now.", cls="text-muted")
        return simple_toast_response(
            content=Div(event_drawer(request, event_id), id="detail-drawer-body", hx_swap_oob="innerHTML:#detail-drawer-body"),
            message="Program collection ended. Assigned Utility sessions will expire.",
            variant="success",
        )

    @app.get("/church-data/programs/campaigns/{campaign_id}/report")
    async def campaign_report_page(request: Request, campaign_id: str, view: str = "chart"):
        ctx = build_context(request)
        campaign = await ProgramService.get_campaign(request, ctx, campaign_id)
        if campaign is None:
            body = page_stack(page_intro("Campaign report", "The selected campaign could not be found.", scope_label=ctx.current_scope_label, scope_kind=ctx.current_scope_kind))
            return shell_layout(
                ctx,
                request_path=request.url.path,
                active_key="programs",
                title="Programs",
                subtitle="Campaign reporting",
                primary_action=None,
                content=body,
            )
        activity = await ProgramService.campaign_activity(request, ctx, campaign_id)
        body = page_stack(
            page_intro(
                campaign["title"],
                f"{campaign['domain_name']} campaign reporting.",
                scope_label=campaign["scope_id"] or ctx.current_scope_label,
                scope_kind=f"{campaign['event_mode'].title()} Campaign",
            ),
            section_card(
                "Campaign report",
                "Campaign chart and summary.",
                _campaign_report_toggle(ctx, campaign_id, view),
                await _campaign_report_panel(ctx, campaign, activity, view=view),
            ),
        )
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="programs",
            title="Programs",
            subtitle="Campaign reporting",
            primary_action=primary_button("Back To Programs", href=ctx.url_for("/church-data/programs")),
            content=body,
        )

    @app.get("/church-data/programs/campaigns/{campaign_id}/report-panel")
    async def campaign_report_panel(request: Request, campaign_id: str, view: str = "chart"):
        ctx = build_context(request)
        campaign = await ProgramService.get_campaign(request, ctx, campaign_id)
        if campaign is None:
            return Div(empty_state("calendar-range", "Campaign not found", "Choose another campaign to continue."), id="campaign-report-panel")
        activity = await ProgramService.campaign_activity(request, ctx, campaign_id)
        return await _campaign_report_panel(ctx, campaign, activity, view=view)

    @app.get("/church-data/programs/events/{event_id}/assignments/new")
    async def new_assignment_form(request: Request, event_id: str):
        ctx = build_context(request)
        event = await ProgramService.get_event(request, ctx, event_id)
        if event is None:
            return P("Program event not found.", cls="text-muted")
        assignments = await ProgramService.list_assignments(request, ctx, event_id) if await ProgramService.live_enabled(request) else []
        workers = [
            row
            for row in await PeopleService.list_workers(request, ctx)
            if row.get("status") == "active" and row.get("approval_status") in {"approved", ""}
        ]
        return Form(
            *hidden_context_inputs(ctx),
            H3("Assign field worker", cls="h5 fw-semibold"),
            P(f"Assign approved workers to {event['title']}. Their Utility app will load this session automatically after approval, and access ends when collection expires.", cls="text-muted"),
            FsSelect("worker_id", ("", "Select worker"), *[
                (row["worker_id"], f"{row['name']} ({row.get('public_code') or row['worker_id']})")
                for row in workers
            ], label="Worker", required=True),
            P("Assigned workers already scheduled on this event:", cls="small text-muted mt-3 mb-1"),
            Div(*[
                Div(Span(row["worker_name"], cls="fw-semibold"), Span(f" · {row['status'].title()} · {row['assignment_type'].title()}", cls="text-muted small"), cls="d-flex justify-content-between border-bottom py-2")
                for row in assignments
            ] or [P("No workers assigned yet.", cls="small text-muted")], cls="mb-3"),
            FsInput("assignment_label", input_type="text", label="Assignment label", placeholder="Block, zone, desk, or seat section", cls="mb-3"),
            Div(
                FsSelect("assignment_type", *[(name, name.replace("_", " ").title(), name == "both") for name in ASSIGNMENT_TYPES], label="Data access", required=True),
                FsSelect(
                    "source_role",
                    *[(name, name.title(), name == ("regular" if event and event.get("reporting_scope") in {"group", "region", "state"} else "alpha"))
                      for name in ( ["regular"] if event and event.get("reporting_scope") in {"group", "region", "state"}
                                    else ["alpha", "satellite"] if event and event.get("event_mode") in {"crusade", "retreat"}
                                    else ["regular"] )],
                    label="Reporting source", required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Textarea(name="note", placeholder="Short assignment note", cls="form-control mb-3", rows="3"),
            Button("Save assignment", variant="success", size="md", type="submit", cls="w-100"),
            hx_post=ctx.url_for(f"/church-data/programs/events/{event_id}/assignments/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/church-data/programs/events/{event_id}/assignments/create")
    async def create_assignment(request: Request, event_id: str):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        try:
            row = await ProgramService.create_assignment(request, ctx, event_id, data) if await ProgramService.live_enabled(request) else None
        except BackendClientError as exc:
            return P(f"Could not save this assignment: {exc}", cls="text-muted")
        if row is None:
            return P("Could not save this assignment right now.", cls="text-muted")
        refreshed = Div(
            event_drawer(request, event_id),
            id="detail-drawer-body",
            hx_swap_oob="innerHTML:#detail-drawer-body",
        )
        return simple_toast_response(
            content=(
                Div(H3("Assignment saved", cls="h5 fw-semibold"), P(f"{row['worker_name']} is now queued for event approval.", cls="mb-0")),
                refreshed,
            ),
            message="Officiating assignment saved.",
            variant="success",
        )

    @app.post("/church-data/programs/assignments/{assignment_id}/approve")
    async def approve_assignment(request: Request, assignment_id: str):
        ctx = build_context(request)
        try:
            updated = await ProgramService.approve_assignment(request, ctx, assignment_id) if await ProgramService.live_enabled(request) else None
        except BackendClientError as exc:
            return P(f"Could not approve this assignment: {exc}", cls="text-muted")
        if updated is None:
            return P("Could not approve this assignment right now.", cls="text-muted")
        refreshed = Div(
            event_drawer(request, updated["event_id"]),
            id="detail-drawer-body",
            hx_swap_oob="innerHTML:#detail-drawer-body",
        )
        return simple_toast_response(
            content=refreshed,
            message=f"{updated['worker_name']} approved for this event.",
            variant="success",
        )

    @app.post("/church-data/programs/assignments/{assignment_id}/reject")
    async def reject_assignment(request: Request, assignment_id: str):
        form = await request.form()
        ctx = build_context(request)
        note = str(form.get("note") or "")
        try:
            updated = await ProgramService.reject_assignment(request, ctx, assignment_id, note=note) if await ProgramService.live_enabled(request) else None
        except BackendClientError as exc:
            return P(f"Could not reject this assignment: {exc}", cls="text-muted")
        if updated is None:
            return P("Could not reject this assignment right now.", cls="text-muted")
        refreshed = Div(
            event_drawer(request, updated["event_id"]),
            id="detail-drawer-body",
            hx_swap_oob="innerHTML:#detail-drawer-body",
        )
        return simple_toast_response(
            content=refreshed,
            message=f"{updated['worker_name']} assignment rejected.",
            variant="warning",
        )
