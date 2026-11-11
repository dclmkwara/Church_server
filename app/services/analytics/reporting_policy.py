"""Shared inclusion rules for reviewable church submissions.

The policy intentionally keeps the current behavior: approved rows count by
default; pending rows count only when explicitly requested; rejected and
returned rows never count. Models without a review status use their own
documented semantics and must not be passed through this policy.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.sql.elements import ColumnElement


APPROVED_STATUS = "approved"
PENDING_STATUS = "pending"
CORRECTED_STATUS = "corrected"
REJECTED_STATUSES = frozenset({"rejected", "returned"})


def counted_statuses(include_pending: bool = False) -> tuple[str, ...]:
    """Statuses included in totals under the current church review model."""
    return (APPROVED_STATUS, PENDING_STATUS, CORRECTED_STATUS) if include_pending else (APPROVED_STATUS,)


def is_counted_status(status: Any, include_pending: bool = False) -> bool:
    """Return whether a stored review status contributes to a reported total."""
    return str(status or "").strip().lower() in counted_statuses(include_pending)


def is_pending_status(status: Any) -> bool:
    """Statuses that represent a submitted report awaiting acceptance."""
    return str(status or "").strip().lower() in {PENDING_STATUS, CORRECTED_STATUS}


def is_rejected_status(status: Any) -> bool:
    """Statuses that are never counted as an accepted report."""
    return str(status or "").strip().lower() in REJECTED_STATUSES


def counted_status_clause(column_sql: str, include_pending: bool = False) -> str:
    """SQL fragment for trusted, code-owned column expressions in text queries."""
    # Status values are constants owned by this module, never caller input.
    values = ", ".join(f"'{status}'" for status in counted_statuses(include_pending))
    return f"{column_sql} IN ({values})"


def counted_status_filter(column: ColumnElement, include_pending: bool = False):
    """SQLAlchemy expression applying the shared status policy."""
    return column.in_(counted_statuses(include_pending))
