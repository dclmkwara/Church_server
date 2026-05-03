"""Fix ltree columns and reporting materialized views

Revision ID: 9f0d0e1a2b3c
Revises: fead1055eafd
Create Date: 2026-03-21 18:30:00.000000+00:00
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "9f0d0e1a2b3c"
down_revision = "fead1055eafd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree")

    op.drop_index("ix_church_members_path", table_name="church_members")
    op.execute(
        """
        ALTER TABLE church_members
        ALTER COLUMN path TYPE LTREE
        USING path::ltree
        """
    )
    op.execute("CREATE INDEX ix_church_members_path ON church_members USING GIST (path)")

    op.drop_index("ix_worker_removal_requests_path", table_name="worker_removal_requests")
    op.execute(
        """
        ALTER TABLE worker_removal_requests
        ALTER COLUMN path TYPE LTREE
        USING path::ltree
        """
    )
    op.execute("CREATE INDEX ix_worker_removal_requests_path ON worker_removal_requests USING GIST (path)")

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_counts_by_location")
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_daily_counts_by_location AS
        SELECT
            DATE(c.date) AS day,
            c.location_id,
            l.location_name,
            c.path AS path,
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
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ux_mv_daily_counts_by_location
        ON mv_daily_counts_by_location (day, location_id)
        """
    )

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_monthly_financial_summary")
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_monthly_financial_summary AS
        SELECT
            date_trunc('month', o.date) AS month,
            o.location_id,
            l.location_name,
            o.path AS path,
            COALESCE(SUM(o.amount), 0)::float AS total_amount,
            COUNT(*) AS transaction_count
        FROM offerings o
        JOIN locations l ON l.location_id = o.location_id
        WHERE o.is_deleted = FALSE
        GROUP BY date_trunc('month', o.date), o.location_id, l.location_name, o.path
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ux_mv_monthly_financial_summary
        ON mv_monthly_financial_summary (month, location_id)
        """
    )

    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_attendance_trends")
    op.execute(
        """
        CREATE MATERIALIZED VIEW mv_attendance_trends AS
        SELECT
            date_trunc('week', wa.created_at) AS week,
            wa.location_id,
            l.location_name,
            wa.path AS path,
            wa.status,
            COUNT(*) AS worker_count
        FROM worker_attendance wa
        JOIN locations l ON l.location_id = wa.location_id
        WHERE wa.is_deleted = FALSE
        GROUP BY date_trunc('week', wa.created_at), wa.location_id, l.location_name, wa.path, wa.status
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX ux_mv_attendance_trends
        ON mv_attendance_trends (week, location_id, status)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ux_mv_attendance_trends")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_attendance_trends")

    op.execute("DROP INDEX IF EXISTS ux_mv_monthly_financial_summary")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_monthly_financial_summary")

    op.execute("DROP INDEX IF EXISTS ux_mv_daily_counts_by_location")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_counts_by_location")

    op.drop_index("ix_worker_removal_requests_path", table_name="worker_removal_requests")
    op.execute(
        """
        ALTER TABLE worker_removal_requests
        ALTER COLUMN path TYPE VARCHAR
        USING path::text
        """
    )
    op.create_index("ix_worker_removal_requests_path", "worker_removal_requests", ["path"], unique=False)

    op.drop_index("ix_church_members_path", table_name="church_members")
    op.execute(
        """
        ALTER TABLE church_members
        ALTER COLUMN path TYPE TEXT
        USING path::text
        """
    )
    op.create_index("ix_church_members_path", "church_members", ["path"], unique=False)
