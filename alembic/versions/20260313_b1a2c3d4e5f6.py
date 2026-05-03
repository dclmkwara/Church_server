"""add worker approval fields

Revision ID: b1a2c3d4e5f6
Revises: f14fc281567e
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b1a2c3d4e5f6"
down_revision = "f14fc281567e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Column already exists due to partial failure
    # op.add_column(
    #     "workers",
    #     sa.Column("approval_status", sa.String(), nullable=False, server_default="approved"),
    # )
    op.add_column(
        "workers",
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "workers",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workers",
        sa.Column("rejection_reason", sa.String(), nullable=True),
    )
    op.create_index("ix_workers_approval_status", "workers", ["approval_status"])
    op.create_foreign_key(
        "fk_workers_approved_by_users",
        "workers",
        "users",
        ["approved_by"],
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_workers_approved_by_users", "workers", type_="foreignkey")
    op.drop_index("ix_workers_approval_status", table_name="workers")
    op.drop_column("workers", "rejection_reason")
    op.drop_column("workers", "approved_at")
    op.drop_column("workers", "approved_by")
    op.drop_column("workers", "approval_status")
