"""Seed or remove clearly marked B2 Sunday Worship analytics demo rows.

This utility is deliberately locked to the configured Supabase development
project. It writes only marked Count rows and one temporary opened_on value;
it never creates or deletes hierarchy, worker, or user records.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time as time_module
from zoneinfo import ZoneInfo

import psycopg2
from sqlalchemy.engine import make_url

from app.core.config import settings


LAGOS = ZoneInfo("Africa/Lagos")
SNAPSHOT_DIR = Path(r"C:\Users\Meshell\Desktop\FastHTML\_dev_db_snapshots")
MARKER_DEFAULT = "b2-sunday-demo-v1"
PG_DUMP = Path(r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe")
ROLE_SCORE = {"Location Worker": 1, "Location Usher": 1, "Location Pastor": 2, "Group Pastor": 3, "Region Pastor": 4, "State Overseer": 5}


def connect_args(url):
    return {
        "host": url.host,
        "port": url.port or 5432,
        "user": url.username,
        "password": url.password,
        "dbname": url.database or "postgres",
        "sslmode": "require",
        "connect_timeout": 20,
    }


def validate_development_target(url, project_ref: str) -> None:
    if not re.fullmatch(r"[a-z0-9]{20}", project_ref or ""):
        raise SystemExit("Pass the 20-character Supabase project reference with --dev-project-ref.")
    if "pooler.supabase.com" not in (url.host or ""):
        raise SystemExit("Refusing: database host does not look like the designated Supabase development pooler.")
    if project_ref not in (url.username or ""):
        raise SystemExit("Refusing: the supplied project reference does not match the configured database user.")
    if (url.database or "").lower() != "postgres":
        raise SystemExit("Refusing: the database name is not the expected development database.")


def make_snapshot(url, purpose: str) -> Path:
    if not PG_DUMP.exists():
        raise SystemExit(f"pg_dump is missing: {PG_DUMP}")
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = SNAPSHOT_DIR / f"church_server_{purpose}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.dump"
    env = os.environ.copy()
    env["PGPASSWORD"] = url.password or ""
    args = [
        str(PG_DUMP), "--format=custom", "--no-owner", "--no-acl",
        "--host", url.host or "", "--port", str(url.port or 5432),
        "--username", url.username or "", "--dbname", url.database or "postgres",
        "--file", str(snapshot),
    ]
    subprocess.run(args, env=env, check=True, timeout=180, capture_output=True, text=True)
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    print(f"Snapshot saved: {snapshot} ({snapshot.stat().st_size} bytes, sha256 {digest})")
    return snapshot


def manifest_path(marker: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", marker)
    return SNAPSHOT_DIR / f"{safe}_manifest.json"


def latest_sunday(today: date) -> date:
    return today - timedelta(days=(today.weekday() - 6) % 7)


def sunday_sequence(end: date) -> list[date]:
    newest = end - timedelta(days=(end.weekday() - 6) % 7)
    return [newest - timedelta(days=7 * offset) for offset in reversed(range(8))]


def fetch_hierarchy(cur, state_code: str):
    cur.execute("SELECT path::text FROM states WHERE state_code = %s", (state_code,))
    state_row = cur.fetchone()
    if not state_row:
        raise SystemExit(f"No state has code {state_code!r} in the configured dev database.")
    state_path = state_row[0]
    cur.execute("SELECT region_name, path::text FROM regions WHERE path <@ %s::ltree ORDER BY path", (state_path,))
    regions = cur.fetchall()
    cur.execute("SELECT group_name, path::text FROM dclm_groups WHERE path <@ %s::ltree ORDER BY path", (state_path,))
    groups = cur.fetchall()
    cur.execute(
        """SELECT location_id::text, location_name, path::text, church_type, opened_on, is_active
           FROM locations WHERE path <@ %s::ltree ORDER BY path""",
        (state_path,),
    )
    locations = cur.fetchall()
    return state_path, regions, groups, locations


def user_index(cur):
    cur.execute(
        """SELECT u.user_id::text, u.path::text, r.role_name
           FROM users u JOIN user_roles ur ON ur.user_id = u.user_id
           JOIN roles r ON r.id = ur.role_id
           WHERE u.is_active IS TRUE AND u.is_deleted IS FALSE AND u.approval_status = 'approved'
           ORDER BY u.path, r.role_name"""
    )
    rows = cur.fetchall()
    return rows


def choose_user(users, node_path: str, location_path: str) -> str:
    candidates = []
    for user_id, user_path, role_name in users:
        if user_path == location_path and role_name in {"Location Worker", "Location Usher", "Location Pastor"}:
            candidates.append((ROLE_SCORE.get(role_name, 0), user_id))
        elif user_path == node_path and role_name in {"Group Pastor", "Region Pastor", "State Overseer"}:
            candidates.append((ROLE_SCORE.get(role_name, 0), user_id))
    if candidates:
        return sorted(candidates, reverse=True)[0][1]
    # Prefer the highest available pastor in the actual state chain if the
    # synthetic hierarchy node has no dedicated user account.
    for preferred in ("State Overseer", "Region Pastor", "Group Pastor", "Location Pastor", "Location Usher", "Location Worker"):
        for user_id, user_path, role_name in users:
            if role_name == preferred and (location_path.startswith(user_path + ".") or location_path == user_path):
                return user_id
    if users:
        return users[0][0]
    raise SystemExit("No approved active user is available as a submitter in this development database.")


def nearest_path(location_path: str, level: str) -> str:
    segment_count = {"Local": 6, "Group": 5, "Region": 4, "State": 3}[level]
    return ".".join(location_path.split(".")[:segment_count])


def insert_count(cur, *, marker, row, program_domain_id, program_type_id, categories, status,
                 level, scope_path, submitter_id, created_at, auto_accepted=False,
                 approved_by_id=None, approved_at=None, supersedes_id=None,
                 rejection_reason=None, rejected_by_id=None, rejected_at=None, section=None):
    adult_male, adult_female, youth_male, youth_female, boys, girls = categories
    total = sum(categories)
    section_note = f"Section: {section} | " if section else ""
    note = f"B2_DEMO:{marker} | {section_note}Synthetic Sunday Worship sample for analytics testing."
    count_id = __import__("uuid").uuid4()
    client_id = __import__("uuid").uuid4()
    submitted_date = datetime.combine(row["occurrence"], time.min, LAGOS).astimezone(timezone.utc)
    cur.execute(
        """INSERT INTO counts (
            id, client_id, path, location_id, date, event_id, church_type,
            program_level, program_domain_id, program_type_id, program_scope_path,
            program_domain, program_type, adult_male, adult_female, youth_male,
            youth_female, boys, girls, total, status, note, source_role,
            submission_channel, entered_by_id, created_at, last_modify, is_deleted,
            operation, auto_accepted, approved_by_id, approved_at, supersedes_id,
            rejection_reason, rejected_by_id, rejected_at
        ) VALUES (
            %s, %s, %s::ltree, %s, %s, NULL, %s,
            %s, %s, %s, %s::ltree, 'Weekly Programs', 'Sunday Worship Service',
            %s, %s, %s, %s, %s, %s, %s, %s, %s, 'regular',
            'field_utility', %s, %s, %s, false, 'CREATE', %s, %s, %s, %s,
            %s, %s, %s
        )""",
        (
            str(count_id), str(client_id), row["path"], row["location_id"], submitted_date,
            row["church_type"], level, program_domain_id, program_type_id, scope_path,
            adult_male, adult_female, youth_male, youth_female, boys, girls, total,
            status, note, submitter_id, created_at, created_at, auto_accepted,
            approved_by_id, approved_at, str(supersedes_id) if supersedes_id else None,
            rejection_reason, rejected_by_id, rejected_at,
        ),
    )
    return str(count_id)


def seed(cur, args, url):
    marker = args.marker
    prefix = f"B2_DEMO:{marker}"
    cur.execute("SELECT count(*) FROM counts WHERE left(note, length(%s))=%s AND is_deleted IS FALSE", (prefix, prefix))
    if cur.fetchone()[0]:
        raise SystemExit(f"Marker {marker!r} already exists. Run --remove before reseeding.")
    state_path, regions, groups, raw_locations = fetch_hierarchy(cur, args.state_code)
    users = user_index(cur)
    locations = [
        {"location_id": loc_id, "name": name, "path": path, "church_type": church_type or "DLBC", "opened_on": opened_on, "active": active}
        for loc_id, name, path, church_type, opened_on, active in raw_locations if active
    ]
    if not locations:
        raise SystemExit("No active locations exist under the selected dev state.")
    cur.execute("SELECT id FROM program_domains WHERE slug='weekly_programs' AND is_deleted IS FALSE")
    domain_id = cur.fetchone()[0]
    cur.execute("SELECT id FROM program_types WHERE slug='sunday_worship_service' AND is_deleted IS FALSE")
    type_row = cur.fetchone()
    if not type_row:
        raise SystemExit("The Sunday Worship program type is missing from the canonical taxonomy.")
    type_id = type_row[0]

    weeks = sunday_sequence(date.fromisoformat(args.end_date) if args.end_date else latest_sunday(datetime.now(LAGOS).date()))
    by_path = {item["path"]: item for item in locations}
    groups_by_path = {path: name for name, path in groups}
    target_group_path = next((path for name, path in groups if name.lower() == args.demo_group.lower()), None)
    if not target_group_path or not any(_is_descendant(item["path"], target_group_path) for item in locations):
        raise SystemExit(f"Demo group {args.demo_group!r} has no active locations in state {args.state_code}.")
    group_locations = [item for item in locations if _is_descendant(item["path"], target_group_path)]
    if len(weeks) != 8:
        raise SystemExit("Exactly eight Sunday dates are required.")

    mid_location = next((item for item in locations if item["name"].startswith("DEMO ") and item["opened_on"] is None), None)
    if mid_location is None:
        raise SystemExit("Could not find a synthetic DEMO location with no existing opened_on date to use for the mid-period case.")
    mid_open_date = weeks[3]
    manifest = {
        "marker": marker, "snapshot": "created before seed", "state_path": state_path,
        "opened_on_changes": [{"location_id": mid_location["location_id"], "original": None, "seeded": mid_open_date.isoformat()}],
    }
    cur.execute("UPDATE locations SET opened_on=%s, last_modify=now() WHERE location_id=%s", (mid_open_date, mid_location["location_id"]))
    mid_location["opened_on"] = mid_open_date

    # These dates intentionally showcase a group-combined report and a
    # state-level auto-accepted report without requiring ProgramEvent rows.
    group_week = weeks[-2]
    state_week = weeks[-3]
    missing_location = next((item for item in locations if item["path"] != mid_location["path"]), locations[-1])
    zero_location = next((item for item in group_locations if item["path"].endswith(".D01")), group_locations[0])
    correction_location = next((item for item in group_locations if item["path"].endswith(".003")), group_locations[0])
    section_location = correction_location
    section_week = weeks[-5]
    zero_week = weeks[-6]
    correction_week = weeks[-4]
    pending_location = next((item for item in group_locations if item["location_id"] != correction_location["location_id"]), group_locations[0])
    pending_week = weeks[-5]
    created = 0
    approver_by_scope = {}
    for user_id, user_path, role_name in users:
        if role_name in {"Group Pastor", "Region Pastor", "State Overseer"}:
            approver_by_scope[(user_path, role_name)] = user_id

    def base_values(location, occurrence, index):
        if occurrence < (location["opened_on"] or date.min):
            return None
        if location["location_id"] == zero_location["location_id"] and occurrence == zero_week:
            return (0, 0, 0, 0, 0, 0)
        return (38 + index % 19, 44 + index % 23, 13 + index % 9, 15 + index % 11, 8 + index % 7, 7 + index % 5)

    now = datetime.now(timezone.utc)
    for week_index, occurrence in enumerate(weeks):
        if occurrence == group_week:
            categories = [0] * 6
            for index, location in enumerate(group_locations):
                cats = base_values(location, occurrence, index)
                if cats:
                    categories = [left + right for left, right in zip(categories, cats)]
            venue = group_locations[0]
            submitter = choose_user(users, target_group_path, venue["path"])
            region_path = ".".join(target_group_path.split(".")[:4])
            approver = approver_by_scope.get((region_path, "Region Pastor"))
            insert_count(cur, marker=marker, row={"occurrence": occurrence, **venue}, program_domain_id=domain_id,
                         program_type_id=type_id, categories=categories, status="approved", level="Group",
                         scope_path=target_group_path, submitter_id=submitter, created_at=now - timedelta(days=2),
                         approved_by_id=approver, approved_at=now - timedelta(days=1))
            created += 1
        elif occurrence == state_week:
            categories = [0] * 6
            for index, location in enumerate(locations):
                cats = base_values(location, occurrence, index)
                if cats:
                    categories = [left + right for left, right in zip(categories, cats)]
            venue = locations[0]
            submitter = choose_user(users, state_path, venue["path"])
            accepted_at = now - timedelta(days=week_index + 1)
            insert_count(cur, marker=marker, row={"occurrence": occurrence, **venue}, program_domain_id=domain_id,
                         program_type_id=type_id, categories=categories, status="approved", level="State",
                         scope_path=state_path, submitter_id=submitter, created_at=accepted_at,
                         auto_accepted=True, approved_at=accepted_at)
            created += 1
        else:
            for location_index, location in enumerate(locations):
                if occurrence == weeks[-1] and location["location_id"] == missing_location["location_id"]:
                    continue
                if location["path"] == mid_location["path"] and occurrence < mid_open_date:
                    continue
                # Replace the local submissions for one location/date with a
                # rejected source and its linked correction awaiting review.
                if location["location_id"] == correction_location["location_id"] and occurrence == correction_week:
                    submitter = choose_user(users, nearest_path(location["path"], "Local"), location["path"])
                    reviewer = approver_by_scope.get((target_group_path, "Group Pastor"))
                    rejected_id = insert_count(
                        cur, marker=marker, row={"occurrence": occurrence, **location}, program_domain_id=domain_id,
                        program_type_id=type_id, categories=(21, 24, 9, 10, 5, 4), status="rejected", level="Local",
                        scope_path=location["path"], submitter_id=submitter, created_at=now - timedelta(days=4),
                        rejection_reason="The submitted category breakdown did not match the reviewed tally.",
                        rejected_by_id=reviewer, rejected_at=now - timedelta(days=3),
                    )
                    insert_count(
                        cur, marker=marker, row={"occurrence": occurrence, **location}, program_domain_id=domain_id,
                        program_type_id=type_id, categories=(20, 25, 8, 11, 5, 4), status="pending", level="Local",
                        scope_path=location["path"], submitter_id=submitter, created_at=now - timedelta(days=2),
                        supersedes_id=rejected_id,
                    )
                    created += 2
                    continue
                categories = base_values(location, occurrence, location_index + week_index)
                if categories is None:
                    continue
                if location["location_id"] == section_location["location_id"] and occurrence == section_week:
                    split = [
                        (categories[0] // 3, categories[1] // 3, categories[2] // 3, categories[3] // 3, categories[4] // 3, categories[5] // 3),
                        (categories[0] // 3, categories[1] // 3, categories[2] // 3, categories[3] // 3, categories[4] // 3, categories[5] // 3),
                    ]
                    split.append(tuple(categories[i] - split[0][i] - split[1][i] for i in range(6)))
                    for label, section in zip(("Main hall", "Overflow", "Youth section"), split):
                        submitter = choose_user(users, nearest_path(location["path"], "Local"), location["path"])
                        group_path = nearest_path(location["path"], "Group")
                        reviewer = approver_by_scope.get((group_path, "Group Pastor"))
                        at = datetime.combine(occurrence, time.min, LAGOS).astimezone(timezone.utc) + timedelta(hours=12)
                        insert_count(cur, marker=marker, row={"occurrence": occurrence, **location}, program_domain_id=domain_id,
                                     program_type_id=type_id, categories=section, status="approved", level="Local",
                                     scope_path=location["path"], submitter_id=submitter, created_at=at,
                                     approved_by_id=reviewer, approved_at=at + timedelta(hours=4), section=label)
                        created += 1
                    continue
                status = "approved"
                created_at = datetime.combine(occurrence, time.min, LAGOS).astimezone(timezone.utc) + timedelta(hours=9)
                approved_by_id = None
                approved_at = None
                if location["location_id"] == pending_location["location_id"] and occurrence == pending_week:
                    status = "pending"
                    created_at = now - timedelta(hours=31)
                elif location["location_id"] == pending_location["location_id"] and occurrence == weeks[-1]:
                    status = "pending"
                    created_at = now - timedelta(hours=6)
                else:
                    group_path = nearest_path(location["path"], "Group")
                    approved_by_id = approver_by_scope.get((group_path, "Group Pastor"))
                    approved_at = created_at + timedelta(hours=3)
                if status == "pending" and created_at > now:
                    created_at = now - timedelta(hours=6)
                submitter = choose_user(users, nearest_path(location["path"], "Local"), location["path"])
                insert_count(cur, marker=marker, row={"occurrence": occurrence, **location}, program_domain_id=domain_id,
                             program_type_id=type_id, categories=categories, status=status, level="Local",
                             scope_path=location["path"], submitter_id=submitter, created_at=created_at,
                             approved_by_id=approved_by_id, approved_at=approved_at)
                created += 1

    cur.connection.commit()
    opened = manifest["opened_on_changes"][0]
    manifest_path(marker).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Seeded {created} marked count rows across {len(weeks)} Sundays, {len(regions)} regions, {len(groups)} groups, and {len(locations)} locations.")
    print(f"Group-combined Sunday: {group_week.isoformat()} at {groups_by_path[target_group_path]} ({target_group_path}).")
    print(f"State auto-accepted Sunday: {state_week.isoformat()} at {state_path}.")
    print(f"No-report case: {missing_location['name']} on {weeks[-1].isoformat()}; zero case: {zero_location['name']} on {zero_week.isoformat()}; three labelled submissions at {section_location['name']} on {section_week.isoformat()}.")
    print(f"Mid-period location: {mid_location['name']} opened {opened['seeded']}; correction history: {correction_location['name']} on {correction_week.isoformat()}.")
    print(f"Marker: B2_DEMO:{marker} | manifest: {manifest_path(marker)}")


def _is_descendant(path: str, scope: str) -> bool:
    return path == scope or path.startswith(scope + ".")


def remove(cur, marker: str):
    marker_file = manifest_path(marker)
    manifest = None
    if marker_file.exists():
        manifest = json.loads(marker_file.read_text(encoding="utf-8"))
    prefix = f"B2_DEMO:{marker}"
    cur.execute("SELECT count(*) FROM counts WHERE left(note, length(%s))=%s", (prefix, prefix))
    count = cur.fetchone()[0]
    if not count:
        print(f"No count rows found for marker {marker!r}.")
        return
    if not manifest:
        raise SystemExit("Refusing --remove: seed manifest is missing, so the temporary location lifecycle value cannot be restored safely.")
    for item in manifest.get("opened_on_changes", []):
        cur.execute("SELECT opened_on FROM locations WHERE location_id=%s FOR UPDATE", (item["location_id"],))
        current = cur.fetchone()
        if not current or (current[0].isoformat() if current[0] else None) != item["seeded"]:
            raise SystemExit("Refusing --remove: the seeded location opened_on value changed after seeding.")
    cur.execute("DELETE FROM counts WHERE left(note, length(%s))=%s", (prefix, prefix))
    for item in manifest.get("opened_on_changes", []):
        cur.execute("UPDATE locations SET opened_on=%s, last_modify=now() WHERE location_id=%s", (item.get("original"), item["location_id"]))
    cur.connection.commit()
    marker_file.unlink(missing_ok=True)
    print(f"Removed {count} marked count rows and restored the temporary location lifecycle value.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed B2 Sunday Worship demo data into a designated dev Supabase database.")
    parser.add_argument("--dev-project-ref", required=True, help="The 20-character Supabase project reference; must match DATABASE_URL's pooler user.")
    parser.add_argument("--state-code", default="KW")
    parser.add_argument("--demo-group", default="Ilorin East Group")
    parser.add_argument("--end-date", default="", help="Optional latest Sunday YYYY-MM-DD; defaults to the latest Sunday in Africa/Lagos.")
    parser.add_argument("--marker", default=MARKER_DEFAULT)
    parser.add_argument("--remove", action="store_true", help="Remove only rows carrying this exact B2 marker and restore lifecycle metadata.")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{3,64}", args.marker):
        raise SystemExit("Marker must be 3-64 letters, digits, underscores, or hyphens.")
    url = make_url(settings.SYNC_DATABASE_URL or settings.DATABASE_URL)
    validate_development_target(url, args.dev_project_ref)
    connection = psycopg2.connect(**connect_args(url))
    try:
        with connection.cursor() as cur:
            if args.remove:
                prefix = f"B2_DEMO:{args.marker}"
                cur.execute("SELECT count(*) FROM counts WHERE left(note, length(%s))=%s", (prefix, prefix))
                if cur.fetchone()[0] == 0:
                    print(f"No count rows found for marker {args.marker!r}.")
                    return
                make_snapshot(url, "pre_b2_demo_remove")
                remove(cur, args.marker)
            else:
                make_snapshot(url, "pre_b2_demo_seed")
                seed(cur, args, url)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
