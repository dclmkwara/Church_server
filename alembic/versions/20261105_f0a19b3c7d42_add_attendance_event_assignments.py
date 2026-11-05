"""Persist event assignments on aggregate and individual worker attendance.

Revision ID: f0a19b3c7d42
Revises: e1f4c0b72a91
Create Date: 2026-11-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f0a19b3c7d42"
down_revision = "e1f4c0b72a91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("worker_attendance", "worker_attendance_submissions"):
        op.add_column(table, sa.Column("assignment_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_assignment_id",
            table,
            "event_assignments",
            ["assignment_id"],
            ["id"],
        )
        op.create_index(f"ix_{table}_assignment_id", table, ["assignment_id"])


def downgrade() -> None:
    for table in ("worker_attendance_submissions", "worker_attendance"):
        op.drop_index(f"ix_{table}_assignment_id", table_name=table)
        op.drop_constraint(f"fk_{table}_assignment_id", table, type_="foreignkey")
        op.drop_column(table, "assignment_id")
