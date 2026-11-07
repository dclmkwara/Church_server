# Slice 2 Close-out and B2b Follow-up Report

**Date:** 7 November 2026  
**Port / database:** `8012`; disposable restored local PostgreSQL clone `church_alembic_restore_proof` on `127.0.0.1:55432`.  
**Scope:** B2b commit, Alembic baseline/runbook, query-count reduction, local signed-in dashboard timings, Location approval message, and bulk expected-attendance CSV. B3, menus, split counts, and worker-attendance slices were not started.

## Checkpoints

| Work | Commit / status |
|---|---|
| Reminder recipient and decline-rule corrections | `4d84f2838e07f12a98a8177eec2129fd1980d426` |
| Earlier dashboard query batching/panels | `20d8898b713aea27907ff8a14f16e7c0a76724e9` |
| B2b versioned expected attendance | `bc5ed15994bf608d4f28b6d161281990c7240c0b` |
| Current follow-up: auth/query reductions, review visibility, CSV bulk flow, runbook and regression fixes | reported in the completion handoff (this report is included in that commit). |

## 1. Alembic baseline and migration proof

The full ordered revision inventory, per-revision remote catalog evidence, focused schema comparison, and operator runbook are in [DEPLOY_MIGRATION_RUNBOOK.md](DEPLOY_MIGRATION_RUNBOOK.md). The comparison is against the saved read-only remote catalog snapshot and model metadata at `20d8898b713aea27907ff8a14f16e7c0a76724e9`.

Key remote snapshot evidence:

- Alembic ledger: one row, `c2e5a8f14b31`.
- `a71c3f9d2b40` location lifecycle columns/index/check: present.
- `c2e5a8f14b31` count-review columns/FKs/indexes: present and recorded in ledger.
- `d4a9c1e7f235` reminder-recipient table/indexes: absent.
- `e2b4c6d8f013` expected-population table/indexes: absent.
- Model/schema comparison found real differences and reflection artifacts; see the runbook. No attempt was made to auto-reconcile them.

**Remote access safety:** a previous failed connector call returned the configured database URL in its driver error before establishing a connection. No remote SQL executed. I have not repeated remote access or run any remote migration, stamp, DDL, DML, or role update. Rotate the exposed development database password before further remote measurements or deployment work. The requested live remote timing and a fresh catalog query are blocked until that is done.

Local Alembic CLI proof (all on disposable local databases):

1. Empty database: `python -m alembic upgrade head` exited 0 and finished at `e2b4c6d8f013`; `location_expected_population.path` is `ltree`; expected indexes exist.
2. Restored-clone proof copy: locally reset the disposable copy's expected-population table and ledger to prepare the prior baseline, then ran `stamp d4a9c1e7f235`, `upgrade e2b4c6d8f013`, `downgrade d4a9c1e7f235`, and `upgrade e2b4c6d8f013`. All four Alembic commands exited 0. The original restored source clone and remote database were not altered by the chain proof.

## 2. SQL statement counts and dashboard path

Instrumentation is opt-in with `DCLM_DASHBOARD_PERF=1`. Local records pair frontend API timing, backend request IDs, SQL counts/times, render and response serialization. Measurements below include auth/RLS setup, not just analytics statements.

| Persona / backend call | Statements | Sequential query chain | Observed SQL work |
|---|---:|---:|---|
| State cold-token initial dashboard (`/dashboard/analytics/sunday-worship/dashboard`) | 7 | 7 including auth | Two RLS context setup statements, one user plus joined roles/score/permissions lookup, 3 weekly series reads, one summary aggregate. |
| State deferred panels (`/dashboard/analytics/sunday-worship/panels`) | 5 | 5 | One RLS setup, 3 weekly series reads, one joined count-review queue read. |
| Location cold-token initial dashboard | 7 | 7 including auth | Same initial path. |
| Location deferred panels | 4 | 4 | One RLS setup, 3 weekly series reads; review queue is skipped because the persona cannot review counts. |

A cold State dashboard therefore used **12 SQL statements total** across its initial and deferred backend calls; this meets the requested maximum of 12. A Location dashboard used 11. The first initial call after an app-process restart is cold for the 30-second token-keyed authorization cache; the deferred call reuses the authorized user snapshot. On a cold token-cache request, the first context statement installs the JWT subject as the narrow user identity needed to load the account under RLS; after identity and role resolution, the second installs the authenticated scope, role and user context. They cannot safely be collapsed before identity is known.

The previous captured State request used 20 SQL statements across two calls. The current 7+5 is an 8-statement reduction. The dashboard bootstrap now shares its location roster with the weekly query; review rows load in one joined query. Permission snapshots are keyed by a one-way token digest, live for 30 seconds, and are evicted on application-mediated RBAC/user changes. Direct out-of-band database permission edits can take up to 30 seconds to appear.

A representative local State trace measured the initial backend call at 583.5 ms and deferred panels at 256.2 ms, with measured SQL elapsed sums of 243.4 ms and 13.7 ms respectively. These are individual traces, not persona medians. Query log time includes Postgres execution and local driver round trips; it does not isolate all Python serialization or browser work.

## 3. Signed-in local page timings

Five samples per persona were captured with the app process restarted before each sample. The browser remained signed in; each measurement starts at dashboard navigation and waits until all visible lazy loading shells resolve. The app and database are local. These are cold app-process samples, not sign-in timings.

| Persona | Five samples (ms) | Min | Median | Max |
|---|---|---:|---:|---:|
| State | 2405, 1902, 2691, 2558, 2340 | 1902 | 2405 | 2691 |
| Region | 2703, 2121, 1869, 2001, 1955 | 1869 | 2001 | 2703 |
| Group | 2099, 2320, 3983, 2128, 1833 | 1833 | 2128 | 3983 |
| Location | 1874, 2044, 2088, 1808, 2166 | 1808 | 2044 | 2166 |

One warm State reload took 653 ms. No comparable before sample series was captured, so this report does not claim a controlled before/after page-time improvement. The previous 14.31-second observation was not captured with this method. The local synthetic dataset is small and does not establish production performance.

A cold State page crosses up to 12 sequential database statement boundaries across the initial and deferred calls. With an app colocated with the database at a 5–20 ms round trip, the network portion alone is about 60–240 ms. Using the observed State median as the local-code/browser baseline gives a rough projected median of **2.46–2.64 seconds**; this is an estimate, not a remote benchmark. The observed max is 2.69 seconds on this local sample.

### Remote samples

Not run. A remote five-sample set and the requested worktree at `20d8898b713aea27907ff8a14f16e7c0a76724e9` were not used to access Supabase because the prior driver error exposed the database credential. After password rotation, the remote comparison can be run read-only using the older commit (which does not need the expected-population table). There is no remote before/after table yet.

### Sign-in

Opt-in sign-in instrumentation is controlled by `DCLM_AUTH_PERF=1` and logs durations only. One local State Overseer sample measured the frontend authentication sequence at 1,249.5 ms and the browser from clicking Sign in through dashboard panels loaded at 4,579 ms. Its measured breakdown was:

| Sign-in step | Time | Evidence |
|---|---:|---|
| Login rate limit | 0.07 ms | API route phase log |
| Login RLS email context | 0.03 ms | API route phase log |
| User row/role/score lookup | 205.25 ms | Timed SQL/auth lookup |
| bcrypt password verification | 864.52 ms | Timed password check; largest sign-in component |
| User lookup plus password check | 1,069.87 ms | API route phase log |
| Authenticated scope setup | 6.84 ms | API route phase log; levels 2 through 5 skip the score-8 continent lookup |
| Access/refresh token creation | 0.96 ms | API route phase log |
| Refresh-token persistence | 17.60 ms | API route phase log |
| Login API total | 1,095.5 ms | API route phase log |
| Frontend token exchange | 1,134.2 ms | Frontend server-to-backend call |
| `/auth/me` profile and permission load | 109.4 ms | Frontend call; includes backend request/serialization |
| Frontend auth service total | 1,243.8 ms | Login token call plus `/auth/me` |
| Cookie/redirect response preparation | 4.2 ms | Frontend route phase log |
| Browser click through complete dashboard | 4,579 ms | One local browser sample; includes the dashboard's initial and deferred rendering after sign-in |

The measured password check is the biggest sign-in component in this sample. It is bcrypt configured for 12 rounds, an intentional password-hardening cost; no change was made. Permission loading is not part of the login password query; it is done by `/auth/me` before the frontend redirects and is then cached for 30 seconds. Browser time after the 1.25-second auth flow includes dashboard work and is not a redirect-only delay. These are single-sample local timings, not a five-sample sign-in study or a comparison with the older ~8-second observation.

## 4. Location review responsibility

A Location Pastor without `counts:review` sees a plain “Reports from your location are approved by your Group Pastor.” note. The review queue is not called for this persona, and there is no permission error or misleading empty queue. Group, Region and State persona note tests remain in place. Fixed a missing HTMX out-of-band target that left attention shells spinning, and added a regression test for the Location note target. The browser check confirmed all panels resolve without console errors.

## 5. Expected-attendance CSV entry

The State Overseer screen now supports paste or file upload, template download, preview and explicit confirmation. Preview lists matched locations, unknown codes, invalid rows, changed values, old/new values and effective dates; preview makes no writes. Apply revalidates under transaction/locks, creates a new version per row and an audit record per change. Unknown/out-of-State codes block the entire apply. Local codes repeat across groups, so the CSV accepts full hierarchy paths for unique matching; an ambiguous local code is rejected with guidance to use the full path.

Tests cover unknown codes, preview read-only behavior, one-transaction apply, append-only history/audit, State Overseer restriction, and unique full-path matching. No expected-attendance values were applied or seeded during the browser preview.

## Screenshots

Captured on port `8012` against the disposable local clone:

- State dashboard after deferred-panel fix: [slice2-state-dashboard-final.png](output/playwright/slice2-state-dashboard-final.png)
- Location Pastor dashboard and approval note: [slice2-location-dashboard-final.png](output/playwright/slice2-location-dashboard-final.png)
- State CSV bulk preview: [slice2-bulk-preview-viewport.png](output/playwright/slice2-bulk-preview-viewport.png)

During browser review, mojibake separators and missing-value glyphs were visible in dashboard text. They were corrected to valid UTF-8 punctuation, and the final State and Location screenshots were captured after restarting the app with the correction.

## Verification and remaining work

- Full test suite after the current behavior fixes and text-encoding cleanup: **249 passed**, one third-party deprecation warning.
- No remote writes were performed.
- Remote catalog re-query, remote timing samples, remote older-commit worktree comparison, sign-in phase instrumentation, and before/after page samples remain open.
- B3 and all explicitly deferred slices remain untouched.
