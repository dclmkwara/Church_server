import asyncio
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
import pytest
from uuid import uuid4
from fastapi import HTTPException

from app.frontend.dclm_admin.communication.count_aggregation import aggregate_count_submissions, summarize_count_submissions
from app.api.v1.routes import counts as count_routes
from app.api import deps
from app.api.v1.routes.counts import COUNT_APPROVED, COUNT_PENDING, COUNT_REJECTED, _acceptor_score, _count_group_key
from app.api.v1.routes.counts import close_count_group
from app.models.counts import Count, CountGroup
from app.schemas.counts import CountCreate, CountGroupCloseRequest
from pydantic import ValidationError
from app.utils.count_sections import legacy_section_label
from app.utils.count_groups import count_group_deadline, count_group_is_past_deadline, missing_suggested_labels, require_count_mode, require_section_label_available


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


def test_split_sections_sum_only_when_every_section_is_approved():
    base = {"date": "2026-11-01", "location_id": "l1", "event_id": "", "program_type": "Sunday Worship", "count_mode": "section"}
    rows = [
        {**base, "count_id": "one", "section_label": "Hall A", "status": "approved", "total": 20},
        {**base, "count_id": "two", "section_label": "Hall B", "status": "approved", "total": 30},
    ]
    result = aggregate_count_submissions(rows)[0]
    assert result["total"] == 50
    assert result["split_count"] is True
    assert result["section_count"] == 2

    rows[1]["status"] = "pending"
    partial = aggregate_count_submissions(rows)[0]
    assert partial["total"] is None
    assert partial["status"] == "partial_approval"


def test_multiple_single_counts_and_mixed_modes_are_conflicts_not_totals():
    base = {"date": "2026-11-01", "location_id": "l1", "event_id": "", "program_type": "Sunday Worship", "status": "approved"}
    two_single = aggregate_count_submissions([
        {**base, "count_id": "one", "count_mode": "single", "total": 20},
        {**base, "count_id": "two", "count_mode": "single", "total": 30},
    ])[0]
    mixed = aggregate_count_submissions([
        {**base, "count_id": "one", "count_mode": "single", "total": 20},
        {**base, "count_id": "two", "count_mode": "section", "section_label": "Hall B", "total": 30},
    ])[0]
    assert two_single["status"] == mixed["status"] == "conflict"
    assert two_single["total"] is None
    assert mixed["total"] is None


def test_legacy_rows_continue_to_sum_without_becoming_conflicts():
    base = {"date": "2026-11-01", "location_id": "l1", "event_id": "", "program_type": "Sunday Worship", "status": "approved"}
    result = aggregate_count_submissions([
        {**base, "count_id": "one", "total": 20},
        {**base, "count_id": "two", "total": 30},
    ])[0]
    assert result["total"] == 50
    assert result["status"] == "approved"
    assert result["mode_recorded"] is False


def test_count_group_key_keeps_distinct_event_occurrences_separate():
    common = {"location_id": "location-a", "program_type_id": 4, "date": datetime(2026, 11, 1, tzinfo=timezone.utc)}
    first = Count(**common, event_id=uuid4(), program_level="Local", program_scope_path="org.state.region.group.location")
    second = Count(**common, event_id=uuid4(), program_level="Group", program_scope_path="org.state.region.group")
    assert _count_group_key(first) != _count_group_key(second)


def test_split_count_group_id_is_the_occurrence_identity_and_service_is_separate():
    rows = [
        {"count_id": "a1", "count_group_id": "service-a", "date": "2026-11-01", "location_id": "l1", "program_type": "Sunday Worship", "service_id": "Morning", "count_mode": "section", "section_label": "Hall A", "status": "approved", "total": 40},
        {"count_id": "a2", "count_group_id": "service-a", "date": "2026-11-01", "location_id": "l1", "program_type": "Sunday Worship", "service_id": "Morning", "count_mode": "section", "section_label": "Hall B", "status": "approved", "total": 60},
        {"count_id": "b1", "count_group_id": "service-b", "date": "2026-11-01", "location_id": "l1", "program_type": "Sunday Worship", "service_id": "Evening", "count_mode": "single", "status": "approved", "total": 80},
    ]
    groups = aggregate_count_submissions(rows)
    assert len(groups) == 2
    by_service = {row["service_id"]: row for row in groups}
    assert by_service["Morning"]["total"] == 100
    assert by_service["Evening"]["total"] == 80


def test_duplicate_section_labels_are_conflicts_and_not_summed():
    base = {"date": "2026-11-01", "location_id": "l1", "event_id": "", "program_type": "Sunday Worship", "count_group_id": "g", "count_mode": "section", "status": "approved", "section_label": "Hall A"}
    result = aggregate_count_submissions([
        {**base, "count_id": "one", "total": 20},
        {**base, "count_id": "two", "total": 30},
    ])[0]
    assert result["status"] == "conflict"
    assert result["total"] is None


def test_mixed_mode_is_rejected_with_plain_language_conflict():
    with pytest.raises(HTTPException) as error:
        require_count_mode("single", "section")
    assert error.value.status_code == 409
    assert "already using a different count mode" in str(error.value.detail)


def test_missing_suggestions_are_a_soft_warning_and_duplicate_labels_are_rejected():
    suggestions = [{"label": "Balcony", "hidden": False}, {"label": "Overflow", "hidden": True}]
    missing = missing_suggested_labels(suggestions, set())
    assert missing == ["Balcony"]
    assert missing_suggested_labels(suggestions, {"balcony"}) == []
    with pytest.raises(HTTPException) as error:
        require_section_label_available(["Balcony"], " balcony ")
    assert error.value.status_code == 409
    assert "different section label" in str(error.value.detail)


def test_count_group_auto_closes_at_existing_missing_window_end_in_lagos():
    deadline = count_group_deadline(date(2026, 11, 1))
    assert deadline.isoformat() == "2026-11-03T00:00:00+01:00"
    assert not count_group_is_past_deadline(date(2026, 11, 1), deadline - timedelta(seconds=1))
    assert count_group_is_past_deadline(date(2026, 11, 1), deadline)


def test_one_approval_action_approves_every_pending_part(monkeypatch):
    pastor_id = uuid4()
    rows = [
        Count(id=uuid4(), status="pending", count_mode="section", section_label=label, total=number, auto_accepted=False)
        for label, number in (("Hall A", 20), ("Hall B", 30))
    ]

    async def review_target(_db, _count_id, _current_user):
        return rows[0], rows

    class Session:
        commits = 0

        async def commit(self):
            self.commits += 1

    monkeypatch.setattr(count_routes, "_review_target", review_target)
    cache_cleared = []
    monkeypatch.setattr(count_routes.analytics_cache, "clear", lambda: cache_cleared.append(True))
    db = Session()
    result = asyncio.run(count_routes.approve_count_group(
        uuid4(), db=db, current_user=SimpleNamespace(user_id=pastor_id),
    ))
    assert [row.status for row in rows] == ["approved", "approved"]
    assert len(result["count_ids"]) == 2
    assert db.commits == 1
    assert cache_cleared == [True]


def test_any_user_at_the_location_can_close_a_split_group(monkeypatch):
    group_id, count_id, lead_id, other_id = uuid4(), uuid4(), uuid4(), uuid4()
    row = SimpleNamespace(id=count_id, count_group_id=group_id, is_deleted=False, path="org.234.kw.r.g.l", entered_by_id=lead_id)
    group = SimpleNamespace(id=group_id, location_id="loc", lead_usher_id=lead_id, state="open", finalized_at=None, finalized_by=None, auto_closed_at=None, close_reason=None)

    class Result:
        def scalars(self):
            return self

        def all(self):
            return []

    class Session:
        async def get(self, model, _id, **_kwargs):
            return row if model is Count else group if model is CountGroup else None

        async def execute(self, _statement):
            return Result()

        async def commit(self):
            pass

    monkeypatch.setattr(deps, "ensure_path_in_scope", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(deps, "effective_scope_path", lambda _actor: row.path)
    monkeypatch.setattr(count_routes, "_section_suggestions", lambda *_args: asyncio.sleep(0, result=[]))
    result = asyncio.run(close_count_group(
        count_id, CountGroupCloseRequest(), db=Session(),
        current_user=SimpleNamespace(user_id=other_id),
    ))
    assert result["ready_for_approval"] is True
    assert group.finalized_by == other_id


def test_field_utility_split_submission_requires_a_section_label():
    base = {"event_id": uuid4(), "location_id": "location-a"}
    with pytest.raises(ValidationError):
        CountCreate(**base, count_mode="section")
    submission = CountCreate(**base, count_mode="section", section_label="Main hall")
    assert submission.count_mode == "section"
    assert submission.section_label == "Main hall"
    assert CountCreate(**base).count_mode == "single"
