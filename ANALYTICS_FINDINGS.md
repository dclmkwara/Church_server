# Analytics Redesign Findings — Phase A and B1

**Verification date:** 6 November 2026  
**Scope:** Phase A of `proposed_changes/CODEX_ANALYTICS_BRIEF.md` only. This report records source and local checks; it does not claim staging or production verification.

## 1. Why the dashboard could show 30% for 8 of 26

The backend dashboard attendance calculation in `app/api/v1/routes/dashboard.py` computes `round((submitted_present / opportunities) * 100, 1)`. With exactly 8 present and 26 opportunities, it returns **30.8%**. The concrete truncation was in the frontend `DashboardService.attendance_summary_section`: its bootstrap adapter converted `rate` with `_safe_int` before the dashboard rendered it. The offline mock summary also used integer truncation. Both paths now preserve one decimal place, and render-level regression checks cover 8/26 displaying as 30.8%.

Separately, a source-level denominator issue is confirmed for split usher submissions: each accepted `WorkerAttendanceSubmission` carries the full roster snapshot, while both dashboard attendance summary and `/attendance/stats` sum `expected_workers_count` across all submissions. If multiple submissions represent one meeting, the same expected roster can be counted repeatedly. This can change the ratio and is distinct from rounding. The finding and proposed Phase B1 treatment are recorded in Addendum 2 of `proposed_changes/CODEX_ANALYTICS_BRIEF.md`; no schema or aggregation change was made in Phase A.

## 2. Why child selection did not consistently change figures or remain in navigation

The dashboard bootstrap and some dashboard service calls already sent a selected `scope_path`, and backend dashboard endpoints validate it with `deps.resolve_scope_path`. However, the signed-in `AdminContext` and several shared service helpers were anchored at identity scope. People and program services returned the identity path; report scope similarly came from identity; mock route loaders often used `ctx.current_scope_path`. As a result, the dashboard could query a selected descendant while its dedicated pages, service summaries, and links reverted to the login scope.

The backend resolver already rejects malformed paths and paths outside the role-derived authorization envelope. In this source, role expansion is based on the highest role score and assigned user path (`app/api/deps.py::effective_scope_path`). Frontend session context now keeps the assigned path separate from the role-derived maximum used to validate an active analytical path. The URL parameter is `scope_path`; `period` and `include_pending` are also retained. The API remains the final authorization boundary.

## 3. Phase A changes

- Added `app/frontend/dclm_admin/communication/active_scope.py` with active-scope parsing, local descendant validation, period validation, context adaptation, and `scope_link()` query retention.
- Updated backend identity context to retain the role-derived maximum scope separately from the assigned path. Dashboard bootstrap now returns the authorized maximum from the authenticated backend user rather than accepting a client-supplied maximum.
- Passed selected scope through dashboard, workers, people, program, counts, attendance, finance, newcomers, and report service reads. Mock read paths use the same active path.
- Added `scope_path` support to existing read-only dashboard attendance stats, locations, and report breakdown/growth/anomaly endpoints. Each uses existing backend scope resolution before querying.
- Added an active hierarchy breadcrumb in the shared shell and placed it before page content. Sidebar and mobile navigation retain scope and period filters. The dashboard's scope and period form now submits to the full `/dashboard` route, so the selected path is reflected in the breadcrumb and navigation, survives refresh, and does not leave the browser at the fragment-only `/dashboard/content` endpoint.
- Added focused active-scope tests and updated existing service adapter expectations for explicitly scoped report requests.
- Fixed attendance-rate truncation in live bootstrap and mock paths. The worker dashboard distinguishes zero attendance opportunities (shown as **No submission**) from a received report with zero present (shown as **0 present**, **0.0%** when the denominator is nonzero). This depends on `opportunities` being available in the dashboard aggregate; it is not a complete expected-unit coverage calculation.
- Fixed runtime imports exposed during the live check (`Optional` in hierarchy routes and `Input` in the dashboard route).

No reporting expectation table or seeded obligation was added. No count split schema, count-group behavior, Field Utility changes, or church reporting records were added or edited. The canonical RBAC initializer was run against the configured development database with the application's score-9 seed context; it aligned permission metadata and default role-permission mappings with `app/db/init_rbac.py`.

## 4. Missing submissions versus zero

Phase A only changes scope selection and propagation. It does not introduce expected reporting units or coverage calculations. The dashboard worker panel now displays **No submission** when its aggregate has no recorded attendance opportunities, instead of treating missing data as zero present or zero percent. The existing attendance API still does not return an `n_received` coverage field, and its aggregate attendance counters are separate from the submitted present-opportunity calculation; therefore this is a conservative empty-opportunity indicator, not full reporting coverage. Other existing pages may still display zero-valued aggregates where the current UI/model does so. Per Addendum 2, no expectations should be seeded until church leadership answers the recorded questions. Phase B must represent not expected, expected but missing, received with zero, and received with a nonzero value separately.

## 5. Verification performed

- `python -m pytest -q tests/test_active_scope.py tests/test_frontend_live_service_adapters.py tests/test_phase5_attendance.py tests/test_global_admin_dashboard.py --tb=short` — **39 passed**, one third-party deprecation warning from `fastcore`.
- `python -m compileall -q app/frontend/dclm_admin app/api/v1/routes/dashboard.py app/api/v1/routes/hierarchy.py app/api/v1/routes/reports.py app/api/v1/routes/attendance.py` — passed.
- `git diff --check` — passed; Git printed line-ending conversion notices for edited files.
- Started the edited checkout on port 8011 and used the State Overseer, Region Pastor, Group Pastor, and Location Pastor personas. The checked-in RBAC seed initially did not match the development database: the State Admin role lacked `statistics:read`. After an unprivileged seed attempt was rejected by row-level security, the canonical `init_rbac.py` initializer was run with the application's score-9 seed context and completed, aligning default role mappings. No church reporting records were written.
- Browser verified the State → Region → Group → Location path using the State Overseer persona. Each selected scope changed the totals and remained in the full `/dashboard` URL after form submission and reload; the hierarchy breadcrumb and sidebar links updated to the same path. The Region, Group, and Location pastor accounts each opened at their own assigned maximum: Ilorin Region (93 workers), Ilorin East Group (49 workers), and location 003 (47 workers). The State view showed 40 locations, 7 regions, and 185 workers. A sibling State path returned **403**.
- Two sampled sibling locations in Ilorin East (001 and 002) contained no worker records; the dedicated Workers page returned its empty state for location 001. Location 003 held 47 workers. This reflects uneven demo data coverage and is reported as missing records, not as zero attendance.
- The local server was stopped after the check. The browser walk covered the dashboard, selected-scope Workers page, URL/reload behavior, and out-of-scope rejection. It did not manually open every dedicated reporting page under every persona; service and route scope coverage is supplemented by the focused automated tests.

## 6. Phase A status and follow-up

The focused code checks and required State → Region → Group → Location browser gate pass after the development RBAC mappings were synchronized. The provided State, Region, Group, and Location persona emails match the repository's intended 2–5 hierarchy by account role; the numeric labels in the pasted list do not match the repository's role-score mapping. Remaining product limits are the uneven synthetic worker distribution and the lack of reporting-expectation coverage, which is deferred until church leadership confirms the policy. The Phase B1 policy questions, event reporting-unit mapping, approval authority gaps, and split-count design conflicts remain outside Phase A.

---

# Phase B1: Sunday Worship Coverage Slice

**Verification date:** 6 November 2026  
**Scope:** Addendum 3's single Sunday Worship metric, location lifecycle, and dashboard presentation. No other program family or Field Utility workflow was implemented.

## 7. Implemented behavior

- Added Location lifecycle fields `is_active`, `opened_on`, and `closed_on` in migration `a71c3f9d2b40`. Existing rows default to active; historic opening dates remain unknown (`NULL`). The check constraint disallows a close date before a known open date. Downgrade stops if lifecycle values would be lost.
- Added the code-level standing program configuration and centralized Africa/Lagos time zone, awaiting/late/missing windows, and pending-review alert thresholds. Tuesday Leaders Meeting has no missing-report expectation. Leaders Meeting and Workers Meeting remain distinct configuration entries.
- Added the Sunday Worship analytics service and scoped endpoint. It returns expected, received, and counted location coverage; date; status counts; and approved population category totals. Pending is excluded by default, and no submitted report remains `total: null`; an approved report with total zero remains `total: 0`.
- Approved combined events replace covered location submissions. Their count rows enter rollups once, while replaced local rows are excluded. Local scheduled-event rows count at their physical location. An approved combined meeting with no count submission still contributes Awaiting/Late/Missing coverage as the occurrence clock advances. Events tied to inactive campaigns are excluded.
- Updated the Faststrap dashboard. The latest Sunday card and population panel present the occurrence date, counted population, location receipt ratio, and separate coverage badges. The view includes a visible opt-in for pending counts. The population period filter does not change the latest Sunday occurrence; it continues to apply to the other dashboard summaries.
- Captured and reviewed a 1280×720 desktop screenshot for the Region persona at [b1-region-dashboard-desktop.png](<C:/Users/Meshell/Desktop/FastHTML/Church_server/output/playwright/b1-region-dashboard-desktop.png>) and a 390×844 mobile screenshot for the Location persona at [b1-location-dashboard-mobile.png](<C:/Users/Meshell/Desktop/FastHTML/Church_server/output/playwright/b1-location-dashboard-mobile.png>). The dashboard filter wraps on mobile, and the panel remains further down the scrollable page in the normal card grid. Browser checks used State, Region, Group, and Location pastor credentials.

## 8. Database and browser evidence

- Before migration, created `C:\Users\Meshell\Desktop\FastHTML\_dev_db_snapshots\church_server_pre_analytics_b1_20261106T175706Z.dump` (887,901 bytes; SHA-256 `af24b3beb08958376ff1502774f94866827c17d5437068bcf50976f307512185`). `pg_restore --list` read its 1,316 archive entries. The archive is outside the repository. A restore into a scratch database was **not** performed: the available local PostgreSQL listener requires a password that is not configured in this session, and restoring over the development database would be unsafe. Treat archive readability as verified, but actual restoreability as unverified. The Alembic revision after migration was `a71c3f9d2b40`.
- The API-backed dashboard showed **40 expected / 0 received** for the State, **16 / 0** for the Ilorin Region, **4 / 0** for Ilorin East Group, and **1 / 0** for Location 003 on 1 November 2026. These are missing submissions, not reports of zero population. The card correctly said “No counted report.”
- Port 8010 was already serving an older process that rendered the old population analytics. It was left running. The current checkout was launched on port 8012 and used for the B1 UI check; the old process must be restarted or redeployed before it can display these changes.
- An initial browser pass exposed two runtime defects that static tests had not caught: `APIClient` did not forward the new endpoint, and the content renderer passed a dictionary directly to `asyncio.gather`. Both were fixed; the page then loaded for all four personas.
- The local API used for persona checks validates scope using the authenticated user. A direct ORM query without setting request scope context returned no rows and is not evidence that the database is empty. Scope verification is based on the authenticated API/browser result.
- Phase A had run the canonical RBAC initializer with the application score-9 context. No pre-run dump, before-state export, or equivalent record was found, so custom role grants cannot be compared or claimed preserved. The B1 snapshot is after that run. The RBAC initializer was not rerun in B1.

## 9. Verified source gaps that remain

- `FellowshipAttendance` contains `men`, `women`, `youths`, `children`, and `total`. It cannot distinguish adult male/female, young-adult/campus male/female, youth male/female, or children boys/girls. `FellowshipMember.fellowship_group` classifies a member but does not provide a dated attendance count. Fellowship remains excluded from the B1 broad program spine, consistent with the prior user instruction that fellowship records are location and fellowship scoped.
- `WorkerAttendanceSubmission` stores IDs for workers marked present in JSONB, but expected roster data is only `expected_workers_count`. There are no stable IDs for expected workers in each meeting snapshot. Both existing attendance aggregates sum that full roster count per submission, so split usher submissions can double the denominator.
- Counts currently start pending, but no formal count review route or correction-row `supersedes_id` workflow was found. The B1 dashboard's optional pending display does not implement approval.
- Campaign cancellation is represented by campaign status and event soft deletion; a campaign-less event has no distinct canceled status. The service excludes soft-deleted and unapproved events and events whose campaign is not active.
- The reporting dashboard for B1 only supports Sunday Worship population counts and the latest Sunday in the UI. The API accepts an explicit Sunday date. There is no trend chart or month/quarter/year series in this slice.

## 10. Verification commands and phase status

- `python -m pytest -q tests/test_sunday_worship_analytics.py tests/test_active_scope.py tests/test_frontend_live_service_adapters.py tests/test_global_admin_dashboard.py --tb=short` — **45 passed** after adding regression checks for missing combined reports and location-level scheduled-event reports. One third-party `fastcore` deprecation warning remains.
- `python -m compileall -q app/services/analytics app/api/v1/routes/dashboard.py app/frontend/dclm_admin/backend/client.py app/frontend/dclm_admin/communication/api_client.py app/frontend/dclm_admin/communication/dashboard_service.py app/frontend/dclm_admin/routes/dashboard.py` — passed.
- Real browser checks exercised the dashboard with State, Region, Group, and Location Pastor accounts on current-source port 8012. The first pass found runtime errors; those were fixed and the pages subsequently loaded. The old port 8010 process was not treated as current-source verification.
- The Sunday-only slice is implemented, and its focused automated and browser checks pass. The full B1 gate remains open until the development backup is restored to a scratch database and verified. Phase B1 does not close the broader analytics redesign. Count approvals, count-group/split behavior, attendance correction and denominator changes, House Caring category expansion, Crusade/Retreat sessions, and other program dashboards remain for later phases.


---

# Addendum 4 close-out: B1 restore and B2 count review

**Verification date:** 7 November 2026  
**Scope:** B1 close-out evidence and B2 only. B3 has not started.

This addendum supersedes conflicting B1 status statements above about the restore, port 8010, count review, and B2 seed data. Earlier notes describe the state at their own verification time.

## 11. B1 close-out evidence

- Restored `C:\Users\Meshell\Desktop\FastHTML\_dev_db_snapshots\church_server_pre_analytics_b1_20261106T175706Z.dump` into a temporary PostgreSQL cluster on port **55439** using trust authentication. The Supabase-only `supabase_vault` extension/schema archive entries were omitted because the throwaway cluster does not provide that extension; application data restored.
- Compared dev and restored row counts for key tables; every listed count matched: `states` 37/37, `regions` 7/7, `locations` 40/40, `workers` 349/349, `users` 73/73, `counts` 13/13, `program_domains` 5/5, `program_types` 27/27, `program_events` 5/5, `event_assignments` 1/1, `roles` 20/20, `permissions` 80/80, and `role_permissions` 916/916. The temporary cluster was stopped and deleted.
- Regression coverage now proves that Group-, Region-, and State-level Sunday Worship counts without a `ProgramEvent` replace the covered locations' local reports using the program level and scope path. An event is an additional replacement trigger, not a prerequisite.
- `init_rbac.py` was **not rerun** in B2. The migration added the new review permission/grants directly. No later initializer run was needed; the requested before/after export-and-diff gate remains mandatory before any future run.

## 12. B2 implementation

### Count review and approval

- The dev database is at Alembic revision `c2e5a8f14b31`. The additive, reversible migration adds `approved_by_id`, `approved_at`, `auto_accepted`, `supersedes_id`, `rejection_reason`, `rejected_by_id`, and `rejected_at` to counts, with indexes and user/count relationships. Downgrade refuses to erase recorded review history.
- No existing count-review permission was found. Added `counts:review` and assigned it to the Group Pastor, Region Pastor, and State Overseer roles. Review action mapping is Local/Location → Group Pastor (score 3), Group → Region Pastor (score 4), Region → State Overseer (score 5). State-level reports are automatically stored as `approved` with `auto_accepted=true` and an approval timestamp.
- Stored status values are exactly `pending`, `approved`, and `rejected`. Analytics counts only approved rows by default; rejected rows never count. The optional pending switch is explicit.
- The queue endpoint is scoped to the signed-in user's authorized path and groups pending rows by location, program type, Lagos calendar occurrence date, program level, scope path, and event. It orders oldest first and provides category totals, submission and section counts, submitter names, group age, 10-hour and 24-hour flags, accepting-pastor actions, and next-level visibility after 24 hours. Approve and reject update all pending rows in that group; rejection requires a reason. Program Counts now displays an explicit **Auto-accepted** badge for state-level rows on desktop and mobile.
- Rejected history is linked through `supersedes_id` and exposed by the count history endpoint. A correction is a new pending count referencing the rejected count and is reviewed by the same level-mapped approver. Utility app was not changed. Its correction submission needs the rejected row's UUID as `supersedes_id` plus the corrected count's existing location, occurrence date, program type/domain, program level/scope (and event ID if applicable), category values, submitter, and note fields. Utility should display the rejection reason/history to the correcting user.
- The current data model does **not** have dedicated `count_mode` or `section_label` columns. B2 labels sections using a `Section: <label> |` prefix in the existing note field; the queue recognizes that prefix, and labels older rows without it as unrecorded. This supports the seeded review demonstration but does not implement B3 split-count rules.
- Needs-attention thresholds come from the shared `PENDING_ACCEPTOR_ALERT_HOURS=10` and `PENDING_NEXT_LEVEL_ALERT_HOURS=24` configuration. The count-review page includes a Remind action that sends the existing in-app broadcast to active users at an uncovered location. Reminder behavior is currently limited to Sunday Worship and validates that no local or combined report already covers the location.

### Meetings and attendance integrity

- Tuesday Leaders Meeting and Saturday Workers Meeting remain separate program types and separate pages: `/church-data/meetings/leaders-tuesday` and `/church-data/meetings/workers-saturday`; they have independent queries and metrics and are never combined. The current dev dataset has no attendance submissions for those pages, so they show empty/no-submission states rather than fabricated zero attendance.
- The pre-existing attendance denominator issue is still present in the underlying dashboard and attendance aggregate: split `WorkerAttendanceSubmission` rows each carry a full expected roster count, and summing those values can double-count the denominator. This B2 dashboard labels the roster rate **Rate withheld** and explains why. The underlying aggregate has not yet been corrected.

### Synthetic demonstration data

- Added `scripts/seed_b2_sunday_analytics.py`, guarded by an explicit dev Supabase project reference check and a snapshot prerequisite. It writes only rows marked `B2_DEMO:b2-sunday-demo-v1`; `--remove` removes only that marker's counts and restores the manifest-recorded location lifecycle date.
- Took a pre-seed backup: `C:\Users\Meshell\Desktop\FastHTML\_dev_db_snapshots\church_server_pre_b2_demo_seed_20261107T061644Z.dump` (892,609 bytes; SHA-256 `0f2cd76e3368b58375518f613dbf681723c2fa1be8e5ce8b5d665d9eae9412ff`). Manifest: `C:\Users\Meshell\Desktop\FastHTML\_dev_db_snapshots\b2-sunday-demo-v1_manifest.json`.
- Seeded 241 marked count rows covering eight Sundays, 7 regions, 19 groups, and 40 locations, with the specified approved, pending (including older than 24 hours), rejected plus correction, missing, approved-zero, three-section, eventless Group combined, and mid-period location-opening cases. This is synthetic development data and is removable by the script's guarded `--remove` command.

## 13. Dashboard presentation and live verification

- Replaced the old `/dashboard` content with the prototype's coverage strip, latest population and average cards, scope-child table, needs-attention panel, weekly trend, and 4/8-week controls. It now renders **inside the existing DCLM app shell**: the existing left sidebar, account header, and active-jurisdiction breadcrumb remain visible. The prototype's dark colors were not carried over; the dashboard content uses the light DCLM blue/white palette. At narrower widths, the child table and attention panel stack so table columns remain readable.
- The line chart now leaves gaps for missing reports. It plots an approved zero at the zero axis but never invents a zero point for a missing week.
- Live development values at the State Overseer scope for Sunday 1 November: 39/40 reporting units received, 38 approved, 1 pending, 1 missing, approved population 6,072, and 143 active workers out of 185 on register. Region, Group, and Location dashboards showed their own scoped records. Screenshots are under `output/playwright/`: `b2-state-dashboard-redesign.png`, `b2-region-dashboard-redesign.png`, `b2-group-dashboard-redesign.png`, and `b2-location-dashboard-redesign.png`.
- Port 8010 was restarted from the current checkout. Latest process uses `run_server.py`; live requests and DB startup succeeded. This verifies the local development host only, not staging or production.

## 14. Tests, limits, and status

- Focused verification after the missing-week chart fix: `python -m pytest -q tests/test_analytics_dashboard_chart.py tests/test_sunday_worship_analytics.py tests/test_count_review_workflow.py tests/test_rbac_default_role_grants.py tests/test_program_level_metadata.py tests/test_frontend_live_service_adapters.py` — **63 passed**, with one third-party `fastcore` deprecation warning. Changed route modules compile with `python -m compileall`.
- The automated review tests verify status values, approver-level mapping, pending/rejected exclusion, reported zero, count-group identity, and correction aggregation; browser checks verify live persona data and page layout. The State dashboard makes multiple per-date/per-child analytics calls and is slower to load than the former summary dashboard on this development database; this response-time limit should be measured and improved before broad rollout.
- The Field Utility correction interface, dedicated split-count fields/rules, worker-attendance denominator correction, and all B3 work remain out of this slice. **B3 has not started**; its required Retreat/Crusade storage inventory is scheduled after B2 close-out and B2b.

## 15. v2.1 B2 close-out update (7 November 2026)

- `proposed_changes/CODEX_ANALYTICS_BRIEF_v2.md` is the canonical working copy of the supplied v2.1 brief. The original downloaded `CODEX_ANALYTICS_BRIEF_v2 (1).md` remains alongside it; no user file was deleted.
- RBAC source check: `app/db/init_rbac.py` declares `counts:review` and grants it to Group Pastor, Region Pastor, and State Overseer. Scores 6-9 also receive it through `HIGHER_ADMIN_PERMS`, consistent with their higher backend authority. A regression test requires the three in-scope pastors to retain the grant and ensures Group Admin does not receive it. `init_rbac.py` was not run; the required JSON export-and-diff is still a gate before any future run.
- Performance change: added `GET /api/v1/dashboard/sunday-worship/series`, returning all selected weeks and direct-child histories. The service performs a fixed five database reads for the selected scope: program type, scoped locations, direct children, approved program events, and date-bounded count rows. The dashboard now makes three backend API calls per page load: grouped Sunday series, dashboard bootstrap, and count-review queue. Former repeated per-date/per-child analytics calls and the hierarchy-tree request were removed. Count-review payload construction also batches locations, program types, events, submitter names, and correction history rather than querying each group separately.
- Performance measurements used the seeded development database, local Faststrap app on port 8011, and authenticated State Overseer, Region Pastor, Group Pastor, and Location Pastor browser sessions. First uncached-per-scope load (one sample per persona): State 14.31s, Region 10.84s, Group 11.69s, Location 9.93s. Five subsequent browser reloads per persona gave warm medians: State 3.823s, Region 3.496s, Group 3.552s, Location 2.721s. The required median of five cold samples per persona is **not yet available**; first cold samples were captured, but the development process was not restarted between five independent cold samples for each role. State's warm median remains above the 3s target. Cold State latency is also above target. The fixed three-call page fan-out improved the former repeated calls, but database and render latency still need further work before the target is met.
- Legacy section-label parsing is now centralized in `app/utils/count_sections.py` and marked as interim compatibility behavior. The review route and Program Counts adapter use that helper. B5 is expected to replace it with dedicated columns and a backfill; this change does not expand reject/resubmit behavior or remove `supersedes_id`.
- Verification for this close-out update: `python -m compileall -q app tests` passed; `python -m pytest -q` reported **209 passed**, with one third-party `fastcore` deprecation warning. Browser checks loaded the dashboard under all four personas and retained the existing sidebar and light DCLM shell. The new series adapter initially lacked forwarding through `APIClient`; the live check caught this, the adapter was added, and the next run rendered successfully.
- The pre-existing server on port 8010 was not stopped. The updated checkout was exercised on port 8011; port 8010 may still serve the previous process. The temporary port 8011 process is held open by the current verification session.
- **B2 close-out remains open** pending five cold samples per persona and State performance below 3s or a complete measured floor explanation. B2b and B3 have not started. The v2.1 usher edit window remains deferred to B5, and B2's `supersedes_id` and rejection history remain intact.
