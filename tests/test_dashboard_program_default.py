from datetime import date

from app.frontend.dclm_admin.routes.analytics_dashboard import (
    _DASHBOARD_PROGRAM_WEEKDAYS,
    _latest_standing_program_date,
    _most_recent_standing_program,
)


def test_default_program_tracks_most_recent_standing_schedule_day():
    assert _most_recent_standing_program(date(2026, 11, 8)) == (
        "sunday_worship_service", date(2026, 11, 8)
    )
    assert _most_recent_standing_program(date(2026, 11, 10)) == (
        "monday_bible_study", date(2026, 11, 9)
    )
    assert _most_recent_standing_program(date(2026, 11, 13)) == (
        "thursday_revival_hour", date(2026, 11, 12)
    )


def test_selected_program_date_is_latest_scheduled_occurrence_on_or_before_today():
    assert _latest_standing_program_date("monday_bible_study", date(2026, 11, 11)) == date(2026, 11, 9)
    assert _latest_standing_program_date("thursday_revival_hour", date(2026, 11, 12)) == date(2026, 11, 12)


def test_dashboard_default_candidates_are_weekly_services_only():
    assert set(_DASHBOARD_PROGRAM_WEEKDAYS) == {
        "sunday_worship_service",
        "monday_bible_study",
        "thursday_revival_hour",
    }
