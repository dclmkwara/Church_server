"""add program event audience segments

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-31 10:35:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("program_events", sa.Column("audience_segment", sa.String(), nullable=True))
    op.create_index(op.f("ix_program_events_audience_segment"), "program_events", ["audience_segment"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_program_events_audience_segment"), table_name="program_events")
    op.drop_column("program_events", "audience_segment")
