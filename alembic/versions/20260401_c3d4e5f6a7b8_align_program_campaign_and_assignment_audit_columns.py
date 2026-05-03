"""align program campaign and assignment audit columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-01 12:10:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = :table_name AND column_name = :column_name
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.first() is not None


def upgrade() -> None:
    tables = ('program_campaigns', 'event_assignments')
    for table_name in tables:
        if not _has_column(table_name, 'last_modify'):
            op.add_column(table_name, sa.Column('last_modify', sa.DateTime(timezone=True), nullable=True))
        if not _has_column(table_name, 'operation'):
            op.add_column(table_name, sa.Column('operation', sa.String(), nullable=False, server_default='CREATE'))
        op.execute(sa.text(f"UPDATE {table_name} SET last_modify = COALESCE(last_modify, updated_at, created_at, NOW())"))
        op.execute(sa.text(f"UPDATE {table_name} SET operation = COALESCE(operation, 'CREATE')"))
        op.alter_column(table_name, 'last_modify', nullable=False)
        op.alter_column(table_name, 'operation', server_default=None)


def downgrade() -> None:
    for table_name in ('event_assignments', 'program_campaigns'):
        if _has_column(table_name, 'operation'):
            op.drop_column(table_name, 'operation')
        if _has_column(table_name, 'last_modify'):
            op.drop_column(table_name, 'last_modify')
