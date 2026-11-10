# B6 Fellowship Remote Migration Report

**Date:** 10 November 2026  
**Revision:** `c6d7e8f9a012`  
**Database:** Supabase development, session pooler

## Backup and preflight

A fresh custom-format archive was captured before the migration at `_dev_db_snapshots/pre_b6_admin_20261110.dump` (942,535 bytes; SHA-256 `379B0A5DA1AFE2D16EB768826CF59A75B2690C9CA4086DCE60B3E550EBDBC9E4`). `pg_restore --list` succeeded with 1,373 entries, and `pg_restore --file NUL` decompressed the entire archive successfully.

The remote ledger was `b5f7a9c2d341`. Before the write, all six fellowship activity tables were inspected. There were three valid-format UUID strings that did not reference a fellowship: one each in members, attendance, and offerings. No malformed UUID values were present. B6 removes those orphan development records because they cannot satisfy the new foreign keys; the verified backup is the recovery copy.

## Migration and verification

`alembic upgrade c6d7e8f9a012` completed successfully. The remote ledger is now `c6d7e8f9a012`.

- All six activity `fellowship_id` columns are UUID.
- All six named foreign keys to `fellowships.fellowship_id` exist.
- Fellowship attendance contains the six non-null, zero-default categories: adult male/female, youth male/female, boys, and girls.
- The six activity tables now contain zero rows; the three orphan development rows were removed, and the remaining three activity tables were empty before migration.

Every command and the remote write are recorded in [MIGRATION_LOG.md](MIGRATION_LOG.md). No production database was changed.
