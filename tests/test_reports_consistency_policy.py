from types import SimpleNamespace
from urllib.parse import urlencode

from fasthtml.common import to_xml

from app.frontend.dclm_admin.communication.count_aggregation import report_count_occurrences
from app.frontend.dclm_admin.routes.reports import _dedicated_report_link
from app.services.analytics.reporting_policy import (
    counted_statuses,
    is_counted_status,
    is_pending_status,
)


def test_shared_counting_policy_is_approved_by_default_and_pending_is_opt_in():
    assert counted_statuses() == ("approved",)
    assert counted_statuses(include_pending=True) == ("approved", "pending", "corrected")
    assert is_counted_status("approved")
    assert not is_counted_status("pending")
    assert is_counted_status("pending", include_pending=True)
    assert is_counted_status("corrected", include_pending=True)
    assert not is_counted_status("rejected", include_pending=True)
    assert not is_counted_status("returned", include_pending=True)
    assert is_pending_status("corrected")


def test_reports_summary_keeps_legacy_occurrences_separate_and_sums_only_count_group_parts():
    records = [
        {"count_id": "legacy-a", "date": "2026-11-08", "location": "ILE.001", "event_title": "Sunday Worship", "total": 30, "adult_male": 10, "status": "approved"},
        {"count_id": "legacy-b", "date": "2026-11-08", "location": "ILE.001", "event_title": "Sunday Worship", "total": 12, "adult_male": 4, "status": "approved"},
        {"count_id": "part-a", "count_group_id": "group-1", "date": "2026-11-08", "location": "ILE.001", "event_title": "Sunday Worship", "total": 5, "adult_male": 2, "status": "approved", "service_id": "main"},
        {"count_id": "part-b", "count_group_id": "group-1", "date": "2026-11-08", "location": "ILE.001", "event_title": "Sunday Worship", "total": 7, "adult_male": 3, "status": "approved", "service_id": "main"},
        {"count_id": "pending", "date": "2026-11-08", "location": "ILE.001", "event_title": "Sunday Worship", "total": 90, "status": "pending"},
        {"count_id": "rejected", "date": "2026-11-08", "location": "ILE.001", "event_title": "Sunday Worship", "total": 100, "status": "rejected"},
    ]

    approved = report_count_occurrences(records)
    with_pending = report_count_occurrences(records, include_pending=True)

    assert sorted(row["total"] for row in approved) == [12, 12, 30]
    assert sorted(row["total"] for row in with_pending) == [12, 12, 30, 90]
    assert next(row for row in approved if row.get("count_group_id") == "group-1")["adult_male"] == 5


def test_reports_dedicated_links_keep_scope_period_and_pending_filter():
    ctx = SimpleNamespace(
        current_scope_path="dcl.234.kw.ilr.ile.001",
        query_extras={"period": "4w", "include_pending": "false"},
        url_for=lambda path, **kwargs: path + ("?" + urlencode(kwargs) if kwargs else ""),
    )
    rendered = to_xml(_dedicated_report_link(
        ctx, "Finance", "Approved entries.", "/church-data/finance", "Open Finance Analytics", "Details are on the finance page.",
    ))

    assert "href=\"/church-data/finance?scope_path=dcl.234.kw.ilr.ile.001&amp;period=4w&amp;include_pending=false\"" in rendered
    assert "Approved entries." in rendered
