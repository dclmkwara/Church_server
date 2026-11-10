# Slice F: Consistency, Field Utility and Remote Readiness

**Status:** Partial evidence gathered; Slice F is not complete. No product features were added. No remote database write, push or deployment was performed. The local test records created during the browser attempt were removed.

## F1. Reconciliation matrix

Added [test_slice_f_reconciliation_reference.py](tests/test_slice_f_reconciliation_reference.py), a small independent reference oracle for:

- Current approved rows versus pending, rejected, superseded and missing rows.
- Reported zero versus no row.
- Six-category addition for split count parts while keeping service occurrences separate.
- Combined group report replacement of covered location rows at an ancestor scope.
- Pooled ratio versus an average of location percentages.

The test does not call application analytics services. It passed **4 tests** and is collected by the normal Church_server pytest run.

This is not the full requested page-to-page reconciliation matrix. I did not establish independent SQL totals and compare them against every named page/export for all four scopes. The current fixture also does not cover offerings, worker attendance, fellowship, newcomer/convert, retreat/crusade day totals, or all review/edit states through their live pages. I found no verified page disagreement to fix; that is an evidence gap, not proof of parity. No page-specific patch was made.

| Metric | Independent oracle added | Compared across every requested page and scope |
|---|---:|---:|
| Six count categories and total | Yes, fixture cases | No |
| Offerings | No | No |
| Worker attendance | No | No |
| Fellowship counts | No | No |
| Newcomers and converts | No | No |
| Retreat/crusade/leaders/workers event totals | Only occurrence-grain rule | No |
| Exports and Pastor Report | No | No |

## F2. Field Utility to local database

The Utility and Church_server ran locally on ports **8013** and **8012**, against the disposable PostgreSQL clone `dclm_slice_f` on **55434**. A real Chrome session signed in, loaded the location context, completed setup, and reached the existing Population Counter. The initial apparent sign-in stall was a short observation window; the API later confirmed login and a longer browser run reached Home without page errors.

The browser attempt submitted one marked section count through the actual counter UI and the real Utility proxy/sync path. It arrived as a pending row with categories `(adult male 2, adult female 2, youth male 1, youth female 1, boys 1, girls 1)`, total `8`, and section `A`. The intended single-count attempt did not produce a confirmed API row. A second section was saved locally in the Utility queue rather than confirmed by the API. Therefore the split sum, repeated-label rejection, single-count path, admin visibility, offerings, worker attendance, fellowship, offline replay, edit limits, and approval lock were **not** demonstrated end to end.

Screenshots from the live browser attempt:

- [Utility Home after sign-in](output/playwright/slice-f-utility-home.png)
- [Counter, unchecked single-count control](output/playwright/slice-f-utility-single.png) — UI state only; the displayed zero means the attempted single count was not confirmed.
- [Counter, section A with six categories](output/playwright/slice-f-utility-split-a.png) — captured while Save was still pending; the marked database row was independently confirmed afterwards.
- [Counter, second section attempt](output/playwright/slice-f-utility-split-b.png) — displayed the on-device queue fallback; no successful second database row was confirmed.

Added [remove_slice_f_demo.py](scripts/remove_slice_f_demo.py). It only accepts a loopback URL to database `dclm_slice_f`, previews counts by table, and requires `--apply`. The test row and its empty count group were removed. A repeated preview reported zero matching rows. This cleanup can be rerun safely.

The Church_server and Utility full test suites passed after the changes: **353 passed, 1 skipped** for Church_server and **40 passed** for Utility. These automated suites do not substitute for the incomplete live Utility scenarios listed above.

## F3. Timing and SQL traces

The five cold-process samples required by Slice F were not completed. The most recent available evidence remains the single State dashboard trace in Slice E:

| Measure | Existing single sample | Slice F five-sample set |
|---|---:|---:|
| State dashboard server render | 1,693 ms | Not run |
| SQL statements | 7 | Not collected per page |
| State and Location Dashboard, domain pages, Pastor Report medians | — | Not run |

The Slice E sign-in diagnostic measured API login at about **2,482 ms**, including approximately **1,166 ms** attributed to user lookup and **1,240 ms** to password verification. The frontend recorded about **2,878 ms** total. This was one diagnostic, not a repeated sample.

The restored clone has unique indexes on `users.email` (`uq_user_email` and `ix_users_email`). An isolated `EXPLAIN (ANALYZE, BUFFERS)` on its 73-user table chose a sequential scan and executed in **0.297 ms**; PostgreSQL's choice is expected for a small table. The index is present, so missing index is not supported by evidence. The earlier 1.166-second application interval is not accounted for by that SQL execution. Cold connection setup, other authentication work and timing boundaries were not separated, so I did not claim a cause or change sign-in code.

## F4. Remote readiness

The disposable-clone migration proof completed from the B5 snapshot at `b5f7a9c2d341` through:

1. `c6d7e8f9a012` — B6 fellowship UUID conversion, foreign keys and categories.
2. `d71a9c4e2b60` — admin role policy data revision.
3. `d7a4c1e2f809` — scoped pastor audit-log permission.

The final ledger was `d7a4c1e2f809`; the six fellowship ID columns were UUID and the RBAC tables had 20 roles, 85 permissions and 977 grants. No downgrade was needed for the test path. The restored archive required excluding four Supabase Vault TOC entries that are not available in a local PostgreSQL restore. The database was a disposable local clone; no remote write was performed.

[DEPLOY_MIGRATION_RUNBOOK.md](DEPLOY_MIGRATION_RUNBOOK.md) now includes the B5-to-head revision sequence, backup/listing/decompression commands, ledger gates, verification SQL, RLS explanation, rollback note, and release order. The recorded remote state in `MIGRATION_LOG.md` is already `d7a4c1e2f809`; verify the current ledger before acting. If it remains at head, skip migration. If it is at B5, migrate and verify before publishing either app.

No database URL, password, access token or secret was included in this report. The remote was not contacted during Slice F.

## F5. Confirmations

### Admin audit trail

The scoped read path exists at `/api/v1/system/audit-logs` in [system.py](app/api/v1/routes/system.py), and the pastor-facing page is `/system/audit-logs` in [system.py](app/frontend/dclm_admin/routes/system.py). It requires `system:read_audit_logs`, permits levels 2–5, and filters records by the caller's effective hierarchy scope. The permission was added to the four pastor roles by `d7a4c1e2f809`.

This supports pastors seeing recorded actions in their scope; it does not establish that every mutation in the application writes a complete audit entry. Slice F did not conduct a per-action audit completeness audit or a browser verification of every pastor persona.

### A4 browser print

The Pastor Report has server-generated A4 PDF layout evidence from ReportLab. It has **not** been verified through the browser print path in this slice. A browser print preview and the phone print/save-to-PDF check remain open.

### Demo and seed data observed in the disposable clone

- **B2 Sunday sample:** 241 marked count rows remain in the clone. The script's remove path is `uv run python scripts/seed_b2_sunday_analytics.py --remove --dev-project-ref <development-project-ref>`, but its current guard requires the designated Supabase development pooler. Do not point it at a different database or run it until its target and backup are confirmed.
- **B3 event fixture:** zero marked B3 counts, records and campaigns were found in this clone. If seeded later, remove with `uv run python scripts/seed_b3_events.py --remove` on an allowed local clone.
- **Synthetic hierarchy:** 12 group names beginning `DEMO`, 36 location names beginning `DEMO`, and 60 demo-address users were present in the clone. `scripts/seed_demo_hierarchy.py` has no `--remove` option. There is currently no safe one-command removal for this hierarchy; do not delete these rows by broad name matching because there are linked workers, users and audit data.
- **Slice F:** zero marked rows remain after running the new cleanup command.

The temporary clusters on ports 55434 and 55432 were stopped. The operating environment rejected recursive deletion of their temporary data directories, so they remain at:

- `C:\Users\Meshell\AppData\Local\Temp\dclm-slice-f-clone-20261110`
- `C:\Users\Meshell\AppData\Local\Temp\dclm-analytics-validation-20261110`

The live server process on port 8000 was not touched. The Slice F local app processes on ports 8012 and 8013 were stopped.

## Open before Slice F can be called complete

- Complete independent SQL reconciliation against the named pages and exports at State, Region, Group and Location; fix any measured disagreements at their shared source.
- Build and run the full live Utility-to-database scenario, including the failed single-count and second section paths, offerings, worker attendance, fellowship, replay idempotency, edits, approval lock and Admin views.
- Add a repeatable browser E2E test script for those scenarios; the cleanup command alone is not an E2E test.
- Collect five cold-process State and Location timings and SQL counts for the dashboard, every domain page and Pastor Report.
- Verify browser A4 print and phone print behavior.
- Provide a safe removal path for the synthetic hierarchy or explicitly retain it as development data.

## Checkpoint

This report and its reference tests are a partial Slice F checkpoint. No push or deployment was performed. The commit hash is recorded in the handoff after this checkpoint is committed.
