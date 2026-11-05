"""Add stable client IDs for offline worker candidate intake.

Revision ID: d9e3a70c18f4
Revises: c2138e4a6f90
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d9e3a70c18f4"
down_revision = "c2138e4a6f90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workers", sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index(
        "uq_workers_client_id",
        "workers",
        ["client_id"],
        unique=True,
        postgresql_where=sa.text("client_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_workers_client_id", table_name="workers")
    op.drop_column("workers", "client_id")
