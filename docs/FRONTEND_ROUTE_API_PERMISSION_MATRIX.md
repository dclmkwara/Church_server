# Church Admin Frontend Route, API, and Permission Matrix

This matrix records the contract used by the administrative frontend. Backend permission checks and the signed-in user's effective hierarchy path are authoritative. Frontend level and role labels control presentation only.

## Role and scope baseline

| Level | Backend role family | Effective reach | Oversight and technical permissions |
|---:|---|---|---|
| 1 | House Fellowship Leader | Assigned fellowship | Fellowship read and fellowship activity permissions. Routine submissions belong to the Level 1-2 source app. |
| 2 | Location Worker / Location Usher | Assigned location | Workers have base read; ushers also have source-entry permissions. Routine source entry belongs to the Level 1-2 source app. |
| 3 | Location Pastor / Location Admin | Assigned location and descendants | Pastor roles inherit report read, review, user approval and management permissions. Admin roles have technical CRUD and user-role permissions but do not inherit `reports:read`. |
| 4 | Group Pastor / Group Admin / Group Usher | Assigned group and descendants | Pastors inherit scoped reports and review; admins add group-level appointment permissions; ushers have data-entry permissions. |
| 5 | Region Pastor / Region Admin / Region Usher | Assigned region and descendants | Pastors inherit scoped reports and review; admins add region hierarchy management; ushers have data-entry permissions. |
| 6 | State Overseer / State Admin / State Usher | Assigned state and descendants | State Admin receives `reports:read`; State Overseer inherits pastor reporting/review and state hierarchy permissions. |
| 7 | National Overseer / National Admin | Assigned national scope and descendants | Pastor reporting/review plus national governance, media, public-intake, and audit permissions as assigned by role. |
| 8 | Continental Overseer / Continental Admin | Assigned continental scope and descendant nations | Pastor reporting/review plus continental governance permissions. Backend scope filtering must constrain reads to the user's assigned continental path. |
| 9 | Global Admin | Global scope | Full default permission set. |

Multiple roles may contribute permissions in the backend. Frontend identity displays the highest-scored role and its scope for navigation; it does not compute or grant permissions. Every request uses the backend access token, and the backend derives the principal's effective scope before accepting a caller-supplied descendant scope.

## Route and service families

| Frontend area | Backend API family | Read permission | Retained admin mutations | Source-entry policy |
|---|---|---|---|---|
| Program Counts | `/counts`, `/programs/events` | `counts:read`, `programs:read` | None in this console | Count create/update/delete routes in this frontend return 403. Level 1-2 app submits rows. |
| Offerings & Tithes | `/offerings` | `offerings:read` | No finance submission here; review is a separate permissioned workflow | Finance create route in this frontend returns 403. |
| Newcomers and Converts | `/records` | `records:read` | Follow-up changes only where a matching backend operation and permission exist | Registration route in this frontend returns 403. |
| Worker Attendance | `/attendance` | `attendance:read` | No attendance entry here | Attendance create route in this frontend returns 403. |
| Workers and Members | `/workers`, `/church-members`, `/users` | `workers:read`, `records:read`, `users:read` | Worker/user review, account state, and role assignment through their matching endpoints and permissions | Worker/member create and worker import routes in this frontend return 403. |
| Programs and Assignments | `/program-domains`, `/program-types`, `/program-events`, `/event-assignments` | `programs:read` | Configuration via `programs:manage`; worker assignment and approval via `programs:assign_workers` and `programs:approve_assignments` | These configure operations and responsibilities, not population or finance submissions. |
| Fellowship | `/fellowships`, fellowship activity endpoints | `fellowship:read` | Fellowship configuration remains governed by hierarchy permissions | Fellowship member/activity source forms in this frontend return 403. |
| Reports | `/reports/*` | `reports:read` | Refresh via `reports:refresh`; exports via report read authorization | Read-only; report queries and export scopes are backend constrained. |
| Announcements | `/announcements` | `announcements:read` | Create/update/publish/deactivate via `announcements:manage` | Public-facing content workflow, not operational source-data intake. |
| Media | `/media` | `media:read` | Gallery/item create and delete use distinct media permissions and API operations | Media management only. |
| Hierarchy and RBAC | `/hierarchy`, `/rbac` | `hierarchy:*`, `rbac:read` | Scope-specific hierarchy permissions; RBAC changes require `rbac:manage` | Technical administration only. |

## Count and finance field semantics

- A source count row represents one usher section/submission. Reusing its `client_id` is an idempotent retry; another usher section has a different ID and remains another row.
- Summary aggregation key is `(event_id, service_date, location_id)`. Service date is the linked event date when available, with the count row date as a fallback for unlinked events. Complementary sections sum; no row-level deduplication occurs in reporting.
- Each aggregate exposes the source-row count; the count detail view lists each source submission, section, submitter, assignment, and entered values.
- `latest_total` means the total for the most recently reported event/date/location group. `monthly_total` sums event/date/location groups in the current calendar month. `locations_reporting` counts unique locations with at least one current-month group. `average_total` is the rounded arithmetic mean of all event/date/location group totals in the visible scope.
- Finance reports sum only `offerings.status = 'approved'` and filter the exact selected offering date range before grouping rows into calendar-month display buckets. Finance entry date and event date are distinct fields; the report API uses the offering date.

## Verification boundaries

- `app/db/init_rbac.py` is the default permission/role seed contract. Existing production role assignments can be customized and must be verified live; the seed matrix alone is not proof of current assignments.
- `app/api/deps.py` and each API route's `PermissionChecker` are the authorization contract. `app/frontend/dclm_admin/auth_context.py` and `VISIBLE_MODULES` only affect UI visibility.
- Automated route tests invoke registered frontend endpoints directly and service tests use fake API clients; they do not prove deployed database permissions or real-user scope behavior.
- No credentials are stored in this matrix. Authenticated live verification evidence is recorded separately by role and level only.
