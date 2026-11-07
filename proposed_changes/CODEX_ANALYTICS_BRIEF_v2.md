# Church Admin Analytics Redesign: Consolidated Brief (v2.1)

**Replaces:** `CODEX_ANALYTICS_BRIEF.md` and Addenda 1 to 4. Nothing in those files applies any more. This file is the only source of requirements. **v2.1 (7 Nov 2026) adds two church requests:** ushers may edit a submitted report for 24 hours, 3 times at most (replaces the reject-and-resubmit correction design, see C4), and attendance is shown as a percentage of each location's estimated population (see C4, C5, slice B2b).
**Stack:** FastAPI backend, FastHTML + FastStrap frontend (use the `faststrap-app-builder` skill), PostgreSQL with ltree paths.
**Scope:** Church Admin for role scores 2 to 5 (Location, Group, Region, State). Scores 1 and 6 to 9 are out of scope but must keep working.
**Reference files:** `STAKEHOLDER_PROJECT_BRIEF.md`, `IMPLEMENTATION_FIX_PLAN.md`, `DASHBOARD_AND_DATA_PRESENTATION_AUDIT.md`, `ANALYTICS_FINDINGS.md`, and `church-analytics-prototype.html` (layout and behaviour reference only; sample data; do not port its JavaScript; its "View as" switch and "Assumptions" panels are prototype-only).

---

# PART A: How to work

1. Work one slice at a time (Part D). After each slice, stop and report. Do not start the next slice until the report is delivered.
2. Verify every file, table and field named here in the repository first. Where it differs, trust the repository and tell me.
3. If a field a metric needs does not exist, report it. Never invent data, defaults or seed values to make a screen look complete.
4. Preserve server-side scope enforcement everywhere. The frontend is never the security boundary. Do not weaken `app/api/deps.py`, `app/db/filters.py` or row-level security.
5. Do not rewrite the backend. Reuse existing endpoints, materialized summaries, models and the existing scope resolver. Migrations are additive and reversible, with a snapshot taken first.
6. Do not claim hosted or production readiness. Report what you verified locally and how. Restart or identify any stale server before judging a screen.
7. Before running `init_rbac.py` again, export roles, permissions and role_permissions to JSON and diff afterwards.
8. Keep comments and docstrings in every file you touch.

**Report format after each slice:** what changed (files, migrations, endpoints); what you verified and how (test names, commands, browser checks, real response excerpts with personal data redacted); what you could not verify; conflicts with this brief; questions that need a church answer.

---

# PART B: Status so far

| Slice | State | Notes |
|---|---|---|
| A. Scope plumbing | Done | `scope_path` and `period` and `include_pending` in URLs; `active_scope.py`; breadcrumb; every dedicated page takes the active scope. 30% was integer truncation in the frontend; fixed. Child selection now persists. |
| B1. Sunday Worship slice | Done | Location lifecycle migration `a71c3f9d2b40`; standing-program config; time windows; Sunday Worship coverage endpoint; latest-Sunday card and population panel on the dashboard. Backup restore not yet proven (close-out item). |
| B2. Count review and realistic data | Done | Close-out items below still open |
| B2b. Expected population | Next | Section D |
| B3. Any program, any day | After B2b | Section D |
| B4 to B6, C, D, E | Later | Section D |

Confirmed gaps from the reports: counts start `pending` and no review route exists; `WorkerAttendanceSubmission` stores present worker IDs but only a count for the expected roster, and both attendance aggregates sum that count per submission (doubled denominator under split submissions); `FellowshipAttendance` has only men, women, youths, children, total; `Location` had no lifecycle flags (now added).

---

# PART C: Product specification

## C1. The problem

The apps already have hierarchy-aware data and server-side scope checks. What was missing is one analytical model. The same word meant different things on different screens, a missing report looked like `0`, the child selector did not carry across pages, and nothing said how many locations were expected to report.

## C2. Principles (non-negotiable)

1. **One definition per metric.** Every screen calls the same metric service.
2. **Absence is not zero.** No report is `null` plus a state. A submitted zero is a real value, shown as "Reported 0".
3. **Never show a total without its coverage.** Every aggregate carries expected, received and counted.
4. **Additivity is declared.** Each metric is *additive* (sums up the tree), *recomputed* (rebuilt from underlying totals at each level, never averaged across children) or *snapshot* (a point in time).
5. **Attendance is a snapshot per occurrence.** Never add attendance across sessions or days, because the same people attend several. Show latest, peak and average per reporting unit. Converts and offerings do add across occurrences.
6. **Scope is first-class.** Identity sets the maximum scope. `scope_path` in the URL sets the active scope. Every endpoint validates it.
7. **Same page, different scope.** One template per page at every level. Only the scope changes, plus the privacy rules in C9.
8. **Latest means latest by date**, never `MAX(total)`.
9. **Pending reports do not count by default**, with a user switch `include_pending`. Rejected reports never count.
10. **Alpha and satellite are shown side by side.** A combined figure is always labelled "Total participation" (or says what is missing). Never an unlabelled combined number.
11. **No ranking of sibling units by attendance.** Sort by name, most unreported, or biggest decline.
12. **Do not over-engineer collection.** Every report already carries five parameters (program domain, program type, program level, location id, date) plus the author. These identify its source, level and meaning. Use them; add structure only where this brief says so.

## C3. Scope contract

```
Authenticated identity -> maximum authorized scope
  -> active analytical scope (scope_path, must be within maximum)
     -> every page and endpoint
```

- Parameter name is `scope_path` (ltree) in URLs and APIs. Default is the user's maximum scope.
- Validation keeps the existing contract: malformed path returns 400, out of scope returns 403. The frontend never falls back silently; it shows an error.
- URL carries a period preset (`4` or `8` weeks) and optional custom `from` and `to`. The Admin route converts these to `period_start` and `period_end`. The API accepts only dates and computes the previous window of equal length itself.
- One `scope_link()` helper builds every link, table row and HTMX target so scope is never dropped.
- Breadcrumb runs from the user's maximum scope down to the active scope. Ancestors above the maximum are never shown.
- Children are one level down only. At Location level there are no children; the page shows records.

## C4. Reporting model

### Standing programs (code-level config, not a table)

Fixed, never edited in the app. A change is a code change.

| Program | Day | Expected unit |
|---|---|---|
| Sunday Worship | Sun | Location |
| House Caring Fellowship | Sun | Location (one combined report; per-fellowship rows roll up) |
| Monday Bible Study | Mon | Location |
| Tuesday Leaders Meeting | Tue | Not defined (list meetings received; no missing state) |
| Thursday Revival Hour | Thu | Location |
| Saturday Workers Meeting | Sat | Location |

Leaders Meeting and Workers Meeting are separate programs with separate statistics and separate pages. Never merge them.

Event programs (Global Crusade monthly; Easter Retreat and December Retreat once a year each; Conferences irregular) have no expectation table. Expected reporters come from `ProgramEvent` plus approved `EventAssignment`; with no assignments, coverage is "unknown", never 100%.

### States and time windows

States per expected cell: `not_configured`, `awaiting`, `late`, `missing`, `combined`, `received` (with review state `pending`, `approved` or `returned`). A received report may have value `0`.

- Reference time is the end of the occurrence date in Africa/Lagos. Up to +10h: awaiting. +10h to +24h: late. After +24h: missing. Constants in one place.
- Pending older than 10h alerts the approving pastor; older than 24h also shows to the next level up. Constants in one place.
- "Returned" is a user-facing label. Map to the real stored status values (for example `rejected`) in one module, tested against the real approval flow.

### Location lifecycle

`Location.is_active`, `opened_on`, `closed_on` (migration `a71c3f9d2b40`). A location is eligible for a week when `is_active` and `opened_on <= week` and (`closed_on` is null or `closed_on >= week`). There is no "excused location" feature; a real closure uses `closed_on`.

### Expected population

The church holds an estimated population for each location and wants attendance shown as a percentage of it.

- Store it versioned: `location_expected_population(location_id, expected_total, effective_from, source, set_by_id, created_at)`. Additive. History is never rewritten; a week uses the estimate effective on its occurrence date. First check whether a similar field already exists on `Location` or elsewhere.
- One total per location, used for **Sunday Worship only** (a config list of programs that use an estimate). No percentage for other programs until the church supplies estimates for them. Estimates by category or by program are a later option.
- Maintained by the State Overseer (new permission). Bulk load through the existing hierarchy Excel template with one added column. Every change is audited. Pastors below cannot edit it, because an estimate they control could flatter their own percentage.
- **Aggregation is pooled, never an average of child percentages.** Numerator and denominator cover the same locations: those with a counted report and an estimate on that date. A location with a counted report but no estimate is left out of both and reported ("n reporting locations have no estimate"). A missing report never lowers the percentage; coverage shows it.
- Above 100% is legitimate. Do not cap it. Flag a location in Needs attention when it is above 150% or below 30% for several consecutive weeks ("estimate may be out of date"). Thresholds in config.
- Show it on the dashboard (context line of the Latest Sunday card, and a "% of expected" column in the children table), on location records, and on the Attendance page.

### Combined meetings

A report at a higher program level (Group, Region or State) for the same program type and week, whose scope covers a location, replaces that location's own report for that program and week. Identify it from program level and scope path; also honour an approved `ProgramEvent` covering the location. The covered location shows state `combined` with the level it was combined at. If an event is cancelled and has no reports, the local expectation returns. If a covered location also submitted its own report, exclude it from totals and flag it `superseded`. Additive rollups use each report at its own scope so nothing counts twice.

### Approval

Location-level reports (counts, offerings, attendance, fellowship) are accepted by the Group Pastor. Group-level reports by the Region Pastor. Region-level reports by the State Overseer. State-level reports are accepted on submission and flagged "auto-accepted". Region and State see accepted reports automatically, which replaces the WhatsApp forwarding chain. The approver may also chase unreported items with a "Remind" action (existing in-app broadcast to the responsible location's users).

### Corrections: the usher edit window

The church's rule: the usher who submitted a report may edit it for **24 hours, at most 3 times**, and the Group Pastor then simply approves.

- An edit changes the same row (same id, same count group). Each edit saves a revision (before and after values, editor, time, edit number) in a revision table. Metrics read current values only. Admin shows "Edited n times, last at ..." and what changed.
- Editing is allowed while the report is `pending`. **Approval locks it.** The review queue shows the time left in the usher's window, so the pastor can see whether the figures may still change.
- The window runs from the server's first receipt of the report. Window and edit count are enforced on the server, never the client. An offline edit that syncs after the window is refused with a clear message, and the usher asks the Group Pastor to return it.
- Each edit carries the revision number it is based on, so a retried sync does not use up another edit.
- The pastor keeps a "Return for correction" action (reason required). It reopens the report to its usher for a fresh 24 hours with one extra edit, regardless of the cap.
- Applies to count, attendance, offering and fellowship submissions, and only to the original submitter, per row. In a split count each usher edits only their own section. Newcomer and convert records follow their own follow-up flow and are out of scope until the church asks.
- The reject-and-resubmit path built in B2 (`supersedes_id`) stays for rows already rejected. New corrections use edits. Do not drop the columns.
- Constants (24 hours, 3 edits, 1 extra edit on return) live in one config place.

### Split counts (several ushers at one location)

- Add `count_mode` (`single` or `section`, null for legacy) and `section_label` to count submissions. Derive a count-group key from (location, program type, occurrence date) so offline ushers need no shared id. A small `count_group` record holds state (`open`, `complete`, `conflict`), `finalized_by`, `finalized_at`, and optional configured zones per location.
- Single counts are never summed with each other; two singles are a conflict for the pastor to resolve. Sections are summed. Single plus section is a conflict.
- A lead usher closes the group; with configured zones it is complete when every zone has reported. The pastor approves the whole group.
- A location-week counts only when all its existing sections are approved (or approved plus pending when `include_pending=1`). Show partial approval as "n of m sections approved"; it is not counted.
- Legacy rows keep summing and are flagged "mode not recorded". They are never marked conflicts.
- Region and State see the total with a "split count" marker. Section detail shows only at Location and Group.
- Combined meetings use the same mechanism, keeping physical venue separate from the reporting scope.

### Workers' and leaders' attendance

- The system loads the roster for the level and location id; each person marks their name; the submission stores the IDs (and names if useful) of those present.
- Credit each present person to their **home location**, regardless of where the meeting was held. The report's location id and level say only where the meeting was held.
- Compute from worker-level rows deduplicated by worker, meeting type and week: present = distinct workers marked present; expected = distinct workers on the loaded roster. Never sum `expected_workers_count` across submissions.
- Store the expected roster as IDs (additive, for example `expected_worker_ids`) if only a count exists today.
- Label the metric "meetings reported". Do not label anything "faithfulness" until church leadership defines the denominator.

## C5. Metric catalogue

Every metric returns `{value, unit, window, status_rule, n_expected, n_received, n_counted, additivity}`. `value` is `null` when nothing counted. **Counted** means approved, or approved plus pending when `include_pending=1`. Rejected never counts.

| ID | Metric | Definition | Additivity |
|---|---|---|---|
| M01 | Latest occurrence attendance | Sum of counted location totals for the latest occurrence date of the program in scope | Additive across locations |
| M02 | Average per reporting unit | Sum of counted totals / counted reports over the window; delta against the previous window of equal length | Recomputed |
| M03 | Reporting coverage | received and counted over expected, with counts per state (approved, pending, returned, awaiting, late, missing, combined, zero reported) | Recomputed |
| M04 | Population mix | Sum of each of the six categories over counted reports, then share of the summed total | Recomputed |
| M05 | Offerings total | Sum of counted offering amounts by fund type and payment method. NGN only | Additive |
| M06 | Offering per report | M05 / counted offering reports | Recomputed |
| M07 | New converts | Convert records in the window within scope, with follow-up status | Additive |
| M08 | Newcomers | Newcomer records in the window | Additive |
| M09 | Workforce snapshot | active, pending verification, suspended, inactive; the parts sum to the total on register | Snapshot |
| M10 | Workers' meeting attendance | distinct present / distinct expected, per C4 | Recomputed |
| M11 | Meeting reporting coverage | meetings received / meetings expected where an expectation or event exists; otherwise "not defined" | Recomputed |
| M12 | Pending decisions | worker candidates, transfers, removal requests, event approvals, count approvals, by stage and age | Snapshot |
| M13 | Alpha attendance and converts | From submissions with `source_role='alpha'` per event occurrence | Additive within Alpha; snapshot across sessions for attendance |
| M14 | Satellite attendance and converts | From satellite submissions per event occurrence, with coverage against eligible locations | Additive across locations |
| M15 | Fellowship activity | Active fellowships, members, latest attendance and offering, share reporting. Location-scoped | Mixed (see C7) |
| M16 | Decline flag | M02 down 15% or more against the previous window | Derived |
| M17 | Event session figures | Per event, day and program type: counted attendance, reporters counted of reporters reporting, peak session, average per reporting unit, comparison with the previous event of the same kind | Peak and average; never summed across sessions |
| M18 | Attendance against expected population | Sum of counted attendance / sum of estimated population, over locations that have both a counted report and an estimate effective on that date. Also returns how many reporting locations had no estimate | Recomputed |

## C6. Dashboard

Layout (the prototype shows it exactly):

```
[breadcrumb]                              [4 wk | 8 wk]  [ ] Count reports pending review
Title: <scope name>                       Level . code
[Coverage strip: "n of m locations have reported", approved / pending / returned / not reported, zeros noted]
[Six cards: Latest Sunday | Average per reporting location | Approved offerings |
            New converts | Active workers | Workers' meeting attendance]
   each card: label, value, tag (Adds up / Recomputed / Snapshot), context line
[Children table                      ] [Needs attention (ranked, each links to the child scope)]
 coverage bar, latest, average,        [Waiting on a decision: candidates, transfers, removals]
 vs previous, offerings, workers,
 workers' meeting. Row click drills down.
[Weekly trend: line = average per reporting unit; bars = share counted; gaps for weeks with no counted report]
```

- At Location scope, replace the children table with the last 8 occurrences as rows. A week with no report is a row that says "Not reported".
- The Latest Sunday card carries M18 in its context line ("62% of expected"), and the children table has a "% of expected" column. A child whose reporting locations have no estimate shows "No estimate", not 0%.
- Every panel has explicit loading, empty ("No counted report") and error states. An error is never rendered as zero or "nothing needs attention".
- Dashboard bootstrap must be fast. Use per-scope, per-week pre-aggregation if raw scans are too slow, and report timings before and after (the audit saw about 16 seconds).
- **The dashboard is built incrementally.** Each slice adds its own card, its children-table column and its needs-attention rule. The dashboard is complete when all six cards exist.

## C7. Domain pages

One shared template with a `DomainPageConfig` (domain key, obligation source, KPI metric IDs, breakdown dimension, child table columns, leaf record columns, minimum score for person-level data, export columns). Adding a domain is a config change plus its metric functions. Template: controls, coverage strip for that domain's obligation, 4 to 6 KPI cards, breakdown tabs, children table and needs-attention, trend, records, export of what is on screen.

| Page | KPI cards (metrics) | Breakdown | Special rules |
|---|---|---|---|
| **Attendance (population counts)**: Sunday Worship, Monday Bible Study, Thursday Revival Hour | M01, M02, M03, M04, M18 (Sunday Worship), sections, last report | Program type | Shares hidden when nothing counted. "n sections" beside each location total |
| **Workers' attendance**: Saturday Workers Meeting | M10, M11, present, expected, late | Meeting level held | Worker names at Location and Group only. Counted at each worker's home location |
| **Leaders' meetings**: Tuesday | Meetings received, leaders present, by level held | Level | Own page. Coverage "not defined" |
| **Offerings** | M05 approved, awaiting, returned, M06, month and year to date | Fund type, payment method | Cards and table respond to the same filters. Aggregate only, never donor-level |
| **Newcomers and converts** | M07, M08, awaiting first follow-up, share followed up | Source program, follow-up status | Names and phones only at Location and Group. Existing follow-up statuses only |
| **Workforce** | M09 with reconciliation, M12 by stage, linked accounts | Status, unit | Parts sum to the total. Worker and user are separate |
| **House Caring Fellowship** | M15 | Fellowship | Location-scoped; no program spine. Remove the per-fellowship N+1 requests. Category gap: see D |
| **Retreat** | M17 | Program type by day | Below |
| **Global Crusade** | M13, M14, M17 | Program type by day, source | Below |
| **Conferences and programs** | Per-event totals, reporters assigned versus reported | Event | Coverage from assignments |

### Retreat page

Held twice a year, five to six days, region by region at a camp. Reports are Region-level with the region as scope and the venue kept separate. Inside the retreat run programs such as Bible Study, Revival Service, Faith Clinic and Seminars, each its own program type.

- Event selector (default latest past event). A matrix of program-type rows by day columns; each column header shows day number and date. A cell shows counted attendance, "n of m regions", and pending or returned counts, or "No report".
- Selecting a cell shows the by-region breakdown for that program and day; opening a region shows its own camp report. This answers: "what was the population of the Bible Study on day 2 of the last retreat".
- Event and date identify the retreat and the day. The five parameters identify the program and the reporting unit. Day number is derived from the event start date.
- Compare Easter with the previous Easter and December with the previous December only. Show the delta only when both exist.
- Do not invent expected sessions. Show "sessions reported" and "planned sessions not defined". An event may declare its planned sessions in a later slice.
- Region-level Sunday Worship at camp replaces local reports under the combined-meeting rule.
- Group and Location views have no retreat figures of their own; show an explanation.
- Cards: sessions reported, peak session, average per reporting region (delta), regions reporting, pending, returned. No card sums attendance across sessions.

### Crusade page

Held monthly, several days, with its own programs (Crusade Evening, Leadership Development Meeting, Impact Academy, Global Sunday Service). The crusade ground is the **Alpha** location: assigned workers record physical attendance and converts. Every church location joining from elsewhere is a **satellite** and reports as a normal local program.

- Same event selector and day-by-program matrix. Attendance and Converts toggle.
- Each cell shows Alpha, Satellite and a labelled "Total participation" (or "Alpha only", "Satellites only, no Alpha", "Total participation" with no number when nothing is counted), plus "n of m locations".
- Alpha is reported at State level. Region, Group and Location pastors see their satellites; Alpha shows at State level only. **Confirm with church leadership whether regional pastors should also see Alpha.**
- Expected satellites: every eligible location in scope, for any session that has a report. Expected Alpha reporters: approved `EventAssignment`; with none, coverage is "unknown".
- Cards: peak session (labelled total), peak satellite session, converts (Alpha plus satellite, labelled), satellite coverage, average per reporting location (delta against the previous crusade), pending. Converts add across sessions; attendance does not.
- Selecting a cell shows Alpha, then children by scope (satellite coverage bar and counted figure); opening a child goes one level down; at Location it shows that location's own report.

## C8. API contract (adapt to existing routers)

All endpoints take `scope_path`, `period_start`, `period_end`, `include_pending`, enforce scope server-side, and keep logic in `app/services/analytics/` (scope resolver, reporting-state calculator, metric registry), not in route handlers.

```
GET /api/v1/analytics/scope?scope_path=...
GET /api/v1/analytics/overview?scope_path=...&period_start=...&period_end=...&include_pending=0
GET /api/v1/analytics/programs/occurrences?scope_path=...&domain=...&program_type=...&program_level=...&event_id=...&date_from=...&date_to=...&include_pending=0
    -> counted rows grouped by (event, date, program type, source role), with coverage per C4
GET /api/v1/analytics/domains/{domain}?scope_path=...
```

`Metric` shape: `{ value: number|null, unit, window, status_rule, n_expected, n_received, n_counted, additivity, delta: { vs: "previous_window", pct: number|null } }`. No endpoint returns `0` where it means "no data".

## C9. Privacy rules (confirm with the church and its privacy lead)

- Person-level newcomer, convert and worker details: Location and Group only. Region and State see counts, statuses and ratios.
- Exports follow the same rule and include only what is on screen for the user's scope.
- This is a proposal, not legal advice, and does not replace a Nigeria Data Protection Act review.

## C10. Decisions

| Decision | Status |
|---|---|
| Six standing weekly programs, fixed | Confirmed by the church |
| Expected unit: location for all standing programs except Leaders Meeting (not defined) | Confirmed |
| Combined meeting at a higher level replaces local reports | Confirmed |
| Pending reports do not count | Confirmed |
| Group Pastor accepts location-level reports | Confirmed |
| Overdue approval alerts at 10h and 24h | Confirmed |
| Ushers may edit a submitted report for 24 hours, 3 times at most; the Group Pastor then approves | Confirmed (church meeting, 6 Nov) |
| The church holds an estimated population per location and wants attendance as a percentage of it | Confirmed (church meeting, 6 Nov) |
| Approval locks a report; "Return for correction" reopens it with one extra edit | Default. Confirm |
| An offline edit that syncs after the 24-hour window is refused | Default. Confirm |
| Estimates are set by the State Overseer only, and used for Sunday Worship only | Default. Confirm |
| Meaning of the estimate: expected Sunday attendance or total membership | Open. Ask the church; it changes what the percentage means |
| Retreat is region-level at a camp; Crusade has Alpha and satellite | Confirmed |
| Rejection creates a linked new submission | Superseded by the edit window (v2.1). Old path kept for rows already rejected |
| State-level reports auto-accepted | Default |
| Alpha visibility below State | Default: State only. Confirm |
| Person-level data at Location and Group only | Default. Confirm |
| Fellowship: one report per location per Sunday, six categories like counts | Church wants it; needs a schema and Field Utility change (slice B6) |
| Whether every location reports as a satellite for each crusade session | Default yes. Confirm |

---

# PART D: Slices, in order. Stop and report after each.

**Close-out for B1 (do first):** prove the backup restore by creating a throwaway Postgres cluster (initdb in a temp dir, another port, trust auth), restoring the snapshot, comparing row counts of key tables with the dev DB, then deleting it. Add a test that a Group-, Region- or State-level Sunday Worship count with no `ProgramEvent` still replaces covered locations' local reports.

**B2. Count review and realistic data**
- Review queue in Admin: pending count groups (location, program type, date) inside the approver's active scope, oldest first, with total, categories, number of sections, submitter, and age flags at 10h and 24h. Approve (applies to every row in the group) and Reject (reason required).
- Use an existing count-approval permission if there is one; otherwise add one. Report what exists. Auto-accept State-level reports.
- Additive migration: nullable `supersedes_id`, `rejection_reason`, `rejected_by_id`, `rejected_at`. Show correction history. List what the Field Utility needs to submit a correction; do not change the Utility in this slice.
- Needs attention: pending beyond 10h for the approver, beyond 24h also for the next level up; "Remind" action on unreported items.
- Dev-only seed script with a marker on every row and a `--remove` command; refuses to run if the database URL does not look like dev; snapshot first. Include approved, pending (some older than 24h), rejected with a correction, missing, one approved zero, one location with 3 sections, one Group-level combined meeting week, one location opened mid-period. Tests assert hand-calculated values.
- Deliver screenshots of the four personas showing real numbers.

**B2 close-out (do first)**
- Confirm `init_rbac.py` itself includes `counts:review` for Group Pastor, Region Pastor and State Overseer, with a test that fails if it is removed.
- Report measured dashboard load times (median of 5, cold and warm) for all four personas and the number of backend calls per State page load. Replace the many per-date and per-child calls with one grouped query per scope returning all children and all weeks, with pre-aggregation per scope and week if still slow. Target: State dashboard under 3 seconds cold on dev data; otherwise report the floor and why. Do this before adding more programs.
- Isolate the interim `Section: <label> |` note prefix in one function, marked legacy. B5 replaces it with real columns and a backfill.

**B2b. Expected population** (small; before the B3 pages)
- Inventory first: does any estimated or expected population field already exist? Report.
- Additive migration for `location_expected_population` per C4, a State Overseer permission, an audit entry on every change, an extra column in the hierarchy Excel template and import, and an edit screen in location management.
- Metric M18 in the metric service (pooled, same-locations rule), then the dashboard card line, the children-table column, location records, and the Attendance page. Needs-attention flag for estimates that look out of date (thresholds in config).
- Add estimates to the B2 demo data (same marker, same `--remove`), including two locations with no estimate and one above 100%.
- Tests: the percentage equals sum of attendance over sum of estimates for the same locations; locations without an estimate are left out and counted; missing reports do not lower it; the estimate effective on the week's date is used; above 100% is not capped.
- Stop and report.

**B3. Any program, any day**
- First inventory and report: how Retreat and Crusade events, their days, their sub-programs and the Alpha or satellite source are stored. If the model cannot express "event + day + program type", propose the smallest additive change.
- Build the `programs/occurrences` endpoint. Sunday Worship, Monday Bible Study and Thursday Revival Hour become configs of it.
- Build the Retreat and Crusade pages per C7 and the prototype. Build the Leaders' meetings page.

**B4. Workers' and leaders' attendance** per C4: roster IDs, deduplicated metrics, home-location credit, fix the doubled denominator, Workers' meeting card and page.

**B5. Split counts, usher edit window and Field Utility** per C4. These touch the same phone forms and the same rows, so do them together: `count_mode` and `section_label` columns with backfill, the revision table and edit endpoint with server-side window and edit-count enforcement, an edit screen in the Utility (showing time left and edits left), "Return for correction" replacing Reject in Admin, the edited badge and time-left in the review queue, and the Utility showing a returned report's reason.

**B6. House Caring Fellowship categories.** Verify today's fields; propose an additive change so fellowship attendance carries the six categories (adult male/female, young adult or campus male/female, youth male/female, children boys/girls) like counts; update the Field Utility form. Until then do not merge fellowship figures into the population mix.

**C. Dashboard completion.** Each earlier slice has already added its card. Finish the children table, needs-attention panel and trend chart to match the prototype; add the offerings and converts cards.

**D. Remaining domain pages.** Offerings, newcomers and converts, workforce, conferences, programs.

**E. Validation.** Permission matrix across personas and direct URL edits; formula fixtures re-run; timings on production-shaped data; fellowship N+1 removal; stale-server check.

---

# PART E: Tests

- Children sum to parent for every additive metric at every level; recomputed metrics equal the pooled ratio.
- `null` is never returned as `0`; a reported zero returns `0` with `n_counted >= 1`.
- Pending excluded by default, included only with `include_pending=1`; rejected never counted; latest uses date not value.
- Scope: in-scope child returns 200 and changes the figures; sibling, parent above maximum, and another State return 403; malformed returns 400. Reloading a URL reproduces the page.
- Person-level fields absent from Region and State responses.
- Alpha and satellite are never in one summed number without a label; coverage is "unknown", not 100%, when an event has no assignments.
- Attendance is never summed across sessions; converts and offerings are.
- Workers' attendance: expected is never summed across submissions; each present worker credits their home location.
- Edit window: the original submitter can edit while pending and within 24 hours; a fourth edit, an edit by another user, an edit after approval, and an edit after the window are all refused by the server. A retried sync does not consume another edit. Revisions record before and after. Return for correction grants a fresh window and one extra edit.
- Expected population: percentage equals sum of attendance over sum of estimates for the same locations; children's attendance and estimates sum to the parent's; locations without an estimate are left out and counted; a missing report never lowers it; the estimate effective on the week's date is used; above 100% is not capped.
- Hand-calculated fixtures cover zero, missing, pending, rejected with correction, multi-section, combined meeting, closed and newly opened locations. Never derive expected values by calling the code under test.

---

# PART F: What not to do

- No predictive analytics, forecasting or AI summaries.
- No separate dashboard per role. One template, four scopes.
- No ranking of sibling units by attendance.
- No person-level data above Group level.
- Never average rates across children, treat missing as zero, or treat unknown coverage as 100%.
- Never add attendance across sessions.
- No reporting-expectation table, "excused location" feature or `faithfulness` label.
- Do not claim hosted or production readiness.
