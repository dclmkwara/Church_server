"""Persist the submitting user for worker registrations.

Revision ID: e1f4c0b72a91
Revises: d9e3a70c18f4
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e1f4c0b72a91"
down_revision = "d9e3a70c18f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workers",
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_workers_created_by_users",
        "workers",
        "users",
        ["created_by"],
        ["user_id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_workers_created_by", "workers", ["created_by"])


def downgrade() -> None:
    op.drop_index("ix_workers_created_by", table_name="workers")
    op.drop_constraint("fk_workers_created_by_users", "workers", type_="foreignkey")
    op.drop_column("workers", "created_by")
