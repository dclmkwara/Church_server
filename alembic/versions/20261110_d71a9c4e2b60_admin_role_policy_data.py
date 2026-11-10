"""Reconcile scoped admin and pastor permissions with approved role policy.

Revision ID: d71a9c4e2b60
Revises: c6d7e8f9a012
Create Date: 2026-11-10
"""

from alembic import op
import sqlalchemy as sa


revision = "d71a9c4e2b60"
down_revision = "c6d7e8f9a012"
branch_labels = None
depends_on = None


NEW_PERMISSIONS = (
    (
        "population_estimates:manage",
        "Manage Documented Population",
        "Can manage versioned location-level population records within the assigned State",
    ),
    (
        "programs:approve_events",
        "Approve Program Events",
        "Can approve or reject event schedules at the assigned level",
    ),
    (
        "workers:request_changes",
        "Request Worker Changes",
        "Can prepare worker transfer, removal, and status-change requests",
    ),
)

GRANTS_TO_ADD = (
    ("Continental Admin", "counts:review"),
    ("Continental Admin", "population_estimates:manage"),
    ("Continental Admin", "programs:approve_events"),
    ("Continental Admin", "workers:request_changes"),
    ("Continental Overseer", "counts:review"),
    ("Continental Overseer", "population_estimates:manage"),
    ("Continental Overseer", "programs:approve_events"),
    ("Continental Overseer", "workers:request_changes"),
    ("Global Admin", "counts:review"),
    ("Global Admin", "population_estimates:manage"),
    ("Global Admin", "programs:approve_events"),
    ("Global Admin", "workers:request_changes"),
    ("Group Admin", "counts:remind"),
    ("Group Admin", "reports:read"),
    ("Group Admin", "statistics:read"),
    ("Group Admin", "workers:request_changes"),
    ("Group Pastor", "programs:approve_events"),
    ("Group Pastor", "workers:request_changes"),
    ("Location Admin", "counts:remind"),
    ("Location Admin", "reports:read"),
    ("Location Admin", "statistics:read"),
    ("Location Admin", "workers:request_changes"),
    ("Location Pastor", "counts:remind"),
    ("Location Pastor", "programs:approve_events"),
    ("Location Pastor", "workers:request_changes"),
    ("National Admin", "counts:review"),
    ("National Admin", "population_estimates:manage"),
    ("National Admin", "programs:approve_events"),
    ("National Admin", "workers:request_changes"),
    ("National Overseer", "counts:review"),
    ("National Overseer", "population_estimates:manage"),
    ("National Overseer", "programs:approve_events"),
    ("National Overseer", "workers:request_changes"),
    ("Region Admin", "counts:remind"),
    ("Region Admin", "reports:read"),
    ("Region Admin", "statistics:read"),
    ("Region Admin", "workers:request_changes"),
    ("Region Pastor", "programs:approve_events"),
    ("Region Pastor", "workers:request_changes"),
    ("State Admin", "counts:remind"),
    ("State Admin", "population_estimates:manage"),
    ("State Admin", "workers:request_changes"),
    ("State Overseer", "population_estimates:manage"),
    ("State Overseer", "programs:approve_events"),
    ("State Overseer", "workers:request_changes"),
    ("Zonal Coordinator", "counts:review"),
    ("Zonal Coordinator", "population_estimates:manage"),
    ("Zonal Coordinator", "programs:approve_events"),
    ("Zonal Coordinator", "workers:request_changes"),
)

GRANTS_TO_REMOVE = (
    ("Group Admin", "users:assign_roles"),
    ("Location Admin", "users:assign_roles"),
    ("Region Admin", "users:assign_roles"),
    ("State Admin", "users:assign_roles"),
)


def upgrade() -> None:
    bind = op.get_bind()
    identity = bind.execute(
        sa.text(
            "SELECT current_user, r.rolsuper, r.rolbypassrls "
            "FROM pg_roles AS r WHERE r.rolname = current_user"
        )
    ).one()
    if not (identity.rolsuper or identity.rolbypassrls):
        raise RuntimeError("RBAC data revision requires the privileged migration role")

    baseline = bind.execute(
        sa.text(
            "SELECT (SELECT count(*) FROM roles WHERE NOT is_deleted), "
            "(SELECT count(*) FROM permissions WHERE NOT is_deleted), "
            "(SELECT count(*) FROM role_permissions)"
        )
    ).one()
    if tuple(baseline) != (20, 82, 928):
        raise RuntimeError(
            f"Unexpected RBAC baseline {tuple(baseline)}; expected 20 roles, 82 permissions, 928 grants"
        )

    for permission, name, description in NEW_PERMISSIONS:
        bind.execute(
            sa.text(
                "INSERT INTO permissions (permission, name, description, is_deleted, operation) "
                "VALUES (:permission, :name, :description, false, 'CREATE') "
                "ON CONFLICT (permission) DO NOTHING"
            ),
            {"permission": permission, "name": name, "description": description},
        )

    for role_name, permission in GRANTS_TO_ADD:
        result = bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles AS r CROSS JOIN permissions AS p "
                "WHERE r.role_name = :role_name AND NOT r.is_deleted "
                "AND p.permission = :permission AND NOT p.is_deleted "
                "ON CONFLICT (role_id, permission_id) DO NOTHING"
            ),
            {"role_name": role_name, "permission": permission},
        )
        if result.rowcount != 1:
            raise RuntimeError(f"Expected to add grant {role_name} -> {permission}")

    for role_name, permission in GRANTS_TO_REMOVE:
        result = bind.execute(
            sa.text(
                "DELETE FROM role_permissions AS rp USING roles AS r, permissions AS p "
                "WHERE rp.role_id = r.id AND rp.permission_id = p.id "
                "AND r.role_name = :role_name AND p.permission = :permission"
            ),
            {"role_name": role_name, "permission": permission},
        )
        if result.rowcount != 1:
            raise RuntimeError(f"Expected to remove grant {role_name} -> {permission}")

    final_counts = bind.execute(
        sa.text(
            "SELECT (SELECT count(*) FROM roles WHERE NOT is_deleted), "
            "(SELECT count(*) FROM permissions WHERE NOT is_deleted), "
            "(SELECT count(*) FROM role_permissions)"
        )
    ).one()
    if tuple(final_counts) != (20, 85, 973):
        raise RuntimeError(
            f"Unexpected RBAC result {tuple(final_counts)}; expected 20 roles, 85 permissions, 973 grants"
        )


def downgrade() -> None:
    bind = op.get_bind()
    for role_name, permission in reversed(GRANTS_TO_REMOVE):
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles AS r CROSS JOIN permissions AS p "
                "WHERE r.role_name = :role_name AND p.permission = :permission "
                "ON CONFLICT (role_id, permission_id) DO NOTHING"
            ),
            {"role_name": role_name, "permission": permission},
        )
    for role_name, permission in reversed(GRANTS_TO_ADD):
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions AS rp USING roles AS r, permissions AS p "
                "WHERE rp.role_id = r.id AND rp.permission_id = p.id "
                "AND r.role_name = :role_name AND p.permission = :permission"
            ),
            {"role_name": role_name, "permission": permission},
        )
    for permission, _, _ in reversed(NEW_PERMISSIONS):
        bind.execute(
            sa.text(
                "DELETE FROM permissions AS p WHERE p.permission = :permission "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.permission_id = p.id)"
            ),
            {"permission": permission},
        )
