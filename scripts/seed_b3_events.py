"""Seed/remove a clearly marked multi-day Retreat and Crusade B3 fixture.

By default this script only accepts the local restored development clone on
127.0.0.1:55432. It never targets the configured remote database implicitly.
Every campaign, event, count and convert record carries B3_DEMO marker text.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
import sys
import uuid
from zoneinfo import ZoneInfo

import psycopg2
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings

MARKER = "B3_DEMO:b3-events-demo-v1"
LOCAL_DATABASES = {"church_alembic_restore_proof", "dclm_perf"}
LAGOS = ZoneInfo("Africa/Lagos")


def _database_url():
    return make_url(str(settings.SYNC_DATABASE_URL or settings.DATABASE_URL))


def _connect(url):
    return psycopg2.connect(
        host=url.host, port=url.port or 5432, user=url.username,
        password=url.password, dbname=url.database,
        sslmode="require" if url.host not in {"localhost", "127.0.0.1", "::1"} else "prefer",
        connect_timeout=8,
    )


def _require_local(url):
    if url.host not in {"localhost", "127.0.0.1", "::1"} or (url.port or 5432) != 55432 or url.database not in LOCAL_DATABASES:
        raise SystemExit("Refusing: use the disposable local restored clone on loopback port 55432.")


def _ids(cur):
    cur.execute("SELECT id, slug, name, domain_id FROM program_types WHERE is_deleted IS FALSE")
    return {row[1]: {"id": row[0], "name": row[2], "domain_id": row[3]} for row in cur.fetchall()}


def _program_type(cur, types, *, domain_id, slug, name):
    if slug in types:
        return types[slug]["id"]
    cur.execute(
        "INSERT INTO program_types (domain_id,slug,name,description,created_at,last_modify,is_deleted,operation) "
        "VALUES (%s,%s,%s,%s,now(),now(),false,'CREATE') RETURNING id",
        (domain_id, slug, name, MARKER),
    )
    type_id = cur.fetchone()[0]
    types[slug] = {"id": type_id, "name": name, "domain_id": domain_id}
    return type_id


def _campaign(cur, *, domain_id, code, title, mode, reporting_scope, path, alpha_id, start, end, creator):
    campaign_id = str(uuid.uuid4())
    cur.execute(
        """INSERT INTO program_campaigns
           (id,domain_id,path,campaign_code,title,description,event_mode,reporting_scope,status,
            alpha_location_id,start_date,end_date,created_by_id,created_at,last_modify,is_deleted,operation)
           VALUES (%s,%s,%s::ltree,%s,%s,%s,%s,%s,'completed',%s,%s,%s,%s,now(),now(),false,'CREATE')""",
        (campaign_id, domain_id, path, code, title, MARKER, mode, reporting_scope, alpha_id, start, end, creator),
    )
    return campaign_id


def _event(cur, *, campaign_id, program_type_id, event_date, title, path, scope, alpha_id, creator):
    event_id = str(uuid.uuid4())
    cur.execute(
        """INSERT INTO program_events
           (id,program_type_id,campaign_id,path,date,title,is_public,published_at,event_mode,reporting_scope,
            campaign_code,alpha_location_id,is_alpha_event,collection_window_start,collection_window_end,
            audience_segment,approval_status,created_by_id,approved_by_id,approved_at,approval_note,
            created_at,last_modify,is_deleted,operation)
           VALUES (%s,%s,%s,%s::ltree,%s,%s,false,NULL,%s,%s,%s,%s,%s,NULL,NULL,NULL,
                   'approved',%s,%s,now(),%s,now(),now(),false,'CREATE')""",
        (event_id, program_type_id, campaign_id, path, event_date, title,
         "retreat" if scope == "region" else "crusade", scope, MARKER, alpha_id,
         bool(alpha_id), creator, creator, MARKER),
    )
    return event_id


def _insert_count(cur, *, event_id, location, scope_path, level, program_domain_id,
                  program_type_id, program_domain, program_type, source_role,
                  status, total, entered_by, occurrence_date, rejection_reason=None):
    count_id, client_id = str(uuid.uuid4()), str(uuid.uuid4())
    categories = (total // 6, total // 6, total // 6, total // 6, total // 6, total - (total // 6) * 5)
    created_at = datetime.now(timezone.utc) - timedelta(hours=36 if status == "pending" else 3)
    local_midnight = datetime.combine(occurrence_date, time.min, LAGOS).astimezone(timezone.utc)
    cur.execute(
        """INSERT INTO counts
           (id,client_id,path,location_id,date,event_id,church_type,program_level,program_domain_id,
            program_type_id,program_scope_path,program_domain,program_type,adult_male,adult_female,
            youth_male,youth_female,boys,girls,total,status,note,source_role,submission_channel,
            entered_by_id,created_at,last_modify,is_deleted,operation,auto_accepted,approved_by_id,
            approved_at,rejection_reason,rejected_by_id,rejected_at)
           VALUES (%s,%s,%s::ltree,%s,%s,%s,%s,%s,%s,%s,%s::ltree,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                   'field_utility',%s,%s,%s,false,'CREATE',false,%s,%s,%s,%s,%s)""",
        (count_id, client_id, location["path"], location["id"], local_midnight, event_id,
         location.get("church_type") or "DLBC", level, program_domain_id, program_type_id,
         scope_path, program_domain, program_type, *categories, total, status,
         f"{MARKER} | synthetic B3 sample", source_role, entered_by, created_at,
         created_at, entered_by if status == "approved" else None,
         created_at if status == "approved" else None,
         rejection_reason, entered_by if status == "rejected" else None,
         created_at if status == "rejected" else None),
    )
    return count_id


def _insert_convert(cur, *, event_id, location, scope_path, level, domain_id,
                    program_type_id, entered_by, occurrence_date):
    local_midnight = datetime.combine(occurrence_date, time.min, LAGOS).astimezone(timezone.utc)
    cur.execute(
        """INSERT INTO records
           (id,path,location_id,date,event_id,church_type,program_level,program_domain_id,
            program_type_id,program_scope_path,program_domain,program_type,record_type,name,gender,
            phone,details,status,note,source_role,submission_channel,entered_by_id,created_at,
            last_modify,is_deleted,operation)
           VALUES (%s,%s::ltree,%s,%s,%s,%s,%s,%s,%s,%s::ltree,'Global Crusade',%s,
                   'convert',%s,'unknown','0000000000','{}'::jsonb,'approved',%s,%s,'field_utility',
                   %s,now(),now(),false,'CREATE')""",
        (str(uuid.uuid4()), location["path"], location["id"], local_midnight, event_id,
         location.get("church_type") or "DLBC", level, domain_id, program_type_id, scope_path,
        "Crusade Evening", "B3 Demo Convert", f"{MARKER} synthetic convert", "satellite", entered_by),
    )


def seed(cur, state_code: str):
    cur.execute("SELECT state_name,path::text FROM states WHERE state_code=%s", (state_code,))
    state = cur.fetchone()
    if not state:
        raise SystemExit(f"State code {state_code!r} is not present in the local clone.")
    state_name, state_path = state
    cur.execute("SELECT count(*) FROM program_campaigns WHERE campaign_code LIKE %s", (f"{MARKER}%",))
    if cur.fetchone()[0]:
        raise SystemExit(f"{MARKER} already exists; run --remove before reseeding.")
    cur.execute("SELECT slug,id FROM program_domains WHERE slug IN ('retreat','global_crusade') AND is_deleted IS FALSE")
    domain_ids = dict(cur.fetchall())
    if set(domain_ids) != {"retreat", "global_crusade"}:
        raise SystemExit("Canonical Retreat and Global Crusade domains are required.")
    cur.execute("SELECT region_name,path::text FROM regions WHERE path <@ %s::ltree ORDER BY path", (state_path,))
    regions = [{"name": n, "path": p} for n, p in cur.fetchall()]
    cur.execute("""SELECT location_id::text,location_name,path::text,church_type,opened_on,is_active,closed_on
                   FROM locations WHERE path <@ %s::ltree ORDER BY path""", (state_path,))
    all_locations = [{"id": i, "name": n, "path": p, "church_type": t, "opened_on": o,
                      "is_active": active, "closed_on": close} for i,n,p,t,o,active,close in cur.fetchall()]
    locations_by_region = {r["path"]: [x for x in all_locations if x["path"].startswith(r["path"] + ".")] for r in regions}
    if not regions or not all_locations:
        raise SystemExit("The selected state must have Regions and Locations.")
    cur.execute("""SELECT u.user_id::text,u.path::text,r.role_name FROM users u
                   JOIN user_roles ur ON ur.user_id=u.user_id JOIN roles r ON r.id=ur.role_id
                   WHERE u.is_active IS TRUE AND u.is_deleted IS FALSE AND u.approval_status='approved'
                   AND u.path::ltree <@ %s::ltree ORDER BY u.path""", (state_path,))
    people = cur.fetchall()
    if not people:
        raise SystemExit("An approved active user is required to author synthetic rows.")
    fallback_user = people[0][0]
    def user_at(path):
        return next((uid for uid, upath, _ in people if upath == path), fallback_user)
    type_rows = _ids(cur)
    def type_id(slug, name, domain_slug):
        domain_id = domain_ids[domain_slug]
        found = type_rows.get(slug)
        if found and int(found["domain_id"]) == int(domain_id):
            return found["id"]
        # ProgramType.slug is globally unique. Reuse is safe only when the
        # type already belongs to this domain; otherwise create a marked type.
        demo_slug = f"b3_demo_{slug}"
        demo_found = type_rows.get(demo_slug)
        if demo_found and int(demo_found["domain_id"]) == int(domain_id):
            return demo_found["id"]
        return _program_type(cur, type_rows, domain_id=domain_id, slug=demo_slug, name=name)

    retreat_types = [(type_id("bible_study", "Bible Study", "retreat"), "Bible Study"),
                     (type_id("b3_demo_prayer", "Prayer", "retreat"), "Prayer"),
                     (type_id("b3_demo_evening_service", "Evening Service", "retreat"), "Evening Service")]
    crusade_types = [(type_id("crusade_evening", "Crusade Evening", "global_crusade"), "Crusade Evening"),
                     (type_id("leadership_development", "Leadership Development Meeting", "global_crusade"), "Leadership Development Meeting"),
                     (type_id("impact_academy", "Impact Academy", "global_crusade"), "Impact Academy")]
    alpha = all_locations[0]
    years = [("easter-2025", "Easter Retreat 2025", date(2025,4,17)), ("easter-2026", "Easter Retreat 2026", date(2026,4,2))]
    event_count = count_count = record_count = campaign_count = 0

    for suffix, title, start in years:
        end = start + timedelta(days=4)
        campaign_id = _campaign(cur, domain_id=domain_ids["retreat"], code=f"{MARKER}:{suffix}",
            title=f"{title} [{MARKER}]", mode="retreat", reporting_scope="region", path=state_path,
            alpha_id=None, start=start, end=end, creator=fallback_user)
        campaign_count += 1
        previous_campaign = suffix == "easter-2025"
        for region in regions:
            venue = next(iter(locations_by_region[region["path"]]), None)
            if not venue:
                continue
            for day_index in range(5):
                event_date = start + timedelta(days=day_index)
                for type_index, (program_type_id, label) in enumerate(retreat_types):
                    event_id = _event(cur, campaign_id=campaign_id, program_type_id=program_type_id,
                        event_date=event_date, title=f"Day {day_index+1}: {label}", path=region["path"],
                        scope="region", alpha_id=None, creator=user_at(region["path"]))
                    event_count += 1
                    missing = not previous_campaign and region == regions[-1] and day_index == 1 and type_index == 1
                    if missing:
                        continue
                    stable_region_offset = sum(ord(char) for char in region["path"]) % 47
                    status, total = "approved", 280 + 29*day_index + 41*type_index + stable_region_offset
                    if not previous_campaign and region == regions[1] and day_index == 1 and type_index == 0:
                        status = "pending"
                    if not previous_campaign and region == regions[2] and day_index == 3 and type_index == 2:
                        status, total = "rejected", 999
                    if not previous_campaign and region == regions[3] and day_index == 0 and type_index == 0:
                        total = 0
                    _insert_count(cur, event_id=event_id, location=venue, scope_path=region["path"],
                        level="Region", program_domain_id=domain_ids["retreat"], program_type_id=program_type_id,
                        program_domain="Retreat", program_type=label, source_role="regular", status=status,
                        total=total, entered_by=user_at(region["path"]), occurrence_date=event_date,
                        rejection_reason="Synthetic rejected example" if status=="rejected" else None)
                    count_count += 1

    crusade_cycles = [("previous", "September 2026 Crusade", date(2026,9,16)), ("october", "October 2026 Global Crusade", date(2026,10,14))]
    for suffix, title, start in crusade_cycles:
        end = start + timedelta(days=4)
        campaign_id = _campaign(cur, domain_id=domain_ids["global_crusade"], code=f"{MARKER}:crusade-{suffix}",
            title=f"{title} [{MARKER}]", mode="crusade", reporting_scope="state", path=state_path,
            alpha_id=alpha["id"], start=start, end=end, creator=fallback_user)
        campaign_count += 1
        for day_index in range(5):
            for type_index, (program_type_id, label) in enumerate(crusade_types):
                event_date = start + timedelta(days=day_index)
                event_id = _event(cur, campaign_id=campaign_id, program_type_id=program_type_id,
                    event_date=event_date, title=f"Day {day_index+1}: {label}", path=state_path,
                    scope="state", alpha_id=alpha["id"], creator=fallback_user)
                event_count += 1
                # Alpha is one report at State scope for every scheduled session.
                _insert_count(cur, event_id=event_id, location=alpha, scope_path=state_path, level="State",
                    program_domain_id=domain_ids["global_crusade"], program_type_id=program_type_id,
                    program_domain="Global Crusade", program_type=label, source_role="alpha", status="approved",
                    total=2100 + 180*day_index + 200*type_index, entered_by=fallback_user, occurrence_date=event_date)
                count_count += 1
                for location_index, location in enumerate(all_locations):
                    if location["id"] == alpha["id"]:
                        continue
                    active_on_date = (location["is_active"] or location["closed_on"] and location["closed_on"] > event_date)
                    active_on_date = bool(active_on_date and (location["opened_on"] is None or location["opened_on"] <= event_date)
                                          and (location["closed_on"] is None or location["closed_on"] > event_date))
                    if not active_on_date:
                        continue
                    # Leave one satellite silent for each session; the omitted
                    # location rotates so every location reports in the series.
                    if location_index % 7 == day_index % 7:
                        continue
                    status = "pending" if suffix == "october" and location_index == 1 and day_index == 0 and type_index == 0 else "approved"
                    size = 155 + (location_index * 13 + day_index * 31 + type_index * 23) % 260
                    if suffix == "october" and location_index == 2 and day_index == 3 and type_index == 1:
                        size = 1960
                    _insert_count(cur, event_id=event_id, location=location, scope_path=location["path"],
                        level="Location", program_domain_id=domain_ids["global_crusade"], program_type_id=program_type_id,
                        program_domain="Global Crusade", program_type=label, source_role="satellite", status=status,
                        total=size, entered_by=user_at(location["path"]), occurrence_date=event_date)
                    count_count += 1
                # One approved convert record without a count row on the
                # October day-two Crusade Evening event.
                if suffix == "october" and day_index == 1 and type_index == 0:
                    _insert_convert(cur, event_id=event_id, location=all_locations[1], scope_path=all_locations[1]["path"],
                        level="Location", domain_id=domain_ids["global_crusade"], program_type_id=program_type_id,
                        entered_by=user_at(all_locations[1]["path"]), occurrence_date=event_date)
                    record_count += 1

    return {"campaigns": campaign_count, "events": event_count, "counts": count_count, "records": record_count,
            "state": state_name}


def remove(cur):
    marker_like = f"%{MARKER}%"
    cur.execute("DELETE FROM records WHERE note LIKE %s", (marker_like,))
    removed_records = cur.rowcount
    cur.execute("DELETE FROM counts WHERE note LIKE %s", (marker_like,))
    removed_counts = cur.rowcount
    cur.execute("DELETE FROM program_events WHERE campaign_id IN (SELECT id FROM program_campaigns WHERE campaign_code LIKE %s)", (f"{MARKER}%",))
    removed_events = cur.rowcount
    cur.execute("DELETE FROM program_campaigns WHERE campaign_code LIKE %s", (f"{MARKER}%",))
    removed_campaigns = cur.rowcount
    cur.execute("DELETE FROM program_types WHERE description=%s AND slug IN ('b3_demo_bible_study','b3_demo_prayer','b3_demo_evening_service') AND NOT EXISTS (SELECT 1 FROM program_events e WHERE e.program_type_id=program_types.id)", (MARKER,))
    removed_types = cur.rowcount
    return {"records": removed_records, "counts": removed_counts, "events": removed_events,
            "campaigns": removed_campaigns, "created_types": removed_types}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-code", default="KW", help="State code (default: KW).")
    parser.add_argument("--remove", action="store_true", help="Delete only rows carrying the B3 demo marker.")
    args = parser.parse_args()
    url = _database_url()
    _require_local(url)
    connection = _connect(url)
    try:
        with connection:
            with connection.cursor() as cur:
                result = remove(cur) if args.remove else seed(cur, args.state_code.upper())
        print(("Removed" if args.remove else "Seeded") + f" {MARKER}: {result}")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
