"""Seed the five mother domains and canonical lookup IDs on submissions.

Revision ID: 4e68a01bd527
Revises: 92b7e4c1d630
Create Date: 2026-11-04
"""

from alembic import op
import sqlalchemy as sa


revision = "4e68a01bd527"
down_revision = "92b7e4c1d630"
branch_labels = None
depends_on = None

TABLES = ("counts", "offerings", "records", "worker_attendance", "worker_attendance_submissions")
DOMAINS = {
    "global_crusade": "Global Crusade",
    "retreat": "Retreat",
    "weekly_programs": "Weekly Programs",
    "conferences": "Conferences",
    "special_programs": "Special Programs",
}
TYPES = {
    "sunday_worship_service": ("Sunday Worship Service", "weekly_programs"),
    "monday_bible_study": ("Monday Bible Study", "weekly_programs"),
    "tuesday_leaders_meeting": ("Tuesday Leaders Meeting", "weekly_programs"),
    "thursday_revival_hour": ("Thursday Revival Hour", "weekly_programs"),
    "saturday_workers_meeting": ("Saturday Workers Meeting", "weekly_programs"),
    "crusade_evening": ("Crusade Evening", "global_crusade"),
    "leadership_development": ("Leadership Development Meeting", "global_crusade"),
    "impact_academy": ("Impact Academy", "global_crusade"),
    "global_sunday": ("Global Sunday Service", "global_crusade"),
    "faith_clinic": ("Faith Clinic", "retreat"),
    "retreat_bible_study": ("Retreat Bible Study", "retreat"),
    "revival_session": ("Revival Session", "retreat"),
    "seminar": ("Seminar", "retreat"),
    "workers_conference": ("Workers Conference", "conferences"),
    "leaders_strategic_conference": ("Ministers and Leaders Strategic Conference", "conferences"),
    "youth_campus_conference": ("Youth and Campus Conference", "conferences"),
    "special_rally": ("Special Rally", "special_programs"),
    "solemn_assembly": ("Solemn Assembly", "special_programs"),
    "anniversary_celebration": ("Anniversary Celebration", "special_programs"),
}


def _domain_id(conn, slug):
    return conn.execute(sa.text("SELECT id FROM program_domains WHERE slug=:slug"), {"slug": slug}).scalar_one()


def upgrade() -> None:
    conn = op.get_bind()

    # Keep existing FK identities by renaming the old domain rows in place.
    for old_slug, canonical_slug, canonical_name in (
        ("regular_services", "weekly_programs", "Weekly Programs"),
        ("open_crusade", "global_crusade", "Global Crusade"),
    ):
        old_id = conn.execute(sa.text("SELECT id FROM program_domains WHERE slug=:slug"), {"slug": old_slug}).scalar()
        canonical_id = conn.execute(sa.text("SELECT id FROM program_domains WHERE slug=:slug"), {"slug": canonical_slug}).scalar()
        if old_id and not canonical_id:
            conn.execute(sa.text("UPDATE program_domains SET slug=:slug, name=:name WHERE id=:id"), {"slug": canonical_slug, "name": canonical_name, "id": old_id})
        elif old_id and canonical_id:
            conn.execute(sa.text("UPDATE program_types SET domain_id=:new WHERE domain_id=:old"), {"new": canonical_id, "old": old_id})
            conn.execute(sa.text("UPDATE program_campaigns SET domain_id=:new WHERE domain_id=:old"), {"new": canonical_id, "old": old_id})
            conn.execute(sa.text("DELETE FROM program_domains WHERE id=:id"), {"id": old_id})

    for slug, name in DOMAINS.items():
        row_id = conn.execute(sa.text("SELECT id FROM program_domains WHERE slug=:slug"), {"slug": slug}).scalar()
        if row_id is None:
            row_id = conn.execute(sa.text("INSERT INTO program_domains (slug,name,created_at,last_modify,is_deleted,operation) VALUES (:slug,:name,now(),now(),false,'CREATE') RETURNING id"), {"slug": slug, "name": name}).scalar_one()
        else:
            conn.execute(sa.text("UPDATE program_domains SET name=:name WHERE id=:id"), {"name": name, "id": row_id})

    # Merge the unused extra starter domain into the canonical Weekly Programs domain.
    weekly_id = _domain_id(conn, "weekly_programs")
    covenant_id = conn.execute(sa.text("SELECT id FROM program_domains WHERE slug='covenant_sunday'")).scalar()
    if covenant_id:
        conn.execute(sa.text("UPDATE program_types SET domain_id=:new WHERE domain_id=:old"), {"new": weekly_id, "old": covenant_id})
        conn.execute(sa.text("UPDATE program_campaigns SET domain_id=:new WHERE domain_id=:old"), {"new": weekly_id, "old": covenant_id})
        conn.execute(sa.text("DELETE FROM program_domains WHERE id=:id"), {"id": covenant_id})

    for slug, (name, domain_slug) in TYPES.items():
        domain_id = _domain_id(conn, domain_slug)
        type_id = conn.execute(sa.text("SELECT id FROM program_types WHERE slug=:slug"), {"slug": slug}).scalar()
        if type_id is None:
            conn.execute(sa.text("INSERT INTO program_types (slug,name,domain_id,created_at,last_modify,is_deleted,operation) VALUES (:slug,:name,:domain_id,now(),now(),false,'CREATE')"), {"slug": slug, "name": name, "domain_id": domain_id})
        else:
            conn.execute(sa.text("UPDATE program_types SET name=:name,domain_id=:domain_id WHERE id=:id"), {"name": name, "domain_id": domain_id, "id": type_id})

    for table in TABLES:
        op.add_column(table, sa.Column("program_domain_id", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("program_type_id", sa.Integer(), nullable=True))
        op.create_foreign_key(f"fk_{table}_program_domain", table, "program_domains", ["program_domain_id"], ["id"], ondelete="RESTRICT")
        op.create_foreign_key(f"fk_{table}_program_type", table, "program_types", ["program_type_id"], ["id"], ondelete="RESTRICT")
        op.create_index(f"ix_{table}_program_domain_id", table, ["program_domain_id"])
        op.create_index(f"ix_{table}_program_type_id", table, ["program_type_id"])
        op.execute(sa.text(f"""
            UPDATE {table} s
               SET program_type_id = e.program_type_id,
                   program_domain_id = t.domain_id
              FROM program_events e
              JOIN program_types t ON t.id=e.program_type_id
             WHERE s.event_id=e.id
        """))
        # Map legacy routine labels only where both values identify a seeded canonical type.
        op.execute(sa.text(f"""
            UPDATE {table} s
               SET program_domain_id=d.id, program_type_id=t.id
              FROM program_domains d, program_types t
             WHERE s.event_id IS NULL
               AND lower(trim(s.program_domain)) IN ('weekly','weekly programs','regular services')
               AND d.slug='weekly_programs' AND t.domain_id=d.id
               AND lower(trim(t.name)) = CASE lower(trim(s.program_type))
                   WHEN 'workers meeting' THEN 'saturday workers meeting'
                   WHEN 'thursday revival & training' THEN 'thursday revival hour'
                   ELSE lower(trim(s.program_type)) END
        """))
        op.execute(sa.text(f"""
            UPDATE {table} s
               SET program_domain_id=d.id, program_type_id=t.id
              FROM program_domains d, program_types t
             WHERE s.event_id IS NULL
               AND lower(trim(s.program_domain))='retreat'
               AND d.slug='retreat' AND t.domain_id=d.id
               AND lower(trim(t.name))=lower(trim(s.program_type))
        """))


def downgrade() -> None:
    raise RuntimeError("Canonical domain/type links and merged taxonomy must be reverted from a reviewed database snapshot.")
