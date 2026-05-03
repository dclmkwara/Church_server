"""add_public_intake_and_visibility_flags

Revision ID: c9d2e3f4a5b6
Revises: b8c1d2e3f4a5
Create Date: 2026-03-30 11:10:00.000000+00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c9d2e3f4a5b6"
down_revision = "b8c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "public_contact_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_public_contact_submissions_created_at"), "public_contact_submissions", ["created_at"], unique=False)
    op.create_index(op.f("ix_public_contact_submissions_email"), "public_contact_submissions", ["email"], unique=False)
    op.create_index(op.f("ix_public_contact_submissions_subject"), "public_contact_submissions", ["subject"], unique=False)
    op.create_index(op.f("ix_public_contact_submissions_status"), "public_contact_submissions", ["status"], unique=False)

    op.create_table(
        "public_prayer_submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("is_urgent", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_public_prayer_submissions_created_at"), "public_prayer_submissions", ["created_at"], unique=False)
    op.create_index(op.f("ix_public_prayer_submissions_email"), "public_prayer_submissions", ["email"], unique=False)
    op.create_index(op.f("ix_public_prayer_submissions_is_urgent"), "public_prayer_submissions", ["is_urgent"], unique=False)
    op.create_index(op.f("ix_public_prayer_submissions_status"), "public_prayer_submissions", ["status"], unique=False)

    op.add_column("program_events", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("program_events", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_program_events_is_public"), "program_events", ["is_public"], unique=False)
    op.create_index(op.f("ix_program_events_published_at"), "program_events", ["published_at"], unique=False)

    op.add_column("media_galleries", sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("media_galleries", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_media_galleries_is_public"), "media_galleries", ["is_public"], unique=False)
    op.create_index(op.f("ix_media_galleries_published_at"), "media_galleries", ["published_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_media_galleries_published_at"), table_name="media_galleries")
    op.drop_index(op.f("ix_media_galleries_is_public"), table_name="media_galleries")
    op.drop_column("media_galleries", "published_at")
    op.drop_column("media_galleries", "is_public")

    op.drop_index(op.f("ix_program_events_published_at"), table_name="program_events")
    op.drop_index(op.f("ix_program_events_is_public"), table_name="program_events")
    op.drop_column("program_events", "published_at")
    op.drop_column("program_events", "is_public")

    op.drop_index(op.f("ix_public_prayer_submissions_status"), table_name="public_prayer_submissions")
    op.drop_index(op.f("ix_public_prayer_submissions_is_urgent"), table_name="public_prayer_submissions")
    op.drop_index(op.f("ix_public_prayer_submissions_email"), table_name="public_prayer_submissions")
    op.drop_index(op.f("ix_public_prayer_submissions_created_at"), table_name="public_prayer_submissions")
    op.drop_table("public_prayer_submissions")

    op.drop_index(op.f("ix_public_contact_submissions_status"), table_name="public_contact_submissions")
    op.drop_index(op.f("ix_public_contact_submissions_subject"), table_name="public_contact_submissions")
    op.drop_index(op.f("ix_public_contact_submissions_email"), table_name="public_contact_submissions")
    op.drop_index(op.f("ix_public_contact_submissions_created_at"), table_name="public_contact_submissions")
    op.drop_table("public_contact_submissions")
