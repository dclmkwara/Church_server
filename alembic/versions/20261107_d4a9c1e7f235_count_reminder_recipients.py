"""Store count reminders as recipient-specific, auditable records.

Revision ID: d4a9c1e7f235
Revises: c2e5a8f14b31
Create Date: 2026-11-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4a9c1e7f235"
down_revision = "c2e5a8f14b31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "count_reminder_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("reminder_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sent_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("occurrence_date", sa.Date(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["sent_by_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.location_id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_count_reminder_recipients_reminder_id", "count_reminder_recipients", ["reminder_id"])
    op.create_index("ix_count_reminder_location_day_sent", "count_reminder_recipients", ["location_id", "occurrence_date", "sent_at"])
    op.create_index("ix_count_reminder_recipient_sent", "count_reminder_recipients", ["recipient_user_id", "sent_at"])


def downgrade() -> None:
    op.drop_index("ix_count_reminder_recipient_sent", table_name="count_reminder_recipients")
    op.drop_index("ix_count_reminder_location_day_sent", table_name="count_reminder_recipients")
    op.drop_index("ix_count_reminder_recipients_reminder_id", table_name="count_reminder_recipients")
    op.drop_table("count_reminder_recipients")
