# Permissions Matrix

This matrix maps route groups to permissions. All writes are scoped by `path`.

## Users
- `users:read` → list/get/search
- `users:create` → create/auto-create
- `users:update` → update
- `users:assign_roles` → assign roles
- `users:delete` → delete

## Workers
- `workers:read` → list/get/search
- `workers:create` → create
- `workers:update` → update
- `workers:delete` → delete

## Hierarchy
- `hierarchy:manage` → create/update/delete
- `hierarchy:read` → list/get/tree/search

## Programs
- `programs:read` → list/get
- `programs:manage` → create/update/delete

## Counts
- `counts:read` → list/aggregate/stats
- `counts:create` → create/batch
- `counts:update` → update
- `counts:delete` → delete

## Offerings/Tithes
- `offerings:read` → list/stats
- `offerings:create` → create/batch
- `offerings:update` → update
- `offerings:delete` → delete

## Attendance
- `attendance:read` → list/stats
- `attendance:create` → create/batch
- `attendance:update` → update
- `attendance:delete` → delete

## Records
- `records:read` → list/get
- `records:create` → create/batch
- `records:update` → update
- `records:delete` → delete

## Announcements/Information
- `announcements:read` → list/get
- `announcements:manage` → create/update/delete/deactivate

## Media
- `media:read` → list/get
- `media:manage` → create/delete

## Reports
- `reports:read` → report queries and exports
- `reports:refresh` → refresh materialized views

## Statistics
- `statistics:read` → population/church/user stats

## Sync
- `sync:batch` → batch upload
- `sync:read_changes` → incremental changes
- `sync:conflicts` → view conflicts
- `sync:resolve` → resolve conflicts

## Approvals
- `approvals:read` → list requests
- `approvals:manage` → approve/reject

## RBAC
- `rbac:read` → list permissions/roles/scores
- `rbac:manage` → create/update/delete

## Recovery
- `recovery:request` → request reset
- `recovery:verify` → verify token
- `recovery:reset` → reset password
- `recovery:questions` → set/read/update recovery questions

