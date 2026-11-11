# Navigation Consolidation Report

**Status:** Proposal recorded before implementation. No routes or metrics changed in this proposal stage.
**Scope:** Levels 2–5 pastor and admin personas. The server remains the access boundary; sidebar visibility is only navigation.

## Refreshed page inventory

The table records the current application purpose and the primary overlap observed in the existing route/page structure. Access is based on the route guards and role permissions in the current source. `L2–L5` means the Location, Group, Region and State personas, with assigned hierarchy scope enforced by the request/backend.

| Page | Who should see it | Purpose | Overlap and disposition |
|---|---|---|---|
| Dashboard | L2–L5, admins and pastors | Scoped headline metrics, coverage, trends and attention | Overview for recurring Sunday counts; keep as the landing page. |
| Retreat | L2–L5 with program read | Day-by-day retreat event population and comparison | Shares event-matrix layout with Crusade, but remains a separate event type/page. |
| Crusade | L2–L5 with program read | Alpha and satellite counts, converts and day matrix | Shares event-matrix layout with Retreat, but retains its source distinction. |
| Leaders Meeting | L2–L5 with attendance read | Tuesday meeting records and roster metrics | Separate program from Workers Meeting; never merge. |
| Workers Meeting | L2–L5 with attendance read | Saturday meeting records and roster metrics | Separate program from Leaders Meeting; never merge. |
| Count Review | L2–L5 only with `counts:review` | Accepting pastor reviews pending count groups | Dashboard attention links to work; keep the full decision queue as a separate page. |
| Expected Attendance | State Admin and State Overseer with `population_estimates:manage` | Versioned State-managed location estimate and bulk upload | Dashboard card summarizes it; keep history and editing on this page. |
| Attendance | L2–L5 with `attendance:read` | Shared attendance reporting and drill-down | Recurring Program Attendance is a specialized population view; keep both, clarify labels. |
| Recurring Program Attendance | L2–L5 with count/report read | Sunday, Monday and Thursday attendance trends and coverage | Overlaps Dashboard Sunday metrics; retain as the multi-program detail view. |
| Finance Analytics | L2–L5 with `reports:read` | Financial summaries and trends in Reports | Overlaps the Finance record list; link to the Financial tab, do not merge records with analytics. |
| Newcomers | L2–L5 with `records:read` | Newcomer and convert detail/reporting | Summary may appear in Reports/Dashboard; keep a detail page. |
| Pastor Report | L2–L5 with `reports:read` | Printable, scoped, multi-domain report and exports | Aggregates concepts from detail pages; retain as a print/export document, not a replacement for detail pages. |
| Inbox | L2–L5 with the existing inbox/session access | Requests, notifications and decisions directed to the user | Overlaps workflow queues by surfacing actionable items; keep as the personal work list. |
| People | L2–L5 with the relevant people permissions | Entry to Workers, Members and App Users | Parent category only; use the existing specialized pages. |
| Church data | L2–L5 with relevant data permissions | Entry to Programs, Counts, Attendance and Finance | Category rather than a distinct consolidated data page. |
| Finance | L2–L5 with `offerings:read` | Offering/tithe records and record-level actions | Finance Analytics is a different aggregated view; retain both. |
| Fellowship | L2–L5 with `fellowship:read` | House Caring Fellowship groups and reports | Location-based source data; distinct from recurring-program attendance. |
| Organization | Group, Region and State (level 3–5) | Hierarchy and location management/read view | Not a substitute for dashboard drill-down; retain as the hierarchy workspace. |
| Reports | L2–L5 with `reports:read` | Summary, financial, attendance, trend and export tabs | Finance Analytics is its Financial tab; use a direct tab link rather than a duplicate report implementation. |
| Programs | L2–L5 with `programs:read` | Domains, program types, campaigns, events and assignments | Retreat/Crusade are event analytics, not program setup; link them separately. |
| Audit log | Users with `system:read_audit_logs` (current pastor grants; not admin grants) | Review recorded system actions | Cross-cutting accountability view; retain and permission-gate. |

### Disabled or unfinished navigation

- **Officials** exists in routes and role policy but is suppressed by the live sidebar's `unsupported_live_keys` guard. The code marks it unsupported in live mode; this is an explicit unfinished/configuration block, not a missing permission grant. It stays out of the proposed menu and is not enabled here.
- **Help & Docs** is not a current sidebar item. The old `/docs` link observed in the earlier audit returned 404, so no replacement link is proposed until a real user-facing page exists.
- The top-bar search is not part of the current sidebar inventory and was previously found unwired. This slice does not add search behavior.

## Proposed menu, before implementation

| Group | Menu items | Visibility rule |
|---|---|---|
| Overview | Dashboard | All in-scope L2–L5 personas. |
| Reports and decisions | Pastor Report; Reports; Count Review; Attendance; Recurring Program Attendance; Workers Meeting; Leaders Meeting; Newcomers | Report/attendance/record pages require their existing read permission; Count Review requires `counts:review`, so admins without it do not see approval actions. |
| Programs and events | Programs; Program Counts; Retreat; Crusade | `programs:read` for setup/event pages; `counts:read` for count records. |
| People | Workers; Members; App Users | `workers:read`, `records:read`, and `users:read`, respectively. Officials remains hidden while live support is disabled. |
| Money | Offerings and Tithes; Finance Analytics | `offerings:read` for the record page; Finance Analytics links directly to `/reports?tab=financial` and requires `reports:read`. |
| Church life and structure | Fellowship; Organization | `fellowship:read`; Organization is level 3+ and remains bounded to assigned scope. |
| Messages | Inbox; Communication | Inbox keeps existing access. Communication requires level 4+ and `announcements:read`. |
| Settings and accountability | Expected Attendance; Audit Log; Roles and Permissions | Expected Attendance requires level 5 and `population_estimates:manage`; Audit Log requires `system:read_audit_logs`; RBAC requires level 5 and `rbac:read`. |

The existing page URLs remain the destinations so bookmarks, external links and integrations do not break. Where a menu item is an entry to an existing tab (Finance Analytics), its URL preserves that tab selection. Pages with distinct data and definitions are linked, not merged. Approval controls remain inside their existing permission-gated pages; admins receive no new approval capabilities.

## Before and after menu inventory

Before: `Core`, `People`, `Church Data`, and `More`, with 17 sidebar entries; Officials was hidden in live mode. Expected Attendance was reachable only from the State Dashboard, and Audit Log was not a top-level sidebar entry.

After: the eight task groups in the proposal above. Exact entries for each of the eight personas will be recorded after permission filtering is implemented and verified. Expected Attendance and Audit Log will be visible only when their current permission gates pass.

## Mobile polish scope

The consolidation implementation will address the previously reported dashboard issues in the shared analytics presentation: separated reminder actions, plain-language status text, a single scope breadcrumb/title hierarchy, removal of “development records” wording, compact child cards without empty columns, waiting age in hours, readable trend axes, distinct Returned and Conflict colors, and removal of excess bottom padding. Values and calculations will not change.

## URL and route compatibility decision

No existing page route is being renamed or removed. The new menu links point to existing routes, so existing URLs continue to render directly rather than requiring redirects. Tests will cover the existing page routes and assert they remain registered; there are no legacy route aliases to redirect in this menu-only change.

## Verification and release

Pending implementation: menu visibility tests for all eight personas, old-route compatibility tests, responsive menu checks at 360/390/768 px, and the shared mobile polish checks. No deployment or push is included.

## Implementation and verification update

**Implemented locally; not pushed.** The shared shell now uses the proposed task-oriented menu. Menus are filtered by module, minimum hierarchy level and page permission. The mobile shortcut bar also checks the read permission for People, Programs and Finance. The deployed routes and their URLs are unchanged, so old links still open directly; there were no renamed URLs to redirect.

### Final menu by persona

Common to all eight Level 2–5 personas: Dashboard; Pastor Report; Reports; Recurring Program Attendance; Attendance; Saturday Workers Meeting; Tuesday Leaders Meeting; Newcomers; My Requests; Programs; Retreat; Crusade; Program Counts; Workers; Members; App Users; Offerings and Tithes; Finance Analytics; Fellowship; Inbox.

| Persona | Additional menu entries |
|---|---|
| Location Pastor | Count Review; Audit Log |
| Location Admin | None |
| Group Pastor | Count Review; Organization; Audit Log |
| Group Admin | Organization |
| Region Pastor | Count Review; Organization; Communication; Audit Log |
| Region Admin | Organization; Communication |
| State Overseer | Count Review; Organization; Communication; Documented Population; Audit Log; Roles and Permissions |
| State Admin | Organization; Communication; Documented Population |

These are the current demo-role menu results. In live mode the menu uses the authenticated account's permissions; the server continues to enforce each route and scope. Officials remains disabled in the live menu because source configuration marks that route family unsupported. Help & Docs is not included because the old `/docs` target returned 404 in the prior audit. No existing page was deleted or merged.

### Mobile and wording fixes

- The region/group card clipping came from a two-column mobile grid rule that left the coverage cell in an auto-sized second column. The corrected mobile card uses one full-width column, then a two-column metric list. No horizontal document overflow at 360, 390 and 768 px in the local component checks.
- The dashboard cards use plain badge wording; the waiting age is displayed in hours, including long waits. Returned and Conflict use separate colors. The expected-population link is now labelled Documented Population and highlights the correct menu item.
- The child table now has seven cells matching its seven headers; mobile detail figures share the final review cell rather than creating an extra blank column.
- No metric calculation, permission grant, database schema, or API was changed for this menu slice.

### Test results

Focused command: `.venv\\Scripts\\python.exe -m pytest -q tests/test_navigation_consolidation.py tests/test_analytics_mobile_layout.py tests/test_analytics_dashboard_chart.py tests/test_analytics_mobile_playwright.py`

Result: **20 passed, 1 skipped**. The skip is the authenticated remote/mobile sweep because this run did not have the four persona browser storage-state files configured. The local rendered-sidebar test covers all eight personas at 360, 390 and 768 px; dashboard card rendering covers State, Region, Group and Location at those widths. The test suite also checks that visible menu destinations have registered routes and that prior URLs remain registered.

The opt-in authenticated sweep is still needed for deployed visual confirmation. No screenshots from that authenticated sweep are claimed here. No push was made.

### Before/after menu by persona

The previous live menu used Core, People, Church Data and More. Across Levels 2–5, it showed Dashboard, Inbox, Workers, Members, App Users, Programs, Program Counts, both meeting pages, Offerings & Tithes, Newcomers, Attendance, Workflows, Fellowship and Reports. Count Review was pastor-only; Organization appeared from Group level; Communication appeared from Region level; Roles & Permissions appeared for the State Overseer. Officials was suppressed in live mode. Documented Population was only linked from the State dashboard, while Finance Analytics was nested as a Reports tab.

| Persona | Previous menu additions/limits | Consolidated menu additions/limits |
|---|---|---|
| Location Pastor | Count Review | Count Review; Audit Log |
| Location Admin | No review queue | No review queue |
| Group Pastor | Count Review; Organization | Count Review; Organization; Audit Log |
| Group Admin | Organization | Organization |
| Region Pastor | Count Review; Organization; Communication | Count Review; Organization; Communication; Audit Log |
| Region Admin | Organization; Communication | Organization; Communication |
| State Overseer | Count Review; Organization; Communication; Roles & Permissions | Count Review; Organization; Communication; Documented Population; Audit Log; Roles and Permissions |
| State Admin | Organization; Communication | Organization; Communication; Documented Population |

The page set is unchanged; the update reorganizes and names the links, makes Finance Analytics and Documented Population easier to find, and adds Audit Log to the pastor's accountability links. No page was merged or deleted: each has different record detail, approval state, source, or reporting definition. Existing URLs stay in service and open directly rather than redirecting.


Full Church_server suite after the final CSS and card markup adjustments: **377 passed, 3 skipped**. `git diff --cached --check` passed for the staged implementation. The 3 full-suite skips include the opt-in authenticated browser checks.
