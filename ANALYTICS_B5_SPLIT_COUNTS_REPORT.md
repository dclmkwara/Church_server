# B5 Split Counts and Edit Window: Close-out Report

**Date:** 9 November 2026
**Status:** B5 implementation and local verification complete; repository checkpoints committed and the remote development database is migrated to B5 head. App deployment is pending because the FastAPI Cloud CLI is not installed in the current environment. B6 was not started.

## Counter design restored

The Field Utility counter matches the supplied original screen: the “Population Counter” title and subtitle, large total card with Edit Numbers and Reset, six demographic counters in the original order and styling, the unchanged Tithe & Offering card, and the blue “Save Count” button. The unchecked split-count state adds no visible controls to that layout.

The only counter addition is the “I'm counting only part of the congregation” checkbox between the demographic counters and offering card. When checked, it reveals a section name input with history suggestions (or A, B, C when no history exists). Duplicate labels in one occurrence are refused with a clear message. Service identity remains `main`; the picker is hidden unless that location has used multiple services for the same program and date. The server remains authoritative for group mode and duplicate labels.

Each saved part carries all six category values and the total. Group totals and category totals are calculated from the retained part rows when read; no merged replacement count is stored. Location users can close a group after a part has been saved. The UI shows the running total, labels already reported, and a one-tap reminder of labels seen in recent history. Closing means “ready for approval”; it does not approve the count.

### Counter screenshots

- [Unchecked counter](../utility_app/output/playwright/b5-counter-unchecked.png)
- [Split checkbox checked](../utility_app/output/playwright/b5-counter-checked.png)
- [Utility split entry](../utility_app/output/playwright/b5-utility-split-entry.png)
- [Utility split complete](../utility_app/output/playwright/b5-utility-split-complete.png)
- [Small-church flow](../utility_app/output/playwright/b5-small-church-count.png)

The unchecked screenshot was compared visually with the user-provided original image. The restored branded layout, spacing, cards, order, colors and button labels match; the checkbox is the only new row in that state.

## Split-count behavior and approval

- A `CountGroup` identifies one location, program, occurrence date, event when applicable, and service identity. `main` is the normal Sunday service; separately identified services remain separate groups.
- The first submission chooses `single` or `section` mode. Subsequent parts with a different mode are rejected. One single count per occurrence is allowed. Duplicate section labels are refused. Client IDs make retries idempotent.
- Parts remain individual rows. Review shows the category breakdown and approves the group’s pending rows in one action. A conflict is not summed. No daily total is invented across multiple services.
- Section suggestions come from previous split counts. No zone configuration or mandatory reason is required to close. Missing-history labels produce a soft hint.
- Any usher at the location, the location admin, or the location pastor can close the count. Closing records who closed it.
- Open groups past the reporting deadline are lazily auto-closed on the next relevant group/review/notification request. They display “auto-closed, not confirmed” and notify the Location Pastor. There is no scheduled worker yet; therefore a group can remain open past the deadline until another qualifying request runs. No rows are merged or rewritten.

## Edit window

The server enforces receipt time, authorization, revision number and replay behavior. Edits are in place; each accepted edit appends a `SubmissionEditRevision` row. A row lock and `base_revision` prevent two concurrent edits from consuming the same revision. Replaying the same `edit_id` returns the existing result instead of making a second revision.

| Submission type | Current server rule | Utility edit support |
|---|---|---|
| Population counts | Original submitter only; 24 hours from server receipt; at most 3 edits. Approval locks the report. A Return for correction reopens it for 24 hours and permits one additional edit. | Count edit form shows remaining edits/time and locked state. Online edits use the edit API; queued offline edits are submitted on sync and refused by the server if the window has expired. |
| Offerings | Same 24-hour and 3-edit rules; approval locks; return grants the extra edit/window. | Editable submission queue uses the same server revision workflow. |
| Worker attendance | Original submitter, 24 hours and 3 edits; no approval lock or return-for-correction extension is configured for this submission type. | Editable-submission listing/form and sync route are present. |
| Fellowship records | Original submitter, 24 hours and 3 edits; no approval lock or return-for-correction extension is configured for this submission type. | Editable-submission listing/form and sync route are present. |

Expired offline edits return a clear “24-hour edit window has closed” message rather than silently changing the record. The user can discard a permanently refused queue item. Current automated coverage includes replay/idempotency, stale revision/concurrent edit rejection, 24-hour expiry, edit limits, return-for-correction and server-side lock behavior. A live offline sync exercised an edit queued while offline and later refused after expiry. The report does not claim a separate live offline test for each of the four submission types.

## Duplicate offering check

The backend does not enforce one offering per service/fund: two distinct usher submissions can both be stored and included in totals. The Utility now checks for an existing offering for the same location, date, program and fund before saving a second one, and asks “An offering was already recorded for this service. Save another one?” It is a warning, not a hard block. The API remains race-prone if two ushers confirm simultaneously; the current database uniqueness rule is client-ID based, not service/fund based. The live API check confirmed the existing-record preflight response. The browser’s native confirmation dialog was not separately automated in the live run.

## Verification

- Church_server full suite: **291 passed**, one third-party deprecation warning.
- Field Utility full suite: **34 passed**, one third-party deprecation warning.
- Live local API/database flow (recorded run): two ushers submitted separate parts; a location admin closed the group; the Group Pastor saw the breakdown and approved; the dashboard displayed the summed total. The same run covered category summation, a normal six-category single count, duplicate-label refusal, single-count conflict, mixed-mode refusal, idempotent retry, edit revision/replay and expiry, and auto-close notification. It generated marker `B5_DEMO:E2E:ae630bf5` in the local test run.
- The API script `scripts/e2e_b5_split_counts.py` is repeatable against an explicitly supplied **local** sync database URL. A repeat in this close-out was stopped before requests because that variable was not set; the script correctly refused to adjust an unspecified database. The previous integrated run and browser captures are the evidence for the completed live flow.
- Browser screenshots show the original counter and split-count flow: [counter states](../utility_app/output/playwright/b5-counter-unchecked.png), [split entry](../utility_app/output/playwright/b5-utility-split-entry.png), [split complete](../utility_app/output/playwright/b5-utility-split-complete.png). These were captured from the running Utility. The scripted full API workflow is in [e2e_b5_split_counts.py](scripts/e2e_b5_split_counts.py).
- Local syntax checks for Utility JavaScript (`node --check` on `app.js`, `db.js`, and `sync.js`) passed in the B5 verification run.

## Schema and migration state

| Revision | Change |
|---|---|
| `b5e6f8a1c234` | Adds count groups, mode/section/group linkage and append-only submission edit revisions. |
| `b5f7a9c2d341` | Adds service identity and close/auto-close metadata, removes mandatory configured zones and adds optional location label suggestions. |

`alembic history` initially failed when invoked without `PYTHONPATH`; with the project root on `PYTHONPATH`, the chain resolves and `b5f7a9c2d341` is the single head. The remote development ledger was read-only checked: it contains `e2b4c6d8f013`; the remote has 54 public tables. No remote migration, stamp, or schema write was performed.

A custom-format snapshot was produced at `_dev_db_snapshots/b5_pre_migration_20261109.dump` (928,317 bytes; SHA-256 `EF2AAD5DA59CE865CF384DFF487B09C88357420B85C76BCBF7E258121F3ECAD4`). `pg_restore --list` and a full archive read to `NUL` both succeeded. The `pg_dump` client did not exit within 120 seconds through the pooler, although the resulting archive parsed and decompressed successfully. Treat this as a usable snapshot artifact, but retain that timeout caveat. The first attempt to delete/replace a zero-byte temporary dump was rejected by the command safety review; the subsequent run overwrote it successfully.

The remote migration was applied after confirming the ledger at `e2b4c6d8f013`, reviewing the prior catalog reconciliation at that revision, and creating the local snapshot above. `alembic upgrade head` applied B4 `a4d92c16e7b3`, then B5 `b5e6f8a1c234` and `b5f7a9c2d341`. A read-only post-check confirmed the final ledger, all three new tables, the new count/service/roster columns and indexes. All three new tables are empty. No synthetic count or estimate rows were seeded remotely. The B5 migration includes a legacy note-prefix backfill for count mode/section label; a follow-up row count could not be retrieved because the pooler hostname stopped resolving after migration.

## Deployment status and remaining items

No app was deployed. I installed the CLI in an isolated user tool environment without changing project dependencies. `fastapi cloud whoami` reported no credentials. The browser device-login flow returned HTTP 400 from the FastAPI Cloud login endpoint, so deployment could not proceed. Once login succeeds, the current official command is `uv run fastapi deploy` from each repository root; first-time authentication opens a browser. Neither repository was deployed, so no synthetic-account smoke test was run. [FastAPI Cloud deployment instructions](https://fastapi.tiangolo.com/deployment/fastapicloud/).

Before deployment, the remaining operational work is:

1. Install or activate the approved FastAPI Cloud CLI and authenticate; deploy both repositories and smoke-test with a synthetic account.
2. Restore the new snapshot into a disposable cluster for an additional full database-restore proof. The archive passed listing and decompression checks; it was not restored in this run.
3. Add a scheduled worker for exact-time auto-close if the church requires it; current implementation is request-triggered.

B6 and later slices were not started. No menu changes were made.
