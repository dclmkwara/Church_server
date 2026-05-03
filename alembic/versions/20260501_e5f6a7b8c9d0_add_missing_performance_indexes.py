"""add missing performance indexes

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-01 17:00:00.000000

Adds partial and full indexes on columns that appear in WHERE clauses across
analytics, report, and notification queries but had no dedicated index.

The indexes are created CONCURRENTLY so this migration does not lock tables in
production. Postgres requires concurrent index statements to run outside a
transaction, so Alembic executes them inside autocommit blocks.
"""

from alembic import op


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


INDEX_STATEMENTS = [
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_workers_approval_status
    ON workers(approval_status)
    WHERE is_deleted = false
    """,
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_workers_email
    ON workers(email)
    WHERE is_deleted = false
    """,
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_users_approval_status
    ON users(approval_status)
    """,
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_counts_date
    ON counts(date)
    WHERE is_deleted = false
    """,
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_counts_created_at
    ON counts(created_at)
    WHERE is_deleted = false
    """,
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_offerings_date
    ON offerings(date)
    WHERE is_deleted = false
    """,
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_worker_attendance_status
    ON worker_attendance(status)
    WHERE is_deleted = false
    """,
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_records_record_type
    ON records(record_type)
    WHERE is_deleted = false
    """,
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_church_members_status
    ON church_members(status)
    WHERE is_deleted = false
    """,
    """
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_announcements_is_active
    ON announcements(is_active)
    """,
]

INDEX_NAMES = [
    "ix_workers_approval_status",
    "ix_workers_email",
    "ix_users_approval_status",
    "ix_counts_date",
    "ix_counts_created_at",
    "ix_offerings_date",
    "ix_worker_attendance_status",
    "ix_records_record_type",
    "ix_church_members_status",
    "ix_announcements_is_active",
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for statement in INDEX_STATEMENTS:
            op.execute(statement)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for index_name in INDEX_NAMES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {index_name}")
