"""Independent reference rules for Slice F reconciliation cases.

This fixture deliberately does not call dashboard/domain page services. It is
a small reference oracle for status, replacement, splitting, and occurrence
grain rules; endpoint-by-endpoint parity is reported separately.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Count:
    scope: str
    date: str
    service: str
    status: str
    categories: tuple[int, int, int, int, int, int]
    mode: str = "single"
    covered: tuple[str, ...] = ()
    revision_current: bool = True

    @property
    def total(self) -> int:
        return sum(self.categories)


LOCATIONS = ("L1", "L2", "L3")
ANCESTORS = {
    "L1": ("G1", "R1", "S1"),
    "L2": ("G1", "R1", "S1"),
    "L3": ("G2", "R1", "S1"),
    "G1": ("R1", "S1"),
    "G2": ("R1", "S1"),
    "R1": ("S1",),
    "S1": (),
}


def reference_counts(rows: list[Count], scope: str, include_pending: bool = False) -> list[Count]:
    """Return current counted records visible at scope, preserving occurrence grain."""
    allowed_statuses = {"approved"} | ({"pending"} if include_pending else set())
    visible = [
        row for row in rows
        if row.revision_current and row.status in allowed_statuses
        and (row.scope == scope or scope in ANCESTORS.get(row.scope, ()))
    ]
    # A combined report replaces only the covered local rows for the same
    # program occurrence and service; it is counted once at its own scope.
    descendants = set(scope_descendants(scope))
    combined = [row for row in visible if row.covered and row.scope in descendants | {scope}]
    replaced = {
        (location, row.date, row.service)
        for row in combined for location in row.covered
    }
    return [row for row in visible if row.scope == scope or (
        row.scope in descendants and (row.scope, row.date, row.service) not in replaced
    )]


def scope_descendants(scope: str) -> tuple[str, ...]:
    return tuple(node for node, ancestors in ANCESTORS.items() if scope in ancestors)


def metric_by_occurrence(rows: list[Count]) -> dict[tuple[str, str], tuple[int, ...]]:
    totals: dict[tuple[str, str], list[int]] = {}
    for row in rows:
        key = (row.date, row.service)
        bucket = totals.setdefault(key, [0] * 6)
        for index, value in enumerate(row.categories):
            bucket[index] += value
    return {key: tuple(values) for key, values in totals.items()}


def test_pending_is_opt_in_rejected_missing_and_old_revision_do_not_count():
    rows = [
        Count("L1", "2026-11-01", "main", "approved", (1, 2, 3, 4, 5, 6)),
        Count("L1", "2026-11-01", "main", "pending", (10, 10, 10, 10, 10, 10)),
        Count("L1", "2026-11-01", "main", "rejected", (20, 20, 20, 20, 20, 20)),
        Count("L1", "2026-11-01", "main", "approved", (30, 30, 30, 30, 30, 30), revision_current=False),
        # No row for L2 is deliberately missing; it is not a zero.
        Count("L3", "2026-11-01", "main", "approved", (0, 0, 0, 0, 0, 0)),
    ]
    assert [row.total for row in reference_counts(rows, "G1")] == [21]
    assert [row.total for row in reference_counts(rows, "G1", include_pending=True)] == [21, 60]
    assert "L2" not in {row.scope for row in reference_counts(rows, "G1")}
    assert any(row.scope == "L3" and row.total == 0 for row in reference_counts(rows, "G2"))


def test_split_parts_sum_categories_but_keep_service_occurrences_separate():
    rows = [
        Count("L1", "2026-11-01", "main", "approved", (2, 3, 1, 2, 1, 2), "section"),
        Count("L1", "2026-11-01", "main", "approved", (1, 1, 2, 1, 2, 1), "section"),
        Count("L1", "2026-11-01", "evening", "approved", (1, 0, 0, 0, 0, 0)),
    ]
    by_occurrence = metric_by_occurrence(reference_counts(rows, "L1"))
    assert by_occurrence[("2026-11-01", "main")] == (3, 4, 3, 3, 3, 3)
    assert by_occurrence[("2026-11-01", "evening")] == (1, 0, 0, 0, 0, 0)
    assert len(by_occurrence) == 2  # readers get separate occurrences, not a cross-session sum


def test_combined_approved_occurrence_replaces_covered_location_reports():
    rows = [
        Count("L1", "2026-11-08", "main", "approved", (5, 0, 0, 0, 0, 0)),
        Count("L2", "2026-11-08", "main", "approved", (7, 0, 0, 0, 0, 0)),
        Count("G1", "2026-11-08", "main", "approved", (20, 1, 2, 3, 4, 5), covered=("L1", "L2")),
    ]
    visible = reference_counts(rows, "S1")
    assert sum(row.total for row in visible) == 35
    assert sum(row.total for row in reference_counts(rows, "G1")) == 35
    # The same covered locations' local reports remain visible at location scope.
    assert sum(row.total for row in reference_counts(rows, "L1")) == 5


def test_pooled_ratio_uses_pooled_totals_not_mean_of_location_rates():
    attendance = [90, 10]
    estimates = [100, 10]
    pooled = sum(attendance) / sum(estimates) * 100
    mean_of_rates = sum(a / e * 100 for a, e in zip(attendance, estimates)) / 2
    assert round(pooled, 2) == 90.91
    assert mean_of_rates == 95
    assert pooled != mean_of_rates
