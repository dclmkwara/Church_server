"""Preserve event grain in population count summaries.

Revision ID: fa12c0e7d8b9
Revises: e41a8b9c7d6f
Create Date: 2026-11-03
"""

from alembic import op


revision = "fa12c0e7d8b9"
down_revision = "e41a8b9c7d6f"
branch_labels = None
depends_on = None


def _create_daily_count_view() -> None:
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
        GROUP BY COALESCE(e.date, DATE(c.date)),
                 COALESCE(c.event_id::text, ''),
                 COALESCE(e.title, 'Unassigned event'),
                 c.location_id, l.location_name, c.path::ltree
    """)
    op.create_index(
        "ux_mv_daily_counts_by_location", "mv_daily_counts_by_location",
        ["day", "event_id", "location_id", "path"], unique=True,
    )


def upgrade() -> None:
    _create_daily_count_view()


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_counts_by_location")
    op.execute("""
        CREATE MATERIALIZED VIEW mv_daily_counts_by_location AS
        SELECT DATE(c.date) AS day, c.location_id, l.location_name, c.path,
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
        WHERE c.is_deleted = FALSE
        GROUP BY DATE(c.date), c.location_id, l.location_name, c.path
    """)
    op.create_index(
        "ux_mv_daily_counts_by_location", "mv_daily_counts_by_location",
        ["day", "location_id", "path"], unique=True,
    )
