"""add approvals, app_versions, and offering fund_type

Revision ID: f14fc281567e
Revises: 4f7eda7933f7
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "f14fc281567e"
down_revision = "4f7eda7933f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    def table_exists(name: str) -> bool:
        return name in inspector.get_table_names()

    def column_exists(table: str, column: str) -> bool:
        return column in {col["name"] for col in inspector.get_columns(table)}

    def index_exists(table: str, index_name: str) -> bool:
        return index_name in {idx["name"] for idx in inspector.get_indexes(table)}

    # App versions
    if not table_exists("app_versions"):
        op.create_table(
            "app_versions",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("app_name", sa.String(), nullable=False),
            sa.Column("platform", sa.String(), nullable=False),
            sa.Column("version_number", sa.String(), nullable=True),
            sa.Column("version_tag", sa.String(), nullable=True),
            sa.Column("release_date", sa.Date(), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("file_name", sa.String(), nullable=True),
            sa.Column("download_url", sa.String(), nullable=True),
            sa.Column("min_os_version", sa.String(), nullable=True),
            sa.Column("build", sa.String(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("operation", sa.String(), nullable=False, server_default=sa.text("'CREATE'")),
        )
    if not index_exists("app_versions", "ix_app_versions_created_at"):
        op.create_index(op.f("ix_app_versions_created_at"), "app_versions", ["created_at"], unique=False)
    if not index_exists("app_versions", "ix_app_versions_is_deleted"):
        op.create_index(op.f("ix_app_versions_is_deleted"), "app_versions", ["is_deleted"], unique=False)
    if not index_exists("app_versions", "ix_app_versions_operation"):
        op.create_index(op.f("ix_app_versions_operation"), "app_versions", ["operation"], unique=False)

    # Ensure ltree extension is available
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree")

    # Approvals: transfer requests
    if not table_exists("transfer_requests"):
        op.create_table(
            "transfer_requests",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("from_location_id", sa.String(), nullable=False),
            sa.Column("to_location_id", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("reason", sa.String(), nullable=True),
            sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["worker_id"], ["workers.worker_id"]),
            sa.ForeignKeyConstraint(["requested_by"], ["users.user_id"]),
            sa.ForeignKeyConstraint(["approved_by"], ["users.user_id"]),
        )
    if not index_exists("transfer_requests", "ix_transfer_requests_created_at"):
        op.create_index(op.f("ix_transfer_requests_created_at"), "transfer_requests", ["created_at"], unique=False)
    if not index_exists("transfer_requests", "ix_transfer_requests_from_location_id"):
        op.create_index(op.f("ix_transfer_requests_from_location_id"), "transfer_requests", ["from_location_id"], unique=False)
    if not index_exists("transfer_requests", "ix_transfer_requests_to_location_id"):
        op.create_index(op.f("ix_transfer_requests_to_location_id"), "transfer_requests", ["to_location_id"], unique=False)
    if not index_exists("transfer_requests", "ix_transfer_requests_status"):
        op.create_index(op.f("ix_transfer_requests_status"), "transfer_requests", ["status"], unique=False)
    if not index_exists("transfer_requests", "ix_transfer_requests_worker_id"):
        op.create_index(op.f("ix_transfer_requests_worker_id"), "transfer_requests", ["worker_id"], unique=False)
    if not index_exists("transfer_requests", "ix_transfer_requests_path"):
        op.create_index(op.f("ix_transfer_requests_path"), "transfer_requests", ["path"], unique=False)

    # Approvals: status change requests
    if not table_exists("status_change_requests"):
        op.create_table(
            "status_change_requests",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column("worker_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("old_status", sa.String(), nullable=True),
            sa.Column("new_status", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=True),
            sa.Column("reason", sa.String(), nullable=True),
            sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("last_modify", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("path", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["worker_id"], ["workers.worker_id"]),
            sa.ForeignKeyConstraint(["requested_by"], ["users.user_id"]),
            sa.ForeignKeyConstraint(["approved_by"], ["users.user_id"]),
        )
    if not index_exists("status_change_requests", "ix_status_change_requests_created_at"):
        op.create_index(op.f("ix_status_change_requests_created_at"), "status_change_requests", ["created_at"], unique=False)
    if not index_exists("status_change_requests", "ix_status_change_requests_status"):
        op.create_index(op.f("ix_status_change_requests_status"), "status_change_requests", ["status"], unique=False)
    if not index_exists("status_change_requests", "ix_status_change_requests_worker_id"):
        op.create_index(op.f("ix_status_change_requests_worker_id"), "status_change_requests", ["worker_id"], unique=False)
    if not index_exists("status_change_requests", "ix_status_change_requests_path"):
        op.create_index(op.f("ix_status_change_requests_path"), "status_change_requests", ["path"], unique=False)

    # Convert path columns to ltree
    if table_exists("transfer_requests"):
        op.execute("ALTER TABLE transfer_requests ALTER COLUMN path TYPE ltree USING path::ltree")
        op.execute("DROP INDEX IF EXISTS ix_transfer_requests_path")
        op.execute("CREATE INDEX IF NOT EXISTS ix_transfer_requests_path ON transfer_requests USING GIST (path)")
    if table_exists("status_change_requests"):
        op.execute("ALTER TABLE status_change_requests ALTER COLUMN path TYPE ltree USING path::ltree")
        op.execute("DROP INDEX IF EXISTS ix_status_change_requests_path")
        op.execute("CREATE INDEX IF NOT EXISTS ix_status_change_requests_path ON status_change_requests USING GIST (path)")

    # Offerings fund_type
    if table_exists("offerings") and not column_exists("offerings", "fund_type"):
        op.add_column("offerings", sa.Column("fund_type", sa.String(), nullable=False, server_default=sa.text("'offering'")))
        if not index_exists("offerings", "ix_offerings_fund_type"):
            op.create_index(op.f("ix_offerings_fund_type"), "offerings", ["fund_type"], unique=False)
        op.alter_column("offerings", "fund_type", server_default=None)

    # Locations geo
    if table_exists("locations") and not column_exists("locations", "latitude"):
        op.add_column("locations", sa.Column("latitude", sa.Float(), nullable=True))
    if table_exists("locations") and not column_exists("locations", "longitude"):
        op.add_column("locations", sa.Column("longitude", sa.Float(), nullable=True))

    # Recovery questions
    if table_exists("users") and not column_exists("users", "recovery_question_one"):
        op.add_column("users", sa.Column("recovery_question_one", sa.String(), nullable=True))
    if table_exists("users") and not column_exists("users", "recovery_question_two"):
        op.add_column("users", sa.Column("recovery_question_two", sa.String(), nullable=True))
    if table_exists("users") and not column_exists("users", "recovery_answer_one"):
        op.add_column("users", sa.Column("recovery_answer_one", sa.String(), nullable=True))
    if table_exists("users") and not column_exists("users", "recovery_answer_two"):
        op.add_column("users", sa.Column("recovery_answer_two", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "recovery_answer_two")
    op.drop_column("users", "recovery_answer_one")
    op.drop_column("users", "recovery_question_two")
    op.drop_column("users", "recovery_question_one")

    op.drop_column("locations", "longitude")
    op.drop_column("locations", "latitude")

    op.drop_index(op.f("ix_offerings_fund_type"), table_name="offerings")
    op.drop_column("offerings", "fund_type")

    op.execute("DROP INDEX IF EXISTS ix_status_change_requests_path")
    op.drop_index(op.f("ix_status_change_requests_worker_id"), table_name="status_change_requests")
    op.drop_index(op.f("ix_status_change_requests_status"), table_name="status_change_requests")
    op.drop_index(op.f("ix_status_change_requests_created_at"), table_name="status_change_requests")
    op.drop_table("status_change_requests")

    op.execute("DROP INDEX IF EXISTS ix_transfer_requests_path")
    op.drop_index(op.f("ix_transfer_requests_worker_id"), table_name="transfer_requests")
    op.drop_index(op.f("ix_transfer_requests_status"), table_name="transfer_requests")
    op.drop_index(op.f("ix_transfer_requests_to_location_id"), table_name="transfer_requests")
    op.drop_index(op.f("ix_transfer_requests_from_location_id"), table_name="transfer_requests")
    op.drop_index(op.f("ix_transfer_requests_created_at"), table_name="transfer_requests")
    op.drop_table("transfer_requests")

    op.drop_index(op.f("ix_app_versions_operation"), table_name="app_versions")
    op.drop_index(op.f("ix_app_versions_is_deleted"), table_name="app_versions")
    op.drop_index(op.f("ix_app_versions_created_at"), table_name="app_versions")
    op.drop_table("app_versions")
