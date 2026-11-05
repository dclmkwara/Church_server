"""Normalize shared-backend higher admin home paths.

Revision ID: 1c7d4e9a2f60
Revises: 0d8f6a2b4c91
Create Date: 2026-11-04
"""

from alembic import op
import sqlalchemy as sa


revision = "1c7d4e9a2f60"
down_revision = "0d8f6a2b4c91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Location pastors submit removal requests; score 3+ is required for the
    # direct worker removal action exposed by the administrative API.
    bind.execute(sa.text("""
        DELETE FROM role_permissions rp
        USING roles r, role_scores rs, permissions p
        WHERE rp.role_id = r.id
          AND r.score_id = rs.id
          AND rp.permission_id = p.id
          AND rs.score = 2
          AND p.permission = 'workers:delete'
    """))
    # Keep each role's worker/home record aligned with the jurisdiction
    # consumed by shared-backend scope resolution. Zone (score 6) is unchanged
    # until a zone-to-path mapping exists.
    bind.execute(sa.text("""
        WITH user_scores AS (
            SELECT ur.user_id, max(rs.score) AS score
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id AND r.is_deleted = false
            JOIN role_scores rs ON rs.id = r.score_id
            GROUP BY ur.user_id
        )
        UPDATE users u
        SET path = CASE
            WHEN s.score IN (7, 8) THEN subpath(u.path::ltree, 0, 2)::text
            WHEN s.score = 9 THEN subpath(u.path::ltree, 0, 1)::text
        END
        FROM user_scores s
        WHERE u.user_id = s.user_id
          AND s.score >= 7
          AND u.path IS NOT NULL
          AND nlevel(u.path::ltree) >= 2
    """))
    bind.execute(sa.text("""
        WITH user_scores AS (
            SELECT ur.user_id, max(rs.score) AS score
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id AND r.is_deleted = false
            JOIN role_scores rs ON rs.id = r.score_id
            GROUP BY ur.user_id
        )
        UPDATE workers w
        SET path = CASE
            WHEN s.score IN (7, 8) THEN subpath(w.path::ltree, 0, 2)::text
            WHEN s.score = 9 THEN subpath(w.path::ltree, 0, 1)::text
        END
        FROM users u
        JOIN user_scores s ON s.user_id = u.user_id
        WHERE w.worker_id = u.worker_id
          AND s.score >= 7
          AND w.path IS NOT NULL
          AND nlevel(w.path::ltree) >= 2
    """))


def downgrade() -> None:
    raise RuntimeError(
        "Higher admin paths cannot be safely restored without a pre-change snapshot."
    )
