"""Restore Region and State grants for fellowship hierarchy management.

Revision ID: f6b8d2a4c910
Revises: f5a7c9e1d3b2
Create Date: 2026-11-05
"""

from alembic import op
import sqlalchemy as sa


revision = "f6b8d2a4c910"
down_revision = "f5a7c9e1d3b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    permission_id = connection.execute(sa.text(
        "INSERT INTO permissions (permission, name, description, is_deleted, operation) "
        "VALUES ('hierarchy:create_fellowship', 'Create Fellowships', "
        "'Can create fellowships', false, 'CREATE') "
        "ON CONFLICT (permission) DO UPDATE SET name = EXCLUDED.name, "
        "description = EXCLUDED.description, is_deleted = false "
        "RETURNING id"
    )).scalar_one()
    connection.execute(sa.text(
        "INSERT INTO role_permissions (role_id, permission_id) "
        "SELECT id, :permission_id FROM roles "
        "WHERE role_name IN ('Region Admin', 'Region Pastor', 'State Admin', 'State Overseer') "
        "AND is_deleted = false ON CONFLICT DO NOTHING"
    ), {"permission_id": permission_id})


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text(
        "DELETE FROM role_permissions rp USING roles r, permissions p "
        "WHERE rp.role_id = r.id AND rp.permission_id = p.id "
        "AND r.role_name IN ('Region Admin', 'Region Pastor', 'State Admin', 'State Overseer') "
        "AND p.permission = 'hierarchy:create_fellowship'"
    ))
