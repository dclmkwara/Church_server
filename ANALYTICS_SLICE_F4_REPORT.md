# Analytics Slice F4 Reconciliation Report

**Status:** Bounded reconciliation complete; report committed separately. No push or remote database write.

## Commits

| Commit | Scope |
|---|---|
| `d43b9b5a8421b84a9250d9e824b983be6eec4b94` | F3 checkpoint: independent reconciliation SQL, rendered dashboard/Pastor Report test, and opt-in `DCLM_ANALYTICS_PERF` timing instrumentation. |
| `5a4faa9b2cb4022282bffedd0607848044d9be3a` | F4 fixture, rendered reconciliation test, independent SQL corrections, and shared-source fixes. |
| Report commit | Added after this report is written; hash recorded in the final handoff. |

## Test environment and dataset

All writes were confined to the disposable local PostgreSQL clone `dclm_slice_f` on port **55434**. The Church Admin instance used for rendered HTTP pages and exports ran on port **8028**. The fixture script `scripts/seed_f4_reconciliation.py` refuses non-loopback hosts and any database name other than `dclm_slice_f`; it supports `--apply` and `--remove` and marks its rows `F4_TEST:f4-v1`.

The marked fixture included approved offerings in two funds (one with a corrected service date), Saturday workers attendance using a changed roster snapshot, Tuesday leaders attendance, fellowship attendance and offering, approved newcomer and convert records, an approved zero Sunday report, an edited-then-approved demographic count, and a regional retreat day count. Existing pending finance and follow-up records remained unmodified and were included where the corresponding page reports them.

## Rendered-page and export reconciliation

The permanent opt-in test `tests/test_f4_rendered_reconciliation.py` calls the running app over HTTP, parses rendered HTML, downloads and parses Pastor Report XLSX/CSV, and compares those values with independent SQL. It does not call analytics service functions. Each assertion runs at State, Region, Group, and Location scope paths. `scripts/f3_reconciliation_queries.sql` contains the independent SQL definitions for demographic counts, offerings, roster-based workers, fellowship attendance and offerings, newcomers/converts, and event counts.

| Metric | State | Region | Group | Location | Result |
|---|---:|---:|---:|---:|---|
| SWS total, 8 Nov | 60 | 60 | 60 | 60 | HTML card, category export, and CSV agree with SQL. Categories are Adult M/F 18/22, Youth M/F 7/8, Children M/F 3/2. |
| SWS total, 1 Nov | 6,072 | 2,400 | 503 | 166 | Rendered dashboard/export agrees with SQL. |
| SWS total, 25 Oct | 536 | 536 | 536 | No local report | Combined group report replaces covered location rows; the location page does not inherit the group report. |
| SWS total, 18 Oct | 6,263 | No report in this Region | No report in this Group | No local report | Rendered/exported State result agrees with SQL. |
| Approved offering/tithe amount, selected period | ₦19,000 (₦13,800 offering + ₦5,200 tithe) | ₦19,000 | ₦19,000 | ₦19,000 | Finance page and workbook/CSV match SQL. The edited tithe service date is 31 Oct → 1 Nov and has one correction audit. |
| Pending/corrected finance amount | ₦535,001 across 4 records | Same | Same | Same | Finance page and workbook/CSV match SQL; excluded from approved amount. |
| Saturday Workers Meeting | 9 present / 28 expected; 32.1% over 3 meetings | Same | Same | Same | Meeting page roster denominator and rate match SQL; stored roster snapshot is counted once per meeting, not current roster size. |
| Tuesday Leaders Meeting | 1 present / 2 expected; 50% | Same | Same | Same | Separate page and SQL metric agree. |
| Fellowship latest attendance | 25 | 25 | 25 | 25 | Fellowship view matches SQL latest-per-fellowship average; Pastor Report HCF export agrees. |
| Fellowship offering | ₦1,250 | ₦1,250 | ₦1,250 | ₦1,250 | SQL and rendered Fellowship view agree. |
| Newcomer records / convert records | 2 / 5 | 2 / 5 | 2 / 5 | 2 / 5 | Rendered follow-up page and dashboard cards match record SQL. These are records, including existing pending follow-up records, not unique-person totals. |
| Marked retreat Bible Study day | 130 | 130 | Not included | Not included | Retreat page and Retreat/Crusade export agree with SQL at the event reporting scope and ancestor; Group/Location do not show this region-level record. |
| Crusade | No campaign/report in local clone | No campaign/report | No campaign/report | No campaign/report | The page and export empty states were checked; there was no value to reconcile. |

Finance summary and offering detail exports, worker Saturday/Tuesdays pages, Fellowship view and HCF export, Newcomers, Retreat/Crusade views and exports, dashboard cards, and Pastor Report exports were fetched from the live local app. No separate standalone Fellowship export or Newcomers CSV/XLSX route exists in the current app; those metrics were compared on their rendered pages and, for HCF, on the Pastor Report sheet. The Crusade page had no campaign in this clone, so it was validated as an empty state only.

## Mismatches found and fixed

1. **Retreat count leaked from Region to descendant pages.** A report is physically attached to its venue, while `program_scope_path` identifies its reporting scope. The event occurrence query filtered only by physical path, allowing a regional report to appear at its venue’s Group/Location pages. `get_program_occurrences()` now applies both physical scope and declared reporting scope (falling back to physical path for legacy rows). The rendered test confirms 130 at State/Region and excludes it at Group/Location.
2. **Fellowship page returned HTTP 500 against the live adapter.** The adapter supplies normalized `location`, while the page indexed `location_name`. The route now accepts either representation; a regression test covers normalized and legacy rows.
3. **Independent count SQL omitted exact-scope rows and mixed program types.** The F3 reference query previously used only descendant paths and did not restrict counts to Sunday Worship. It now includes the exact scope path, descendants, and the Sunday Worship program type. This made the SQL comparator match the Location view and prevented unrelated program counts from entering the comparison.

The fixture’s canonical program-level spelling and unique prior Saturday were also corrected while preparing the test; these were fixture issues, not application defects.

## Verification and cleanup

- F4 rendered reconciliation plus related program-occurrence, dashboard-period, and Fellowship tests: **15 passed**.
- F3 rendered reconciliation: **1 passed**.
- One third-party `pytest-asyncio` configuration deprecation warning was emitted. The full repository suite was not run for this bounded slice.
- The fixture was removed with `scripts/seed_f4_reconciliation.py --remove`. The script reported **0 marked rows** in each checked table: counts, offerings, worker attendance and submissions, fellowship attendance and offerings, records, program events and campaigns, fellowships, edit revisions, and offering audits.
- The temporary server was run only against the local clone. No remote DB was accessed or modified.
- No screenshots were requested for F4 and none were captured.

## Still open

- There was no Crusade campaign in the local clone, so only its empty state was reconciled; populated Crusade figures remain unverified.
- Standalone Fellowship and Newcomers exports do not exist; their rendered views were checked, and Fellowship’s HCF export was checked through the Pastor Report workbook/CSV.
- The complete repository test suite was not run. No push was made.
