"""Placeholder base revision to match existing database state.

If the database is empty, bootstrap the full schema using model metadata.
This keeps existing databases untouched while allowing fresh installs.
"""

from alembic import op
from sqlalchemy import inspect

from app.db.base import Base


# revision identifiers, used by Alembic.
revision = "4f7eda7933f7"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create full schema if database is empty."""
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())
    non_alembic = {t for t in existing_tables if t != "alembic_version"}

    # If non-alembic tables already exist, keep this as a no-op
    if non_alembic:
        return

    # Ensure ltree extension for path columns
    op.execute("CREATE EXTENSION IF NOT EXISTS ltree")

    # Create all tables from metadata
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    """No-op placeholder."""
    pass
