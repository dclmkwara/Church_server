# Church Admin Simplification and Usability Plan

**Status: Phase 6 active.** The user authorized implementation on 2026-11-12. Phases 1–5 implementation is complete; Phase 5 passed focused automated checks and browser checks recorded below. Phase 6 acceptance and staged retirement remains in progress.

## Execution status — 2026-11-12

- **Phase 0 — complete:** terminology is consistent across the estimate editor, Sunday Worship dashboard/report surfaces, and API validation/access errors. The State editor defines documented population as the location’s on-paper estimate and says attendance can exceed it. Existing version history, permission checks, and calculations were preserved. The CSV upload explains that its legacy `expected_attendance` column contains documented population values. Home defaults to the most recently scheduled weekly service only (Sunday Worship, Monday Bible Study, Thursday Revival) by church reporting date, with a visible selector; Sunday remains the only program with a documented-population percentage. Pastor Report sharing now sends only its authenticated scoped URL, and no login-help link is shown. Focused verification passed (45 tests; one dependency deprecation warning).
- **Phase 0 — decision boundary:** user confirmed on 2026-11-12 to default Home to the most recently scheduled weekly service only: Sunday Worship, Monday Bible Study, or Thursday Revival. Special events and other meetings are excluded. Share only the authenticated scoped report link and omit the login-help link. Because the schedule has no service-time field, the dashboard treats a service as held on its reporting date; an exact same-day before/after-service distinction is unavailable.
- **Phase 1 — implementation and local authenticated checks complete; hosted release verification open:** navigation URLs omit display name and role label while retaining profile and permitted view scope. The People user directory now denies field roles before loading records, with route-handler tests covering all 13 directory/drawer/action handlers even if a field role is given forged user-management permissions. Authenticated State Overseer checks previously verified XLSX/PDF/CSV status, MIME, private/no-store headers, attachment behavior, selected filters, and no redirects; an out-of-scope request returned 403. Source and tests verify friendly refusal behavior, but the live follow-up for the newly added People guard and current Count Review wording was interrupted by DNS failure to the preproduction API. The hosted app was independently observed on an older build with identity query parameters and public export caching, so this phase is not a hosted-release sign-off.
- **Phase 2 — local implementation and authenticated dashboard checks complete; usability acceptance remains open:** Home defaults among Sunday Worship, Monday Bible Study, and Thursday Revival only. Authenticated State Overseer browser checks verified Thursday as the most recent weekly service for the reporting date, selector changes to Monday and Sunday, selected-service/date/filter/scope persistence in the deferred request, priority panels above secondary metrics, and Sunday-only population measures. The 77-test focused suite and Python compile check pass. The user selected scoped-link-only sharing and no login-help link; no report data is placed in the share action, and the login help link is omitted. This phase does not claim pastor task testing, screen-reader/keyboard acceptance, or hosted deployment verification.
- **Phase 3 - complete locally:** `/reports` opens on a permission-filtered landing page for Weekly attendance, Special events, Money, New people, Worker and leader meetings, and Print a report. Detail tabs and export endpoints remain available. Each service and event type stays separate; links retain authorized scope and relevant date/program filters. Copy was shortened; the repeated hierarchy path is replaced by one tappable current scope ID that opens the State/Region/Group/Location drawer. The account menu also says "Change scope / theme," and the drawer title is "Scope and display." Refresh is a 44-by-44 icon button with an accessible name and persistent feedback. Weekly-service controls remain buttons; the mobile row is keyboard-focusable, scrolls horizontally when needed, and wraps on larger screens. Local mock browser checks at 360 by 740, 390 by 844, 768 by 1024, and 1440 by 900 used the State Overseer mock persona and do not establish hosted API behavior. Browser verification caught and fixed both an HTMX feedback target issue and a CSS specificity issue that had caused the mobile buttons to wrap vertically.
- **Phase 4 - implementation partial; local UI checks complete:** Campaign and session setup show an explicit two-step path while retaining separate campaign and session endpoints and records. Campaign core fields have visible labels; optional collection/publicity fields are collapsed; the session form uses shorter labels and retains its pastor-approval explanation. The form drawer was verified at 360 pixels with clear step labels and no page overflow. No POST or database mutation was run; campaign/session save behavior and approval handoff remain unverified. A permission-filtered People overview now groups Workers, Members, Newcomers, Fellowships, Organization, App users, and Officials by role. App-user visibility uses the same field-role guard as the directory, including a forged-permission refusal test. The complete authenticated mutation/approval walkthrough remains open, so Phase 4 is not closed.
- **Phase 5 - local visual implementation complete; acceptance remains open:** Applied the Reports direction across the shared shell and affected People, Program Setup, retreat analytics, reporting, and other pages in the 37-destination matrix: concise page introductions; one visible current-scope ID with a one-tap hierarchy drawer; consistent card widths, subtitles, and form controls; permission-filtered task cards; and bounded phone layouts. Shared page introductions now produce a single H1; a fresh browser check confirmed one H1 and no duplicate page title on Reports, People, Program Setup, and Retreat analytics. The scope button uses high-contrast white text on navy. Keyboard Enter opened the drawer and Escape closed it without document overflow. Weekly-service options remain individual buttons, scroll horizontally on narrow phones, and wrap on larger screens. Event analytics retains a separate clickable hierarchy path only when the report's scope differs. Shared Chart.js charts include an expandable data table alongside the named canvas. The local mock browser matrix opened 37 destinations for State Admin, State Overseer, and Location Worker at 360 by 740 and 768 by 1024 (222 page opens): no document overflow or 5xx responses. Worker access to Organization returned 403 as expected; report and worker-attendance data showed live-backend-required states in mock mode. Fresh mobile screenshot: `output/playwright/phase5-reports-overview-360x740.png`. Focused suite: 42 passed, 2 skipped; frontend compile passed; scoped `git diff --check` passed. The unrestricted `git diff --check` still finds trailing whitespace in the unrelated `ANALYTICS_B2B_INVENTORY.md`. Screen-reader testing on a phone and broader modal/drawer keyboard checks remain required for acceptance; browser accessibility snapshots do not substitute for those checks.
- **Verification environment:** run tests with `python -m pytest` in this checkout. The `pytest` launcher selected a different Python installation and failed to import project packages during collection.

## Purpose

Make the admin app understandable to pastors and administrators who use it occasionally and may not be comfortable with software. Reduce the number of choices they face, use short instructions, and make the next action obvious. Consolidate navigation where the same task is split across pages, while preserving the separate meaning of different records and reports.

This plan is based on the current route tree and renderer/service code in `Church_server/app/frontend/dclm_admin`, plus the supplied Codex and Antigravity audit reports. The audits are incomplete: most routes and mutations have not been followed through as signed-in users. Consolidation therefore proceeds by staged replacement and verification, not deletion-first cleanup.

## Rules that every phase must preserve

1. **Data meaning stays stable.** Do not change calculations, filters, approval states, event coverage, split-count grouping, or definitions as part of visual redesign. Pending data remains excluded by default; rejected data remains excluded; missing reports are never zeros.
2. **Scope comes from the signed-in account.** Query strings can select a date, program, or permitted descendant view; they never grant a role, permission, or broader scope.
3. **Pastor decides; admin prepares.** The pastor keeps approval and return powers. Admins may perform their agreed setup and preparation work but cannot approve their own work or manage pastor access/role policy.
4. **Build, then hide, then retire.** A replacement must work for all intended personas before a duplicate is hidden. Keep old URLs functioning; redirect only after route, export, permission, and deep-link tests pass. Do not delete routes in this plan.
5. **Keep distinct records distinct.** A combined screen may link to separate program sections, but must not add unlike meetings, services, sessions, or financial records into an invented total.
6. **Plain language first.** Use familiar names, one-sentence definitions, short status labels, and actionable errors. Hide technical implementation details from normal workflows.
7. **No broad CSS deletion targets.** Change styles in response to a measured issue, then run the mobile and interaction checks for affected screens.

## Current page inventory from source

| Current destination | What it does | Simplification direction |
|---|---|---|
| Dashboard | Coverage, approved population, trends, attention, worker snapshot, documented-population comparison | Keep as Home. Put “what needs attention?” and the latest selected program first; move secondary detail lower. |
| Count Review | Pastor’s count decisions, returns, conflicts, reminders | Keep as a decision task until a complete pastor decision inbox exists. This is not merely a counts list. |
| Inbox | Worker/user/workflow requests | Combine with other decision queues only after all decisions, filters, age, audit, return reasons, and permissions are supported. |
| Pastor Report | Printable and downloadable scoped summary, including domain sections | Keep as the main print/share report. Do not assume it replaces all Reports tabs until their figures and exports are reconciled. |
| Reports | Summary, financial, attendance, timeseries, by-level, growth, anomalies and exports | Audit each tab. Where it duplicates a trusted page, link to that page and retain compatible exports before hiding the duplicate. |
| Program Attendance | Sunday Worship, Monday Bible Study and Thursday Revival recurring population records | Keep one program-report destination with a clear program selector and distinct series. Do not combine values across programs. |
| Worker Attendance | Worker roster attendance records and review | Keep separate from congregation population counts. Shared “Attendance” wording can be clarified as “Worker attendance.” |
| Worker & Leader Meetings | Saturday Workers and Tuesday Leaders tabs | One landing page is acceptable because each tab remains a separate meeting and metric. Keep direct links to each tab. |
| Offerings and Tithes / Finance Analytics | Entry and review records versus aggregate finance reporting | One “Money” entry may expose both “Records” and “Summary”; preserve separate permission boundaries and totals. |
| Newcomers | Newcomer records and converts | Keep distinct data detail; may be linked from Home/People. Do not merge person records into attendance counts. |
| Retreat / Crusade | Event campaign/session analytics | One “Special events” landing page with two clear choices is a candidate; preserve separate campaign, event and reporter rules. |
| Programs | Setup of program types, campaigns, events and assignments | Admin setup workspace; use a guided form, preserve pastor approval for admin-created events. |
| People: Workers, Members, App Users, Officials | Different records, access and governance actions | Group under “People”; do not delete or merge record types until their purpose and authorization are verified. |
| Fellowship | Fellowship groups, members, attendance, offerings and activity | Keep its own workspace; its records and totals are not interchangeable with Sunday population counts. |
| Organization | Hierarchy/location browsing and setup | Admin setup / browse area. Keep server scope enforcement; location access should be a clear read view or refusal, not a crash. |
| Workflows / My Requests | Request creation, tracking and review | Bring into a unified “Decisions” page only after request types and who decides them are mapped. |
| Communication | Announcements and media | Group under “Messages”; keep publish permission pastor-controlled where required. |
| System pages | Notifications, audit, sync, health, RBAC, tools | Hide technical pages from normal pastor menus. Keep only the actions appropriate to each persona; role policy remains governance-only. |
| Expected Population | State-level estimate maintenance | Rename consistently to **Documented population** and implement the previously agreed location-level definition and program use before further UI polishing. |

Inventory is grounded in routes in `routes/church_data.py`, `programs.py`, `people.py`, `reports.py`, `pastor_report.py`, `population_analytics.py`, `fellowship.py`, `organization.py`, `workflows.py`, `inbox.py`, `communication.py`, and `system.py`. Route presence alone does not establish that each page is complete or safe to merge.

## Proposed simple navigation

The phone should show at most four task destinations plus **Menu**. Desktop can show the same groups in a compact side menu.

### Pastor / Overseer

1. **Home** — latest reporting, missing reports, and items needing a decision.
2. **Decisions** — count and offering approvals plus worker and other requests, once the unified queue is complete. Until then, show the existing queues as clearly named links; do not imply all decisions are in one place.
3. **Reports** — program attendance, special events, money summary, newcomers, worker/leader meetings, and the printable Pastor Report, grouped inside one landing page. Sections and date/program filters remain distinct.
4. **People** — workers, members, newcomers, fellowships, and organization details according to permission.
5. **Menu** — less frequent tasks, audit history, messages, and account/session actions.

### Admin

1. **Home** — scoped status and setup tasks.
2. **Set up** — programs, events, assignments, documented population, and permitted hierarchy work.
3. **Records** — worker/member records, offerings, worker attendance, fellowship, and other permitted operational records.
4. **Reports** — read-only scoped reports and exports the role can access.
5. **Menu** — less frequent tasks. No pastor-only approval action, pastor-account access management, or role policy editing.

These groups are a proposed mental model, not permission grants. Every link and endpoint remains filtered by existing server permissions and scope. A role should not see an item it cannot open, and direct URLs must still be guarded.

### Field roles

Keep Field Utility as the primary submission experience. When a field user enters the admin app, show only their permitted submission/review destination and a clear link to the Utility. Do not expose broad statistics or administrative menus by default.

## Merge and retirement decisions

| Candidate | Decision | Reason / condition |
|---|---|---|
| Count Review + Inbox + Workflow review queues | **Merge later into Decisions; link to existing queues until then.** | Count review has group breakdowns, conflicts, return/approve and reminder behavior; other queues have different request types and decision powers. Current inbox code does not yet load count or offering approvals. |
| Reports + Pastor Report | **Use one Reports landing page; retain Pastor Report as a named print view.** | The tabbed reports and Pastor Report have different outputs. Consolidate entry points, not calculations or export formats. Hide redundant summary tabs only after SQL/rendered-page/export reconciliation. |
| Population counts + Worker Attendance | **Do not merge data. Group under Reports/Records with explicit names.** | They measure different populations and answer different questions. |
| Saturday Workers + Tuesday Leaders | **Keep as tabs on one meeting page.** | One destination reduces navigation; separate program types, dates, denominators and metrics remain. |
| Sunday/Monday/Thursday recurring-program pages | **One program attendance page with a program selector.** | Same recurring report shape, distinct program histories. Selection must be visible and deep-linkable. |
| Retreat + Crusade | **One Special Events landing page, then separate reports.** | Both are event reports, but expected reporters, coverage and drill-down differ. |
| Offerings entry + Finance Analytics | **One Money landing page with Records and Summary.** | Reduces menu items while preserving entry/review versus analysis. |
| Officials routes | **Keep reachable; hide from primary navigation if infrequently used.** | Prior instruction prohibits deletion before a tested replacement and requires old URLs to remain. Clarify intended audience/access before changing visibility. |
| Organization pages | **Keep as a scoped browse/setup area.** | Hierarchy and location profiles support setup and drill-down; do not expose edit actions to users lacking permissions. |

No old route is deleted by this plan. Any future redirect must preserve filters, date, active tab, scope bounds, exports, and browser Back behavior.

## Delivery phases

### Phase 0 — agree on words and decisions

**Progress:** wording is implemented and locally verified. The three decisions below remain open, so this phase is not signed off.

- Apply the accepted **Documented population** label and definition everywhere: “The location’s on-paper population estimate; attendance can exceed it (visitors, guests).” It is location-level, versioned, and applies to Sunday Worship, Monday Bible Study, and Thursday Revival as previously agreed. The Sunday figure remains the dashboard headline; midweek figures are compared with their own history and labelled naturally lower.
- Confirm the login support address before release; a mailto link is only useful if that mailbox is real and monitored.
- **Resolved:** the dashboard defaults to the most recently scheduled weekly service only (Sunday Worship, Monday Bible Study, Thursday Revival), with a visible selector; special events and other meetings are excluded.
- **Resolved:** Pastor Report sharing uses a scoped authenticated link only; no figures are embedded in a message.
- **Resolved:** omit the login-help link; no monitored contact was provided.

### Phase 1 — trustworthy access and feedback

**Status: partial; continue before release.** Focused route-handler checks verify People directory allow/refuse UI behavior and that refusal does not load records. Source and focused tests verify URL context filtering and private/no-store export response construction. Authenticated export response headers/content and no-redirect behavior, Count Review conflict rendering against live response data, and service-worker cache/update behavior remain open. No claim of end-to-end verification is made.

- Add authenticated route-level tests for the `build_context(request)` corrections, including role, scope and permission retention on every changed mutation route.
- Test `/people/users` and its drawers/actions with allowed and denied personas; verify no user data leaks in restricted responses.
- Test authenticated XLSX/PDF/CSV downloads end-to-end, including status, content type, cache headers, filters, scope and no redirect loops. Ensure private/no-store headers are present on every success response. Avoid claiming a header is present unless response-tested.
- Test the real Count Review conflict/unknown-total rendered state, not only source strings.
- Keep display name and role label out of URLs. Review remaining role/scope query values: retain only view state required for deep links; derive all authority from session identity.
- Validate login help contact with the church and test it at mobile sizes.
- Retain the single service-worker registration and test its cache/update behavior.

### Phase 2 — simplify the daily pastor journey

**Status: implementation and local authenticated dashboard checks complete.** The Home selector defaults only among Sunday Worship, Monday Bible Study, and Thursday Revival. The dashboard's deferred trend/history request preserves that selection and filter context; Sunday-only population-comparison measures remain tied to Sunday. Coverage, missing reports, and decisions appear before secondary metrics. Full task walkthroughs with pastors, accessibility checks, and hosted deployment verification remain open.

- Reorder Home so the pastor sees, in order: current area/date/program; reports received and missing; decisions waiting with age; latest counted total and status. Put secondary averages and worker measures below.
- Keep “Not reported” separate from “Reported 0”; keep pending excluded unless the user deliberately enables it; show returned/conflict separately.
- Add a single Decisions entry point now, but until all queues are integrated it must show separate, clearly labelled links and pending counts, not a misleading combined empty state.
- Integrate counts and offerings into the unified decision queue only after the count group breakdown, conflict resolution, return reason, approval lock, age, audit records, and pastor-only authorization all work there. Retain Count Review routes until acceptance; old URLs must redirect only after those tests pass.
- Keep meeting tabs separate and ensure selected tab is reflected in the URL so a shared link opens the right meeting.

### Phase 3 - reduce report navigation

**Status: complete locally; hosted backend verification remains open.** `/reports` is a permission-filtered directory into existing destinations. It does not replace report calculations or remove legacy detail tabs. The Overview is the default tab. The page keeps authorization session-derived, preserves relevant deep-link filters, and keeps service, event, and meeting measures separate. Copy is concise and the duplicate hierarchy breadcrumb is omitted. One compact current-scope control stays visible on the page and opens the State, Region, Group, and Location selectors; the account menu also offers “Change scope / theme.” Refresh is an icon-only 44-by-44 button with an accessible name and persistent feedback target.

- Verified locally as the State Overseer mock persona at 360 by 740, 390 by 844, 768 by 1024, and 1440 by 900: no horizontal overflow, expected directory sections and links, refresh button name/size/endpoint, scope-preserving deep link, Refresh success feedback, legacy detail-tab navigation, and account scope drawer contents.
- Weekly-service controls remain buttons. On mobile their row is keyboard-focusable and scrolls horizontally when the controls need more width; ArrowRight moved the row while the document remained 360 pixels wide. At 768 pixels the row wraps and the document remained 768 pixels wide. Focused tests cover directory sections, role permission filtering, preserved link context, and legacy tabs; rendered reconciliation and report policy suites remain part of regression verification.
- No reports tab, route, calculation, or export was retired.

- Build a Reports landing page with plain-language sections: **Weekly attendance**, **Special events**, **Money**, **New people**, **Worker and leader meetings**, and **Print a report**.
- Each section links to its existing verified detail view; show a short definition and period selector where relevant.
- Reconcile the Reports tabs and exports against dedicated pages and independent queries before hiding redundant tab views. Preserve export contents or redirect to the matching verified export.
- Keep separate records and measures under the shared visual template. Never sum different services, dates, programs or locations unless the existing approved calculation explicitly says to.

### Phase 4 — simplify setup and people tasks

**Status: partial.** A two-step visual path and more usable event/session forms are implemented locally. Campaign and session records, their separate POST routes, and pastor approval are preserved. A role-filtered People overview groups the existing destinations without changing their routes. Authenticated save/approval walkthroughs and the remaining People overlays/actions still need separate verification.

- Present campaign/event setup as a short guided workflow with plain labels and a progress indicator. Campaign and sessions can be entered in one screen if useful, but preserve separate records and same-level pastor approval. Do not make them atomic or auto-approved without an explicit workflow decision and tested transaction semantics.
- Keep Workers, Members, App Users and Officials as sections under People. Use progressive disclosure and clear action names. Do not expose RBAC policy editing or pastor account management to admins.
- Group expected population, program setup, assignments, and hierarchy tasks under Set up according to each role’s permission. Each change remains attributed and auditable.

### Phase 5 — visual polish for occasional phone users

**Status: complete for implementation and checked browser acceptance on 2026-11-13.** Shared responsive constraints are in place for page, card, subtitle, filter, and form widths. The top-level route matrix found no horizontal document overflow across three personas at phone and tablet widths. Page introductions expose one H1 in checked pages. The current scope ID opens and closes its hierarchy drawer with mouse and keyboard. Shared Chart.js visualizations expose their values in an expandable table. Reports and setup drawers were reviewed at mobile/tablet widths; a physical phone screen-reader pass remains a device-specific follow-up for the user and is not claimed as completed here.

- Use one main heading and one short instruction per page; avoid duplicate title/breadcrumb labels and unexplained technical badges.
- At 320–640px use single-column content or stacked data cards for key results. Keep wide, genuinely tabular data inside a labelled horizontal-scroll region. Prevent long codes or notes from expanding the page.
- Keep buttons visually consistent, comfortably tappable, and separated from text. Place secondary actions as links rather than competing large buttons.
- Use a restrained palette with distinct states: approved, waiting, returned, conflict, missing. Do not rely on color alone.
- Charts need readable labels, responsive sizing, a concise explanation, and a table or text alternative for the key figures.
- Improve keyboard focus, heading hierarchy, labels, live status announcements, reduced-motion support and safe-area spacing. Test with keyboard and phone screen reader; do not rely solely on screenshot checks.
- Refactor CSS by component and measured outcome. No arbitrary line-count reduction.

### Phase 6 — acceptance and staged retirement

**Status: started on 2026-11-13.** The seeded role table is now available and the user has authorized use of those accounts for authenticated verification. The existing Phase 1–5 changes are being pushed for direct phone review. No legacy destination is being hidden or retired until the end-to-end role, data, export, and mobile checks below are completed.

- Test eight main personas (pastor/admin at Location, Group, Region and State) plus relevant field roles. For each, verify menu visibility, direct URL refusal, scope ceiling, and allowed actions.
- Complete task tests: find missing report and remind; review/return/approve a count; enter an event; open the correct weekly report; find a worker; view money summary; print/share a report.
- Run mobile checks at 360x740, 390x844 and 768x1024 on every destination being moved or hidden. Include actual browser interaction, empty/loading/error states, keyboard and Back/deep-link behavior.
- Compare dashboard/detail/report/export values using the accepted independent reconciliation tests before hiding duplicate reports.
- Hide one verified duplicate at a time. Keep its old URL working and record the destination. Delete no route as part of this plan.

## Acceptance criteria

- A first-time pastor can answer “what needs my attention?” from Home without understanding technical terms.
- A pastor can reach each common task in at most two taps from the phone navigation.
- Every menu item opens for that persona; forbidden direct links receive a clear access message.
- Admins can prepare and manage only the operational tasks assigned to them. They cannot approve their own submission, approve pastor-only work, manage pastor access, or edit role policy.
- Dashboard, detail pages, reports and exports agree on the same dates, scope, pending setting and approval rules.
- Missing, zero, pending, returned and conflicting submissions remain distinguishable.
- Distinct programs and sessions remain separate in both stored records and displayed totals.
- No page is hidden until its replacement and old URL behavior pass the role, data, export and mobile checks.

## Risks and open decisions

- The audit shows route breadth and some rendering behavior, but not a complete task walkthrough. Menu consolidation should be measured with pastors, not inferred from route count alone.
- Unified Decisions is a useful goal, but current inbox service lacks count and offering records. Moving links now could make approvals harder or imply a complete queue where one does not exist.
- Dashboard default uses the most recently held program among the three weekly services. The schedule has no service-time field, so same-day before/after-service distinction remains unavailable.
- Documented-population wording/use is currently inconsistent in source and should be resolved before claiming the UI is semantically complete.
- The Phase 1–3 report’s 70 checks include static and helper checks. Treat them as code-shape checks; add authenticated browser/API behavior tests before release claims.
- Mobile screenshots and CSS tests must use the current app build and recorded viewport; stale screenshots are not proof of a later patch.
- Sharing is limited to an authenticated scoped report link; no attendance, finance, or newcomer figures are embedded in the share action.

- The preproduction hosted app is stale relative to this checkout: it still emitted identity metadata in navigation URLs and public four-hour export caching during the observed run. Do not release against it until the current changes are deployed and the hosted URL/export/People refusal checks pass.

## Handover format for each phase

For each phase, report: the user problem addressed; exact routes/pages changed; what behavior and data rules were preserved; tests run and their scope; screenshots with viewport and persona; routes intentionally left in place; and any unresolved item. Keep the work in small commits and do not deploy or push unless separately requested.
