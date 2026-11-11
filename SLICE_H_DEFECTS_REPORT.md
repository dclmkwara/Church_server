# Slice H Defects Report

**Date:** 11 November 2026
**Scope:** Local-only fixes before the next push. No remote database access, migration, deployment, or push was performed.

## Results

### `/api/v1/reports/summary` ValidationError

**Fixed and regression-tested locally.** `ReportService.get_daily_counts()` validated database row mappings directly as `DailyCountSummary`. PostgreSQL returns `location_id` as a UUID object, while the response schema declares it as a string. Reproducing that input locally raises Pydantic's `ValidationError` (`location_id: Input should be a valid string`). The service now casts the selected UUID and `ltree` path to text and normalizes UUID/path/event values before response-model validation. The regression test includes a UUID object and a null event ID, the latter normalized to the schema's empty-string representation.

The source-level cause is confirmed and the regression test passes. The API was not deployed or re-tested on the cloud in this no-push slice; the previously attached deployment excerpts do not contain a request-correlated `/reports/summary` traceback, so I cannot claim a production request replay.

### Location `/organization` crash

**Fixed at the identity handoff.** The login payload had the location UUID, but `AuthService.get_identity()` reconstructed its user object from cookies without `location_id`. The Location root therefore could not identify its home location reliably. The UUID is now stored in an HttpOnly session cookie, restored into the identity, and cleared at logout. The Location “Open My Location” action now uses that UUID instead of the final hierarchy-code segment. Demo mode retains its path-code fallback. If a live identity still lacks a location UUID, `/organization` returns the existing clean 403 response.

Tests cover the cookie round trip and the missing-ID 403 response.

### Count Review reminder permission

**Already aligned; no implementation change was needed.** The button and page handler both use `counts:remind`, matching the backend reminder endpoint's permission. The permission regression test passes.

### Top-bar search and dead Docs link

**Already absent from the current navigation build.** The top bar has no global search field, and the sidebar has no `/docs` link. A regression test now asserts neither is rendered. The prior navigation audit recorded the former `/docs` target as a 404; the navigation consolidation removed that link.

### Honest error pages with reference IDs

Unhandled 500s now receive a short reference ID. The same ID is logged with the exception and shown to the user on full-page and HTMX responses, and is returned in `X-Error-Reference`. The exception details remain in the server log rather than the user-facing page. 404 responses also carry a reference ID and header. Direct response tests verify both the visible and header values.

### SQL echo

SQLAlchemy engine echo is now disabled unconditionally. The supplied cloud logs showed SQL statements and bound parameters being emitted by `sqlalchemy.engine.Engine`; echoing can disclose identifiers and submitted values. Query timing remains available through the existing opt-in instrumentation without logging SQL parameters. A test asserts `engine.echo is False`.

## Pending visibility table

This table describes current behavior; a pending report being visible in a queue or coverage indicator does not mean its value is included in a total.

| Page/API | Default counted value | Pending visibility | Rejected visibility |
|---|---|---|---|
| Analytics Dashboard | Approved counts only | Pending appears in coverage and Needs attention; the include-pending control opts into pending values | Excluded from counted totals; returned/conflict states remain distinct in coverage |
| Retreat / Crusade analytics | Approved counts only | Excluded by default; include-pending is an explicit query/filter option and pending is separately represented | Excluded |
| Count Review | Not a summary-total page | Pending count groups are shown to authorized reviewers for a decision | Returned/correction history is displayed on the review record; rejected values are not counted |
| Pastor Report | Approved counts only | Optional include-pending filter; pending lines are identified as pending approval | Excluded from counted report values |
| Finance Analytics | Approved offering rows only | Pending offerings do not contribute to the approved financial summary | Excluded |
| Legacy `/api/v1/reports/summary` | **All non-deleted count rows in its materialized view** | The response shape has no status field or include-pending switch, so pending values cannot be separated there | The view also has no status field, so rejected values cannot be separated there |

The last row is a documented legacy limitation, not silently described as approved-only. Changing it safely requires changing the materialized-view/report contract so statuses are available; no migration or semantic change was included in this defect slice.

## Migrations and scope

No Alembic revision was added by the two earlier commits checked for this handoff (`472f2636866f6c2dbf367aef4a378863a3ffd3f3` and `a034d8251c99c6e9486bdf570ea2093caab0877e`), and this slice adds none. No remote migration is needed for these changes. No remote database writes were made.

## Verification

- Focused regression suite: **23 passed**.
- Church_server full suite: **382 passed, 3 skipped**.
- Field Utility full suite: **41 passed**.
- No browser/cloud replay was performed; the code remains local and unpushed.

## Changed files

- `app/services/report_service.py`
- `app/frontend/dclm_admin/communication/auth_service.py`
- `app/frontend/dclm_admin/routes/organization.py`
- `app/frontend/dclm_admin/components/error_pages.py`
- `app/db/session.py`
- `tests/test_report_summary_uuid_serialization.py`
- `tests/test_organization_root.py`
- `tests/test_ui_and_error_pages.py`
- `tests/test_navigation_consolidation.py`
- `tests/test_cloud_sql_logging.py`
- `SLICE_H_DEFECTS_REPORT.md`

The working tree contained unrelated existing files and artifacts. Only the paths listed above were staged for this commit.
