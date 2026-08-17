from __future__ import annotations

import asyncio
from typing import Any

from fasthtml.common import Div, H2, H4, P, Span
from faststrap import Button, PlaceholderCard, Spinner, ToggleGroup
from starlette.requests import Request

from ..auth_context import build_context
from ..communication.dashboard_service import DashboardService
from ..components.chartjs import bar_chart as _bar_chart
from ..components.chartjs import donut_chart as _donut_chart
from ..components.chartjs import sparkline_chart as _sparkline
from ..components.shell import primary_button, shell_layout
from ..components.ui import activity_feed, empty_state, page_stack, quick_actions, section_card, stat_card

PANEL_COPY = {
    "congregation": (
        "Member overview",
        "Directory totals and member mix.",
    ),
    "population": (
        "Attendance mix",
        "Recent count records grouped by gender and age band.",
    ),
    "workers": (
        "Workers and attendance",
        "Worker strength, approvals, and attendance posture.",
    ),
    "newcomers": (
        "Newcomers and converts",
        "Follow-up activity and recent conversion movement.",
    ),
    "programs": (
        "Programs and turnout",
        "Program turnout leaders and special-program movement.",
    ),
    "meetings": (
        "Worker meetings",
        "Attendance strength across key worker meetings.",
    ),
    "governance": (
        "Reporting summary",
        "Coverage and account activity.",
    ),
}

PROFILE_SECTIONS = {
    "local": {
        "autoload": ("congregation", "workers"),
        "deferred": ("newcomers", "programs", "meetings"),
    },
    "state": {
        "autoload": ("governance", "workers"),
        "deferred": ("population", "programs", "newcomers"),
    },
    "governance": {
        "autoload": ("governance",),
        "deferred": ("workers", "population", "programs", "congregation"),
    },
}

SECTION_BOOTSTRAP_KEYS = {
    "congregation": ("summary", "member_analytics"),
    "population": ("summary", "population_statistics"),
    "workers": ("worker_analytics", "attendance_summary"),
    "newcomers": ("newcomer_analytics",),
    "programs": ("program_comparison",),
    "meetings": ("worker_meeting_comparison",),
    "governance": ("summary", "church_statistics", "user_statistics"),
}


def _bootstrap_keys_for_profile(profile: str) -> tuple[str, ...]:
    keys = ["summary"]
    for section_key in PROFILE_SECTIONS[profile]["autoload"]:
        keys.extend(SECTION_BOOTSTRAP_KEYS.get(section_key, ()))
    return tuple(dict.fromkeys(keys))

def _dashboard_intro() -> Any:
    return Div(
        H2("DCLM Admin Dashboard", cls="display-6 fw-semibold text-dark mb-0 dashboard-hero__title"),
        P("Attendance, workers, and decisions — scoped to your level.", cls="dashboard-hero__subtitle text-muted mb-0"),
        id="dashboard-intro",
        cls="dashboard-hero",
    )

CHART_PALETTE = {
    "primary": "#1d4ed8",
    "primary_soft": "#bfdbfe",
    "navy": "#0f2d5e",
    "success": "#059669",
    "success_soft": "#a7f3d0",
    "warning": "#d97706",
    "warning_soft": "#fde68a",
    "danger": "#dc2626",
    "danger_soft": "#fecdd3",
    "purple": "#7c3aed",
    "purple_soft": "#ddd6fe",
    "slate": "#475569",
}


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


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


async def _mix_rows(items: list[tuple[str, str, str]]) -> Any:
    return Div(
        *[
            Div(
                Div(
                    Span(label, cls="fw-semibold text-dark"),
                    Span(value, cls="fw-semibold text-primary"),
                    cls="d-flex justify-content-between align-items-center gap-3",
                ),
                P(note, cls="small text-muted mb-0"),
                cls="py-2 border-top",
            )
            for label, value, note in items
        ],
        cls="d-grid gap-2",
    )


async def _ranking_rows(rows: list[dict[str, Any]], *, empty_title: str, empty_body: str, metric_label: str) -> Any:
    if not rows:
        return empty_state("bar-chart-line", empty_title, empty_body)
    return Div(
        *[
            Div(
                Div(
                    P(row["label"], cls="fw-semibold text-dark mb-1"),
                    P(
                        f"{row.get('records', row.get('present', 0) + row.get('late', 0))} records in this view.",
                        cls="small text-muted mb-0",
                    ),
                ),
                Div(
                    P(str(row.get("total", row.get("present", 0) + row.get("late", 0))), cls="fw-semibold mb-0 text-dark"),
                    P(metric_label, cls="small text-muted mb-0"),
                    cls="text-lg-end",
                ),
                cls="d-flex flex-column flex-lg-row justify-content-between gap-3 breakdown-row",
            )
            for row in rows
        ],
        cls="d-grid gap-3",
    )


async def _scope_snapshot(rows: list[dict[str, Any]]) -> Any:
    if not rows:
        return empty_state("diagram-3", "No comparisons", "No breakdown records are available.")
    return Div(
        *[
            Div(
                Div(
                    Div(
                        P(row["label"], cls="fw-semibold text-dark mb-1"),
                        P(row.get("display_id") or "Scope ID unavailable.", cls="small text-muted mb-1"),
                        P(f"{row['counts']} attendance total", cls="small text-muted mb-0"),
                    ),
                    Div(
                        P(str(row["total"]), cls="fw-semibold mb-0 text-dark"),
                        P("Total", cls="small text-muted mb-0"),
                        cls="text-lg-end",
                    ),
                    cls="d-flex flex-column flex-lg-row justify-content-between gap-3",
                ),
                cls="breakdown-row",
            )
            for row in rows
        ],
        cls="d-grid gap-3",
    )


async def _chart_legend(items: list[dict[str, Any]]) -> Any:
    return Div(
        *[
            Div(
                Div(
                    Span(cls="chart-legend__swatch", style=f"background:{row['color']};"),
                    Span(str(row["label"]), cls="chart-legend__label"),
                    cls="d-flex align-items-center gap-2",
                ),
                Span(str(row["display"]), cls="chart-legend__value"),
                cls="chart-legend__item",
            )
            for row in items
        ],
        cls="chart-legend",
    )


async def _chart_tile(title: str, chart: Any, legend: Any, note: str) -> Any:
    return Div(
        P(title, cls="analytics-chart-card__title"),
        chart,
        legend,
        P(note, cls="dashboard-view-note"),
        cls="analytics-chart-card",
    )


async def _chart_grid(*cards: Any) -> Any:
    return Div(*cards, cls="analytics-chart-grid")


def _format_percent(value: Any) -> str:
    return f"{_safe_float(value):.1f}%"


def _service_gender_rows(population_mix: dict[str, Any]) -> list[dict[str, Any]]:
    men = _safe_int(population_mix.get("adult_male")) + _safe_int(population_mix.get("youth_male")) + _safe_int(population_mix.get("boys"))
    women = _safe_int(population_mix.get("adult_female")) + _safe_int(population_mix.get("youth_female")) + _safe_int(population_mix.get("girls"))
    total = _safe_int(population_mix.get("total"))
    if men == 0 and women == 0 and total > 0:
        men = round(total * (_safe_float(population_mix.get("percentage_men")) / 100))
        women = max(total - men, 0)
    return [
        {"label": "Men", "value": men, "display": f"{men}", "color": CHART_PALETTE["primary"]},
        {"label": "Women", "value": women, "display": f"{women}", "color": CHART_PALETTE["success"]},
    ]


def _service_age_rows(population_mix: dict[str, Any]) -> list[dict[str, Any]]:
    adults = _safe_int(population_mix.get("adult_male")) + _safe_int(population_mix.get("adult_female"))
    youths = _safe_int(population_mix.get("youth_male")) + _safe_int(population_mix.get("youth_female"))
    children = _safe_int(population_mix.get("boys")) + _safe_int(population_mix.get("girls"))
    total = _safe_int(population_mix.get("total"))
    if adults == 0 and youths == 0 and children == 0 and total > 0:
        adults = round(total * (_safe_float(population_mix.get("percentage_adults")) / 100))
        youths = round(total * (_safe_float(population_mix.get("percentage_youths")) / 100))
        children = max(total - adults - youths, 0)
    return [
        {"label": "Adults", "value": adults, "display": f"{adults}", "color": CHART_PALETTE["navy"]},
        {"label": "Youths", "value": youths, "display": f"{youths}", "color": CHART_PALETTE["warning"]},
        {"label": "Children", "value": children, "display": f"{children}", "color": CHART_PALETTE["purple"]},
    ]


async def _dashboard_snapshot(request: Request, ctx) -> dict[str, Any]:
    """Fetch all dashboard data concurrently — ~14× faster than sequential awaits."""
    (
        summary,
        member_mix,
        population_mix,
        worker_mix,
        newcomer_analytics,
        church_stats,
        user_stats,
        trends,
        top_programs,
        special_programs,
        top_worker_meetings,
        scope_rows,
        recent,
        scope_id,
        attendance_summary,
    ) = await asyncio.gather(
        DashboardService.summary_metrics(request, ctx),
        DashboardService.member_mix(request, ctx),
        DashboardService.population_mix(request, ctx),
        DashboardService.worker_mix(request, ctx),
        DashboardService.newcomer_analytics(request, ctx),
        DashboardService.church_statistics(request, ctx),
        DashboardService.user_statistics(request, ctx),
        DashboardService.trend_series(request, ctx),
        DashboardService.top_programs(request, ctx),
        DashboardService.special_program_summary(request, ctx),
        DashboardService.top_worker_meetings(request, ctx),
        DashboardService.scope_snapshot(request, ctx),
        DashboardService.recent_activity(request, ctx),
        DashboardService.scope_display_id(request, ctx),
        DashboardService.attendance_summary(request, ctx),
    )
    return {
        "summary": summary,
        "member_mix": member_mix,
        "population_mix": population_mix,
        "worker_mix": worker_mix,
        "newcomer_analytics": newcomer_analytics,
        "church_stats": church_stats,
        "user_stats": user_stats,
        "trends": trends,
        "top_programs": top_programs,
        "special_programs": special_programs,
        "top_worker_meetings": top_worker_meetings,
        "scope_rows": scope_rows,
        "recent": recent,
        "scope_id": scope_id,
        "attendance_summary": attendance_summary,
    }


def _dashboard_profile(ctx) -> str:
    if ctx.level <= 5:
        return "local"
    if ctx.level == 6:
        return "state"
    return "governance"


async def _summary_snapshot(request: Request, ctx) -> dict[str, Any]:
    summary = await DashboardService.summary_metrics(request, ctx)
    return {"summary": summary}


async def _section_snapshot(request: Request, ctx, section_key: str) -> dict[str, Any]:
    if section_key == "congregation":
        summary, member_mix = await asyncio.gather(
            DashboardService.summary_metrics(request, ctx),
            DashboardService.member_mix(request, ctx),
        )
        return {"summary": summary, "member_mix": member_mix}
    if section_key == "population":
        summary, population_mix = await asyncio.gather(
            DashboardService.summary_metrics(request, ctx),
            DashboardService.population_mix(request, ctx),
        )
        return {"summary": summary, "population_mix": population_mix}
    if section_key == "workers":
        worker_mix, attendance_summary = await asyncio.gather(
            DashboardService.worker_mix(request, ctx),
            DashboardService.attendance_summary(request, ctx),
        )
        return {"worker_mix": worker_mix, "attendance_summary": attendance_summary}
    if section_key == "newcomers":
        return {"newcomer_analytics": await DashboardService.newcomer_analytics(request, ctx)}
    if section_key == "programs":
        top_programs, special_programs = await asyncio.gather(
            DashboardService.top_programs(request, ctx),
            DashboardService.special_program_summary(request, ctx),
        )
        return {"top_programs": top_programs, "special_programs": special_programs}
    if section_key == "meetings":
        return {"top_worker_meetings": await DashboardService.top_worker_meetings(request, ctx)}
    if section_key == "governance":
        summary, church_stats, user_stats = await asyncio.gather(
            DashboardService.summary_metrics(request, ctx),
            DashboardService.church_statistics(request, ctx),
            DashboardService.user_statistics(request, ctx),
        )
        return {"summary": summary, "church_stats": church_stats, "user_stats": user_stats}
    raise KeyError(section_key)


async def _congregation_panel(snapshot: dict[str, Any], *, view: str) -> Any:
    summary = snapshot["summary"]
    member_mix = snapshot["member_mix"]
    if view == "summary":
        return _mix_rows(
            [
                ("Total members", str(member_mix["total"]), f"{summary['active_members']} active records."),
                ("Male to female", f"{member_mix['male']} / {member_mix['female']}", f"{member_mix['male_ratio']}% male and {member_mix['female_ratio']}% female."),
                ("Adults to youths to children", f"{member_mix['adults']} / {member_mix['youths']} / {member_mix['children']}", f"{member_mix['adults_ratio']}% adults, {member_mix['youths_ratio']}% youths, {member_mix['children_ratio']}% children."),
            ]
        )

    gender_rows = [
        {"label": "Male", "value": member_mix["male"], "display": f"{member_mix['male']} ({_format_percent(member_mix['male_ratio'])})", "color": CHART_PALETTE["primary"]},
        {"label": "Female", "value": member_mix["female"], "display": f"{member_mix['female']} ({_format_percent(member_mix['female_ratio'])})", "color": CHART_PALETTE["success"]},
    ]
    age_rows = [
        {"label": "Adults", "value": member_mix["adults"], "display": f"{member_mix['adults']} ({_format_percent(member_mix['adults_ratio'])})", "color": CHART_PALETTE["navy"]},
        {"label": "Youths", "value": member_mix["youths"], "display": f"{member_mix['youths']} ({_format_percent(member_mix['youths_ratio'])})", "color": CHART_PALETTE["warning"]},
        {"label": "Children", "value": member_mix["children"], "display": f"{member_mix['children']} ({_format_percent(member_mix['children_ratio'])})", "color": CHART_PALETTE["purple"]},
    ]
    return _chart_grid(
        _chart_tile(
            "Member gender mix",
            _donut_chart(gender_rows, label="Member gender mix", total_label="Members"),
            _chart_legend(gender_rows),
            "Gender balance updates from the member registry.",
        ),
        _chart_tile(
            "Age distribution",
            _bar_chart(age_rows, label="Member age distribution"),
            _chart_legend(age_rows),
            "Adult, youth, and children distribution in the member registry.",
        ),
    )


async def _population_panel(snapshot: dict[str, Any], *, view: str) -> Any:
    summary = snapshot["summary"]
    population_mix = snapshot["population_mix"]
    if view == "summary":
        return _mix_rows(
            [
                ("Latest population total", str(population_mix.get("total") or summary["latest_total"]), "Drawn from recorded count statistics."),
                ("Men to women", f"{population_mix.get('percentage_men', 0)}% / {population_mix.get('percentage_women', 0)}%", "Recorded attendance mix across count records."),
                ("Adults to youths to children", f"{population_mix.get('percentage_adults', 0)}% / {population_mix.get('percentage_youths', 0)}% / {population_mix.get('percentage_children', 0)}%", "Age-group balance in service attendance."),
            ]
        )

    gender_rows = _service_gender_rows(population_mix)
    age_rows = _service_age_rows(population_mix)
    total_label = f"{population_mix.get('total') or summary['latest_total']}"
    return _chart_grid(
        _chart_tile(
            "Service gender mix",
            _donut_chart(gender_rows, label="Service population gender mix", total_label="Attendance"),
            _chart_legend(gender_rows),
            f"The latest population total is {total_label} people across recorded counts.",
        ),
        _chart_tile(
            "Age-group turnout",
            _bar_chart(age_rows, label="Service age-group turnout"),
            _chart_legend(age_rows),
            "Age-group turnout from recorded service counts.",
        ),
    )


async def _workers_panel(snapshot: dict[str, Any], *, view: str) -> Any:
    worker_mix = snapshot["worker_mix"]
    attendance_summary = snapshot["attendance_summary"]
    if view == "summary":
        return _mix_rows(
            [
                ("Total workers", str(worker_mix["total"]), f"{worker_mix['active']} active and {worker_mix['inactive']} not currently active."),
                ("Male to female", f"{worker_mix['male']} / {worker_mix['female']}", f"{worker_mix['male_ratio']}% male and {worker_mix['female_ratio']}% female."),
                ("Attendance health", f"{attendance_summary.get('present', 0)} present / {attendance_summary.get('late', 0)} late", f"{attendance_summary.get('rate', 0)}% attendance rate."),
            ]
        )

    gender_rows = [
        {"label": "Male workers", "value": worker_mix["male"], "display": f"{worker_mix['male']} ({_format_percent(worker_mix['male_ratio'])})", "color": CHART_PALETTE["primary"]},
        {"label": "Female workers", "value": worker_mix["female"], "display": f"{worker_mix['female']} ({_format_percent(worker_mix['female_ratio'])})", "color": CHART_PALETTE["success"]},
    ]
    attendance_rows = [
        {"label": "Present", "value": attendance_summary.get("present", 0), "display": str(attendance_summary.get("present", 0)), "color": CHART_PALETTE["success"]},
        {"label": "Late", "value": attendance_summary.get("late", 0), "display": str(attendance_summary.get("late", 0)), "color": CHART_PALETTE["warning"]},
        {"label": "Absent", "value": attendance_summary.get("absent", 0), "display": str(attendance_summary.get("absent", 0)), "color": CHART_PALETTE["danger"]},
        {"label": "Excused", "value": attendance_summary.get("excused", 0), "display": str(attendance_summary.get("excused", 0)), "color": CHART_PALETTE["purple"]},
    ]
    return _chart_grid(
        _chart_tile(
            "Worker gender mix",
            _donut_chart(gender_rows, label="Worker gender mix", total_label="Workers"),
            _chart_legend(gender_rows),
            f"{worker_mix['male_ratio']}% male, {worker_mix['female_ratio']}% female across {worker_mix['total']} workers.",
        ),
        _chart_tile(
            "Worker meeting posture",
            _bar_chart(attendance_rows, label="Worker attendance posture"),
            _chart_legend(attendance_rows),
            f"Worker attendance rate: {attendance_summary.get('rate', 0)}%.",
        ),
    )


async def _newcomer_trend_chart(rows: list[dict[str, Any]]) -> Any:
    if not rows:
        return empty_state("person-hearts", "No newcomer trend", "No monthly follow-up records are available.")
    chart_rows = []
    for row in rows[-6:]:
        label = str(row.get("period") or "Current")
        total = _safe_int(row.get("newcomers")) + _safe_int(row.get("converts"))
        chart_rows.append(
            {
                "label": label,
                "value": total,
                "display": total,
                "color": CHART_PALETTE["warning"],
            }
        )
    return _bar_chart(chart_rows, label="Newcomer and convert trend")


async def _newcomers_panel(snapshot: dict[str, Any], *, view: str) -> Any:
    newcomer_analytics = snapshot["newcomer_analytics"]
    total = _safe_int(newcomer_analytics.get("newcomers_total")) + _safe_int(newcomer_analytics.get("converts_total"))
    if view == "summary":
        return _mix_rows(
            [
                ("Follow-up records", str(total), "Newcomer and convert records."),
                ("Newcomers to converts", f"{newcomer_analytics.get('newcomers_total', 0)} / {newcomer_analytics.get('converts_total', 0)}", "Confirmed conversion balance."),
                ("Male to female", f"{newcomer_analytics.get('male', 0)} / {newcomer_analytics.get('female', 0)}", "Gender balance for follow-up records."),
            ]
        )

    status_rows = [
        {"label": "Newcomers", "value": newcomer_analytics.get("newcomers_total", 0), "display": newcomer_analytics.get("newcomers_total", 0), "color": CHART_PALETTE["warning"]},
        {"label": "Converts", "value": newcomer_analytics.get("converts_total", 0), "display": newcomer_analytics.get("converts_total", 0), "color": CHART_PALETTE["success"]},
    ]
    gender_rows = [
        {"label": "Male", "value": newcomer_analytics.get("male", 0), "display": newcomer_analytics.get("male", 0), "color": CHART_PALETTE["primary"]},
        {"label": "Female", "value": newcomer_analytics.get("female", 0), "display": newcomer_analytics.get("female", 0), "color": CHART_PALETTE["success"]},
    ]
    return _chart_grid(
        _chart_tile(
            "Follow-up mix",
            _donut_chart(status_rows, label="Newcomer and convert mix", total_label="Records"),
            _chart_legend(status_rows),
            f"{_safe_int(newcomer_analytics.get('newcomers_total'))} newcomers and {_safe_int(newcomer_analytics.get('converts_total'))} converts across {total} follow-up records.",
        ),
        _chart_tile(
            "Gender balance",
            _donut_chart(gender_rows, label="Newcomer gender mix", total_label="People"),
            _chart_legend(gender_rows),
            f"{newcomer_analytics.get('male', 0)} male and {newcomer_analytics.get('female', 0)} female in follow-up records.",
        ),
        _chart_tile(
            "Recent trend",
            _newcomer_trend_chart(newcomer_analytics.get("trend") or []),
            _chart_legend(status_rows),
            "Monthly follow-up movement over the last 6 periods.",
        ),
    )


def _program_rows(top_programs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    palette = [
        CHART_PALETTE["primary"],
        CHART_PALETTE["success"],
        CHART_PALETTE["warning"],
        CHART_PALETTE["purple"],
    ]
    rows = []
    for index, row in enumerate(top_programs):
        total = _safe_int(row.get("total"))
        rows.append(
            {
                "label": str(row.get("label") or "Unknown program"),
                "value": total,
                "display": total,
                "color": palette[index % len(palette)],
            }
        )
    return rows


def _meeting_rows(top_worker_meetings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    palette = [
        CHART_PALETTE["primary"],
        CHART_PALETTE["warning"],
        CHART_PALETTE["success"],
        CHART_PALETTE["purple"],
    ]
    rows = []
    for index, row in enumerate(top_worker_meetings):
        total = _safe_int(row.get("present")) + _safe_int(row.get("late"))
        rows.append(
            {
                "label": str(row.get("label") or "Unknown meeting"),
                "value": total,
                "display": total,
                "color": palette[index % len(palette)],
            }
        )
    return rows


def _normalize_meeting_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        ranking = value.get("ranking")
        if isinstance(ranking, list):
            return [row for row in ranking if isinstance(row, dict)]
    return []


def _special_program_rows(special_programs: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "label": "This month events",
            "value": _safe_int(special_programs.get("month_events")),
            "display": _safe_int(special_programs.get("month_events")),
            "color": CHART_PALETTE["warning"],
        },
        {
            "label": "This year events",
            "value": _safe_int(special_programs.get("year_events")),
            "display": _safe_int(special_programs.get("year_events")),
            "color": CHART_PALETTE["purple"],
        },
        {
            "label": "This month turnout",
            "value": _safe_int(special_programs.get("month_turnout")),
            "display": _safe_int(special_programs.get("month_turnout")),
            "color": CHART_PALETTE["success"],
        },
        {
            "label": "This year turnout",
            "value": _safe_int(special_programs.get("year_turnout")),
            "display": _safe_int(special_programs.get("year_turnout")),
            "color": CHART_PALETTE["primary"],
        },
    ]


async def _programs_panel(snapshot: dict[str, Any], *, view: str) -> Any:
    top_programs = snapshot["top_programs"]
    special_programs = snapshot["special_programs"]
    strongest = top_programs[0] if top_programs else {}
    if view == "summary":
        return _mix_rows(
            [
                (
                    "Strongest program",
                    str(strongest.get("label") or "No program ranking"),
                    f"{_safe_int(strongest.get('total'))} turnout across {_safe_int(strongest.get('records'))} recorded count(s).",
                ),
                (
                    "Special programs this month",
                    str(_safe_int(special_programs.get("month_events"))),
                    f"{_safe_int(special_programs.get('month_turnout'))} turnout recorded this month.",
                ),
                (
                    "Special programs this year",
                    str(_safe_int(special_programs.get("year_events"))),
                    f"{_safe_int(special_programs.get('year_turnout'))} turnout recorded this year.",
                ),
            ]
        )

    program_rows = _program_rows(top_programs)
    special_rows = _special_program_rows(special_programs)
    return _chart_grid(
        _chart_tile(
            "General program ranking",
            _bar_chart(program_rows, label="Program turnout ranking"),
            _chart_legend(program_rows),
            "Programs ranked by turnout.",
        ),
        _chart_tile(
            "Special program pulse",
            _bar_chart(special_rows, label="Special program summary"),
            _chart_legend(special_rows),
            "Monthly and yearly special-program movement.",
        ),
    )


async def _meetings_panel(snapshot: dict[str, Any], *, view: str) -> Any:
    top_worker_meetings = _normalize_meeting_rows(snapshot["top_worker_meetings"])
    strongest = top_worker_meetings[0] if top_worker_meetings else {}
    if view == "summary":
        strongest_total = _safe_int(strongest.get("present")) + _safe_int(strongest.get("late"))
        return _mix_rows(
            [
                (
                    "Strongest worker meeting",
                    str(strongest.get("label") or "No meeting ranking"),
                    f"{strongest_total} attendance across {_safe_int(strongest.get('records'))} recorded row(s).",
                ),
                (
                    "Present to late",
                    f"{_safe_int(strongest.get('present'))} / {_safe_int(strongest.get('late'))}",
                    "Punctuality balance.",
                ),
                (
                    "Absent trend",
                    str(_safe_int(strongest.get("absent"))),
                    "Recorded absences.",
                ),
            ]
        )

    meeting_rows = _meeting_rows(top_worker_meetings)
    return _chart_grid(
        _chart_tile(
            "Worker meeting ranking",
            _bar_chart(meeting_rows, label="Worker meeting ranking"),
            _chart_legend(meeting_rows),
            "Worker meetings ranked by attendance.",
        )
    )


async def _governance_panel(snapshot: dict[str, Any], *, view: str) -> Any:
    summary = snapshot["summary"]
    church_stats = snapshot["church_stats"]
    user_stats = snapshot["user_stats"]
    if view == "summary":
        return _mix_rows(
            [
                ("Locations", str(church_stats.get("total_locations") or summary["locations_reporting"]), "Branches represented in this report."),
                ("Regions", str(church_stats.get("total_regions") or 0), "Useful for wider oversight levels."),
                ("Registered users", str(user_stats.get("registered_user") or 0), f"{user_stats.get('active_user', 0)} active and {user_stats.get('inactive_user', 0)} inactive user accounts."),
            ]
        )

    coverage_rows = [
        {"label": "Locations", "value": church_stats.get("total_locations") or summary["locations_reporting"], "display": str(church_stats.get("total_locations") or summary["locations_reporting"]), "color": CHART_PALETTE["primary"]},
        {"label": "Regions", "value": church_stats.get("total_regions") or 0, "display": str(church_stats.get("total_regions") or 0), "color": CHART_PALETTE["warning"]},
        {"label": "Users", "value": user_stats.get("registered_user") or 0, "display": str(user_stats.get("registered_user") or 0), "color": CHART_PALETTE["purple"]},
    ]
    account_rows = [
        {"label": "Active accounts", "value": user_stats.get("active_user") or 0, "display": str(user_stats.get("active_user") or 0), "color": CHART_PALETTE["success"]},
        {"label": "Inactive accounts", "value": user_stats.get("inactive_user") or 0, "display": str(user_stats.get("inactive_user") or 0), "color": CHART_PALETTE["slate"]},
    ]
    return _chart_grid(
        _chart_tile(
            "Coverage",
            _bar_chart(coverage_rows, label="Reporting coverage"),
            _chart_legend(coverage_rows),
            "This shows the wider structure represented in reporting.",
        ),
        _chart_tile(
            "Account status mix",
            _donut_chart(account_rows, label="Account status mix", total_label="Accounts"),
            _chart_legend(account_rows),
            "This keeps account posture close to the dashboard.",
        ),
    )


async def _section_toggle(ctx, section_key: str, current_view: str) -> Any:
    active_index = 0 if current_view != "summary" else 1
    target = f"#dashboard-section-{section_key}"
    return ToggleGroup(
        Button(
            "Chart",
            variant="outline-primary",
            size="sm",
            hx_get=ctx.url_for(f"/dashboard/sections/{section_key}", view="chart"),
            hx_target=target,
            hx_swap="outerHTML",
            cls="inbox-filter-chip",
        ),
        Button(
            "Summary",
            variant="outline-primary",
            size="sm",
            hx_get=ctx.url_for(f"/dashboard/sections/{section_key}", view="summary"),
            hx_target=target,
            hx_swap="outerHTML",
            cls="inbox-filter-chip",
        ),
        active_index=active_index,
        active_cls="active",
        cls="admin-toggle-group dashboard-view-toggle",
    )


async def _dashboard_section(request: Request, ctx, section_key: str, *, view: str = "chart") -> Any:
    snapshot = await _section_snapshot(request, ctx, section_key)
    return await _render_dashboard_section(ctx, section_key, snapshot, view=view)


async def _render_dashboard_section(ctx, section_key: str, snapshot: dict[str, Any], *, view: str = "chart") -> Any:
    title, subtitle = PANEL_COPY[section_key]
    renderer = {
        "congregation": _congregation_panel,
        "population": _population_panel,
        "workers": _workers_panel,
        "newcomers": _newcomers_panel,
        "programs": _programs_panel,
        "meetings": _meetings_panel,
        "governance": _governance_panel,
    }[section_key]
    return Div(
        section_card(
            title,
            subtitle,
            await renderer(snapshot, view=view),
            action=await _section_toggle(ctx, section_key, view),
            cls="mb-0",
        ),
        id=f"dashboard-section-{section_key}",
        cls="dashboard-section",
    )


async def _autoload_section_snapshot(request: Request, ctx, section_key: str, *, summary: dict[str, Any]) -> dict[str, Any]:
    if section_key == "congregation":
        member_mix = await DashboardService.member_mix(request, ctx)
        return {"summary": summary, "member_mix": member_mix}
    if section_key == "population":
        population_mix = await DashboardService.population_mix(request, ctx)
        return {"summary": summary, "population_mix": population_mix}
    if section_key == "workers":
        worker_mix, attendance_summary = await asyncio.gather(
            DashboardService.worker_mix(request, ctx),
            DashboardService.attendance_summary(request, ctx),
        )
        return {"worker_mix": worker_mix, "attendance_summary": attendance_summary}
    if section_key == "governance":
        church_stats, user_stats = await asyncio.gather(
            DashboardService.church_statistics(request, ctx),
            DashboardService.user_statistics(request, ctx),
        )
        return {"summary": summary, "church_stats": church_stats, "user_stats": user_stats}
    return await _section_snapshot(request, ctx, section_key)


def _dashboard_section_placeholder(ctx, section_key: str, *, delay_ms: int | None = None, autoload: bool = False) -> Any:
    title, subtitle = PANEL_COPY[section_key]
    attrs = {
        "id": f"dashboard-section-{section_key}",
        "cls": "dashboard-section",
    }
    if autoload:
        attrs.update(
            {
                "hx_get": ctx.url_for(f"/dashboard/sections/{section_key}"),
                "hx_trigger": f"load delay:{delay_ms or 0}ms",
                "hx_swap": "outerHTML",
            }
        )
        body = Div(
            Spinner(variant="primary", size="sm", label=f"Loading {title}"),
            P(f"Fetching {title.lower()} data…", cls="text-muted mb-0"),
            cls="d-flex align-items-center gap-3 py-2",
        )
    else:
        body = Div(
            P(f"Load {title.lower()} data when you need it.", cls="text-muted mb-0"),
            Button(
                "Load",
                variant="outline-primary",
                size="sm",
                hx_get=ctx.url_for(f"/dashboard/sections/{section_key}"),
                hx_target=f"#dashboard-section-{section_key}",
                hx_swap="outerHTML",
                cls="dashboard-load-btn",
            ),
            cls="d-grid gap-3 py-2 dashboard-section-teaser",
        )
    return Div(
        section_card(
            title,
            subtitle,
            body,
            cls="mb-0",
        ),
        **attrs,
    )


def _section_grid(ctx, profile: str) -> list[Any]:
    config = PROFILE_SECTIONS[profile]
    sections = list(config["autoload"]) + list(config["deferred"])
    blocks: list[Any] = []
    for index in range(0, len(sections), 2):
        pair = sections[index:index + 2]
        pair_items = [
            _dashboard_section_placeholder(
                ctx,
                section_key,
                delay_ms=240 + ((index + offset) * 180),
                autoload=section_key in config["autoload"],
            )
            for offset, section_key in enumerate(pair)
        ]
        blocks.append(pair_items[0] if len(pair_items) == 1 else Div(*pair_items, cls="dashboard-two-up"))
    return blocks


async def _section_grid_with_priority_content(request: Request, ctx, profile: str, *, summary: dict[str, Any]) -> list[Any]:
    config = PROFILE_SECTIONS[profile]
    ordered_sections = list(config["autoload"]) + list(config["deferred"])
    autoload_snapshots = await asyncio.gather(
        *[
            _autoload_section_snapshot(request, ctx, section_key, summary=summary)
            for section_key in config["autoload"]
        ]
    )
    autoload_map = dict(zip(config["autoload"], autoload_snapshots))

    blocks: list[Any] = []
    for index in range(0, len(ordered_sections), 2):
        pair = ordered_sections[index:index + 2]
        pair_items: list[Any] = []
        for section_key in pair:
            if section_key in autoload_map:
                pair_items.append(await _render_dashboard_section(ctx, section_key, autoload_map[section_key], view="summary"))
            else:
                pair_items.append(_dashboard_section_placeholder(ctx, section_key))
        blocks.append(pair_items[0] if len(pair_items) == 1 else Div(*pair_items, cls="dashboard-two-up"))
    return blocks


async def _dashboard_loading_content(ctx) -> Any:
    return page_stack(
        _dashboard_intro(),
        Div(
            *[
                Div(
                    PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
                )
                for _ in range(4)
            ],
            cls="metrics-grid",
        ),
        Div(
            section_card(
                "One moment",
                "Pulling the latest data for your scope.",
                Div(
                    Spinner(variant="primary", size="md", label="Loading analytics"),
                    P("Loading dashboard analytics…", cls="text-muted mb-0"),
                    cls="d-flex align-items-center gap-3 py-2",
                ),
            ),
            *[
                Div(
                    PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
                    PlaceholderCard(animation="wave", show_image=False, cls="border-0 shadow-sm"),
                    cls="dashboard-two-up",
                )
                for _ in range(3)
            ],
            cls="dashboard-stack",
        ),
        id="dashboard-content",
        hx_get=ctx.url_for("/dashboard/content"),
        hx_trigger="load",
        hx_swap="innerHTML",
    )


async def _dashboard_content(request: Request, ctx) -> Any:
    profile = _dashboard_profile(ctx)
    DashboardService.configure_bootstrap_sections(request, _bootstrap_keys_for_profile(profile))
    summary = (await _summary_snapshot(request, ctx))["summary"]

    if profile == "local":
        metrics = [
            stat_card("Members", str(summary["members_total"]), "People listed in this branch.", "person-vcard", tone="primary"),
            stat_card("Workers", str(summary["workers_total"]), "Workers serving in this branch.", "people", tone="success"),
            stat_card("Newcomers", str(summary["newcomers_total"]), "Recent newcomer and convert records.", "person-hearts", tone="warning"),
            stat_card("Latest count", str(summary["latest_total"]), "Most recent attendance record.", "bar-chart", tone="info"),
        ]
    elif profile == "state":
        metrics = [
            stat_card("Members", str(summary["members_total"]), "People in this oversight level.", "person-vcard", tone="primary"),
            stat_card("Workers", str(summary["workers_total"]), "Workers serving across this level.", "people", tone="success"),
            stat_card("Pending reviews", str(summary["pending_items"]), "Requests waiting for review.", "inbox", tone="warning"),
            stat_card("Reporting branches", str(summary["locations_reporting"]), "Reporting branches.", "geo-alt", tone="info"),
        ]
    else:
        metrics = [
            stat_card("Members", str(summary["members_total"]), "Members in this level.", "person-vcard", tone="primary"),
            stat_card("Workers", str(summary["workers_total"]), "Workers in this level.", "people", tone="success"),
            stat_card("Pending reviews", str(summary["pending_items"]), "Requests and approvals needing direction.", "exclamation-circle", tone="warning"),
            stat_card("Reporting branches", str(summary["locations_reporting"]), "Reporting branches.", "diagram-3", tone="info"),
        ]

    actions = [
        {
            "label": "Inbox",
            "hint": "Review pending items",
            "icon": "inbox",
            "href": ctx.url_for("/inbox"),
        },
        {
            "label": "Register Worker",
            "hint": "Create a worker record",
            "icon": "person-plus",
            "href": "#",
            "attrs": {
                "data_bs_toggle": "offcanvas",
                "data_bs_target": "#form-drawer",
                "hx_get": ctx.url_for("/people/workers/new"),
                "hx_target": "#form-drawer-body",
                "hx_swap": "innerHTML",
            },
        },
        {
            "label": "Submit Count",
            "hint": "Record attendance",
            "icon": "bar-chart",
            "href": "#",
            "attrs": {
                "data_bs_toggle": "offcanvas",
                "data_bs_target": "#form-drawer",
                "hx_get": ctx.url_for("/church-data/counts/new"),
                "hx_target": "#form-drawer-body",
                "hx_swap": "innerHTML",
            },
        },
    ]

    section_blocks = await _section_grid_with_priority_content(request, ctx, profile, summary=summary)

    return page_stack(
        _dashboard_intro(),
        Div(*metrics, cls="metrics-grid"),
        section_card("Quick actions", "Go straight to a common task.", quick_actions(actions)),
        *section_blocks,
    )


def register_dashboard_routes(app) -> None:
    @app.get("/dashboard")
    async def dashboard(request: Request):
        ctx = build_context(request)
        return shell_layout(
            ctx,
            request_path=request.url.path,
            active_key="dashboard",
            title="",
            subtitle="",
            primary_action=primary_button("Inbox", href=ctx.url_for("/inbox")),
            content=_dashboard_loading_content(ctx),
            show_shell_intro=False,
        )

    @app.get("/dashboard/content")
    async def dashboard_content(request: Request):
        ctx = build_context(request)
        return await _dashboard_content(request, ctx)

    @app.get("/dashboard/sections/{section_key}")
    async def dashboard_section(request: Request, section_key: str, view: str = "chart"):
        ctx = build_context(request)
        if section_key not in PANEL_COPY:
            return empty_state("x-circle", "Unknown dashboard section", "This dashboard section is not available.")
        DashboardService.configure_bootstrap_sections(request, SECTION_BOOTSTRAP_KEYS.get(section_key, ("summary",)))
        return await _dashboard_section(request, ctx, section_key, view=view)
