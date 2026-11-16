# Pastor First Data Presentation: Page by Page Implementation Plan

**Status:** Planning artifact; no application implementation is included here.  
**Audience:** Church_server product owner, implementation agents, and reviewers including Gemini.  
**Product direction:** Make the first screen answer, in plain language, “How is the part of the church I oversee doing, and where should I look next?” Deeper detail is available by choice.

## 1. Purpose and decision rule

This plan turns the agreed data-presentation direction into a bounded implementation brief. The application already has working reporting, event, people, worker, and review capabilities. The task is to arrange and explain those capabilities so pastors and administrators can understand them at a glance, within their authority, especially on a phone.

Use this rule when implementing or reviewing any page:

> Show the user the useful summary for their own jurisdiction first; identify the direct area that needs attention; make deeper detail an explicit next step; preserve the meaning and provenance of every number.

An implementation agent must not turn a suggestion into new product scope. If a requested detail is not established below or supported by an existing source and workflow, record it under **Open decisions / proposed additions** and wait for the product owner. Do not quietly add it to a page, data model, or workflow.

## 2. Locked product principles

1. **Scope before detail.** A leader sees the aggregate for the jurisdiction they govern and their direct subordinate units. They do not land on a list of distant locations or raw records.
2. **Three-second orientation.** The first viewport uses a clear page title, selected period, scope label, a small number of meaningful measures, and one obvious next action or drill-down.
3. **Plain language.** Prefer “Reported attendance,” “Expected population,” “Needs review,” and “No report received” over unexplained analytics terms. Define any necessary term where it first appears.
4. **Summary first, detail on demand.** Tables, individual records, and lower-level breakdowns are available after a deliberate selection. Do not put a dense data grid ahead of the summary.
5. **Phone first.** Important values and the next action must work at narrow widths without relying on hover, tiny legends, or horizontal scrolling as the only way to read the page.
6. **Honest data states.** A reported zero, no submission, pending submission, and unavailable data are different states. Never render missing as zero or imply that pending data is approved.
7. **Preserve established workflows.** Reorganize entry points only after their existing route, permissions, and successful task path are mapped. Do not remove or hide an operational route as a side effect of redesigning navigation.
8. **Use the configured source.** Events, their sessions, event days, count sections, and worker units can vary. Show configured values; do not invent a fixed catalogue.
9. **Comparable values only.** Label the date range, scope, approval state, and denominator for every rate or comparison. Do not compare unlike periods or count types.
10. **Access follows existing authority.** Page visibility and drill-down do not grant new data access or approval powers.

## 3. Confirmed operating and data rules

### 3.1 Jurisdiction and drill-down

| User’s governing level | Initial aggregate | Direct children shown | Further drill-down |
|---|---|---|---|
| State pastor/admin | State | Regions | Region → group → location, subject to authorization |
| Region pastor/admin | Region | Groups | Group → location, subject to authorization |
| Group pastor/admin | Group | Locations | Location detail, subject to authorization |
| Location pastor/admin | Location | Relevant section/fellowship detail only where configured and supported | No unrelated jurisdiction |
| Assigned worker/usher | Assigned task and submission context | Only assigned event, session, site, or count assignment | No analytics-wide access implied |

The selected scope must stay visible while drilling down, and the user must have a clear way back to the parent level. A direct URL must enforce the same scope rules as navigation.

### 3.2 Recurring weekly programmes

The configured recurring programme set currently includes Sunday Worship, House Caring Fellowship, Monday Bible Study, Tuesday Leaders’ Meeting, Thursday Revival Hour, and Saturday Workers’ Meeting. The church’s agreed reporting focus is:

| Programme | Attendance source | Giving shown |
|---|---|---|
| Sunday Worship | Head count: adults M/F, youth M/F, children M/F | Tithes and offerings collected together; show one combined collection for this Sunday occurrence |
| Monday Bible Study | Same six head-count groups | One combined collection for this Monday occurrence |
| Thursday Revival Hour | Same six head-count groups | One combined collection for this Thursday occurrence |
| Saturday Workers’ Meeting | Marked attendance against eligible active workers in scope | No offering |
| Tuesday Leaders’ Meeting | Marked attendance against eligible active workers in scope | No offering |

Sunday, Monday, and Thursday collections remain **separate from each other**. “Combined” means tithe plus offering for that one programme occurrence; it does not mean a combined weekly total. Do not display a giving card for workers’ or leaders’ meetings.

Workers’/leaders’ attendance is marked against the recognized workers whose status is Active and who are eligible in that scope. For a historical meeting, the eligible roster/denominator used for that meeting must be traceable; later worker status changes must not silently rewrite the past denominator. The current source path has an active-status filtering/snapshot gap to resolve before showing a reliable rate.

Each location has an estimated population. It is an expected-population reference, not a census of members and not a verified actual attendance ceiling. It may be compared with attendance on any programme day. Visitors and guests can make the reported head count larger than the estimate, so a ratio above 100% must remain possible and must not be clamped.

### 3.3 Retreats and crusades

- Retreats are generally held twice each year, around Easter and December, commonly over five or six days. Actual dates, day count, programme names, and sessions are determined for each event; they are not fixed in code.
- A retreat is hosted at a group or region. Its aggregate report terminates at the host scope: a group-hosted event at that group, a region-hosted event at that region. Do not allocate or drill retreat attendance into home churches.
- Retreat count areas may be configured as three or four channels/buildings, with multiple counters covering sections. Render the event’s configured sections and prevent duplicate section/group submissions according to the existing count-group/service semantics.
- Crusades are held monthly in a designated state and may span five or six days with multiple configured programme sessions per day. Preserve the distinction between Alpha-site attendance and satellite participation from church locations.
- A state leader can see the overall crusade view and separate Alpha and satellite figures. Lower-scope users see only the satellite information their permissions allow.
- A count per configured event session is session participation. Adding sessions together does **not** establish a unique-person total. Label any sum accordingly.
- Newcomer/convert collection and assigned usher tasks are event workflows already present in the system. Present their existing captured/reviewed totals and routes without inventing conversion, follow-up, or discipleship rates that the source does not provide.

### 3.4 Workforce and application users

Church workers are the broader recognized workforce. Application users are the subset with accounts and access; these populations must be shown separately. Worker unit/department values are data-driven/open text; do not hard-code a department taxonomy. A worker’s status and approval status are separate concepts and must not be collapsed into a single ambiguous “active” state.

## 4. Information architecture

The first Gemini proposition’s five subject hubs are retained as the product structure:

1. **Overview** — immediate jurisdiction pulse and direct areas for attention.
2. **Weekly Services & Giving** — recurring programme attendance and per-occurrence combined collections.
3. **Major Programs** — retreat and crusade event/session reporting.
4. **People & Demographics** — estimated population and reported age/gender head-count composition.
5. **Workforce & App Access** — recognized workers, marked meeting attendance, and the separate application-user population.

Operational actions remain reachable in context and through their existing routes. A single “Action Center” may be an entry point only after the source-backed task feeds are mapped. It must not be described as containing every approval, count review, or notification unless implementation actually unifies those feeds. Reports/exports remain an explicit secondary destination, not an alternate source of definitions.

## 5. Page specifications

### Page 1 — Overview

**Purpose:** Let a pastor orient to the current state of their jurisdiction, see which direct area warrants attention, and choose a useful next step without reading a report first.

**First viewport, in order:**

1. Page title and a plain scope label, such as “State overview · [state name]”.
2. Reporting period / latest available period and a visible data freshness or submission-coverage cue.
3. Three to five summary cards selected from the established data: latest Sunday attendance, Sunday combined collection, latest weekly reporting coverage, active worker count, and open items that this role can actually act on. Do not force all cards on every role if data is unavailable or irrelevant.
4. A compact direct-child comparison/list (regions for state, groups for region, locations for group). Lead with the measure most useful for the selected period, and identify missing reports distinctly.
5. Clear links to Weekly Services & Giving, Major Programs, People & Demographics, Workforce & App Access, and relevant pending work.

**Visuals:** Use a simple trend for a chosen measure across comparable periods and a ranked direct-child list/bar only where the comparison is valid. Use readable labels and direct values; color must not carry meaning alone. A map is not required by this plan.

**Drill-down:** Selecting a direct child opens that child’s Overview context and preserves the period. Do not open raw location rows from a state overview in the first viewport. Drill-down obeys the jurisdiction table.

**Data and source path:** Existing role-aware dashboard in `app/frontend/dclm_admin/routes/dashboard.py`; summary and analytics adapters in `app/frontend/dclm_admin/communication/dashboard_service.py`; scoped recurring analytics in `routes/analytics_dashboard.py`; reporting policy/source services under `app/services/analytics/`.

**States:** Show “No report received” for missing submissions; show “Reported: 0” for a submitted zero; show “Awaiting review” for pending items; identify partial coverage before showing a jurisdiction total. On load/error, keep the scope and period controls visible and offer retry. Never imply a complete total when child reporting is incomplete.

**Allowed actions:** Change period, open a direct child, open the relevant hub, and open an existing authorized review/action route. Do not add approval buttons whose permission/source path has not been verified.

### Page 2 — Weekly Services & Giving

**Purpose:** Explain what was reported for each recurring programme and help the leader see participation, collection, reporting coverage, and change over time.

**Page shape:** A programme selector or clearly labeled programme sections for Sunday Worship, Monday Bible Study, Thursday Revival Hour, Saturday Workers’ Meeting, and Tuesday Leaders’ Meeting. Do not omit Tuesday Leaders’ Meeting. House Caring Fellowship is an existing configured programme; include it only where the user’s role and established reporting workflow make it relevant, and preserve its own identity rather than silently folding it into another day.

**For Sunday, Monday, and Thursday:**

- Show six head-count values: adults male/female, youth male/female, children male/female; show an overall reported head count as their sum only if the categories are complete and valid.
- Show that programme occurrence’s combined tithe-and-offering collection as a separate measure. Never combine it with the other programme days in the default view.
- Compare reported head count with the location population estimate or properly aggregated estimate when available. Label it “compared with estimated population,” explain that guests can make it exceed 100%, and do not call it membership coverage.
- Show direct-child summaries and reporting coverage before offering deeper location detail.

**For Workers’ and Leaders’ Meetings:**

- Show marked attendance, eligible active-worker denominator, and attendance rate with the denominator and date semantics visible.
- Use only supported statuses from the meeting workflow. Do not invent “late” or “excused” categories if the stored attendance workflow does not capture them.
- No giving chart or offering field.
- Until active roster eligibility and historical denominator behavior are verified/fixed, show counts with a clear “rate unavailable” state rather than a misleading percentage.

**Visuals and drill-down:** A small time trend for the selected programme; a direct-child comparison; then optional age/gender stacked representation and subordinate rows. On mobile, prioritize totals and use a simple labelled list if a chart cannot remain readable.

**Source paths:** `routes/analytics_dashboard.py`, `routes/population_analytics.py`, `routes/church_data.py`; `app/services/analytics/program_config.py`, `sunday_worship.py`, `program_occurrences.py`; `app/models/offerings.py`, `expected_population.py`; worker meeting analytics and attendance API paths.

**Existing route parity:** Preserve report submission, meeting attendance marking, and review routes such as the existing count review. This page is an analytics/presentation hub and must not accidentally replace field submission or approval flows.

### Page 3 — Major Programs

**Purpose:** Give a leader a clean view of major events and a faithful, session-by-session report for the event’s actual configuration.

**Event list:** Show event name/type, host scope, date range, status, submitted/review state, and an authorized action. Separate Retreat and Crusade filters/sections are acceptable. Do not infer event completion or approval from the mere existence of an event row.

**Event detail:**

1. Event identity, host jurisdiction, actual date range, and event status.
2. A daily/session matrix built from configured days and programme/session names.
3. Per-session attendance and coverage/review state.
4. For retreat, configured channel/building/section values and their counts; no home-location expansion.
5. For crusade, Alpha and satellite attendance are visibly separate. State-level page may additionally show a labeled overall participation sum. Lower scope does not receive Alpha counts.
6. Existing newcomer/convert captured/reviewed totals and assignment completion where supported, linked to the source workflow.

**Aggregation rule:** Session totals can be summarized as “total session participation” when useful, with an explanation that people may be counted in multiple sessions. Never label the sum “people reached,” “unique attendees,” or “total persons” without a source-supported deduplication method.

**Workflows:** Admin/head usher creates event and assigns workers. Matching-level pastor approves event schedule; pastor may grant the same-level admin approval permission. Authorized matching-level admins/pastors review assigned submissions according to current permissions; pastor retains highest authority. The event creator cannot approve their own schedule where the current rule applies.

**Source paths:** `routes/programs.py`; `app/services/analytics/program_occurrences.py`; count/event/assignment models and routes. The current retreat matrix contains an explicit region-only depth cutoff that conflicts with the confirmed group-hosted retreat rule; update the presentation/report scope to stop at whichever host level is configured. Keep the existing event setup and assignment workflow intact.

### Page 4 — People & Demographics

**Purpose:** Show the estimated size and reported composition of the church population in the user’s jurisdiction without suggesting that programme head counts are a unique-member register.

**Top summary:** Aggregated estimated population; latest available Sunday head count and its reporting coverage; latest reported adult/youth/children composition with male/female split. Identify the date of the attendance composition separately from the estimate’s effective date.

**Visuals:**

- Use an age-group comparison for adults, youth, and children, with male/female values and a readable text equivalent.
- Show population estimate distribution across direct children; permit step-by-step drill-down to location where authorized.
- Show estimate versus reported head count as two differently named measures. Never present the estimate as a verified census or the head count as a unique member list.
- If data is missing or incomplete, preserve that state and do not fill it from estimates.

**Meaning limits:** A Sunday attendance split is the composition of that reported programme head count. It does not establish the unique number of members in each age/gender group. Do not calculate demographic growth, retention, conversion, or membership ratios from these sources unless a separately verified source and explicit definition are approved.

**Source paths:** `routes/population_analytics.py`, `routes/analytics_dashboard.py`, `app/models/expected_population.py`, recurring programme count services, and dashboard service adapters.

### Page 5 — Workforce & App Access

**Purpose:** Make the size and distribution of the recognized worker body visible, distinguish that workforce from people who use the app, and show workforce meeting attendance at a meaningful aggregate level.

**Sections:**

1. **Church workers:** active, inactive/other statuses, pending recognition/approval where available, and distribution by configured unit. Do not hard-code unit/department choices.
2. **Workers’ Meeting / Leaders’ Meeting:** most recent marked attendance, eligible active roster denominator, rate only when denominator is reliable, trend across comparable meetings, and direct-child distribution.
3. **App users:** account count and distribution/status supported by current source, explicitly labeled “people with app access.” Keep separate from worker totals.
4. **Authorized detail:** individual worker or user records remain a deliberate drill-down, permission checked at the backend and route level. High-level views show sums by default.

**Actions:** Link to existing worker registration/approval, user approval, roster/attendance, and account management workflows only when the actor has permission. Do not promise password reset, worker transfer stages, or role grants on this page until the specific existing route and authorization are verified.

**Source paths:** `app/models/user.py`; worker meeting analytics; `app/api/v1/routes/attendance.py`; `routes/church_data.py`; `communication/workflow_service.py` and `routes/inbox.py` for their existing workflow categories.

### Page 6 — Contextual review/action entry points

**Purpose:** Help an authorized user find work that needs their attention without implying a universal unified workflow that does not exist.

**Presentation:** Page sections or links must name the actual task type and its source: count review, event schedule approval, assignment management/approval, worker registration or status workflow, and app-user approval. Each item shows scope, date/period, status, and a direct route to complete the work.

**Permissions:** Filter actions by current role, jurisdiction, and explicit permissions. Pastor remains highest authority at the level. Admin approval is available only when granted by that level’s pastor. Do not create a new authority by placing an action in a shared list.

**Reality boundary:** Existing `/inbox` feeds worker registration, user approval, and worker workflow requests; it is not known to contain all count, event, assignment, and offering reviews. Existing Count Review stays separately reachable. Notifications currently use polling; do not label them “real-time” or imply guaranteed delivery.

**Source paths:** `routes/inbox.py`, `communication/workflow_service.py`, `routes/church_data.py` Count Review, event routes/services, `app/api/v1/routes/notifications.py`, RBAC definitions in `app/db/init_rbac.py`.

### Page 7 — Reports and exports

**Purpose:** Provide print/export and period-based reports using the same definitions as the five hubs.

**Requirements:** Keep filter labels, scope, period, approval status, missing coverage, estimate provenance, and session-participation semantics in the report. Export totals must match the on-screen selected scope and period. Reports are a presentation/export surface, not a second business-logic implementation.

**Source path:** `routes/pastor_report.py` and existing report/export handlers. Preserve route compatibility while new hub entry points are introduced.

## 6. Shared page behavior and components

Implement once and reuse where it fits the existing FastHTML/FastStrap patterns:

- **Scope header:** selected jurisdiction, period, and parent navigation.
- **Metric card:** plain label, value, period, denominator/basis, approval/coverage cue, and optional detail link.
- **Coverage state:** complete, partial, no reports received, pending review, or unavailable; use only states represented or derivable from source records.
- **Comparison list:** direct children only, with values, status, and accessible drill link.
- **Trend:** consistent period selection and an explicit metric definition; avoid comparing different programme types by default.
- **Chart text equivalent:** accessible labels/table/list for every visual.
- **Empty/loading/error states:** preserve page context, explain what happened in plain language, and provide an appropriate retry or route.

Do not introduce a new chart library or dashboard framework solely because it is suggested in this plan. Check existing FastStrap chart/component capabilities and project dependencies first.

## 7. Implementation sequence and gates

Each phase is reviewable and should preserve current task paths until parity is demonstrated.

### Phase 0 — Data and permission contracts

- Trace each displayed measure to its actual source, status filter, scope filter, period, and denominator.
- Verify admin/pastor role capabilities and delegated same-level admin approvals.
- Resolve/record active-worker eligibility and historical meeting denominator behavior.
- Confirm aggregation completeness and estimate roll-up rules for every level.
- Record route parity for field submission, event creation/approval/assignment, count review, worker/user approval, and export.

**Gate:** no metric is designed as a trusted KPI until its definition and missing/pending behavior are explicit.

### Phase 1 — Page frame and shared language

- Add/adjust hub labels and scope header only after mapping current routes and aliases.
- Build reusable coverage, metric, direct-child, and empty/error presentations.
- Keep old route destinations reachable; do not bulk-delete navigation.

**Gate:** all existing high-value workflows remain reachable by their authorized users.

### Phase 2 — Overview

- Recompose the role-aware dashboard around scope pulse, reporting coverage, and direct-child attention.
- Validate state, region, group, and location layouts separately.

**Gate:** each role sees only its allowed aggregate and direct-child list; totals disclose incomplete coverage.

### Phase 3 — Weekly Services & Giving

- Present each programme separately with the correct count model and giving behavior.
- Extend expected-population comparison to Monday/Thursday where source semantics allow.
- Correct active-worker eligibility/denominator source before showing meeting attendance rates.

**Gate:** no weekday giving is merged; no worker/leader offering appears; no missing report is treated as zero.

### Phase 4 — Major Programs

- Present configured event sessions and count sections dynamically.
- Correct retreat host-scope terminal behavior to group or region.
- Preserve Alpha/satellite scope rules and event workflow permissions.

**Gate:** test representative group-hosted retreat, region-hosted retreat, multi-section counts, and Alpha-plus-satellite crusade in a controlled verification environment.

### Phase 5 — People & Demographics; Workforce & App Access

- Separate estimate from attendance composition and workers from app users.
- Add clear drill-down and status definitions.

**Gate:** no unique-member or retention claim is derived from programme head counts; no worker units are hard-coded.

### Phase 6 — Contextual actions and report parity

- Improve task entry points using only verified workflow feeds and permissions.
- Ensure reports/exports use the same scoped definitions as hubs.

**Gate:** no “unified” or “real-time” claim unless implemented and verified across the underlying feeds/delivery mechanism.

### Phase 7 — Navigation consolidation and role review

- Consolidate duplicate entry points only after parity and direct-URL authorization checks.
- Review each page as state pastor/admin, region pastor/admin, group pastor/admin, location role, and assigned worker where supported.
- Review narrow-phone layouts, loading/errors, missing versus zero, incomplete coverage, and approved versus pending records.

**Gate:** product owner accepts the page map and verified workflow parity before retiring any old route or navigation entry.

## 8. Acceptance checklist

The work is ready for product review when all are true:

- [ ] A leader can identify their jurisdiction, selected period, and latest reporting state immediately.
- [ ] The first overview screen summarizes the leader’s own scope and direct children, not a raw location directory.
- [ ] Drill-down respects state → region → group → location and event-specific terminal scope.
- [ ] Sunday, Monday, and Thursday attendance and combined collections are separate programme measures.
- [ ] Tuesday Leaders’ Meeting and Saturday Workers’ Meeting are distinct; neither shows offering.
- [ ] Weekly head-count categories remain adult/youth/children by male/female.
- [ ] Population estimate is labeled as an estimate and can be compared with any programme day without implying membership or capping at 100%.
- [ ] Worker attendance rate uses a verified eligible active roster denominator and preserves the historical meeting basis.
- [ ] Retreat sessions and sections are data-driven; retreat reporting stops at its group or region host.
- [ ] Crusade Alpha and satellite figures remain separate, with Alpha visibility restricted to the state view.
- [ ] Sums across event sessions are labeled participation, not unique people.
- [ ] Worker totals and application-user totals are separate; worker unit values are not hard-coded.
- [ ] Missing, zero, pending, partial, and error states are not conflated.
- [ ] Charts have readable labels/text equivalents and remain useful on a phone.
- [ ] Existing creation, submission, review, approval, and export routes remain permission-correct and reachable.
- [ ] Every displayed action is enforced by backend authorization, not only hidden in the UI.

## 9. Known gaps to resolve from source before or during implementation

These are specifically known mismatches or verification needs, not permission to expand scope:

1. Worker meeting attendance roster paths appear to check approval but not consistently require `Worker.status == Active`; denominator snapshots/fallbacks need reconciliation with the agreed active-worker rule.
2. Expected-population comparison is currently most explicit for Sunday; Monday/Thursday presentation needs a source-backed extension using the same estimate semantics.
3. Retreat analytics currently has a region-only terminal-depth condition, while the agreed event host can be group or region.
4. Gemini’s first proposition included some useful but unverified concepts (for example follow-up percentages, discipleship progress, a fixed department taxonomy, password-reset actions, and a fully unified action queue). They are excluded until a source path and product definition are confirmed.
5. The notification endpoint is polling-based; current source does not justify a real-time-delivery promise.

Any newly discovered source conflict should be recorded with the relevant route/model/service and presented to the product owner. Do not resolve a product-rule conflict by guessing.

## 10. Review protocol for Codex, Gemini, and the product owner

Gemini may propose a different component, chart, layout, or implementation sequence. Evaluate proposals against the confirmed rules, source data, permissions, usability goal, and acceptance checklist above. A proposal that preserves these constraints can be adopted as an implementation detail. A proposal that adds a metric, workflow, data source, role, or product promise goes into **Open decisions / proposed additions** for the product owner; it does not enter the implementation scope by implication.

Codex’s supervisory review should classify feedback as:

- **Aligned improvement:** clearer or simpler presentation within the locked scope.
- **Source correction:** the plan’s route/data claim is wrong or incomplete; show evidence and correct it.
- **Product decision required:** changes a confirmed meaning, role boundary, or behavior.
- **Out of scope for this implementation:** new feature with no confirmed source/definition.

## 11. Open decisions / proposed additions

None are approved by this plan. Add a proposal here with its user problem, source availability, affected pages/roles, permission implications, and acceptance rule. The product owner decides whether it becomes scope.
