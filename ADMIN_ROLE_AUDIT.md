# Admin Role and Permission Audit

**Scope:** Location, Group, Region and State governance personas; permission defaults and guards reviewed at the current policy implementation. The matrix is generated from `app/db/init_rbac.py`; its grant reconciliation was applied to remote development at `d71a9c4e2b60` and is verified by before/after exports.

## Earlier plan status

- **Step 0 - hygiene:** completed per `ANALYTICS_FULL_PLAN_STEP0_REPORT.md`. It reports 253 passing tests, redacted DB error logging, a secrets scan, and the generated State expected-attendance CSV template.
- **Step 1 - remote migration/deployment:** the November 7 report records `e2b4c6d8f013`; the later B5 close-out in `MIGRATION_LOG.md` records the remote at `b5f7a9c2d341`, after `a4d92c16e7b3`, `b5e6f8a1c234`, and `b5f7a9c2d341` were applied. FastAPI Cloud deployment was not completed. B6 was applied remotely at `c6d7e8f9a012`. The approved admin role data revision was applied at `d71a9c4e2b60`; the RBAC totals are now 20 roles, 85 permissions and 973 grants. FastAPI Cloud deployment remains pending.
- **Navigation page audit:** exists at repository root as [`NAVIGATION_PAGE_AUDIT.md`](NAVIGATION_PAGE_AUDIT.md). No menu consolidation has been done.

## Governance roles and scope

Each pastor/admin pair has the same score and therefore the same maximum hierarchy scope, subject to the assigned `path` and server scope filter. A score does not let an account cross its assigned path. Pastors have additional review, approval, account-access and governance permissions; an admin role is not intended to outrank its pastor.

The app's canonical role defaults currently define these eight level 2-5 roles:

### Location Admin - score 2

`announcements:read`, `attendance:create`, `attendance:read`, `attendance:update`, `counts:create`, `counts:read`, `counts:remind`, `counts:update`, `fellowship:create`, `fellowship:read`, `fellowship:update`, `notifications:read`, `offerings:create`, `offerings:read`, `offerings:update`, `programs:create_event`, `programs:manage`, `programs:read`, `records:create`, `records:read`, `records:update`, `reports:read`, `statistics:read`, `sync:batch`, `users:create`, `users:read`, `users:update`, `workers:create`, `workers:read`, `workers:request_changes`, `workers:update`

### Location Pastor - score 2

`announcements:manage`, `announcements:read`, `attendance:create`, `attendance:delete`, `attendance:read`, `attendance:update`, `counts:create`, `counts:delete`, `counts:read`, `counts:remind`, `counts:update`, `fellowship:create`, `fellowship:delete`, `fellowship:read`, `fellowship:update`, `notifications:read`, `offerings:create`, `offerings:delete`, `offerings:read`, `offerings:review`, `offerings:update`, `programs:approve_events`, `programs:create_event`, `programs:manage`, `programs:read`, `rbac:read`, `records:create`, `records:delete`, `records:read`, `records:update`, `reports:read`, `reports:refresh`, `statistics:read`, `sync:batch`, `users:approve`, `users:assign_roles`, `users:create`, `users:deactivate`, `users:delete`, `users:read`, `users:update`, `workers:approve`, `workers:create`, `workers:read`, `workers:request_changes`, `workers:update`

### Group Admin - score 3

`announcements:read`, `attendance:create`, `attendance:read`, `attendance:update`, `counts:create`, `counts:read`, `counts:remind`, `counts:update`, `fellowship:create`, `fellowship:read`, `fellowship:update`, `notifications:read`, `offerings:create`, `offerings:read`, `offerings:update`, `officials:manage`, `officials:read`, `programs:approve_assignments`, `programs:assign_workers`, `programs:create_event`, `programs:manage`, `programs:read`, `records:create`, `records:read`, `records:update`, `reports:read`, `statistics:read`, `sync:batch`, `users:create`, `users:read`, `users:update`, `workers:create`, `workers:read`, `workers:request_changes`, `workers:update`

### Group Pastor - score 3

`announcements:manage`, `announcements:read`, `attendance:create`, `attendance:delete`, `attendance:read`, `attendance:update`, `counts:create`, `counts:delete`, `counts:read`, `counts:remind`, `counts:review`, `counts:update`, `fellowship:create`, `fellowship:delete`, `fellowship:read`, `fellowship:update`, `notifications:read`, `offerings:create`, `offerings:delete`, `offerings:read`, `offerings:review`, `offerings:update`, `officials:manage`, `officials:read`, `programs:approve_assignments`, `programs:approve_events`, `programs:assign_workers`, `programs:create_event`, `programs:manage`, `programs:read`, `rbac:read`, `records:create`, `records:delete`, `records:read`, `records:update`, `reports:read`, `reports:refresh`, `statistics:read`, `sync:batch`, `users:approve`, `users:assign_roles`, `users:create`, `users:deactivate`, `users:delete`, `users:read`, `users:update`, `workers:approve`, `workers:create`, `workers:delete`, `workers:read`, `workers:request_changes`, `workers:update`

### Region Admin - score 4

`announcements:read`, `attendance:create`, `attendance:read`, `attendance:update`, `counts:create`, `counts:read`, `counts:remind`, `counts:update`, `fellowship:create`, `fellowship:read`, `fellowship:update`, `hierarchy:create_fellowship`, `hierarchy:create_group`, `hierarchy:create_location`, `hierarchy:update_fellowship`, `hierarchy:update_group`, `hierarchy:update_location`, `hierarchy:update_region`, `notifications:read`, `offerings:create`, `offerings:read`, `offerings:update`, `officials:manage`, `officials:read`, `programs:approve_assignments`, `programs:assign_workers`, `programs:create_event`, `programs:manage`, `programs:read`, `records:create`, `records:read`, `records:update`, `reports:read`, `statistics:read`, `sync:batch`, `users:create`, `users:read`, `users:update`, `workers:create`, `workers:read`, `workers:request_changes`, `workers:update`

### Region Pastor - score 4

`announcements:manage`, `announcements:read`, `attendance:create`, `attendance:delete`, `attendance:read`, `attendance:update`, `counts:create`, `counts:delete`, `counts:read`, `counts:remind`, `counts:review`, `counts:update`, `fellowship:create`, `fellowship:delete`, `fellowship:read`, `fellowship:update`, `hierarchy:create_fellowship`, `hierarchy:create_group`, `hierarchy:create_location`, `hierarchy:update_fellowship`, `hierarchy:update_group`, `hierarchy:update_location`, `hierarchy:update_region`, `notifications:read`, `offerings:create`, `offerings:delete`, `offerings:read`, `offerings:review`, `offerings:update`, `officials:manage`, `officials:read`, `programs:approve_assignments`, `programs:approve_events`, `programs:assign_workers`, `programs:create_event`, `programs:manage`, `programs:read`, `rbac:read`, `records:create`, `records:delete`, `records:read`, `records:update`, `reports:read`, `reports:refresh`, `statistics:read`, `sync:batch`, `users:approve`, `users:assign_roles`, `users:create`, `users:deactivate`, `users:delete`, `users:read`, `users:update`, `workers:approve`, `workers:create`, `workers:delete`, `workers:read`, `workers:request_changes`, `workers:update`

### State Admin - score 5

`announcements:read`, `attendance:create`, `attendance:read`, `attendance:update`, `counts:create`, `counts:read`, `counts:remind`, `counts:update`, `fellowship:create`, `fellowship:read`, `fellowship:update`, `hierarchy:create_fellowship`, `hierarchy:create_group`, `hierarchy:create_location`, `hierarchy:create_region`, `hierarchy:delete_fellowship`, `hierarchy:delete_group`, `hierarchy:delete_location`, `hierarchy:delete_region`, `hierarchy:update_fellowship`, `hierarchy:update_group`, `hierarchy:update_location`, `hierarchy:update_region`, `hierarchy:update_state`, `notifications:read`, `offerings:create`, `offerings:read`, `offerings:update`, `officials:manage`, `officials:read`, `population_estimates:manage`, `programs:approve_assignments`, `programs:assign_workers`, `programs:create_event`, `programs:manage`, `programs:read`, `records:create`, `records:read`, `records:update`, `reports:read`, `statistics:read`, `sync:batch`, `users:create`, `users:read`, `users:update`, `workers:create`, `workers:read`, `workers:request_changes`, `workers:update`

### State Overseer - score 5

`announcements:manage`, `announcements:read`, `attendance:create`, `attendance:delete`, `attendance:read`, `attendance:update`, `counts:create`, `counts:delete`, `counts:read`, `counts:remind`, `counts:review`, `counts:update`, `fellowship:create`, `fellowship:delete`, `fellowship:read`, `fellowship:update`, `hierarchy:create_fellowship`, `hierarchy:create_group`, `hierarchy:create_location`, `hierarchy:create_region`, `hierarchy:delete_fellowship`, `hierarchy:delete_group`, `hierarchy:delete_location`, `hierarchy:delete_region`, `hierarchy:update_fellowship`, `hierarchy:update_group`, `hierarchy:update_location`, `hierarchy:update_region`, `hierarchy:update_state`, `notifications:read`, `offerings:create`, `offerings:delete`, `offerings:read`, `offerings:review`, `offerings:update`, `officials:manage`, `officials:read`, `population_estimates:manage`, `programs:approve_assignments`, `programs:approve_events`, `programs:assign_workers`, `programs:create_event`, `programs:manage`, `programs:read`, `rbac:read`, `records:create`, `records:delete`, `records:read`, `records:update`, `reports:read`, `reports:refresh`, `statistics:read`, `sync:batch`, `users:approve`, `users:assign_roles`, `users:create`, `users:deactivate`, `users:delete`, `users:read`, `users:update`, `workers:approve`, `workers:create`, `workers:delete`, `workers:read`, `workers:request_changes`, `workers:update`


## Material pastor/admin differences

- **Location (score 2):** Location Pastor adds announcements management, offering review, user and worker approvals, account-role assignment, RBAC read, report refresh and deletion permissions; Location Admin has reminder, report/statistics read, event setup and worker-change request permissions. Location Pastor does not have direct worker deletion; removal is escalated.
- **Group (score 3):** Group Pastor adds count review, offering review, worker approval/deletion, user approval/access management, event approval, announcements management, report refresh and RBAC read. Group Admin can schedule/assign event workers and review event-worker assignments but cannot review counts or offerings, approve workers, or manage account access.
- **Region (score 4):** Same review/approval separation as Group; both have region-level hierarchy management and event-worker assignment setup. Region Pastor has review/approval and governance permissions.
- **State (score 5):** Both State Admin and State Overseer currently have expected-population management and State hierarchy permissions. State Overseer alone has count/offering/worker/user approvals, event approval, account-role assignment, announcement management, report refresh and RBAC read.

## Authorization checks that were name-based or described in pastor terms

The code scan found these relevant cases. Fixes in the current role-policy work use permissions plus score/path where applicable; remaining names below are data classification or role-catalog protection, not authorization to perform an operational action.

| File and function | Check | Treatment |
|---|---|---|
| `app/api/v1/routes/programs.py` - `_is_event_pastor_for_scope`, `_require_event_pastor` | Previously matched role names; now requires same reporting-level score, `programs:approve_events`, exact scope path, and blocks the event creator from approving. | Permission/score/path check. |
| `app/frontend/dclm_admin/routes/programs.py` - event detail approval control | Previously matched the expected pastor role label; now checks `programs:approve_events`. | Permission-driven UI. |
| `app/api/v1/routes/dashboard.py` - `_can_manage_expected_population` | Previously required the exact `State Overseer` role name; now score 5 plus `population_estimates:manage`. | Allows State Admin and State Overseer; path still must be State scope. |
| `app/frontend/dclm_admin/routes/expected_population.py` - `_can_manage_expected_population` | Previously named for the State Overseer role; now score 5 plus the same permission. | Allows both State governance personas. |
| `app/api/v1/routes/counts.py` - `_eligible_reminder_recipients` | `Location Usher` and `Location Pastor` role names identify the intended recipient account classes. This is recipient selection, not sender authorization. | Kept; sender uses `counts:remind`, level score and scope checks. |
| `app/api/v1/routes/rbac.py` - `update_role`, `delete_role`, `set_role_permissions`, `remove_role_permission` | Role names prevent editing/deleting system, field-worker and reserved enterprise role definitions. | Kept as explicit catalog safeguards; supported score range is also checked. |

Other code uses score and permission gates, with some error text still using pastoral-office wording: `counts.py::_review_target`, `approvals.py` worker-request decisions, and `workers.py` registration/approval. Those text labels describe the accountable office; they do not grant access by string matching. The `church_members.py` docstring also says "location pastors" although the route gate is `records:create`; update wording remains a documentation cleanup.

## Target action check

| Action | Admin today (after local changes) | Pastor today | Alignment / limitation |
|---|---|---|---|
| View dashboards/statistics in assigned scope | Yes (`reports:read`, `statistics:read`); same level/path. | Yes. | Aligned. |
| Set up programs, campaigns, events and assignments | Has program management/event creation; Group/Region/State Admin also has assignment setup/approval permission. Location-scoped event creation is available. | Same setup, plus event approvals; pastor-created same-scope events are auto-approved. | Aligned for setup. Event catalog operations are broader than event scheduling at State score; retain careful review of catalog routes. |
| Approve events | No `programs:approve_events`. | Yes at own level/path; cannot approve own submitted event. | Aligned. |
| Expected attendance including State CSV | State Admin only at score 5 with `population_estimates:manage`; lower admins cannot. CSV preview is read-only and apply creates versions/audit entries. | State Overseer can do the same. | Aligned with target. No values seeded. |
| Send reminders | Admin roles receive `counts:remind`; endpoint checks permission and jurisdiction. Recipients remain eligible Location Ushers and Location Pastor only. | Yes. | Aligned. Admin dashboard attention panel now loads when reminder permission is present. |
| Exports | Admins have `reports:read`; report endpoints expose CSV/Excel/PDF exports under that read capability. | Yes. | Aligned; no separate export permission exists. Export downloads are not currently a dedicated audit event. There is no universal audit event for every admin read/write action; this remains a target gap. |
| Close count groups | Location Admin can close a group at its assigned location through `counts:create`; higher-level admins fail the exact-location close check because count groups are closed at the reporting location. | Location Pastor can close at the assigned location. | Aligned at Location; Group/Region/State admins cannot close a location group through this endpoint. |
| Prepare transfer/removal/status requests | All four admin roles have `workers:request_changes`; request routes use the permission and require the worker's home location to be inside the actor's assigned scope. Location actors are limited to their own location; higher-level admins may prepare requests for a worker below their scope. | Location Pastor can prepare them too. | Aligned. |
| Approve/reject counts and offerings | Cannot: admin defaults do not include `counts:review` or `offerings:review`. | Authorized pastor roles can review at the configured level. | Aligned; API and menu remain permission gated. |
| Approve worker/user requests | Cannot: admin defaults do not include `workers:approve` or `users:approve`. | Pastor roles have these, subject to level gates. | Aligned. |
| Manage admin account/access | Cannot assign roles; same-level account updates are rejected without `users:assign_roles`. | Pastor has `users:assign_roles` and may manage lower/equal roles within score/scope rules. | Aligned, though account edit audit coverage should be checked in the workflow audit. |
| Change role policy | No role receives `rbac:manage`; role-definition changes remain unavailable through direct role editing. Pastor has read-only `rbac:read` at State scope. | Same. | Governance workflow is not implemented; no direct grants/revokes were enabled. |
| Draft/publish announcements | Admin has read only; no draft-only capability. Pastor has `announcements:manage`. | Can manage/publish. | Draft-only workflow is explicitly still open. |
| Edit hierarchy | Region/State Admin has corresponding hierarchy update permissions; changes carry actor fields in the relevant models where supported. | Same and broader destructive permissions. | Partially aligned; there is not a universal audit record for every admin read/write action. |

Admins cannot approve their own event or event-worker assignment. Count and offering approvals are unavailable to admins by permission. Event-worker assignment approval is allowed only where the role has `programs:approve_assignments`; self-approval is rejected.

## Menus under current permission and level rules

Officials remains disabled in live mode. Menu labels below are the configured sidebar groups/items after level and permission filtering; mobile uses shortcuts plus the menu drawer.

| Persona | Visible sidebar pages |
|---|---|
| Location Pastor | Dashboard; Inbox; Workers, Members, App Users; Programs, Program Counts, Saturday Workers Meeting, Tuesday Leaders Meeting, Offerings & Tithes, Newcomers, Attendance; Workflows, Fellowship, Reports. |
| Location Admin | Same as Location Pastor; no Count Review, Organization, Communication, or Roles & Permissions. |
| Group Pastor | Location set plus Count Review and Organization. |
| Group Admin | Same level modules as Group Pastor, but no Count Review. |
| Region Pastor | Group set plus Communication. Count Review visible. |
| Region Admin | Same level modules as Region Pastor, but no Count Review. |
| State Overseer | Region set plus Roles & Permissions. Count Review visible. Expected attendance management is linked from Dashboard. |
| State Admin | State/Region modules without Count Review or Roles & Permissions. Expected attendance management is linked from Dashboard. |

The "same level modules" statement reflects the source configuration; the Count Review and Roles & Permissions items are separately permission-filtered. Live Officials remains suppressed even for level 4+.

## Verification boundary

The role defaults and route guards are reconciled to remote development at `d71a9c4e2b60`. The reviewed before/after exports are linked in `ADMIN_ROLE_RECONCILIATION_REPORT.md`. `init_rbac.py` was not run against remote. The mobile changes, printable report/export work and Slice E validation are still separate plan items.
