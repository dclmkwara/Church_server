# Backend Remediation Phase Plan

**Project:** DCLM Church Management backend (`Church_server`)  
**Scope:** Backend correctness, security, data integrity, performance, and operational verification. Frontend integration may proceed from the verified backend development handoff; pilot/production release remains subject to its separate acceptance gates.  
**Status (2026-11-01):** Backend implementation is ready for frontend development. The four pending migrations are applied to the configured seeded database at `d30e17a4bc52`; schema checks, full local tests, application startup, liveness, and database readiness pass. No Phase 8 is planned. State-level pilot/production release acceptance remains a separate gate for least-privilege RLS, deployed CORS/runtime configuration, backup/restore, workflow/finance reconciliation, and operational sign-offs; do not treat frontend handoff as production-launch approval.

## Goal

Close the backend findings from the engineering review without breaking the church's actual collection workflows. Every phase must end with reviewable evidence, regression coverage, migration checks where applicable, and a recorded pass/fail decision before the next risk-bearing rollout step.

## Non-negotiable domain rules

1. **Complementary usher counts remain distinct records.** Multiple ushers may submit counts for the same event and location when each covers a different section/row. Each submitted section contributes to the event/location total. Never deduplicate or impose one-count-per-location/event uniqueness.
2. **Retry idempotency applies only to the same submitted record.** Replaying the same client-generated submission identifier must return the original record; a different identifier represents a separate submission, even when event and location match.
3. **No automatic aggregation may erase provenance.** Reports may sum complementary submissions, but source rows must retain submitter, section/source metadata, event, and audit history. If section labeling is required for reconciliation, add an optional section/source reference without making it unique by event/location.
4. **Financial and attendance semantics must be decided explicitly.** Financial entries may have different reconciliation rules from population counts. Worker attendance is normally one person per event, unlike usher section counts; confirm and enforce that rule separately.
5. **Effective authorization scope is derived from role and home scope.** The role-derived scope must be authoritative across route checks and database policies. A user must be able to access the scope granted by their role, but never a sibling or ancestor scope beyond that grant.

## Phase 0 — Baseline, data contract, and production safety
### Current state

- Not yet completed. A production read-only catalog/migration-precondition audit was performed on 2026-11-01 (see `docs/PHASE7_PILOT_ACCEPTANCE.md`); it did not inspect member/financial records, run DDL/DML, verify a backup/restore, or establish a full code/schema drift report.
- The user confirmed level 8 means continent-wide governance. Nation records already store a continent value, so the implementation resolves the home Nation and derives the allowed Nation paths by matching normalized continent names. Level 8 keeps `org` as a query envelope but must apply the Nation-path filter; level 9 remains global.

### Work

- Record deployed revision, database engine/version, replica/process count, connection limits, current pool settings, current RLS state, and current partition state. Use read-only queries first.
- Inventory deployed tables, constraints, indexes, materialized views, policies, and migration revision; compare them with Alembic history and SQLAlchemy metadata.
- Agree on data contracts for event/program lifecycle, count submissions, complementary count sections, financial entry/review, newcomer/convert lifecycle, attendance, announcement publication, soft deletion, and correction/audit behavior.
- Identify current client contracts used by the data-sourcing apps and admin backend; document existing API response shapes before modifying sync or reporting behavior.
- Create a production-safe backup and a tested restore point before applying schema changes. Do not run reset scripts against production.

### Verification gate

- A signed-off data dictionary and role/scope matrix exists.
- Current DB schema and code drift report is attached.
- Backup restore has been verified in a non-production environment.
- Baseline examples prove two or more different ushers' same-event/same-location submissions are all retained and summed.

## Phase 1 — Authorization and scope foundation
### Current implementation status (local code only)

- Implemented a fresh database user/role load on authenticated requests, rejects deleted, inactive, and unapproved accounts, ignores the JWT scope claim for authorization, and injects a role-derived effective scope.
- Updated role-derived scope handling across counts, attendance, finance, reports, sync, users, approvals, hierarchy navigation, programs, dashboard/statistics/notification services, and legacy CRUD filters. Level 8 resolves its home Nation's continent and limits queries to matching Nation paths; level 9 remains global. Added object-level continent checks and SQL-side filters before pagination.
- Added object-scope checks to announcement and legacy information ID routes; creation now resolves Region IDs and derives the persisted path/name from the hierarchy record.
- Added local tests for role-derived scopes, level-8 nation membership, stale/forged JWT scope, account approval state, and cross-scope announcement access. Fresh local full-suite verification passed 86 tests; `pip check` is clean. PostgreSQL RLS/direct-role evidence is recorded below; complete endpoint integration remains outstanding.
- RLS policies and the non-bypass runtime role are now installed and directly tested on the configured database. Complete endpoint integration tests and route checks for page underfill remain outstanding.

### Work

- Define one effective-scope helper from current user home path plus highest authorized role score; distinguish it from home path and token claims.
- Make scope checks consistently use that effective scope. Validate token scope against current authorization or establish a deliberate revocation/refresh strategy.
- Audit every ID-addressed read, create, update, delete, publish, approve, reject, transfer, and conflict-resolution endpoint for object-level scope checks.
- Fix announcement create/list/detail/update/publish/delete scope handling. Validate the requested region against the user's effective scope and derive the stored path from the authoritative region record.
- Audit other high-sensitivity domains (finance, users/workers, hierarchy, campaign/event assignments, public intake, fellowships, media) for scope and permission checks.
- Add PostgreSQL RLS policies only after effective scope is defined. Scope setting must be transaction-local on the same connection used for protected statements, and policies must fail closed when scope is absent or invalid. Account for service/admin jobs that intentionally bypass end-user scope with explicit database roles or controlled pathways.
- Confirm database application credentials cannot bypass policies through superuser/BYPASSRLS ownership; use least-privilege runtime role and test it.

### Verification gate

- Automated role matrix covers levels 1–9, home scope, allowed descendants, sibling denial, ancestor denial, missing scope, and stale/changed roles.
- Endpoint tests prove cross-scope announcement and other object ID access is denied for reads and writes.
- PostgreSQL integration tests prove RLS prevents access even when a route omits an application filter.
- Tests include direct SQL executed with the actual runtime DB role; policy behavior is not inferred from ORM filters.

## Phase 2 — Sync correctness and idempotency

### Current implementation status (local code only)

- Sync batches use independent per-item commits. Results preserve the existing `synced`/`duplicates`/`errors` summary and status fields, with an `outcome` field that explicitly reports `created`, `duplicate`, or `error`. Database errors are logged and returned without exposing raw DB exception text.
- All seven supported offline resource buckets require client IDs in batch requests. CRUD create paths perform fast duplicate lookup and recover the canonical row after a concurrent retry that violates the per-table unique index. Existing results are scope-checked before their IDs are returned.
- Added an additive migration with duplicate preflight and partial unique indexes for all eleven nullable `client_id` columns (the seven sync buckets plus church-member and the remaining fellowship activity resources). It has not been applied to any database; any pre-existing collisions intentionally stop the migration for human reconciliation.
- Incremental sync retains its existing arrays and adds a bounded per-bucket timestamp+ID cursor with shared `as_of`, continuation metadata, and tombstone delivery. The per-bucket limit is capped at 1,000 (maximum response page is 7,000 rows across seven buckets).
- Population submissions are never collapsed by event/location. Offering and worker-attendance key collisions are reported for review; automatic key-conflict resolution is disabled pending approved financial/attendance policy. Fellowship-member CRUD now accepts the common sync `user_id` signature, but that table currently has no actor column, so it does not yet persist submitter provenance.
- Focused tests passed: 26 passed across sync idempotency, scope helpers, and fresh-auth scope; the fresh full suite passed 86 tests. Migration history shows the new revision at head; migration execution and PostgreSQL concurrency/incremental-cursor integration checks remain outstanding.

### Phase 2 closure status

Implementation is locally complete for the code-level scope above, but Phase 2 is **not formally closed** until the migration preflight is run against a reviewed non-production database, all seven resource buckets pass PostgreSQL retry/concurrency tests, incremental cursor pages are verified under concurrent inserts/updates and timezone boundaries, and a clean full test suite runs in a compatible dependency environment. Phase 0's production baseline and safe database approval still apply.

### Work

- Define sync contract: per-item independent commit with truthful status, or all-or-nothing batch. Prefer an explicit, documented transaction model; do not combine item-level success claims with batch rollback behavior.
- Refactor generic and domain-specific batch endpoints to share predictable validation, transaction, and response behavior.
- Use database-enforced idempotency keys per resource type. Select a key model that avoids collisions across resource types and does not impose event/location uniqueness. If client IDs are intended globally unique, encode resource type in the unique key; otherwise define unique `(resource_type, client_id)`.
- Handle concurrent retries atomically with `INSERT ... ON CONFLICT` or equivalent and return the canonical existing row. Do not rely on check-then-insert alone.
- Ensure repeated IDs within one submitted batch are handled correctly and response statuses distinguish `created`, `duplicate`, and `error`.
- Validate ownership/scope before returning an existing idempotency result so a guessed client ID cannot disclose another scope's object.
- Repair incremental sync: use a stable cursor (timestamp plus ID or monotonic change sequence), include deletions/tombstones, cap total response size, report `has_more`/next cursor, and ensure all buckets share an unambiguous continuation contract.
- Ensure generic sync's fellowship member CRUD signature is explicit rather than special-cased by object identity; use typed adapters or standard service interfaces.
- Never apply deduplication keys to population category values or event/location pairs. Distinct client IDs from different ushers remain independent count rows.

### Verification gate

- Retry of one client ID creates exactly one row and returns the same canonical ID.
- Concurrent retry test creates exactly one row.
- Two or more different usher client IDs for same event/location create separate count rows; aggregate equals their arithmetic sum.
- Same batch with repeated client IDs, an invalid middle item, valid later item, and network retry returns statuses consistent with committed rows.
- Sync tests cover every supported bucket, scope denial, tombstones, pagination/continuation, timestamps at boundaries, and conflict handling.

## Phase 3 — Event, count, attendance, and finance workflows

### Work

- Formalize program and campaign state transitions: draft, scheduled/active, collection window, closed, archived; validate start/end dates and prevent invalid edits after close except controlled correction flows.
- Validate event path and target path on create/update; require event, campaign, program type, location, alpha location, assignment, and submission paths to be consistent.
- Preserve multiple count submissions per event/location. Add optional submission section/usher metadata if needed for reconciliation; do not make it a uniqueness key.
- Make count totals server-derived on every create/update. Prevent clients from setting total or provenance fields. Verify nonnegative category constraints at the database level as well as request validation.
- Decide worker attendance uniqueness (normally event + worker) and enforce it atomically, separate from population count semantics. Validate worker is active/eligible and belongs to the selected location; decide whether absent rows are explicit or inferred from roster.
- Define finance lifecycle and approval/reconciliation policy for offerings/tithes. Preserve `NUMERIC` values end to end, record approver/time/reason, prevent unauthorized edits and silent amount changes, and distinguish entry totals from approved/reconciled totals.
- Validate newcomer/convert record types and state transitions; define duplicate-person detection as a review signal rather than automatic data loss. Protect phone and personal details with access rules.
- Ensure all soft-delete operations write actor/time/reason and all reads/reports consistently filter deleted rows unless explicitly in an audit view.

### Phase 3 implementation status (2026-11-01)

Implemented locally:

- Campaign date ranges and event/campaign collection windows are validated on create and merged-state update; invalid ordering is rejected.
- Campaign lifecycle transitions follow draft → active → closed → archived, with direct archival allowed for cancellation and archived campaigns terminal. Writes against campaign events require active campaign status.
- Worker attendance accepts only present/absent/late/excused, requires an active approved worker, rejects duplicate active worker/event submissions (409), and includes a partial unique index for concurrent requests. Existing duplicate groups stop the migration for review.
- Count provenance is derived from the event and location, so submitted `source_role` and `campaign_code` cannot change classification. Multiple usher/section entries remain independent and additive; no count uniqueness key was introduced.
- Count update only accepts demographic and note changes and recalculates total in the same transaction. Offering update no longer accepts status changes through the generic endpoint.
- Deleted events cannot receive new count, attendance, or financial submissions. A reversible migration adds fail-fast checks for count components/totals, positive offering amounts, attendance statuses, and valid event/campaign windows.
- Configured event/campaign collection windows gate count, attendance, newcomer/convert, and finance writes; campaign writes require active status. Unconfigured windows allow legitimate backfill for active campaigns or standalone events.
- Newcomer/convert types are constrained, and count/record updates cannot rewrite review status, assignment, provenance, or submission-channel metadata through generic update schemas.
- Financial amount/payment/fund corrections require a reason and create before/after audit rows; corrections return entries to pending review. Approve/reject requires a distinct `offerings:review` permission, rejects self-review, records reviewer/time/note, and permits only pending entries. Financial aggregates now count approved, non-deleted entries only.
- Financial soft deletion requires a reason and records an audit event. Audit history is available to scoped readers. Financial mutations clear the in-process analytics cache.
- Financial API amounts are bounded to `NUMERIC(12,2)` and reject values that would be rounded beyond two decimal places.

Not formally closed: the migrations are intentionally unapplied because the safe non-production database and Phase 0 baseline/restore evidence are not available in this workspace. PostgreSQL preflight, migration upgrade/downgrade, attendance/finance concurrency, full workflow/report tests, and finance-role acceptance remain verification gates. Offline SQL rendering is also blocked by the existing placeholder base migration's use of database inspection against Alembic's offline mock connection; it needs separate migration-chain remediation. The approval policy implemented here is a conservative baseline (pastor review permission, no self-review, explicit reason for rejection/correction/deletion); church finance leadership should validate that division of responsibility before deployment. In-process cache invalidation does not invalidate another application replica's cache; the current TTL remains the cross-replica upper bound. Count submission status review remains a separate workflow question because counts currently aggregate while stored with `pending` status and no reviewer endpoint. Phase 2 remains open for the previously listed PostgreSQL and compatible full-suite gates.

### Verification gate

- Workflow tests cover weekly events, monthly crusade with child events, retreat campaigns, combined services, collection windows, assignments, and close/correction behavior.
- Complementary section-count test remains green after all constraints and state rules are introduced.
- Attendance tests prove the selected duplicate rule under concurrent submissions.
- Financial tests cover decimal precision, pending/approved/rejected states, scoped approvals, adjustments, and audit history.
- Data invariants are validated against existing data before constraints are added; migration reports any rows requiring remediation.

## Phase 4 — Reporting and materialized-view correctness

### Work

- Define report grain for each view: daily location totals, monthly financial totals, attendance by event date/status, and hierarchy rollups.
- Fix view grouping and unique indexes so the unique key exactly identifies one row at the declared grain. Include `path` only if it is truly part of the grain; otherwise aggregate paths safely at location-level and use current authoritative hierarchy joins.
- Avoid historical misclassification when hierarchy names/paths change: decide whether reports use event-time hierarchy snapshots or current hierarchy and model it consistently.
- Resolve stale-view semantics and refresh behavior. Avoid an unplanned blocking refresh fallback in live traffic; alert on refresh failure and use a controlled maintenance/background path.
- Standardize date semantics (event date vs submission timestamp), timezone/calendar boundary, deleted-row filtering, approval status inclusion, and financial precision across reports.
- Parameterize and bound all report date ranges, scope, and output size. Make cache keys include every filter and use mutation-aware invalidation or an explicitly accepted freshness window.
- Verify all report routes, including timeseries, by-level, exports, statistics, and dashboard aggregates against hand-calculated fixture data.

### Phase 4 implementation status (2026-11-01)

Implemented locally:

- Added a migration that rebuilds the daily-count, monthly-finance, and worker-attendance materialized views at explicit grains, with unique indexes matching those grains (`day/month/week + location + path`, and attendance status where applicable).
- Financial materialization includes only approved, non-deleted records and preserves PostgreSQL numeric sums rather than casting money to float. Existing numeric response fields remain compatible; monthly summaries add an exact decimal string alongside the existing numeric value.
- Attendance trends use the linked event date rather than record insertion time and exclude soft-deleted attendance/events. Raw count and attendance report queries now consistently exclude soft-deleted rows; finance queries exclude deleted and unapproved records.
- Monthly financial report date filtering includes the full end month and uses the month bucket for the start boundary.
- Raw report paths now honor soft deletion and inclusive end dates for timestamp-backed counts/finance. Growth reports honor requested daily/weekly/monthly buckets and metric; anomaly totals aggregate all count sections by local calendar date/location.

Not formally closed: no PostgreSQL migration, refresh, duplicate-grain, and hand-calculated fixture checks could be run because the safe database gate is not available. Finance materialized views refresh on the existing refresh schedule, so approval/correction changes are not immediately reflected there; direct summary endpoints clear only the current process cache. Multi-replica freshness and full report parity remain Phase 5/7 verification work. The repository's base migration also prevents offline SQL generation pending migration-chain remediation.

### Verification gate

- Fresh PostgreSQL database migrates to head successfully.
- Upgrade from a production-shaped prior revision succeeds with data retained; downgrade/rollback policy is documented and tested where feasible.
- MV creation and concurrent refresh succeed with realistic duplicate/multi-path data.
- Hand-calculated fixtures cover multiple usher count rows, cross-level rollups, soft deletes, financial decimal sums, event-time dates, and hierarchy changes.
- Report responses match direct source-table calculations exactly within declared precision.

## Phase 5 — Query performance and load characterization

### Work

- Capture `EXPLAIN (ANALYZE, BUFFERS)` and endpoint timings using production-like state-level volumes for dashboard bootstrap, scope lists, event search, count/finance/attendance reports, worker lookup, and sync changes.
- Add/adjust composite and partial indexes only from observed plans; review all `ltree` path index operators/casts for index compatibility.
- Replace unbounded or very deep offset pagination where necessary with stable cursor pagination. Enforce maximum list sizes across all routes.
- Replace non-sargable month/year extraction with date ranges. Add a suitable trigram or search design only if title/name search is measured as a material bottleneck.
- Reduce dashboard database round trips and avoid calculating sections not requested. Keep async-session use sequential unless each task has its own independent session.
- Review analytics cache size, key cardinality, invalidation, per-worker behavior, stale-data policy, and lock cleanup. Move to shared cache only if deployment topology and evidence justify it.
- Calculate total possible DB connections across all app replicas/workers, schedulers, migration jobs, and other clients; set safe pool sizes and timeouts.
- Consider partitioning only after table size, retention, query plans, and operational cost justify it. Design PK/FK/idempotency constraints around PostgreSQL partition rules first.

### Phase 5 implementation status (2026-11-01)

Implemented locally:

- Main count, offering, record, attendance, program, and campaign list routes now validate nonnegative offsets and cap page sizes at 500. The program type-by-domain path now applies pagination in SQL rather than fetching the full domain result and slicing in memory.
- Program event year filters use sargable date bounds rather than `EXTRACT(year)` and reject inverted year/month filter ranges.
- Exact offering amount filtering uses `Decimal` rather than binary float.
- Manual and scheduled materialized-view refreshes now share the same PostgreSQL advisory lock. Failed concurrent refreshes return an explicit failure rather than falling back to a blocking refresh; the manual route no longer acquires an unused request session.
- The in-process analytics cache now caps entries at 1,024 using LRU eviction and releases per-key locks after callers finish, while concurrent misses still share one computation.

Not formally closed: no representative database was available for `EXPLAIN (ANALYZE, BUFFERS)`, latency, row-scan, or connection-pool measurements. Many lower-volume routes still have uncapped or offset-based pagination, substring searches still need workload measurement, and composite indexes/cursor pagination must follow actual query plans. Default SQLAlchemy capacity is 15 connections per app process (pool 5 + overflow 10); deployment replica/process counts were not present in the repo, so fleet-wide connection capacity cannot be computed. Do not claim measured speed improvement from these code changes alone.

### Verification gate

- Before/after benchmark report identifies dataset size, hardware/database plan, query plans, p50/p95 latency, rows scanned, and connection use.
- Performance changes preserve report outputs and role scopes under regression tests.
- Pool/concurrency test remains within configured database connection budget.
- No performance claim is accepted based solely on async code, an index existing, or a passing unit test.

## Phase 6 — Security, operations, and documentation alignment — CLOSED LOCALLY (2026-11-01)

### Work

- Review login rate limiting for multiple replicas and trusted proxy behavior; move to shared enforcement or provider controls where necessary.
- Review bcrypt 72-byte truncation policy and password validation. Ensure passwords differing only after byte 72 cannot be treated as equivalent without explicit user-facing limits and migration handling.
- Audit JWT revocation and role/scope update behavior, refresh-token rotation concurrency, session/cache invalidation, and inactive/unapproved user response semantics.
- Replace production wildcard CORS defaults with an explicit fail-closed configuration. Verify secrets and `.env` are not packaged into deploy artifacts, logs, screenshots, or repository history.
- Pin reproducible compatible API/FastHTML dependency sets and smoke-test the deployed runtime, even though the current local `pip check` and app import now pass with explicit CORS configuration.
- Add operational health/readiness separation, structured logs, database/scheduler/refresh alerts, and audit events for sensitive records and approvals.
- Align README, security, data governance, schema, architecture, scaling, and comprehensive analysis docs with verified deployed behavior. Mark planned items distinctly; remove unsupported claims for RLS, partitions, offline guarantees, and capacity.
- Add Alembic CI checks for fresh install, upgrade path, metadata drift, and migration SQL review. Make release checks reproducible.

### Phase 6 implementation status (2026-11-01)

Implemented locally:

- Password hashing rejects inputs longer than bcrypt's 72 UTF-8-byte limit instead of silently truncating them. Account create/self-registration/update and password-reset schemas validate the same byte limit; verification rejects oversized candidates. Existing bcrypt hashes created from truncated longer passwords remain ambiguous and require a reset to remove that ambiguity.
- Refresh-token rotation atomically claims a still-valid, unrevoked JTI before issuing its successor, and verifies that the JTI belongs to the token subject. Competing refresh requests cannot both rotate the same stored token.
- Protected API authentication rejects refresh-type JWTs, closing token-type confusion where a 30-day refresh token could otherwise be presented as a bearer access token. A focused regression test covers rejection before user lookup.
- Password resets and administrator password changes revoke that user's outstanding refresh tokens and evict the local identity cache. Password-reset request/confirmation endpoints have process-local IP throttles.
- Password-reset tokens are now atomically consumed once, preventing concurrent reuse of one reset token.
- Auto-created inactive accounts now receive a random temporary password instead of a password derived from the worker's first name.
- CORS no longer defaults to wildcard origins. Unset configuration denies cross-origin browser access; deployment documentation requires exact frontend origins. Allowed methods and headers are explicit.
- Added process liveness (`/live`) and database readiness (`/ready`, HTTP 503 on database failure) while retaining `/health` for compatibility.
- The in-process login limiter caps remembered client buckets at 10,000 using LRU eviction. It remains process-local, so the 5/minute login limit multiplies across workers/replicas and is not a fleet-wide brute-force control.
- Updated the deployment and security guides to state explicit CORS configuration, health/readiness behavior, token/password limits, and known security gaps. Corrected README claims about RLS, partitioning, offline behavior, performance, and audit coverage; marked the older comprehensive analysis as historical and superseded.
- Corrected authentication, data-governance, schema-reference, and architecture docs where they overstated token claims, universal route scope, RLS, audit/soft-delete coverage, idempotency, or offline guarantees. The count policy explicitly preserves separate usher partial submissions as additive records.

Phase 6 is closed for the local code and documentation remediation requested. This is not production security approval. The following deployment and verification gaps are carried into Phase 7 as explicit go/no-go prerequisites: shared edge/provider or Redis login enforcement before multi-replica deployment; trusted proxy verification; access-token revocation/logout-all policy; an operational password-reset delivery channel and frontend reset URL; secure delivery and forced change of random temporary passwords; scheduler/materialized-view alerts and sensitive financial audit evidence; reproducible dependency locks and deployed-runtime smoke tests; and Alembic baseline/fresh-database validation. The current configured wildcard CORS value is rejected; the local app imports and mounts when an explicit test origin is supplied. No `.env` values are recorded in this plan.

Fresh local verification: `python -m pytest -q` passed 86 tests with one upstream deprecation warning; `python -m compileall -q app tests`, `pip check`, and `git diff --check` passed. `import app.main` succeeds and mounts 40 routes when given an explicit local CORS origin; the current wildcard origin is correctly rejected. Offline Alembic SQL generation passed after correcting the attendance partial-index predicate, but no migration was applied. Database-backed concurrent behavior, deployed CORS/proxy behavior, and backup/restore remain unverified. RLS is verified on the configured database; hosted role configuration remains outstanding.

### Phase 6 local closure evidence

- Local compilation, the full 86-test suite, app startup, and configured-database RLS/runtime-role verification pass; deployed configuration and operational verification remain outstanding.
- Multi-replica limitations and all remaining operational requirements are documented as Phase 7 go/no-go items.
- Documentation claims were corrected against inspected code where evidence was available. Database and deployment behavior remain unverified.
- No `.env` values were read or emitted.

## Phase 7 — Staged backend rollout and acceptance

### Work

- Deploy additive schema changes first, then compatible application changes, then enforce constraints/RLS after data validation and backfill.
- Run a shadow/observation period for new scope and report logic where possible; compare old and new aggregates without changing collection behavior.
- Roll out to one state-level pilot and exercise normal Sunday/weekday services, Tuesday leadership attendance, Saturday workers, home fellowship, crusade with child programs, and retreat workflows.
- Reconcile real multi-usher section counts against location totals and validate offering/tithe totals with authorized finance reviewers.
- Monitor latency, error rates, failed syncs, idempotency conflicts, migration/refresh status, database connections, and scope-denial events.
- Define rollback triggers and rollback actions for app and schema versions. Preserve source data; do not run destructive cleanup as part of rollout.

### Phase 7 implementation status (2026-11-01)

**Frontend development handoff: READY.** The user confirmed the database rows are seeded test data and authorized migration/data correction. The malformed test campaign was corrected to an overnight window ending 2026-11-01 02:30 UTC. The pending migrations were applied through `e41a8b9c7d6f`; the database has RLS enabled on all public application tables and 98 policies, with no RLS-enabled application table missing a policy. API connections now use the dedicated `church_app_runtime` role (`NOSUPERUSER`, `NOBYPASSRLS`, no database/role creation privileges); the privileged migration URL remains separate in local `SYNC_DATABASE_URL`. Direct runtime-role tests verified fail-closed unscoped reads, scoped reads after commits, authenticated self/role lookup, and shared lookup access. `python -m pytest -q` passed 86 tests; `pip check` is clean. The app lifespan completed, `/live` returned 200, and `/ready` returned 200 with the restricted DB connection. These checks support frontend integration.

State-level pilot/production release acceptance remains separate: hosted runtime credentials must be changed to the non-bypass role, and deployed origin, backup/restore, broader permission-matrix tests, finance/source reconciliation, and church-owner workflow sign-offs remain before launch. This release checklist does not hold up local frontend development.

### Final backend acceptance gate

- All prior phase gates pass.
- No unresolved critical/high findings remain.
- Pilot data reconciles with source submissions, including separate usher sections.
- Migration, backup restore, sync retry, permission matrix, RLS, and report verification evidence is attached.
- Product owner signs off on financial workflow and count aggregation semantics.
- Only after this gate should frontend integration and UX review begin. Phase 6's local closure does not waive earlier phase gates or Phase 7 production prerequisites.

## Finding-to-phase coverage

| Review finding | Planned phase |
|---|---|
| Announcement ID routes lack path enforcement | 1 |
| RLS documented but policies absent; authority scope unclear | 0–1 |
| Batch rollback/status and idempotency races | 2 |
| Incremental sync cursor/tombstone/continuation concerns | 2 |
| Complementary ushers' counts must not be deduplicated | All phases; explicit gate in 0, 2, 3, 4, 7 |
| Count total/client-controlled fields and workflow boundaries | 3 |
| Attendance duplication and missing DB rule | 3 |
| Event scope/path validation and lifecycle | 3 |
| Financial approval, decimal precision, correction trail | 3–4 |
| Soft-delete/date filters and inconsistent report semantics | 3–4 |
| Materialized-view grouping/index mismatch | 4 |
| Historical hierarchy/report attribution | 4 |
| Dashboard/report latency, indexing, pagination, cache, pool | 5 |
| Password, JWT/cache, rate limiting, CORS and operations | 6 |
| Unsupported or stale implementation claims in docs | 6 |
| Production verification and safe rollout | 0, 7 |

## Execution discipline

- Treat every phase as implementation plus evidence, not as a checklist marked done after code changes.
- Keep migrations additive and reversible where possible; inspect deployed schema before assuming migration state.
- Do not edit production data or apply production migrations without a reviewed backup, validated migration, and explicit deployment authorization.
- Do not infer correctness from route presence, compilation, or unit tests alone. Use PostgreSQL integration and deployed-state evidence for database and performance claims.
- Preserve frontend compatibility during backend changes through versioned/compatible responses or an explicit coordinated migration when a contract must change.
