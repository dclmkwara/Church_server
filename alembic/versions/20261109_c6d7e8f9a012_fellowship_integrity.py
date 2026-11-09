"""Align fellowship activity foreign keys with the UUID model.

Revision ID: c6d7e8f9a012
Revises: b5f7a9c2d341
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c6d7e8f9a012"
down_revision = "b5f7a9c2d341"
branch_labels = None
depends_on = None

TABLES = (
    "fellowship_members",
    "fellowship_attendance",
    "fellowship_offerings",
    "fellowship_testimony",
    "fellowship_prayer_request",
    "fellowship_attendance_summaries",
)


def upgrade() -> None:
    # The preflight found only three orphaned development records (one each in
    # members, attendance and offerings); no malformed UUIDs. Orphans cannot
    # satisfy the new FK. Discard only rows with no parent fellowship; this is
    # development data and the pre-migration snapshot remains the recovery copy.
    for name in ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls"):
        op.add_column(
            "fellowship_attendance",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )
    for table in TABLES:
        op.execute(
            sa.text(
                f"""
                DO $$ BEGIN
                    IF EXISTS (
                        SELECT 1 FROM {table}
                        WHERE fellowship_id !~* '^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}}$'
                    ) THEN
                        RAISE EXCEPTION 'Malformed fellowship UUID remains in {table}.fellowship_id';
                    END IF;
                END $$
                """
            )
        )
        op.execute(
            sa.text(
                f"""
                DELETE FROM {table} AS activity
                WHERE NOT EXISTS (
                    SELECT 1 FROM fellowships AS parent
                    WHERE parent.fellowship_id::text = activity.fellowship_id
                )
                """
            )
        )
        op.alter_column(
            table,
            "fellowship_id",
            existing_type=sa.String(),
            type_=postgresql.UUID(as_uuid=False),
            existing_nullable=False,
            postgresql_using="fellowship_id::uuid",
        )
        op.create_foreign_key(
            f"fk_{table}_fellowship_id_fellowships",
            table,
            "fellowships",
            ["fellowship_id"],
            ["fellowship_id"],
        )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_constraint(
            f"fk_{table}_fellowship_id_fellowships", table, type_="foreignkey"
        )
        op.alter_column(
            table,
            "fellowship_id",
            existing_type=postgresql.UUID(as_uuid=False),
            type_=sa.String(),
            existing_nullable=False,
            postgresql_using="fellowship_id::text",
        )
    for name in ("girls", "boys", "youth_female", "youth_male", "adult_female", "adult_male"):
        op.drop_column("fellowship_attendance", name)
