# Slice C: Dashboard Summary Completion

**Status:** Implemented and committed locally. Slice D has not started yet.

## Changes

- Added dashboard cards for approved offerings, newcomers, and converts. The cards use the selected 4- or 8-Sunday window and compare it with the immediately preceding window of the same length.
- Offerings include only non-deleted rows with `status = approved`; the card reports both the amount and number of approved records.
- Newcomer and convert cards count non-deleted `records` by `record_type` and occurrence `date`. These are report-record counts, not deduplicated people.
- Period deltas handle zero and empty prior periods explicitly. A zero prior value is described as “Up from 0” or “New this period”; no division by zero or `NaN` is rendered.
- Added “Waiting on a decision” with scoped counts and the age of the oldest item for worker registrations, user access, count groups, offerings, transfers, status changes, and worker removals. Count rows in a split submission are counted as one approval group. Age comes from the stored `created_at` timestamp.
- The existing pooled expected-attendance percentage remains sourced from the Sunday series calculation, including its current `include_pending` behavior. The dashboard and child/location detail views read the same series values; no estimate or population calculation was duplicated.
- The new card and decision panel markup uses the existing FastHTML/Faststrap dashboard primitives and the current branded light palette.

## Query count

The added period totals, period record counts, pending categories, and oldest timestamps are scalar subqueries inside the existing single `DashboardService.get_summary()` SQL statement. They add no database round trip.

Static call-path count for a State initial dashboard payload:

| Work | SQL statements |
|---|---:|
| Sunday series: hierarchy/estimates, program/events, count rows | 3 |
| Summary aggregate, including the new metrics | 1 |
| Worker meeting analytics | 2, plus 1 worker-ID lookup when roster snapshots contain IDs |
| **Total application data statements** | **6–7** |

This is below the 12-statement target for the dashboard data path. Authentication, permission loading, and database RLS/session setup are shared request work and are excluded from this static count; no live SQL trace was captured for this checkpoint.

## Verification

- `uv run --extra test pytest -q`: **327 passed, 1 skipped**.
- Python compile check passed for the changed service, API, frontend route, and new summary test.
- Tests cover selected-window propagation, a single scoped summary statement, Africa/Lagos-aware period boundaries, zero-safe deltas, and the pending-decision panel’s empty and populated states.
- No remote database writes or deployment were performed. This report does not claim a live browser screenshot or a live data comparison; the dashboard code and tests were verified locally.

## Commit

- Implementation: `edeed4a9b2519a899641df7f8496e16176b610b5` — `Complete dashboard summary cards and pending decisions`.
- Report: committed separately after the implementation checkpoint.

## Still outstanding

- Step A RBAC changes are local; remote RBAC synchronization remains blocked by the remote RLS policy.
- B6 migration is local and validated on a disposable PostgreSQL clone; applying it remotely remains blocked until a fresh, non-empty backup can be obtained.
- The previously requested live Count Review screenshot and remote legacy-count recount remain outstanding because the remote database connection was unavailable.
- Slice D and later validation/navigation work have not started.
