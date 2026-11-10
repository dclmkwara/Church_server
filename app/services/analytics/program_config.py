"""Central code-level definitions for church standing programs and thresholds."""

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo


# Shared dashboard attention policy. Values compare pooled totals for the same
# locations counted in both adjacent reporting periods.
ATTENTION_DECLINE_PCT = 15
ATTENTION_MIN_COMPARABLE_LOCATIONS = 5
SUBMISSION_EDIT_WINDOW_HOURS = 24
SUBMISSION_MAX_EDITS = 3
SUBMISSION_RETURN_EXTRA_EDITS = 1


@dataclass(frozen=True)
class StandingProgram:
    """Describe one recurring program without creating database expectations."""

    key: str
    label: str
    weekday: int | None
    expected_unit: str | None
    program_type_slug: str | None


# Python weekday values follow datetime.date.weekday(): Monday is zero.
STANDING_PROGRAMS = {
    "sunday_worship_service": StandingProgram(
        "sunday_worship_service", "Sunday Worship", 6, "location", "sunday_worship_service"
    ),
    "house_caring_fellowship": StandingProgram(
        "house_caring_fellowship", "House Caring Fellowship", 6, "fellowship", None
    ),
    "monday_bible_study": StandingProgram(
        "monday_bible_study", "Monday Bible Study", 0, "location", "monday_bible_study"
    ),
    "tuesday_leaders_meeting": StandingProgram(
        "tuesday_leaders_meeting", "Tuesday Leaders Meeting", 1, None, "tuesday_leaders_meeting"
    ),
    "thursday_revival_hour": StandingProgram(
        "thursday_revival_hour", "Thursday Revival Hour", 3, "location", "thursday_revival_hour"
    ),
    "saturday_workers_meeting": StandingProgram(
        "saturday_workers_meeting", "Saturday Workers Meeting", 5, "location", "saturday_workers_meeting"
    ),
}


REPORTING_TIMEZONE = "Africa/Lagos"
AWAITING_HOURS_AFTER_OCCURRENCE = 10
MISSING_HOURS_AFTER_OCCURRENCE = 24
PENDING_ACCEPTOR_ALERT_HOURS = 10
PENDING_NEXT_LEVEL_ALERT_HOURS = 24


def reporting_now(now: datetime | None = None) -> datetime:
    """Return an instant normalized to the church reporting timezone."""
    instant = now or datetime.now(ZoneInfo(REPORTING_TIMEZONE))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=ZoneInfo(REPORTING_TIMEZONE))
    return instant.astimezone(ZoneInfo(REPORTING_TIMEZONE))


def reporting_today(now: datetime | None = None) -> date:
    """Return the current church reporting date in Africa/Lagos."""
    return reporting_now(now).date()
