"""Expose ltree paths on all scoped report materialized views.

Revision ID: c84d2f7a6b91
Revises: b73c1d9e5f20
Create Date: 2026-11-05
"""

from alembic import op


revision = "c84d2f7a6b91"
down_revision = "b73c1d9e5f20"
branch_labels = None
depends_on = None


def _rebuild_views() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_counts_by_location")
    op.execute("""
        CREATE MATERIALIZED VIEW mv_daily_counts_by_location AS
        SELECT COALESCE(e.date, DATE(c.date)) AS day,
               COALESCE(c.event_id::text, '') AS event_id,
               COALESCE(e.title, 'Unassigned event') AS event_title,
               c.location_id, l.location_name, c.path::ltree AS path,
               SUM(c.total) AS total_attendance,
               SUM(c.adult_male) AS total_men,
               SUM(c.adult_female) AS total_women,
               SUM(c.youth_male) AS total_youth_male,
               SUM(c.youth_female) AS total_youth_female,
               SUM(c.boys) AS total_boys,
               SUM(c.girls) AS total_girls,
               COUNT(*) AS record_count
        FROM counts c
        JOIN locations l ON l.location_id = c.location_id
        LEFT JOIN program_events e ON e.id = c.event_id AND e.is_deleted = FALSE
        WHERE c.is_deleted = FALSE
        GROUP BY COALESCE(e.date, DATE(c.date)), COALESCE(c.event_id::text, ''),
                 COALESCE(e.title, 'Unassigned event'), c.location_id,
                 l.location_name, c.path::ltree
    """)
    op.create_index("ux_mv_daily_counts_by_location", "mv_daily_counts_by_location", ["day", "event_id", "location_id", "path"], unique=True)

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_monthly_financial_summary")
    op.execute("""
        CREATE MATERIALIZED VIEW mv_monthly_financial_summary AS
        SELECT date_trunc('month', o.date) AS month, o.location_id,
               l.location_name, o.path::ltree AS path,
               COALESCE(SUM(o.amount), 0) AS total_amount,
               COUNT(*) AS transaction_count
        FROM offerings o
        JOIN locations l ON l.location_id = o.location_id
        WHERE o.is_deleted = FALSE AND o.status = 'approved'
        GROUP BY date_trunc('month', o.date), o.location_id, l.location_name, o.path::ltree
    """)
    op.create_index("ux_mv_monthly_financial_summary", "mv_monthly_financial_summary", ["month", "location_id", "path"], unique=True)

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


def upgrade() -> None:
    _rebuild_views()


def downgrade() -> None:
    # Scoped report queries require ltree containment; keep the compatible schema
    # if reverting application code while retaining this database revision.
    _rebuild_views()
