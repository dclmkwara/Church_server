"""Helpers for race-safe client submission identifiers."""

from collections.abc import Awaitable, Callable
from typing import TypeVar
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def commit_idempotent(
    db: AsyncSession,
    obj: T,
    *,
    client_id: UUID | None,
    lookup: Callable[[AsyncSession, UUID], Awaitable[T | None]],
) -> T:
    """Commit a record, recovering the canonical row after a concurrent retry.

    A partial unique index on each resource's client_id is the concurrency
    authority. The in-memory marker is used only to report an accurate sync
    result and is not persisted.
    """
    try:
        await db.commit()
        await db.refresh(obj)
        setattr(obj, "_was_duplicate_submission", False)
        return obj
    except IntegrityError as exc:
        await db.rollback()
        if client_id is None:
            raise
        table_name = getattr(getattr(obj, "__table__", None), "name", "")
        expected_constraint = f"uq_{table_name}_client_id" if table_name else None
        original = getattr(exc, "orig", None)
        actual_constraint = getattr(getattr(original, "diag", None), "constraint_name", None)
        actual_constraint = actual_constraint or getattr(original, "constraint_name", None)
        # asyncpg exposes the violated index through the original DBAPI error.
        # Re-raise unrelated integrity failures instead of misreporting them as
        # a successful retry merely because this ID happens to exist.
        if expected_constraint and actual_constraint != expected_constraint:
            raise
        existing = await lookup(db, client_id)
        if existing is None:
            raise
        setattr(existing, "_was_duplicate_submission", True)
        return existing


def mark_existing_submission(obj: T) -> T:
    """Mark a row returned by the fast pre-insert lookup as a duplicate."""
    setattr(obj, "_was_duplicate_submission", True)
    return obj
