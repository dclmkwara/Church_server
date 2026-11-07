# Full Plan Step 1 Report

**Date:** 7 November 2026  
**Scope:** Remote development database preflight, migration, RBAC reconciliation, and deployment-step gate.

## Result

The remote development database is now at Alembic revision `e2b4c6d8f013`. The `d4a9c1e7f235` and `e2b4c6d8f013` migrations completed and were verified through the session pooler. No demo rows were deleted and no expected-population values were seeded.

The pre-migration Alembic discrepancy was explained: the runtime role could not see the `alembic_version` row because RLS applies to that table. The privileged local restore showed the pre-migration revision was `c2e5a8f14b31`. The remote stamp set that same revision before upgrade; it did not alter application rows or schema.

## Evidence and changes

- A remote development dump was created before migration and validated with `pg_restore --list` (1,318 archive entries). It is stored outside Git under `output/private-backups/`.
- Pre-migration catalogs showed 52 public tables, 792 columns, 493 indexes, 199 constraints, and 102 policies. The pre-migration archive ledger was `c2e5a8f14b31`.
- No `B2_DEMO:` marker rows were present.
- Reminder records and expected-population tables exist after migration, with RLS enabled and expected policies/indexes. The expected-population table is empty.
- Existing `counts:review` grants were present for the Group Pastor, Region Pastor, and State Overseer. `counts:remind` was added as a distinct permission and granted to those pastors plus the higher authority roles.
- JSON role/permission exports before and after show 20 roles unchanged, permission count 81 to 82, grants 919 to 928, nine intended grants added, and no existing grants removed. `init_rbac.py` was not run.
- The local Alembic proof exercised upgrade, one-step downgrade, and re-upgrade on a restored disposable database. Supabase-only `supabase_vault` objects were excluded because they are unavailable in the local PostgreSQL installation.
- Remote execution details are recorded in [MIGRATION_LOG.md](MIGRATION_LOG.md).

## Tests and deployment

The full suite passed: **254 passed**, with one third-party deprecation warning. No cloud deployment was attempted. The installed `fastapi` command exits because the `fastapi[standard]` extra is missing. After installing that documented extra in the intended deployment environment, the deploy command is `fastapi deploy`; then confirm the live commit and smoke-test login and the State dashboard. The remote State timing sample is also outstanding.

## Not done

- FastAPI Cloud deployment and live-commit confirmation.
- Remote State dashboard timing sample with `DCLM_DASHBOARD_PERF=1`.
- Navigation audit and B3, which are continuing locally under the accepted plan.

## Commit

Step 1 code checkpoint: `510ffe76d535b16b7eb076e51c5f94d2ac358606` (`add scoped reminder permission and row policies`). This report and the migration log are committed separately.
