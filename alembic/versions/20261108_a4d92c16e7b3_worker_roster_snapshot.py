"""Add worker IDs to meeting roster snapshots for deduplicated attendance.

Revision ID: a4d92c16e7b3
Revises: e2b4c6d8f013
Create Date: 2026-11-08
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a4d92c16e7b3"
down_revision = "e2b4c6d8f013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "worker_attendance_submissions",
        sa.Column("expected_worker_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("worker_attendance_submissions", "expected_worker_ids")
