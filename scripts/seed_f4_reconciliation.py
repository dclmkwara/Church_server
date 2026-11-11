"""Create/remove a bounded F4 reconciliation fixture in the local clone only.

Usage (PowerShell):
  $env:F4_DATABASE_URL='postgresql://postgres@127.0.0.1:55434/dclm_slice_f'
  python scripts/seed_f4_reconciliation.py --apply
  python scripts/seed_f4_reconciliation.py --remove

The script refuses every host/database except loopback + dclm_slice_f.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import Json

MARKER = "F4_TEST:f4-v1"
STATE_PATH = "org.234.KW"
REGION_PATH = "org.234.KW.ILR"
GROUP_PATH = "org.234.KW.ILR.ILE"
LOCATION_PATH = "org.234.KW.ILR.ILE.003"
ZERO_LOCATION_PATH = "org.234.KW.ILR.ILE.002"
WEEKLY_DOMAIN_ID = 1
RETREAT_DOMAIN_ID = 2
SUNDAY_TYPE_ID = 1
WORKERS_TYPE_ID = 19
LEADERS_TYPE_ID = 17
RETREAT_BIBLE_TYPE_ID = 22


def _connect():
    raw = __import__("os").environ.get("F4_DATABASE_URL", "")
    if not raw:
        raise SystemExit("Set F4_DATABASE_URL to the disposable local clone URL.")
    parsed = urlparse(raw)
    if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Refusing non-loopback database host.")
    dbname = parsed.path.lstrip("/")
    if dbname != "dclm_slice_f":
        raise SystemExit("Refusing database other than dclm_slice_f.")
    return psycopg2.connect(raw)


def _context(cur):
    cur.execute("""
        SELECT current_database(), inet_server_addr()::text, inet_server_port(),
               l.location_id::text, l.path::text, l.church_type,
               z.location_id::text, z.path::text, z.church_type,
               g.group_id::text, g.path::text,
               r.path::text,
               (SELECT user_id::text FROM users WHERE path::text = %s ORDER BY email LIMIT 1),
               (SELECT user_id::text FROM users WHERE path::text = %s ORDER BY email LIMIT 1),
               (SELECT user_id::text FROM users WHERE path::text = %s ORDER BY email LIMIT 1),
               (SELECT fellowship_id::text FROM fellowships WHERE location_id=l.location_id LIMIT 1)
        FROM locations l
        JOIN dclm_groups g USING (group_id)
        JOIN regions r USING (region_id)
        JOIN locations z ON z.group_id=g.group_id AND z.path::text=%s
        WHERE l.path::text=%s
    """, (LOCATION_PATH, GROUP_PATH, STATE_PATH, ZERO_LOCATION_PATH, LOCATION_PATH))
    row = cur.fetchone()
    if not row:
        raise SystemExit("Fixture hierarchy paths were not found in the local clone.")
    db, host, port, loc_id, loc_path, church, zero_id, zero_path, zero_church, group_id, group_path, region_path, loc_user, group_user, state_user, fellowship = row
    host = host.split("/", 1)[0] if host else None
    if db != "dclm_slice_f" or host not in {"127.0.0.1", "::1"}:
        raise SystemExit(f"Refusing unexpected database endpoint {db}@{host}:{port}.")
    if not loc_user or not group_user or not state_user:
        raise SystemExit("Required synthetic location/group/state users are missing.")
    return {
        "location_id": loc_id, "location_path": loc_path, "church_type": church,
        "zero_location_id": zero_id, "zero_location_path": zero_path, "zero_church_type": zero_church,
        "group_id": group_id, "group_path": group_path, "region_path": region_path,
        "location_user": loc_user, "group_user": group_user, "state_user": state_user,
        "fellowship_id": fellowship,
    }


def _date_sunday():
    today = datetime.now(ZoneInfo("Africa/Lagos")).date()
    return today - timedelta(days=(today.weekday() + 1) % 7)


def _insert_count(cur, ctx, *, count_date, location_id, path, level="local", scope_path=None,
                  event_id=None, categories=(0, 0, 0, 0, 0, 0), actor=None, note=MARKER):
    am, af, ym, yf, boys, girls = categories
    return _insert(cur, """
      INSERT INTO counts
        (id,path,location_id,date,event_id,adult_male,adult_female,youth_male,youth_female,boys,girls,total,
         status,note,source_role,submission_channel,entered_by_id,approved_by_id,approved_at,church_type,
         program_domain,program_type,program_level,program_domain_id,program_type_id,program_scope_path,
         created_at,last_modify,is_deleted,operation)
      VALUES (gen_random_uuid(),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'approved',%s,'regular','f4_test',%s,%s,now(),%s,%s,%s,%s,%s,%s,%s,now(),now(),false,'INSERT')
      RETURNING id::text
    """, (
        path, location_id, datetime.combine(count_date, time(10), tzinfo=timezone.utc), event_id,
        am, af, ym, yf, boys, girls, sum(categories), note, actor or ctx["location_user"],
        ctx["state_user"], ctx["church_type"], "Weekly Programs" if not event_id else "Retreat",
        "Sunday Worship Service" if not event_id else "Retreat Bible Study",
        {"local": "Local", "group": "Group", "region": "Region", "state": "State"}.get(level.lower(), level),
        WEEKLY_DOMAIN_ID if not event_id else RETREAT_DOMAIN_ID,
        SUNDAY_TYPE_ID if not event_id else RETREAT_BIBLE_TYPE_ID,
        scope_path or path,
    ))


def _insert(cur, sql, values):
    cur.execute(sql, values)
    return cur.fetchone()[0]


def apply(conn):
    with conn:
        with conn.cursor() as cur:
            ctx = _context(cur)
            cur.execute("SELECT count(*) FROM counts WHERE note LIKE %s", (f"%{MARKER}%",))
            if cur.fetchone()[0]:
                raise SystemExit("Marked F4 rows already exist. Run --remove before --apply.")
            sunday = _date_sunday()
            prior_sunday = sunday - timedelta(days=7)
            now = datetime.now(timezone.utc)

            # An approved current-Sunday record with an edit revision and the
            # contemporaneous other location's explicitly reported zero.
            edited_count = _insert_count(
                cur, ctx, count_date=sunday, location_id=ctx["location_id"], path=ctx["location_path"],
                categories=(18, 22, 7, 8, 3, 2), note=f"{MARKER} edited then approved",
            )
            edit_id = "f4000000-0000-4000-8000-000000000001"
            cur.execute("""
                INSERT INTO submission_edit_revisions
                  (id,submission_type,submission_id,edit_id,revision_no,action,editor_id,before_values,after_values,reason,created_at)
                VALUES (gen_random_uuid(),'count',%s,%s,1,'edit',%s,%s,%s,%s,now())
            """, (edited_count, edit_id, ctx["location_user"], Json({"total": 58}),
                  Json({"adult_male":18,"adult_female":22,"youth_male":7,"youth_female":8,"boys":3,"girls":2,"total":60}),
                  f"{MARKER} correction before approval"))
            _insert_count(cur, ctx, count_date=sunday, location_id=ctx["zero_location_id"],
                          path=ctx["zero_location_path"], categories=(0,0,0,0,0,0),
                          actor=ctx["location_user"], note=f"{MARKER} reported zero")

            # Two approved funds; one offering is corrected to the service date
            # and has a matching append-only OfferingAudit record.
            offering_ids = []
            for fund, amount in (("tithe", 5200.00), ("offering", 13800.00)):
                oid = _insert(cur, """
                    INSERT INTO offerings
                      (id,path,location_id,date,amount,payment_method,fund_type,status,note,entered_by_id,reviewed_by_id,
                       reviewed_at,church_type,program_domain,program_type,program_level,program_domain_id,program_type_id,
                       program_scope_path,created_at,last_modify,is_deleted,operation)
                    VALUES (gen_random_uuid(),%s,%s,%s,%s,'cash',%s,'approved',%s,%s,%s,now(),%s,'Weekly Programs',
                       'Sunday Worship Service','Local',1,1,%s,now(),now(),false,'INSERT') RETURNING id::text
                """, (ctx["location_path"],ctx["location_id"],datetime.combine(prior_sunday-timedelta(days=1) if fund == "tithe" else prior_sunday,time(10),tzinfo=timezone.utc),
                      amount,fund,f"{MARKER} service-date correction" if fund=="tithe" else MARKER,
                      ctx["location_user"],ctx["state_user"],ctx["church_type"],ctx["location_path"]))
                offering_ids.append(oid)
                if fund == "tithe":
                    old_date=datetime.combine(prior_sunday-timedelta(days=1),time(10),tzinfo=timezone.utc)
                    new_date=datetime.combine(prior_sunday,time(10),tzinfo=timezone.utc)
                    cur.execute("UPDATE offerings SET date=%s WHERE id=%s",(new_date,oid))
                    cur.execute("""
                      INSERT INTO offering_audits(id,offering_id,actor_id,action,reason,before_values,after_values,created_at,last_modify)
                      VALUES(gen_random_uuid(),%s,%s,'corrected',%s,%s,%s,now(),now())
                    """,(oid,ctx["state_user"],f"{MARKER} corrected service date",
                         Json({"date":old_date.isoformat()}),Json({"date":new_date.isoformat()})))

            # Snapshot denominator is deliberately two people even when the
            # live location worker roster differs; the snapshot is authoritative.
            cur.execute("SELECT worker_id::text,name,phone,unit FROM workers WHERE location_id=%s AND is_deleted IS NOT TRUE ORDER BY worker_id LIMIT 2",
                        (ctx["location_id"],))
            worker_rows=cur.fetchall()
            worker_ids=[row[0] for row in worker_rows]
            if len(worker_ids)<2:
                raise SystemExit("Two location workers are required for the roster-snapshot fixture.")
            for ptype, meeting_date, label in ((WORKERS_TYPE_ID, sunday-timedelta(days=15), "Saturday Workers Meeting"),
                                                (LEADERS_TYPE_ID, sunday+timedelta(days=2), "Tuesday Leaders Meeting")):
                cur.execute("""
                  INSERT INTO worker_attendance_submissions
                    (id,client_id,path,location_id,date,church_type,program_domain,program_type,program_level,
                     program_domain_id,program_type_id,program_scope_path,expected_workers_count,expected_worker_ids,
                     present_count,present_workers,entered_by_id,submitted_by_worker_id,submitted_by_name,note,
                     created_at,last_modify,is_deleted,operation)
                  VALUES(gen_random_uuid(),gen_random_uuid(),%s,%s,%s,%s,'Weekly Programs',%s,'Local',1,%s,%s,2,%s,1,%s,
                    %s,%s,%s,%s,now(),now(),false,'INSERT') RETURNING id::text
                """, (ctx["location_path"],ctx["location_id"],datetime.combine(meeting_date,time(10),tzinfo=timezone.utc),
                      ctx["church_type"],label,ptype,ctx["location_path"],Json(worker_ids),Json([worker_ids[0]]),
                      ctx["location_user"],worker_ids[0],"F4 Demonstration Usher",f"{MARKER} roster snapshot"))
                submission_id=cur.fetchone()[0]
                worker_id,worker_name,worker_phone,worker_unit=worker_rows[0]
                cur.execute("""
                  INSERT INTO worker_attendance
                    (id,path,location_id,date,church_type,program_level,program_domain_id,program_type_id,
                     program_scope_path,program_domain,program_type,worker_id,worker_name,worker_phone,worker_unit,
                     status,note,submission_id,entered_by_id,created_at,last_modify,is_deleted,operation)
                  VALUES(gen_random_uuid(),%s,%s,%s,%s,'Local',1,%s,%s,'Weekly Programs',%s,%s,%s,%s,%s,'present',%s,%s,%s,now(),now(),false,'INSERT')
                """,(ctx["location_path"],ctx["location_id"],datetime.combine(meeting_date,time(10),tzinfo=timezone.utc),
                      ctx["church_type"],ptype,ctx["location_path"],label,worker_id,worker_name,worker_phone or "",worker_unit,
                      f"{MARKER} roster snapshot",submission_id,ctx["location_user"]))

            # Ensure a fellowship exists only for this fixture, then create the
            # linked attendance and offering rows under the location path.
            fellowship_id=ctx["fellowship_id"]
            if not fellowship_id:
                fellowship_id=_insert(cur,"""
                  INSERT INTO fellowships(fellowship_id,location_id,fellowship_code,fellowship_name,path,created_at,last_modify,created_by,version)
                  VALUES(gen_random_uuid(),%s,'F4V1',%s,%s,now(),now(),%s,1) RETURNING fellowship_id::text
                """,(ctx["location_id"],f"{MARKER} Demo Fellowship",f"{ctx['location_path']}.F4V1",ctx["location_user"]))
            cur.execute("""
              INSERT INTO fellowship_attendance
                (id,path,fellowship_id,date,men,women,youths,children,adult_male,adult_female,youth_male,youth_female,boys,girls,total,
                 topic,note,entered_by_id,created_at,last_modify,is_deleted,operation)
              VALUES(gen_random_uuid(),%s,%s,%s,8,9,5,3,8,9,2,3,1,2,25,'F4 demo',%s,%s,now(),now(),false,'INSERT')
            """,(ctx["location_path"],fellowship_id,datetime.combine(sunday,time(14),tzinfo=timezone.utc),MARKER,ctx["location_user"]))
            cur.execute("""
              INSERT INTO fellowship_offerings(id,path,fellowship_id,date,amount,entered_by_id,note,created_at,last_modify,is_deleted,operation)
              VALUES(gen_random_uuid(),%s,%s,%s,1250,%s,%s,now(),now(),false,'INSERT')
            """,(ctx["location_path"],fellowship_id,datetime.combine(sunday,time(14),tzinfo=timezone.utc),ctx["location_user"],MARKER))

            for typ,name,gender in (("newcomer","F4 Demo Newcomer","female"),("convert","F4 Demo Convert","male")):
                cur.execute("""
                  INSERT INTO records
                    (id,path,location_id,date,record_type,name,gender,phone,status,note,entered_by_id,church_type,
                     program_domain,program_type,program_level,program_domain_id,program_type_id,program_scope_path,
                     source_role,submission_channel,details,created_at,last_modify,is_deleted,operation)
                  VALUES(gen_random_uuid(),%s,%s,%s,%s,%s,%s,%s,'approved',%s,%s,%s,'Weekly Programs','Sunday Worship Service',
                    'Local',1,1,%s,'regular','f4_test','{}'::jsonb,now(),now(),false,'INSERT')
                """,(ctx["location_path"],ctx["location_id"],datetime.combine(sunday,time(11),tzinfo=timezone.utc),typ,name,gender,
                      "0000000000",MARKER,ctx["location_user"],ctx["church_type"],ctx["location_path"]))

            campaign_id=_insert(cur,"""
              INSERT INTO program_campaigns
                (id,domain_id,path,campaign_code,title,description,event_mode,reporting_scope,status,start_date,end_date,
                 publicity_note,created_by_id,created_at,last_modify,is_deleted,operation)
              VALUES(gen_random_uuid(),%s,%s,%s,%s,%s,'retreat','region','active',%s,%s,%s,%s,now(),now(),false,'INSERT')
              RETURNING id::text
            """,(RETREAT_DOMAIN_ID,ctx["region_path"],MARKER,f"{MARKER} Retreat",f"{MARKER} fixture campaign",
                  sunday,sunday+timedelta(days=4),MARKER,ctx["state_user"]))
            event_id=_insert(cur,"""
              INSERT INTO program_events
                (id,program_type_id,campaign_id,path,date,title,is_public,event_mode,reporting_scope,campaign_code,
                 is_alpha_event,approval_status,created_by_id,approved_by_id,approved_at,approval_note,
                 created_at,last_modify,is_deleted,operation)
              VALUES(gen_random_uuid(),%s,%s,%s,%s,%s,false,'retreat','region',%s,false,'approved',%s,%s,now(),%s,
                 now(),now(),false,'INSERT') RETURNING id::text
            """,(RETREAT_BIBLE_TYPE_ID,campaign_id,ctx["region_path"],sunday,f"{MARKER} Bible Study Day 1",MARKER,
                  ctx["state_user"],ctx["state_user"],MARKER))
            event_count=_insert_count(cur,ctx,count_date=sunday,location_id=ctx["location_id"],path=ctx["location_path"],
                                      level="region",scope_path=ctx["region_path"],event_id=event_id,
                                      categories=(40,46,12,15,8,9),actor=ctx["location_user"],note=f"{MARKER} retreat day")
            print(json.dumps({"status":"applied","marker":MARKER,"group_path":ctx["group_path"],"location_path":ctx["location_path"],
                              "zero_location_path":ctx["zero_location_path"],"sunday":sunday.isoformat(),
                              "edited_count_id":edited_count,"retreat_count_id":event_count,"offering_ids":offering_ids,
                              "event_id":event_id,"campaign_id":campaign_id,"fellowship_id":fellowship_id,
                              "worker_snapshot_expected":2,"worker_snapshot_present":1},indent=2))


def remove(conn):
    with conn:
        with conn.cursor() as cur:
            _context(cur)
            # Delete only objects that carry the exact fixture marker. Parent
            # audit/revision rows are removed only when linked to marked parents.
            cur.execute("SELECT id FROM counts WHERE note LIKE %s",(f"%{MARKER}%",))
            count_ids=[row[0] for row in cur.fetchall()]
            cur.execute("SELECT id FROM offerings WHERE note LIKE %s",(f"%{MARKER}%",))
            offering_ids=[row[0] for row in cur.fetchall()]
            cur.execute("SELECT id FROM program_events WHERE title LIKE %s",(f"%{MARKER}%",))
            event_ids=[row[0] for row in cur.fetchall()]
            cur.execute("SELECT id FROM program_campaigns WHERE campaign_code=%s",(MARKER,))
            campaign_ids=[row[0] for row in cur.fetchall()]
            cur.execute("SELECT fellowship_id FROM fellowships WHERE fellowship_name LIKE %s",(f"%{MARKER}%",))
            fellowship_ids=[row[0] for row in cur.fetchall()]
            if count_ids:
                cur.execute("DELETE FROM submission_edit_revisions WHERE submission_id = ANY(%s::uuid[])", (count_ids,))
                cur.execute("DELETE FROM counts WHERE id = ANY(%s::uuid[])",(count_ids,))
            if offering_ids:
                cur.execute("DELETE FROM offering_audits WHERE offering_id = ANY(%s::uuid[])",(offering_ids,))
                cur.execute("DELETE FROM offerings WHERE id = ANY(%s::uuid[])",(offering_ids,))
            for table in ("worker_attendance","worker_attendance_submissions","fellowship_attendance","fellowship_offerings","records"):
                cur.execute(f"DELETE FROM {table} WHERE note LIKE %s",(f"%{MARKER}%",))
            if event_ids:
                cur.execute("DELETE FROM counts WHERE event_id = ANY(%s::uuid[]) AND note LIKE %s",(event_ids,f"%{MARKER}%"))
                cur.execute("DELETE FROM program_events WHERE id = ANY(%s::uuid[])",(event_ids,))
            if campaign_ids:
                cur.execute("DELETE FROM program_campaigns WHERE id = ANY(%s::uuid[])",(campaign_ids,))
            if fellowship_ids:
                cur.execute("DELETE FROM fellowships WHERE fellowship_id = ANY(%s::uuid[])",(fellowship_ids,))
            remaining={}
            for table,column in (("counts","note"),("offerings","note"),("worker_attendance","note"),("worker_attendance_submissions","note"),
                                 ("fellowship_attendance","note"),("fellowship_offerings","note"),("records","note"),
                                 ("program_events","title"),("program_campaigns","campaign_code"),
                                 ("fellowships","fellowship_name"),("submission_edit_revisions","reason"),
                                 ("offering_audits","reason")):
                cur.execute(f"SELECT count(*) FROM {table} WHERE {column} LIKE %s",(f"%{MARKER}%",))
                remaining[table]=cur.fetchone()[0]
            if any(remaining.values()):
                raise RuntimeError(f"Fixture removal incomplete: {remaining}")
            print(json.dumps({"status":"removed","marker":MARKER,"remaining_marked_rows":remaining},indent=2))


def main():
    parser=argparse.ArgumentParser()
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--apply",action="store_true")
    action.add_argument("--remove",action="store_true")
    args=parser.parse_args()
    conn=_connect()
    try:
        (apply if args.apply else remove)(conn)
    finally:
        conn.close()


if __name__=="__main__":
    main()
