"""Reserve direct worker removal for group leadership and above.

Revision ID: 6a9c2e1f4b70
Revises: 1c7d4e9a2f60
Create Date: 2026-11-04
"""

from alembic import op
import sqlalchemy as sa


revision = "6a9c2e1f4b70"
down_revision = "1c7d4e9a2f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        DELETE FROM role_permissions rp
        USING roles r, role_scores rs, permissions p
        WHERE rp.role_id = r.id
          AND r.score_id = rs.id
          AND rp.permission_id = p.id
          AND rs.score = 2
          AND p.permission = 'workers:delete'
    """))


def downgrade() -> None:
    raise RuntimeError("Restore the prior role permission grants from a reviewed database snapshot.")
