# Full Analytics Plan — Step 0 Report

**Date:** 7 November 2026  
**Starting commit:** `f2566450acf9582a447528364d59fd9011490ab1`  
**Scope:** housekeeping only. No remote database access or writes.

## Completed

- Ran the full repository suite: **253 passed**, one third-party `asyncio.iscoroutinefunction` deprecation warning.
- Database connectivity failures now log only the exception type. The global 500 handler no longer logs exception text or tracebacks that can include connection details. `scripts/db_connect_check.py` also redacts driver exception details.
- Added tests proving database failure logs and the connectivity script output do not expose the test password or URL.
- Added a first-party admin frontend source guard against common mojibake markers. It passes.
- Changed the State-only expected-attendance CSV download to query the State's current location list and estimates. The CSV contains full hierarchy path in the importable `location_code` column, display code, location name, current estimate, and blank `effective_from` and `note` fields. A test confirms the output remains accepted by the CSV parser.
- Generated [expected-sunday-attendance-template.csv](output/expected-sunday-attendance-template.csv) from the disposable local restored clone (`127.0.0.1:55432`, database `church_alembic_restore_proof`): **40 locations**, full paths and names, no current estimates. No database rows were changed.

## Secret scan

Scanned tracked text files plus `output/` and `reports/` for database URLs with user/password fields, JWT-shaped strings, and private-key headers. The `reports/` directory does not exist. **No candidate files were found under `output/` or `reports/`.** Tracked-file candidates were limited to placeholder URLs in documentation/config examples and dummy `test:test@localhost` fixtures; no active credential was identified. Filenames only:

- `.env.example`
- `docs/ARCHITECTURE.md`
- `docs/DEPLOYMENT.md`
- `docs/QUICK_START.md`
- `docs/SETUP.md`
- `docs/TECH_STACK.md`
- `docs/TECH_STACK.md.resolved`
- `scripts/db_connect_check.py`
- `tests/test_announcement_scope.py`
- `tests/test_auth_cache.py`
- `tests/test_auth_scope_freshness.py`
- `tests/test_dependency_compat.py`
- `tests/test_global_admin_dashboard.py`
- `tests/test_hierarchy_scope.py`
- `tests/test_notification_service.py`
- `tests/test_phase6_communications.py`
- `tests/test_rbac_permissions.py`
- `tests/test_scope_helpers.py`
- `tests/test_seed_admin_bootstrap.py`
- `tests/test_sync_idempotency.py`
- `tests/test_sync_safety.py`

## Changed files

- `app/db/session.py`
- `app/main.py`
- `app/frontend/dclm_admin/routes/expected_population.py`
- `scripts/db_connect_check.py`
- `tests/test_expected_population_csv.py`
- `tests/test_safe_database_errors.py`
- `tests/test_frontend_mojibake_guard.py`
- `ANALYTICS_FULL_PLAN_STEP0_REPORT.md`

Unrelated existing workspace artifacts were left untouched. The CSV snapshot is a generated local artifact and is not part of the source commit; the application download is dynamic.

## Verification

```text
python -m pytest -q
253 passed, 1 warning
```

**Commit:** reported in the handoff; the report avoids a self-referential hash.  
**Port/database:** local clone on port `55432`; no remote database used.
