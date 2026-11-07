# Analytics Slice 2 and B2b Close-out Report

**Date:** 7 November 2026  
**Scope:** Slice 2 correctness and performance checkpoint, plus B2b expected Sunday attendance. B3 and the deferred attendance/count slices were not started.

## Checkpoints

| Part | Commit | Result |
|---|---|---|
| Part 1: reminder recipients and decline rules | `4d84f2838e07f12a98a8177eec2129fd1980d426` | Committed separately. |
| Part 2: query batching, request timing and dashboard panels | `20d8898b713aea27907ff8a14f16e7c0a76724e9` | Committed separately. |
| B2b: expected Sunday attendance | Included in the B2b checkpoint recorded in the handoff | Implementation and migration are local; remote migration is blocked by the empty Alembic ledger described below. |

## Part 1 correctness confirmations

- **Reminders:** delivery is limited to the reporting usher accounts and Location Pastor for the missing location. A recipient is resolved per location; higher-scope users and `all_users` are not recipients. The route checks reminder permission and that the requested location is within the actor's scope. A `(location, Sunday, recipient)` record prevents sending again within 24 hours and provides the “Reminded … ago” state. Each recipient has its own persisted record. If no eligible usher or pastor account resolves, the UI reports that no usher or pastor is on record and sends nothing.
- **Declines:** compare only locations with counted reports in both weeks, sum those locations' counts in each week, then calculate `(previous pooled total - current pooled total) / previous pooled total * 100`. This is not a mean of per-location percentages. The named threshold is `ATTENTION_DECLINE_PCT = 15` in `app/services/analytics/program_config.py`; fewer than five comparable locations yields “Too few locations to compare.”
- **25 October combined bar:** the dev fixture's State series has a combined report as the only report for that occurrence; its scope coverage includes the four covered locations. Those locations are counted as covered, not missing. This was verified against the local development snapshot used for the browser captures.

## Part 2 performance evidence

Instrumentation is opt-in with `DCLM_DASHBOARD_PERF=1`. It correlates request ID, backend call time, SQL statement time/count and render/serialization time. Normal runs leave it disabled. A page request sends the series and bootstrap calls concurrently; the trend, child table and attention panels load afterward with visible loading and error states.

### Query counts and sequential depth

These counts describe the analytics work in the request trace; authentication, permission, and RLS setup SQL are additional database statements in a full HTTP request.

| Call | Analytics queries | Sequential depth | Slowest observed chain / measured work |
|---|---:|---:|---|
| Sunday Worship series | 4 | 4 | Local restored clone: 4 statements, total service time about 726 ms; SQL elapsed-time sum about 202 ms; slowest statement about 70 ms. |
| Dashboard bootstrap | 2 aggregate reads for the rendered summary | 2 | One local browser request trace recorded 9 statements attributed to bootstrap including request-scoped auth/RLS and supporting reads. |
| Review queue | 2, with a third history read when corrections exist | 2–3 | Not separately cold-sampled across all personas. |

The first traced State request had 20 SQL statements across the two dashboard calls including auth/RLS work (11 attributed to series and 9 to bootstrap). The analytics body is batched, but the full request does **not** currently meet a 15-statement State total. We did not add caching; results are not intentionally served stale.

### Database round-trip and page timing

| Environment / measure | Min | Median | Max | Notes |
|---|---:|---:|---:|---|
| Remote Supabase `SELECT 1`, 10 warmed samples | 134.7 ms | 163.5 ms | 191.1 ms | App host to development DB; network RTT, not dashboard time. |
| Local restored clone `SELECT 1`, 10 warmed samples | 0.72 ms | 0.80 ms | 0.89 ms | Disposable local Postgres on port 55432. |
| Local service-only State series | — | 725.6 ms (single sample) | — | Four analytics queries, about 202 ms sum of SQL time. Not a five-sample cold browser result. |
| Local browser State dashboard | — | 1,093 ms (single trace) | — | One earlier shell/render trace; another server trace measured 555 ms total for a dashboard response. These are individual traces, not a min/median/max sample set. |
| Local browser Location dashboard | — | 402 ms (single trace) | — | One screenshot run; not a five-sample cold set. |

The remote network floor is material: at the measured median RTT, a four-round-trip serial chain costs about **654 ms**, before query execution or Python/rendering. At 5–20 ms RTT, the same four-round-trip floor is **20–80 ms**. These are lower-bound calculations, not projected full-page measurements.

The historical State cold load of 14.31 seconds has no matching current five-sample baseline or full browser trace breakdown in this run. We therefore cannot claim a measured before/after improvement or a projected State cold load under three seconds. The requested five cold samples per persona against both remote and local databases, with process restart and already-signed-in browser sessions, remain outstanding. The remote sample set also cannot be completed safely until the remote schema baseline is reconciled and the new migration is applied through the approved deployment path.

Sign-in was not independently timed in this run. The old browser report's approximately eight-second pre-dashboard interval is not split into password verification, token creation, permission loading and redirect timings here; no sign-in optimization is claimed.

## B2b inventory and implementation

The pre-build inventory is in [ANALYTICS_B2B_INVENTORY.md](ANALYTICS_B2B_INVENTORY.md). It inspected the Location model/profile, migration history, location forms/schemas, hierarchy and worker imports, and reporting records. There is no existing expected congregation size field or table. `WorkerAttendanceSubmission.expected_workers_count` is a roster snapshot for workers at a meeting and is not a congregation estimate.

Implemented locally:

- Additive, reversible `location_expected_population` migration with a location, expected value, effective-from date, author, note and timestamp, plus location/effective and GiST path indexes. No estimate values are seeded.
- History is append-only; editing creates a new effective version. Each change writes an audit entry in the same transaction.
- Only the exact State Overseer role at score 5 can manage estimates. The API and UI enforce this; the State page shows the estimate list, form, history and “No estimates yet” empty state.
- Sunday Worship dashboard, child-scope table, Location records and Attendance page show expected attendance and pooled percentage. The calculation is counted population divided by the sum of effective estimates for locations with both an estimate and a counted report; it is not a mean of location percentages and is not capped at 100%. Locations without estimates are excluded from the ratio and counted separately. Pending inclusion follows the dashboard switch.
- The UI label is “Expected Sunday attendance.” No menu entries were added.

The migration's table/index DDL was exercised with equivalent SQL against the disposable local restored clone; the Alembic migration itself was not replayed there because the restored database also has a pre-existing schema with an empty revision ledger. The remote dev database has no `location_expected_population` table. Its `alembic_version` table has zero rows even though 52 public tables already exist. Running `alembic upgrade` there would attempt to replay the application's historical migrations against a populated, unbaselined schema. No remote migration was run. Deployment requires a reviewed baseline reconciliation first.

## Verification and screenshots

- Focused analytics/estimate suite: **29 passed**.
- Full repository suite: **231 passed**, one third-party Python deprecation warning.
- Alembic reports the new revision `e2b4c6d8f013` as the repository head. It was not applied to remote Supabase.
- Browser screenshots from the local restored clone:
  - State dashboard: [b2b-state-dashboard.png](output/playwright/b2b-state-dashboard.png)
  - State expected-attendance management, empty state: [b2b-state-expected-population.png](output/playwright/b2b-state-expected-population.png)
  - Location dashboard: [b2b-location-dashboard.png](output/playwright/b2b-location-dashboard.png)
- Browser port: **8012**. Database: disposable local restored clone `dclm_perf` on **55432**. No remote write was performed.

The screenshots use synthetic/dev data. The Location dashboard surfaces an explicit permission error for the review queue where that persona lacks approval permission; it does not silently present an empty queue. The local clone has no submitted Sunday counts for the current period, so its dashboard correctly shows missing reports rather than zero attendance.

## Not done

- B2b commit is not yet created; this report and implementation are part of that pending checkpoint.
- Remote Alembic baseline reconciliation and remote migration application.
- Five cold browser samples per State, Region, Group and Location persona against both databases, with restart between samples and start time from an authenticated session.
- Comparable five-sample before/after timing table and detailed sign-in timing.
- B3 inventory/pages, worker attendance, split counts, and other deferred slices.
