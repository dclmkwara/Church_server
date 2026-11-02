"""Use ltree for the scoped daily count summary path.

Revision ID: b73c1d9e5f20
Revises: fa12c0e7d8b9
Create Date: 2026-11-04
"""

from alembic import op


revision = "b73c1d9e5f20"
down_revision = "fa12c0e7d8b9"
branch_labels = None
depends_on = None


def _create_view(path_expression: str) -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_counts_by_location")
    op.execute(f"""
        CREATE MATERIALIZED VIEW mv_daily_counts_by_location AS
        SELECT COALESCE(e.date, DATE(c.date)) AS day,
               COALESCE(c.event_id::text, '') AS event_id,
               COALESCE(e.title, 'Unassigned event') AS event_title,
               c.location_id, l.location_name, {path_expression} AS path,
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
                 c.location_id, l.location_name, {path_expression}
    """)
    op.create_index(
        "ux_mv_daily_counts_by_location", "mv_daily_counts_by_location",
        ["day", "event_id", "location_id", "path"], unique=True,
    )


def upgrade() -> None:
    _create_view("c.path::ltree")


def downgrade() -> None:
    _create_view("c.path::text")
