"""Persist the hierarchy scope of each program submission.

Revision ID: a4c29e81b705
Revises: 4e68a01bd527
Create Date: 2026-11-04
"""

from alembic import op
import sqlalchemy as sa

from app.models.core import LtreeType


revision = "a4c29e81b705"
down_revision = "4e68a01bd527"
branch_labels = None
depends_on = None

TABLES = ("counts", "offerings", "records", "worker_attendance", "worker_attendance_submissions")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("program_scope_path", LtreeType(), nullable=True))
        op.create_index(f"ix_{table}_program_scope_path", table, ["program_scope_path"])
        op.execute(sa.text(f"""
            UPDATE {table} s SET program_scope_path=e.path
              FROM program_events e
             WHERE s.event_id=e.id AND s.program_scope_path IS NULL
        """))
        op.execute(sa.text(f"UPDATE {table} SET program_scope_path=path WHERE program_scope_path IS NULL"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_index(f"ix_{table}_program_scope_path", table_name=table)
        op.drop_column(table, "program_scope_path")
