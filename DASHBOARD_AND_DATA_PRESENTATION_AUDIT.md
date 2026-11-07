# Church Admin Dashboard and Data Presentation Audit

**Review date:** 6 November 2026  
**Application scope:** Church Admin for role scores 2–5 (Location, Group, Region, and State leadership)  
**Review mode:** Read-only source review and authenticated browser/API observation in the current development environment  
**Purpose:** Describe what the product currently presents, what its figures mean, how the hierarchy affects visibility, and where the interface or calculations can mislead institutional users.

## 1. Executive summary

Church Admin is the oversight and operations application for Location Pastors (level 2), Group Pastors (level 3), Regional Pastors (level 4), and State Overseers (level 5). It is a browser-based administrative interface that combines a role-scoped dashboard with dedicated pages for workers, attendance, program counts, offerings, newcomers, events, fellowships, reports, and operational approvals. Field collection is a separate application; the Admin screens consume submitted data and handle oversight, review, and analysis.

The dashboard is not merely a link page. It loads a set of summary metrics, then renders role-specific panels. Levels 2–4 see a local profile with member, population, worker, and attendance panels; level 5 sees a state profile with governance coverage, population, and workforce panels. Several detailed panels are deferred behind “Load” actions. The application also has dedicated data pages, although some pages did not finish loading during the browser observation window in this development session.

The underlying authorization design has a sound central idea: each account has an organizational path, and API queries are constrained to that path and its descendants. A user should not gain another jurisdiction by manually changing a URL. However, the dashboard’s child-scope selector did not produce a corresponding change in the displayed figures during the observed browser session. Its selection was not retained in the URL, and dedicated data pages derive scope from the signed-in identity rather than the dashboard’s temporary child selection. As a result, the current child-selector experience is not a reliable way to move through data at a lower level.

The most important reporting issue is ambiguity. A missing submission is not the same as a submitted zero, but the dashboard often renders an absent aggregate as `0`. The population panel has no explicit “no submissions for this period” state. The app also has no clear coverage view that says how many expected locations have reported, how many submitted a zero, and how many have not submitted. The State dashboard’s “Reporting branches” value is a count of distinct locations found in count records; it is not a complete submitted-versus-expected coverage report. Its separate governance location figure is hierarchy size, not report coverage.

In the seeded development data, all four personas could read their dashboard data, but the values exposed several inconsistencies. At state scope the dashboard showed 185 workers, 143 active, and 42 pending verification. The workforce panel’s status presentation did not account for those 42 pending records in its active/inactive language. Population figures were 47 across every persona because all observed count submissions were concentrated at one location. State hierarchy contained 40 locations, while the reporting-branch count was 1. These numbers are not proof of live church coverage; they describe the development dataset observed on the review date.

The Reports page rendered an access-denied message for the tested State Overseer identity because it lacked `reports:read`, even though dashboard statistics were available through a separate `statistics:read` path. This is a real distinction between the tested account’s permissions and the screens it can open. A page that cannot be opened must not be described as available based solely on its route or API existing.

### Overall assessment

| Area | Assessment |
|---|---|
| Role-scoped API access | **Good foundation.** Scope is validated against the authenticated user’s hierarchy path. |
| Dashboard presentation | **Useful role-specific starting point, but easy to misread.** Several `0` values conceal the absence of submissions, and some cards do not share the selected period. |
| Scope drill-down | **Not reliable in the observed UI.** Child selection did not refresh figures as expected, was not encoded in the URL, and did not carry into dedicated pages. |
| Reporting coverage | **Insufficient for accountability use.** The interface does not provide a clear expected / submitted / zero / missing breakdown. |
| Dedicated data pages | **Broadly present in source; runtime evidence is mixed.** Some pages showed loading placeholders throughout the observation window. |
| Metrics and time definitions | **Inconsistent.** Some figures are all-time, some use current-month/event dates, some use the dashboard period, and some are based on submission rows rather than people or meetings. |
| Production readiness for institutional reporting | **Not established by this review.** This is a development environment with synthetic data; no load, backup/restore, privacy-impact, or production-deployment verification was performed. |

## 2. Evidence labels and review boundaries

Statements in this document use the following labels:

- **[BR] Browser/runtime observed:** Seen in a rendered page or a successful read-only request in the running development app.
- **[SRC] Source verified:** Confirmed in the current source implementation, but not necessarily seen completing in the browser.
- **[BR+SRC] Runtime and source agree:** Both the rendered result and implementation were checked.
- **[INF] Interpretation:** An explanation derived from verified behavior; not itself an independent product guarantee.
- **[UV] Unverified:** The review did not establish this in the current runtime.
- **[NI] Not implemented in the reviewed flow:** The current inspected page or code path does not provide the described behavior. This does not rule out an uninspected external process.

### What was done

- Inspected the Admin frontend routes, components, service layer, API routes, data models, scope filters, and report/statistics services.
- Opened the actual Admin pages in a browser using four existing development identities representing Location, Group, Region, and State leadership.
- Read sanitized responses from the development API for dashboard bootstrap and relevant data endpoints. No names, phone numbers, login credentials, access tokens, or other personal data are included here.
- Used signed access tokens held only in a temporary local browser session to avoid the normal login endpoint, which writes a refresh-token record. The observed pages were the real application routes and the API requests were read-only. Normal sign-in, token refresh, and cookie behavior were therefore not exercised.
- Observed dashboard rendering for all four personas and the Reports access-denied screen for the State persona. Tried a dashboard child-scope selection and inspected its resulting display.
- Inspected source for dedicated pages whose browser content stayed in a loading shell.

### What was not done

- No source code, database records, permissions, or configuration were changed for this audit.
- No application tests or data-seeding commands were run.
- No production deployment, live church data, mobile-device, offline, accessibility, penetration, load, backup-restore, or legal compliance assessment was performed.
- No claim is made that the development seed data represents actual church reporting coverage.
- A request that returned an error because it was made without a required identifier (for example, a generic fellowship summary request without a fellowship ID) is not treated as proof that the correctly parameterized page is broken.
- Some dedicated pages remained on loading placeholders for up to the browser’s observation window. This is recorded as runtime-unverified; the placeholder is not interpreted as an empty dataset.

## 3. Product and organizational context

Church Admin is intended for organizational leadership levels 2–5:

| Score | Leadership scope | Main reporting perspective |
|---:|---|---|
| 2 | Location Pastor | One location and its local records/workers |
| 3 | Group Pastor | The group and its locations |
| 4 | Regional Pastor | The region and its groups/locations |
| 5 | State Overseer | The state and its regions/groups/locations |

The field utility is the primary data-sourcing app for field submissions. Church Admin is the leadership-facing application for looking across those submissions, managing people and workflows, and reviewing operational information. The two apps have different users and tasks, even though their data is shared.

Organizational scope is represented with a hierarchy path. For example, a path can identify the state, region, group, and location ancestry in one value. A parent-level user’s permitted scope can therefore include descendant locations. This supports filtering and aggregation by organizational level. It does not, by itself, mean that every descendant has submitted data.

The system’s numeric role scores extend beyond this application, but this audit concerns only the Admin personas at scores 2–5. Other score values or future applications are outside the observed screen matrix.

## 4. Dashboard experience by persona

### 4.1 Shared dashboard structure

**[BR+SRC]** The shared shell displays the application navigation, current user/scope context, search and notification controls, and the dashboard content. The dashboard page title is “DCLM Operations Dashboard,” with a short operational subtitle. It includes a dashboard-scope selector where the role has children, plus a population-period selector. The current page does not provide a strong breadcrumb trail that clearly represents the selected descendant.

The visible content is composed from KPI cards and panels. Some panels load immediately; others start in a deferred state and require a “Load” action. A chart/summary mode control is available on applicable panels. This means a pastor’s first view is not a complete analytics report: it is a summary with some deeper information deliberately loaded on demand.

### 4.2 Location Pastor (level 2)

**Observed layout, paraphrased:**

```text
┌─────────────────────────────────────────────────────────────────┐
│ DCLM Operations Dashboard     Location scope / period controls   │
├─────────────────────────────────────────────────────────────────┤
│ Headline cards: Members | Workers | Pending items | Latest count│
├───────────────────────────────┬─────────────────────────────────┤
│ Member overview               │ Population / attendance mix     │
├───────────────────────────────┼─────────────────────────────────┤
│ Workers and attendance        │ Newcomers / Programs / Meetings │
│                               │ (some panels require Load)       │
└───────────────────────────────┴─────────────────────────────────┘
```

**[BR]** In the observed seed state, the dashboard showed 0 members, 47 workers, one newcomer, and a latest count of 71. The population panel showed 47 people across its breakdown. The workforce panel showed 5 active and 42 pending workers, and the attendance panel showed 8 present with a displayed 30% attendance rate. Those values came from test data. The 0 member total must be interpreted as “the query found no member rows,” not proof that the location has no church members in reality.

**[SRC]** Levels 2–4 use the local dashboard profile. The page includes a member overview, population/attendance mix, workforce and attendance, and deferred newcomer/program/worker-meeting panels. The exact account’s controls and records are permission- and scope-dependent.

### 4.3 Group Pastor (level 3)

**Observed layout:** same local-profile panel arrangement as Location, with a group-scoped headline and data panels.

**[BR]** The seed dashboard showed 49 workers, 7 active, and 42 pending verification. The count-derived population stayed at 47, because the observed count rows were concentrated at one location. This is a useful demonstration of an aggregation trap: a parent dashboard may show a group worker roster but only the population submitted by one reporting branch.

**[SRC]** The group’s descendant scope is available to the API as a path-filtered set. The UI’s child selector lists direct child locations. However, the runtime child-selection behavior did not reliably refresh displayed figures, as described in Section 6.

### 4.4 Regional Pastor (level 4)

**Observed layout:** same local-profile panel arrangement, with regional scope.

**[BR]** The seed dashboard showed 93 workers, of whom 51 were active and 42 pending verification. It showed the same population total of 47 and the same worker-attendance figures as lower levels. There was one observed reporting branch in the count data.

**[SRC]** The Region scope can have groups as direct children. The region profile does not automatically show an all-group reporting coverage matrix or a fully expanded location-level table on the dashboard. Dedicated pages provide more detailed records when they load and are authorized.

### 4.5 State Overseer (level 5)

**Observed layout, paraphrased:**

```text
┌─────────────────────────────────────────────────────────────────┐
│ DCLM Operations Dashboard        State scope / period controls   │
├─────────────────────────────────────────────────────────────────┤
│ Headline cards: Members | Workers | Pending items | Latest count│
├───────────────────────────────┬─────────────────────────────────┤
│ State reporting/governance    │ Population / attendance mix     │
│ Locations, regions, app users │                                 │
├───────────────────────────────┼─────────────────────────────────┤
│ Workers and attendance        │ Programs / Newcomers (deferred) │
└───────────────────────────────┴─────────────────────────────────┘
```

**[BR]** The seed dashboard showed 185 workers, 143 active, 42 pending verification, 44 pending items, 40 hierarchy locations, 7 regions, 70 active registered users, and 1 reporting branch. Population total was 47. The 40 locations are a hierarchy/governance count, while 1 is a location represented in count submissions. These values answer different questions and should not be presented as interchangeable coverage indicators.

**[BR]** Opening `/reports` as the tested State identity displayed “Access restricted” and “Your assigned role does not have reports:read permission.” The dashboard itself still showed statistics. In this app, access to dashboard statistics and access to Reports are separate permissions. The route existing or the sidebar’s general navigation cannot establish that a particular pastor can use it.

**[SRC]** The state profile adds governance information to the local dashboard sections. The current governance panel is a set of hierarchy and user totals. It is not a report-submission compliance dashboard.

## 5. Dashboard metric catalogue

The table records both the visible meaning and the source/query meaning. If a label is broader or more current-sounding than the query, that mismatch is called out.

| Metric or panel | What the screen suggests | What the inspected implementation counts | Time / status behavior | Presentation risk |
|---|---|---|---|---|
| Members | Members in the current jurisdiction | Non-deleted `ChurchMember` rows in the authenticated/query scope | No selected dashboard-period filter in the all-time summary | An absent member dataset renders as 0; user cannot tell “not loaded/not registered” from true zero. |
| Workers | Workers in the current jurisdiction | Non-deleted worker rows in scope, including pending and inactive records | All time; does not mean active workforce | Label can be read as currently serving workers. Separate pending/status values are needed. |
| Active workers | Active workers | Worker rows with the active status | All time/current database status | Pending verification is separate and can be omitted from active/inactive wording. |
| Pending workers | Workers awaiting verification | Pending-verification worker records | Current status | More precise than the headline total, but does not show the specific decision stage in the dashboard. |
| Pending items | Items awaiting action | Aggregated pending workers, users, transfers, status changes, and removals, with scope-specific filters | Current queue state | One total combines different workflows and record types; the breakdown is needed for action planning. |
| Newcomers / converts | Recent arrivals or converts | `Record` entries categorized as newcomer/convert under the dashboard scope | The dashboard summary is all time, despite “recent” copy in parts of the page | “Recent” can imply a date window that the query does not apply. A person may be counted in both broader records/labels depending on category handling. |
| Latest count | Recent attendance/population count | Dashboard bootstrap uses the maximum `Count.total` value in scope | Not necessarily the latest date or event | `MAX(total)` is not chronological latest. The dedicated counts page uses event/date aggregation and may show a different notion of latest. |
| Reporting branches | Locations that have reported | Distinct count `location_id` values represented by count records | Dashboard summary is not restricted to the selected period | It is a count of locations represented in count data, not a submitted-versus-expected compliance rate. |
| Population categories | Male/female and age-group counts | Sums of adult male/female, youth male/female, boys, and girls from `Count` records | Dashboard period selector affects population calculations | When no rows exist, UI defaults numeric values/percentages to 0 instead of “No submissions.” |
| Population total | Combined attendance/population | Sum of the six submitted categories for grouped count occurrences | Period-dependent; occurrence grouping combines locations for the same event/program dimensions before averaging | This represents submitted counts, not an independently verified estimate of all members/residents. Duplicate/overlapping submissions can inflate it. |
| Population average | Average number attending | Average of grouped count occurrences in scope after event/date/program grouping | Depends on the period selection | It is not an average per location, nor necessarily an average of every scheduled service. No submission rows are absent from the denominator. |
| Population percentages | Demographic proportions | Category totals divided by the count total, rounded for display | Period-dependent | Zero defaults can make a no-data period look like a valid 0% demographic result. |
| Worker attendance present | Present workers / attendance | Aggregated attendance submission present counts and/or worker-level marks, depending on panel | Dashboard summary is all-time and does not follow population-period selector | Must distinguish submitted meeting records from all meetings expected to happen. |
| Attendance rate | Workers attending | Aggregate present count divided by aggregate expected-worker opportunities | All observed aggregate attendance submissions; not the current roster | It measures attendance opportunities, not a worker’s month-long faithfulness and not meeting coverage. Current roster is omitted from the displayed panel. |
| Attendance status | Present, late, absent, excused | Worker-level attendance rows grouped by status in the relevant view | Rows created for submitted attendance | No row is not automatically an absent worker. The interface needs explicit event/submission completeness before claiming absence. |
| Program comparison | Program attendance / counts | Event-linked counts grouped by program type in the dashboard program panel | All time in the inspected comparison; not necessarily same period as population | Eventless/legacy counts are excluded, and the comparison should expose date range and submission coverage. |
| Governance locations | Locations under state | Hierarchy records from the organization tree, with a fallback expression in source | Current organization structure | This is configured hierarchy size, not count-reporting locations. |
| Registered users | Accounts under state | User account rows in scope, with active/inactive status | Current account status | Users and workers are separate entities; totals should not be read as worker totals. |

### Seed data values observed across scopes

All figures below are sanitized aggregate values from the development database on the review date. They are not real church statistics.

| Persona scope | Worker rows | Active | Pending verification | Pending items | Count reporting locations | Population in period panel | Hierarchy / governance facts |
|---|---:|---:|---:|---:|---:|---:|---|
| Location | 47 | 5 | 42 | 43 | 1 | 47 | — |
| Group | 49 | 7 | 42 | 43 | 1 | 47 | — |
| Region | 93 | 51 | 42 | 44 | 1 | 47 | — |
| State | 185 | 143 | 42 | 44 | 1 | 47 | 40 locations, 7 regions, 70 active users |

The location/group/region/state worker numbers are not expected to reconcile simply by adding these rows because each row is a parent-scope total that includes descendants. The exact hierarchy and demo seed layout should be used to validate subtotals before stakeholder demonstrations.

## 6. Scope navigation and drill-down behavior

### Intended behavior

At a parent scope, leadership needs a cumulative view by default and a way to select a child scope for detail. The code exposes direct children in the dashboard bootstrap: a State can select Regions, a Region can select Groups, and a Group can select Locations. The API checks that requested paths remain within the authenticated hierarchy. This is a useful security boundary.

### Observed behavior and limitations

1. **[BR] Child selection did not change the displayed state totals during the tested State dashboard session.** The dropdown showed a Region selection, but the headline values remained at state scope (including 185 workers, 40 locations, and the same population aggregate). This is a functional presentation defect in the observed flow; the exact underlying trigger/cache interaction was not proven.
2. **[BR] The browser URL did not capture the child selection.** Refreshing or navigating away cannot be relied on to preserve the temporary selection.
3. **[SRC] Dashboard-selected scope is not shared with dedicated data pages.** People, church-data, and program service layers derive their effective scope from the signed-in identity. Their requests do not inherit the temporary child selected on the dashboard. Moving from a selected child dashboard into a dedicated list therefore returns to the identity’s home scope unless the page itself has a separate scope control.
4. **[SRC] The selector provides direct children only.** It does not itself provide a complete expandable tree or breadcrumb path through several levels.
5. **[SRC] API scope enforcement remains in place.** Requested paths are checked against the user’s allowed path (with higher-score special cases outside the level-2–5 personas). LTree descendant filtering scopes records. A failed UI drill-down should not be “fixed” by removing this check.

### Implication for a pastor

The parent dashboard is useful for a cumulative overview, but the currently observed interface does not establish a dependable “select a specific group/location, then inspect every related page at that same scope” workflow. The child scope must be visibly represented, retained in navigation state, and passed consistently to authorized page requests while every endpoint continues to enforce the authenticated user’s maximum scope.

## 7. Dedicated pages: layout, data and findings

The following describes the actual route/UI source and, where available, rendered behavior. “Not runtime verified” means the page did not finish loading in this review; it does not mean the dataset is empty.

### 7.1 Workers and people

**Route family:** `/people/workers`, `/people/members`, `/people/users`; some additional people routes are role/permission dependent.

**Workers page layout [SRC]:** explanatory heading and a notice directing worker intake to the level-1/2 data-sourcing app; search/status filters; a workers table; worker detail/history and administrative actions when permitted. The data table includes worker identity/code, contact, location/unit, approval/account/status context, and action affordances. Sensitive fields are present in the interface and must be protected by role checks and privacy controls.

**Worker data semantics [SRC]:** a worker is not the same thing as an app user. Worker rows can exist without an account; a user account is expected to be associated with a worker. Summary totals may include pending/inactive worker rows. A list may request multiple API pages and filter client-side, which increases data volume at state scope.

**Runtime [BR]:** the worker page remained at a “Loading workers” shell during the observation window. Backend reads for the seeded scopes returned successfully, but this did not establish full browser table rendering or pagination behavior.

**Reporting recommendation:** show separate totals for active, awaiting approval, suspended/inactive, and linked app accounts. Avoid one unlabeled “Workers” number when the key leadership decision depends on active/approved status.

### 7.2 Program counts (`/church-data/counts`)

**Layout [SRC]:** page title “Program Counts,” a combined-service/count-record explanation, summary cards, location and event filters, a table of aggregated event/date/location rows, and a detail view for category/section submissions. The table is intended to roll up field submissions into a location/program count.

**Underlying model [SRC]:** a count row carries fields including hierarchy path, physical location, date, optional event/domain/type, program scope/level, demographic counts and total, status, submitter, and assignment metadata. Some of those fields are optional for legacy or non-scheduled use. Program events associate dated activity to counts when present.

**Aggregation [SRC]:** the Admin client groups field rows using an event/date/location key and sums the six population categories and totals. It can display the combined total and section/source details. It does not deduplicate people; population counting is numeric. If two submissions cover overlapping groups, naive summation can double-count unless assignments and sections are non-overlapping or the business process prevents overlap.

**Time semantics [SRC]:** the page’s latest occurrence, current-month total, reporting locations, and average-service cards use different date/window logic. The latest occurrence is date-oriented; current month uses the event/count date; average is based on available occurrences. The summary is not a guarantee that each expected location submitted. The client aggregation and dashboard `MAX(total)` are not the same latest-value calculation.

**Runtime [BR]:** the route opened, but its content stayed in the loading shell within the wait window. API `GET /counts/` returned 9 sanitized count rows across the tested scoped requests; the observed rows were concentrated at one location. This does not prove the fully rendered table was usable in that session.

### 7.3 Worker attendance (`/attendance`)

**Layout [SRC]:** KPI cards for expected workers, present, absent, late, and attendance rate; status/unit/event/location filters; and a worker-level attendance table with record detail. The Admin view is intended to let leadership inspect attendance submissions sourced from the field utility.

**Data semantics [SRC]:** attendance includes aggregate roster submissions and linked worker-level marks. An aggregate submission records an event/date/location/program context, expected-worker count, and present worker identifiers; linked rows support individual status reporting. A worker’s absence should be claimed only when there is a valid expected roster and a completed/submitted meeting record.

**Important denominator issue [SRC]:** the summary’s “expected” count is derived from submitted attendance opportunities, not the whole current worker roster. The dashboard’s attendance percentage sums present counts against expected-worker counts from submitted sessions. It is not a faithfulness percentage for a selected worker over a month or quarter. In the seed data, 8 present divided by 26 opportunities is about 30.8%, while the dashboard rounded the displayed value to `30%`.

**Status caveat [SRC]:** absence is represented by an explicit attendance row/status where generated by the workflow. A missing attendance mark or missing meeting submission cannot safely be read as absence. The API had 2 attendance-submission rows in the reviewed seed state; this does not describe the number of meetings expected in the calendar.

**Runtime [BR]:** the attendance route did not finish loading in the browser window. Read-only API access returned attendance summary/submission data, but no full interactive attendance table was visually verified.

### 7.4 Finance and offerings (`/finance`)

**Layout [SRC]:** four KPI cards: approved this month, approved this year, awaiting review, and rejected; filters for fund type, payment method, and location; a table with date, program/event, location, amount, status, payment method, and submitter; a row detail view.

**Data semantics [SRC]:** offering rows are aggregate/event-location submissions, not a ledger of individual donor contributions. Approved totals use approved status; pending/rejected cards use their relevant status rows. Currency presentation is formatted as Nigerian naira, but the data model does not provide a multi-currency conversion framework.

**Potential inconsistency [SRC]:** KPI totals are derived independently of the table’s client-side filters. The month/year totals use entry/event dates and current calendar boundaries; pending/rejected totals are status summaries and may be all-time. A filtered table can therefore sit below cards that do not respond to the chosen filters.

**Runtime [BR]:** the finance page remained at a loading shell in the tested browser session. The scoped offering endpoint returned 4 rows in the seed database; detailed visuals were not runtime verified.

### 7.5 Newcomers and converts (`/newcomers`)

**Layout [SRC]:** All / Newcomers / New Converts tabs, search and filters for follow-up status, gender, and location; a person-oriented record table with contact, type, gender, service/event/location, and follow-up information.

**Data semantics [SRC]:** records are individual person submissions and contain personal information. Follow-up date may come from JSON detail metadata or record creation time. The record’s event/date context and the follow-up date are different facts and should not be conflated.

**Runtime [BR]:** the page did not complete loading within the observation window. The read-only API returned 1 newcomer and 4 convert records across related endpoints in the test data, but a blank/loading screen was not treated as a zero count.

### 7.6 Programs, campaigns and events (`/programs`)

**Layout [SRC]:** tabs for domains, program types, campaigns, and event sessions; filters for domain/type/status/location; summary cards; event/campaign lists and details. Create/approve/assign controls are conditional on permissions. Program events can carry dates, campaign, scope path, reporting scope, status, and Alpha-location/source flags.

**Data relationships [SRC]:** program domains/types form the catalog. Campaigns/series and dated events are additional structures for scheduled runs. Counts can reference an event, but some count metadata is optional. This means a program catalog, a dated event, an assignment, and a submitted count are related concepts, not interchangeable records.

**Runtime [BR]:** API reads returned 5 program events in the inspected data. The page itself did not finish loading during the observation window. No create/approve/assignment action was performed because this was a read-only audit.

### 7.7 Fellowship (`/fellowship`, `/fellowship/{id}`)

Fellowship is an exception to the shared program metadata spine: its records are location-bound and should be scoped by location. The fellowship workflow is not an extra user-registration mechanism.

**Layout [SRC]:** fellowship cards/list with leader, active members, latest attendance, latest offering, open prayers, and description; search/location/status filters; a detail workspace with Overview, Members, Attendance, Offerings, Testimonies, and Prayer Requests tabs. The page has no broad common-program date selector in the inspected layout.

**Performance concern [SRC]:** list construction fetches fellowship details and several related collections sequentially per fellowship. This is an N+1-style request pattern and can become slow as locations/fellowships grow. The shown average is derived from each fellowship’s latest attendance data rather than a full longitudinal attendance average.

**Runtime [UV]:** the full list/detail interaction did not complete in the browser observation window. A generic summary API request without a required `fellowship_id` returned a validation error; that request was incomplete and is not evidence that a valid fellowship detail page fails.

### 7.8 Reports (`/reports`)

**Layout [SRC]:** a date-range selector (default approximately the most recent 90 days), with tabs for Summary, Financial, Attendance, Timeseries, By Level, Growth, Anomalies, and Exports. The source contains CSV/Excel/PDF export flows for report data.

**Access [BR+SRC]:** the State identity used in this review was denied by the page with `reports:read` missing. The dashboard used a separate statistics permission. Other personas’ report access was not proven by this state-specific observation; permissions must be checked account by account.

**Report calculation and labeling concerns [SRC]:**

- The Summary tab uses daily count summary rows; “locations reporting” is the number of locations represented in the selected report result, not a comparison against the expected organization tree.
- Financial summaries group approved offering data by month/location. The UI presentation combines multiple financial kinds into a single displayed total in parts of the page.
- The Financial tab’s selected-range total is used for both period-total cards in the inspected frontend flow, and “Transactions” / “Entry count” duplicate the same row count. This makes the labels misleading for a custom range.
- The Attendance tab is based on weekly attendance trend rows. The displayed expected value is assembled from trend-row worker counts with a fallback of one per row; this is not the official roster size. Its present share is based on present rows versus attendance status-record rows and may not treat late as present in the same way as the dashboard rate.
- “By Level” requests count, offering, and attendance summaries separately. Its results represent those endpoint-specific aggregates; they should not be assumed to share one common denominator.
- Timeseries/growth metrics depend on the selected date range and report-service aggregation. A count is not automatically a meeting attendance record, and an attendance trend row is not one unique worker.
- The Anomalies UI has an error/empty handling path that can display “No anomalies detected” when the source data is empty or a request fails. That wording can confuse no observations with a clean scan unless error state is separately surfaced.
- Exports are source-verified but were not downloaded/visually verified in this audit. Some export flows produce aggregated/materialized-view rows rather than raw submission records.
- A route-level help message says reports are for level 3+ while inspected route gating allows a level 2 persona when it has the required permission. This is a copy/authorization-rule mismatch; the actual permission still controls access.

## 8. Missing submission versus reported zero

This distinction is essential for institutional reporting:

| Situation | Meaning | Correct representation |
|---|---|---|
| No submission exists for an expected activity/location/date | No report was received or recorded | “Not submitted,” “No report,” or “Coverage unknown”; it must not become zero. |
| A valid submission exists and reports `0` | The authorized submitter explicitly recorded zero attendance/population | “Reported: 0,” with date, event, location, submitter, and approval/completeness state. |
| A submission is pending or rejected | A record exists but is not yet an accepted result | Show its review state and exclude/include it in totals according to a clearly stated rule. |
| A report is not expected at that scope/time | No obligation to report | “Not scheduled/not required,” distinct from both missing and zero. |
| A query/page failed or is still loading | Data availability is unknown | Show loading/error; do not show a numeric zero or “no anomalies.” |

### Current handling found

- **[SRC]** Population calculations sum available count rows. With no rows, the service can return an empty object; frontend numeric conversion and missing-key defaults produce zeros and 0% values. There is no explicit no-submission state in that panel.
- **[SRC]** The program-counts page derives totals from rows that exist. It does not by itself enumerate all locations that were expected to submit.
- **[SRC]** A `Count` has a status field and records may be pending. The dashboard population/statistics queries inspected do not consistently filter to an approved/accepted state. Pending values may therefore affect statistics unless other route-level conditions exclude them.
- **[SRC]** `locations_reporting` is computed from locations with count rows, but the dashboard does not show the expected-location denominator and missing children beside it.
- **[SRC]** The State governance location total is based on the organization hierarchy. It is not a substitute for report coverage.
- **[SRC]** Worker absence must not be inferred solely from lack of a row. Aggregate submissions and linked marks provide a basis for attendance, but meeting schedule/expected-roster completeness must also be established.
- **[BR]** The seed data showed a 47 population count and one reporting branch. It did not establish that all other locations had zero population; they had no observed count submissions in this dataset.

### Recommended reporting states

Every report obligation should be classifiable as **Not scheduled**, **Awaiting submission**, **Submitted (including explicit zero)**, **Submitted but pending review**, **Approved**, **Rejected/returned**, or **Submission incomplete**. Dashboards should show a coverage denominator such as `1 of 40 locations reported` only when those 40 locations are actually expected in the chosen program/date/scope. If not all locations are expected, use the applicable assignment/schedule as the denominator. A zero should always be traceable to a submitted record.

## 9. Period and aggregation semantics

Different pages currently answer different temporal questions:

| Screen/value | Observed or source period behavior |
|---|---|
| Dashboard population | Selector supports a recent 30-day window, current month, current quarter, and current year. The “recent” window is based on the last 29 days plus today (30 calendar days). Population and selected-period scope comparisons use this selector. |
| Dashboard headline member/worker/pending/newcomer counts | Generally current all-time/current-state summaries; do not assume the population period selector applies to them. |
| Dashboard latest count | Uses maximum numeric total in the inspected summary path, not chronological latest. |
| Dashboard reporting branches | Distinct count locations over available count rows, not necessarily limited to selected period. |
| Dashboard worker attendance | Aggregate opportunities/marks are not consistently filtered by selected population period. |
| Program count page | Uses count/event dates; latest, current-month, and average cards use distinct rules. |
| Finance page | Approved month/year use calendar boundaries; pending/rejected summaries can represent all-time status queues. Table filters may not recalculate KPI cards. |
| Reports | Date range is passed to report endpoints, with a default of roughly 90 days. Some subtabs use daily, monthly, or weekly materialized summaries. |
| Fellowship | Cards use latest fellowship records in source; no common report-period control was found. |

**Practical implication:** the same “attendance” or “total” concept can differ across screens because the windows, denominators, and underlying rows differ. Each KPI should expose its date range, status inclusion rule, aggregation unit (person, event, submission, or location), and denominator.

## 10. Data lineage and ownership

### Common data context for submitted program data

For most field submissions, the intended shared context is:

1. **Domain** — broad program family.
2. **Program type** — named activity within that domain.
3. **Program level** — organizational level at which the activity/report belongs.
4. **Location ID/path** — the relevant location node at that level, with its organizational ancestry.
5. **Author/submitter** — the authenticated person who entered the data.
6. **Activity date and submission/audit metadata** — date, workflow status, source/assignment where relevant, and record timestamps.

The inspected schema carries many of these values on count records; program-event linkage and some catalog metadata are optional to support unscheduled/local use and legacy rows. Therefore it would be inaccurate to say every record is currently guaranteed to have every common anchor. This audit found that Count can include optional event/domain/type references and separate program level/scope fields. Other record families have their own fields and workflows.

### Important record families

| Record family | Primary meaning | Scope/lineage notes |
|---|---|---|
| Worker | Person registered as a church worker | Belongs to an organizational location and may or may not have an app-user account. Worker approval/status is separate from account status. |
| User | Login identity and permissions | Associated to hierarchy/role; authorization uses user role and scope. It is not a substitute for the worker record. |
| Count | Numerical population/service count | Carries location/path, date, category totals, submitter/status and optional program/event metadata. Multiple submissions may be aggregated by event/date/location. |
| Program domain/type | Catalog vocabulary | Classifies programs; catalog entries are not themselves dated occurrences. |
| Campaign/event | Particular run or dated occurrence | An event can supply a date/scope and connect count or other operational reports. Assignment and event status matter to who may report. |
| Attendance submission/marks | Roster/event attendance | One aggregate submission can be linked to individual worker marks; denominator and submission completeness must be explicit. |
| Offering | Aggregate financial report | Usually event/location/date/status/submission context; not a donor-level ledger. |
| Newcomer/convert record | Person-oriented follow-up record | Contains personal data and event/location/submitter context; requires stricter access and retention controls. |
| Fellowship data | Location’s house fellowship operations | Location-bound; it does not need the broader shared program spine, consistent with the defined business rule. |

### Multi-usher submissions

**[SRC]** The count page’s aggregation combines submission sections with the same event/date/location key by summing their category totals. The detail view can preserve the section/source rows. This allows multiple assigned workers to contribute sections that form one location total.

**Risk:** the sum is arithmetic, not deduplication or proof that sections are disjoint. If two ushers count the same attendees, the total can be inflated. The workflow should define who owns which section, whether a finalizing/submitting action is required, and whether all assigned sections are complete before the location aggregate is treated as final. Conflict detection and idempotency should be verified at the API/client boundary before claiming duplicate protection. This audit did not submit overlapping data.

## 11. Authorization and security observations relevant to reporting

### Positive foundations

- **[SRC] Hierarchy-aware scope checks:** API dependencies derive effective role and scope from the authenticated identity and validate a requested path against the user’s allowed scope. Path filters constrain descendant records.
- **[SRC] Separate permissions:** statistics, reports, worker/people functions, programs, and actions have distinct permission checks rather than relying only on the navigation menu.
- **[SRC] Dashboard summaries are scope-filtered:** the API has a central bootstrap path and role/scope-dependent panels.
- **[SRC] Aggregate versus person data is represented separately:** worker attendance supports aggregate submission metadata and worker-level marks; worker/person records are distinct from accounts.
- **[SRC] Materialized reporting structures exist:** daily count, finance, and attendance trend reporting uses summarized database views/services, reducing the need to rebuild every report from raw rows on every request.

### Observed/identified weaknesses

- **[BR] Permission mismatch in experience:** State dashboard statistics were visible while the Reports route denied access for missing `reports:read`. This may be intentional, but the user-facing navigation/copy should make the distinction clear and tested across personas.
- **[SRC] Numeric defaults erase absence:** a data-load or no-row condition can become visible 0/0%, weakening reporting integrity.
- **[SRC] Pending-status inclusion is not consistently explicit:** some statistics query count rows without a clear approval-state filter. A pending field report may influence an overview unless the workflow intentionally treats it as usable. The rule should be made explicit per metric.
- **[SRC] Sensitive newcomer and worker fields are present in page data:** access scope, browser cache, export handling, audit trails, retention, and least-privilege access matter. This audit did not test all of those controls.
- **[SRC] Dashboard query selector behavior is not reliably connected to navigation:** scope context can be lost between dashboard and dedicated screens even when each API independently protects maximum scope.
- **[UV]** No penetration test, session rotation/refresh review, CSRF review, production cookie configuration, database row-level security deployment verification, backup/restore check, or privacy compliance assessment was performed in this task.

## 12. Performance and scalability observations

These are source-level risk indicators, not a measured capacity conclusion.

1. **Fellowship list fan-out [SRC]:** list population loads details and related member, attendance, offering, and prayer collections sequentially per fellowship. Request count grows with the number of fellowships and can make an oversight-level page slow.
2. **Client-side scope/filter work [SRC]:** worker and some other services page through API data and then filter/aggregate in the frontend. A state-level roster is materially larger than a location roster and may increase response time, memory use, and browser rendering cost.
3. **Dashboard/bootstrap latency [BR]:** dashboard bootstrap took roughly 16 seconds per persona in this environment during the observed run. This is an observation from a development host, not a production benchmark and not a guaranteed steady-state latency. Caches exist in the backend/frontend layers, but their behavior does not remove the need to measure a cold load.
4. **Dedicated pages [BR]:** several pages remained in loading placeholders during waits of up to about 15 seconds. It is not known whether this reflects local host latency, a failing request, browser session behavior, or another runtime issue. It should be investigated with request timing and error logs before deployment.
5. **Database indexes [SRC]:** relevant models/migrations include indexes for key date/path/location/status and hierarchy access patterns. Index presence does not establish a query’s performance at expected scale.
6. **No capacity conclusion [UV]:** no load test, concurrent user test, production-like dataset benchmark, query plan review, or infrastructure sizing exercise was performed. Avoid claims about the number of simultaneous users or response-time service levels until measured.

## 13. Priority findings

### High priority: reporting correctness

1. **Make no-data explicit.** Replace silent zero defaults for unsubmitted population/attendance periods with separate “no submission,” “reported zero,” “not expected,” and “load failed” states.
2. **Add expected-versus-reported coverage.** Compute the eligible reporting set from an approved schedule/assignment or explicitly defined obligation, then show submitted, missing, pending, rejected, and reported-zero separately. Do not use the total hierarchy location count as the denominator unless every location was expected to report.
3. **Fix and verify dashboard child selection.** Ensure a selected child actually scopes the displayed cards, panels, and subsequent dedicated pages; expose the chosen path in a breadcrumb and URL/state; retain the authenticated maximum-scope check on every API request.
4. **Correct latest semantics.** Select latest by event/count date (plus deterministic tie-breaker), not highest count value. Label any historical maximum separately if that metric is useful.
5. **Publish metric definitions.** Every KPI should state unit, time window, status inclusion, numerator, denominator, and source. In particular, label worker attendance as meeting opportunities if that is what it measures; do not call it worker faithfulness.
6. **Reconcile worker states.** Show pending verification distinctly beside active/inactive/suspended totals so the counts reconcile and the state dashboard does not imply all non-active records are inactive.

### Medium priority: usability and accountability

7. Make parent-to-child navigation consistent between dashboard, workers, counts, finance, attendance, newcomers, programs, and reports.
8. Align Reports permission feedback, sidebar/navigation visibility, and “level 3+” help copy with actual permission rules. Test all four role personas and representative permission combinations.
9. Make deferred panels clearly say what is available after loading and preserve errors as errors rather than empty results.
10. Establish multi-usher assignment/section completeness and overlap rules; show each submitted section and whether the location total is complete/final.
11. Improve the Reports tab’s selected-range KPI labels and avoid duplicated “Transactions”/“Entry count” cards. Ensure filters affect both cards and rows or disclose the separate scopes.
12. Reduce fellowship list fan-out and measure page response with realistic group/region/state data.

### Before production or broad institutional rollout

13. Run a permission matrix against actual representative accounts, including direct API access and URL edits.
14. Validate all reporting formulas using hand-calculated fixtures for zero, missing, pending, rejected, multiple submissions, duplicate sections, and cross-location aggregation.
15. Conduct load/query profiling using production-shaped data, plus backup/restore and operational monitoring checks.
16. Review personal-data access, export scope, retention, auditability, and privacy obligations with the responsible church/privacy stakeholders. This audit does not certify legal compliance.

## 14. Suggested stakeholder acceptance questions

The following questions should be answered by church stakeholders who understand the operational process before reporting rules are finalized:

1. For each domain/program type, which organizational levels can schedule it, and which locations are actually expected to report?
2. Is a zero count a valid, explicit result for every data type, or are some zeros impossible and therefore likely missing submissions?
3. For a combined meeting, who owns the final report and what makes its assigned usher sections complete?
4. Can multiple ushers record disjoint attendance sections? What prevents the same worker or attendee from being counted twice?
5. Which worker statuses should appear in the active workforce total, and when is a pending worker allowed to attend meetings or appear in denominators?
6. For a monthly attendance “faithfulness” measure, is the denominator every scheduled meeting, each worker’s expected meetings, or meetings for which their group/location submitted a complete roster?
7. Should leaders see all workers under them by default, or only approved/active workers with separate pending/suspended views?
8. Does an event’s approved/active status determine whether its count is visible in dashboards? Should pending/rejected reports be excluded from official totals?
9. What is the approved date definition for each report: event date, submission date, approval date, or a combination?
10. Which parts of newcomer, worker, and offering data may be exported at each level, and who is allowed to see direct contact information?

## 15. Source and runtime evidence map

The implementation review used these source areas in the current checkout; references below are paths and symbols to aid follow-up, not claims that every corresponding flow completed in the browser.

| Concern | Primary source areas inspected |
|---|---|
| Application setup and shell | `app/frontend/dclm_admin/app_factory.py`; `app/frontend/dclm_admin/components/shell.py`; `app/frontend/dclm_admin/auth_context.py` |
| Dashboard layout/panels | `app/frontend/dclm_admin/routes/dashboard.py` (`_dashboard_content`, profile and panel renderers) |
| Dashboard API/bootstrap and calculations | `app/api/v1/routes/dashboard.py`; `app/services/dashboard_service.py`; `app/services/statistics_service.py`; `app/frontend/dclm_admin/communication/dashboard_service.py` |
| Permission and scope enforcement | `app/api/deps.py`; `app/db/filters.py`; `app/db/init_rbac.py` |
| Counts and aggregation | `app/frontend/dclm_admin/routes/church_data.py`; `app/frontend/dclm_admin/communication/church_data_service.py`; `app/frontend/dclm_admin/communication/count_aggregation.py`; `app/api/v1/routes/counts.py`; `app/models/counts.py` |
| People and workers | `app/frontend/dclm_admin/routes/people.py`; `app/frontend/dclm_admin/communication/people_service.py`; worker/user/member models and API routes |
| Attendance | attendance frontend route/service, `app/api/v1/routes/attendance.py`, attendance and aggregate-submission models |
| Finance/newcomers/programs/fellowships | corresponding `app/frontend/dclm_admin/routes/` and `communication/` modules; matching `app/api/v1/routes/` modules and models |
| Reports and materialized summaries | `app/frontend/dclm_admin/routes/reports.py`; `app/frontend/dclm_admin/communication/report_service.py`; `app/api/v1/routes/reports.py`; `app/services/report_service.py` |

Relevant sanitized runtime observations included successful scoped GET requests for dashboard bootstrap and the principal data resources; the tested scopes returned 9 count rows, 2 attendance-submission rows, 4 offerings, 4 converts, 1 newcomer, and 5 program events in the development data. These are response counts from this environment, not expected production totals. The State dashboard reported one distinct count-reporting branch. No person-level data is reproduced in this document.

## 16. Final conclusion

The application has a meaningful foundation for level-2–5 oversight: role-specific dashboards, hierarchy-aware API scope, separate modules for major church records, and summarized reporting services. The current product presentation still requires refinement before its statistics can safely be treated as institution-wide operational truth. The main gap is not simply the absence of more charts; it is the clarity and consistency of what a number means, whether a report was expected, whether a zero was explicitly submitted, which status is included, and which jurisdiction is currently on screen.

The strongest next step is to define reporting obligations and metric rules with church stakeholders, then make the dashboard and dedicated screens carry the same selected scope and show report completeness. Until those changes are verified across the four personas with data cases for missing, zero, pending, rejected, and duplicate/partial submission, stakeholders should regard the current dashboard as a development-stage overview rather than a certified reporting ledger.
