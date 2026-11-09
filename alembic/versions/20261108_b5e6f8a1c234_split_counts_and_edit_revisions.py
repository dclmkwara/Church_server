"""Add split count groups and auditable submission revisions.

Revision ID: b5e6f8a1c234
Revises: a4d92c16e7b3
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b5e6f8a1c234"
down_revision = "a4d92c16e7b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "count_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("group_key", sa.String(255), nullable=False, unique=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("program_type_key", sa.String(120), nullable=False),
        sa.Column("occurrence_date", sa.Date(), nullable=False),
        sa.Column("reporting_scope_path", sa.String(), nullable=True),
        sa.Column("state", sa.String(12), nullable=False, server_default="open"),
        sa.Column("finalized_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("configured_zones", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_count_groups_group_key", "count_groups", ["group_key"], unique=True)
    op.create_index("ix_count_groups_location_id", "count_groups", ["location_id"])
    op.create_index("ix_count_groups_occurrence_date", "count_groups", ["occurrence_date"])
    op.create_index("ix_count_groups_state", "count_groups", ["state"])
    op.create_table(
        "submission_edit_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("submission_type", sa.String(40), nullable=False),
        sa.Column("submission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("edit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("editor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("before_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("after_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("submission_type", "submission_id", "edit_id", name="uq_submission_edit_id"),
        sa.UniqueConstraint("submission_type", "submission_id", "revision_no", name="uq_submission_revision_no"),
    )
    op.create_index("ix_submission_edit_revisions_type", "submission_edit_revisions", ["submission_type"])
    op.create_index("ix_submission_edit_revisions_submission", "submission_edit_revisions", ["submission_id"])
    op.create_index("ix_submission_edit_revisions_action", "submission_edit_revisions", ["action"])
    op.create_index("ix_submission_edit_revisions_editor", "submission_edit_revisions", ["editor_id"])
    op.create_index("ix_submission_edit_revisions_created", "submission_edit_revisions", ["created_at"])
    op.add_column("counts", sa.Column("count_mode", sa.String(12), nullable=True))
    op.add_column("counts", sa.Column("section_label", sa.String(120), nullable=True))
    op.add_column("counts", sa.Column("count_group_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_counts_count_group_id", "counts", "count_groups", ["count_group_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_counts_count_group_id", "counts", ["count_group_id"])
    op.execute("""
        UPDATE counts
        SET section_label = NULLIF(trim(substring(note from '^Section:\\s*([^|]+)')) , ''),
            count_mode = 'section'
        WHERE note ~* '^Section:' AND count_mode IS NULL
    """)


def downgrade() -> None:
    op.drop_index("ix_counts_count_group_id", table_name="counts")
    op.drop_constraint("fk_counts_count_group_id", "counts", type_="foreignkey")
    op.drop_column("counts", "count_group_id")
    op.drop_column("counts", "section_label")
    op.drop_column("counts", "count_mode")
    for name in (
        "ix_submission_edit_revisions_created", "ix_submission_edit_revisions_editor",
        "ix_submission_edit_revisions_action", "ix_submission_edit_revisions_submission",
        "ix_submission_edit_revisions_type",
    ):
        op.drop_index(name, table_name="submission_edit_revisions")
    op.drop_table("submission_edit_revisions")
    for name in ("ix_count_groups_state", "ix_count_groups_occurrence_date", "ix_count_groups_location_id", "ix_count_groups_group_key"):
        op.drop_index(name, table_name="count_groups")
    op.drop_table("count_groups")
