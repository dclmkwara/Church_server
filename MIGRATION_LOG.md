# Remote Development Database Migration Log

All timestamps are Africa/Lagos (UTC+01:00). Connection strings, usernames, passwords, and tokens are intentionally omitted.

## 2026-11-07 — Step 1 preflight

| Time (approx.) | Revision / command | Mode | Result |
|---|---|---|---|
| 21:42–21:44 | `pg_dump --format=custom --no-owner --no-privileges --host <Supabase session-pooler> --port 5432 --username <redacted> --dbname <redacted> --file output/private-backups/remote-dev-pre-migration-20261107.dump --no-password` | Remote read / local backup | Archive created (913,731 bytes); `pg_restore --list` returned exit 0 with 1,318 archive entries. The backup is local and excluded from Git. |
| 21:45 | Direct database endpoint DNS/TCP reachability check, port 5432 | Remote network check | Direct hostname returned no A record; one AAAA record was returned, but its TCP connection was unreachable from this host. |
| 21:46 | Configured session-pooler endpoint check, port 5432, via the `pg_dump` connection | Remote read | Completed as part of the valid archive capture. |
| 21:48 | `SELECT version_num FROM alembic_version ORDER BY version_num` | Remote read, application transaction pooler | Succeeded; ledger table exists and contains **zero rows**. |
| 21:49 | Read-only RBAC query joining `roles`, `role_scores`, `role_permissions`, and `permissions` for count-review/reminder permissions | Remote read, application transaction pooler | `counts:review` is granted to Group Pastor (score 3), Region Pastor (score 4), and State Overseer (score 5). `counts:remind` does not yet exist. |
| 21:49 | `SELECT to_regclass(...)` for `count_reminder_recipients`, `location_expected_population`, and `counts` | Remote read, application transaction pooler | Reminder and expected-population tables are absent; `counts` exists. |
| 21:49 | `SELECT split_part(note, ' |', 1), count(*) FROM counts WHERE note LIKE 'B2_DEMO:%' GROUP BY 1` | Remote read, application transaction pooler | No B2 demo markers found. |
| 21:53–21:57 | Read-only public catalog queries for tables, columns, indexes, constraints, policies, and Alembic ledger | Remote read, application transaction pooler | 52 tables, 792 columns, 493 indexes, 199 constraints, 102 policies; zero ledger rows. Tables, columns, indexes, and constraints match the saved catalog snapshot that recorded `c2e5a8f14b31`; only the ledger row differs. |
| 22:00 | Read-only export of `roles`, `permissions`, and `role_permissions` to `output/remote-rbac-before-step1.json` | Remote read, application transaction pooler | Export contains 20 roles, 81 permissions, and 919 grants. `init_rbac.py` was not run. |

The remote migration preflight is read-only except for the local backup artifact. No revision has been stamped or upgraded yet. Local proof of the proposed `c2e5a8f14b31 → d4a9c1e7f235 → e2b4c6d8f013` chain succeeded on a restored disposable database after excluding the Supabase-only `supabase_vault` extension/schema data, which this local PostgreSQL installation does not provide. The proof included upgrade, one-step downgrade, and re-upgrade. The remote migration will use a session-pooler connection, not the transaction pooler.
