# Church Admin Frontend Remediation Plan

**Project:** Church_server administrative frontend  
**Scope:** Live frontend correctness, role and scope fit, reporting accuracy, performance at state scale, and visual polish. This plan covers `app/frontend/dclm_admin`; it does not include the separately hosted public church website or data-sourcing applications.  
**Status:** Phases 0–4 are closed for local implementation and automated verification. Phase 5 remains open for UI pagination, freshness, and representative-volume profiling. Phase 6 remains open: local authenticated report evidence is recorded, while the wider role/workflow and cross-scope acceptance matrix is incomplete. Phase 7 local visual and handoff review is in progress; deployment and state-level sign-off remain outstanding.
**Relationship to backend plan:** This is the frontend follow-through for `BACKEND_REMEDIATION_PHASE_PLAN.md`. Backend authorization and RLS remain authoritative; frontend controls are not security boundaries.

## Product and data rules

1. **Levels 3–5 need scoped oversight.** Pastors need usable statistics, reports, trends, and records inside their authorized region/group/location. An administrator at the same organizational level needs the technical actions explicitly granted to that role. Score alone must not stand in for permission.
2. **Scope is inherited from the backend identity.** The frontend may offer drill-down only to descendants of the user's effective scope. It must never widen scope based on a query parameter or browser-controlled role selector.
3. **Usher submissions are additive source records.** Multiple ushers can submit separate sections for the same event and location. Keep each submission and submitter traceable; aggregate only at event + location + service date (and any other agreed grouping dimensions). Do not deduplicate complementary rows.
4. **Retry safety is per submission.** Generate and retain a stable client ID for retrying the same submission. A new usher section gets a different ID and remains a distinct record.
5. **Finance is approval-aware.** Pending, approved, rejected, corrected, and reversed entries must be distinguishable. Pastor summaries must not present pending figures as approved totals.
6. **Every displayed statistic states its meaning.** Show date range, scope, aggregation basis, approval status where applicable, and last refresh time. Do not call an all-time value “this month” or an individual section “latest attendance.”
7. **Credentials stay out of the repository.** Use seeded accounts only in local/staging verification. Do not put passwords, access tokens, or session cookies in plans, screenshots, commits, logs, or browser artifacts. Rotate shared seeded credentials before any real-user launch and use unique test passwords in any long-lived environment.

8. **Separate intake from oversight.** The Level 1-2 app is the normal source-data entry channel. This console reads and analyzes that data and keeps scoped review and technical administration; any correction must be auditable.

## Phase overview

| Phase | Name | Gate | Status |
|---|---|---|---|
| 0 | Contract and role baseline | Approved role/permission/scope matrix and field semantics | **Closed locally**; matrix and backend seed/API contracts documented |
| 1 | Repair live service adapters | Critical create, review, and delete actions call the correct API and are covered by focused tests | **Closed locally**; mapped adapter and source-entry boundary regression tests pass |
| 2 | Counts, usher sections, and analytics | Level 1-2 source app captures additive usher rows; admin console reports the combined scoped totals | **Closed locally**; common aggregation, event-grain view migration, and additive fixtures pass; live source rows are empty |
| 3 | Finance review and reconciliation | Finance statuses and month/year totals match approved backend data | **Closed locally**; permissioned review, reasoned correction/reversal, status-aware totals, audit history, and paginated listing are covered; non-empty real-data reconciliation remains Phase 6 |
| 4 | Pastor reports and hierarchy navigation | Levels 3-5 see permitted scoped reports and safe descendant drill-down | **Closed locally**; permission persistence, scoped identity, selected date window, export parameters, and adapter tests pass; live accounts remain Phase 6 |
| 5 | State-scale lists and cache freshness | No silent truncation; mutations refresh the affected data | In progress; backend adapters now exhaust offset pages and preserve list failures; UI paging, visible freshness, and representative-volume profiling remain |
| 6 | End-to-end role and workflow verification | Role matrix and representative live workflows pass in staging | In progress; local automated coverage passes; authenticated staging workflows are not yet verified |
| 7 | Visual refinement and launch handoff | Visual changes support dense operations and all release evidence is recorded | Not started |

Phases 1–5 may be developed in parallel only where contracts are stable; verification gates are sequential. Phase 7 follows functional acceptance so polish does not obscure broken flows.

## Implementation and verification log

### Intake boundary and count overview slice (2026-11-02)

- Product boundary confirmed: the dedicated Level 1-2 app is the routine source-data intake channel. This console is for scoped oversight, reporting, and technical administration.
- Removed source-entry actions and forms for counts, finances, newcomer/convert intake, worker/member registration, worker attendance, and fellowship member/activity records. Corresponding direct POST endpoints return 403 before any service call. Read-only views and technical admin/review workflows remain.
- Multi-usher count summaries combine source rows by event + event date + location, while individual rows remain traceable. A mobile overview failure exposed during fixture testing was fixed.
- Validation: `python -m compileall -q app/frontend/dclm_admin tests` passed; `python -m pytest -q` -> 93 passed, 1 upstream deprecation warning. Twelve source POST route handlers were invoked directly and returned 403; rendered page routes show no intake actions/forms and include the Level 1-2 app notice.
- No source records were submitted. Authenticated browser evidence predates this edit; the existing local server process has not been restarted/reloaded, so the changed UI still needs a browser pass after reload.

### Scoped reports for levels 3-5 (2026-11-02)

- Added the Reports module for levels 3-5 and removed the level-6 page gate. The frontend now permits scoped oversight users to reach the report hub; backend `reports:read` permission checks remain authoritative for each report request.
- Backend 403 responses from report data methods now propagate to the route and render an explicit access-restricted state rather than an empty report that could be mistaken for zero activity.
- Validation: focused report/intake suite -> 10 passed; full suite -> 96 passed, 1 upstream deprecation warning; `compileall` passed. Tests cover level 3/4/5 report-page access, report permission denial, and level 2 refresh/export denials.
- Live authenticated role and scope checks remain open. The local server has not been reloaded, and no browser claim is made for this change.

### Local closure of phases 0, 1, 2, and 4 (2026-11-02)

- **Phase 0:** Added `docs/FRONTEND_ROUTE_API_PERMISSION_MATRIX.md`, covering role family, scope, permissions, API families, source-intake ownership, count grouping, finance date/status semantics, and verification boundaries. It distinguishes seed roles from current live assignments.
- **Phase 1:** Corrected misleading live service adapter names/targets across workflow, system/RBAC, and reports; source entry POST routes remain blocked before service calls. Added/retained focused route and adapter tests for matching APIs, forbidden intake paths, permission denial, and error behavior.
- **Phase 2:** One shared `(event_id, service_date, location_id)` aggregation helper powers dashboard/count/report summaries while preserving source rows and usher section/submitter provenance. Applied event-grain migration `fa12c0e7d8b9`, then corrective migrations `b73c1d9e5f20` and `c84d2f7a6b91` to expose compatible `ltree` paths on all scoped report materialized views. Final DB revision is `c84d2f7a6b91`; event grain/index and view source-row counts were checked. Current configured database contains 0 active count, offering, and worker-attendance rows, so live additive reconciliation is unproven; fixture tests prove complementary sections sum without deduplication.
- **Phase 4:** API identity returns the union of assigned permissions and the frontend retains them in an HttpOnly session cookie. Report access/navigation and refresh use explicit permissions. Browser query parameters cannot override authenticated scope path, kind, label, or score. A single selected date window flows through summary, finance, attendance, trend, breakdown, growth, anomaly, and export APIs; finance now filters approved entries by exact dates before month grouping. Removed an unfiltered all-operational-datasets export from the filtered report hub.
- Validation: `python -m compileall -q app tests` passed; focused adapter suite -> 18 passed; full `python -m pytest -q` -> 105 passed, one upstream `asyncio.iscoroutinefunction` deprecation warning. Live DB verification: `alembic current` -> `c84d2f7a6b91`; all three report view `path` columns are `ltree`; 98 RLS policies remain present; no duplicate count grains and the view `record_count` equals active source rows (both zero). `git diff --check` found no whitespace errors (Git reports existing LF-to-CRLF normalization warnings).
- Browser verification on a separate full local app using the seeded location pastor: login succeeded; report date controls rendered; summary, finance, attendance, timeseries, and by-level empty states rendered; October 1–31 was applied, persisted when switching tabs, and the CSV export returned 200 with matching dates and the authenticated location scope. Initial DB type and date-bound defects were caught and corrected with live reruns. Same-level location admin login rendered the expected `reports:read` denial and had no report data. Growth/anomaly browser tabs and broader group/region account workflows remain to be exercised in Phase 6. No source records were submitted.
- These phases are closed for local implementation, automated tests, database migration checks, and the limited authenticated local browser paths listed above. They do not close Phase 6: group/region accounts, descendant/sibling denial, remaining report tabs/export/date-submit browser checks, actual API-vs-UI range reconciliation, and non-empty additive source data remain required there.

## Phase 0 - Contract and role baseline

### Work

- Maintain the agreed ownership boundary: levels 1-2 submit source records in their dedicated app; levels 3-5 use this console for scoped oversight. Pastors need reporting and review visibility; administrators need only technical actions granted to their role.
- Record route/API/permission/payload/response mappings for counts, finance, newcomers/converts, worker/member attendance and records, events/assignments, user administration, fellowship, reports, announcements, media, and public-intake review.
- Confirm home/effective scopes, descendants, multiple-role behavior, pastor/admin capability differences, and backend enforcement. Frontend query parameters and hidden controls are not security boundaries.
- Confirm count grouping and finance date/status semantics. Keep levels 6+ governance UI outside the current level 3-5 launch focus unless the role matrix explicitly requires it.

### Acceptance gate

- **Closed locally (2026-11-02):** route/API and role/scope/permission matrices are documented and checked against role seeds and route permission dependencies.
- **Closed locally:** source app versus oversight console is reflected in UI and direct mutation routes, with route regression tests.
- **Closed locally:** count and finance semantics are documented; role test identities are listed by role/level only, with no secrets.
- **Still required in Phase 6:** verify live role assignments and current effective scope against authenticated test accounts.

## Phase 1 - Repair live service adapters and enforce the app boundary

### Work

- Replace copy/paste method reassignments with explicit, correctly named adapters and signatures for the administrative actions retained in this console.
- Keep scoped app-user/account management, worker approval and lifecycle review, event/program/assignment configuration, announcement management, media management, and other technical administration mapped to the matching backend endpoints.
- Keep operational source intake in the dedicated Level 1-2 app. This console must not create service counts, finance submissions, newcomer/convert registrations, worker/member registrations, worker attendance, or fellowship activity entries.
- Remove source-entry buttons/forms from the admin UI and make every corresponding direct POST return 403 before invoking any service. Keep read-only directories, details, summaries, and review workflows available.
- For retained mutations, invalidate only the relevant request and TTL cache entries after success. Catch expected backend and validation failures, retain values where practical, and show accessible errors.

### Acceptance gate

- **Closed locally (2026-11-02):** retained routes map to intended service operations; focused adapters, source POST blocks, error/permission paths, and distinct media/RBAC operations are covered by passing tests.
- **Still required in Phase 6:** exercise retained actions with live authenticated pastor/admin accounts and confirm backend success/failure UI on a responsive local/staging stack.

## Phase 2 - Multi-usher count reporting and additive statistics

### Work

- Treat the Level 1-2 app/API as the source of count rows, including one distinct submission per usher section, authenticated submitter, assignment/section, source channel, and retry idempotency key.
- In this console, preserve individual source rows in detail and combine only for summaries at event + service date + location. Never deduplicate complementary usher submissions.
- Show combined totals, section/submission counts, and available section/assignment provenance on desktop and mobile. Clearly distinguish a combined service total from one submission.
- Define latest, monthly, average, and locations-reporting measures against explicit periods and agreed grouping keys. Reuse the same grouping in dashboards and reports.
- Keep count pages read-only. Verify retry idempotency through the source-app/backend integration: same client ID is safe, while a distinct section remains a separate row.

### Acceptance gate

- **Closed locally (2026-11-02):** fixture tests prove complementary usher source rows sum at event/date/location and remain traceable. Shared grouping is wired into count workspace, dashboard, reports, and the migrated materialized view.
- **Closed locally:** source-app/backend idempotency behavior is covered by backend sync/count tests from the backend remediation work; the admin console has no operational count form or writable source POST route.
- **Still required in Phase 6:** live source-app retry integration and reconciliation against non-empty authorized data. Current database has zero active count rows; no data was fabricated for verification.

## Phase 3 — Finance review and reconciliation

### Work

- Expose pending/approved/rejected/corrected/reversed states in finance rows and detail screens; add review actions only for roles with the relevant backend permission.
- Add period filters and correct month-to-date/year-to-date calculations using the agreed financial date basis. Display approved totals separately from pending totals and show transaction counts for both.
- Preserve event, location, fund type, payment method, submitter, reviewer, timestamps, and notes in the detail view. Avoid treating entry date and event date as interchangeable.
- Add review queues and correction/audit trails using existing backend operations. If a required review/correction API is absent, record that as an explicit backend dependency before building a UI affordance.
- Invalidate finance list, summary, report, and dashboard caches after review or correction.

### Acceptance gate

- **Closed locally (2026-11-02):** approved MTD/YTD totals use the backend event-date field and exclude pending, rejected, and reversed rows. Pending amounts and counts are separate. Regression fixtures cover status and date periods.
- **Closed locally:** review, correction, and reversal use scoped backend permissions and audited operations. Review blocks self-review; rejection, correction, and reversal require meaningful reasons; reversed entries are terminal. Successful UI actions re-fetch the drawer, list, and summary. Drawer history and actions are permission-gated, with rendered output covered by regression tests.
- **Not claimed:** the live database currently has no finance rows, so reconciliation against non-empty approved/pending/rejected/reversed data remains a Phase 6 staging gate. No finance records were created or changed during this phase.

## Phase 4 — Pastor reports, access model, and hierarchy navigation

### Work

- Make report navigation and route access permission-based, not a hard-coded level-6 threshold. Enable the agreed report views for levels 3–5 within each user's effective backend scope.
- Fix report service bindings so breakdown rows, growth series, finance summaries, attendance summaries, anomalies, and exports each call and normalize the correct API response.
- Add scoped hierarchy drill-down for permitted descendants. Backend scope remains authoritative for every request; a user cannot select ancestors or siblings outside their effective grant.
- Differentiate pastor and administrator capabilities through backend permissions, not level score alone. Hide unavailable actions and preserve backend 403 behavior if a request is forged.
- Provide clear scope breadcrumbs and selected period on every report. Show comparisons only where the underlying data window and grouping make the comparison meaningful.
- Add useful Level 3–5 overview reports: attendance/population trends, locations reporting, newcomer/convert follow-up, worker/leader attendance, program turnout, and approved finance totals. Keep sensitive person-level and finance detail permissioned.

### Acceptance gate

- **Closed locally (2026-11-02):** authenticated UI permissions survive session reconstruction; permission gates and backend 403 behavior are tested; query scope metadata cannot override identity path; report adapter shapes and date parameters are tested.
- **Closed locally:** all report exports receive the selected scope/date window; report caches vary by scope and date range.
- **Still required in Phase 6:** actual Level 3–5 pastor account access, same-level admin differences, descendant/sibling/ancestor backend behavior, and live API/export row reconciliation. Local API process was unresponsive during this run, preventing browser sign-in verification.

## Phase 5 — State-scale lists, performance, and freshness

### Work

- Add explicit pagination (or cursor pagination where supported) to workers, users, counts, offerings, records, attendance, programs, locations, announcements, fellowships, and media. Return total/next-page metadata and expose it in the UI.
- Apply search, status, date, location, and event filters server-side when endpoints support them; avoid loading large state-wide tables into memory for local filtering.
- Review frontend cache keys for effective scope and relevant filters. In particular, scope-sensitive announcement results must not be reused across different users/scopes in the shared process cache.
- Keep caches bounded and short-lived for operational data. Invalidate after writes/reviews and add a visible “updated at” indicator. Do not describe cached content as real-time.
- Profile the actual page load and backend request pattern at representative state data volume. Optimize N+1 location/event/submitter lookups with batched endpoints or joined responses.
- Ensure page loading is section-based where useful, but show retryable error states instead of turning backend failures into empty lists that look like “no data.”

### Acceptance gate

- Data above one page is reachable through the UI, with no silent truncation or duplicate/missing rows when moving between pages.
- Scope-specific cache isolation is tested across two users with different effective scopes.
- Representative load checks record dataset size, request count, response size, and p50/p95 page/endpoint timings. Claims of performance improvement require before/after evidence.
- A backend failure is visibly different from a valid empty result.

## Phase 6 — Authenticated end-to-end workflow verification

### Progress update (2026-11-02)

- Phase 6 has started while Phase 5's implementation gap remains explicitly open, per the user's direction. Verification completion still follows the acceptance gates below.
- Local automated baseline: `python -m pytest -q` passed 118 tests (one upstream deprecation warning). Existing coverage includes current-role/scope recomputation, stale/unapproved/refresh-token rejection, ancestor/sibling/descendant scope behavior, frontend permission persistence, source-entry denial in the oversight console, additive multi-usher aggregation, finance status/correction/reversal rules, adapter-to-backend operation mapping, cache isolation, and report permission handling. See `tests/test_auth_scope_freshness.py`, `tests/test_scope_helpers.py`, `tests/test_frontend_live_service_adapters.py`, `tests/test_phase3_workflow_validation.py`, and `tests/test_announcement_scope.py`.
- On 2026-11-02 a dedicated loopback app instance was started on port 8012 with the normal scheduler disabled. `/health`, `/ready`, and `/login` returned 200. A seeded Location Pastor completed browser login; `/api/v1/auth/me` returned `reports:read`, `reports:refresh`, and `statistics:read`; the Reports navigation and location-scoped summary empty state rendered. No source records were submitted.
- Runtime role checks on 2026-11-02 used seeded accounts with credentials excluded from the report: Location, Group, and Region Admin received 403 for report summary and refresh; Group and Region Pastors received 200 for summary; State Admin received 200 for summary and 403 for refresh; State Overseer received 200 for both; Location Worker and House Fellowship Leader received 403 for both. All authenticated `/auth/me` responses matched the tested role. Location Pastor also received 200 for summary/financial/attendance, 403 for a sibling-location scope, 200 for CSV export, and 200 for refresh after the refresh fix below. Logout returned 204 and reuse of its refresh token returned 401.
- Report refresh initially failed for Group/Region Pastors because the restricted runtime DB role did not own the materialized views. Added and applied `f12a9c6e4d31`, which exposes only a fixed three-view `SECURITY DEFINER` refresh function to `church_app_runtime`; the function is owned by the privileged migration role and executable privilege is revoked from PUBLIC. The runtime refresh call then returned 200 and all three views reported `refreshed`. `refresh_materialized_views(raise_on_error=True)` also succeeded directly through the runtime DB connection.
- Live browser report-tab verification found Growth and Anomalies failing with 500 because the frontend API adapter did not forward selected start/end dates. Updated `communication/api_client.py` to pass those dates through. After reload, all eight report tabs returned successful content requests. A Location Pastor opened 14 authenticated read pages (dashboard, programs, counts, finance, newcomers, attendance, workers, members, app users, fellowship, communication, media, inbox, reports); all main document responses were 200 with content and no 5xx responses. At 390×844 the report page had document/body widths of 390px and keyboard Tab moved focus to a link. The post-fix browser session recorded no console errors.
- Final automated verification after these changes: `python -m compileall -q app tests` passed; `python -m pytest -q` passed 118 tests with one upstream `asyncio.iscoroutinefunction` deprecation warning; `python -m alembic current` returned `f12a9c6e4d31 (head)`.
- **Phase 6 remains open:** authenticated live create/review/update workflows (event assignments, additive multi-usher source submissions and retry, newcomer/convert follow-up, worker/user administration, attendance, offering review/correction/reversal, fellowship attendance, announcement/media publishing), non-empty aggregate/export reconciliation, full hierarchy scope drill-down, and separate level 1–2 source-app offline/retry integration have not been exercised end to end. Read-only page availability and automated workflow tests do not satisfy the plan's staging workflow gate. No church source records were fabricated or submitted during this pass.

### Test roles

Use the already seeded role accounts supplied by the user, identified in test notes by role and level only: Location Pastor/Admin (3), Group Pastor/Admin (4), Region Pastor/Admin (5), State Overseer/Admin (6), plus representative lower-level identities (1–2) for access-denial and shared workflow checks. Do not write their credentials to this plan, repository, screenshots, test reports, or shell history.

### Workflow coverage

- Login/logout/session refresh and role/scope display.
- Dashboard metrics, filters/drill-down, empty/error/stale state, and scope boundaries.
- Event/campaign setup, event assignment create/approve/reject, usher count submission, multi-usher additive totals, and retry/idempotency.
- Newcomer/convert registration and follow-up status changes.
- Worker registration/review; worker and leader attendance workflows; app-user approval, role assignment, deactivate/reactivate.
- Offering/tithe submission, review, correction and report reconciliation.
- Fellowship list/detail, member management, Sunday home-care attendance/summaries, and related workflows.
- Announcement draft/edit/publish/archive; gallery and media item create/delete.
- Reports, filters, exports, permissions, and cross-scope denials.
- Desktop and narrow mobile layouts, keyboard navigation, visible focus, form labels/errors, and screen-reader names for key actions.

### Acceptance gate

- Each workflow is exercised using authenticated staging accounts at the relevant pastor and administrator levels, not mock identities.
- Allowed and denied actions are verified against backend responses and visible frontend state.
- No unexplained console errors, failed HTMX requests, or mismatched aggregate values remain in the exercised flows.
- Evidence records environment, account role/level (never credentials), route, outcome, and date. Production database remains untouched.

## Phase 7 — Visual refinement and launch handoff

### Work

- Preserve the existing restrained admin shell and reusable components; do not replace dense operational views with marketing-style layouts.
- Improve information hierarchy: date/scope context, critical reporting gaps, trend/exception panels, and action queues should take precedence over repeated generic statistic cards.
- Refine chart/table consistency, table density, filters, empty/error/loading states, mobile cards, and typography. Maintain clear number units and accessible contrast.
- Add confirmation and success feedback that names the affected event, location, section, or finance status. Avoid generic “saved” messages for high-impact updates.
- Check visual consistency across light/dark themes and ensure color is not the only status signal. Honor reduced-motion preferences and keyboard focus.
- Document known limits, role configuration, rollout toggles, and a recovery path for each deployment change.

### Final handoff gate

- Phases 0–6 are closed with linked evidence and no open P1 defects.
- Remaining P2/P3 items have an owner, rationale, and planned resolution.
- A state-level pastor and state-level administrator review the workflows against their real responsibilities.
- No production launch claim is made from mock-only checks; hosted origin, TLS/cookie configuration, deployed backend, database permissions, and backup/restore gates remain governed by the backend pilot acceptance plan.

### Progress update (2026-11-02)

- Phase 7 visual refinement and state-level pastor/admin sign-off are not closed. The local report shell and all eight tabs rendered; narrow-width overflow and one keyboard focus transition were checked. Full contrast/theme/reduced-motion/accessibility review and state-level responsibility sign-off remain outstanding.
- The plan scope excludes the separate levels 1–2 data-sourcing app. That app must receive its own workflow and permission audit before the overall product handoff; its submission, offline/retry, idempotency, and reconciliation contracts should be verified against this oversight backend.
- Keep Phase 7 open until the pilot acceptance checklist in `docs/PHASE7_PILOT_ACCEPTANCE.md` is completed, P2/P3 issues have owners, and state-level pastor plus state administrator reviews are recorded.

## Defect-to-phase index

| Audit finding | Planned phase |
|---|---|
| Count create method/signature mismatch | 1 |
| Worker create and review method mismatches | 1 |
| User approval/deactivation/reactivation method mismatches | 1 |
| Program assignment create/approve/reject adapter mismatch | 1 |
| Announcement create scope helper missing; media create/delete adapters mismatched | 1 |
| Multiple usher sections lack clear frontend assignment/provenance workflow | 2 |
| Count latest/monthly summaries have incorrect semantics | 2 |
| Finance totals ignore period/status; review queue absent | 3 |
| Reports breakdown adapter returns wrong shape | 4 |
| Levels 3–5 are blocked from reports | 4 |
| Live scope selector is empty; pastor/admin actions rely too much on level score | 4 |
| List endpoints are fetched as one page and may silently truncate | 5 |
| Scope-sensitive caches and mutation freshness need isolation/invalidation | 5 |
| Fellowship and other end-to-end flows were not live-verified | 6 |
| Repetitive card styling and weak data hierarchy | 7 |


## 2026-11-02 phase progress update

- **Phase 3 closed locally:** finance reads retain event date, status, submitter/reviewer identifiers, timestamps, and notes. Approved MTD/YTD exclude pending, corrected, rejected, and reversed entries; pending and corrected amounts are separately counted as awaiting review; naira rendering preserves cents. Scoped approve/reject, reasoned correction, and terminal reversal write backend audit events. Finance listing fetches all backend pages; successful mutations refresh drawer/list/summary and invalidate report/dashboard TTL caches. Tests cover status/date totals, pagination, permissioned controls, cache invalidation, review/correction/reversal rules, and audit snapshots.
- **Verification boundary:** the connected database has no finance rows, so reconciliation against non-empty real finance data remains a Phase 6 staging gate. No finance records were created or changed. A local browser rendered the finance overview and empty state; review controls were verified using a rendered fixture.
- **Phase 5 in progress:** announcement and gallery shared-cache keys include authenticated user and effective scope; list page failures propagate instead of becoming empty results. A two-user announcement cache-isolation regression test passes. Adapter pagination is implemented; UI pagination, freshness/retry indicators, and state-volume profiling remain open.

### Phase 5 implementation update (2026-11-02)

- Added a shared offset-pagination adapter and applied it to live workers, users, locations, fellowships, church members, counts, offerings, records, attendance, program events and campaigns, announcements, media galleries, and fellowship sublists. A failure on any page now fails the list operation rather than returning partial rows as complete.
- Extended backend client pagination arguments for counts, announcements, program events, and campaigns; those backend routes already accept `skip` and `limit`.
- Removed empty-list fallbacks for operational list failures in people, fellowship, program-map, communication-gallery, church-data event, and report-anomaly reads. A backend outage can no longer be cached as a successful empty collection in these paths.
- Scoped gallery shared-cache keys by authenticated user and effective scope, matching the announcement cache isolation model.
- Added pagination helper coverage for complete multi-page reads and mid-stream page failure. Verification: `python -m compileall -q app tests` passed; `python -m pytest -q` passed (118 tests, 1 upstream deprecation warning); `git diff --check` passed with existing LF/CRLF normalization warnings.
- Phase 5 remains open: the list screens still load complete collections rather than exposing page navigation/total metadata; visible updated-at/retry UI is not yet wired across sections; fellowship list hydration still makes per-fellowship detail calls; and representative state-volume request-count/response-size/p50/p95 evidence has not been collected. Do not mark this phase closed until those acceptance items are implemented and verified.
