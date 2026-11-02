"""Allow routine field records without scheduled event and persist metadata.

Revision ID: 3f8a2c7d91e4
Revises: f12a9c6e4d31
Create Date: 2026-11-06
"""

from alembic import op
import sqlalchemy as sa


revision = "3f8a2c7d91e4"
down_revision = "f12a9c6e4d31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("counts", "offerings", "records", "worker_attendance"):
        op.add_column(table, sa.Column("church_type", sa.String(length=40), nullable=True))
        op.add_column(table, sa.Column("program_domain", sa.String(length=80), nullable=True))
        op.add_column(table, sa.Column("program_type", sa.String(length=120), nullable=True))
        op.create_index(f"ix_{table}_church_type", table, ["church_type"])
        op.create_index(f"ix_{table}_program_domain", table, ["program_domain"])
        op.create_index(f"ix_{table}_program_type", table, ["program_type"])

    op.alter_column("offerings", "event_id", existing_type=sa.UUID(), nullable=True)
    op.alter_column("worker_attendance", "event_id", existing_type=sa.UUID(), nullable=True)
    op.add_column("records", sa.Column("date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("worker_attendance", sa.Column("date", sa.DateTime(timezone=True), nullable=True))
    op.execute("""
        UPDATE records r SET date = COALESCE(e.date::timestamptz, r.created_at, now())
        FROM program_events e WHERE r.event_id = e.id AND r.date IS NULL
    """)
    op.execute("UPDATE records SET date = COALESCE(created_at, now()) WHERE date IS NULL")
    op.execute("""
        UPDATE worker_attendance wa SET date = COALESCE(e.date::timestamptz, wa.created_at, now())
        FROM program_events e WHERE wa.event_id = e.id AND wa.date IS NULL
    """)
    op.execute("UPDATE worker_attendance SET date = COALESCE(created_at, now()) WHERE date IS NULL")
    op.alter_column("records", "date", nullable=False)
    op.alter_column("worker_attendance", "date", nullable=False)
    op.create_index("ix_records_date", "records", ["date"])
    op.create_index("ix_worker_attendance_date", "worker_attendance", ["date"])
    op.create_index(
        "uq_worker_attendance_eventless_worker_day",
        "worker_attendance",
        ["location_id", "date", "worker_id"],
        unique=True,
        postgresql_where=sa.text("event_id IS NULL AND is_deleted = FALSE"),
    )

    op.add_column("fellowship_members", sa.Column("fellowship_group", sa.String(length=30), nullable=True))
    op.create_index("ix_fellowship_members_fellowship_group", "fellowship_members", ["fellowship_group"])
    op.create_check_constraint(
        "ck_fellowship_members_group",
        "fellowship_members",
        "fellowship_group IS NULL OR fellowship_group IN ('adult', 'young_adult', 'campus', 'youth', 'children')",
    )
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_attendance_trends")
    op.execute("""
        CREATE MATERIALIZED VIEW mv_attendance_trends AS
        SELECT date_trunc('week', wa.date) AS week,
               wa.location_id, l.location_name, wa.path::ltree AS path, wa.status,
               COUNT(*) AS worker_count
        FROM worker_attendance wa
        JOIN locations l ON l.location_id = wa.location_id
        WHERE wa.is_deleted = FALSE
        GROUP BY date_trunc('week', wa.date), wa.location_id, l.location_name,
                 wa.path::ltree, wa.status
    """)
    op.create_index("ux_mv_attendance_trends", "mv_attendance_trends", ["week", "location_id", "path", "status"], unique=True)


def downgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM counts WHERE event_id IS NULL)
               OR EXISTS (SELECT 1 FROM offerings WHERE event_id IS NULL)
               OR EXISTS (SELECT 1 FROM records WHERE event_id IS NULL)
               OR EXISTS (SELECT 1 FROM worker_attendance WHERE event_id IS NULL) THEN
                RAISE EXCEPTION 'Cannot downgrade while eventless field records exist';
            END IF;
        END $$;
    """)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_attendance_trends")
    op.execute("""
        CREATE MATERIALIZED VIEW mv_attendance_trends AS
        SELECT date_trunc('week', e.date::timestamp) AS week,
               wa.location_id, l.location_name, wa.path::ltree AS path, wa.status,
               COUNT(*) AS worker_count
        FROM worker_attendance wa
        JOIN program_events e ON e.id = wa.event_id
        JOIN locations l ON l.location_id = wa.location_id
        WHERE wa.is_deleted = FALSE AND e.is_deleted = FALSE
        GROUP BY date_trunc('week', e.date::timestamp), wa.location_id,
                 l.location_name, wa.path::ltree, wa.status
    """)
    op.create_index("ux_mv_attendance_trends", "mv_attendance_trends", ["week", "location_id", "path", "status"], unique=True)
    op.drop_constraint("ck_fellowship_members_group", "fellowship_members", type_="check")
    op.drop_index("ix_fellowship_members_fellowship_group", table_name="fellowship_members")
    op.drop_column("fellowship_members", "fellowship_group")
    op.drop_index("ix_records_date", table_name="records")
    op.drop_index("ix_worker_attendance_date", table_name="worker_attendance")
    op.drop_index("uq_worker_attendance_eventless_worker_day", table_name="worker_attendance")
    op.drop_column("records", "date")
    op.drop_column("worker_attendance", "date")
    op.alter_column("offerings", "event_id", existing_type=sa.UUID(), nullable=False)
    op.alter_column("worker_attendance", "event_id", existing_type=sa.UUID(), nullable=False)
    for table in ("counts", "offerings", "records", "worker_attendance"):
        for column in ("church_type", "program_domain", "program_type"):
            op.drop_index(f"ix_{table}_{column}", table_name=table)
            op.drop_column(table, column)
