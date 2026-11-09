# B6 Fellowship Checkpoint

**Date:** 9 November 2026

**Status:** Local implementation and verification complete. The remote migration is pending because a fresh remote backup could not be captured. No remote schema or data was changed.

## What changed

- Added six explicit attendance categories to Fellowship attendance: Adult Male, Adult Female, Youth Male, Youth Female, Boys, and Girls. The server calculates the row total from the six values when a current Utility submission supplies them.
- Kept the old `men`, `women`, `youths`, and `children` fields so historical and older-client submissions retain their existing meaning. Legacy attendance remains a legacy total; it is not split into guessed categories. The Utility edit screen shows the old fields for legacy rows and the six fields for new rows.
- Added a one-query aggregate to the scoped Fellowship list API. It includes active member count, most recent attendance total, latest offering amount, and open prayer count. The Admin list and its summary now share those list rows for the request. Previously, the list service fetched members, attendance, offerings, prayers, and location details per fellowship. The resulting data path is one paginated API read and one aggregate SQL statement per returned page, rather than several sequential API reads for each fellowship. A single load has not yet been measured in a live browser trace.
- Kept the Fellowship detail page location-scoped and used the existing shared responsive table/card components to show the six categories in attendance history.

## Data check and migration

The remote pooler was unavailable for a fresh B6 backup. I restored the existing public snapshot `_dev_db_snapshots/b5_pre_migration_20261109.dump` (928,317 bytes; captured before the B5 migration) to a disposable local PostgreSQL cluster on port **55434**. I excluded the Supabase-only `supabase_vault` objects and installed the local `ltree`/`pgcrypto` extensions before restoring the public schema. This archive is useful for local inspection but is **not a current backup for a remote B6 migration**.

The snapshot showed:

| Activity table | `fellowship_id` type | FK to `fellowships` | Rows before migration | Orphan rows |
|---|---|---:|---:|---:|
| `fellowship_members` | varchar | No | 1 | 1 |
| `fellowship_attendance` | varchar | No | 1 | 1 |
| `fellowship_offerings` | varchar | No | 1 | 1 |
| `fellowship_testimony` | varchar | No | 0 | 0 |
| `fellowship_prayer_request` | varchar | No | 0 | 0 |
| `fellowship_attendance_summaries` | varchar | No | 0 | 0 |

All three populated rows used the same well-formed UUID text, but the snapshot had no `fellowships` rows. No malformed UUIDs were found. Because those development rows had no parent, a valid FK could not be added while retaining them. Migration `c6d7e8f9a012` deletes rows whose fellowship does not exist, converts all six columns to UUID, and adds six FK constraints. It also adds the six non-null attendance category columns with a default of zero. The prior database snapshot is the recovery source for removed orphan development rows; the migration downgrade does not recreate those rows.

The Alembic chain was applied to the disposable restored database from ledger `e2b4c6d8f013` through `a4d92c16e7b3`, `b5e6f8a1c234`, `b5f7a9c2d341`, and `c6d7e8f9a012`. All six ID columns were UUID and all six FK constraints were present afterward. A one-step downgrade and re-upgrade of the B6 revision also succeeded. No remote migration was attempted.

Fresh `pg_dump` attempts at 15:03 and 15:08 Lagos time produced zero-byte files while the configured pooler could not resolve/connect. Those files were rejected and are not backups. Details are recorded in [MIGRATION_LOG.md](MIGRATION_LOG.md).

## Verification

- Church_server full suite: **323 passed, 1 skipped**.
- Field Utility full suite: **36 passed**.
- The skip is the existing authenticated mobile-browser sweep; no persona session was configured.
- Added tests for six-category total calculation, legacy total compatibility, one aggregate list request without per-fellowship fetches, six Utility form inputs, and six-category sync payload forwarding.
- No deployed-browser screenshot was taken for this B6 change. No FastAPI Cloud login or deployment was attempted.

## Carry-over requested with B5 acceptance

- In the restored snapshot after replaying the B5 migration, there were **254 count rows**, **0** rows with a `Section:` note prefix, **0** backfilled section-mode rows, and **0** count groups. This is a local historical snapshot result; a current remote recount is still pending because the pooler is unavailable.
- A B5 Count Review screenshot showing a real section breakdown and “Return for correction” was not captured. The restored snapshot has no count groups, so this needs a marked local test fixture before capture.
- New required B4/B5 environment variables: **none**.

## Not done

- Applying `c6d7e8f9a012` to remote development. Take and verify a fresh snapshot first, then review the current orphan counts before running the migration.
- A live browser timing capture for the Fellowship list/detail pages.
- FastAPI Cloud deployment and smoke test. The user said they will perform cloud login and deployments.
- Subsequent Slice C and Slice D work.
