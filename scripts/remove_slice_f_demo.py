"""Remove Slice F synthetic rows from the disposable local validation clone.

The script never prints the database URL and refuses non-loopback hosts or any
database other than ``dclm_slice_f``. Run once in preview mode, then with
``--apply``. Repeated apply runs are safe.
"""
from __future__ import annotations

import argparse
import os
from urllib.parse import urlparse

import psycopg2

MARKER = "F_TEST:slice-f-v1"
EXPECTED_DATABASE = "dclm_slice_f"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="delete matching synthetic records")
    args = parser.parse_args()

    database_url = os.environ.get("SYNC_DATABASE_URL", "")
    parsed = urlparse(database_url)
    database_name = parsed.path.lstrip("/").split("?", 1)[0]
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or database_name != EXPECTED_DATABASE:
        raise SystemExit("Refusing: SYNC_DATABASE_URL must target loopback database dclm_slice_f.")

    with psycopg2.connect(database_url) as connection, connection.cursor() as cursor:
        specs = {
            "counts": ("note",),
            "offerings": ("note",),
            "worker_attendance_submissions": ("note",),
            "worker_attendance": ("note",),
            "records": ("note",),
            "fellowship_attendance": ("note", "topic"),
            "fellowship_offerings": ("note",),
        }
        matches: dict[str, list[tuple[str, ...]]] = {}
        client_ids: set[str] = set()
        for table, columns in specs.items():
            clauses = " OR ".join(f"COALESCE({column}, '') = %s" for column in columns)
            cursor.execute(f"SELECT id::text, client_id::text FROM {table} WHERE {clauses}", (MARKER,) * len(columns))
            rows = cursor.fetchall()
            matches[table] = rows
            client_ids.update(client_id for _, client_id in rows if client_id)

        count_group_ids: set[str] = set()
        if matches["counts"]:
            cursor.execute(
                "SELECT DISTINCT count_group_id::text FROM counts WHERE note = %s AND count_group_id IS NOT NULL",
                (MARKER,),
            )
            count_group_ids = {row[0] for row in cursor.fetchall()}

        print("Slice F marker cleanup preview")
        for table, rows in matches.items():
            print(f"{table}: {len(rows)}")
        print(f"count_groups eligible for empty-group cleanup: {len(count_group_ids)}")
        if not args.apply:
            print("Preview only. Re-run with --apply to delete these marked rows.")
            return 0

        if client_ids:
            cursor.execute("DELETE FROM idempotency_keys WHERE client_id = ANY(%s::uuid[])", (list(client_ids),))
        # Worker rows belong to an aggregate submission; remove children first.
        submission_ids = [row[0] for row in matches["worker_attendance_submissions"]]
        if submission_ids:
            cursor.execute("DELETE FROM worker_attendance WHERE submission_id = ANY(%s::uuid[])", (submission_ids,))
        for table in (
            "counts", "offerings", "worker_attendance", "worker_attendance_submissions",
            "records", "fellowship_attendance", "fellowship_offerings",
        ):
            ids = [row[0] for row in matches[table]]
            if ids:
                cursor.execute(f"DELETE FROM {table} WHERE id = ANY(%s::uuid[])", (ids,))
        if count_group_ids:
            cursor.execute(
                "DELETE FROM count_groups WHERE id = ANY(%s::uuid[]) "
                "AND NOT EXISTS (SELECT 1 FROM counts WHERE counts.count_group_id = count_groups.id)",
                (list(count_group_ids),),
            )
        cursor.execute(
            "DELETE FROM audit_logs WHERE COALESCE(changes::text, '') LIKE %s",
            (f"%{MARKER}%",),
        )
        connection.commit()

        remaining = 0
        for table, columns in specs.items():
            clauses = " OR ".join(f"COALESCE({column}, '') = %s" for column in columns)
            cursor.execute(f"SELECT count(*) FROM {table} WHERE {clauses}", (MARKER,) * len(columns))
            remaining += cursor.fetchone()[0]
        print(f"Marked source rows remaining: {remaining}")
        return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
