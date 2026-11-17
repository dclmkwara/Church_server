"""Seed a removable, synthetic Kwara pilot dataset.

This writes only rows carrying PILOT_KWARA_2026. It targets the configured
database only after an explicit --apply --confirm-pilot-write acknowledgement.
Use --remove with the same acknowledgement to remove only marked rows.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import uuid
from zoneinfo import ZoneInfo

import psycopg2
from sqlalchemy.engine import make_url

from app.core.config import settings

MARK = "PILOT_KWARA_2026"
LAGOS = ZoneInfo("Africa/Lagos")
STATE_PATH = "org.234.KW"


def connect():
    u = make_url(settings.sync_database_url)
    return psycopg2.connect(host=u.host, port=u.port or 5432, user=u.username,
        password=u.password, dbname=u.database, sslmode="require", connect_timeout=12)


def require_ack(args):
    if not args.apply and not args.remove:
        raise SystemExit("Dry run only. Pass --apply --confirm-pilot-write to seed, or --remove --confirm-pilot-write to remove marked rows.")
    if args.confirm_pilot_write != "SEED-KWARA-PILOT":
        raise SystemExit("Explicit acknowledgement required: --confirm-pilot-write SEED-KWARA-PILOT")


def remove(cur):
    cur.execute("DELETE FROM worker_attendance WHERE note LIKE %s", (f"%{MARK}%",))
    attendance = cur.rowcount
    cur.execute("DELETE FROM worker_attendance_submissions WHERE note LIKE %s", (f"%{MARK}%",))
    submissions = cur.rowcount
    cur.execute("DELETE FROM records WHERE note LIKE %s", (f"%{MARK}%",))
    records = cur.rowcount
    cur.execute("DELETE FROM location_expected_population WHERE note LIKE %s", (f"%{MARK}%",))
    population_estimates = cur.rowcount
    cur.execute("DELETE FROM offerings WHERE note LIKE %s", (f"%{MARK}%",))
    offerings = cur.rowcount
    cur.execute("SELECT DISTINCT count_group_id::text FROM counts WHERE note LIKE %s AND count_group_id IS NOT NULL", (f"%{MARK}%",))
    marked_count_group_ids = [row[0] for row in cur.fetchall()]
    cur.execute("DELETE FROM counts WHERE note LIKE %s", (f"%{MARK}%",))
    counts = cur.rowcount
    cur.execute("""DELETE FROM count_groups cg WHERE cg.id::text = ANY(%s)
        AND NOT EXISTS (SELECT 1 FROM counts c WHERE c.count_group_id=cg.id)""", (marked_count_group_ids,))
    count_groups = cur.rowcount
    cur.execute("DELETE FROM event_assignments WHERE note LIKE %s", (f"%{MARK}%",))
    assignments = cur.rowcount
    cur.execute("DELETE FROM program_events WHERE approval_note LIKE %s OR title LIKE %s", (f"%{MARK}%", f"%{MARK}%"))
    events = cur.rowcount
    cur.execute("DELETE FROM program_campaigns WHERE campaign_code LIKE %s", (f"%{MARK}%",))
    campaigns = cur.rowcount
    cur.execute("DELETE FROM broadcast_messages WHERE title LIKE %s", (f"%{MARK}%",))
    broadcasts = cur.rowcount
    cur.execute("DELETE FROM announcements WHERE general_announcements LIKE %s OR revival_info LIKE %s", (f"%{MARK}%", f"%{MARK}%"))
    announcements = cur.rowcount
    cur.execute("DELETE FROM transfer_requests WHERE reason LIKE %s", (f"%{MARK}%",))
    transfers = cur.rowcount
    cur.execute("DELETE FROM workers WHERE email=%s", (f"pilot.transfer.{MARK.lower()}@example.test",))
    demo_workers = cur.rowcount
    cur.execute("DELETE FROM program_types WHERE description=%s AND NOT EXISTS (SELECT 1 FROM program_events e WHERE e.program_type_id=program_types.id)", (MARK,))
    types = cur.rowcount
    return {"attendance": attendance, "submissions": submissions, "records": records,
            "population_estimates": population_estimates, "offerings": offerings,
            "counts": counts, "count_groups": count_groups, "assignments": assignments,
            "events": events, "campaigns": campaigns, "broadcasts": broadcasts,
            "announcements": announcements, "transfers": transfers,
            "demo_workers": demo_workers, "types": types}


def seed(cur):
    cur.execute("SELECT count(*) FROM program_campaigns WHERE campaign_code LIKE %s", (f"{MARK}:%",))
    if cur.fetchone()[0]:
        raise RuntimeError(f"{MARK} already exists; remove the marked fixture before reseeding.")
    cur.execute("SELECT state_name,path::text FROM states WHERE state_code='KW'")
    state = cur.fetchone()
    if not state or state[1] != STATE_PATH:
        raise RuntimeError("Expected Kwara State at org.234.KW; refusing to write.")
    state_name, state_path = state
    cur.execute("""SELECT r.region_id::text,r.region_name,r.path::text FROM regions r
                    WHERE r.path <@ %s::ltree ORDER BY r.path""", (state_path,))
    regions = [dict(id=i,name=n,path=p) for i,n,p in cur.fetchall()]
    cur.execute("""SELECT g.group_id::text,g.group_name,g.path::text,r.region_name,r.path::text
                    FROM dclm_groups g JOIN regions r USING(region_id)
                    WHERE g.path <@ %s::ltree ORDER BY g.path""", (state_path,))
    groups = [dict(id=i,name=n,path=p,region=r,region_path=rp) for i,n,p,r,rp in cur.fetchall()]
    cur.execute("""SELECT l.location_id::text,l.location_name,l.path::text,l.church_type,
                    l.opened_on,l.closed_on,g.group_name,g.path::text,r.region_name,r.path::text
                    FROM locations l JOIN dclm_groups g USING(group_id) JOIN regions r USING(region_id)
                    WHERE l.path <@ %s::ltree AND l.is_active IS TRUE ORDER BY l.path""", (state_path,))
    locations = [dict(id=i,name=n,path=p,church=t,opened=o,closed=c,group=g,group_path=gp,region=r,region_path=rp)
                 for i,n,p,t,o,c,g,gp,r,rp in cur.fetchall()]
    if not regions or not groups or not locations:
        raise RuntimeError("Kwara requires regions, groups, and active locations before seeding.")
    alpha = next((l for l in locations if l['name']=='DLCF Living Spring'),locations[0])
    sample_locations=[]
    for region in regions:
        row=next((l for l in locations if l['region_path']==region['path']),None)
        if row and row not in sample_locations: sample_locations.append(row)
    for row in (alpha,next((l for l in locations if l['path']=='org.234.KW.ILR.ILE.004'),None)):
        if row and row not in sample_locations: sample_locations.append(row)
    cur.execute("""SELECT u.user_id::text,u.email,u.path::text,r.role_name
                    FROM users u JOIN user_roles ur ON ur.user_id=u.user_id JOIN roles r ON r.id=ur.role_id
                    WHERE u.is_active IS TRUE AND u.is_deleted IS FALSE AND u.approval_status='approved'
                    AND u.path::ltree <@ %s::ltree ORDER BY u.path""", (state_path,))
    users = [dict(id=i,email=e,path=p,role=r) for i,e,p,r in cur.fetchall()]
    def user(role, path=None):
        rows=[x for x in users if x['role']==role and (path is None or x['path']==path)]
        if rows: return rows[0]['id']
        if path:
            rows=[x for x in users if x['role']==role and (path.startswith(x['path']+'.') or path==x['path'])]
            if rows: return rows[0]['id']
        rows=[x for x in users if x['role']=='State Admin' and x['path']==state_path]
        if rows: return rows[0]['id']
        raise RuntimeError(f"Approved {role} required in {path or 'Kwara'}")
    state_pastor=user('State Overseer',state_path)
    for idx,loc in enumerate(locations):
        cur.execute("""INSERT INTO location_expected_population(id,location_id,path,expected_value,effective_from,set_by_id,note,created_at)
          VALUES(%s,%s,%s::ltree,%s,%s,%s,%s,now())""",
          (str(uuid.uuid4()),loc['id'],loc['path'],700+((idx*83)%1200),date(2026,1,1),state_pastor,
           f'{MARK} synthetic estimate; demonstration only'))
    cur.execute("""SELECT d.slug,d.id,t.slug,t.id,t.name FROM program_types t
                    JOIN program_domains d ON d.id=t.domain_id
                    WHERE d.is_deleted IS FALSE AND t.is_deleted IS FALSE""")
    types={(d,slug):{'id':tid,'name':n} for d,i,slug,tid,n in cur.fetchall()}
    # Keep the exceptional conference as configured programme data, never a code path.
    conference_key=('global_crusade','young_adults_ministers_conference')
    if conference_key not in types:
        cur.execute("SELECT id FROM program_domains WHERE slug='global_crusade' AND is_deleted IS FALSE")
        domain_id=cur.fetchone()[0]
        cur.execute("""INSERT INTO program_types(domain_id,slug,name,description,created_at,last_modify,is_deleted,operation)
                    VALUES(%s,%s,%s,%s,now(),now(),false,'CREATE') RETURNING id""",
                    (domain_id,conference_key[1],"Young Adults and Ministers Conference",MARK))
        types[conference_key]={'id':cur.fetchone()[0],'name':'Young Adults and Ministers Conference'}
    cur.execute("SELECT id FROM program_domains WHERE slug=%s AND is_deleted IS FALSE",('weekly_programs',)); weekly_domain=cur.fetchone()[0]
    cur.execute("SELECT id FROM program_domains WHERE slug='retreat' AND is_deleted IS FALSE"); retreat_domain=cur.fetchone()[0]
    cur.execute("SELECT id FROM program_domains WHERE slug='global_crusade' AND is_deleted IS FALSE"); crusade_domain=cur.fetchone()[0]
    domain_name={'weekly_programs':'Weekly Programs','retreat':'Retreat','global_crusade':'Global Crusade'}
    type_slugs={
      'sunday_worship_service':('weekly_programs','Sunday Worship Service'),
      'monday_bible_study':('weekly_programs','Monday Bible Study'),
      'thursday_revival_hour':('weekly_programs','Thursday Revival Hour'),
      'saturday_workers_meeting':('weekly_programs','Saturday Workers Meeting'),
      'tuesday_leaders_meeting':('weekly_programs','Tuesday Leaders Meeting'),
    }
    for slug,(dom,label) in type_slugs.items():
        if (dom,slug) not in types: raise RuntimeError(f"Required configured program type missing: {slug}")
    weekly=[]
    for label, weekday, slug in [('Sunday Worship',6,'sunday_worship_service'),('Monday Bible Study',0,'monday_bible_study'),('Thursday Revival Hour',3,'thursday_revival_hour')]:
        # Four recent completed occurrences, ending before today.
        d=date(2026,11,16)
        while d.weekday()!=weekday: d-=timedelta(days=1)
        for w in range(4): weekly.append((label,slug,d-timedelta(days=7*w)))
    meetings=[]
    for label,weekday,slug in [('Workers Meeting',5,'saturday_workers_meeting'),('Leaders Meeting',1,'tuesday_leaders_meeting')]:
        d=date(2026,11,17)
        while d.weekday()!=weekday: d-=timedelta(days=1)
        for w in range(4): meetings.append((label,slug,d-timedelta(days=7*w)))
    now=datetime.now(timezone.utc)
    counts=events=offers=attendance_subs=attendance_rows=assignments=0
    event_by_id={}
    count_group_ids={}
    def ensure_count_group(loc,domain_slug,type_slug,day,event_id,scope_path):
        key=f"{loc['id']}:{domain_slug}:{type_slug}:{day.isoformat()}:{event_id or 'none'}:main"
        if key in count_group_ids: return count_group_ids[key]
        gid=str(uuid.uuid4())
        program_key=types[(domain_slug,type_slug)].get('id') or type_slug
        cur.execute("""INSERT INTO count_groups(id,group_key,location_id,program_type_key,occurrence_date,
            reporting_scope_path,service_id,count_mode,state,created_at,last_modify)
            VALUES(%s,%s,%s,%s,%s,%s,'main','single','complete',now(),now())""",
            (gid,key,loc['id'],str(program_key),day,scope_path or loc['path']))
        count_group_ids[key]=gid
        return gid
    def reporting_midnight(day):
        return datetime.combine(day,time.min,LAGOS).astimezone(timezone.utc)
    def add_event(type_slug,domain_slug,path,day,title,*,campaign_id=None,mode='regular',scope='location',alpha=None,creator=None,approval='approved'):
        nonlocal events
        eid=str(uuid.uuid4()); type_id=types[(domain_slug,type_slug)]['id']
        cur.execute("""INSERT INTO program_events(id,program_type_id,campaign_id,path,date,title,is_public,published_at,
            event_mode,reporting_scope,campaign_code,alpha_location_id,is_alpha_event,approval_status,created_by_id,
            approved_by_id,approved_at,approval_note,created_at,last_modify,is_deleted,operation)
            VALUES(%s,%s,%s,%s::ltree,%s,%s,false,NULL,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),now(),false,'CREATE')""",
            (eid,type_id,campaign_id,path,day,f"{title} [{MARK}]",mode,scope,f"{MARK}:{campaign_id or 'weekly'}",alpha,
             bool(alpha),approval,creator or state_pastor,state_pastor if approval=='approved' else None,
             now if approval=='approved' else None,MARK if approval=='pending' else None))
        events+=1; return eid
    def add_count(eid,loc,domain_slug,type_slug,day,total,source='regular',scope_path=None,level='Local',status='approved'):
        nonlocal counts
        domid={'weekly_programs':weekly_domain,'retreat':retreat_domain,'global_crusade':crusade_domain}[domain_slug]
        t=types[(domain_slug,type_slug)]; vals=[int(total*.32),int(total*.31),int(total*.12),int(total*.13),int(total*.07),total-int(total*.32)-int(total*.31)-int(total*.12)-int(total*.13)-int(total*.07)]
        dt=reporting_midnight(day)
        group_id=ensure_count_group(loc,domain_slug,type_slug,day,eid,scope_path)
        cur.execute("""INSERT INTO counts(id,client_id,path,location_id,date,event_id,church_type,program_level,
            program_domain_id,program_type_id,program_scope_path,program_domain,program_type,count_group_id,adult_male,adult_female,
            youth_male,youth_female,boys,girls,total,count_mode,status,note,source_role,submission_channel,
            entered_by_id,created_at,last_modify,is_deleted,operation,auto_accepted)
            VALUES(%s,%s,%s::ltree,%s,%s,%s,%s,%s,%s,%s,%s::ltree,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'single',%s,%s,%s,'admin_web',%s,now(),now(),false,'CREATE',false)""",
            (str(uuid.uuid4()),str(uuid.uuid4()),loc['path'],loc['id'],dt,eid,loc['church'],level,domid,t['id'],scope_path or loc['path'],
             domain_name[domain_slug],t['name'],group_id,*vals,total,status,f"{MARK} synthetic pilot count",source,
             user('Location Admin',loc['path'])))
        counts+=1
    def add_offer(eid,loc,domain_slug,type_slug,day,kind,amount,status='approved'):
        nonlocal offers
        domid={'weekly_programs':weekly_domain,'retreat':retreat_domain,'global_crusade':crusade_domain}[domain_slug]
        t=types[(domain_slug,type_slug)]; dt=reporting_midnight(day)
        cur.execute("""INSERT INTO offerings(id,client_id,path,location_id,date,event_id,church_type,program_level,
            program_domain_id,program_type_id,program_scope_path,program_domain,program_type,amount,payment_method,
            fund_type,status,note,entered_by_id,created_at,last_modify,is_deleted,operation)
            VALUES(%s,%s,%s::ltree,%s,%s,%s,%s,'Local',%s,%s,%s::ltree,%s,%s,%s,'cash',%s,%s,%s,%s,now(),now(),false,'CREATE')""",
            (str(uuid.uuid4()),str(uuid.uuid4()),loc['path'],loc['id'],dt,eid,loc['church'],domid,t['id'],loc['path'],
             domain_name[domain_slug],t['name'],Decimal(str(amount)),kind,status,f"{MARK} synthetic pilot giving",user('Location Admin',loc['path'])))
        offers+=1
    # Weekly counts and one paired tithe/offering collection per occurrence.
    for label,slug,day in weekly:
        for idx,loc in enumerate(sample_locations):
            if loc['opened'] and loc['opened']>day or loc['closed'] and loc['closed']<=day: continue
            eid=add_event(slug,'weekly_programs',loc['path'],day,label,creator=user('Location Admin',loc['path']))
            total=140+((idx*19+day.day*7)%180)
            status='pending' if label=='Thursday Revival Hour' and idx==1 else 'approved'
            add_count(eid,loc,'weekly_programs',slug,day,total,status=status)
            if slug in {'sunday_worship_service','monday_bible_study','thursday_revival_hour'}:
                add_offer(eid,loc,'weekly_programs',slug,day,'tithe',Decimal(4000+idx*250))
                add_offer(eid,loc,'weekly_programs',slug,day,'offering',Decimal(6500+idx*300))
    # Worker and leaders meeting rosters are marked against each location's active approved workers.
    cur.execute("""SELECT worker_id::text,location_id::text,name,phone,unit,path::text FROM workers
        WHERE path::ltree <@ %s::ltree AND is_deleted IS FALSE AND status='Active'
          AND approval_status='approved' ORDER BY path,name""",(state_path,))
    workers=cur.fetchall(); by_location={}
    for w in workers: by_location.setdefault(w[1],[]).append(w)
    for label,slug,day in meetings:
      for loc in sample_locations:
        roster=by_location.get(loc['id'],[])
        if not roster: continue
        eid=add_event(slug,'weekly_programs',loc['path'],day,label,creator=user('Location Admin',loc['path']))
        present=roster[:max(1,(len(roster)*3+3)//4)]
        sid=str(uuid.uuid4()); submitted_by=present[0]
        dt=reporting_midnight(day)
        present_json=[{'worker_id':w[0],'worker_name':w[2]} for w in present]
        expected_ids=[w[0] for w in roster]
        cur.execute("""INSERT INTO worker_attendance_submissions(id,client_id,path,location_id,event_id,date,church_type,
            program_level,program_domain_id,program_type_id,program_scope_path,program_domain,program_type,
            expected_workers_count,expected_worker_ids,present_count,present_workers,entered_by_id,
            submitted_by_worker_id,submitted_by_name,note,created_at,last_modify,is_deleted,operation)
            VALUES(%s,%s,%s::ltree,%s,%s,%s,%s,'Local',%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb,%s,%s,%s,%s,now(),now(),false,'CREATE')""",
            (sid,str(uuid.uuid4()),loc['path'],loc['id'],eid,dt,loc['church'],weekly_domain,types[('weekly_programs',slug)]['id'],loc['path'],
             domain_name['weekly_programs'],types[('weekly_programs',slug)]['name'],len(roster),__import__('json').dumps(expected_ids),len(present),
             __import__('json').dumps(present_json),user('Location Admin',loc['path']),submitted_by[0],submitted_by[2],f'{MARK} synthetic roster capture'))
        attendance_subs+=1
        for j,w in enumerate(roster):
            cur.execute("""INSERT INTO worker_attendance(id,client_id,path,location_id,event_id,date,church_type,program_level,
              program_domain_id,program_type_id,program_scope_path,program_domain,program_type,worker_id,worker_name,worker_phone,
              worker_unit,status,note,submission_id,entered_by_id,created_at,last_modify,is_deleted,operation)
              VALUES(%s,%s,%s::ltree,%s,%s,%s,%s,'Local',%s,%s,%s::ltree,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),now(),false,'CREATE')""",
              (str(uuid.uuid4()),str(uuid.uuid4()),loc['path'],loc['id'],eid,dt,loc['church'],weekly_domain,types[('weekly_programs',slug)]['id'],
               loc['path'],domain_name['weekly_programs'],types[('weekly_programs',slug)]['name'],w[0],w[2],w[3],w[4],
               'present' if w in present else 'absent',f'{MARK} synthetic roster capture',sid,user('Location Admin',loc['path'])))
            attendance_rows+=1
    # Host-level Retreats: a six-day regional Easter and a six-day group December event.
    retreat_session_types=[(slug,row) for (dom,slug),row in types.items() if dom=='retreat' and slug not in {'easter_retreat','december_retreat'}]
    if not retreat_session_types: raise RuntimeError('No configured Retreat session types are available.')
    ilorin=next((r for r in regions if r['name']=='Ilorin Region'),regions[0])
    easter_start=date(2026,4,1); dec_start=date(2026,12,2)
    def add_campaign(domain_id,path,code,title,mode,scope,start,end,alpha=None,status='closed'):
        cid=str(uuid.uuid4()); window_start=datetime.combine(start,time.min,LAGOS); window_end=datetime.combine(end+timedelta(days=1),time.min,LAGOS)
        cur.execute("""INSERT INTO program_campaigns(id,domain_id,path,campaign_code,title,description,
          event_mode,reporting_scope,status,alpha_location_id,start_date,end_date,collection_window_start,
          collection_window_end,created_by_id,created_at,last_modify,is_deleted,operation)
          VALUES(%s,%s,%s::ltree,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),now(),false,'CREATE') RETURNING id""",
          (cid,domain_id,path,f'{MARK}:{code}',f'{title} [{MARK}]',f'{MARK} synthetic pilot campaign',mode,scope,status,alpha,start,end,window_start,window_end,state_pastor))
        return cid
    easter=add_campaign(retreat_domain,ilorin['path'],'easter-2026','Easter Retreat 2026','retreat','region',easter_start,easter_start+timedelta(days=5))
    target_group=next((g for g in groups if g['name']=='Ilorin East Group'),None)
    if not target_group: raise RuntimeError('Ilorin East Group is required for December pilot fixture.')
    group_loc=next((l for l in locations if l['group_path']==target_group['path']),None)
    if not group_loc: raise RuntimeError('Ilorin East Group requires a host location for the group-level count records.')
    december=add_campaign(retreat_domain,target_group['path'],'december-2026','December Retreat 2026','retreat','group',dec_start,dec_start+timedelta(days=5),status='active')
    for cid,start,host_path,host_loc,level,scope,label in [
      (easter,easter_start,ilorin['path'],next(l for l in locations if l['region_path']==ilorin['path']),'Region','region','Easter Retreat'),
      (december,dec_start,target_group['path'],group_loc,'Group','group','December Retreat')]:
      for di in range(6):
        day=start+timedelta(days=di)
        for slug,row in retreat_session_types:
          eid=add_event(slug,'retreat',host_path,day,f'{label} Day {di+1}: {row["name"]}',campaign_id=cid,mode='retreat',scope=scope,creator=state_pastor)
          add_count(eid,host_loc,'retreat',slug,day,600+di*47+len(slug)*3,scope_path=host_path,level=level)
    # Six-day November Global Crusade, Kwara alpha plus all active satellite locations.
    crusade_start=date(2026,11,4); crusade_end=date(2026,11,9)
    campaign=add_campaign(crusade_domain,state_path,'november-crusade','November 2026 Global Crusade','crusade','state',crusade_start,crusade_end,alpha['id'],'closed')
    crusade_sessions=[]
    for di in range(6):
      day=crusade_start+timedelta(days=di)
      scheduled=[('crusade_evening','Global Crusade Evening')]
      if di in {1,2,5}: scheduled.append(('young_adults_ministers_conference','Young Adults and Ministers Conference'))
      if di==3: scheduled.append(('impact_academy','Impact Academy'))
      if di==4: scheduled.append(('global_sunday','Global Sunday Worship'))
      for slug,title in scheduled:
        eid=add_event(slug,'global_crusade',state_path,day,title,campaign_id=campaign,mode='crusade',scope='state',alpha=alpha['id'],creator=state_pastor)
        crusade_sessions.append((eid,slug,day,title))
        add_count(eid,alpha,'global_crusade',slug,day,2800+di*117,source='alpha',scope_path=state_path,level='State')
        for ix,loc in enumerate(locations):
          if loc['id']==alpha['id'] or (ix+di)%11==0: continue
          add_count(eid,loc,'global_crusade',slug,day,130+(ix*13+di*17)%410,source='satellite',scope_path=loc['path'])
        if slug in {'crusade_evening','global_sunday'}:
          satellite=loc
          sources=[(alpha,'alpha',state_path,'State'),(satellite,'satellite',satellite['path'],'Local')]
          for record_location,source_role,record_scope,level in sources:
            for rec_type,person in [('newcomer','Synthetic Newcomer'),('convert','Synthetic Convert')]:
              cur.execute("""INSERT INTO records(id,client_id,path,location_id,date,event_id,church_type,program_level,
                program_domain_id,program_type_id,program_scope_path,program_domain,program_type,record_type,name,gender,phone,
                details,status,note,source_role,submission_channel,entered_by_id,created_at,last_modify,is_deleted,operation)
                VALUES(%s,%s,%s::ltree,%s,%s,%s,%s,%s,%s,%s,%s::ltree,'Global Crusade',%s,%s,%s,'unknown',%s,
                '{}'::jsonb,'approved',%s,%s,'admin_web',%s,now(),now(),false,'CREATE')""",
                (str(uuid.uuid4()),str(uuid.uuid4()),record_location['path'],record_location['id'],reporting_midnight(day),eid,
                 record_location['church'],level,crusade_domain,types[('global_crusade',slug)]['id'],record_scope,types[('global_crusade',slug)]['name'],rec_type,person,
                 f'{MARK}-{uuid.uuid4().hex[:6]}',f'{MARK} synthetic {source_role} {rec_type}',source_role,
                 user('State Admin',state_path) if source_role=='alpha' else user('Location Admin',record_location['path'])))
    # One approved and one pending event assignment per crusade session at sample locations.
    cur.execute("""SELECT w.worker_id::text,w.location_id::text,w.path::text FROM workers w
      WHERE w.path::ltree <@ %s::ltree AND w.is_deleted IS FALSE AND w.status='Active'
      AND w.approval_status='approved' ORDER BY w.path,w.name""",(state_path,))
    worker_rows=cur.fetchall(); worker_at={}
    for wid,lid,path in worker_rows: worker_at.setdefault(lid,[]).append((wid,path))
    for eid,slug,day,title in crusade_sessions:
      for loc,source in [(alpha,'alpha'),(next((l for l in locations if l['id']!=alpha['id']),alpha),'satellite')]:
        roster=worker_at.get(loc['id'],[])
        if not roster: continue
        wid,_=roster[0]; aid=str(uuid.uuid4()); creator=user('State Admin',state_path)
        cur.execute("""INSERT INTO event_assignments(id,event_id,worker_id,path,assignment_label,assignment_type,source_role,
          status,note,assigned_by_id,approved_by_id,approved_at,submission_completed,created_at,last_modify,is_deleted,operation)
          VALUES(%s,%s,%s,%s::ltree,%s,'both',%s,'approved',%s,%s,%s,now(),false,now(),now(),false,'CREATE')""",
          (aid,eid,wid,loc['path'],f'{source.title()} counting team',source,f'{MARK} assigned synthetic pilot usher',creator,state_pastor))
        assignments+=1
    # A scoped public report and a scoped in-app broadcast for communication checks.
    cur.execute("""INSERT INTO announcements(id,region_id,region_name,meeting,date,revival_topic,revival_info,
      general_announcements,is_active,published_at,path,created_at,last_modify)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,true,now(),%s::ltree,now(),now())""",
      (str(uuid.uuid4()),ilorin['id'],ilorin['name'],'Pilot Week',date(2026,11,17),'Pilot gathering',
       f'{MARK} Synthetic pilot notice',f'{MARK} Synthetic announcement; no real church directive.',ilorin['path']))
    cur.execute("""INSERT INTO broadcast_messages(id,sender_id,sender_role_score,target_level,audience,title,content,priority,
      sent_at,is_active,path,created_at,last_modify) VALUES(%s,%s,'5','state','all_users',%s,%s,'normal',now(),true,%s::ltree,now(),now())""",
      (str(uuid.uuid4()),state_pastor,f'{MARK} Kwara pilot message',f'{MARK} Synthetic test message; not a real directive.',state_path))
    # Keep a pending transfer workflow attached only to a synthetic worker.
    cur.execute("""SELECT w.worker_id::text,w.location_id::text,w.path::text FROM workers w
      WHERE w.path::ltree <@ %s::ltree AND w.is_deleted IS FALSE AND w.status='Active'
      AND w.approval_status='approved' ORDER BY w.path LIMIT 1""",(target_group['path'],))
    source_real=cur.fetchone()
    destinations=[l for l in locations if l['group_path']==target_group['path'] and source_real and l['id']!=source_real[1]]
    transfers=0
    if source_real and destinations:
      source_loc=next(l for l in locations if l['id']==source_real[1]); dest=destinations[0]
      transfer_worker=str(uuid.uuid4())
      cur.execute("""INSERT INTO workers(worker_id,user_id,location_id,location_name,church_type,state,region,"group",
        name,gender,phone,email,address,unit,status,approval_status,approved_by,approved_at,path,created_at,last_modify,is_deleted,operation)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'Female',%s,%s,%s,'Ushering','Active','approved',%s,now(),%s::ltree,now(),now(),false,'CREATE')""",
        (transfer_worker,f'DEMO-{MARK}',source_loc['id'],source_loc['name'],source_loc['church'],state_name,source_loc['region'],source_loc['group'],
         f'Synthetic Transfer Worker [{MARK}]',f'+999{uuid.uuid4().int % 10**10:010d}',f'pilot.transfer.{MARK.lower()}@example.test',
         f'Synthetic test profile; {MARK}; do not contact',user('Location Pastor',source_loc['path']),source_loc['path']))
      cur.execute("""INSERT INTO transfer_requests(id,worker_id,from_location_id,to_location_id,status,reason,requested_by,
        created_at,last_modify,path,current_level,workflow_stage,reviews) VALUES(%s,%s,%s,%s,'pending',%s,%s,now(),now(),%s,3,'origin_group','[]'::jsonb)""",
        (str(uuid.uuid4()),transfer_worker,source_loc['id'],dest['id'],f'{MARK} synthetic pending transfer; pilot approval only',
         user('Location Pastor',source_loc['path']),source_loc['path']))
      transfers=1
    return {'state':state_name,'locations':len(locations),'population_estimates':len(locations),'weekly_occurrences':len(weekly),'events':events,'counts':counts,
       'giving_rows':offers,'meeting_submissions':attendance_subs,'meeting_worker_rows':attendance_rows,
       'crusade_assignments':assignments,'campaigns':3,'retreat_session_types':len(retreat_session_types),
       'crusade_sessions':len(crusade_sessions),'transfer_requests':transfers}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--apply',action='store_true')
    p.add_argument('--remove',action='store_true')
    p.add_argument('--confirm-pilot-write',default='')
    args=p.parse_args()
    if args.apply==args.remove: p.error('choose exactly one of --apply or --remove')
    require_ack(args)
    conn=connect()
    try:
      with conn:
        with conn.cursor() as cur:
          cur.execute("SELECT current_database(),current_user")
          print('Target database:',cur.fetchone())
          result=remove(cur) if args.remove else seed(cur)
      print(('Removed' if args.remove else 'Seeded')+f' {MARK}: {result}')
    finally: conn.close()


if __name__=='__main__': main()
