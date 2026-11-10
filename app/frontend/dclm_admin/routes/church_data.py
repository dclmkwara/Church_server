from __future__ import annotations

import asyncio
import datetime

from fasthtml.common import A, Div, Form, H3, H4, Input, Label, Option, P, Select, Textarea
from decimal import Decimal, InvalidOperation
from starlette.requests import Request

from faststrap import Badge, Button, PlaceholderCard, Spinner, TabPane, Tabs

from ..backend import BackendClientError
from ..auth_context import build_context
from ..communication import ChurchDataService, PeopleService
from ..communication.dashboard_service import DashboardService
from ..communication.active_scope import active_scope_context
from ..communication.count_aggregation import aggregate_count_submissions
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, shell_layout
from ..components.ui import empty_state, filter_field, format_naira, page_intro, page_stack, responsive_table, section_card, stat_card, status_badge
from ..mock_data import STORE, UNITS
from ..source_intake import reject_source_submission, source_intake_notice
from app.core.program_page_perf import program_page_trace
from app.services.analytics.program_config import reporting_today


FUND_TYPES = ["offering", "tithe"]
PAYMENT_METHODS = ["Cash", "Bank Transfer", "Mobile Money"]
RECORD_STATUSES = ["follow_up_pending", "contacted", "integrated"]
RECORD_GENDERS = ["Male", "Female"]
ATTENDANCE_STATUSES = ["present", "late", "absent", "excused"]


def _scope_path(ctx) -> str:
    """Return the selected scope or the context current path."""
    return str((getattr(ctx, "query_extras", {}) or {}).get("scope_path") or getattr(ctx, "current_scope_path", ""))


def _can_remind_counts(ctx) -> bool:
    return bool(ctx.has_permission("counts:remind"))


def _scope_level_number(ctx) -> int:
    return max(0, len([part for part in _scope_path(ctx).split(".") if part]) - 1)


def _finance_rows_in_view(rows, *, date_from: str = "", date_to: str = "", include_pending: bool = False):
    filtered = list(rows)
    if date_from:
        filtered = [row for row in filtered if str(row.get("date") or "")[:10] >= date_from]
    if date_to:
        filtered = [row for row in filtered if str(row.get("date") or "")[:10] <= date_to]
    statuses = {"approved", "pending", "corrected"} if include_pending else {"approved"}
    return [row for row in filtered if str(row.get("status") or "").lower() in statuses]


def _finance_summary_for_rows(rows, *, date_from: str, date_to: str):
    period = list(rows)
    if date_from:
        period = [row for row in period if str(row.get("date") or "")[:10] >= date_from]
    if date_to:
        period = [row for row in period if str(row.get("date") or "")[:10] <= date_to]
    approved = [row for row in period if str(row.get("status") or "").lower() == "approved"]
    pending = [row for row in period if str(row.get("status") or "").lower() in {"pending", "corrected"}]
    rejected = [row for row in period if str(row.get("status") or "").lower() == "rejected"]
    return {
        "approved_total": sum((Decimal(str(row.get("amount") or 0)) for row in approved), Decimal("0")),
        "approved_count": len(approved),
        "pending_total": sum((Decimal(str(row.get("amount") or 0)) for row in pending), Decimal("0")),
        "pending_count": sum(str(row.get("status") or "").lower() == "pending" for row in pending),
        "corrected_count": sum(str(row.get("status") or "").lower() == "corrected" for row in pending),
        "rejected_count": len(rejected),
    }

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
    ctx = active_scope_context(request, ctx)
    if await ChurchDataService.live_enabled(request):
        return [{"value": row["location_id"], "label": row["location_name"]} for row in await PeopleService.list_locations(request, ctx)]
    scope_path = await ChurchDataService.effective_scope_path(request, ctx)
    return [{"value": row["location"], "label": row["location"]} for row in STORE.visible_locations(scope_path)]


async def _scope_events(request: Request, ctx) -> list[dict[str, str]]:
    ctx = active_scope_context(request, ctx)
    if await ChurchDataService.live_enabled(request):
        events = await ChurchDataService.list_events(request, ctx)
        if events:
            return [{"value": row["event_id"], "label": row["title"]} for row in events]
    scope_path = str((getattr(ctx, "query_extras", {}) or {}).get("scope_path") or getattr(ctx, "current_scope_path", ""))
    return [{"value": event["title"], "label": event["title"]} for event in STORE.list_program_events(scope_path)]


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
        Div(
            status_badge(row["status"]),
            Badge("Auto-accepted", variant="info") if row.get("auto_accepted") else "",
            cls="d-flex flex-wrap align-items-center gap-1 mb-2",
        ),
        P(f"Sections: {', '.join(sections)}", cls="small text-muted mb-2"),
        Div(
            Div(P("Counted total", cls="small text-muted mb-1"), P(str(row["total"]) if row["total"] is not None else "Not counted", cls="fw-semibold mb-0")),
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
    ctx = active_scope_context(request, ctx)
    summary = await ChurchDataService.count_summary(request, ctx)
    _month = reporting_today().strftime("%B")
    _year = reporting_today().year
    return _summary_grid(
        [
            ("Latest approved attendance", str(summary["latest_total"]) if summary["latest_total"] is not None else "No approved report", "Approved submissions only; pending and rejected values are excluded", "bar-chart"),
            (f"{_month} approved total", str(summary["monthly_total"]) if summary["monthly_total"] is not None else "No approved reports", f"Approved service totals in {_month} after combining submissions", "calendar3"),
            ("Locations reporting", str(summary["locations_reporting"]), "Locations with service counts this month", "geo-alt"),
            ("Average approved service", str(summary["average_total"]) if summary["average_total"] is not None else "No approved reports", "Average total per event, date, program, and reporting unit", "calculator"),
        ],
        grid_id="counts-stats",
        grid_cls="counts-stat-grid",
        oob=oob,
    )


async def _counts_table(request: Request, ctx, *, location: str = "", event_title: str = "", oob: bool = False) -> Div:
    ctx = active_scope_context(request, ctx)
    scope_path = str((getattr(ctx, "query_extras", {}) or {}).get("scope_path") or getattr(ctx, "current_scope_path", ""))
    rows = await ChurchDataService.list_counts(request, ctx, location=location, event_id=event_title) if await ChurchDataService.live_enabled(request) else STORE.list_counts(scope_path, location=location, event_title=event_title)
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
                str(row["total"]) if row["total"] is not None else "Not counted",
                Div(
                    status_badge(row["status"]),
                    Badge("Auto-accepted", variant="info") if row.get("auto_accepted") else "",
                    cls="d-flex flex-wrap align-items-center gap-1",
                ),
                Div(P(f"{row['submissions']} submission(s)", cls="fw-semibold mb-1"), P(", ".join(row["sections"]) or "Section labels are not recorded", cls="small text-muted mb-0")),
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
        ["Program", "Date", "Location / venue", "Approved total", "Review status", "Submissions", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="counts-results",
        oob="outerHTML:#counts-results" if oob else None,
    )


async def _count_review_workspace(request: Request, ctx, occurrence_date: str) -> Div:
    try:
        groups, unreported = await asyncio.gather(
            ChurchDataService.list_count_review_groups(request),
            ChurchDataService.list_unreported_sunday_locations(request, occurrence_date),
        )
    except BackendClientError as exc:
        return Div(P(f"Count review is unavailable: {exc}", cls="text-danger mb-0"), id="count-review-content")
    aged_10 = sum(bool(row.get("flag_10h")) for row in groups)
    aged_24 = sum(bool(row.get("flag_24h")) for row in groups)
    cards = await _summary_grid(
        [
            ("Pending groups", str(len(groups)), "Pending submissions grouped by reporting unit, program, and date", "clipboard-check"),
            ("Waiting 10+ hours", str(aged_10), "Needs attention for the accepting pastor", "clock"),
            ("Waiting 24+ hours", str(aged_24), "Escalates one level up for visibility", "exclamation-circle"),
            ("Unreported locations", str(len(unreported)), f"Sunday Worship on {occurrence_date}", "geo-alt"),
        ],
        grid_id="count-review-stats",
        grid_cls="counts-stat-grid",
    )
    review_cards = []
    for row in groups:
        flags = []
        if row.get("flag_10h"):
            flags.append(Badge("10+ hours", variant="warning", cls="me-1"))
        if row.get("flag_24h"):
            flags.append(Badge("24+ hours", variant="danger", cls="me-1"))
        if row.get("escalated"):
            flags.append(Badge("Escalated", variant="info", cls="me-1"))
        if row.get("group_state") == "conflict":
            flags.append(Badge("Conflict — excluded from totals", variant="danger", cls="me-1"))
        if row.get("auto_closed"):
            flags.append(Badge("Auto-closed; not confirmed by an usher", variant="warning", cls="me-1"))
        cat = row.get("categories") or {}
        categories = " • ".join(
            f"{label}: {int(cat.get(field) or 0)}"
            for label, field in (("Adult men", "adult_male"), ("Adult women", "adult_female"), ("Youth men", "youth_male"), ("Youth women", "youth_female"), ("Boys", "boys"), ("Girls", "girls"))
        )
        section_note = (
            f"{row.get('section_count', 0)} section(s): {', '.join(row.get('section_labels') or [])}"
            if row.get("sections_recorded") else f"{row.get('submission_count', 0)} submissions; section labels are not recorded"
        )
        correction_note = ""
        if row.get("correction_history"):
            latest_prior = row["correction_history"][-1]
            correction_note = Div(
                P("Correction history", cls="small fw-semibold mb-1"),
                P(f"This submission corrects rejected count {latest_prior['supersedes_id']} • {latest_prior.get('rejection_reason') or 'No reason recorded'}", cls="small text-warning-emphasis mb-0"),
                cls="rounded bg-warning-subtle p-2 mt-2",
            )
        if row.get("group_conflict"):
            actions = P("Conflict: resolve this count group before it can be approved.", cls="small text-danger mb-0")
        elif row.get("awaiting_close"):
            actions = P("Waiting for the lead usher to close this count group before approval.", cls="small text-muted mb-0")
        else:
            actions = P("Waiting for the accepting pastor; this level can view the delay but cannot decide this group.", cls="small text-muted mb-0")
        if row.get("actionable"):
            actions = Div(
                Form(
                    *hidden_context_inputs(ctx),
                    Button("Approve count group", variant="primary", size="md", type="submit"),
                    hx_post=ctx.url_for(f"/church-data/count-review/{row['count_id']}/approve"),
                    hx_target="#count-review-content", hx_swap="outerHTML", cls="d-inline-flex",
                ),
                Form(
                    *hidden_context_inputs(ctx),
                    Textarea(name="reason", required=True, rows="2", placeholder="Required reason for returning this count", cls="form-control mb-2"),
                    Button("Return for correction", variant="outline-danger", size="md", type="submit"),
                    hx_post=ctx.url_for(f"/church-data/count-review/{row['count_id']}/return"),
                    hx_target="#count-review-content", hx_swap="outerHTML", cls="mt-2",
                ),
                cls="d-grid gap-2 mt-3",
            )
        review_cards.append(
            Div(
                Div(H4(f"{row.get('program_type')} — {row.get('date')}", cls="h6 fw-semibold mb-0"), *flags, cls="d-flex flex-wrap gap-2 align-items-center justify-content-between"),
                P(f"{row.get('location')} • {row.get('program_level')} report • {row.get('event_title') or 'Standing program'} • Service: {row.get('service_id') or 'legacy'}", cls="small text-muted mt-2 mb-2"),
                Div(P(f"Pending total: {row.get('total')}", cls="h4 fw-semibold mb-0"), P(f"{row.get('submission_count')} submissions • {section_note}", cls="small text-muted mb-0"), cls="d-flex justify-content-between align-items-start gap-3 flex-wrap"),
                Div(*(P(f"{part.get('section_label') or part.get('count_mode') or 'Legacy part'}: {part.get('total')} • {part.get('status')}", cls="small mb-1") for part in row.get("parts", [])), cls="rounded bg-light p-2 mt-2") if row.get("split_count") else None,
                P(categories, cls="small mt-3 mb-1"),
                P(f"Submitted by {', '.join(row.get('submitters') or []) or 'Unknown'} • waiting {row.get('age_hours')} hours", cls="small text-muted mb-0"),
                P(
                    f"Edited {row.get('edited_count', 0)} time(s) • {row.get('edit_window_hours_left', 0)} hours remain"
                    if row.get("edited_count") else "No edits recorded • 24-hour correction window",
                    cls="small text-muted mt-1 mb-0",
                ),
                P(f"Returned for correction: {row.get('return_reason')}", cls="small text-warning-emphasis mt-2 mb-0") if row.get("return_reason") else None,
                correction_note,
                actions,
                cls="border rounded-3 bg-white p-3 p-lg-4 shadow-sm",
            )
        )
    if not review_cards:
        review_content = empty_state("clipboard-check", "No count groups need review", "Pending counts in this scope will appear here, oldest first.")
    else:
        review_content = Div(*review_cards, cls="d-grid gap-3")
    reminder_rows = []
    if _can_remind_counts(ctx):
        for row in unreported:
            reminder_rows.append(
            Div(
                Div(H4(row["location"], cls="h6 fw-semibold mb-1"), P(f"Sunday Worship • {row['date']}", cls="small text-muted mb-0")),
                Form(
                    *hidden_context_inputs(ctx),
                    Input(type="hidden", name="location_id", value=row["location_id"]),
                    Input(type="hidden", name="program_type_id", value=str(row["program_type_id"])),
                    Input(type="hidden", name="occurrence_date", value=row["date"]),
                    Button("Remind location", variant="outline-primary", size="md", type="submit"),
                    hx_post=ctx.url_for("/church-data/count-review/remind"),
                    hx_target="#count-review-content", hx_swap="outerHTML",
                ),
                cls="d-flex align-items-center justify-content-between gap-3 border rounded-3 p-3 bg-white",
            )
            )
    reminders = Div(
        H4("Unreported Sunday Worship", cls="h6 fw-semibold"),
        P("Locations without a report and not covered by a combined event. Reminders go to active users at the location through the in-app broadcast.", cls="small text-muted"),
        *(reminder_rows or ([empty_state("geo-alt", "No uncovered locations", f"No unreported locations were found for {occurrence_date}.")] if _can_remind_counts(ctx) else [P("Reminders are not available for this role.", cls="small text-muted")])),
        cls="d-grid gap-3 mt-4",
    )
    return Div(
        cards,
        Form(
            *hidden_context_inputs(ctx),
            filter_field("Sunday date", Input(type="date", name="occurrence_date", value=occurrence_date, required=True, cls="form-control"), field_id="count-review-date"),
            Button("Load date", variant="outline-primary", size="md", type="submit"),
            hx_get=ctx.url_for("/church-data/count-review/content"), hx_target="#count-review-content", hx_swap="outerHTML",
            cls="d-flex align-items-end gap-2 flex-wrap mb-3",
        ),
        Div(H4("Pending count groups", cls="h5 fw-semibold"), review_content, reminders, cls="mt-4"),
        id="count-review-content",
    )


async def _render_meeting_program_page(request: Request, ctx, *, title: str, subtitle: str, program_type_slug: str, active_key: str) -> Div:
    if not ctx.has_permission("attendance:read"):
        return shell_layout(ctx, request_path=request.url.path, active_key="attendance", title=title, subtitle=subtitle, primary_action=None, content=empty_state("shield-lock", "Attendance access required", "Your role does not include attendance reporting."), show_shell_intro=False)
    metrics = await DashboardService.meeting_program_metrics(request, ctx, program_type_slug=program_type_slug)
    rows = metrics.get("ranking") or []
    if rows:
        item = rows[0]
        cards = await _summary_grid(
            [
                ("Present workers", str(item.get("present", 0)), "Distinct workers marked present, counted once per meeting", "person-check"),
                ("Late workers", str(item.get("late", 0)), "Distinct workers marked late, counted once per meeting", "clock"),
                ("Attendance rate", f"{item.get('attendance_rate')}%" if item.get("attendance_rate") is not None else "No roster snapshot", "Present and late workers divided by the expected roster IDs for each meeting", "percent"),
                ("Meetings reported", str(item.get("meetings", 0)), "Distinct meeting occurrences with an attendance submission", "clipboard-data"),
            ],
            grid_id=f"{active_key}-stats", grid_cls="counts-stat-grid",
        )
    else:
        cards = empty_state("clipboard-check", "No attendance reports", f"No worker attendance rows are recorded for {title} in this scope.")
    monthly = metrics.get("monthly_trend") or []
    if monthly:
        trend_rows = [
            [row["period"], row["present"], row["late"], row["absent"], row["excused"], row["expected"], f"{row['attendance_rate']}%" if row.get("attendance_rate") is not None else "No roster snapshot", row["meetings"]]
            for row in monthly
        ]
        trend_table = responsive_table(
            ["Month", "Present workers", "Late", "Absent", "Excused", "Expected roster places", "Attendance rate", "Meetings reported"],
            trend_rows, [], results_id=f"{active_key}-trend",
        )
    else:
        trend_table = empty_state("calendar3", "No monthly trend yet", "Monthly rows appear after attendance is submitted for this meeting type.")
    leaders_panel = Div()
    if program_type_slug == "tuesday_leaders_meeting":
        raw_rows = await ChurchDataService.list_attendance(request, ctx, resolve_events=False)
        leader_rows = [
            row for row in raw_rows
            if "leader" in str(row.get("program_type") or "").casefold()
            or "leader" in str(row.get("event_title") or "").casefold()
        ]
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        for row in leader_rows:
            key = (row.get("date", ""), row.get("program_level", "unspecified").title(), row.get("location", "Unknown location"))
            grouped.setdefault(key, []).append(row)
        show_names = int(getattr(getattr(ctx, "profile", None), "level", 9) or 9) <= 3
        meeting_table_rows = []
        for (meeting_date, held_level, home_location), present_rows in sorted(grouped.items(), reverse=True):
            present = [row for row in present_rows if row.get("status") in {"present", "late"}]
            names = ", ".join(sorted({row.get("worker_name", "") for row in present if row.get("worker_name")})) if show_names else f"{len(present)} leaders present"
            meeting_table_rows.append([meeting_date, held_level, home_location, names, len(present)])
        meeting_table = responsive_table(
            ["Meeting date", "Level held", "Leader home location", "Leaders present" if show_names else "Reported presence", "Present entries"],
            meeting_table_rows, [], results_id="leaders-meeting-received",
        ) if meeting_table_rows else empty_state("people", "No leaders meetings received", "Submitted Tuesday Leaders Meeting attendance will appear here.")
        leaders_panel = section_card(
            "Meetings received",
            "Coverage is not defined. Home location comes from each stored worker attendance row; reported entries are shown without a unique-worker claim.",
            P("Raw records, not unique attendees. Summary metrics above deduplicate workers within each meeting.", cls="small text-warning-emphasis mb-2"),
            meeting_table,
        )
    body = page_stack(
        cards,
        leaders_panel,
        section_card(
            "Attendance trend",
            f"Monthly deduplicated meeting metrics for {title}; this page filters strictly to program type {program_type_slug}.",
            trend_table,
        ),
        section_card(
            "How to read these figures",
            "People are deduplicated within each meeting using the captured roster IDs. A worker may be counted again at a later meeting. Legacy meetings without roster IDs use the largest saved roster count once and are marked as legacy in the data.",
        ),
    )
    return shell_layout(
        ctx, request_path=request.url.path, active_key=active_key, title=title,
        subtitle=subtitle, primary_action=None, content=body, show_shell_intro=False,
    )


async def _meeting_program_page(request: Request, ctx, *, title: str, subtitle: str, program_type_slug: str, active_key: str) -> Div:
    page_key = "leaders" if program_type_slug == "tuesday_leaders_meeting" else "workers"
    with program_page_trace(page_key, str(getattr(ctx, "current_scope_path", "") or "")):
        return await _render_meeting_program_page(
            request, ctx, title=title, subtitle=subtitle,
            program_type_slug=program_type_slug, active_key=active_key,
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
    ctx = active_scope_context(request, ctx)
    today = reporting_today()
    date_from = (today - datetime.timedelta(days=27)).isoformat()
    date_to = today.isoformat()
    rows = await _load_finance_rows(request, ctx)
    return _finance_window_stats(rows, date_from=date_from, date_to=date_to, oob=oob)


def _finance_window_stats(rows, *, date_from: str, date_to: str, oob: bool = False) -> Div:
    summary = _finance_summary_for_rows(rows, date_from=date_from, date_to=date_to)
    return _summary_grid(
        [
            ("Approved in selected period", format_naira(summary["approved_total"]), f"{summary['approved_count']} approved entries - event date {date_from} to {date_to}", "cash-coin"),
            ("Awaiting review", format_naira(summary["pending_total"]), f"{summary['pending_count']} new - {summary['corrected_count']} corrected - same date range", "hourglass-split"),
            ("Rejected in selected period", str(summary["rejected_count"]), f"{date_from} to {date_to} - excluded from approved totals", "x-circle"),
        ],
        grid_id="finance-stats",
        grid_cls="counts-stat-grid",
        oob=oob,
    )


async def _load_finance_rows(request: Request, ctx, *, fund_type: str = "", location: str = "", method: str = ""):
    ctx = active_scope_context(request, ctx)
    return (await ChurchDataService.list_finance(request, ctx, fund_type=fund_type, location=location, method=method)
            if await ChurchDataService.live_enabled(request)
            else STORE.list_finance(_scope_path(ctx), fund_type=fund_type, location=location, method=method))


async def _finance_table(request: Request, ctx, *, fund_type: str = "", location: str = "", method: str = "", date_from: str = "", date_to: str = "", include_pending: bool = False, source_rows=None, results_id: str = "finance-results", oob: bool = False) -> Div:
    ctx = active_scope_context(request, ctx)
    rows = source_rows if source_rows is not None else await _load_finance_rows(request, ctx, fund_type=fund_type, location=location, method=method)
    rows = _finance_rows_in_view(rows, date_from=date_from, date_to=date_to, include_pending=include_pending)
    if not rows:
        attrs = {"id": results_id}
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
        results_id=results_id,
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
    ctx = active_scope_context(request, ctx)
    all_rows = await ChurchDataService.list_records(
        request,
        ctx,
        search=search,
        status=status,
        location=location,
        gender=gender,
    ) if await ChurchDataService.live_enabled(request) else STORE.list_records(
        _scope_path(ctx),
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
    ctx = active_scope_context(request, ctx)
    summary = await ChurchDataService.attendance_summary(request, ctx) if await ChurchDataService.live_enabled(request) else STORE.attendance_summary(_scope_path(ctx))
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


async def _sunday_population_expectation_panel(request: Request, ctx) -> Div:
    today = reporting_today()
    latest = today - datetime.timedelta(days=(today.weekday() + 1) % 7)
    result = await DashboardService.sunday_worship_series(
        request, ctx, weeks=4, latest_date=latest.isoformat(),
    )
    if not isinstance(result, dict):
        result = {"error": "Sunday population data is unavailable."}
    history = result.get("scope") or [] if isinstance(result, dict) else []
    current = history[-1] if history else {}
    if result.get("error") or result.get("unavailable"):
        explanation = result.get("error") or result.get("message") or "Sunday population data is unavailable."
        return section_card("Sunday Worship population attendance", "Congregation population is shown separately from the worker roster below.", P(str(explanation), role="alert", cls="text-danger mb-0"))
    percent = current.get("expected_population_percent")
    if not current.get("locations_with_estimate"):
        expected_label, expected_note = "No estimates yet", "The State Overseer has not entered expected Sunday attendance estimates in this scope."
    else:
        expected_label = "No eligible report" if percent is None else f"{float(percent):.1f}%"
        expected_note = (
            "No counted location report has both an estimate and a population count."
            if percent is None else
            f"Pooled over {int(current.get('expected_population_counted_locations') or 0)} counted locations with estimates; "
            f"{int(current.get('expected_population_no_estimate_locations') or 0)} counted locations have no estimate."
        )
    return section_card(
        "Sunday Worship population attendance",
        f"Congregation population for {latest.isoformat()}, separate from worker attendance.",
        Div(
            stat_card("% of expected Sunday attendance", expected_label, expected_note, "graph-up", tone="primary"),
            stat_card("Counted population", "No counted report" if current.get("total") is None else f"{int(current.get('total') or 0):,}", "Location-level reports counted for this Sunday", "people", tone="success"),
            stat_card("Expected Sunday attendance", "No estimate" if current.get("expected_population_total") is None else f"{int(current.get('expected_population_total') or 0):,}", "Pooled estimate for locations with counted reports", "bullseye", tone="info"),
            cls="counts-stat-grid",
        ),
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
    ctx = active_scope_context(request, ctx)
    rows = await ChurchDataService.list_attendance(request, ctx, status=status, location=location, unit=unit, event_id=event_title) if await ChurchDataService.live_enabled(request) else STORE.list_attendance(
        _scope_path(ctx),
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
    @app.get("/church-data/meetings/workers-saturday")
    async def saturday_workers_meeting_page(request: Request):
        ctx = active_scope_context(request, build_context(request))
        return await _meeting_program_page(
            request, ctx, title="Saturday Workers Meeting",
            subtitle="Weekly worker attendance records for Saturday Workers Meeting.",
            program_type_slug="saturday_workers_meeting", active_key="workers-meeting",
        )

    @app.get("/church-data/meetings/leaders-tuesday")
    async def tuesday_leaders_meeting_page(request: Request):
        ctx = active_scope_context(request, build_context(request))
        return await _meeting_program_page(
            request, ctx, title="Tuesday Leaders Meeting",
            subtitle="Weekly leader attendance records for Tuesday Leaders Meeting.",
            program_type_slug="tuesday_leaders_meeting", active_key="leaders-meeting",
        )

    @app.get("/church-data/count-review")
    async def count_review_page(request: Request, occurrence_date: str = ""):
        ctx = active_scope_context(request, build_context(request))
        if not ctx.has_permission("counts:review"):
            return shell_layout(ctx, request_path=request.url.path, active_key="counts", title="Count Review", subtitle="Count approvals are restricted to the accepting pastor.", primary_action=None, content=empty_state("shield-lock", "Review access required", "Your role does not approve program counts."), show_shell_intro=False)
        if not occurrence_date:
            local_today = reporting_today()
            occurrence_date = (local_today - datetime.timedelta(days=(local_today.weekday() - 6) % 7)).isoformat()
        content = await _count_review_workspace(request, ctx, occurrence_date)
        return shell_layout(
            ctx, request_path=request.url.path, active_key="count-review", title="Count Review",
            subtitle="Approve or return count submissions together, and follow up on unreported Sunday Worship.",
            primary_action=None, content=content, show_shell_intro=False,
        )

    @app.get("/church-data/count-review/content")
    async def count_review_content(request: Request, occurrence_date: str = ""):
        ctx = active_scope_context(request, build_context(request))
        if not ctx.has_permission("counts:review"):
            return Div(P("Count review access is required.", cls="text-danger"), id="count-review-content")
        if not occurrence_date:
            local_today = reporting_today()
            occurrence_date = (local_today - datetime.timedelta(days=(local_today.weekday() - 6) % 7)).isoformat()
        return await _count_review_workspace(request, ctx, occurrence_date)

    @app.post("/church-data/count-review/{count_id}/approve")
    async def count_review_approve(request: Request, count_id: str):
        ctx = build_context(request)
        if not ctx.has_permission("counts:review"):
            return Div(P("Count review access is required.", cls="text-danger"), id="count-review-content")
        try:
            await ChurchDataService.approve_count_group(request, count_id)
            local_today = reporting_today()
            sunday = (local_today - datetime.timedelta(days=(local_today.weekday() - 6) % 7)).isoformat()
            panel = await _count_review_workspace(request, ctx, sunday)
            return simple_toast_response(panel, "Every pending submission in this count group was approved.", title="Count approved")
        except BackendClientError as exc:
            return Div(P(f"Approval was not saved: {exc}", cls="text-danger"), id="count-review-content")

    @app.post("/church-data/count-review/{count_id}/return")
    async def count_review_return(request: Request, count_id: str):
        ctx = build_context(request)
        if not ctx.has_permission("counts:review"):
            return Div(P("Count review access is required.", cls="text-danger"), id="count-review-content")
        form = await request.form()
        reason = str(form.get("reason") or "").strip()
        if not reason:
            return Div(P("Enter a reason before returning this count group.", cls="text-danger"), id="count-review-content")
        try:
            await ChurchDataService.return_count_group(request, count_id, reason=reason)
            local_today = reporting_today()
            sunday = (local_today - datetime.timedelta(days=(local_today.weekday() - 6) % 7)).isoformat()
            panel = await _count_review_workspace(request, ctx, sunday)
            return simple_toast_response(panel, "Every pending submission in this count group was returned with the supplied reason.", title="Count returned", variant="warning")
        except BackendClientError as exc:
            return Div(P(f"Return was not saved: {exc}", cls="text-danger"), id="count-review-content")

    @app.post("/church-data/count-review/remind")
    async def count_review_remind(request: Request):
        ctx = build_context(request)
        if not _can_remind_counts(ctx):
            return Div(P("Count reminder access is required.", cls="text-danger"), id="count-review-content")
        form = await request.form()
        payload = {key: str(form.get(key) or "") for key in ("location_id", "program_type_id", "occurrence_date")}
        try:
            await ChurchDataService.remind_count_location(request, payload)
            panel = await _count_review_workspace(request, ctx, payload["occurrence_date"])
            return simple_toast_response(panel, "An in-app reminder was sent to users at the location.", title="Reminder sent")
        except BackendClientError as exc:
            return Div(P(f"Reminder was not sent: {exc}", cls="text-danger"), id="count-review-content")

    @app.get("/church-data/counts")
    async def counts_page(request: Request, location: str = "", event_title: str = ""):
        ctx = active_scope_context(request, build_context(request))
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
        ctx = active_scope_context(request, build_context(request))
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
        ctx = active_scope_context(request, build_context(request))
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
        ctx = active_scope_context(request, ctx)
        source_rows = await ChurchDataService.list_counts(request, ctx) if await ChurchDataService.live_enabled(request) else STORE.list_counts(_scope_path(ctx))
        row = next((entry for entry in source_rows if entry["count_id"] == count_id), None)
        if row is None:
            return P("Count not found.", cls="text-muted")
        service_rows = [
            entry for entry in source_rows
            if (entry["event_id"], entry["date"], entry["location_id"], entry.get("program_type"), entry.get("program_level"), entry.get("program_scope_path"))
            == (row["event_id"], row["date"], row["location_id"], row.get("program_type"), row.get("program_level"), row.get("program_scope_path"))
        ]
        approved_rows = [entry for entry in service_rows if entry.get("status") == "approved"]
        category_fields = ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")
        combined = {field: sum(int(entry.get(field) or 0) for entry in approved_rows) for field in category_fields}
        rejected_rows = [entry for entry in service_rows if entry.get("status") == "rejected"]
        return Div(
            H3(row.get("program_type") or row["event_title"], cls="h5 fw-semibold"),
            P(f"{row['location']} - {row['date']}", cls="text-muted"),
            P(f"Review status: {row['status']} • {len(service_rows)} submission(s); {len(approved_rows)} approved", cls="small text-muted"),
            Div(
                Div(P("Adult male", cls="small text-muted mb-1"), P(str(combined["adult_male"]), cls="fw-semibold mb-0")),
                Div(P("Adult female", cls="small text-muted mb-1"), P(str(combined["adult_female"]), cls="fw-semibold mb-0")),
                Div(P("Youth male", cls="small text-muted mb-1"), P(str(combined["youth_male"]), cls="fw-semibold mb-0")),
                Div(P("Youth female", cls="small text-muted mb-1"), P(str(combined["youth_female"]), cls="fw-semibold mb-0")),
                Div(P("Boys", cls="small text-muted mb-1"), P(str(combined["boys"]), cls="fw-semibold mb-0")),
                Div(P("Girls", cls="small text-muted mb-1"), P(str(combined["girls"]), cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            Div(P("Approved total", cls="small text-muted mb-1"), P(str(sum(combined.values())) if approved_rows else "Not counted", cls="display-6 fw-semibold mb-0"), cls="drawer-note-box mt-3"),
            Div(P(f"Rejected submissions: {len(rejected_rows)}", cls="small text-danger mb-0"), P(rejected_rows[-1].get("rejection_reason") or "", cls="small text-muted mb-0") if rejected_rows else "", cls="mt-2") if rejected_rows else "",
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
    async def finance_page(request: Request, fund_type: str = "", location: str = "", method: str = "", date_from: str = "", date_to: str = "", include_pending: bool = False):
        ctx = active_scope_context(request, build_context(request))
        today = reporting_today()
        date_from = date_from or (today - datetime.timedelta(days=27)).isoformat()
        date_to = date_to or today.isoformat()
        body = await _church_data_loading_shell(
            request,
            ctx,
            title="Offerings and Tithes",
            subtitle="Record and review finance entries.",
            section_title="Finance overview",
            section_note="Offering, tithe, and payment records.",
            target_url=ctx.url_for("/church-data/finance/content", fund_type=fund_type, location=location, method=method, date_from=date_from, date_to=date_to, include_pending=str(include_pending).lower()),
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
    async def finance_content(request: Request, fund_type: str = "", location: str = "", method: str = "", date_from: str = "", date_to: str = "", include_pending: bool = False):
        ctx = active_scope_context(request, build_context(request))
        today = reporting_today()
        date_from = date_from or (today - datetime.timedelta(days=27)).isoformat()
        date_to = date_to or today.isoformat()
        locations, source_rows = await asyncio.gather(
            _scope_locations(request, ctx),
            _load_finance_rows(request, ctx, fund_type=fund_type, location=location, method=method),
        )
        stats = _finance_window_stats(source_rows, date_from=date_from, date_to=date_to)
        table = await _finance_table(
            request, ctx, fund_type=fund_type, location=location, method=method,
            date_from=date_from, date_to=date_to, include_pending=include_pending,
            source_rows=source_rows,
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
            filter_field("From", Input(type="date", name="date_from", value=date_from, cls="form-control"), field_id="finance-date-from"),
            filter_field("To", Input(type="date", name="date_to", value=date_to, cls="form-control"), field_id="finance-date-to"),
            Label(Input(type="checkbox", name="include_pending", value="true", checked=include_pending), " Include pending entries", cls="form-check-label d-flex align-items-center gap-2"),
            Button("Apply filters", variant="primary", type="submit"),
            hx_get=ctx.url_for("/church-data/finance/list"),
            hx_target="#finance-results",
            hx_swap="outerHTML",
            hx_trigger="change from:select, change from:input[type=checkbox], submit",
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
    async def finance_list(request: Request, fund_type: str = "", location: str = "", method: str = "", date_from: str = "", date_to: str = "", include_pending: bool = False):
        ctx = active_scope_context(request, build_context(request))
        rows = await _load_finance_rows(request, ctx, fund_type=fund_type, location=location, method=method)
        stats = _finance_window_stats(rows, date_from=date_from, date_to=date_to, oob=True)
        table = await _finance_table(
            request, ctx, fund_type=fund_type, location=location, method=method,
            date_from=date_from, date_to=date_to, include_pending=include_pending,
            source_rows=rows, results_id="finance-results-content",
        )
        return Div(stats, table, id="finance-results")

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
                P("Returning sends the entry back to its submitter and opens a fresh 24-hour edit window. Rejection is final.", cls="small text-muted"),
                Textarea(name="note", placeholder="Review note or correction instructions", cls="form-control", rows="3"),
                Div(
                    Button("Approve", type="submit", name="decision", value="approved", variant="success", size="md"),
                    Button("Return for correction", type="submit", name="decision", value="returned", variant="outline-warning", size="md"),
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
        if decision not in {"approved", "rejected", "returned"}:
            return P("Choose approve or reject.", cls="text-danger")
        if decision == "rejected" and len(note) < 20:
            return P("A rejection reason must contain at least 20 characters.", cls="text-danger")
        try:
            if decision == "returned":
                await ChurchDataService.return_finance(request, entry_id, note or "Please review and correct this offering.")
            else:
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
        ctx = active_scope_context(request, build_context(request))
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
        ctx = active_scope_context(request, build_context(request))
        if _scope_level_number(ctx) <= 3:
            analytics = await DashboardService.newcomer_analytics(request, ctx)
            return Div(
                section_card(
                    "Privacy-protected summary",
                    "Person-level names and contact details are available only at Group and Location scope.",
                    Div(
                        await _summary_grid([
                            ("Newcomers", str(analytics.get("newcomers_total", 0)), "Count in this scope", "person-plus"),
                            ("Converts", str(analytics.get("converts_total", 0)), "Count in this scope", "people"),
                            ("Male", str(analytics.get("male", 0)), "Recorded gender", "person"),
                            ("Female", str(analytics.get("female", 0)), "Recorded gender", "person"),
                        ], grid_id="newcomer-privacy-summary", grid_cls="counts-stat-grid"),
                        P("Individual records are intentionally withheld at Region and State scope.", cls="small text-muted mb-0 mt-2"),
                    ),
                ),
                id="newcomer-page-content",
            )
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
        ctx = active_scope_context(request, build_context(request))
        if _scope_level_number(ctx) <= 3:
            return P("Person-level records are available only at Group and Location scope.", cls="text-muted", role="status")
        return await _records_workspace(request, ctx, search=search, status=status, location=location, gender=gender)

    @app.get("/church-data/newcomers/new")
    async def new_record_form(request: Request):
        return source_intake_notice("Newcomer and convert registrations")

    @app.post("/church-data/newcomers/create")
    async def create_record(request: Request):
        return reject_source_submission()

    @app.get("/church-data/newcomers/{record_id}/drawer")
    async def record_drawer(request: Request, record_id: str):
        ctx = active_scope_context(request, build_context(request))
        if _scope_level_number(ctx) <= 3:
            return P("Person-level details are available only at Group and Location scope.", cls="text-muted", role="status")
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
        ctx = active_scope_context(request, build_context(request))
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
        ctx = active_scope_context(request, build_context(request))
        events, locations, stats_div, table_div, sunday_population_panel = await asyncio.gather(
            _scope_events(request, ctx),
            _scope_locations(request, ctx),
            _attendance_stats(request, ctx),
            _attendance_table(request, ctx, status=status, location=location, unit=unit, event_title=event_title),
            _sunday_population_expectation_panel(request, ctx),
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
        return Div(
            section_card(
                "Population attendance",
                "Sunday Worship, House Caring Fellowship, Monday Bible Study and Thursday Revival Hour.",
                A("Open recurring-program attendance", href=ctx.url_for("/church-data/population-attendance", program_key="sunday_worship_service", weeks="4"), cls="btn btn-outline-primary"),
            ),
            sunday_population_panel,
            section_card(
                "Worker attendance overview",
                "Worker roster attendance totals, filters, and records.",
                source_intake_notice("Worker and leader attendance"),
                stats_div,
                filter_form,
                table_div,
            ),
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
