"""Grant group, region, and state administrators and pastors event assignment governance.

Revision ID: f4c1d8a6b203
Revises: f3e6b8c0d2a4
Create Date: 2026-11-05
"""

from alembic import op
import sqlalchemy as sa


revision = "f4c1d8a6b203"
down_revision = "f3e6b8c0d2a4"
branch_labels = None
depends_on = None


_GOVERNANCE_ROLES = (
    "Group Admin", "Group Pastor",
    "Region Admin", "Region Pastor",
    "State Admin", "State Overseer",
)


def upgrade() -> None:
    connection = op.get_bind()
    permissions = connection.execute(sa.text(
        "SELECT id, permission FROM permissions "
        "WHERE permission IN ('programs:assign_workers', 'programs:approve_assignments')"
    )).all()
    permission_ids = {row.permission: row.id for row in permissions}
    missing = {
        "programs:assign_workers", "programs:approve_assignments"
    } - permission_ids.keys()
    if missing:
        raise RuntimeError(f"Required event permission rows are missing: {sorted(missing)}")

    connection.execute(sa.text(
        "INSERT INTO role_permissions (role_id, permission_id) "
        "SELECT roles.id, permission.permission_id "
        "FROM roles CROSS JOIN (VALUES "
        "  (:assign_id), (:approve_id)"
        ") AS permission(permission_id) "
        "WHERE roles.role_name IN :role_names "
        "ON CONFLICT DO NOTHING"
    ).bindparams(sa.bindparam("role_names", expanding=True)), {
        "assign_id": permission_ids["programs:assign_workers"],
        "approve_id": permission_ids["programs:approve_assignments"],
        "role_names": list(_GOVERNANCE_ROLES),
    })


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text(
        "DELETE FROM role_permissions "
        "WHERE permission_id IN ("
        "  SELECT id FROM permissions "
        "  WHERE permission IN ('programs:assign_workers', 'programs:approve_assignments')"
        ") AND role_id IN (SELECT id FROM roles WHERE role_name IN :role_names)"
    ).bindparams(sa.bindparam("role_names", expanding=True)), {
        "role_names": list(_GOVERNANCE_ROLES),
    })
