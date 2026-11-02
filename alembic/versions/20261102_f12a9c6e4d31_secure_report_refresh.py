"""Expose a narrowly scoped analytics refresh to the runtime role.

Revision ID: f12a9c6e4d31
Revises: e01c4a8b6d20
Create Date: 2026-11-02
"""

from alembic import op
from sqlalchemy import text


revision = "f12a9c6e4d31"
down_revision = "e01c4a8b6d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    migration_role = bind.execute(text("SELECT current_user")).scalar_one()
    flags = bind.execute(text("""
        SELECT rolsuper, rolbypassrls
        FROM pg_roles
        WHERE rolname = current_user
    """)).one()
    if migration_role == "church_app_runtime" or not (flags.rolsuper or flags.rolbypassrls):
        raise RuntimeError("Analytics refresh function must be created by the privileged migration role")

    runtime_exists = bind.execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'church_app_runtime'")).scalar()
    if not runtime_exists:
        raise RuntimeError("Expected church_app_runtime role is missing")

    op.execute(text("""
        CREATE OR REPLACE FUNCTION public.refresh_church_analytics_views()
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $function$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_daily_counts_by_location;
            REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_monthly_financial_summary;
            REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_attendance_trends;
        END;
        $function$
    """))
    op.execute(text("REVOKE ALL ON FUNCTION public.refresh_church_analytics_views() FROM PUBLIC"))
    op.execute(text("GRANT EXECUTE ON FUNCTION public.refresh_church_analytics_views() TO church_app_runtime"))


def downgrade() -> None:
    op.execute(text("REVOKE EXECUTE ON FUNCTION public.refresh_church_analytics_views() FROM church_app_runtime"))
    op.execute(text("DROP FUNCTION IF EXISTS public.refresh_church_analytics_views()"))
