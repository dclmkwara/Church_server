"""Grant scoped audit-log visibility to level 2-5 pastor roles.

Revision ID: d7a4c1e2f809
Revises: d71a9c4e2b60
Create Date: 2026-11-10
"""

from alembic import op
import sqlalchemy as sa

revision = "d7a4c1e2f809"
down_revision = "d71a9c4e2b60"
branch_labels = None
depends_on = None

PASTOR_ROLES = ("Location Pastor", "Group Pastor", "Region Pastor", "State Overseer")


def upgrade() -> None:
    bind = op.get_bind()
    permission_id = bind.execute(
        sa.text("SELECT id FROM permissions WHERE permission = 'system:read_audit_logs' AND NOT is_deleted")
    ).scalar_one_or_none()
    if permission_id is None:
        raise RuntimeError("Required permission system:read_audit_logs is missing")
    roles = bind.execute(
        sa.text("SELECT id, role_name FROM roles WHERE role_name = ANY(:roles) AND NOT is_deleted"),
        {"roles": list(PASTOR_ROLES)},
    ).all()
    found = {row.role_name for row in roles}
    if found != set(PASTOR_ROLES):
        raise RuntimeError(f"Expected pastor roles missing: {sorted(set(PASTOR_ROLES) - found)}")
    for row in roles:
        bind.execute(
            sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :permission_id) ON CONFLICT DO NOTHING"),
            {"role_id": row.id, "permission_id": permission_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM role_permissions rp USING roles r, permissions p "
            "WHERE rp.role_id = r.id AND rp.permission_id = p.id "
            "AND r.role_name = ANY(:roles) AND p.permission = 'system:read_audit_logs'"
        ),
        {"roles": list(PASTOR_ROLES)},
    )
