"""Printable, data-backed Pastor report and scoped workbook/CSV exports."""

from __future__ import annotations

import asyncio
import csv
import html
import io
import json
from urllib.parse import urlencode
import zipfile
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fasthtml.common import A, Div, Form as HtmlForm, H1, H2, H3, Img, Input as HtmlInput, Label, Link, NotStr, Option as HtmlOption, P, Select as HtmlSelect, Span, Strong, Script
from fastapi.responses import Response, RedirectResponse
from faststrap import Button, Icon
from starlette.requests import Request

from app.services.analytics.program_config import STANDING_PROGRAMS, reporting_today
from app.services.analytics.pastor_report_config import (
    CONSECUTIVE_MISSING_SUNDAYS, DECLINE_ATTENTION_PERCENT, DEFINITIONS, MIN_COMPARABLE_LOCATIONS,
)
from app.core.program_page_perf import program_page_trace
from ..auth_context import build_context
from ..backend import BackendClientError, format_scope_display_id
from ..communication import AuthService, ProgramService
from ..communication.dashboard_service import DashboardService
from ..communication.active_scope import active_scope_context, scope_link
from ..communication.api_client import get_api_client
from ..communication.async_compat import async_client
from ..communication.report_service import ReportService
from ..components.shell import hidden_context_inputs, shell_layout
from ..components.ui import empty_state, page_stack, section_card
from .analytics_dashboard import _line_chart, _number, _integer


PERIODS = {
    "4w": ("Last 4 Sundays", 4),
    "8w": ("Last 8 weeks", 8),
    "month": ("Last month", 5),
    "quarter": ("Last quarter", 13),
}
CATEGORY_KEYS = ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")


def _report_scope_breadcrumb(ctx, data: dict[str, Any]) -> Any:
    selected = str(data.get("scope_path") or "")
    maximum = str((ctx.query_extras or {}).get("home_path") or ctx.profile.root_path or selected)
    selected_parts = [part for part in selected.split(".") if part]
    maximum_parts = [part for part in maximum.split(".") if part]
    paths = [".".join(selected_parts[:depth]) for depth in range(len(maximum_parts), len(selected_parts) + 1)]
    paths = [path for path in paths if path == maximum or path.startswith(maximum + ".")]
    if not paths:
        paths = [selected]
    crumbs = []
    for index, path in enumerate(paths):
        label = format_scope_display_id(path) or path.rsplit(".", 1)[-1]
        if path == selected:
            crumbs.append(Span(label, aria_current="location", cls="pastor-report-scope-current"))
        else:
            crumbs.append(A(
                label,
                href=scope_link(
                    ctx,
                    "/dashboard/pastor-report",
                    scope_path=path,
                    period=data["period"],
                    include_pending=str(data["include_pending"]).lower(),
                    campaign_id=str((data.get("selected_campaign") or {}).get("campaign_id") or ""),
                    event_mode=str(data.get("event_mode") or ""),
                ),
                cls="pastor-report-scope-link",
            ))
        if index < len(paths) - 1:
            crumbs.append(Span("›", aria_hidden="true", cls="pastor-report-scope-separator"))
    return Div(*crumbs, role="navigation", aria_label="Report scope breadcrumb", cls="pastor-report-scope-breadcrumb")
CATEGORY_LABELS = {
    "adult_male": "Adult male", "adult_female": "Adult female", "youth_male": "Youth male",
    "youth_female": "Youth female", "boys": "Children male", "girls": "Children female",
}
BRAND_BLUE = "#174ea6"


def _fmt(value: Any) -> str:
    try:
        return f"{int(value or 0):,}"
    except (TypeError, ValueError):
        return "0"


def _category_values(row: dict[str, Any] | None) -> dict[str, int | None]:
    values = (row or {}).get("categories") or {}
    return {key: (None if values.get(key) is None else _integer(values.get(key))) for key in CATEGORY_KEYS}


def _report_period(period: str, latest_sunday: date, event_campaign: dict[str, Any] | None = None) -> tuple[str, date, date, int]:
    if period == "event" and event_campaign:
        start = date.fromisoformat(str(event_campaign["start_date"])[:10])
        end = date.fromisoformat(str(event_campaign["end_date"])[:10])
        return f"{event_campaign.get('title') or 'Event'} ({start:%d %b %Y} – {end:%d %b %Y})", start, end, 4
    if period == "month":
        start = latest_sunday.replace(day=1)
        label = "Month to date"
    elif period == "quarter":
        start = date(latest_sunday.year, ((latest_sunday.month - 1) // 3) * 3 + 1, 1)
        label = "Quarter to date"
    else:
        period = period if period in PERIODS else "4w"
        label, weeks = PERIODS[period]
        start = latest_sunday - timedelta(weeks=weeks - 1)
    first_sunday = start + timedelta(days=(6 - start.weekday()) % 7)
    weeks = 0 if first_sunday > latest_sunday else ((latest_sunday - first_sunday).days // 7) + 1
    return f"{label} ({start:%d %b %Y} – {latest_sunday:%d %b %Y})", start, latest_sunday, max(1, weeks)


def _previous_period_range(period: str, start: date, end: date) -> tuple[date, date]:
    if period == "month":
        previous_end_month = start - timedelta(days=1)
        previous_start = previous_end_month.replace(day=1)
        elapsed = (end - start).days
        previous_end = min(previous_end_month, previous_start + timedelta(days=elapsed))
        return previous_start, previous_end
    if period == "quarter":
        previous_end_quarter = start - timedelta(days=1)
        previous_start = date(previous_end_quarter.year, ((previous_end_quarter.month - 1) // 3) * 3 + 1, 1)
        elapsed = (end - start).days
        return previous_start, min(previous_end_quarter, previous_start + timedelta(days=elapsed))
    days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    return previous_end - timedelta(days=days - 1), previous_end


def _history_totals(rows: list[dict[str, Any]]) -> tuple[int, int]:
    counted = [row for row in rows if row.get("total") is not None]
    return sum(_integer(row.get("total")) for row in counted), len(counted)


def _pct_change(current: int, prior: int) -> float | None:
    if prior <= 0:
        return None
    return (current - prior) * 100.0 / prior


def _coverage_state(row: dict[str, Any]) -> str:
    status = str(row.get("status") or "").lower()
    if status in {"approved", "pending", "returned", "conflict", "missing", "late", "awaiting"}:
        return {"approved": "Counted", "pending": "Pending", "returned": "Returned", "conflict": "Conflict", "missing": "Not reported", "late": "Late", "awaiting": "Awaiting"}[status]
    return "Counted" if row.get("total") is not None else "Not reported"


def _hcf_summary(payload: dict[str, Any] | None) -> Any:
    rows = (payload or {}).get("scope") or []
    latest = rows[-1] if rows else None
    if latest is None or latest.get("total") is None:
        return Div(P("Not reported", cls="fw-semibold"), P("No House Caring Fellowship count was received for the latest Sunday in this reporting window.", cls="small text-muted mb-0"))
    categories = latest.get("categories") or {}
    category_text = " · ".join(f"{CATEGORY_LABELS[key]}: {_fmt(categories[key])}" for key in CATEGORY_KEYS if categories.get(key) is not None)
    return Div(P(f"{_fmt(latest.get('total'))} reported on {latest.get('occurrence_date')}", cls="fw-semibold"), P(category_text or "Category breakdown not recorded.", cls="small text-muted mb-0"), P("Fellowship attendance is location-linked and is not added to program attendance.", cls="small text-muted mb-0"))


def _event_sources(row: dict[str, Any]) -> str:
    sources = row.get("sources") or {}
    return ", ".join(f"{key.title()}: {_fmt(value)}" for key, value in sorted(sources.items())) or "No source report"


def _event_coverage(row: dict[str, Any]) -> str:
    coverage = row.get("coverage") or {}
    reported = coverage.get("reported", coverage.get("approved", 0))
    return f"{_integer(reported)} of {_integer(coverage.get('expected'))}"


def _insights(history: list[dict[str, Any]], children: list[dict[str, Any]], summary: dict[str, Any]) -> list[dict[str, str]]:
    insights: list[dict[str, str]] = []
    if not history:
        return [
            {"text": "No counted Sunday report is available in this period.", "how": "No submission is shown as zero; zero is reported only when a saved count equals zero."},
            {"text": "Attendance change cannot be calculated yet.", "how": "Both compared periods require at least one counted report."},
            {"text": "Coverage and documented-population percentage are unavailable.", "how": "A valid expected-unit roster and at least one counted location with an estimate are required."},
        ]
    midpoint = len(history) // 2
    current_rows = history[midpoint:] if midpoint else history
    prior_rows = history[:midpoint]
    current_total, current_n = _history_totals(current_rows)
    prior_total, prior_n = _history_totals(prior_rows)
    current_avg = current_total / current_n if current_n else None
    prior_avg = prior_total / prior_n if prior_n else None
    change = _pct_change(round(current_avg or 0), round(prior_avg or 0)) if current_avg is not None and prior_avg is not None else None
    if change is None:
        insights.append({"text": "Not enough reports to compare attendance periods.", "how": "Both equal-length periods need at least one counted report."})
    else:
        label = "increased" if change >= 0 else "decreased"
        insights.append({"text": f"Average attendance per counted reporting unit {label} {abs(change):.1f}% ({round(prior_avg):,} to {round(current_avg):,}).", "how": "Each period is pooled by attendance and counted reporting-unit-weeks; missing weeks are excluded."})

    latest = history[-1]
    coverage = latest.get("coverage") or {}
    expected, received = _integer(latest.get("n_expected")), _integer(latest.get("n_received"))
    insights.append({"text": f"{received} of {expected} expected reporting locations reported in the latest week.", "how": "Coverage comes from the reporting calculator; a saved zero is still a report."})
    gaps = []
    for child in children:
        child_history = child.get("history") or []
        trailing = 0
        for row in reversed(child_history):
            if row.get("total") is None:
                trailing += 1
            else:
                break
        if trailing >= CONSECUTIVE_MISSING_SUNDAYS:
            gaps.append(str(child.get("name") or "Reporting unit"))
    if gaps:
        insights.append({"text": f"{len(gaps)} child reporting units have missed at least {CONSECUTIVE_MISSING_SUNDAYS} consecutive Sundays.", "how": "A week without a counted report is missing, not zero; pending and returned records do not count."})
    else:
        insights.append({"text": "No child unit has reached the consecutive-missing follow-up threshold.", "how": f"Threshold: {CONSECUTIVE_MISSING_SUNDAYS} consecutive Sundays without a counted report."})
    if len(children) >= MIN_COMPARABLE_LOCATIONS:
        child_changes = []
        for child in children:
            rows = child.get("history") or []
            left, right = rows[:midpoint], rows[midpoint:]
            left_total, left_n = _history_totals(left)
            right_total, right_n = _history_totals(right)
            if left_n and right_n:
                child_changes.append((str(child.get("name") or "Reporting unit"), right_total - left_total))
        if child_changes:
            largest = max(child_changes, key=lambda item: abs(item[1]))
            direction = "increased" if largest[1] > 0 else "decreased" if largest[1] < 0 else "was unchanged"
            insights.append({"text": f"{largest[0]} had the largest comparable change ({direction} by {abs(largest[1]):,}).", "how": f"For each child, current-period counted population total minus prior-period counted population total; only children with counted reports in both windows are compared. At least {MIN_COMPARABLE_LOCATIONS} units are required."})
    else:
        insights.append({"text": "Not enough reporting units to compare child-unit changes.", "how": f"At least {MIN_COMPARABLE_LOCATIONS} reporting units are required."})
    offerings = summary.get("approved_offerings") or {}
    approved_count = _integer(offerings.get("current_records"))
    approved_total = float(offerings.get("current_total") or 0)
    pending_count = next((_integer(item.get("count")) for item in summary.get("pending_approvals") or [] if item.get("label") == "Offerings"), 0)
    insights.append({"text": (f"Approved offerings: ₦{approved_total:,.2f} from {approved_count:,} records; {pending_count:,} pending records are separate." if approved_count else f"No approved offering records are available in the selected period; {pending_count:,} pending records are separate."), "how": "Amounts are summed from stored offering records. No approved records is not a reported zero offering."})
    expected_percent = latest.get("expected_population_percent")
    if expected_percent is not None:
        insights.append({"text": f"Attendance is {float(expected_percent):.1f}% of documented population across {latest.get('expected_population_counted_locations', 0)} counted locations; {latest.get('expected_population_no_estimate_locations', 0)} counted locations have no estimate.", "how": DEFINITIONS["expected_percent"]})
    else:
        insights.append({"text": "Documented-population percentage is unavailable for the latest week.", "how": "At least one counted location with a documented population estimate is required."})
    return insights[:6]


async def _report_data(request: Request, ctx, *, period: str, include_pending: bool, campaign_id: str, event_mode: str) -> dict[str, Any]:
    ctx = active_scope_context(request, ctx)
    scope_path = await DashboardService.scope_path(request, ctx)
    today = reporting_today()
    if period == "event" and event_mode not in {"retreat", "crusade"}:
        event_mode = "retreat"
    latest_sunday = today - timedelta(days=(today.weekday() + 1) % 7)
    campaigns: list[dict[str, Any]] = []
    selected_campaign = None
    if event_mode in {"retreat", "crusade"}:
        domain = "retreat" if event_mode == "retreat" else "global_crusade"
        campaigns = await ProgramService.list_analytics_campaigns(request, ctx, domain_slug=domain, event_mode=event_mode)
        selected_campaign = next((row for row in campaigns if str(row.get("campaign_id")) == campaign_id), None)
        if selected_campaign is None:
            past = [row for row in campaigns if str(row.get("start_date") or "")[:10] <= today.isoformat()]
            selected_campaign = max(past or campaigns, key=lambda row: str(row.get("start_date") or ""), default=None)
            campaign_id = str((selected_campaign or {}).get("campaign_id") or "")
    title_range, start_date, end_date, selected_weeks = _report_period(period, latest_sunday, selected_campaign)
    ctx.query_extras["include_pending"] = "true" if include_pending else "false"
    # A full extra period is retained for deterministic, like-for-like insights.
    history_weeks = selected_weeks if period == "event" else min(selected_weeks * 2, 26)
    summary_weeks = selected_weeks if period != "event" else 4
    daily_payload, full_history = await asyncio.gather(
        DashboardService.sunday_worship_dashboard(
            request, ctx, weeks=summary_weeks, scope_path=scope_path, latest_date=latest_sunday.isoformat(),
        ),
        DashboardService.sunday_worship_series(
            request, ctx, weeks=history_weeks, scope_path=scope_path, latest_date=latest_sunday.isoformat(), include_locations=True,
        ) if period != "event" else asyncio.sleep(0, result={"scope": [], "children": []}),
    )
    if daily_payload.get("error") or not isinstance(daily_payload.get("series"), dict):
        raise BackendClientError(str(daily_payload.get("error") or "Attendance data did not return a valid report."))
    summary = ((daily_payload.get("bootstrap") or {}).get("summary") or {})
    sunday_series = daily_payload.get("series") or {}
    scope_name = next((str(item.get("name")) for item in sunday_series.get("ancestors") or [] if item.get("path") == scope_path and item.get("name")), ctx.current_scope_label)
    hist_rows = (full_history.get("scope") or []) if isinstance(full_history, dict) else []
    if not hist_rows:
        hist_rows = sunday_series.get("scope") or []
    hist_rows = hist_rows[-history_weeks:]
    active_rows = hist_rows[-selected_weeks:] if period != "event" else []
    previous_rows = hist_rows[-2 * selected_weeks:-selected_weeks] if period != "event" else []
    children = full_history.get("children") or sunday_series.get("children") or []
    for child in children:
        child["history"] = (child.get("history") or [])[-history_weeks:]
    standing: dict[str, Any] = {"sunday_worship_service": {"scope": active_rows}}
    if period != "event":
        other_programs = ["monday_bible_study", "thursday_revival_hour", "house_caring_fellowship"]
        async def load_program(key: str):
            program = STANDING_PROGRAMS[key]
            latest = today - timedelta(days=(today.weekday() - int(program.weekday)) % 7)
            return key, await DashboardService.standing_program_series(
                request, ctx, program_key=key, weeks=selected_weeks, scope_path=scope_path,
                latest_date=latest.isoformat(), include_pending=include_pending,
            )
        program_results = await asyncio.gather(*(load_program(key) for key in other_programs), return_exceptions=True)
        for result in program_results:
            if isinstance(result, tuple):
                standing[result[0]] = result[1]
            elif isinstance(result, Exception):
                standing[f"program_error_{len(standing)}"] = {"error": str(result)}
    offerings = []
    if await ReportService.live_enabled(request):
        client = async_client(get_api_client())
        try:
            offerings = await client.get_offerings_by_program(
                AuthService.get_access_token(request), scope_path=scope_path,
                start_date=start_date.isoformat(), end_date=end_date.isoformat(),
            )
        except BackendClientError as exc:
            offerings = [{"error": str(exc)}]
    else:
        offerings = []
    # Event matrices are scoped and returned as aggregate session rows only.
    event_rows: list[dict[str, Any]] = []
    event_campaigns: list[dict[str, Any]] = []
    if period == "event" and selected_campaign:
        event_campaigns = [selected_campaign]
    elif period != "event":
        for mode in ("retreat", "crusade"):
            domain = "retreat" if mode == "retreat" else "global_crusade"
            available = await ProgramService.list_analytics_campaigns(request, ctx, domain_slug=domain, event_mode=mode)
            event_campaigns.extend([
                row for row in available
                if str(row.get("start_date") or "")[:10] <= end_date.isoformat()
                and str(row.get("end_date") or row.get("start_date") or "")[:10] >= start_date.isoformat()
            ])
    for campaign in event_campaigns:
        mode = str(campaign.get("event_mode") or "")
        domain = "retreat" if mode == "retreat" else "global_crusade"
        event_result = await ProgramService.occurrences(
            request, ctx, domain=domain, campaign_id=str(campaign.get("campaign_id")),
            include_pending=include_pending,
        )
        event_rows.extend(row for row in (event_result.get("occurrences") or []) if str(row.get("campaign_id")) == str(campaign.get("campaign_id")))
    for result in standing.values():
        if result.get("error"):
            raise BackendClientError(str(result["error"]))
    if offerings and offerings[0].get("error"):
        raise BackendClientError(str(offerings[0]["error"]))
    if period != "event" and await ReportService.live_enabled(request):
        previous_start, previous_end = _previous_period_range(period, start_date, end_date)
        previous_offerings = await client.get_offerings_by_program(
            AuthService.get_access_token(request), scope_path=scope_path,
            start_date=previous_start.isoformat(), end_date=previous_end.isoformat(),
        )
        if previous_offerings and previous_offerings[0].get("error"):
            raise BackendClientError(str(previous_offerings[0]["error"]))
    else:
        previous_offerings = []
    def offering_totals(rows: list[dict[str, Any]]) -> dict[str, float | int]:
        totals = {"approved": 0.0, "pending": 0.0, "approved_records": 0, "pending_records": 0}
        for row in rows:
            status = str(row.get("status") or "").lower()
            if status in totals:
                totals[status] += float(row.get("amount") or 0)
                totals[f"{status}_records"] += _integer(row.get("records"))
        return totals
    financial = offering_totals(offerings)
    financial_previous = offering_totals(previous_offerings)
    return {
        "ctx": ctx, "scope_path": scope_path, "scope_name": scope_name,
        "period": period, "period_label": title_range, "start_date": start_date, "end_date": end_date,
        "include_pending": include_pending, "summary": summary, "series": sunday_series,
        "history": active_rows, "previous_history": previous_rows, "all_history": hist_rows,
        "children": children, "standing": standing, "offerings": offerings,
        "offering_summary": financial, "offering_previous": financial_previous,
        "events": event_rows, "campaigns": event_campaigns, "selected_campaign": selected_campaign, "event_mode": event_mode,
        "generated_at": datetime.now(ZoneInfo("Africa/Lagos")), "generated_by": ctx.profile.user_name,
    }


def _sections(data: dict[str, Any]) -> list[tuple[str, Any]]:
    history = data["history"]
    summary = data["summary"]
    worker = summary.get("attendance_summary") or {}
    pending = summary.get("pending_approvals") or []
    latest = history[-1] if history else {}
    if data["period"] != "event":
        insights = _insights(data["all_history"], data["children"], summary)
    else:
        event_rows = data["events"]
        counted_events = [row for row in event_rows if row.get("report_state") == "counted" and row.get("counted_population") is not None]
        peak = max((_integer(row.get("counted_population")) for row in counted_events), default=None)
        average = sum(_integer(row.get("counted_population")) for row in counted_events) / len(counted_events) if counted_events else None
        insights = [
            {"text": f"{len(counted_events)} of {len(event_rows)} scheduled sessions have counted reports.", "how": "A session is counted only when its report is approved, or pending when the include-pending option is selected."},
            {"text": "Peak reported session population: " + ("No counted report." if peak is None else f"{peak:,}."), "how": "Maximum of counted session cells; attendance is never summed across days."},
            {"text": "Average counted session population: " + ("No counted report." if average is None else f"{average:,.1f}."), "how": "Mean of counted sessions; missing sessions are excluded."},
            {"text": f"Convert records in this campaign: {sum(_integer(row.get('converts')) for row in event_rows):,}.", "how": "Additive convert record count, not a unique-person count."},
            {"text": f"{sum(1 for row in event_rows if row.get('report_state') == 'pending')} sessions are pending; {sum(1 for row in event_rows if row.get('report_state') == 'rejected')} rejected sessions are excluded.", "how": "Review state comes from event submissions; pending inclusion follows the report filter."},
        ]
    coverage = latest.get("coverage") or {}
    attendance_rows = []
    for row in history:
        status = "Counted" if row.get("total") is not None else ("Pending" if _integer((row.get("coverage") or {}).get("pending")) else "Not reported")
        attendance_rows.append([row.get("occurrence_date", ""), status,
            "No report" if row.get("total") is None else _fmt(row.get("total")),
            ", ".join(f"{CATEGORY_LABELS[key]} {_fmt((row.get('categories') or {}).get(key))}" for key in CATEGORY_KEYS if (row.get("categories") or {}).get(key) is not None) or "Categories not reported",
            f"{_integer(row.get('n_received'))} of {_integer(row.get('n_expected'))}",
            "—" if row.get("expected_population_percent") is None else f"{float(row['expected_population_percent']):.1f}%"])
    child_rows = []
    for child in data["children"]:
        rows = child.get("history") or []
        current_rows = rows[-len(history):] if history else []
        prev_rows = rows[-2 * len(history):-len(history)] if history else []
        current, n_current = _history_totals(current_rows)
        prev, n_prev = _history_totals(prev_rows)
        change = current - prev if n_current and n_prev else None
        child_rows.append([str(child.get("name") or "Reporting unit"), str(child.get("path") or ""),
            "No counted report" if not n_current else _fmt(round(current / n_current)),
            "Not enough reports to compare" if change is None else f"{change:+,}"])
    offering_rows = data["offerings"]
    if offering_rows and not offering_rows[0].get("error"):
        financial_rows = [[row.get("date"), row.get("program"), row.get("fund_type"), row.get("status"), f"₦{float(row.get('amount') or 0):,.2f}", _fmt(row.get("records"))] for row in offering_rows]
    else:
        financial_rows = [["—", "Unclassified", "—", "Not available", "No offering detail returned", "—"]]
    approved_total = float(data.get("offering_summary", {}).get("approved") or 0)
    approved_count = _integer(data.get("offering_summary", {}).get("approved_records"))
    pending_amount = float(data.get("offering_summary", {}).get("pending") or 0)
    prior_approved_total = float(data.get("offering_previous", {}).get("approved") or 0)
    prior_approved_count = _integer(data.get("offering_previous", {}).get("approved_records"))
    offering_change = approved_total - prior_approved_total
    offering_change_text = f"Change from previous equal-length period: {'+' if offering_change >= 0 else ''}₦{offering_change:,.2f} (previous approved total ₦{prior_approved_total:,.2f})." if approved_count and prior_approved_count else "Change from previous period: not enough approved offering records to compare."
    pending_offerings = next((item for item in pending if item.get("label") == "Offerings"), {})
    newcomer = summary.get("newcomer_period") or {}
    worker_rows = [["Workers meeting", _fmt(worker.get("present")), _fmt(worker.get("expected")), "Not enough reports to compare" if not worker.get("expected") else f"{float(worker.get('rate') or 0):.1f}%", _fmt(worker.get("meetings_reported"))]]
    waiting_rows = [[item.get("label"), _fmt(item.get("count")), "Age unavailable" if item.get("oldest_age_hours") is None else f"{_integer(item.get('oldest_age_hours'))} hours"] for item in pending]
    event_table = [[row.get("campaign_title") or row.get("campaign_name") or "Event", row.get("program_type") or row.get("program_type_name") or "Program", row.get("day_number") or "—", row.get("date") or "—", row.get("report_state") or "No report", _event_coverage(row), _event_sources(row), "No report" if row.get("counted_population") is None else _fmt(row.get("counted_population")), _fmt(row.get("converts"))] for row in data["events"]]
    if not event_table:
        event_table = [["—", "—", "—", "—", "No scheduled session in this period", "—", "—"]]
    return [
        ("Key findings", Div(*[Div(P(item["text"], cls="mb-1"), P(f"How calculated: {item['how']}", cls="small text-muted mb-0"), cls="pastor-insight") for item in insights], cls="d-grid gap-2")),
        ("Coverage", Div(P(f"{_integer(coverage.get('approved'))} approved · {_integer(coverage.get('pending'))} pending · {_integer(coverage.get('returned'))} returned · {_integer(coverage.get('conflict'))} conflict · {_integer(coverage.get('missing'))} not reported", cls="fw-semibold"), P("Coverage is measured against the active units expected for the program and period. Missing reports are not zero.", cls="small text-muted mb-0"))),
        ("Attendance", Div(_line_chart([{"date": row.get("occurrence_date"), "average": None if row.get("total") is None or not _integer(row.get("n_counted")) else round(_integer(row.get("total")) / _integer(row.get("n_counted"))), "counted": _integer(row.get("n_counted")), "expected": _integer(row.get("n_expected"))} for row in history], max(4, len(history) or 4)), _table(["Sunday", "Report state", "Population", "Six recorded categories", "Coverage", "% documented population"], attendance_rows), _table(["Child unit", "Scope path", "Average per counted week", "Change vs previous period"], child_rows))),
        ("Offerings and tithes", Div(P(f"Approved in period: ₦{approved_total:,.2f} across {approved_count:,} records." if approved_count else "No approved offering records are available in this period.", cls="fw-semibold"), P(offering_change_text, cls="small text-muted"), P(f"Pending offering amount: ₦{pending_amount:,.2f} across {_integer(pending_offerings.get('count')):,} records. Pending values are not included in the approved amount.", cls="small text-muted"), _table(["Date", "Program", "Fund", "Status", "Amount", "Records"], financial_rows))),
        ("Newcomers and converts", Div(
            P(
                f"Newcomer records: {_fmt(newcomer.get('newcomers_current'))} · Convert records: {_fmt(newcomer.get('converts_current'))}"
                if _integer(newcomer.get("newcomers_current")) or _integer(newcomer.get("converts_current"))
                else "No newcomer or convert records are available for this period.",
                cls="fw-semibold",
            ),
            P("These are report counts, not unique-person counts. No records does not mean a reported zero.", cls="small text-muted mb-0"),
        )),
        ("Workers’ meeting", Div(_table(["Meeting type", "Present", "Expected places", "Attendance rate", "Meetings reported"], worker_rows), P("Roster-based totals deduplicate expected workers per meeting where a roster snapshot exists.", cls="small text-muted mb-0"))),
        ("House Caring Fellowship", _hcf_summary(data["standing"].get("house_caring_fellowship"))),
        ("Waiting on a decision", _table(["Request type", "Waiting", "Oldest age"], waiting_rows) if waiting_rows else P("No pending decisions were reported for this scope.")),
        ("Retreat and crusade summary", _table(["Campaign", "Program", "Day", "Date", "Report state", "Coverage", "Source roles", "Population", "Convert records"], event_table)),
        ("Appendix: definitions and data quality", Div(*[P(f"{key.replace('_', ' ').title()}: {value}", cls="small mb-2") for key, value in DEFINITIONS.items()], P(f"At least {MIN_COMPARABLE_LOCATIONS} units are required for child comparison insights; a decline attention threshold is {DECLINE_ATTENTION_PERCENT}% and the consecutive-missing threshold is {CONSECUTIVE_MISSING_SUNDAYS} Sundays.", cls="small mb-0"))),
    ]


def _table(headers: list[str], rows: list[list[Any]]) -> Any:
    if not rows:
        return P("Not enough reports to show this table.", cls="text-muted")
    head = "".join(f"<th scope='col'>{html.escape(str(cell))}</th>" for cell in headers)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>" for row in rows)
    return NotStr(f"<div class='table-responsive pastor-table-scroll'><table class='table table-sm table-bordered pastor-report-table'><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>")


def _workbook_bytes(data: dict[str, Any]) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    summary = wb.active
    summary.title = "Summary"
    summary.append(["Pastor report", data["scope_name"]])
    summary.append(["Period", data["period_label"]])
    summary.append(["Status", "Including pending" if data["include_pending"] else "Approved only"])
    summary.append(["Generated by", data["generated_by"]])
    summary.append(["Generated at", data["generated_at"].isoformat()])
    summary.append(["Latest Sunday population", data["history"][-1].get("total") if data["history"] else "No report"])
    summary.append(["Documented population percentage", data["history"][-1].get("expected_population_percent") if data["history"] else "No report"])
    summary.append(["Approved offerings in period", data.get("offering_summary", {}).get("approved")])
    summary.append(["Pending offerings in period", data.get("offering_summary", {}).get("pending")])
    summary.append(["Previous period approved offerings", data.get("offering_previous", {}).get("approved")])
    summary.append(["Calculation", DEFINITIONS["expected_percent"]])
    weekly = wb.create_sheet("Weekly by unit")
    weekly.append(["Sunday", "Unit", "Scope path", "Population", "Counted reports", "Expected units"])
    for week in data["history"]:
        weekly.append([week.get("occurrence_date"), data["scope_name"], data["scope_path"], week.get("total"), week.get("n_counted"), week.get("n_expected")])
        for child in data["children"]:
            row = next((item for item in child.get("history", []) if item.get("occurrence_date") == week.get("occurrence_date")), None)
            weekly.append([week.get("occurrence_date"), child.get("name"), child.get("path"), None if row is None else row.get("total"), None if row is None else row.get("n_counted"), None if row is None else row.get("n_expected")])
    coverage = wb.create_sheet("Location coverage")
    selected_dates = {str(row.get("occurrence_date")) for row in data["history"]}
    coverage.append(["Location", "Scope path", "Sunday", "Reporting state", "Population", *[CATEGORY_LABELS[k] for k in CATEGORY_KEYS], "Documented population", "% documented population"])
    for node in data["series"].get("locations") or []:
        for row in node.get("history") or []:
            if str(row.get("occurrence_date")) not in selected_dates:
                continue
            coverage_state = _coverage_state(row)
            coverage.append([node.get("name"), node.get("path"), row.get("occurrence_date"), coverage_state, row.get("total"), *[(row.get("categories") or {}).get(k) for k in CATEGORY_KEYS], row.get("expected_population_total"), row.get("expected_population_percent")])
    categories = wb.create_sheet("Counts by category")
    categories.append(["Sunday", "Unit", "Scope path", "Status", *[CATEGORY_LABELS[k] for k in CATEGORY_KEYS], "Total"])
    for week in data["history"]:
        categories.append([week.get("occurrence_date"), data["scope_name"], data["scope_path"], "Counted" if week.get("total") is not None else "Not reported", *[week.get("categories", {}).get(k) for k in CATEGORY_KEYS], week.get("total")])
        for child in data["children"]:
            row = next((item for item in child.get("history", []) if item.get("occurrence_date") == week.get("occurrence_date")), None) or {}
            categories.append([week.get("occurrence_date"), child.get("name"), child.get("path"), "Counted" if row.get("total") is not None else "Not reported", *[(row.get("categories") or {}).get(k) for k in CATEGORY_KEYS], row.get("total")])
    for node in data["series"].get("locations") or []:
        for row in node.get("history") or []:
            if str(row.get("occurrence_date")) not in selected_dates:
                continue
            categories.append([row.get("occurrence_date"), node.get("name"), node.get("path"), _coverage_state(row), *[(row.get("categories") or {}).get(k) for k in CATEGORY_KEYS], row.get("total")])
    offers = wb.create_sheet("Offerings summary")
    offers.append(["Date", "Program", "Fund type", "Status", "Amount", "Record count"])
    for row in data["offerings"]:
        if not row.get("error"):
            offers.append([row.get("date"), row.get("program"), row.get("fund_type"), row.get("status"), row.get("amount"), row.get("records")])
    hcf = wb.create_sheet("House Caring Fellowship")
    hcf.append(["Date", "Reported total", *[CATEGORY_LABELS[k] for k in CATEGORY_KEYS], "Status"])
    hcf_history = (data["standing"].get("house_caring_fellowship") or {}).get("scope") or []
    for row in hcf_history:
        if str(row.get("occurrence_date")) not in selected_dates:
            continue
        hcf.append([row.get("occurrence_date"), row.get("total"), *[(row.get("categories") or {}).get(k) for k in CATEGORY_KEYS], "Counted" if row.get("total") is not None else "Not reported"])
    events = wb.create_sheet("Retreat Crusade")
    events.append(["Campaign", "Program", "Day", "Date", "State", "Coverage", "Source roles", "Population", "Convert records"])
    for row in data["events"]:
        events.append([row.get("campaign_title") or row.get("campaign_name"), row.get("program_type") or row.get("program_type_name"), row.get("day_number"), row.get("date"), row.get("report_state"), _event_coverage(row), _event_sources(row), row.get("counted_population"), row.get("converts")])
    definitions = wb.create_sheet("Definitions")
    definitions.append(["Term", "Definition"])
    for key, value in DEFINITIONS.items():
        definitions.append([key.replace("_", " ").title(), value])
    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for column_cells in ws.columns:
            width = min(48, max(12, max((len(str(cell.value or "")) for cell in column_cells), default=0) + 2))
            ws.column_dimensions[column_cells[0].column_letter].width = width
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _csv_zip_bytes(data: dict[str, Any]) -> bytes:
    xlsx = _workbook_bytes(data)
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(xlsx), read_only=True, data_only=True)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for ws in wb.worksheets:
            content = io.StringIO(newline="")
            writer = csv.writer(content)
            for row in ws.iter_rows(values_only=True):
                writer.writerow(["" if value is None else value for value in row])
            zf.writestr(f"{ws.title.lower().replace(' ', '_')}.csv", content.getvalue())
    return archive.getvalue()


def _pdf_bytes(data: dict[str, Any]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image as PdfImage, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from reportlab.graphics.shapes import Circle, Drawing, Line, Rect, String
    from xml.sax.saxutils import escape

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=14 * mm, leftMargin=14 * mm, topMargin=16 * mm, bottomMargin=17 * mm, title="Pastor's report", pageCompression=0)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("DCLTitle", parent=styles["Title"], textColor=colors.HexColor(BRAND_BLUE), alignment=TA_LEFT, fontSize=19, leading=23)
    head_style = ParagraphStyle("DCLHead", parent=styles["Heading2"], textColor=colors.HexColor(BRAND_BLUE), fontSize=12, leading=15, spaceBefore=9, spaceAfter=5)
    body_style = styles["BodyText"]
    logo_path = __import__("pathlib").Path(__file__).resolve().parents[1] / "assets" / "img" / "dclm-logo.png"
    story = [Paragraph("DCLM · KWARA STATE", styles["Normal"]), Spacer(1, 4), Paragraph("Pastor’s report", title_style),
             Paragraph(escape(data["scope_name"]) + " · " + escape(data["period_label"]), styles["Heading3"]),
             Paragraph(f"{'Including pending' if data['include_pending'] else 'Approved reports only'} · Generated {data['generated_at']:%d %b %Y %H:%M %Z} · {escape(data['generated_by'])}", styles["Normal"]), Spacer(1, 8)]
    if logo_path.exists():
        logo = PdfImage(str(logo_path), width=30 * mm, height=18 * mm, kind="proportional")
        story.insert(0, logo)
    for section_title, section in _sections(data):
        story.append(Paragraph(escape(section_title), head_style))
        # Use the same structured data values in PDF text; HTML components are
        # deliberately not stringified as they may contain scripts/markup.
        if section_title == "Key findings":
            for item in _insights(data["all_history"], data["children"], data["summary"]):
                story.append(KeepTogether([Paragraph(escape(item["text"]), body_style), Paragraph("How calculated: " + escape(item["how"]), styles["Italic"]), Spacer(1, 4)]))
        elif section_title == "Attendance":
            story.append(_pdf_trend(data["history"], Drawing, Line, Circle, Rect, String, colors))
            rows = [["Sunday", "Report state", "Population", "Categories"]] + [[r.get("occurrence_date", ""), "Counted" if r.get("total") is not None else "No report", "No report" if r.get("total") is None else str(r.get("total")), ", ".join(f"{CATEGORY_LABELS[k]} {_fmt((r.get('categories') or {}).get(k))}" for k in CATEGORY_KEYS if (r.get("categories") or {}).get(k) is not None) or "Categories not reported"] for r in data["history"]]
            story.append(_pdf_table(rows))
        elif section_title == "Offerings and tithes":
            total = float(data.get("offering_summary", {}).get("approved") or 0)
            approved_rows = _integer(data.get("offering_summary", {}).get("approved_records"))
            story.append(Paragraph(f"Approved in period: NGN {total:,.2f}." if approved_rows else "No approved offering records are available in this period.", body_style))
            prior_total = float(data.get("offering_previous", {}).get("approved") or 0)
            prior_rows = _integer(data.get("offering_previous", {}).get("approved_records"))
            delta = f"Change from previous equal-length period: {'+' if total >= prior_total else ''}NGN {total - prior_total:,.2f}." if approved_rows and prior_rows else "Change from previous period: not enough approved offering records to compare."
            story.append(Paragraph(f"{delta} Pending offering amount: NGN {float(data.get('offering_summary', {}).get('pending') or 0):,.2f}, shown separately.", body_style))
            rows = [["Date", "Program", "Fund", "Status", "Amount"]] + [[str(r.get("date")), str(r.get("program")), str(r.get("fund_type")), str(r.get("status")), f"NGN {float(r.get('amount') or 0):,.2f}"] for r in data["offerings"] if not r.get("error")]
            story.append(_pdf_table(rows))
        elif section_title == "Retreat and crusade summary":
            rows = [["Campaign", "Program", "Day", "Date", "State", "Coverage", "Sources", "Population", "Converts"]] + [[str(r.get("campaign_title") or r.get("campaign_name") or "Event"), str(r.get("program_type") or r.get("program_type_name") or "Program"), str(r.get("day_number") or "—"), str(r.get("date") or "—"), str(r.get("report_state") or "No report"), _event_coverage(r), _event_sources(r), "No report" if r.get("counted_population") is None else str(r.get("counted_population")), str(r.get("converts") or 0)] for r in data["events"]]
            story.append(_pdf_table(rows))
        elif section_title == "Appendix: definitions and data quality":
            for key, value in DEFINITIONS.items():
                story.append(Paragraph(f"<b>{escape(key.replace('_', ' ').title())}:</b> {escape(value)}", body_style))
        elif section_title == "Coverage":
            row = data["history"][-1] if data["history"] else {}
            c = row.get("coverage") or {}
            story.append(Paragraph(escape(f"{_integer(c.get('approved'))} approved; {_integer(c.get('pending'))} pending; {_integer(c.get('returned'))} returned; {_integer(c.get('conflict'))} conflict; {_integer(c.get('missing'))} not reported. Missing is not zero."), body_style))
        elif section_title == "Newcomers and converts":
            item = data["summary"].get("newcomer_period") or {}
            if _integer(item.get("newcomers_current")) or _integer(item.get("converts_current")):
                record_text = f"Newcomer records: {_fmt(item.get('newcomers_current'))}; convert records: {_fmt(item.get('converts_current'))}. These are records, not unique-person counts."
            else:
                record_text = "No newcomer or convert records are available for this period. No records does not mean a reported zero."
            story.append(Paragraph(escape(record_text), body_style))
        elif section_title == "Workers’ meeting":
            item = data["summary"].get("attendance_summary") or {}
            rows = [["Meeting", "Present", "Expected", "Rate", "Meetings"] , ["Workers meeting", _fmt(item.get("present")), _fmt(item.get("expected")), "Not enough reports" if not item.get("expected") else f"{float(item.get('rate') or 0):.1f}%", _fmt(item.get("meetings_reported"))]]
            story.append(_pdf_table(rows))
        elif section_title == "House Caring Fellowship":
            hcf_history = (data["standing"].get("house_caring_fellowship") or {}).get("scope") or []
            row = hcf_history[-1] if hcf_history else None
            if row is None or row.get("total") is None:
                story.append(Paragraph("Not reported. Missing fellowship data is not zero.", body_style))
            else:
                categories = row.get("categories") or {}
                detail = ", ".join(f"{CATEGORY_LABELS[k]}: {_fmt(categories[k])}" for k in CATEGORY_KEYS if categories.get(k) is not None) or "Category breakdown not recorded"
                story.append(Paragraph(escape(f"{row.get('occurrence_date')}: {_fmt(row.get('total'))} reported. {detail}"), body_style))
        elif section_title == "Waiting on a decision":
            rows = [["Request type", "Waiting", "Oldest age"]] + [[str(x.get("label")), _fmt(x.get("count")), "Age unavailable" if x.get("oldest_age_hours") is None else f"{_integer(x.get('oldest_age_hours'))} hours"] for x in data["summary"].get("pending_approvals") or []]
            story.append(_pdf_table(rows) if len(rows) > 1 else Paragraph("No pending decisions were reported for this scope.", body_style))
        else:
            story.append(Paragraph("See the attached workbook for structured detail.", body_style))
    def footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#53657a"))
        canvas.drawString(14 * mm, 9 * mm, "Powered by: Kwara State ICT Unit")
        canvas.drawRightString(A4[0] - 14 * mm, 9 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()


def _pdf_trend(history: list[dict[str, Any]], Drawing, Line, Circle, Rect, String, colors):
    drawing = Drawing(480, 150)
    left, right = 34, 466
    top, bottom = 112, 46
    slot = (right - left) / max(1, len(history))
    averages = [None if row.get("total") is None or not _integer(row.get("n_counted")) else _integer(row.get("total")) / _integer(row.get("n_counted")) for row in history]
    scale = max(1, max((value for value in averages if value is not None), default=0))
    for fraction in (0, .5, 1):
        y = bottom + (top - bottom) * fraction
        drawing.add(Line(left, y, right, y, strokeColor=colors.HexColor("#d5dce5"), strokeWidth=.35))
        drawing.add(String(0, y - 2, _fmt(round(scale * fraction)), fontSize=6, fillColor=colors.HexColor("#53657a")))
    prior_point = None
    for index, (row, value) in enumerate(zip(history, averages)):
        x = left + slot * (index + .5)
        if value is None:
            prior_point = None
        else:
            y = bottom + (top - bottom) * value / scale
            if prior_point is not None:
                drawing.add(Line(prior_point[0], prior_point[1], x, y, strokeColor=colors.HexColor("#174ea6"), strokeWidth=1.5))
            drawing.add(Circle(x, y, 2.3, fillColor=colors.HexColor("#174ea6"), strokeColor=colors.HexColor("#174ea6")))
            prior_point = (x, y)
        expected, received = _integer(row.get("n_expected")), _integer(row.get("n_received"))
        share = min(1, received / expected) if expected else 0
        bar_h = 18 * share
        drawing.add(Rect(x - min(6, slot * .22), 12, min(12, slot * .44), bar_h, fillColor=colors.HexColor("#16855b"), strokeColor=colors.HexColor("#16855b")))
        if index == 0 or index == len(history) - 1 or index % max(1, len(history) // 5) == 0:
            drawing.add(String(x - 10, 2, str(row.get("occurrence_date") or "")[-5:], fontSize=5, fillColor=colors.HexColor("#53657a")))
    drawing.add(String(left, 132, "Average population per counted location", fontSize=7, fillColor=colors.HexColor("#1b2b3c")))
    drawing.add(String(280, 132, "Coverage bars: reported / expected", fontSize=7, fillColor=colors.HexColor("#1b2b3c")))
    return drawing


def _pdf_table(rows: list[list[Any]]) -> Any:
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    wrapped = [[str(cell)[:250] for cell in row] for row in rows]
    table = Table(wrapped, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND_BLUE)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), .35, colors.HexColor("#aab6c4")),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f6fb")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def register_pastor_report_routes(app) -> None:
    async def load(request: Request, *, period: str = "4w", include_pending: bool = False, campaign_id: str = "", event_mode: str = ""):
        ctx = build_context(request)
        try:
            scoped_ctx = active_scope_context(request, ctx)
            with program_page_trace("pastor_report", str(scoped_ctx.current_scope_path or "")):
                data = await _report_data(request, scoped_ctx, period=period, include_pending=include_pending, campaign_id=campaign_id, event_mode=event_mode)
            return data, None
        except BackendClientError as exc:
            return None, str(exc)

    async def audit(request: Request, data: dict[str, Any], export_format: str) -> None:
        client = async_client(get_api_client())
        await client.audit_report_export(
            AuthService.get_access_token(request), export_kind="pastor_report", export_format=export_format,
            scope_path=data["scope_path"], start_date=data["start_date"].isoformat(), end_date=data["end_date"].isoformat(),
        )

    @app.get("/dashboard/pastor-report")
    async def pastor_report_page(request: Request, period: str = "4w", include_pending: bool = False, campaign_id: str = "", event_mode: str = ""):
        data, error = await load(request, period=period, include_pending=include_pending, campaign_id=campaign_id, event_mode=event_mode)
        ctx = build_context(request)
        if error:
            content = section_card("Pastor’s report could not load", "The report did not return data.", P(error, cls="text-danger mb-0"))
        else:
            sections = _sections(data)
            selected_campaign_id = str((data.get("selected_campaign") or {}).get("campaign_id") or campaign_id)
            selected_event_mode = str(data.get("event_mode") or event_mode)
            selector = HtmlForm(
                *hidden_context_inputs(ctx),
                Div(
                    Label("Period", HtmlSelect(*[HtmlOption("4 Sundays" if key == "4w" else "8 Sundays" if key == "8w" else label, value=key, selected=data["period"] == key) for key, (label, _weeks) in PERIODS.items()], HtmlOption("Events", value="event", selected=data["period"] == "event"), name="period", aria_label=f"Period, {data['period_label']}", cls="form-select pastor-report-select"), cls="pastor-report-control-label pastor-report-period-control"),
                    Label("Event type", HtmlSelect(HtmlOption("Retreat", value="retreat", selected=selected_event_mode == "retreat"), HtmlOption("Crusade", value="crusade", selected=selected_event_mode == "crusade"), name="event_mode", cls="form-select pastor-report-select"), cls="pastor-report-control-label pastor-report-event-type") if data["period"] == "event" else HtmlInput(type="hidden", name="event_mode", value=selected_event_mode),
                    Label("Campaign", HtmlSelect(HtmlOption("Choose a campaign", value=""), *[HtmlOption(str(row.get("title") or "Campaign"), value=str(row.get("campaign_id")), selected=str(row.get("campaign_id")) == selected_campaign_id) for row in data["campaigns"]], name="campaign_id", cls="form-select pastor-report-select"), cls="pastor-report-control-label pastor-report-campaign") if data["period"] == "event" else HtmlInput(type="hidden", name="campaign_id", value=selected_campaign_id),
                    Div(
                        Button(Icon("arrow-clockwise", cls="me-2"), "Update report", variant="primary", size="md", type="submit", cls="pastor-report-update"),
                        Div(
                            Button(Icon("three-dots-vertical"), type="button", variant="outline-primary", cls="pastor-report-more-toggle", aria_label="More report actions", title="More report actions", data_bs_toggle="dropdown", aria_expanded="false"),
                            Div(
                                Div("DCLM report actions", cls="dropdown-header"),
                                A(Icon("share-fill", cls="me-2"), "Share scoped link", href="#share-scoped-report", role="button", cls="dropdown-item", onclick="(function(){const reportUrl=window.location.href;if(navigator.share){navigator.share({title:'Pastor Report',url:reportUrl}).catch(()=>{});}else{window.open('https://api.whatsapp.com/send?text='+encodeURIComponent(reportUrl),'_blank');}})();return false;"),
                                Button(Icon("printer", cls="me-2"), "Print / Save PDF", type="button", cls="dropdown-item", onclick="fetch('/dashboard/pastor-report/record-print?" + urlencode({"scope_path": data["scope_path"], "period": data["period"], "include_pending": str(data["include_pending"]).lower(), "campaign_id": selected_campaign_id, "event_mode": selected_event_mode}) + "',{credentials:'same-origin'}).then(r=>{if(!r.ok)throw new Error('Could not record report access');window.print()}).catch(e=>alert(e.message))"),
                                A(Icon("file-earmark-pdf", cls="me-2"), "Download PDF", href=scope_link(ctx, "/dashboard/pastor-report/export.pdf", scope_path=data["scope_path"], period=data["period"], include_pending=str(data["include_pending"]).lower(), campaign_id=selected_campaign_id, event_mode=selected_event_mode), cls="dropdown-item"),
                                A(Icon("file-earmark-spreadsheet", cls="me-2"), "Export Excel", href=scope_link(ctx, "/dashboard/pastor-report/export.xlsx", scope_path=data["scope_path"], period=data["period"], include_pending=str(data["include_pending"]).lower(), campaign_id=selected_campaign_id, event_mode=selected_event_mode), cls="dropdown-item"),
                                A(Icon("filetype-csv", cls="me-2"), "Export CSV files", href=scope_link(ctx, "/dashboard/pastor-report/export.csv", scope_path=data["scope_path"], period=data["period"], include_pending=str(data["include_pending"]).lower(), campaign_id=selected_campaign_id, event_mode=selected_event_mode), cls="dropdown-item"),
                                cls="dropdown-menu dropdown-menu-end shadow-sm pastor-report-more-menu",
                            ),
                            cls="dropdown pastor-report-more",
                        ),
                        cls="pastor-report-primary-actions",
                    ),
                    cls="pastor-report-control-row",
                ),
                Div(Label(HtmlInput(type="checkbox", name="include_pending", value="true", checked=data["include_pending"], onchange="this.form.submit()"), Span("Include pending reports", cls="ms-2"), cls="form-check-label"), cls="pastor-report-pending-row"),
                method="get", action="/dashboard/pastor-report", cls="pastor-report-controls",
            )
            generated = data["generated_at"].strftime("%d %b %Y %H:%M %Z")
            scope_breadcrumb = _report_scope_breadcrumb(ctx, data)
            report_header = Div(
                Img(src="/assets/img/dclm-logo.png", alt="DCLM", cls="pastor-report-logo"),
                Div(P("DCLM · KWARA STATE", cls="pastor-report-overline"), H1("Pastor’s report", cls="pastor-report-title"), H2(data["scope_name"], cls="pastor-report-scope"), P(data["period_label"], cls="pastor-report-period"), P("Including pending reports" if data["include_pending"] else "Approved reports only", cls="pastor-report-status"), P(f"Generated {generated} by {data['generated_by']}", cls="pastor-report-generated"), cls="min-w-0"),
                cls="pastor-report-cover",
            )
            report_sections = [section_card(title, "", body, cls="pastor-report-section") for title, body in sections]
            content = Div(
                scope_breadcrumb, selector,
                Div(report_header, *report_sections, P("Powered by: Kwara State ICT Unit", cls="pastor-report-footer"), id="pastor-report-printable", cls="pastor-report-document"),
                Link(rel="stylesheet", href="/assets/css/pastor-report.css?v=20261113_02"),
                Script("if(new URLSearchParams(location.search).get('print')==='1'){fetch('/dashboard/pastor-report/record-print?'+new URLSearchParams(location.search),{credentials:'same-origin'}).then(r=>{if(!r.ok)throw new Error();window.print()}).catch(()=>document.querySelector('.pastor-report-page').insertAdjacentHTML('afterbegin','<div role=alert class=alert alert-danger>Could not record report access; printing was not started.</div>'))}"),
                cls="pastor-report-page",
            )
        return shell_layout(ctx, request_path=request.url.path, active_key="pastor-report", title="Pastor’s report", subtitle="A printable, scoped report with definitions and data-quality notes.", primary_action=None, content=page_stack(content), show_scope_breadcrumb=False)

    @app.get("/dashboard/pastor-report/export.xlsx")
    async def pastor_report_xlsx(request: Request, period: str = "4w", include_pending: bool = False, campaign_id: str = "", event_mode: str = ""):
        data, error = await load(request, period=period, include_pending=include_pending, campaign_id=campaign_id, event_mode=event_mode)
        if error:
            return Response(error, status_code=502, media_type="text/plain")
        try:
            content = _workbook_bytes(data)
            await audit(request, data, "xlsx")
        except (BackendClientError, ValueError) as exc:
            return Response(str(exc), status_code=502, media_type="text/plain")
        return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Cache-Control": "private, no-cache, no-store, must-revalidate", "Content-Disposition": f"attachment; filename=pastor-report-{data['start_date']}-{data['end_date']}.xlsx"})

    @app.get("/dashboard/pastor-report/record-print")
    async def pastor_report_record_print(request: Request, period: str = "4w", include_pending: bool = False, campaign_id: str = "", event_mode: str = ""):
        data, error = await load(request, period=period, include_pending=include_pending, campaign_id=campaign_id, event_mode=event_mode)
        if error:
            return Response(error, status_code=502, media_type="text/plain")
        try:
            await audit(request, data, "print")
        except BackendClientError as exc:
            return Response(str(exc), status_code=502, media_type="text/plain")
        return Response('{"recorded":true}', media_type="application/json")

    @app.get("/dashboard/pastor-report/export.csv")
    async def pastor_report_csv(request: Request, period: str = "4w", include_pending: bool = False, campaign_id: str = "", event_mode: str = ""):
        data, error = await load(request, period=period, include_pending=include_pending, campaign_id=campaign_id, event_mode=event_mode)
        if error:
            return Response(error, status_code=502, media_type="text/plain")
        try:
            content = _csv_zip_bytes(data)
            await audit(request, data, "csv_zip")
        except (BackendClientError, ValueError) as exc:
            return Response(str(exc), status_code=502, media_type="text/plain")
        return Response(content, media_type="application/zip", headers={"Cache-Control": "private, no-cache, no-store, must-revalidate", "Content-Disposition": f"attachment; filename=pastor-report-{data['start_date']}-{data['end_date']}-csv.zip"})

    @app.get("/dashboard/pastor-report/export.pdf")
    async def pastor_report_pdf(request: Request, period: str = "4w", include_pending: bool = False, campaign_id: str = "", event_mode: str = ""):
        data, error = await load(request, period=period, include_pending=include_pending, campaign_id=campaign_id, event_mode=event_mode)
        if error:
            return Response(error, status_code=502, media_type="text/plain")
        try:
            content = _pdf_bytes(data)
            await audit(request, data, "pdf")
        except (BackendClientError, ImportError, ValueError) as exc:
            return Response(f"PDF export failed: {exc}", status_code=502, media_type="text/plain")
        return Response(content, media_type="application/pdf", headers={"Cache-Control": "private, no-cache, no-store, must-revalidate", "Content-Disposition": f"attachment; filename=pastor-report-{data['start_date']}-{data['end_date']}.pdf"})
