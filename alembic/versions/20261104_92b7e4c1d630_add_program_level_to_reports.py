"""Persist the reporting level selected for program submissions.

Revision ID: 92b7e4c1d630
Revises: 6a9c2e1f4b70
Create Date: 2026-11-04
"""

from alembic import op
import sqlalchemy as sa


revision = "92b7e4c1d630"
down_revision = "6a9c2e1f4b70"
branch_labels = None
depends_on = None


REPORT_TABLES = (
    "counts",
    "offerings",
    "records",
    "worker_attendance",
    "worker_attendance_submissions",
)


def upgrade() -> None:
    for table in REPORT_TABLES:
        op.add_column(table, sa.Column("program_level", sa.String(length=20), nullable=True))
        op.create_index(f"ix_{table}_program_level", table, ["program_level"])


def downgrade() -> None:
    for table in reversed(REPORT_TABLES):
        op.drop_index(f"ix_{table}_program_level", table_name=table)
        op.drop_column(table, "program_level")
