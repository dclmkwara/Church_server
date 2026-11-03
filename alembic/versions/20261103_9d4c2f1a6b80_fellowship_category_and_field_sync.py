"""Persist fellowship category and permit field-role batch uploads.

Revision ID: 9d4c2f1a6b80
Revises: 3f8a2c7d91e4
Create Date: 2026-11-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "9d4c2f1a6b80"
down_revision = "3f8a2c7d91e4"
branch_labels = None
depends_on = None


FELLOWSHIP_GROUPS = ("adult", "young_adult", "campus", "youth", "children")


def upgrade() -> None:
    op.add_column("fellowships", sa.Column("fellowship_group", sa.String(length=30), nullable=True))
    op.create_index("ix_fellowships_fellowship_group", "fellowships", ["fellowship_group"])
    op.create_check_constraint(
        "ck_fellowships_group",
        "fellowships",
        "fellowship_group IS NULL OR fellowship_group IN ('adult', 'young_adult', 'campus', 'youth', 'children')",
    )

    # Reuse existing member classifications only when every classified member agrees.
    op.execute(text("""
        WITH uniform_groups AS (
            SELECT fellowship_id, MIN(fellowship_group) AS fellowship_group
            FROM fellowship_members
            WHERE fellowship_group IS NOT NULL AND is_deleted = FALSE
            GROUP BY fellowship_id
            HAVING COUNT(DISTINCT fellowship_group) = 1
        )
        UPDATE fellowships f
        SET fellowship_group = u.fellowship_group
        FROM uniform_groups u
        WHERE f.fellowship_id::text = u.fellowship_id::text
    """))

    op.execute(text("""
        INSERT INTO permissions (permission, name, description, is_deleted, operation)
        VALUES ('sync:batch', 'Run Batch Sync', 'Can submit batch sync operations', FALSE, 'CREATE')
        ON CONFLICT (permission) DO UPDATE
        SET name = EXCLUDED.name,
            description = EXCLUDED.description,
            is_deleted = FALSE,
            operation = 'UPDATE'
    """))
    op.execute(text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT DISTINCT rp.role_id, sync_permission.id
        FROM role_permissions rp
        JOIN permissions data_permission ON data_permission.id = rp.permission_id
        CROSS JOIN permissions sync_permission
        JOIN roles r ON r.id = rp.role_id
        WHERE data_permission.permission IN (
            'counts:create', 'offerings:create', 'records:create', 'attendance:create', 'fellowship:create'
        )
          AND sync_permission.permission = 'sync:batch'
          AND r.is_deleted = FALSE
          AND data_permission.is_deleted = FALSE
          AND sync_permission.is_deleted = FALSE
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """))
    op.execute(text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r
        CROSS JOIN permissions p
        WHERE r.role_name = 'Location Worker'
          AND r.is_deleted = FALSE
          AND p.permission = 'sync:batch'
          AND p.is_deleted = FALSE
        ON CONFLICT (role_id, permission_id) DO NOTHING
    """))


def downgrade() -> None:
    op.execute(text("""
        DELETE FROM role_permissions rp
        USING permissions sync_permission
        WHERE rp.permission_id = sync_permission.id
          AND sync_permission.permission = 'sync:batch'
          AND EXISTS (
              SELECT 1 FROM roles r
              WHERE r.id = rp.role_id
                AND (
                    r.role_name = 'Location Worker'
                    OR EXISTS (
                        SELECT 1
                        FROM role_permissions data_rp
                        JOIN permissions data_permission ON data_permission.id = data_rp.permission_id
                        WHERE data_rp.role_id = r.id
                          AND data_permission.permission IN (
                              'counts:create', 'offerings:create', 'records:create', 'attendance:create', 'fellowship:create'
                          )
                    )
                )
          )
    """))
    op.drop_constraint("ck_fellowships_group", "fellowships", type_="check")
    op.drop_index("ix_fellowships_fellowship_group", table_name="fellowships")
    op.drop_column("fellowships", "fellowship_group")
