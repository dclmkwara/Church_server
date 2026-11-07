"""Opt-in request-correlated performance tracing for the admin dashboard."""
from __future__ import annotations

import contextvars
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("dclm.dashboard.performance")


@dataclass
class DashboardTrace:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started: float = field(default_factory=time.perf_counter)
    backend_calls: list[dict[str, Any]] = field(default_factory=list)
    database_queries: list[dict[str, Any]] = field(default_factory=list)
    phases: list[dict[str, Any]] = field(default_factory=list)


_active_trace: contextvars.ContextVar[DashboardTrace | None] = contextvars.ContextVar(
    "dclm_dashboard_trace", default=None
)


def enabled() -> bool:
    return os.getenv("DCLM_DASHBOARD_PERF", "0").strip().lower() in {"1", "true", "yes", "on"}


def start_trace() -> tuple[DashboardTrace | None, contextvars.Token | None]:
    if not enabled():
        return None, None
    trace = DashboardTrace()
    return trace, _active_trace.set(trace)


def current_trace() -> DashboardTrace | None:
    return _active_trace.get()


def begin_correlated_api_trace(request_id: str) -> tuple[DashboardTrace | None, contextvars.Token | None]:
    if not enabled() or current_trace() is not None:
        return None, None
    trace = DashboardTrace(request_id=request_id)
    return trace, _active_trace.set(trace)


def finish_trace(trace: DashboardTrace | None, token: contextvars.Token | None, *, render_ms: float, request=None) -> None:
    if trace is None:
        return
    _active_trace.reset(token)
    if request is not None:
        request.state._dashboard_perf_trace = trace
        request.state._dashboard_perf_render_ms = render_ms
    logger.info(
        "dashboard_perf request_id=%s render_ms=%.1f phases=%s backend_calls=%s db_query_count=%d db_total_ms=%.1f db_queries=%s",
        trace.request_id,
        render_ms,
        trace.phases,
        trace.backend_calls,
        len(trace.database_queries),
        sum(row["elapsed_ms"] for row in trace.database_queries),
        trace.database_queries,
    )


def record_backend_call(name: str, elapsed_ms: float, status_code: int | None = None) -> None:
    trace = current_trace()
    if trace is not None:
        trace.backend_calls.append({"call": name, "elapsed_ms": round(elapsed_ms, 1), "status": status_code})


def record_database_query(statement: str, elapsed_ms: float) -> None:
    trace = current_trace()
    if trace is not None:
        normalized = " ".join(statement.split())
        trace.database_queries.append({"sql": normalized[:180], "elapsed_ms": round(elapsed_ms, 1)})


def timed_phase(trace: DashboardTrace | None, name: str, started: float) -> None:
    if trace is not None:
        trace.phases.append({"phase": name, "elapsed_ms": round((time.perf_counter() - started) * 1000, 1)})


async def measure_dashboard_response(request, call_next):
    """Measure through HTML serialization and attach Server-Timing diagnostics."""
    started = time.perf_counter()
    response = await call_next(request)
    trace = getattr(request.state, "_dashboard_perf_trace", None)
    if trace is not None:
        total_ms = (time.perf_counter() - started) * 1000
        render_ms = float(getattr(request.state, "_dashboard_perf_render_ms", 0.0))
        serialization_ms = max(total_ms - render_ms, 0.0)
        response.headers["Server-Timing"] = (
            f"dashboard;dur={total_ms:.1f}, render;dur={render_ms:.1f}, serialize;dur={serialization_ms:.1f}"
        )
        logger.info(
            "dashboard_response request_id=%s total_server_ms=%.1f render_ms=%.1f serialization_and_response_ms=%.1f",
            trace.request_id, total_ms, render_ms, serialization_ms,
        )
    return response
