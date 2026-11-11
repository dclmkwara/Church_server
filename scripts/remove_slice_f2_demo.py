"""Remove the marked Slice F2 Utility reproduction rows from local clone only."""
from __future__ import annotations

import argparse
import os
from urllib.parse import urlparse

import psycopg2

MARKER = "F2_TEST:f2-utility-v1"
MARKER_PREFIX = "F2_TEST:"
EXPECTED_DATABASE = "dclm_slice_f"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="delete matching test rows")
    args = parser.parse_args()
    database_url = os.environ.get("SYNC_DATABASE_URL", "")
    parsed = urlparse(database_url)
    database_name = parsed.path.lstrip("/").split("?", 1)[0]
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or database_name != EXPECTED_DATABASE:
        raise SystemExit("Refusing: SYNC_DATABASE_URL must target loopback database dclm_slice_f.")

    with psycopg2.connect(database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT id::text, client_id::text, count_group_id::text FROM counts WHERE note LIKE %s", (MARKER_PREFIX + "%",))
        rows = cursor.fetchall()
        specs = {
            "offerings": ("note",), "worker_attendance_submissions": ("note",),
            "worker_attendance": ("note",), "records": ("note",),
            "fellowship_attendance": ("note", "topic"),
            "fellowship_offerings": ("note",),
        }
        matches: dict[str, list[tuple[str, str | None]]] = {"counts": [(row[0], row[1]) for row in rows]}
        for table, columns in specs.items():
            clauses = " OR ".join(f"COALESCE({column}, '') LIKE %s" for column in columns)
            cursor.execute(f"SELECT id::text, client_id::text FROM {table} WHERE {clauses}", (MARKER_PREFIX + "%",) * len(columns))
            matches[table] = cursor.fetchall()
        cursor.execute(
            "SELECT fellowship_id::text, NULL::text FROM fellowships "
            "WHERE fellowship_name LIKE %s",
            (MARKER_PREFIX + "%",),
        )
        marked_fellowships = cursor.fetchall()
        print("Slice F2 marked-row cleanup preview")
        for table, table_rows in matches.items():
            print(f"{table}: {len(table_rows)}")
        print(f"fellowships: {len(marked_fellowships)}")
        if not args.apply:
            print("Preview only; add --apply to remove these marked test rows.")
            return 0
        client_ids = sorted({row[1] for table_rows in matches.values() for row in table_rows if row[1]})
        group_ids = sorted({row[2] for row in rows if row[2]})
        if client_ids:
            cursor.execute("DELETE FROM idempotency_keys WHERE client_id = ANY(%s::uuid[])", (client_ids,))
        submission_ids = [row[0] for row in matches["worker_attendance_submissions"]]
        if submission_ids:
            cursor.execute("DELETE FROM worker_attendance WHERE submission_id = ANY(%s::uuid[])", (submission_ids,))
        for table in matches:
            ids = [row[0] for row in matches[table]]
            if ids:
                cursor.execute(f"DELETE FROM {table} WHERE id = ANY(%s::uuid[])", (ids,))
        if marked_fellowships:
            fellowship_ids = [row[0] for row in marked_fellowships]
            cursor.execute(
                "DELETE FROM fellowships WHERE fellowship_id = ANY(%s::uuid[]) "
                "AND NOT EXISTS (SELECT 1 FROM fellowship_attendance WHERE fellowship_attendance.fellowship_id = fellowships.fellowship_id) "
                "AND NOT EXISTS (SELECT 1 FROM fellowship_offerings WHERE fellowship_offerings.fellowship_id = fellowships.fellowship_id) "
                "AND NOT EXISTS (SELECT 1 FROM fellowship_members WHERE fellowship_members.fellowship_id = fellowships.fellowship_id)",
                (fellowship_ids,),
            )
        if group_ids:
            cursor.execute(
                "DELETE FROM count_groups WHERE id = ANY(%s::uuid[]) "
                "AND NOT EXISTS (SELECT 1 FROM counts WHERE counts.count_group_id = count_groups.id)",
                (group_ids,),
            )
        cursor.execute("DELETE FROM audit_logs WHERE COALESCE(changes::text, '') LIKE %s", ("%F2_TEST:%",))
        connection.commit()
        cursor.execute("SELECT count(*) FROM counts WHERE note LIKE %s", (MARKER_PREFIX + "%",))
        remaining = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM fellowships WHERE fellowship_name LIKE %s", (MARKER_PREFIX + "%",))
        remaining_fellowships = cursor.fetchone()[0]
        print(f"marked count rows remaining: {remaining}")
        print(f"marked fellowships remaining: {remaining_fellowships}")
        return 0 if remaining == 0 and remaining_fellowships == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
