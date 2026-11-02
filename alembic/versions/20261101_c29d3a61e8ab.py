"""add financial review and correction audit trail

Revision ID: c29d3a61e8ab
Revises: b18f2c6d9a40
Create Date: 2026-11-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "c29d3a61e8ab"
down_revision = "b18f2c6d9a40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        DECLARE invalid_rows bigint;
        BEGIN
            SELECT count(*) INTO invalid_rows FROM offerings
            WHERE status IS NULL OR status NOT IN ('pending', 'approved', 'rejected');
            IF invalid_rows > 0 THEN
                RAISE EXCEPTION 'Cannot enforce financial review states: % offering rows have unrecognized status values', invalid_rows;
            END IF;
        END $$;
    """)
    op.add_column("offerings", sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("offerings", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("offerings", sa.Column("review_note", sa.Text(), nullable=True))
    op.create_foreign_key("fk_offerings_reviewed_by_user", "offerings", "users", ["reviewed_by_id"], ["user_id"])
    op.create_index("ix_offerings_reviewed_by_id", "offerings", ["reviewed_by_id"])
    op.create_check_constraint(
        "ck_offerings_review_status",
        "offerings",
        "status IS NOT NULL AND status IN ('pending', 'approved', 'rejected')",
    )
    op.create_table(
        "offering_audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offering_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("before_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.user_id"], name="fk_offering_audits_actor_user"),
        sa.ForeignKeyConstraint(["offering_id"], ["offerings.id"], name="fk_offering_audits_offering"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("action IN ('corrected', 'approved', 'rejected', 'deleted')", name="ck_offering_audits_action"),
    )
    op.create_index("ix_offering_audits_offering_id", "offering_audits", ["offering_id"])
    op.create_index("ix_offering_audits_actor_id", "offering_audits", ["actor_id"])
    op.create_index("ix_offering_audits_action", "offering_audits", ["action"])


def downgrade() -> None:
    op.drop_index("ix_offering_audits_action", table_name="offering_audits")
    op.drop_index("ix_offering_audits_actor_id", table_name="offering_audits")
    op.drop_index("ix_offering_audits_offering_id", table_name="offering_audits")
    op.drop_table("offering_audits")
    op.drop_constraint("ck_offerings_review_status", "offerings", type_="check")
    op.drop_index("ix_offerings_reviewed_by_id", table_name="offerings")
    op.drop_constraint("fk_offerings_reviewed_by_user", "offerings", type_="foreignkey")
    op.drop_column("offerings", "review_note")
    op.drop_column("offerings", "reviewed_at")
    op.drop_column("offerings", "reviewed_by_id")
