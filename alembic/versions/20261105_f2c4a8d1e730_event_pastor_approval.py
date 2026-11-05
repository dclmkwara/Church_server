"""Require same-level pastor approval for scheduled events.

Revision ID: f2c4a8d1e730
Revises: f1b2c3d4e5a6
Create Date: 2026-11-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f2c4a8d1e730"
down_revision = "f1b2c3d4e5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("program_events", sa.Column(
        "approval_status", sa.String(length=20), nullable=False, server_default="approved"
    ))
    op.add_column("program_events", sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("program_events", sa.Column("approved_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("program_events", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("program_events", sa.Column("approval_note", sa.Text(), nullable=True))
    op.create_foreign_key("fk_program_events_created_by", "program_events", "users", ["created_by_id"], ["user_id"])
    op.create_foreign_key("fk_program_events_approved_by", "program_events", "users", ["approved_by_id"], ["user_id"])
    op.create_index("ix_program_events_approval_status", "program_events", ["approval_status"])
    op.alter_column("program_events", "approval_status", server_default="pending")
    op.create_check_constraint(
        "ck_program_events_approval_status", "program_events",
        "approval_status IN ('pending','approved','rejected')",
    )

    connection = op.get_bind()
    permission_id = connection.execute(sa.text(
        "INSERT INTO permissions (permission, name, description, is_deleted, operation) "
        "VALUES ('programs:create_event', 'Create Program Events', "
        "'Can schedule program events within the assigned jurisdiction', false, 'CREATE') "
        "ON CONFLICT (permission) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description "
        "RETURNING id"
    )).scalar_one()
    connection.execute(sa.text(
        "INSERT INTO role_permissions (role_id, permission_id) "
        "SELECT roles.id, :permission_id FROM roles "
        "WHERE roles.role_name IN ('Location Admin','Group Admin','Region Admin','State Admin',"
        "'Zonal Coordinator','National Admin','National Overseer','Continental Admin',"
        "'Continental Overseer','Global Admin') "
        "ON CONFLICT DO NOTHING"
    ), {"permission_id": permission_id})


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE permission = 'programs:create_event')"
    ))
    connection.execute(sa.text("DELETE FROM permissions WHERE permission = 'programs:create_event'"))
    op.drop_constraint("ck_program_events_approval_status", "program_events", type_="check")
    op.drop_index("ix_program_events_approval_status", table_name="program_events")
    op.drop_constraint("fk_program_events_approved_by", "program_events", type_="foreignkey")
    op.drop_constraint("fk_program_events_created_by", "program_events", type_="foreignkey")
    op.drop_column("program_events", "approval_note")
    op.drop_column("program_events", "approved_at")
    op.drop_column("program_events", "approved_by_id")
    op.drop_column("program_events", "created_by_id")
    op.drop_column("program_events", "approval_status")
