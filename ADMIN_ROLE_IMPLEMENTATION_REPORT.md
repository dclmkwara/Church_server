# Admin Role Policy Implementation Report

**Date:** 9 November 2026 (historical report; remote status updated 10 November)
**Scope:** Step A local policy and authorization implementation. Its initial remote attempt was blocked under the application identity. The subsequent approved migration-role reconciliation is complete; see [ADMIN_ROLE_RECONCILIATION_REPORT.md](ADMIN_ROLE_RECONCILIATION_REPORT.md).

## Mobile checkpoint

The analytics mobile correction is separately committed and pushed as `87eed27` (`Fix stale analytics stylesheet on dashboard`). The cause was a stale route-level stylesheet link (`?v=8`) loaded after the shell's newer stylesheet. The route now uses the shell's single stylesheet (`?v=10`). The desktop/mobile cascade test passed at widths 320, 360, 390, 640, and 768 px. The authenticated all-pages sweep was skipped because persona storage states and a live test base URL were not configured.

## Local role-policy changes

- Admin roles at scores 2-5 receive scoped dashboard/report access, reminders, program/event setup, and worker-change request permission. State Admin receives the State expected-population permission, including CSV operations.
- Pastor roles retain all same-level admin permissions and additionally hold approval and account-governance permissions. Automated checks confirm each pastor permission set contains its paired admin set and both share the same score.
- Expected-attendance access now checks score plus `population_estimates:manage`, not the exact role name.
- Event approval uses `programs:approve_events`, score, exact scope, and creator separation. If an admin changes an approved schedule, its approval resets to pending for same-level pastor approval.
- Worker transfer, removal, and status-change request endpoints accept actors with `workers:request_changes` when the worker's home location is inside the actor's scope. The approval stages still require `workers:approve` and remain unavailable to admin roles.
- The roles catalogue menu is permission-filtered by `rbac:read`.
- Reminder recipient selection still uses the Location Usher and Location Pastor role names to identify the intended recipient accounts. That is recipient resolution, not sender authorization; sender access uses permission and scope checks.
- Admin actions are not covered by one universal audit log. Expected-attendance changes and several workflow records retain actor IDs, but export downloads and some edits do not have a dedicated actor audit entry. This target item remains incomplete.

The full permission lists, role differences, authorization-name scan, target-action matrix, and menus for all eight personas are in [ADMIN_ROLE_AUDIT.md](ADMIN_ROLE_AUDIT.md).

## Remote RBAC preflight and result

A same-day public-schema snapshot was captured before the attempt and validated with `pg_restore --list`: `output/private-backups/remote-dev-public-pre-rbac-20261109T142219Z.dump` (666,514 bytes; 57 public table-data entries; SHA-256 `4217D938EB00870D829BE86C3AE941428AF011037B548E31490B924EB168C043`). The database was read-only exported immediately before the attempt and after it:

- Before: [remote-rbac-before-admin-role-final.json](output/remote-rbac-before-admin-role-final.json)
- After failed attempt: [remote-rbac-after-admin-role-attempt.json](output/remote-rbac-after-admin-role-attempt.json)

Both exports contain 20 roles, 82 permissions, and 928 grants; a structural comparison is identical. The reviewed local-default diff before attempting the write was 49 grants to add and 4 to remove (`users:assign_roles` from Location, Group, Region, and State Admin). Three permission records are absent remotely: `population_estimates:manage`, `programs:approve_events`, and `workers:request_changes`. The remote-only `resource:read` permission remains outside the local defaults.

The first remote attempt used the application identity and failed because the permissions write policy requires `app.role_score >= 9`. No synthetic score was set and the post-attempt export showed no changes. This blocker was resolved on 10 November by applying the reviewed Alembic data revision through the migration identity, which had `BYPASSRLS`; see [ADMIN_ROLE_RECONCILIATION_REPORT.md](ADMIN_ROLE_RECONCILIATION_REPORT.md) and [MIGRATION_LOG.md](MIGRATION_LOG.md). The policy itself was not changed.

## Verification

- Full repository suite: **320 passed, 1 skipped**. The skipped test is the authenticated mobile sweep, which requires State, Region, Group, and Location browser sessions. The non-authenticated Playwright CSS cascade checks passed.
- No FastAPI Cloud login or deployment was attempted; deployment remains user-run as previously requested.

## Not completed

- FastAPI Cloud deployment and live persona smoke tests.
- Universal audit coverage for admin setup actions, printable report/export, and Slice E validation; these remain later plan items.

## Checkpoint

Local Step A code and audit were committed as `9f957e0` (`Implement scoped admin role policies`). The remote RBAC synchronization is now recorded at `d71a9c4e2b60`. The application deployment remains unverified.
