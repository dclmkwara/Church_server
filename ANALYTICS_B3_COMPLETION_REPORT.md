# Analytics B3 Completion Report

**Date:** 8 November 2026  
**Scope:** B3 event analytics completion and its required small operational fixes. B4 is in progress; no B5 work is claimed here. No menu changes were made.

## Prior plan steps

| Step | Status | Evidence |
|---|---|---|
| Step 0: repository hygiene | Completed earlier | `ANALYTICS_FULL_PLAN_STEP0_REPORT.md`. |
| Step 1: migration/deployment | Database migration step completed earlier; hosted app deployment remains incomplete | `ANALYTICS_FULL_PLAN_STEP1_REPORT.md` records ledger head `e2b4c6d8f013` and the two migration revisions applied. No remote database writes were performed in this turn. Hosted app deployment was not confirmed; the current unfinished branch is not deployed. |
| Step 2: navigation audit | Completed earlier; navigation intentionally unchanged | Root `NAVIGATION_PAGE_AUDIT.md`. |

## B3 event data and reporting behavior

The removable fixture is `scripts/seed_b3_events.py`, marked `B3_DEMO:b3-events-demo-v1`. It supports `--remove` and refuses databases outside the approved loopback development databases. The fixture was run only against the disposable local restored clone (`church_alembic_restore_proof`, PostgreSQL port 55432), not against Supabase.

It provides Easter Retreats in 2025 and 2026, plus earlier and October 2026 Crusades. Retreat fixtures have five days with Bible Study, Prayer, and Evening Service sessions across regions, including a missing day, pending and rejected records, and a reported zero. Crusade fixtures include one State Alpha source, satellite reports, an omitted location, a convert-only submission, an unusually high count, and mixed approval statuses. The seed can be removed by marker.

Approved scheduled `ProgramEvent` rows define the session denominator. Future sessions display as upcoming; past unreported sessions are missing; missing is not represented as zero. Retreat coverage is region-based. Crusade satellite coverage uses active locations and their open/close dates; the church decision that every location participates is reflected by the plain `Locations reporting: n of m` label. Alpha remains one State-level reporter and is hidden below State scope.

The default State Retreat view selects the latest past Easter Retreat and day 2 Bible Study. On the current demo fixture the State-level cell is **2,026** with pending excluded and **2,360** with pending included. One region's approved value is `Reported 0`; a pending report contributes only when the pending switch is enabled. Retreat drills State to Region and stops there. Crusade drills State to Region to Group to Location. Campaign comparisons use only reporters with counted data in both campaigns; attendance is never totalled across days or sessions. Crusade Alpha and satellite counts are separate and the explicitly labelled total participation is shown only where Alpha is visible.

The old campaign-wide population sum has been removed from `campaign_activity()`. That page now identifies a count of submissions as “Records submitted”; per-event amounts remain available. Tuesday Leaders Meeting remains a separate page from Saturday Workers Meeting. The Leaders page retains the raw record view and says coverage is not defined.

## B3 and small operational fixes

- Location `/organization` now gives the location persona a valid home-location view, with a clean 403 if no valid location is available.
- Analytics dates use Africa/Lagos time for current-Sunday selection and related default dates; midnight boundary tests were added.
- The Count Review Remind control is shown only when the user has `counts:remind`.
- The top-bar search was removed because no scoped implementation existed; Help & Docs was removed because the target page is not mounted in normal mode.
- Roles & Permissions is restricted to State score 5 and above, including its menu entry.
- Reports show inline service errors instead of an empty-looking result on non-403 failures.
- Officials remains disabled because `unsupported_live_keys={"officials"}` in the shell configuration marks the page as unfinished; it was not enabled.
- “Average per reporting location” now defines the value as the mean of weekly per-location averages.

The requested small-fix browser/runtime checks and tests are included in this checkpoint. The scope remains unchanged for navigation menus.

## Performance and browser checks

State page traces on the local clone report:

| Page | SQL statements | Sequential depth | Observed server render elapsed | Evidence boundary |
|---|---:|---:|---:|---|
| Retreat | 11 | 11 | 191 ms | Latest instrumented State request; backend calls were campaign list (4 SQL) and occurrence matrix (7 SQL). |
| Crusade | 10 | 10 | 112 ms | Instrumented State request; campaign list (2 SQL) and occurrence matrix (8 SQL). |
| Tuesday Leaders Meeting | 9 | 9 | 592 ms | Latest instrumented State request after eliminating event lookup from the raw attendance panel; 5 SQL comparison call, 2 SQL location lookup, 2 SQL attendance read. |

A five-navigation browser sample from the earlier B3 pass yielded Retreat 317–429 ms (median 353 ms), Crusade 355–529 ms (median 358 ms), and Leaders 167–287 ms (median 223 ms). Those are repeat navigations in one running server, **not** five process-restart cold loads. The Leaders endpoint later changed as B4 roster deduplication was introduced, and the latest single server trace is listed above. So the requested five cold-process timings are not claimed as complete. Query count/depth is at or below 12 for each State page after the raw-attendance lookup reduction.

Browser inspection verified populated State Retreat (day 2 Bible Study), State Crusade, and State Leaders routes on port **8013**. Existing Region and Location screenshots are included from the same local fixture. Screenshots are synthetic demo data and do not represent church records:

- [State Retreat](output/playwright/b3/state-retreat-completion.png)
- [State Crusade](output/playwright/b3/state-crusade-completion.png)
- [Region Crusade](output/playwright/b3/region-crusade.png)
- [Location Crusade](output/playwright/b3/location-crusade-completion.png)
- [State Leaders Meeting](output/playwright/b3/state-leaders-completion.png)

The local app uses restored clone `church_alembic_restore_proof` on PostgreSQL port **55432**. App port **8013**. No remote write or migration occurred.

## Verification

- Full suite: **271 passed**, one third-party `fastcore` deprecation warning.
- Runtime: State Leaders page renders successfully after the ltree scope cast correction and lookup reduction.
- The default Retreat day 2 Bible Study pending toggle, coverage, comparison, zero-vs-missing, drill-down scope, Alpha visibility, and rendered-value assertions are covered by `tests/test_program_occurrences_api.py` and related tests.
- The new roster snapshot migration is applied to the local throwaway clone only. The remote database was not touched.

## Next work and limits

B3 is committed separately. The small-fix checkpoint follows as its own commit. B4 worker meeting analytics and B5 usher edit-window work remain in progress; the user requested a stop for review after B5. B6, C, D, E and navigation consolidation are not started. Hosted app deployment and the five cold-process timing set remain unverified.
