"""Route legacy origin-approved transfers through the receiving leadership stages.

Revision ID: c2138e4a6f90
Revises: b1342f6a7c91
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa

revision = "c2138e4a6f90"
down_revision = "b1342f6a7c91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rows created by the former two-party API may already have origin approval
    # but lack explicit receiving Location and Group approvals. Keep them open
    # at the receiving Location stage; do not let regional approval skip them.
    op.execute(sa.text("""
        UPDATE worker_transfers
           SET workflow_stage = 'receiving_location',
               current_level = 2,
               status = 'pending_receiving_location'
         WHERE origin_approved_by IS NOT NULL
           AND receiving_location_approved_by IS NULL
           AND status IN ('pending_region', 'approved_by_origin')
    """))


def downgrade() -> None:
    op.execute(sa.text("""
        UPDATE worker_transfers
           SET workflow_stage = 'region',
               current_level = 4,
               status = 'pending_region'
         WHERE workflow_stage = 'receiving_location'
           AND receiving_location_approved_by IS NULL
           AND origin_approved_by IS NOT NULL
    """))
