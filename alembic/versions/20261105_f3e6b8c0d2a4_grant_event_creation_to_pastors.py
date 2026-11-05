"""Allow level pastors to schedule events with immediate same-level approval.

Revision ID: f3e6b8c0d2a4
Revises: f2c4a8d1e730
Create Date: 2026-11-05
"""

from alembic import op
import sqlalchemy as sa


revision = "f3e6b8c0d2a4"
down_revision = "f2c4a8d1e730"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    permission_id = connection.execute(sa.text(
        "SELECT id FROM permissions WHERE permission = 'programs:create_event'"
    )).scalar_one()
    connection.execute(sa.text(
        "INSERT INTO role_permissions (role_id, permission_id) "
        "SELECT roles.id, :permission_id FROM roles "
        "WHERE roles.role_name IN ('Location Pastor','Group Pastor','Region Pastor','State Overseer') "
        "ON CONFLICT DO NOTHING"
    ), {"permission_id": permission_id})


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE permission = 'programs:create_event') "
        "AND role_id IN (SELECT id FROM roles WHERE role_name IN "
        "('Location Pastor','Group Pastor','Region Pastor','State Overseer'))"
    ))
