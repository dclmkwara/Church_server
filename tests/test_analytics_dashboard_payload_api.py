import asyncio
from datetime import date
from types import SimpleNamespace

from app.api.v1.routes import dashboard


def test_initial_dashboard_payload_combines_summary_and_series(monkeypatch):
    calls = []

    async def fake_series(db, scope, *, occurrence_dates, include_pending):
        calls.append(("series", scope, len(occurrence_dates), include_pending))
        return {"scope": [{"total": 14}]}

    async def fake_summary(db, scope, **kwargs):
        calls.append(("summary", scope))
        return {
            "workers_total": 4, "active_workers": 3,
            "pending_workers": 1, "suspended_workers": 0,
            "attendance_summary": {"expected": 2, "present": 1},
        }

    monkeypatch.setattr(dashboard, "_effective_scope", lambda user, requested: "dclm.234.kw")
    monkeypatch.setattr(dashboard.SundayWorshipAnalytics, "series", fake_series)
    monkeypatch.setattr(dashboard.DashboardService, "get_summary", fake_summary)
    user = SimpleNamespace(path="dclm.234.kw", roles=[])
    result = asyncio.run(dashboard.get_sunday_worship_dashboard_payload(
        scope_path=None, weeks=4, latest_date=date(2026, 11, 1), include_pending=False,
        db=object(), current_user=user,
    ))

    assert [call[0] for call in calls] == ["series", "summary"]
    assert result["series"]["scope"][0]["total"] == 14
    assert result["bootstrap"]["worker_analytics"]["active"] == 3
    assert result["bootstrap"]["attendance_summary"] == {"expected": 2, "present": 1}


def test_dashboard_payload_passes_selected_reporting_window_into_summary(monkeypatch):
    seen = {}

    async def fake_series(db, scope, *, occurrence_dates, include_pending):
        return {"scope": []}

    async def fake_summary(db, scope, **kwargs):
        seen.update(kwargs)
        return {"workers_total": 0, "active_workers": 0, "pending_workers": 0, "suspended_workers": 0}

    monkeypatch.setattr(dashboard, "_effective_scope", lambda user, requested: "dclm.234.kw")
    monkeypatch.setattr(dashboard.SundayWorshipAnalytics, "series", fake_series)
    monkeypatch.setattr(dashboard.DashboardService, "get_summary", fake_summary)
    user = SimpleNamespace(path="dclm.234.kw", roles=[])
    asyncio.run(dashboard.get_sunday_worship_dashboard_payload(
        scope_path=None, weeks=8, latest_date=date(2026, 11, 1), include_pending=False,
        db=object(), current_user=user,
    ))
    assert seen == {"weeks": 8, "latest_date": date(2026, 11, 1)}


def test_deferred_dashboard_panels_do_not_query_review_queue_without_permission(monkeypatch):
    async def fake_series(db, scope, *, occurrence_dates, include_pending):
        return {"scope": []}

    async def unexpected_review(**kwargs):
        raise AssertionError("a user without review permission must not load the review queue")

    monkeypatch.setattr(dashboard, "_effective_scope", lambda user, requested: "dclm.234.kw")
    monkeypatch.setattr(dashboard.SundayWorshipAnalytics, "series", fake_series)
    from app.api.v1.routes import counts
    monkeypatch.setattr(counts, "list_count_review_groups", unexpected_review)
    user = SimpleNamespace(path="dclm.234.kw", roles=[])
    result = asyncio.run(dashboard.get_sunday_worship_dashboard_panels(
        scope_path=None, weeks=4, latest_date=date(2026, 11, 1), include_pending=False,
        db=object(), current_user=user,
    ))
    assert result == {"series": {"scope": []}, "can_review": False, "review_groups": []}


def test_deferred_dashboard_panels_include_review_queue_for_authorized_role(monkeypatch):
    async def fake_series(db, scope, *, occurrence_dates, include_pending):
        return {"scope": []}

    async def fake_review(**kwargs):
        return [{"count_id": "pending-1"}]

    monkeypatch.setattr(dashboard, "_effective_scope", lambda user, requested: "dclm.234.kw")
    monkeypatch.setattr(dashboard.SundayWorshipAnalytics, "series", fake_series)
    from app.api.v1.routes import counts
    monkeypatch.setattr(counts, "list_count_review_groups", fake_review)
    permission = SimpleNamespace(permission="counts:review")
    user = SimpleNamespace(path="dclm.234.kw", roles=[SimpleNamespace(permissions=[permission])])
    result = asyncio.run(dashboard.get_sunday_worship_dashboard_panels(
        scope_path=None, weeks=4, latest_date=date(2026, 11, 1), include_pending=False,
        db=object(), current_user=user,
    ))
    assert result["can_review"] is True
    assert result["review_groups"] == [{"count_id": "pending-1"}]
