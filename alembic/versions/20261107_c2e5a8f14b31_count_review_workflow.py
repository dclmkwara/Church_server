"""Add count review, correction history, and scoped review permission.

Revision ID: c2e5a8f14b31
Revises: a71c3f9d2b40
Create Date: 2026-11-07
"""

from alembic import op
import sqlalchemy as sa


revision = "c2e5a8f14b31"
down_revision = "a71c3f9d2b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add auditable count decisions and grant review only to level pastors."""
    op.add_column("counts", sa.Column("approved_by_id", sa.UUID(), nullable=True))
    op.add_column("counts", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("counts", sa.Column("auto_accepted", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("counts", sa.Column("supersedes_id", sa.UUID(), nullable=True))
    op.add_column("counts", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column("counts", sa.Column("rejected_by_id", sa.UUID(), nullable=True))
    op.add_column("counts", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_counts_approved_by_id_users", "counts", "users", ["approved_by_id"], ["user_id"])
    op.create_foreign_key("fk_counts_supersedes_id_counts", "counts", "counts", ["supersedes_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_counts_rejected_by_id_users", "counts", "users", ["rejected_by_id"], ["user_id"])
    op.create_index("ix_counts_approved_by_id", "counts", ["approved_by_id"])
    op.create_index("ix_counts_auto_accepted", "counts", ["auto_accepted"])
    op.create_index("ix_counts_supersedes_id", "counts", ["supersedes_id"])
    op.create_index("ix_counts_rejected_by_id", "counts", ["rejected_by_id"])

    op.execute("""
        INSERT INTO permissions (permission, name, description, created_at, last_modify, is_deleted, operation)
        VALUES (
            'counts:review',
            'Review Program Counts',
            'Approve or reject count submissions within the assigned reporting level',
            now(), now(), false, 'CREATE'
        )
        ON CONFLICT (permission) DO NOTHING
    """)
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r CROSS JOIN permissions p
        WHERE r.role_name IN ('Group Pastor', 'Region Pastor', 'State Overseer')
          AND p.permission = 'counts:review'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    """Remove the review grants and fields; refuse to erase decision history."""
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM counts
                WHERE approved_by_id IS NOT NULL OR rejected_by_id IS NOT NULL
                   OR supersedes_id IS NOT NULL OR rejection_reason IS NOT NULL
                   OR rejected_at IS NOT NULL OR (auto_accepted IS TRUE)
            ) THEN
                RAISE EXCEPTION 'Count review history exists; restore the pre-B2 snapshot before downgrade';
            END IF;
        END $$;
    """)
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE permission = 'counts:review')")
    op.execute("DELETE FROM permissions WHERE permission = 'counts:review'")
    op.drop_index("ix_counts_rejected_by_id", table_name="counts")
    op.drop_index("ix_counts_supersedes_id", table_name="counts")
    op.drop_index("ix_counts_auto_accepted", table_name="counts")
    op.drop_index("ix_counts_approved_by_id", table_name="counts")
    op.drop_constraint("fk_counts_rejected_by_id_users", "counts", type_="foreignkey")
    op.drop_constraint("fk_counts_supersedes_id_counts", "counts", type_="foreignkey")
    op.drop_constraint("fk_counts_approved_by_id_users", "counts", type_="foreignkey")
    op.drop_column("counts", "rejected_at")
    op.drop_column("counts", "rejected_by_id")
    op.drop_column("counts", "rejection_reason")
    op.drop_column("counts", "supersedes_id")
    op.drop_column("counts", "auto_accepted")
    op.drop_column("counts", "approved_at")
    op.drop_column("counts", "approved_by_id")
