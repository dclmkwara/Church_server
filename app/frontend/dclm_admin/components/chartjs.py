from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from fasthtml.common import Canvas, Div, P

from .ui import empty_state


CHART_MUTED = "#64748b"
CHART_LABEL = "#475569"


def _chart_host(
    config: dict[str, Any],
    *,
    height: int = 220,
    cls: str = "report-chart-shell dashboard-chart-shell",
    center_value: str = "",
    center_label: str = "",
) -> Any:
    chart_id = f"chartjs-{uuid4().hex[:10]}"
    overlay = ""
    if center_value or center_label:
        overlay = Div(
            P(center_value, cls="chartjs-center-value"),
            P(center_label, cls="chartjs-center-label"),
            cls="chartjs-center-copy",
        )
    return Div(
        Canvas(id=chart_id, cls="chartjs-canvas", aria_label=str(config.get("data", {}).get("datasets", [{}])[0].get("label") or "Chart")),
        overlay,
        cls=f"chartjs-shell {cls}",
        style=f"--chart-height:{height}px;",
        **{"data-chartjs-config": json.dumps(config, separators=(",", ":"))},
    )


def sparkline_chart(
    points: list[tuple[str, int]],
    *,
    stroke: str,
    fill: str,
    label: str = "Trend",
    cls: str = "report-chart-shell dashboard-chart-shell",
) -> Any:
    if not points:
        return empty_state("graph-up", "No chart data", "No trend records are available.")
    labels = [str(label_value) for label_value, _value in points]
    values = [int(value) for _label_value, value in points]
    config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": label,
                    "data": values,
                    "borderColor": stroke,
                    "backgroundColor": fill,
                    "fill": True,
                    "tension": 0.35,
                    "borderWidth": 3,
                    "pointRadius": 2 if len(values) <= 10 else 0,
                    "pointHoverRadius": 4,
                    "pointBackgroundColor": stroke,
                    "pointBorderWidth": 0,
                }
            ],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "interaction": {"intersect": False, "mode": "index"},
            "plugins": {
                "legend": {"display": False},
                "tooltip": {"displayColors": False},
            },
            "scales": {
                "x": {
                    "grid": {"display": False},
                    "border": {"display": False},
                    "ticks": {"color": CHART_MUTED, "maxRotation": 0, "autoSkip": True, "maxTicksLimit": 6},
                },
                "y": {
                    "display": False,
                    "grid": {"display": False},
                    "border": {"display": False},
                },
            },
        },
    }
    return _chart_host(config, height=220, cls=cls)


def donut_chart(
    items: list[dict[str, Any]],
    *,
    label: str,
    total_label: str,
    cls: str = "report-chart-shell dashboard-chart-shell",
) -> Any:
    rows = [row for row in items if float(row.get("value") or 0) > 0]
    if not rows:
        return empty_state("pie-chart", "No ratio available", "No matching records are available.")
    labels = [str(row["label"]) for row in rows]
    values = [float(row.get("value") or 0) for row in rows]
    colors = [str(row.get("color") or "#1d4ed8") for row in rows]
    total = int(round(sum(values)))
    config = {
        "type": "doughnut",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": label,
                    "data": values,
                    "backgroundColor": colors,
                    "borderWidth": 0,
                    "hoverOffset": 6,
                }
            ],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "cutout": "68%",
            "plugins": {
                "legend": {"display": False},
                "tooltip": {"displayColors": False},
            },
        },
    }
    return _chart_host(config, height=220, cls=cls, center_value=str(total), center_label=total_label)


def bar_chart(
    rows: list[dict[str, Any]],
    *,
    label: str,
    cls: str = "report-chart-shell dashboard-chart-shell",
) -> Any:
    active_rows = [row for row in rows if float(row.get("value") or 0) > 0]
    if not active_rows:
        return empty_state("bar-chart-line", "No comparison", "No matching records are available.")
    labels = [str(row["label"]) for row in active_rows]
    values = [float(row.get("value") or 0) for row in active_rows]
    colors = [str(row.get("color") or "#1d4ed8") for row in active_rows]
    height = min(max(220, 84 + (len(active_rows) * 42)), 480)
    config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": label,
                    "data": values,
                    "backgroundColor": colors,
                    "borderRadius": 999,
                    "borderSkipped": False,
                    "barThickness": 18,
                }
            ],
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": False,
            "indexAxis": "y",
            "plugins": {
                "legend": {"display": False},
                "tooltip": {"displayColors": False},
            },
            "scales": {
                "x": {
                    "beginAtZero": True,
                    "grid": {"color": "rgba(148, 163, 184, 0.16)"},
                    "border": {"display": False},
                    "ticks": {"color": CHART_MUTED, "precision": 0},
                },
                "y": {
                    "grid": {"display": False},
                    "border": {"display": False},
                    "ticks": {"color": CHART_LABEL},
                },
            },
        },
    }
    return _chart_host(config, height=height, cls=cls)
