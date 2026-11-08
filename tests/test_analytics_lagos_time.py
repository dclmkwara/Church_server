from datetime import datetime, timezone

from app.frontend.dclm_admin.routes.analytics_dashboard import _lagos_sunday
from app.services.analytics.program_config import reporting_today


def test_reporting_date_and_sunday_roll_over_at_lagos_midnight():
    before_midnight = datetime(2026, 11, 7, 22, 59, tzinfo=timezone.utc)
    at_midnight = datetime(2026, 11, 7, 23, 0, tzinfo=timezone.utc)

    assert reporting_today(before_midnight).isoformat() == "2026-11-07"
    assert _lagos_sunday(now=before_midnight).isoformat() == "2026-11-01"
    assert reporting_today(at_midnight).isoformat() == "2026-11-08"
    assert _lagos_sunday(now=at_midnight).isoformat() == "2026-11-08"
