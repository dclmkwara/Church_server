"""Add versioned location expected Sunday attendance estimates.

Revision ID: e2b4c6d8f013
Revises: d4a9c1e7f235
Create Date: 2026-11-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e2b4c6d8f013"
down_revision = "d4a9c1e7f235"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "location_expected_population",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("expected_value", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("set_by_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("expected_value >= 0", name="ck_location_expected_population_nonnegative"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.location_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["set_by_id"], ["users.user_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("ALTER TABLE location_expected_population ALTER COLUMN path TYPE LTREE USING path::ltree")
    op.create_index(
        "ix_location_expected_population_location_effective",
        "location_expected_population", ["location_id", "effective_from", "created_at"],
    )
    op.create_index(
        "ix_location_expected_population_path_gist", "location_expected_population", ["path"],
        postgresql_using="gist",
    )
    op.execute("ALTER TABLE public.location_expected_population ENABLE ROW LEVEL SECURITY")
    scoped = (
        "NULLIF(current_setting('app.scope_path', true), '') IS NOT NULL AND "
        "path <@ NULLIF(current_setting('app.scope_path', true), '')::ltree"
    )
    op.execute(
        "CREATE POLICY expected_population_read ON public.location_expected_population "
        f"FOR SELECT TO PUBLIC USING ({scoped})"
    )
    op.execute(
        "CREATE POLICY expected_population_state_write ON public.location_expected_population "
        f"FOR ALL TO PUBLIC USING ((COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int = 5) AND ({scoped})) "
        f"WITH CHECK ((COALESCE(NULLIF(current_setting('app.role_score', true), ''), '0')::int = 5) AND ({scoped}))"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS expected_population_state_write ON public.location_expected_population")
    op.execute("DROP POLICY IF EXISTS expected_population_read ON public.location_expected_population")
    op.drop_index("ix_location_expected_population_path_gist", table_name="location_expected_population")
    op.drop_index("ix_location_expected_population_location_effective", table_name="location_expected_population")
    op.drop_table("location_expected_population")
