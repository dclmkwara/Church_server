from datetime import date

from app.frontend.dclm_admin.communication.count_aggregation import aggregate_count_submissions, summarize_count_submissions
from app.api.v1.routes.counts import COUNT_APPROVED, COUNT_PENDING, COUNT_REJECTED, _acceptor_score
from app.utils.count_sections import legacy_section_label


def test_legacy_section_prefix_parser_is_isolated_and_does_not_change_plain_notes():
    assert legacy_section_label("Section: Gallery | counted from the west door") == "Gallery"
    assert legacy_section_label("ordinary usher note") == ""
    assert legacy_section_label("Section: Main Hall") == "Main Hall"


def test_count_review_uses_stored_status_values_and_pastor_approval_levels():
    assert {COUNT_PENDING, COUNT_APPROVED, COUNT_REJECTED} == {"pending", "approved", "rejected"}
    assert _acceptor_score("Local") == 3
    assert _acceptor_score("Group") == 4
    assert _acceptor_score("Region") == 5
    assert _acceptor_score("State") is None


def test_population_aggregation_excludes_pending_and_rejected_and_preserves_approved_zero():
    rows = [
        {"count_id": "approved", "date": "2026-11-01", "location_id": "l1", "event_id": "", "program_type": "Sunday Worship", "status": "approved", "total": 0},
        {"count_id": "pending", "date": "2026-11-01", "location_id": "l2", "event_id": "", "program_type": "Sunday Worship", "status": "pending", "total": 90},
        {"count_id": "rejected", "date": "2026-11-01", "location_id": "l3", "event_id": "", "program_type": "Sunday Worship", "status": "rejected", "total": 120},
    ]
    groups = aggregate_count_submissions(rows)
    by_location = {row["location_id"]: row for row in groups}
    assert by_location["l1"]["total"] == 0
    assert by_location["l2"]["total"] is None
    assert by_location["l2"]["pending_total"] == 90
    assert by_location["l3"]["total"] is None
    assert by_location["l3"]["status"] == "rejected"
    summary = summarize_count_submissions(rows, today=date(2026, 11, 7))
    assert summary["latest_total"] == 0
    assert summary["monthly_total"] == 0
    assert summary["locations_reporting"] == 1


def test_program_and_reporting_scope_are_part_of_the_count_group_key():
    rows = [
        {"count_id": "workers", "date": "2026-11-01", "location_id": "l1", "event_id": "", "program_type": "Workers Meeting", "program_level": "Local", "program_scope_path": "org.234.kw.r.g.001", "status": "approved", "total": 50},
        {"count_id": "leaders", "date": "2026-11-01", "location_id": "l1", "event_id": "", "program_type": "Leaders Meeting", "program_level": "Group", "program_scope_path": "org.234.kw.r.g", "status": "approved", "total": 30},
    ]
    groups = aggregate_count_submissions(rows)
    assert len(groups) == 2
    assert {row["program_type"] for row in groups} == {"Workers Meeting", "Leaders Meeting"}


def test_state_approved_groups_keep_an_explicit_auto_accepted_marker():
    rows = [
        {"count_id": "state", "date": "2026-11-01", "location_id": "venue", "event_id": "", "program_type": "Sunday Worship", "program_level": "State", "program_scope_path": "org.234.kw", "status": "approved", "auto_accepted": True, "total": 200},
        {"count_id": "pastor", "date": "2026-11-01", "location_id": "l1", "event_id": "", "program_type": "Sunday Worship", "program_level": "Local", "program_scope_path": "org.234.kw.r.g.001", "status": "approved", "auto_accepted": False, "total": 100},
    ]

    groups = aggregate_count_submissions(rows)
    by_level = {row["program_level"]: row for row in groups}
    assert by_level["State"]["auto_accepted"] is True
    assert by_level["Local"]["auto_accepted"] is False
