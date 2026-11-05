"""Add staged worker transfer reviews and removal restoration snapshots.

Revision ID: b1342f6a7c91
Revises: a4c29e81b705
Create Date: 2026-11-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b1342f6a7c91"
down_revision = "a4c29e81b705"
branch_labels = None
depends_on = None


def _add_transfer_review_fields(table: str) -> None:
    op.add_column(table, sa.Column("current_level", sa.Integer(), nullable=False, server_default="3"))
    op.add_column(table, sa.Column("workflow_stage", sa.String(), nullable=False, server_default="origin_group"))
    op.add_column(table, sa.Column("reviews", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column(table, sa.Column("group_approved_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(table, sa.Column("group_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("group_note", sa.Text(), nullable=True))
    op.add_column(table, sa.Column("region_approved_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(table, sa.Column("region_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("region_note", sa.Text(), nullable=True))
    op.add_column(table, sa.Column("receiving_location_approved_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(table, sa.Column("receiving_location_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("receiving_location_note", sa.Text(), nullable=True))
    op.add_column(table, sa.Column("receiving_group_approved_by", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(table, sa.Column("receiving_group_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(table, sa.Column("receiving_group_note", sa.Text(), nullable=True))
    op.create_index(f"ix_{table}_current_level", table, ["current_level"])
    op.create_index(f"ix_{table}_group_approved_by", table, ["group_approved_by"])
    op.create_index(f"ix_{table}_region_approved_by", table, ["region_approved_by"])
    op.create_index(f"ix_{table}_receiving_location_approved_by", table, ["receiving_location_approved_by"])
    op.create_index(f"ix_{table}_receiving_group_approved_by", table, ["receiving_group_approved_by"])
    op.create_index(f"ix_{table}_workflow_stage", table, ["workflow_stage"])
    op.create_foreign_key(f"fk_{table}_group_approved_by_users", table, "users", ["group_approved_by"], ["user_id"])
    op.create_foreign_key(f"fk_{table}_region_approved_by_users", table, "users", ["region_approved_by"], ["user_id"])
    op.create_foreign_key(f"fk_{table}_receiving_location_approved_by_users", table, "users", ["receiving_location_approved_by"], ["user_id"])
    op.create_foreign_key(f"fk_{table}_receiving_group_approved_by_users", table, "users", ["receiving_group_approved_by"], ["user_id"])


def upgrade() -> None:
    _add_transfer_review_fields("transfer_requests")
    op.add_column("transfer_requests", sa.Column("rejection_reason", sa.Text(), nullable=True))
    _add_transfer_review_fields("worker_transfers")
    op.add_column("worker_removal_requests", sa.Column("worker_status_before_request", sa.String(), nullable=True))
    op.add_column("worker_removal_requests", sa.Column("user_was_active_before_request", sa.Boolean(), nullable=True))

    # Preserve the old in-flight origin/destination workflow as its closest
    # equivalent staged state. New requests use pending -> pending_region.
    op.execute(sa.text("""
        UPDATE worker_transfers
           SET group_approved_by = origin_approved_by,
               group_approved_at = origin_approved_at,
               group_note = origin_note,
               region_approved_by = destination_approved_by,
               region_approved_at = destination_approved_at,
               region_note = destination_note,
               current_level = CASE WHEN origin_approved_by IS NULL THEN 3 ELSE 4 END,
               workflow_stage = CASE WHEN origin_approved_by IS NULL THEN 'origin_group' ELSE 'region' END,
               status = CASE WHEN status = 'approved_by_origin' THEN 'pending_region' ELSE status END
    """))
    op.execute(sa.text("UPDATE transfer_requests SET current_level = 4 WHERE status = 'approved'"))


def downgrade() -> None:
    op.drop_column("worker_removal_requests", "user_was_active_before_request")
    op.drop_column("worker_removal_requests", "worker_status_before_request")
    for table in ("worker_transfers", "transfer_requests"):
        op.drop_constraint(f"fk_{table}_region_approved_by_users", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_group_approved_by_users", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_receiving_location_approved_by_users", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_receiving_group_approved_by_users", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_region_approved_by", table_name=table)
        op.drop_index(f"ix_{table}_group_approved_by", table_name=table)
        op.drop_index(f"ix_{table}_current_level", table_name=table)
        op.drop_index(f"ix_{table}_workflow_stage", table_name=table)
        op.drop_index(f"ix_{table}_receiving_location_approved_by", table_name=table)
        op.drop_index(f"ix_{table}_receiving_group_approved_by", table_name=table)
        for column in (
            "region_note", "region_approved_at", "region_approved_by", "receiving_location_note", "receiving_location_approved_at", "receiving_location_approved_by", "receiving_group_note", "receiving_group_approved_at", "receiving_group_approved_by", "workflow_stage",
            "group_note", "group_approved_at", "group_approved_by", "reviews", "current_level",
        ):
            op.drop_column(table, column)
    op.drop_column("transfer_requests", "rejection_reason")
