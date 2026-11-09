# Remote Development Database Migration Log

All timestamps are Africa/Lagos (UTC+01:00). Connection strings, usernames, passwords, and tokens are intentionally omitted.

## 2026-11-07 — Step 1 preflight

| Time (approx.) | Revision / command | Mode | Result |
|---|---|---|---|
| 21:42–21:44 | `pg_dump --format=custom --no-owner --no-privileges --host <Supabase session-pooler> --port 5432 --username <redacted> --dbname <redacted> --file output/private-backups/remote-dev-pre-migration-20261107.dump --no-password` | Remote read / local backup | Archive created (913,731 bytes); `pg_restore --list` returned exit 0 with 1,318 archive entries. The backup is local and excluded from Git. |
| 21:45 | Direct database endpoint DNS/TCP reachability check, port 5432 | Remote network check | Direct hostname returned no A record; one AAAA record was returned, but its TCP connection was unreachable from this host. |
| 21:46 | Configured session-pooler endpoint check, port 5432, via the `pg_dump` connection | Remote read | Completed as part of the valid archive capture. |
| 21:48 | `SELECT version_num FROM alembic_version ORDER BY version_num` | Remote read, application runtime role | Returned no rows. Later check showed `alembic_version` has RLS enabled and the runtime role cannot bypass it, so this was a visibility result, not evidence of an empty ledger. |
| 21:49 | Read-only RBAC query joining `roles`, `role_scores`, `role_permissions`, and `permissions` for count-review/reminder permissions | Remote read, application runtime role/session pooler | `counts:review` is granted to Group Pastor (score 3), Region Pastor (score 4), and State Overseer (score 5). `counts:remind` does not yet exist. |
| 21:49 | `SELECT to_regclass(...)` for `count_reminder_recipients`, `location_expected_population`, and `counts` | Remote read, application runtime role/session pooler | Reminder and expected-population tables are absent; `counts` exists. |
| 21:49 | `SELECT split_part(note, ' |', 1), count(*) FROM counts WHERE note LIKE 'B2_DEMO:%' GROUP BY 1` | Remote read, application runtime role/session pooler | No B2 demo markers found. |
| 21:53–21:57 | Read-only public catalog queries for tables, columns, indexes, constraints, policies, and Alembic ledger | Remote read, application runtime role | 52 tables, 792 columns, 493 indexes, 199 constraints, 102 policies. Tables, columns, indexes, and constraints match the saved catalog snapshot that recorded `c2e5a8f14b31`. |
| 22:00 | Read-only export of `roles`, `permissions`, and `role_permissions` to `output/remote-rbac-before-step1.json` | Remote read, application runtime role | Export contains 20 roles, 81 permissions, and 919 grants. `init_rbac.py` was not run. |
| 22:03 | Restored the verified pre-migration archive to a disposable local database and read `public.alembic_version` with the local privileged role | Local read only | The archive contains `c2e5a8f14b31`. The runtime-role query had hidden this row because of RLS; the prior one-row catalog snapshot was correct. |
| 22:04 | `alembic stamp c2e5a8f14b31` | **REMOTE WRITE**, session pooler port 5432 | Success. The pre-migration archive already contained `c2e5a8f14b31`; the stamp set the ledger to that same revision and changed no application rows or schema. |
| 22:05 | `alembic upgrade e2b4c6d8f013` | **REMOTE WRITE**, session pooler port 5432 | Success. Applied `d4a9c1e7f235` and `e2b4c6d8f013`. |
| 22:06 | Read-only verification of ledger, table RLS, policies, indexes, expected-estimate row count, and reminder grants | Remote read, migration session pooler | Ledger is `e2b4c6d8f013`; both tables exist with RLS enabled; reminder table has SELECT and INSERT policies; expected table has read and State-write policies; expected-estimate rows = 0; all required pastor grants are present. |
| 22:07 | Read-only export of `roles`, `permissions`, and `role_permissions` to `output/remote-rbac-after-step1.json`; JSON diff against pre-migration export | Remote read, migration session pooler | 20 roles, 82 permissions, 928 grants. Diff: only `counts:remind` added and nine intended grants added; zero existing grants removed. |

Local proof of the `c2e5a8f14b31 → d4a9c1e7f235 → e2b4c6d8f013` chain succeeded on a restored disposable database after excluding the Supabase-only `supabase_vault` extension/schema data, which this local PostgreSQL installation does not provide. The proof included upgrade, one-step downgrade, and re-upgrade. Remote migrations used the session-pooler connection, not a transaction pooler. No application rows were deleted or estimates seeded.


## 2026-11-07 ? Step 1 close-out

| Time (approx.) | Revision / command | Mode | Result |
|---|---|---|---|
| 22:10 | `fastapi --help` | Local deployment CLI check | Not available: installed CLI entry point requires the `fastapi[standard]` extra. No deployment was attempted. The user-authorized deployment step remains pending. |
| 22:10 onward | Local development work | Local only | No further remote database writes were performed after the migration verification above. |

The remote migration is complete. The FastAPI Cloud deploy and remote State dashboard timing sample remain outstanding because the FastAPI CLI dependency is absent. The exact deploy command after installing the documented extra is `fastapi deploy`; do not treat the cloud app as updated until its live commit is confirmed.

## 2026-11-09 — B4/B5 close-out

| Time (approx., Africa/Lagos) | Revision / command | Mode | Result |
|---|---|---|---|
| 12:25 | Read `public.alembic_version`, public table count and schema catalog | Remote read | Ledger contained `e2b4c6d8f013`; 54 public tables. Prior Step 1 log records a catalog match at `e2b4c6d8f013`. |
| 12:29 | `pg_dump --format=custom --no-owner --no-privileges` via the Supabase session pooler to `_dev_db_snapshots/b5_pre_migration_20261109.dump` | Remote read / local backup | `pg_dump` did not exit within 120 seconds. The resulting 928,317-byte archive passed `pg_restore --list` and a full archive decompression to `NUL`; SHA-256 `EF2AAD5DA59CE865CF384DFF487B09C88357420B85C76BCBF7E258121F3ECAD4`. A disposable-cluster restore of this specific snapshot was not performed. |
| 12:34 | `PYTHONPATH=<Church_server>; alembic upgrade head` | **REMOTE WRITE**, Supabase session pooler | Applied `e2b4c6d8f013 -> a4d92c16e7b3 -> b5e6f8a1c234 -> b5f7a9c2d341`. Alembic reported transactional DDL and exit code 0. |
| 12:35 | Read-only post-migration catalog and row-count checks | Remote read | Ledger is `b5f7a9c2d341`. `count_groups`, `submission_edit_revisions`, and `count_section_suggestions` exist; expected worker IDs and B5 count/service columns exist. Required indexes exist. All three new B5 tables contain zero rows. |
| 12:36 | `fastapi --help` | Local CLI check | Command exits because `fastapi[standard]` / Cloud CLI extras are not installed. No deployment or CLI authentication was attempted. |
| 12:37 | `uv tool install "fastapi[standard]"` | Local user tool install | Installed the CLI in an isolated uv tool environment; no project dependency files were changed. |
| 12:38 | `fastapi cloud whoami`, then device login | Cloud account auth | `whoami` reported no credentials. The device login endpoint returned HTTP 400 after opening the browser flow. No app deployment or smoke test occurred. |
| 12:39 | Read-only count-backfill verification | Remote read | Pooler DNS resolution failed after migration, so the number of legacy note-prefixed rows updated by B5 could not be re-queried. |

No remote synthetic rows were seeded by the migration. No app deployment or synthetic-account smoke test was performed. The remote is migrated, but applications should not be considered deployed until both repository deployments and smoke tests complete.
