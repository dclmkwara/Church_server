"""Add lifecycle dates and active status for locations.

Revision ID: a71c3f9d2b40
Revises: f7c2d4a6b810
Create Date: 2026-11-06

Existing rows remain active, while their historical opening date stays
unknown. The pre-migration database snapshot is retained outside the repo.
"""

from alembic import op
import sqlalchemy as sa


revision = "a71c3f9d2b40"
down_revision = "f7c2d4a6b810"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add location lifecycle fields without fabricating legacy opening dates."""
    op.add_column(
        "locations",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("locations", sa.Column("opened_on", sa.Date(), nullable=True))
    op.add_column("locations", sa.Column("closed_on", sa.Date(), nullable=True))
    op.alter_column("locations", "opened_on", server_default=sa.text("CURRENT_DATE"))
    op.create_index("ix_locations_is_active", "locations", ["is_active"])
    op.create_check_constraint(
        "ck_locations_lifecycle_dates",
        "locations",
        "opened_on IS NULL OR closed_on IS NULL OR closed_on >= opened_on",
    )


def downgrade() -> None:
    """Refuse to discard lifecycle information entered after this migration."""
    op.execute(
        """
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM locations
                WHERE is_active IS FALSE OR opened_on IS NOT NULL OR closed_on IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'Location lifecycle data exists; restore the pre-migration snapshot before downgrade';
            END IF;
        END $$;
        """
    )
    op.drop_constraint("ck_locations_lifecycle_dates", "locations", type_="check")
    op.drop_index("ix_locations_is_active", table_name="locations")
    op.drop_column("locations", "closed_on")
    op.drop_column("locations", "opened_on")
    op.drop_column("locations", "is_active")
