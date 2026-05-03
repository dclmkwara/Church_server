"""add_notification_read_states

Revision ID: b8c1d2e3f4a5
Revises: 9f0d0e1a2b3c
Create Date: 2026-03-30 10:15:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "b8c1d2e3f4a5"
down_revision = "9f0d0e1a2b3c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_read_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_key", sa.String(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "notification_key", name="uq_notification_read_state_user_key"),
    )
    op.create_index(op.f("ix_notification_read_states_created_at"), "notification_read_states", ["created_at"], unique=False)
    op.create_index(op.f("ix_notification_read_states_notification_key"), "notification_read_states", ["notification_key"], unique=False)
    op.create_index(op.f("ix_notification_read_states_read_at"), "notification_read_states", ["read_at"], unique=False)
    op.create_index(op.f("ix_notification_read_states_user_id"), "notification_read_states", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notification_read_states_user_id"), table_name="notification_read_states")
    op.drop_index(op.f("ix_notification_read_states_read_at"), table_name="notification_read_states")
    op.drop_index(op.f("ix_notification_read_states_notification_key"), table_name="notification_read_states")
    op.drop_index(op.f("ix_notification_read_states_created_at"), table_name="notification_read_states")
    op.drop_table("notification_read_states")
