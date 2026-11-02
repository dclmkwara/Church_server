"""Keep report refresh restricted to pastor/overseer roles.

Revision ID: e01c4a8b6d20
Revises: d95e3f1a2b4c
Create Date: 2026-11-02
"""

from alembic import op
from sqlalchemy import text


revision = "e01c4a8b6d20"
down_revision = "d95e3f1a2b4c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text("""
        DELETE FROM role_permissions rp
        USING roles r, permissions p
        WHERE rp.role_id = r.id
          AND rp.permission_id = p.id
          AND r.role_name = 'State Admin'
          AND p.permission = 'reports:refresh'
    """))


def downgrade() -> None:
    # State Admin was intentionally not granted reports:refresh by the RBAC seed.
    pass
