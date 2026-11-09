"""Shared validation and clock rules for split count groups."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.services.analytics.program_config import MISSING_HOURS_AFTER_OCCURRENCE

_LAGOS = ZoneInfo("Africa/Lagos")


def require_count_mode(established: str | None, requested: str) -> None:
    if established and requested != established:
        raise HTTPException(
            status_code=409,
            detail="This service is already using a different count mode. Use the same mode or ask the pastor to resolve the group.",
        )


def missing_suggested_labels(suggestions: list[dict], reported_labels: set[str]) -> list[str]:
    return [
        item["label"] for item in suggestions
        if not item.get("hidden") and str(item.get("label") or "").strip().casefold() not in reported_labels
    ]


def require_section_label_available(existing_labels: list[str], requested_label: str) -> None:
    key = requested_label.strip().casefold()
    if any(str(label or "").strip().casefold() == key for label in existing_labels):
        raise HTTPException(409, "That label has already been reported in this count. Enter a different section label.")


def count_group_deadline(occurrence: date) -> datetime:
    return datetime.combine(occurrence + timedelta(days=1), time.min, _LAGOS) + timedelta(hours=MISSING_HOURS_AFTER_OCCURRENCE)


def count_group_is_past_deadline(occurrence: date, now: datetime) -> bool:
    localized_now = now.astimezone(_LAGOS) if now.tzinfo else now.replace(tzinfo=_LAGOS)
    return localized_now >= count_group_deadline(occurrence)
