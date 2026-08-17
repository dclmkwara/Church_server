from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from fasthtml.common import Div, Form, H3, H4, Input, Option, P, Select, Span, Textarea
from starlette.requests import Request

from faststrap import Button, PlaceholderCard, Spinner, TabPane, Tabs, ToggleGroup

from ..auth_context import build_context
from ..communication import PeopleService, ProgramService
from ..components.chartjs import bar_chart as _bar_chart
from ..components.chartjs import donut_chart as _donut_chart
from ..components.feedback import simple_toast_response
from ..components.shell import hidden_context_inputs, primary_button, shell_layout
from ..components.ui import empty_state, filter_field, page_intro, page_stack, responsive_table, section_card, status_badge


EVENT_STATUSES = ["scheduled", "completed", "cancelled", "draft"]
CAMPAIGN_STATUSES = ["draft", "active", "closed", "archived"]
CAMPAIGN_MODES = ["crusade", "retreat", "special", "regular"]
ASSIGNMENT_TYPES = ["both", "count", "convert"]
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


def _segment_label(value: str) -> str:
    return value.replace("_", " ").title() if value else "General"


def _chart_legend(rows: list[dict[str, Any]]) -> Any:
    return Div(
        *[
            Div(
                Div(cls="report-legend-swatch", style=f"background:{row['color']};"),
                Span(str(row["label"]), cls="small text-muted"),
                Span(str(row.get("display") or row.get("value") or ""), cls="small fw-semibold text-dark"),
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


async def _scope_locations(request: Request, ctx) -> list[str]:
    rows = await PeopleService.list_locations(request, ctx)
    options = []
    for row in rows:
        location = row.get("location_name") or row.get("location_id") or ""
        if location and location not in options:
            options.append(location)
    return options


async def _program_summary(request: Request, ctx) -> Div:
    summary = await ProgramService.summary(request, ctx)
    return Div(
        Div(P("Domains", cls="small text-muted mb-1"), H3(str(summary["domains"]), cls="h4 fw-semibold mb-0")),
        Div(P("Types", cls="small text-muted mb-1"), H3(str(summary["types"]), cls="h4 fw-semibold mb-0")),
        Div(P("Campaigns", cls="small text-muted mb-1"), H3(str(summary["campaigns"]), cls="h4 fw-semibold mb-0")),
        Div(P("Events", cls="small text-muted mb-1"), H3(str(summary["events"]), cls="h4 fw-semibold mb-0")),
        Div(P("Still scheduled", cls="small text-muted mb-1"), H3(str(summary["scheduled"]), cls="h4 fw-semibold mb-0")),
        cls="counts-stat-grid",
    )


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
        Div(P(row["location"], cls="small text-muted mb-0"), P(row["date"], cls="small text-muted mb-0"), cls="d-flex justify-content-between gap-2 mb-3"),
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
        ["Title", "Type", "Domain", "Location", "Date", "Status", "Action"],
        desktop_rows,
        mobile_cards,
        results_id="program-events-results",
        oob="outerHTML:#program-events-results" if oob else None,
    )


def _campaign_activity_summary(activity: dict[str, object]) -> Div:
    return Div(
        Div(P("Events", cls="small text-muted mb-1"), H4(str(activity["event_count"]), cls="h6 fw-semibold mb-0")),
        Div(P("Population", cls="small text-muted mb-1"), H4(str(activity["total_population"]), cls="h6 fw-semibold mb-0")),
        Div(P("Alpha ground", cls="small text-muted mb-1"), H4(str(activity["alpha_population"]), cls="h6 fw-semibold mb-0")),
        Div(P("Satellite", cls="small text-muted mb-1"), H4(str(activity["satellite_population"]), cls="h6 fw-semibold mb-0")),
        Div(P("Converts", cls="small text-muted mb-1"), H4(str(activity["converts"]), cls="h6 fw-semibold mb-0")),
        Div(P("Newcomers", cls="small text-muted mb-1"), H4(str(activity["newcomers"]), cls="h6 fw-semibold mb-0")),
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
                    P(f"Segment: {_segment_label(str(row.get('audience_segment') or ''))}", cls="small text-dark mb-1"),
                    P(f"Population: {row['population']}", cls="small text-dark mb-1"),
                    P(f"Alpha: {row['alpha_population']}", cls="small text-dark mb-1"),
                    P(f"Satellite: {row['satellite_population']}", cls="small text-dark mb-1"),
                    P(f"Converts: {row['converts']}", cls="small text-dark mb-1"),
                    P(f"Newcomers: {row['newcomers']}", cls="small text-dark mb-1"),
                    P(f"Assignments submitted: {row.get('assignment_submitted', 0)}/{row.get('assignment_total', 0)}", cls="small text-dark mb-0"),
                ),
                cls="mobile-worker-card",
            )
        )
    return responsive_table(
        ["Event", "Location", "Date", "Segment", "Population", "Alpha", "Satellite", "Converts", "Newcomers", "Assignments"],
        desktop_rows,
        mobile_cards,
        results_id="campaign-activity-results",
    )


async def _campaign_report_panel(ctx, campaign: dict[str, Any], activity: dict[str, Any], *, view: str) -> Div:
    source_rows = [
        {"label": "Alpha", "value": _safe_int(activity.get("alpha_population")), "display": str(activity.get("alpha_population") or 0), "color": "#0f766e"},
        {"label": "Satellite", "value": _safe_int(activity.get("satellite_population")), "display": str(activity.get("satellite_population") or 0), "color": "#2563eb"},
    ]
    follow_up_rows = [
        {"label": "Converts", "value": _safe_int(activity.get("converts")), "display": str(activity.get("converts") or 0), "color": "#7c3aed"},
        {"label": "Newcomers", "value": _safe_int(activity.get("newcomers")), "display": str(activity.get("newcomers") or 0), "color": "#ea580c"},
    ]
    trend_rows = [
        {
            "label": str(row.get("date") or row.get("title") or "Event"),
            "value": _safe_int(row.get("population")),
            "display": str(row.get("population") or 0),
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
    segment_rows = [
        {
            "label": _segment_label(str(row.get("segment") or "")),
            "value": _safe_int(row.get("population")),
            "display": str(row.get("population") or 0),
            "color": color,
        }
        for row, color in zip(
            activity.get("segment_breakdown") or [],
            ["#0f766e", "#2563eb", "#7c3aed", "#ea580c", "#1d4ed8", "#be123c"],
        )
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
                "Adult, campus, youth, and children reporting stays visible when the campaign is a retreat cycle.",
                _bar_chart(segment_rows, label="Retreat audience segment breakdown") if campaign["event_mode"] == "retreat" and segment_rows else empty_state("pie-chart", "No retreat segments", "No audience-segmented retreat events are available."),
                _chart_legend(segment_rows) if campaign["event_mode"] == "retreat" and segment_rows else Div(),
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
                    _donut_chart(source_rows, label="Population source split", total_label="Population"),
                    _chart_legend(source_rows),
                ),
                section_card(
                    "Follow-up split",
                    "Crusade and retreat follow-up reporting.",
                    _donut_chart(follow_up_rows, label="Follow-up split", total_label="People"),
                    _chart_legend(follow_up_rows),
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
                    _bar_chart(segment_rows, label="Retreat audience segment breakdown") if campaign["event_mode"] == "retreat" and segment_rows else empty_state("bar-chart-line", "No retreat segments", "No audience-segmented retreat events are available."),
                    _chart_legend(segment_rows) if campaign["event_mode"] == "retreat" and segment_rows else Div(),
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
            "Officiating workers",
            "Use assignments for crusade alpha-ground count and convert control.",
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
                P(f"{row['assignment_type'].title()} - {row['source_role'].title()}", cls="small text-dark mb-1"),
                P(row["assignment_label"] or "No block/label set", cls="small text-dark mb-2"),
                P(f"Submitted at: {row['submitted_at'] or 'Not yet'}", cls="small text-dark mb-2"),
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
    workspace = Div(
        Tabs(
            ("program-domains", "Domains", True),
            ("program-types", "Types"),
            ("program-campaigns", "Campaigns"),
            ("program-events", "Events"),
            variant="pills",
            cls="mb-3",
        ),
        Div(
            TabPane(
                Div(
                    Div(
                        H4("Program domains", cls="h6 fw-semibold mb-1"),
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
                        H4("Program types", cls="h6 fw-semibold mb-1"),
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
                        H4("Program campaigns", cls="h6 fw-semibold mb-1"),
                        P("Crusades, retreats, and special program cycles begin here before event-level recording starts.", cls="text-muted mb-0"),
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
                        H4("Program events", cls="h6 fw-semibold mb-1"),
                        P("Events are the actual meetings that counts, finance, and attendance attach to.", cls="text-muted mb-0"),
                        cls="mb-3",
                    ),
                    event_filter_form,
                    events_tbl,
                ),
                tab_id="program-events",
            ),
            cls="tab-content",
        ),
    )
    return section_card(
        "Programs",
        "Domains, campaigns, and events for the selected scope.",
        summary_card,
        Div(
            primary_button(
                "Create Campaign",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/church-data/programs/campaigns/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            primary_button(
                "Add Domain",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/church-data/programs/domains/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            primary_button(
                "Add Type",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/church-data/programs/types/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            cls="d-grid d-md-flex gap-2 mb-4",
        ),
        workspace,
    )


async def _programs_loading_shell(ctx, **params: str) -> Div:
    return Div(
        Div(
            H3("Programs", cls="h5 fw-semibold mb-3"),
            Div(
                Spinner(variant="primary", size="md", label="Loading programs"),
                P(
                    "Loading program records.",
                    cls="text-muted mb-0",
                ),
                cls="d-flex align-items-center gap-3 py-2",
            ),
        ),
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
        ctx = build_context(request)
        body = page_stack(
            page_intro(
                "Programs and Events",
                "Manage domains, types, and event instances used by the rest of the admin records.",
                scope_label=ctx.current_scope_label,
                scope_kind=ctx.current_scope_kind,
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
                "Create Campaign",
                href="#",
                data_bs_toggle="offcanvas",
                data_bs_target="#form-drawer",
                hx_get=ctx.url_for("/church-data/programs/campaigns/new"),
                hx_target="#form-drawer-body",
                hx_swap="innerHTML",
            ),
            content=body,
        )

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
        ctx = build_context(request)
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

    @app.get("/church-data/programs/types/list")
    async def types_list(request: Request, types_domain_id: str = ""):
        ctx = build_context(request)
        return await _types_table(request, ctx, domain_id=types_domain_id)

    @app.get("/church-data/programs/campaigns/list")
    async def campaigns_list(
        request: Request,
        campaign_domain_id: str = "",
        campaign_event_mode: str = "",
        campaign_status: str = "",
    ):
        ctx = build_context(request)
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
        ctx = build_context(request)
        return await _events_table(request, ctx, search=event_search, domain_id=domain_id, type_id=type_id, status=status, location=location)

    @app.get("/church-data/programs/campaigns/new")
    async def new_campaign_form(request: Request):
        ctx = build_context(request)
        domains = await ProgramService.list_domains(request, ctx)
        locations = await PeopleService.list_locations(request, ctx)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Create campaign", cls="h5 fw-semibold"),
            P("Create the real crusade, retreat, or special program cycle first. Events and reporting will sit under it.", cls="text-muted"),
            Input(type="text", name="title", placeholder="Campaign title", cls="form-control mb-3", required=True),
            Input(type="text", name="campaign_code", placeholder="Campaign code", cls="form-control mb-3", required=True),
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
                Input(type="date", name="start_date", value=date.today().isoformat(), cls="form-control", required=True),
                Input(type="date", name="end_date", value=date.today().isoformat(), cls="form-control", required=True),
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
            Textarea(name="description", placeholder="Short campaign description", cls="form-control mb-3", rows="3"),
            Textarea(name="publicity_note", placeholder="Publicity note", cls="form-control mb-3", rows="2"),
            Button("Save campaign", variant="success", size="md", type="submit", cls="w-100"),
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
            return P("Could not save this campaign right now.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(H3("Campaign saved", cls="h5 fw-semibold"), P(f"{row['title']} is now ready for event planning and submissions.", cls="mb-0")),
                await _campaigns_table(request, ctx, domains=await ProgramService.list_domains(request, ctx), oob=True),
            ),
            message="Program campaign saved.",
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
                Div(H3("Domain saved", cls="h5 fw-semibold"), P(f"{row['name']} is now available for program types.", cls="mb-0")),
                await _domains_table(request, ctx, oob=True),
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
                Div(H3("Type saved", cls="h5 fw-semibold"), P(f"{row['name']} is now ready for event creation.", cls="mb-0")),
                await _types_table(request, ctx, oob=True),
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
        domains = await ProgramService.list_domains(request, ctx)
        campaigns = await ProgramService.list_campaigns(request, ctx)
        return Form(
            *hidden_context_inputs(ctx),
            H3("Create event", cls="h5 fw-semibold"),
            P("This is the event record other pages will use for counts, finance, and attendance.", cls="text-muted"),
            Input(type="text", name="title", placeholder="Event title", cls="form-control mb-3", required=True),
            Div(
                Select(
                    Option("Select domain", value=""),
                    *[Option(row["name"], value=row["domain_id"]) for row in domains],
                    name="domain_id",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select type", value=""),
                    *[Option(row["name"], value=row["type_id"]) for row in await ProgramService.list_types(request, ctx)],
                    name="type_id",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Div(
                Select(
                    Option("No campaign link", value=""),
                    *[Option(f"{row['title']} ({row['campaign_code']})", value=row["campaign_id"]) for row in campaigns],
                    name="campaign_id",
                    cls="form-select",
                ),
                Input(type="date", name="date", value=date.today().isoformat(), cls="form-control", required=True),
                cls="drawer-two-up mb-3",
            ),
            Select(
                Option("General audience", value=""),
                *[Option(_segment_label(name), value=name) for name in AUDIENCE_SEGMENTS],
                name="audience_segment",
                cls="form-select mb-3",
            ),
            P("Use audience segment for retreat reporting. Leave it blank for general services, crusades, and special programs.", cls="small text-muted mb-3"),
            Div(
                Select(
                    Option("Select location", value=""),
                    *[Option(name, value=name) for name in await _scope_locations(request, ctx)],
                    name="location",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Select status", value=""),
                    *[Option(name.title(), value=name) for name in EVENT_STATUSES],
                    name="status",
                    cls="form-select",
                    required=True,
                ),
                cls="drawer-two-up mb-3",
            ),
            Input(type="text", name="created_by", value=ctx.profile.user_name, cls="form-control mb-3", readonly=True),
            Button("Save event", variant="success", size="md", type="submit", cls="w-100"),
            hx_post=ctx.url_for("/church-data/programs/events/create"),
            hx_target="#form-drawer-body",
            hx_swap="innerHTML",
        )

    @app.post("/church-data/programs/events/create")
    async def create_event(request: Request):
        form = await request.form()
        data = {key: str(value) for key, value in form.items()}
        ctx = build_context(data)
        selected_location = next(
            (
                row
                for row in await PeopleService.list_locations(request, ctx)
                if (row.get("location_name") or row.get("location_id")) == data.get("location")
            ),
            None,
        )
        payload = {**data, "path": str(selected_location.get("path") or "") if selected_location else ""}
        row = await ProgramService.create_event(request, payload) if await ProgramService.live_enabled(request) else None
        if row is None:
            return P("Could not save this event right now.", cls="text-muted")
        return simple_toast_response(
            content=(
                Div(H3("Event saved", cls="h5 fw-semibold"), P(f"{row['title']} has been added for {row['location']}.", cls="mb-0")),
                await _events_table(request, ctx, oob=True),
            ),
            message="Program event saved.",
            variant="success",
        )

    @app.get("/church-data/programs/events/{event_id}/drawer")
    async def event_drawer(request: Request, event_id: str):
        ctx = build_context(request)
        row = await ProgramService.get_event(request, ctx, event_id)
        if row is None:
            return P("Program event not found.", cls="text-muted")
        return Div(
            H3(row["title"], cls="h5 fw-semibold"),
            P(f"{row['program_type']} - {row['domain_name']}", cls="text-muted"),
            Div(
                Div(P("Status", cls="small text-muted mb-1"), status_badge(row["status"])),
                Div(P("Date", cls="small text-muted mb-1"), P(row["date"], cls="fw-semibold mb-0")),
                Div(P("Location", cls="small text-muted mb-1"), P(row["location"], cls="fw-semibold mb-0")),
                Div(P("Audience", cls="small text-muted mb-1"), P(_segment_label(str(row.get("audience_segment") or "")), cls="fw-semibold mb-0")),
                Div(P("Campaign", cls="small text-muted mb-1"), P(row["campaign_title"] or row["campaign_code"] or "Not linked", cls="fw-semibold mb-0")),
                Div(P("Created by", cls="small text-muted mb-1"), P(row["created_by"], cls="fw-semibold mb-0")),
                cls="drawer-meta-grid",
            ),
            _assignments_section(request, ctx, event_id),
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
        workers = [
            row
            for row in await PeopleService.list_workers(request, ctx)
            if row.get("status") == "active" and row.get("approval_status") in {"approved", ""}
        ]
        return Form(
            *hidden_context_inputs(ctx),
            H3("Assign officiating worker", cls="h5 fw-semibold"),
            P(f"Prepare approved workers for {event['title']}. Alpha-ground count and convert capture will use these assignments.", cls="text-muted"),
            Select(
                Option("Select worker", value=""),
                *[
                    Option(
                        f"{row['name']} ({row.get('public_code') or row['worker_id']})",
                        value=row["worker_id"],
                    )
                    for row in workers
                ],
                name="worker_id",
                cls="form-select mb-3",
                required=True,
            ),
            Input(type="text", name="assignment_label", placeholder="Block, zone, desk, or seat section", cls="form-control mb-3"),
            Div(
                Select(
                    Option("Assignment type", value="both"),
                    *[Option(name.title(), value=name) for name in ASSIGNMENT_TYPES],
                    name="assignment_type",
                    cls="form-select",
                    required=True,
                ),
                Select(
                    Option("Source role", value="alpha"),
                    *[Option(name.title(), value=name) for name in ASSIGNMENT_SOURCE_ROLES],
                    name="source_role",
                    cls="form-select",
                    required=True,
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
        row = await ProgramService.create_assignment(request, ctx, event_id, data) if await ProgramService.live_enabled(request) else None
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
        updated = await ProgramService.approve_assignment(request, ctx, assignment_id) if await ProgramService.live_enabled(request) else None
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
        updated = await ProgramService.reject_assignment(request, ctx, assignment_id, note=note) if await ProgramService.live_enabled(request) else None
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
