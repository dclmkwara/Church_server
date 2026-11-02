# Phase 7 — State-Level Backend Pilot Acceptance

This checklist defines the evidence required before the backend is opened to a state-level pilot. It is a test and rollout plan, not proof that any item has passed. Record the environment, date, app revision, database revision, operator, evidence link, and result for every executed item. Use synthetic or approved staging data until the data owner authorizes a pilot.

## 1. Go/No-Go Prerequisites

| Gate | Required evidence | Status |
|---|---|---|
| Runtime dependency split | FastAPI API runtime and FastHTML UI runtime have satisfiable, locked dependencies and independent smoke checks; no incompatible Starlette versions are installed together | `pip check` is clean locally and app import succeeds with explicit CORS; reproducible locks and deployed runtime are not verified |
| Application startup | API starts, imports all routes, serves `/live`, and serves `/ready` with expected status behavior | Local lifespan passed; `/live` and `/ready` both returned 200 with DB connected |
| Migration chain | Fresh database reaches head; upgrade from a production-shaped prior revision succeeds; schema and Alembic metadata agree | Upgrade from configured revision succeeded to `e41a8b9c7d6f`; fresh-database bootstrap/schema parity still needs a disposable PostgreSQL instance |
| Database access boundary | RLS policies cover scoped data tables, fail closed without scope, and pass direct SQL tests using the least-privilege runtime role; policy bypass by ownership/BYPASSRLS is ruled out | Local DB verified at revision `e41a8b9c7d6f`: 98 policies, all public application tables RLS-enabled, no application table without a policy; `church_app_runtime` is NOBYPASSRLS; direct role tests pass. Hosted credentials still need changing. |
| Recovery and backup | Staging backup restore succeeds and rollback procedure is rehearsed against a disposable copy | Not run |
| CORS and proxy | Exact frontend origins work; unlisted origins fail; trusted proxy/client-IP behavior is verified at the actual edge | Not run |
| Rate limits | Shared gateway/provider or shared-store policy verified across every replica; login and reset limits are observed | Current app limiter is process-local |
| Reset delivery | Reset instructions reach the intended user through configured delivery; reset URL and one-time consumption verified | Email delivery is not implemented |
| Secrets and HTTPS | Deployment secret manager, TLS, log redaction, and artifact exclusion checks recorded without exposing values | Not run |
| Observability | Alerts cover app failures, DB pool saturation, scheduler jobs, materialized-view refresh failures, sync errors, and scope-denials | Not run |

Any blocked or failed prerequisite is a no-go for opening the pilot to users. Resolve the runtime and migration blockers before scheduling workflow acceptance.

### Production read-only preflight before migration (2026-11-01)

This was a read-only catalog and migration-precondition check against the configured production database. No DDL/DML or migration was run.

- Server reports PostgreSQL 17.6; `alembic_version` is at `f7b8c9d0e1f2`. The pending local chain is `a07be837513a` → `b18f2c6d9a40` → `c29d3a61e8ab` → `d30e17a4bc52`.
- At this historical preflight, 49 public tables had RLS enabled but no policies; the privileged migration connection bypassed RLS. Migration `e41a8b9c7d6f` later installed 98 policies and the API was switched locally to `church_app_runtime` with `NOBYPASSRLS`.
- All 11 client-ID duplicate checks returned zero groups, including `fellowship_offerings` on a follow-up read-only scan with a longer statement timeout.
- Preflight found zero duplicate active attendance groups, invalid count totals/categories, nonpositive offering amounts, invalid offering statuses, invalid attendance statuses, or invalid event windows.
- One campaign has a reversed collection window. It has no linked events from which the intended hours can be inferred. Its identifier and schedule details were deliberately omitted from this repository document; a data owner must confirm the intended value before the Phase 3 constraints can be applied.
- The `offering_audits` table is not present yet, and no dependent views were found for the three materialized views that the pending report migration replaces.
- Backup/restore was not performed. The user confirmed this database contains seeded test data and will be reset before publication.
- Offline Alembic SQL generation completed for the pending chain. Review exposed a malformed partial-index predicate in the attendance migration; it was corrected to render `WHERE is_deleted = false`. Offline SQL generation now confirms the expected predicate. This does not replace execution against a disposable PostgreSQL database.
- The original wildcard CORS setting was rejected by app validation and was replaced locally with explicit localhost development origins.

### Migration application and verification (2026-11-01)

- The seeded campaign with a reversed collection window was corrected to an overnight window ending 2026-11-01 02:30 UTC, with its campaign end date advanced one day. The user confirmed the data is disposable test data.
- Applied the full pending chain: `a07be837513a` → `b18f2c6d9a40` → `c29d3a61e8ab` → `d30e17a4bc52`.
- Read-only schema verification confirmed the head revision, all eight new check constraints validated, `offering_audits` exists, all three materialized views exist, and the active worker attendance unique index has predicate `(is_deleted = false)`.
- All 11 client-ID duplicate checks had zero groups before migration. Complementary usher count submissions remain independent; no event/location uniqueness index was added.
- `python -m pytest -q`: 86 passed, 1 upstream deprecation warning. `python -m compileall -q app tests` and `python -m pip check` passed.
- With the declared `APScheduler` dependency installed, TestClient lifespan completed; `/live` and `/ready` both returned 200 and readiness confirmed database connectivity.

**Frontend development handoff: READY.** This does not certify state-level pilot or production launch. Local RLS is enforced through 98 policies and the API uses a least-privilege `NOBYPASSRLS` role; hosted deployment credentials still must be changed to that role. Backup/restore rehearsal, fresh-database migration parity, deployed CORS/proxy/rate-limit configuration, external reset delivery, broader role-matrix checks, finance reconciliation, and workflow owner sign-offs remain prelaunch acceptance items.

## 2. Role and Scope Matrix

Use synthetic hierarchy fixtures for at least two nations in two continents, two states in the pilot nation, two regions, multiple groups, and multiple locations. For each role, exercise allowed reads/writes and a deliberate out-of-scope attempt; record the endpoint, actor role, target path, expected result, actual result, and response evidence.

| Role level | Pilot checks |
|---|---|
| 1–3 | Location-bound access; verify a neighboring location is denied |
| 4 | Group paths and locations are visible; adjacent group is denied |
| 5 | Region data is visible; adjacent region is denied |
| 6 | State-level data is visible; another state is denied |
| 7 | Nation-level data is visible; another nation is denied |
| 8 | Data resolves only to nations within the user's home continent; a nation in another continent is denied |
| 9 | Root/global behavior is explicitly approved and tested with a designated non-production account |

Check list, detail, export, aggregate/report, update, approval, delete/restore, announcement, and sync routes separately where the operation exists. Do not infer route safety from a passing dashboard request. Direct RLS checks cover basic fail-closed and scoped visibility; this does not replace the complete endpoint and role matrix.

## 3. Program, Attendance, and Count Workflows

For every scenario, record the input source rows, expected aggregate, returned result, and independent SQL/source-table calculation.

| Scenario | Acceptance evidence |
|---|---|
| Weekly services | Sunday, Monday, and Thursday event instances accept valid dates and types; closed/future event rules behave as approved |
| Crusade | Monthly parent campaign and child events retain their relationship and report at the intended grain |
| Retreats | Easter and December retreat dates, multiple program sessions, and reporting boundaries are correct |
| Home caring fellowship | Sunday fellowship submissions remain distinct from the main service and aggregate only where requested |
| Leaders' attendance | Tuesday leader attendance uses the correct eligibility and event identity; duplicate active attendance is rejected per the approved rule |
| General workers' attendance | Saturday worker attendance is distinct from Tuesday leaders' attendance and from other program events |
| Multiple ushers | Submit at least three different section counts for the same event/location using separate source identifiers. All three remain stored and the total equals their sum. |
| Usher retry | Resubmit one of those same submissions with the same idempotency key. It is recognized as a retry and contributes exactly once. |
| Count correction | Correct or void one source entry with actor, reason, timestamp, and resulting total visible; retain the original audit evidence |
| Combined services | A service combining locations/groups/regions follows the explicit submission scope and does not multiply or omit component counts |

The count test must distinguish a new complementary usher entry from a retry. Never impose uniqueness only on `(event, location)` because that would discard legitimate partial counts.

## 4. Registration and Financial Workflows

| Scenario | Acceptance evidence |
|---|---|
| Newcomer registration | A valid registration is stored once, appears in the correct scoped review/report, and a retry does not create a duplicate |
| Convert registration | Conversion follow-up and status changes retain their actor and timestamps; scoped staff cannot access another location's record |
| Tithe and offering | Decimal values and payment-method totals reconcile to source submissions; pending/rejected records are excluded from approved totals |
| Financial approval | Only authorized reviewers approve within scope; approval, rejection, correction, and deletion/void produce a traceable history |
| Financial retry | Same-key retry does not duplicate money; two legitimate separate submissions remain separate |
| Announcement | Delegated publisher can create/update/publish only within authorized scope; public output excludes drafts/inactive items |

An authorized finance reviewer and the product owner must sign off on the source-to-report reconciliation before live financial entry begins.

## 5. Reports, Sync, and Operations

- Compare dashboard and reports with hand-calculated counts, approved finance, attendance, newcomers, and converts from the fixture dataset.
- Cover timezone boundaries, inclusive end dates, deleted records, hierarchy path changes, pagination caps, and empty-result behavior.
- Exercise offline-client replay against each supported idempotent endpoint: same key/same payload, same key/different payload, partial batch failure, retry, and continuation. Record exactly which routes are supported; do not claim offline guarantees for untested clients or routes.
- Verify the materialized-view refresh schedule and manual refresh coordination, including failure alerting and stale-data behavior.
- Record p50/p95 response latency, DB query plans, rows scanned, pool use, replica/worker count, and total fleet DB connection budget using pilot-sized staging data.
- Verify logs contain correlation identifiers and useful error context but no passwords, tokens, reset secrets, or sensitive financial/member payloads.
- Verify `/live` remains healthy during a DB outage and `/ready` returns HTTP 503; confirm the orchestrator removes an unready instance from traffic.

## 6. Rollout, Reconciliation, and Rollback

1. Deploy only to isolated staging and run the prerequisite gates.
2. Take a backup and prove restore before applying migrations.
3. Apply additive migrations, then deploy the matching application version; record both revisions.
4. Run workflow and scope scenarios using synthetic data, then run a read-only shadow comparison where feasible.
5. Obtain finance, data-owner, and product-owner sign-off before approved pilot submissions begin.
6. Start with one state-level pilot and a named support window. Keep a dated reconciliation of source entries against reports, including separate usher sections.
7. Monitor latency, error rate, failed syncs, idempotency conflicts, scope denials, refresh failures, and DB connection headroom.
8. Stop/rollback on data loss, duplicate financial/count totals, cross-scope access, unexplained report variance, migration failure, or exhausted pool capacity.
9. Use the rehearsed app rollback and backup restore plan. Preserve submitted records and audit evidence; do not use destructive cleanup as a rollback shortcut.

## 7. Backend Acceptance Sign-Off

| Sign-off | Name/date | Evidence |
|---|---|---|
| Technical owner: runtime, migration, backup, monitoring, rollback | Pending | — |
| Security owner: scope matrix, CORS/proxy, secrets, rate limits | Pending | — |
| Finance reviewer: offering/tithe reconciliation and corrections | Pending | — |
| Data owner: count, attendance, registration reconciliation | Pending | — |
| Product owner: church workflows and pilot go/no-go | Pending | — |

Frontend integration and UX review should begin after the backend technical, security, data, and finance gates have passed or the product owner has explicitly accepted each remaining limitation.
