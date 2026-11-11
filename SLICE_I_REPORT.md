# Slice I: Reports Consistency

**Scope:** Local application changes only. No push, remote database access, remote write, or migration was performed.

## Result

Reports Summary now reads count submissions directly and presents one row per occurrence/service. It sums split parts only when they share the same `count_group_id`; legacy ungrouped rows remain separate. It does not add attendance across dates or across separate services. Approved rows count by default. The Summary checkbox and count exports can explicitly include pending/corrected rows. Rejected and returned rows never count. A count group with conflicting state or mixed review states is not presented as a complete count.

The old `mv_daily_counts_by_location` view is no longer used by Reports Summary because it does not preserve the review-state and service distinctions needed here. The view itself and the figures on the Dashboard, Pastor Report, Retreat/Crusade, Finance Analytics, and meeting pages were not changed.

## Shared review-state policy

The new policy is [reporting_policy.py](app/services/analytics/reporting_policy.py). It defines the current rule in one place: approved by default; pending and corrected only when explicitly included; rejected and returned excluded. It provides Python helpers, SQLAlchemy filters, and a trusted SQL-fragment helper.

The policy is now used by:

- Sunday Worship/dashboard and shared recurring-program calculations in `analytics/sunday_worship.py` and `analytics/program_occurrences.py`.
- Dashboard offering totals in `dashboard_service.py` and the dashboard API route.
- Reports Summary, the Reports count export, and the Reports financial SQL in `report_service.py` and the Reports API route.
- Reports mock count occurrence grouping, plus Finance Analytics totals in the Admin frontend communication services.
- Reports API count time series, level breakdown, growth and anomaly count/finance queries. Those tabs no longer present their independent figures in the UI, but their routes remain and use the same default rule.

The Pastor Report uses the shared Sunday Worship calculation. Retreat/Crusade uses the shared program-occurrence calculation. Finance Analytics now uses the shared rule for reviewable offerings. House Caring Fellowship records have no review-status field and retain their documented saved-record behavior; the policy is not applied to them. Worker meeting attendance `present`/`late` states describe attendance, not report approval, so they are not treated as review states.

## Reports tab audit and disposition

| Reports tab | Review-state behavior before this slice | Could differ from its dedicated page? | Result and definition shown |
|---|---|---|---|
| Summary | Materialized view did not distinguish pending or rejected rows. | Yes; it could include unapproved rows and combine separate services/dates. | Kept. One row is one count occurrence/service; split parts are summed only within their count group. Pending is optional; rejected/returned are excluded. |
| Financial | API summary already filtered to approved offerings. | Yes; duplicate calculation and export paths could drift from Finance Analytics. | Replaced the figures with a link to Finance Analytics. Definition: approved offerings and tithes for selected dates; pending and rejected excluded. |
| Attendance | Used raw worker attendance trend records, not the meeting pages' roster snapshot calculations. | Yes; its denominator and meeting record semantics differ. | Replaced with links to separate Saturday Workers Meeting, Tuesday Leaders Meeting and recurring program attendance pages. Definition: each meeting/program remains separate; meeting rates use that meeting's roster snapshot. |
| Timeseries | Count series included all review states; finance was approved-only; worker-attendance series counted raw records. | Yes; count series could include pending/rejected and combine concepts unlike dedicated pages. | Replaced with links to Dashboard, Finance Analytics and separate meeting pages. Definitions state each page's source and exclusions. |
| By Level | Count branch included all review states; finance was approved-only; attendance used raw trend rows. | Yes; its totals could disagree with the corresponding scoped pages. | Replaced with a Dashboard link. Definition: hierarchy drill-down and coverage are read from the scoped Dashboard. |
| Growth | Count growth included all review states and summed counts by time bucket. | Yes; pending/rejected rows and multiple sessions could inflate a bucket. | Replaced with Dashboard and recurring-program links. Definition: Dashboard trend is an average per reporting location with coverage; sessions/days are not combined. |
| Anomalies | Count anomaly scan included all review states; finance used approved rows. | Yes; its inputs could disagree with current reporting and attention rules. | Replaced with Dashboard Needs attention. Definition: missing reports, overdue reviews, returned reports and qualifying declines under the shared rules. |
| Exports | Count and financial exports had separate paths; Excel/PDF count scope handling could fall back to the user's default scope. | Yes. | Routes remain. Count CSV/Excel/PDF now use the shared occurrence summary, scope and include-pending setting. Financial exports remain approved-only. Worker attendance export is explicitly defined as attendance records, not a unique-attendee or population count. |

No route was deleted. The Financial, Attendance, Timeseries, By Level, Growth and Anomalies tabs now link to the corresponding authoritative pages instead of showing competing calculations. The Exports tab remains available. Export endpoints remain available for existing callers.

## Summary and export details

- `/api/v1/reports/summary` defaults to approved-only and accepts `include_pending=true` for pending/corrected rows.
- A count group's parts are summed at read time and grouped by the stored group identity. Different `service_id` values and different dates remain separate occurrences.
- Conflicting groups and groups whose parts have mixed review states are omitted, including when pending is enabled. This avoids presenting an incomplete group as a valid whole.
- CSV, Excel and PDF count exports accept the same pending option and validated scope. The Admin frontend forwards both values.
- Financial and count endpoints continue to apply scope validation at the API boundary.

## Reconciliation coverage and limits

The permanent opt-in browser test in `tests/test_f3_rendered_reconciliation.py` now compares the rendered Reports Summary and its count CSV export with independent SQL over source rows. It verifies each occurrence, service, status and count total. The existing scope loop covers State, Region, Group and Location, so State and Location are included.

The live rendered comparison could not run in this workspace: `F3_DATABASE_URL`, `F3_BASE_URL`, `F3_SCOPE_PATHS` and `F3_COOKIE_STATE` are not configured, and the local clone/server are not running. The test skipped by design. No live-page result is claimed. Unit and API-path tests cover approved/pending/rejected behavior, grouped split parts, service separation, mixed-state conflicts, frontend links and pending-option forwarding.

## Migration

**No migration is needed.** The implementation uses existing `counts`, `count_groups`, `locations`, `program_events`, `program_types`, and `offerings` columns. No Alembic revision was added and the materialized view was not altered.

For a future application release, deploy the application code normally; do not run `alembic upgrade` for Slice I. The local clone used during this slice was not migrated or written.

## Verification

- Focused Reports, service adapter and reconciliation tests: **44 passed, 1 skipped**.
- Full Church_server suite: **389 passed, 3 skipped**.
- Full Field Utility suite: **41 passed**.
- Skips are environment-gated live integration tests. Pytest emitted the existing `pytest-asyncio` fixture-loop deprecation warning; one frontend test also emitted the existing Faststrap global-default warning.
- No remote database access, remote write, deployment, or push occurred.

## Commit

The Slice I changes and this report are committed together. See the commit hash in the handoff message.
