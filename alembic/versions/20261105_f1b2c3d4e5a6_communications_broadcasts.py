"""Add structured weekly information and scoped broadcast messages.

Revision ID: f1b2c3d4e5a6
Revises: f0a19b3c7d42
Create Date: 2026-11-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.models.core import _LTREE


revision = "f1b2c3d4e5a6"
down_revision = "f0a19b3c7d42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, length in (
        ("sws_hymn", 255),
        ("mbs_topic", 255),
        ("revival_topic", 255),
    ):
        op.add_column("announcements", sa.Column(name, sa.String(length=length), nullable=True))
    for name in ("revival_info", "wedding_announcements", "general_announcements"):
        op.add_column("announcements", sa.Column(name, sa.Text(), nullable=True))

    op.create_table(
        "broadcast_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_role_score", sa.String(length=2), nullable=False),
        sa.Column("target_level", sa.String(length=20), nullable=False),
        sa.Column("audience", sa.String(length=20), server_default="all_users", nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=12), server_default="normal", nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("path", _LTREE(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["sender_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("target_level IN ('state','region','group','location')", name="ck_broadcast_target_level"),
        sa.CheckConstraint("audience IN ('all_users','pastors')", name="ck_broadcast_audience"),
        sa.CheckConstraint("priority IN ('low','normal','high')", name="ck_broadcast_priority"),
    )
    op.create_index("ix_broadcast_messages_sender_id", "broadcast_messages", ["sender_id"])
    op.create_index("ix_broadcast_messages_target_level", "broadcast_messages", ["target_level"])
    op.create_index("ix_broadcast_messages_audience", "broadcast_messages", ["audience"])
    op.create_index("ix_broadcast_messages_sent_at", "broadcast_messages", ["sent_at"])
    op.create_index("ix_broadcast_messages_is_active", "broadcast_messages", ["is_active"])
    op.create_index("ix_broadcast_messages_path", "broadcast_messages", ["path"], postgresql_using="gist")

    op.execute("ALTER TABLE public.broadcast_messages ENABLE ROW LEVEL SECURITY")
    scope = "NULLIF(current_setting('app.scope_path', true), '')::ltree"
    op.execute(
        "CREATE POLICY church_broadcast_read ON public.broadcast_messages "
        f"FOR SELECT TO PUBLIC USING ({scope} IS NOT NULL AND (path <@ {scope} OR {scope} <@ path))"
    )
    op.execute(
        "CREATE POLICY church_broadcast_write ON public.broadcast_messages "
        f"FOR ALL TO PUBLIC USING ({scope} IS NOT NULL AND path <@ {scope}) "
        f"WITH CHECK ({scope} IS NOT NULL AND path <@ {scope})"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS church_broadcast_write ON public.broadcast_messages")
    op.execute("DROP POLICY IF EXISTS church_broadcast_read ON public.broadcast_messages")
    op.drop_table("broadcast_messages")
    for name in ("general_announcements", "wedding_announcements", "revival_info", "revival_topic", "mbs_topic", "sws_hymn"):
        op.drop_column("announcements", name)
