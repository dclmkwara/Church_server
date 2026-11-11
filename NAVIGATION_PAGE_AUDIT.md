# Navigation and Data Presentation Audit

**Date:** 7 November 2026  
**Environment:** local development frontend port 8012, API port 8010, restored local PostgreSQL clone `dclm_perf` on port 55432. API health reported healthy and database-connected.  
**Evidence key:** `[BR]` seen in browser; `[SRC]` confirmed in source; `[BR+SRC]` both; `[INF]` interpretation; `[UV]` unverified.  
**Privacy:** no account names, phone numbers, email addresses, or tokens are included. Screenshot profile identity is blurred or replaced.  
**Scope:** read-only. No pages, menus, roles, or permissions were changed.

## Findings at a glance

- `[BR+SRC]` The analytics dashboard occupies the content area inside the existing DCLM sidebar shell. The sidebar remains on desktop; mobile has a drawer and bottom navigation. The app brand and light theme remain in place.
- `[BR]` State dashboard showed 0 of 40 expected locations reported for the current Sunday. Location showed 0 of 1, no counted report, and eight distinct Sunday rows labeled `Not reported`. Missing submissions were not shown as zero population.
- `[BR]` Location dashboard showed 5 active workers, 0 awaiting approval, 0 suspended, 0 inactive/other, 5 on register. Workers' meeting rate said `No report`; the review note says the Group Pastor accepts location reports.
- `[BR]` Location opening `/organization` returned HTTP 500. This is broken for that persona, not an empty hierarchy result.
- `[BR+SRC]` The global search input has no global search handler. Help & Docs points to `/docs`, which returned 404 on the frontend at 8012.
- `[SRC]` Workers and Members direct data entry to the Field Utility. The admin worker import preview/commit handlers return a source-intake notice instead of importing. A hierarchy template download exists; hierarchy import is offered starting at Group scope.
- `[SRC]` Saturday Workers Meeting and Tuesday Leaders Meeting use distinct routes and program-type slugs. They share a renderer, not data. Their page warns that a unique-worker attendance rate is withheld because repeated submissions may repeat the full roster denominator.
- `[SRC]` Dashboard expected attendance is pooled. General Reports tabs use separate endpoints and definitions; they do not share the dashboard's `include_pending` switch.
- `[SRC]` RBAC Studio is a role/permission catalogue, not a pastor-controlled permission editor. The role-edit route says changes require an approved governance workflow. No level-pastor grant/revoke UI was found.

## 1. Menu inventory

`Lowest role` refers to this app's current score chain: Location 2, Group 3, Region 4, State 5. Level 1 field users are outside the admin dashboard scope. Menu visibility is controlled by `VISIBLE_MODULES`, permissions and level checks in `components/shell.py`; opening a route also requires an authenticated session. Data routes may rely on backend permission and scope checks rather than hiding every URL.

| Page | Route | Purpose / visible content | Writes? | Lowest menu role / gate | Browser observation | Overlap / merge constraint |
|---|---|---|---|---|---|---|
| Dashboard | `/dashboard` | Sunday coverage, latest population, expected Sunday attendance, average, active-worker snapshot, worker-meeting state; child table or location's last eight Sundays; needs-attention and trend | Read; Remind can write | Location 2 | State and Location loaded | Summary view; preserve definitions and drill-down |
| Inbox | `/inbox` | Action queue filtered by worker, user access, removal, transfer, status change; detail and review cards | Yes: approve/reject/escalate | Location 2 | Both returned 200 | Cross-type queue overlaps Workflows; keep request history distinct |
| Workers | `/people/workers` | Worker directory, filters, details, lifecycle actions; registration points to Field Utility | Some actions write; admin create/import is incomplete | Location 2 | State showed intake notice; Location showed 5 rows | Worker is operational staff identity, not login account or member |
| Members | `/people/members` | Member registry and details; entry directed to data-sourcing app | No working admin entry observed | Location 2 | Both showed entry/empty state | Separate member registry and lifecycle |
| App Users | `/people/users` | Login accounts, approval/status, linked role assignments and account details | Yes: create/review/deactivate/reactivate/role routes | Location 2 | Location showed one row; State had no visible rows | Account is login/security identity, normally linked to a Worker |
| Officials | `/people/officials` | Official appointments and status/detail | Yes, routes exist | Intended score 4+; live shell disables the item | Direct route returned 200 at both personas; hidden in menu | Appointment is distinct from account role or worker record |
| Programs | `/church-data/programs` | Domains, program types, campaigns, events, assignments, event detail/report panels | Yes: create/update/status/assignment routes | Location 2 | Both returned 200; little content in sampled scope | Catalogue/scheduling is not proof of a report |
| Program Counts | `/church-data/counts` | Recent count overview, Location/Event filters, count detail drawer | Read; new count is routed to Field Utility | Location 2 | Both returned 200 | Reads count history; Count Review changes approval state |
| Count Review | `/church-data/count-review` | Date-scoped pending groups and approve/reject/remind actions | Yes | `counts:review`; Group 3 is first in-scope pastor role | State had review workspace; Location had no review content | Approval queue is not general count history |
| Saturday Workers Meeting | `/church-data/meetings/workers-saturday` | Present/late/absent row counts and monthly rows for Saturday program type | Read-only stats | `attendance:read` | Both returned 200; no rows in sampled scope | Separate program from Tuesday Leaders Meeting |
| Tuesday Leaders Meeting | `/church-data/meetings/leaders-tuesday` | Same row-status measures filtered to Tuesday Leaders Meeting | Read-only stats | `attendance:read` | Both returned 200; no rows in sampled scope | Keep its own page and metrics |
| Offerings & Tithes | `/church-data/finance` | Approved/pending/rejected finance summary, fund/location/method filters, record details | Entry/edit/correction/review/delete routes | Location 2 | Both returned 200; no sampled records | Reports Financial has separate date window/definitions |
| Newcomers | `/church-data/newcomers` | Convert/newcomer follow-up records and status/details | Create/update/delete routes; field entry is directed to Utility | Location 2 | Both returned 200; Location showed intake notice | Not Members or Users; protect contact details |
| Attendance | `/church-data/attendance` | Worker attendance records and detail/filter flow | Read-only reporting; field submissions via Utility | `attendance:read` | Both returned 200; no rows in sampled scopes | Overlaps meeting pages and Reports Attendance, with different aggregation |
| Workflows | `/workflows` | My Requests and Review Queue for transfers, status changes, removals; timeline/history and actions | Yes | Location 2; actions permission/scope-gated | Both returned 200 | Some requests also surface in Inbox; workflow is request history |
| Fellowship | `/fellowship` | Fellowship activity summaries, categories and records | Location-level field entry; no separate fellowship login | Location 2 plus data permission | Both returned 200; sampled summaries were zero | Fellowship remains location-linked, outside program spine |
| Organization | `/organization` | Hierarchy explorer, locations/profiles, hierarchy template and import | Yes | Group 3 in menu | State returned 200; Location returned 500 by URL | Master hierarchy data, not event reporting |
| Communication | `/communication` | Announcements, targeted broadcasts, media subpages | Yes | Region 4 | State returned 200; Location route had no usable content and is hidden | Separate from notifications and workflows |
| Reports | `/reports` | Summary, Financial, Attendance, Timeseries, By Level, Growth, Anomalies, Exports | Refresh/export | `reports:read`, granted to configured pastor roles | Both returned 200 | Legacy/report endpoints have distinct definitions |
| Roles & Permissions | `/system/rbac` | RBAC roles, permission families and score mapping; detail drawers | Catalogue is read-only; edit route requires governance workflow | Level 2 via `_system_guard` | Both returned 200 | Assigning a role to one account is separate from editing role policy |

### Sidebar and shell

`[BR+SRC]` Desktop pages keep the navy sidebar. Mobile uses a drawer and five bottom shortcuts (Home, People, Church, Finance, Inbox). Shared top bar has search, notification drawer and account menu. The branded light theme is used. The dashboard stays within the shell's main content column.

Live backend mode disables Officials in the sidebar even though its route and menu definition exist. Count Review is permission-gated by `counts:review`; Reports is removed without `reports:read`; Communication is in Region/State modules, not Location/Group.

## 2. Page behavior, figures and actions

### Dashboard

- `[BR+SRC]` Filters are a 4/8-week window and `Count reports pending review`. They submit immediately as GET parameters and preserve the active scope. Current occurrence is the most recent Sunday calculated from server `date.today()`; this route does not explicitly apply `Africa/Lagos` to that date calculation.
- Coverage shows expected reporting locations, received reports, and separate Approved, Pending review, Returned, Not reported states. A valid approved zero is distinguishable from missing. Pending inclusion changes whether pending reports contribute to population totals.
- `Latest Sunday population` sums counted population for the current occurrence. `% of expected Sunday attendance` is pooled counted population divided by effective expected population among locations with both a counted report and estimate. Locations without estimates are excluded and counted separately; values are uncapped. State Overseer alone sees the management link.
- `Average per reporting location` first calculates each week's total / counted locations, then averages available weekly averages. Missing weeks are omitted. It is not a pooled person-week average.
- `Active workers` is a current snapshot: active, awaiting approval, suspended, inactive/other, total on register. It is not accumulated across time.
- `Workers' meeting attendance rate` is withheld when roster denominator data exists; otherwise it says no report. Source warns that repeated full-roster submissions can inflate the denominator until roster snapshot/deduplication is implemented.
- State/Region/Group child table links names and shows latest state, population, average, expected attendance, pooled percentage and review state. Location instead shows eight separate Sundays, with `Not reported` distinct from reported zero, plus review responsibility.
- Needs-attention includes missing, returned, pooled declines, pending review and reminder controls where allowed. Declines compare only the same locations counted in both weeks, pool their counts before calculating percentage drop, use a named 15% constant and require five comparable locations. Reminders target eligible ushers and the Location Pastor through the backend.
- Weekly trend line is average reported population per counted location; bars are counted locations / expected locations. Missing weeks leave a line gap; reported zero is valid. Bars cap at 100%.
- Child/trend/attention panels lazy-load with visible loading/error states. No dashboard export is present.

### Inbox and Workflows

- Inbox filters are All, Workers, User access, Removal, Transfers, Status change. Cards open detail with current stage, location, submitter/time, summary and linked Worker, App User or Workflow record. Confirm actions support approve/reject/escalate where the request permits it.
- Workflows has My Requests and Review Queue. Types: transfer, status change, removal. States: Pending, Approved, Rejected, Escalated. Detail drawer shows request timeline and review history; create/review actions depend on permission/scope.
- Worker/user approvals appear in Inbox; transfer/removal/status requests are in Workflows and may also surface in Inbox. There is no single universal state machine: the backend request model/service owns transitions.
- Notification source types in `NotificationService` include counts, offerings, fellowship attendance, prayer requests, pending workers/users, worker removals and testimonies, plus addressed count reminders and active broadcasts. Generic items are fetched by the caller's hierarchy scope; reminders are filtered by recipient user ID. Broadcast visibility checks target path and audience/role.

### Workers, Members, App Users

- Workers shows worker identity/status, unit/location and lifecycle actions. State browser view directed registration to Level 1-2 Field Utility; Location showed five synthetic rows. `/people/workers/import/preview` and `/commit` return a source-intake notice instead of importing. A worker template download route exists; that alone does not make admin import operational.
- Members is a distinct church-member registry; sampled page showed the entry notice and no populated table.
- App Users is authenticated accounts, role assignment and review/deactivation/reactivation. Location had one row; State had no visible rows. Contact values are intentionally omitted here.
- These objects overlap by person but differ: Worker = operational staff identity; Member = congregation registry; App User = login/security identity, normally linked to a Worker.

### Programs, Program Counts and Count Review

- Programs is the configuration area for domain, type, campaign, event and assignments; routes expose create/detail/edit/status/assignment forms. It is not the activity-statistics dashboard.
- Program Counts is a read view of submitted count records with Location and Event filters and a detail drawer. It does not yet expose the complete five-filter reporting spine. Submission is routed to Field Utility.
- Count Review groups by date and presents pending group state; approve applies to the group; reject requires a reason; Remind calls the backend reminder endpoint. Rejected rows are excluded from counted totals. Correction is a linked new submission in this slice.
- **Permission mismatch:** frontend Count Review reminder control checks `counts:review`; backend reminder route requires `counts:remind`. An account with review but without remind can see the action and then be denied. Default in-scope pastor roles currently have both.

### Meetings and Attendance

- Saturday and Tuesday routes have distinct slugs (`saturday_workers_meeting`, `tuesday_leaders_meeting`) and strictly filter by their own program type. They share page rendering only.
- Cards count stored rows marked Present, Late and Absent plus total records. Monthly table columns are Month, Present, Late, Absent, Excused, Total records. The explainer warns that unique-worker rate is withheld because full-roster submissions can repeat the denominator. There is not yet a roster snapshot or meeting list on these pages.
- Attendance is a separate general worker-attendance records page. Reports > Attendance also displays individual worker rows. Reports calculates Present rows / all returned attendance rows; it is not a distinct-worker roster rate. Filters can differ.
- The sampled clone had no submissions on these pages. Empty results do not prove zero attendance.

### Finance, Newcomers and Fellowship

- Finance shows approved month/year, pending amount/count, rejected count, fund/location/method filters, and detail. Approved sums are separate from pending/rejected. Entry/edit/correction/review/delete routes exist by permission. Reports Financial uses different date-window logic.
- Newcomers is labeled Follow-up records and has list/create/update/delete routes. Location sample directed entry to Field Utility. Contact fields are person-level and need privacy constraints.
- Fellowship is location-scoped and separate from the program metadata spine. Corresponding Location level 1 field utility records fellowship activity; no extra fellowship account is needed. Sampled zero summaries refer only to current dev rows. Exact requests per page load were not instrumented; source has separate summary/content/list/detail handlers.

### Organization, Communication, RBAC

- Organization has hierarchy explorer, location/profile views, hierarchy template download and import control. Import is offered at score 3+. Location direct route failed HTTP 500.
- Communication has announcement content/status, targeted broadcast and media gallery/item subroutes. Region/State menu module. No broadcast was sent.
- RBAC Studio reads roles, permission families and score mapping. Role/permission detail drawers exist; role edit says changes require an approved governance workflow. No local pastor permission delegation editor was found. Location can open the catalogue (HTTP 200), which is read visibility, not edit authority.

## 3. Reports tabs and definition drift

Reports defaults to a 90-day window (today minus 90 days through today) and offers eight tabs. These report functions do not accept the dashboard `include_pending` selection. Live mode calls separate `/reports/*` endpoints; several responses have 45-second process-local TTL caching. Some non-403 service failures become empty arrays, which can resemble no data.

| Tab | Display/formula | Scope/date/pending | Difference from dashboard |
|---|---|---|---|
| Summary | Latest count total; distinct locations in returned rows; recent date/location/event/total/submitter count rows | Scoped path, selected 90 days; no pending switch | General count submissions, not Sunday-only current occurrence |
| Financial | Approved total, transaction count, average entry; date/location/fund/amount/method/recorder | Scoped dates; no pending switch | Not the dashboard's Sunday population or necessarily Finance page month/year view |
| Attendance | All worker rows, Present rows, Late rows; Present share = Present / all returned rows | Scoped dates; no pending switch | Row share, not distinct worker roster percentage; repeated submissions affect it |
| Timeseries | Counts, offerings and worker-attendance sparklines; direction compares first and last point | Scoped dates; no pending switch | Counts span programs/dates, not weekly Sunday average/coverage |
| By Level | Child counts, finance total and worker-attendance record count | Scoped dates; next hierarchy level | No Sunday-specific expected/coverage semantics |
| Growth | Weekly count totals and week-over-week growth from backend | Scoped dates; backend returned growth | Not the dashboard's pooled same-location decline rule |
| Anomalies | Backend count anomalies rendered with location/date/value | Scoped dates; cached | Distinct backend anomaly rule, not the 15% dashboard rule |
| Exports | Attendance Counts, Financial Summary, Worker Attendance; CSV/Excel/PDF live routes | Authenticated export and selected dates | Report-family exports, not a dashboard export |

Do not quote Reports Attendance/Growth as dashboard measures without their definitions. Dashboard distinguishes missing from zero and excludes pending by default; Reports has no shared pending switch.

## 4. Search, notifications, install, help

- **Global search:** shared shell renders a `q` field without HTMX or a global search handler. Page-specific searches exist but are not the top-bar search. `[SRC]` global control is not wired.
- **Notification bell:** loads `/partials/notifications` and renders up to eight latest title/body/time items. The partial has no read/unread controls or deep links. Notification source types and scoping are described above.
- **Install App:** hidden sidebar trigger is revealed when `beforeinstallprompt` fires. Fallback JS gives Chrome/Edge address-bar and iOS Safari Share > Add to Home Screen directions. No install was performed.
- **Help & Docs:** link targets frontend `/docs`; local request returned 404 on port 8012. Backend API documentation is a different port and is not linked here.
- Account menu has identity/logout; no account or theme state was changed.

## 5. Route access and scope

Login middleware protects dashboard, inbox, people, church data, workflows, fellowship, organization, communication, reports, system and partial routes. Analytics and reports use `active_scope_context`; backend calls use access token/scope and API permission/RLS checks. Menu visibility is not the authorization boundary. Some route handlers rely on backend denial, and several non-403 service errors become empty data or inline error states.

At Location, direct `/organization` returned HTTP 500; Count Review returned HTTP 200 with no review data/control; RBAC catalogue returned HTTP 200 and is read-only. This proves hidden menu does not necessarily mean a clean denial and that Organization is broken for Location. It does not prove all nested routes are accessible. An explicit malformed/out-of-scope route matrix was not run in this audit; active-scope safety has separate tests.

## 6. Menu visibility by persona

| Page group | Location 2 | Group 3 | Region 4 | State 5 | Notes |
|---|---:|---:|---:|---:|---|
| Dashboard, Inbox | Yes | Yes | Yes | Yes | Scope follows identity maximum with allowed drill-down |
| Workers, Members, App Users | Yes | Yes | Yes | Yes | Worker/member input goes to Field Utility |
| Officials | Hidden in live menu | Hidden | Hidden | Hidden | Source has min score 4 but live shell disables key |
| Programs, Program Counts | Yes | Yes | Yes | Yes | Count entry is from Field Utility |
| Count Review | Permission-gated | Yes with review grant | Yes with review grant | Yes with review grant | Group Pastor is first in-scope default pastor reviewer |
| Meetings, Finance, Newcomers, Attendance | Yes | Yes | Yes | Yes | Attendance data requires `attendance:read` |
| Workflows, Fellowship, Reports, RBAC | Yes | Yes | Yes | Yes | Reports also needs `reports:read`; RBAC min score 2 |
| Organization | No | Yes | Yes | Yes | Location direct route was 500 |
| Communication | No | No | Yes | Yes | Region/State module |

Group and Region access above is source-derived from module and role rules; the browser exercise covered State and Location only.

## 7. Metric overlap matrix

| Concept | Dashboard | Other page | Reconciliation rule |
|---|---|---|---|
| Sunday population | Current Sunday, coverage, pooled expected/average and weekly trend | Program Counts, Reports Summary/Timeseries | Same accepted-count rule and explicit date/program; zero differs from missing |
| Expected population | Pooled percent | Location records and Attendance views | Same effective date and counted scope; exclude and count locations without estimate |
| Worker attendance | Rate withheld pending roster dedupe | Attendance, each meeting page, Reports Attendance | Separate program type; distinguish row count from unique workers and roster denominator |
| Finance | No current dashboard card | Finance and Reports Financial | Approved/pending/rejected states and event date need clear definition |
| Worker lifecycle | Current snapshot/attention | Workers, Inbox, Workflows | Snapshot counts differ from pending request count |
| Fellowship | Not on current dashboard | Fellowship | Location-only data spine, not ProgramEvent session spine |
| Program schedule | No dashboard schedule editor | Programs | Domain/type/campaign/event/assignment config does not prove a submission |

Share a visual template only when program type, occurrence date, expected-unit level, source, approval inclusion and privacy remain explicit. Do not merge the two meeting datasets.

## 8. Registered routes outside primary menu

- `/dashboard/panels` lazy dashboard content; `/analytics/expected-population`, template CSV, bulk preview/apply, linked only from State Dashboard.
- Worker import/template, detail/review/suspend/removal/transfer/status-change; `/bulk/templates/workers`.
- Organization hierarchy/location profiles, import and `/bulk/templates/hierarchy`.
- Program domain/type/campaign/event create/detail/report/assignment routes; count detail/history/create routes (count create returns source-intake notice).
- Workflow My Requests/Review Queue subpages; Communication broadcasts/content/media/gallery/item pages.
- System notification history, public intake, sync conflicts, app versions, health, audit logs, utilities and RBAC detail routes.
- Reports tab content, refresh and live export routes; notification partial and PWA manifest/service worker/offline routes.

Route registration does not prove successful action: worker import preview/commit return the Field Utility intake notice, and Location Organization is 500.

## 9. Tests, timings, screenshots and limits

- No tests were added or run for this read-only audit. Related existing suites identified: `test_sunday_worship_analytics.py`, `test_scope_route_safety.py`, `test_program_level_metadata.py`, `test_notification_service.py`, `test_dashboard_review_visibility.py`, `test_count_review_workflow.py`, `test_analytics_dashboard_payload_api.py`, and `test_analytics_dashboard_chart.py`.
- One Playwright navigation observation per State/Location route (20 routes each), sequential and after sign-in; measurement is `domcontentloaded` plus 150 ms settle, not a cold/warm benchmark and not full lazy-panel completion. Values ranged 238-1,545 ms. State median was about 300 ms; Location median about 290 ms; Location `/organization` took 345 ms and returned 500. These are navigation responsiveness figures, not complete dashboard timings.
- Local clone had no Sunday counts or expected-population values. Missing is shown as missing; empty worker/finance/fellowship tables do not prove no real activity.
- Screenshots (synthetic local data; profile identity redacted): [State dashboard](output/playwright/nav-audit/state-dashboard.png), [Location dashboard](output/playwright/nav-audit/location-dashboard.png).
- No forms submitted, broadcasts sent, statuses changed, estimates saved or reports exported.

## 10. Findings to carry forward

1. Fix Location `/organization` HTTP 500 and retest.
2. Wire global search to a scoped search endpoint or remove the misleading input.
3. Point Help & Docs at a real page or intended API documentation URL.
4. Align Count Review reminder permission check with backend `counts:remind`.
5. Reconcile dashboard, Reports and detail-page definitions and pending state.
6. Complete worker roster snapshot/deduplication before publishing a meeting attendance rate.
7. Verify person-level fields against approved scope/privacy rules by role.
8. No pastor permission delegation editor or level-specific permission history was found; retain approved governance workflow until that design is implemented.

## 11. Navigation consolidation implementation update (11 November 2026)

The proposed groups are now implemented in the shared sidebar. All page URLs remain the same; no route was renamed or removed, so bookmarks continue to resolve directly and no redirect aliases were needed. Visibility is filtered by the user's module, minimum level and explicit page permission. The server-side route and data-scope checks remain authoritative.

| Group | Page entries | Visibility notes |
|---|---|---|
| Overview | Dashboard | All Level 2–5 roles. |
| Reports and decisions | Pastor Report, Reports, Recurring Program Attendance, Attendance, Saturday Workers Meeting, Tuesday Leaders Meeting, Newcomers, Count Review, My Requests | Explicit report, count, attendance, or record read/review permissions apply where configured. Count Review is hidden from admins lacking `counts:review`. |
| Programs and events | Programs, Retreat, Crusade, Program Counts | Program and count read permissions apply. Retreat and Crusade remain distinct. |
| People | Workers, Members, App Users | Worker, record, and user read permissions respectively. Officials remains intentionally hidden in live mode. |
| Money | Offerings and Tithes, Finance Analytics | Finance Analytics opens the existing Reports financial tab; record and report permissions apply separately. |
| Church life and structure | Fellowship, Organization | Fellowship permission applies; Organization is limited to levels 3–5. |
| Messages | Inbox, Communication | Communication is limited to levels 4–5 and requires `announcements:read`. |
| Settings and accountability | Documented Population, Audit Log, Roles and Permissions | Documented Population is State-only with `population_estimates:manage`; Audit Log requires `system:read_audit_logs`; Roles and Permissions is State-only with `rbac:read`. |

The test fixtures render eight role menus. Current demo-menu differences are: all eight roles see the common pages above; pastors additionally see Count Review and Audit Log; Group, Region and State roles additionally see Organization; Region and State roles additionally see Communication; both State roles additionally see Documented Population; the State Overseer additionally sees Roles and Permissions. In live mode each item is still gated by the permissions returned for that signed-in account.

The compact bottom navigation now applies the same read grants to People, Church and Finance shortcuts. Inbox and Dashboard remain available. The mobile full menu remains reachable from the Menu button.

Mobile review found a concrete source of the clipped group and region cards: a later CSS rule assigned a second auto-sized grid column to the coverage cell. On narrow screens that column shrank the name and metric area to only a few characters. The final mobile rule now puts every card row in one full-width column, with the name, coverage, then two-column figures. It also keeps the review count in the actual final table column, uses plain badge wording, displays waiting age in hours, and separates the conflict color from returned.

The authenticated live-site sweep remains opt-in because it needs storage-state files for all four scopes. Local Playwright tests render the real sidebar for all eight personas at 360, 390 and 768 px and exercise the dashboard child cards at the same widths. See `NAVIGATION_CONSOLIDATION_REPORT.md` for implementation and test status.

### Previous menu structure recorded for comparison

The previous menu grouped entries under Core, People, Church Data and More. Dashboard/Inbox were under Core; Workers/Members/App Users under People; Programs, Program Counts, Count Review, both meetings, Offerings & Tithes, Newcomers and Attendance under Church Data; Workflows, Fellowship, Organization, Communication, Reports and Roles & Permissions under More. Live Officials was suppressed. The level and permission differences are now listed in the consolidation report's persona table. Finance Analytics was reachable as a tab inside Reports; Documented Population was linked from the dashboard rather than the main navigation.
