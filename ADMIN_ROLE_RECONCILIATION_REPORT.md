# Remote Admin Role Reconciliation

**Date:** 10 November 2026  
**Revision:** `d71a9c4e2b60`  
**Database:** Supabase development, session pooler

## Result

The role policy was applied through an Alembic data revision, not by running `init_rbac.py` against the remote database. The connection identity was PostgreSQL with `rolbypassrls = true`. The existing `church_permissions_write` policy allows writes only when `app.role_score >= 9`; the migration role bypasses RLS, so the policy did not need to be changed. The earlier rejected attempt had used a different identity and confirmed that the policy blocks non-bypass writers. This migration does not weaken row-level security.

The revision has an exact starting-state guard: 20 roles, 82 permission rows and 928 grants. It aborts if the remote state differs. The successful application advanced the ledger from `c6d7e8f9a012` to `d71a9c4e2b60`.

## Before and after

| Item | Before | After | Difference |
|---|---:|---:|---:|
| Roles | 20 | 20 | None |
| Permission rows | 82 | 85 | +3 |
| Role-permission grants | 928 | 973 | +49, -4; net +45 |

Added permission keys: `population_estimates:manage`, `programs:approve_events`, and `workers:request_changes`. The remote-only `resource:read` permission is preserved. No permission rows were removed.

The grant additions and removals are recorded as code in the migration and as full JSON exports:

- Before: [remote-rbac-before-admin-role-20261110.json](output/remote-rbac-before-admin-role-20261110.json)
- After: [remote-rbac-after-admin-role-20261110.json](output/remote-rbac-after-admin-role-20261110.json)
- Migration history: [MIGRATION_LOG.md](MIGRATION_LOG.md)

The four removed grants were `users:assign_roles` from Location, Group, Region, and State Admin. Admins therefore cannot manage pastor/admin account access. Admins received the scoped report/statistics, reminder, worker-change-request and expected-population grants defined for their level. Count and offering review remain pastor-only. State Admin can manage documented-population records at score 5. Pastor roles retain approval and governance permissions.

## RLS policy note

`church_permissions_write` is `FOR ALL TO PUBLIC` with both `USING` and `WITH CHECK` requiring `COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int >= 9`. `church_rls_permissions_read` allows SELECT. The migration ran as PostgreSQL with `BYPASSRLS`; it did not assign a synthetic score and did not alter either policy.

The first migration attempt failed because `permissions.operation` is a required column. Alembic rolled back the transaction; a read-only check confirmed the ledger and RBAC counts remained at baseline. The corrected revision sets `operation='CREATE'` and completed successfully.

## Verification and remaining deployment work

Focused role, event authorization, expected-population and fellowship tests passed: **68 passed**. The migration's before/after structural diff matches the reported additions and removals. Application deployment and live role login smoke tests remain pending; no FastAPI Cloud deployment was attempted.

The full persona permission matrix and menu visibility remain in [ADMIN_ROLE_AUDIT.md](ADMIN_ROLE_AUDIT.md), now at the repository root.
