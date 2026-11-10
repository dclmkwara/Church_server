# Analytics Slice E Validation Report

**Status:** Validation is partial; this report records passed checks and open evidence gates. No B3/B4/B5 work, navigation consolidation, remote database mutation, push, or deployment was performed in this validation pass.

## Database and Alembic validation

- A disposable PostgreSQL 17 cluster was created under the system temporary directory and listened on `127.0.0.1:55432`.
- The non-empty development snapshot `output/private-backups/remote-dev-public-pre-b6-retry-20261109T150826Z.dump` was restored. The Windows PostgreSQL installation lacks Supabase's `supabase_vault` extension, so the restore TOC excluded only the Vault extension, its schema, comment, and `vault.secrets` data (4 TOC entries). The remaining snapshot restored successfully: **57 public tables**, Alembic revision `b5f7a9c2d341`, 73 users, 349 workers, and 40 locations.
- `uv run alembic upgrade head` succeeded against that disposable clone, advancing it to `d7a4c1e2f809`. No remote connection was used.
- The original local service on port 5432 required a password; it was not modified or used. The temporary validation cluster is isolated from that service.

## Tests and reconciliation coverage

- Pastor report tests: **7 passed**.
- Full Church_server suite after the validation fix: **349 passed, 1 skipped in 21.43 seconds**. The skip is the authenticated browser sweep when its external test settings are absent; this pass supplied local personas and ran that sweep separately.
- Existing focused tests cover core Sunday-series parent/child aggregation, combined reports replacing covered location submissions, counted zero versus missing, fellowship categories, event additivity/non-additivity, and dashboard period formulas. Pastor report tests cover workbook/CSV sheets, six categories, no `NaN`/`undefined` in exported CSV, missing-vs-zero handling, and offering display state.
- This is not a complete reconciliation matrix across every additive metric on every page. Some pages use independent service calculations and still need explicit cross-page equality fixtures.

## Local live trace (diagnostic sample, not the required five-run matrix)

One authenticated State dashboard request against the restored local clone on port 55432 produced the following trace on port 8011:

| Measure | Observation |
|---|---:|
| Dashboard server render | 1,693 ms |
| Sunday dashboard API call | 1,655 ms |
| SQL statements | 7 |
| Sum of SQL elapsed time | 1,159 ms |

This single request does not satisfy the required five cold-process samples per persona for the dashboard, each domain page, and the report. A per-page live SQL trace matrix was not completed.

One local sign-in trace recorded about 2,482 ms in the API, including about 1,166 ms for user lookup and 1,240 ms for password verification. The admin frontend recorded about 2,704 ms for token exchange, 165 ms for profile/permission loading, 7 ms for redirect/cookie response, and about 2,878 ms total. This is one diagnostic sign-in, not a repeated benchmark.

## Mobile browser sweep

The authenticated Playwright sweep visited 12 analytics page entries (Dashboard, Retreat, Crusade, Leaders Meeting, Workers Meeting, Count Review, Expected Attendance, Attendance, Recurring Program Attendance, Finance Analytics, Newcomers, Pastor Report) plus 8 existing admin entries (Inbox, People, Church data, Finance, Fellowship, Organization, Reports, Programs) for State, Region, Group, and Location at 360×740, 390×844, and 768×1024 (240 persona/page/viewport combinations).

The first run found a real 500 on Retreat and Crusade. Their report action attempted to use `DashboardService` without importing it. The import is fixed, and a focused live browser check now receives HTTP 200 for Retreat, Crusade, and Pastor report.

The first run also raised false positives for content in a closed off-canvas menu and the dashboard's metric information icon. The latter is an accessible `summary` control whose visible “i” is a CSS pseudo-element, so its text font is intentionally zero-sized. The sweep ignores hidden off-canvas descendants and excludes only that icon control from the tiny-text check; document overflow, clipping, tap-target, and stacked-table checks remain active.

The corrected authenticated sweep passed: **1 passed in 209.98 seconds**, covering all 240 persona/page/viewport combinations. No horizontal overflow, clipping, undersized checked analytics action/link targets, or narrow-table layout failures were reported. The real Retreat/Crusade 500 found in the first run was fixed by importing `DashboardService`; both pages and the Pastor report returned HTTP 200 in focused browser checks.

Authenticated mobile screenshot of the State Pastor report page at 390×844: [pastor-report-state-mobile.png](output/playwright/pastor-report-state-mobile.png). This is a viewport screenshot of the preview page, not a browser print-dialog capture. The two A4 PDF page screenshots remain in the [Pastor report export report](PASTOR_REPORT_EXPORT_REPORT.md).

## Utility to database test

Not completed. The local database snapshot and backend are available, but this pass did not submit marked synthetic B6/E records through a running Field Utility and verify persistence/removal end to end. No utility data was written as part of validation.

## Still open

- No mobile layout violations remain in the tested routes/viewports; other widths, devices, and browser engines were not exercised.
- Five cold-process timings per persona for the dashboard, each new page, and Pastor report, plus live SQL statement traces per page.
- Full reconciliation and cross-page consistency matrix for every additive metric.
- Live Field Utility-to-local-database submission test with a synthetic marker and removal command.
- The Supabase-only Vault extension/data cannot be restored on this workstation's PostgreSQL build; Vault is excluded from the local analytics validation clone.

No production deployment or cloud smoke test was performed. FastAPI Cloud login and deployment remain with the user as previously agreed.
