# Admin Leftovers: Scoped Audit and Announcement Access

**Status:** Implemented and migrated on the remote development database. No navigation consolidation was done.

## Audit trail

- Authenticated API requests attach the actor name, highest role name/score, and effective scope to the SQLAlchemy request session.
- A central ORM flush hook writes append-only `audit_logs` rows for campaign, event, event-assignment, transfer, worker-removal, worker-status-change, and hierarchy-node create/update/delete operations. It stores the resource's scope path, actor scope, timestamp, action, role, and a small allowlist of changed fields. Free-text reasons, announcement text, contact details, and other personal data are omitted.
- Successful CSV, Excel, and PDF report exports each create an audit entry with report type, format, date range, actor, role, and scope. The endpoint commits the record before returning the completed file.
- The existing Audit Logs page is now available to Location, Group, Region, and State pastors with the `system:read_audit_logs` permission. API and page queries filter by the caller's maximum scope path. Entries show actor, role, action, resource, changed-field names, scope, and time. The view has no edit/delete controls. Admin roles do not receive the permission by default.
- Legacy audit rows with no `scope_path` metadata are excluded from the level 2–5 scoped view; no old row is assigned a guessed scope.

## Announcement workflow finding

`Announcement` has `published_at` and `is_active` fields, but no explicit `status` column. The existing workflow uses those fields and supports draft/publish/archive actions. Per the specified fallback, accounts without `announcements:manage` now see the scoped read-only list and detail; create/edit/publish/archive controls are hidden, and direct UI mutation routes refuse the action. Pastor permissions and the existing backend mutation workflow are unchanged. No new draft state or migration was introduced.

## Migration and remote verification

The additive data revision `d7a4c1e2f809` grants the existing `system:read_audit_logs` permission to Location Pastor, Group Pastor, Region Pastor, and State Overseer only. It does not add permission rows or change any RLS policy.

Before the migration, a fresh `public`-schema custom-format backup was written to `_dev_db_snapshots/pre_admin_audit_permission_20261110.dump` (777,392 bytes; SHA-256 `82A88C1137C266BBC1A7A0B1C27E03760E1F9CCA17C47D8D00A803EFAD256204`). `pg_restore --list` returned 990 lines and `pg_restore --file NUL` decompressed the archive successfully. A full-database dump using the runtime account was denied on the `auth` schema; the migration connection (`postgres`, `BYPASSRLS`) was used for the public-schema backup. The permission and role tables are in `public`.

Before/after role-permission exports are stored outside the repository with the local backup artifacts. Remote ledger advanced from `d71a9c4e2b60` to `d7a4c1e2f809`. Active role-permission pairs increased from 973 to 977; the only additions are the four pastor grants above. Permission rows stayed unchanged; no grant was removed. Existing policies remain `church_permissions_write` and `church_role_permissions_write` with `app.role_score >= 9`, plus read policies; the migration identity has `rolbypassrls=true`. No policy was weakened.

All remote actions and the backup are logged in [MIGRATION_LOG.md](MIGRATION_LOG.md).

## Verification

- Focused audit/announcement tests: **5 passed**.
- Full Church_server suite before the final export-audit test was added: **341 passed, 1 skipped**. Re-run the full suite after the next slice's changes.
- Source compilation passed for the modified application modules and migration.

## Limits

- Central ORM logging covers mutations made through authenticated SQLAlchemy sessions. Direct database writes, scripts that bypass the app session, and integrations that do not attach a request actor are not attributed by this hook.
- Admin setup actions are represented as changes to the relevant records; approval actions on those records are also captured as updates when they change the allowlisted workflow fields.
- CSV/XLSX/PDF export coverage refers to the existing Reports API exports. New printable-report/export actions will be added in their own slice.
