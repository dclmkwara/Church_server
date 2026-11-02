"""Grant scoped reporting reads to pastor roles at levels 3-5.

Revision ID: d95e3f1a2b4c
Revises: c84d2f7a6b91
Create Date: 2026-11-02
"""

from alembic import op
from sqlalchemy import text


revision = "d95e3f1a2b4c"
down_revision = "c84d2f7a6b91"
branch_labels = None
depends_on = None


REPORTING_ROLES = (
    "Location Pastor",
    "Group Pastor",
    "Region Pastor",
    "State Admin",
    "State Overseer",
    "National Admin",
    "National Overseer",
    "Continental Admin",
    "Continental Overseer",
    "Global Admin",
)


def upgrade() -> None:
    bind = op.get_bind()
    permissions = (
        ("reports:read", "Read Reports", "Can view reports"),
        ("reports:refresh", "Refresh Reports", "Can refresh report materializations"),
        ("statistics:read", "Read Statistics", "Can view statistics endpoints"),
    )
    for key, name, description in permissions:
        bind.execute(
            text("""
                INSERT INTO permissions (permission, name, description, is_deleted, operation)
                VALUES (:permission, :name, :description, FALSE, 'CREATE')
                ON CONFLICT (permission) DO UPDATE
                SET name = EXCLUDED.name,
                    description = EXCLUDED.description,
                    is_deleted = FALSE,
                    operation = 'UPDATE'
            """),
            {"permission": key, "name": name, "description": description},
        )

    bind.execute(
        text("""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id
            FROM roles AS r
            JOIN role_scores AS rs ON rs.id = r.score_id
            CROSS JOIN permissions AS p
            WHERE r.role_name = ANY(:role_names)
              AND r.is_deleted = FALSE
              AND rs.score >= 3
              AND p.permission = ANY(:permission_names)
              AND p.is_deleted = FALSE
            ON CONFLICT (role_id, permission_id) DO NOTHING
        """),
        {
            "role_names": list(REPORTING_ROLES),
            "permission_names": ["reports:read", "statistics:read", "reports:refresh"],
        },
    )


def downgrade() -> None:
    op.execute(text("""
        DELETE FROM role_permissions rp
        USING roles r, permissions p
        WHERE rp.role_id = r.id
          AND rp.permission_id = p.id
          AND r.role_name = ANY(ARRAY[
              'Location Pastor', 'Group Pastor', 'Region Pastor', 'State Admin',
              'State Overseer', 'National Admin', 'National Overseer',
              'Continental Admin', 'Continental Overseer', 'Global Admin'
          ])
          AND p.permission = ANY(ARRAY['reports:read', 'statistics:read', 'reports:refresh'])
    """))
