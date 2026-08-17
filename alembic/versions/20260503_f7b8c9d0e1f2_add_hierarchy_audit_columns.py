"""add audit columns to uuid hierarchy tables

Revision ID: f7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-03 18:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql


revision = "f7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


HIERARCHY_TABLES = [
    "nations",
    "states",
    "regions",
    "dclm_groups",
    "locations",
    "fellowships",
]


def _columns(inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def _indexes(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    for table_name in HIERARCHY_TABLES:
        if table_name not in existing_tables:
            continue
        columns = _columns(inspector, table_name)
        if "created_by" not in columns:
            op.add_column(table_name, sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True))
        if "version" not in columns:
            op.add_column(
                table_name,
                sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
            )
            op.alter_column(table_name, "version", server_default=None)
        indexes = _indexes(inspector, table_name)
        index_name = f"ix_{table_name}_created_by"
        if index_name not in indexes:
            op.create_index(index_name, table_name, ["created_by"])


def downgrade() -> None:
    for table_name in reversed(HIERARCHY_TABLES):
        op.drop_index(f"ix_{table_name}_created_by", table_name=table_name)
        op.drop_column(table_name, "version")
        op.drop_column(table_name, "created_by")
