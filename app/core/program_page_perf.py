"""Opt-in timing for Retreat, Crusade, and other program analytics pages."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import logging
import os
from time import perf_counter
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ProgramPageTrace:
    request_id: str
    page: str
    scope_path: str
    started: float = field(default_factory=perf_counter)
    db_ms: float = 0.0
    sql_statements: int = 0
    backend_calls: list[tuple[str, float, int | None, int, float]] = field(default_factory=list)


_trace: ContextVar[ProgramPageTrace | None] = ContextVar("program_page_perf_trace", default=None)


def current_trace() -> ProgramPageTrace | None:
    return _trace.get()


def record_database_query(elapsed_ms: float) -> None:
    trace = current_trace()
    if trace is not None:
        trace.sql_statements += 1
        trace.db_ms += elapsed_ms


def record_backend_call(name: str, elapsed_ms: float, status_code: int | None, sql_statements: int = 0, db_ms: float = 0.0) -> None:
    trace = current_trace()
    if trace is not None:
        trace.backend_calls.append((name, elapsed_ms, status_code, sql_statements, db_ms))


@contextmanager
def program_page_trace(page: str, scope_path: str):
    if os.getenv("DCLM_ANALYTICS_PERF", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        yield None
        return
    trace = ProgramPageTrace(uuid4().hex[:12], page, scope_path)
    token = _trace.set(trace)
    try:
        yield trace
    finally:
        elapsed_ms = (perf_counter() - trace.started) * 1000
        # The route currently awaits backend reads serially. Thus each SQL
        # statement is on the measured critical path; no query text is logged.
        logger.info(
            "program_page_perf request_id=%s page=%s scope=%s elapsed_ms=%.1f db_ms=%.1f sql_statements=%d sequential_depth=%d backend_calls=%s",
            trace.request_id, trace.page, trace.scope_path, elapsed_ms, trace.db_ms,
            trace.sql_statements, trace.sql_statements,
            [(name, round(ms, 1), status, statements, round(db_ms, 1)) for name, ms, status, statements, db_ms in trace.backend_calls],
        )
        _trace.reset(token)
