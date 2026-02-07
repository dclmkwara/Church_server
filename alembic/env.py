"""Alembic environment for async migrations in DCLM backend.

This script configures Alembic to run both offline and online migrations,
using settings from app.config. It ensures our async DB engine (asyncpg)
is used and all models from app.models are registered in metadata.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import pool
from alembic import context

# --- Absolute Path Resolution ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

# --- Alembic Config ---
config = context.config
if config.config_file_name and os.path.exists(config.config_file_name):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# --- Import Application Settings AFTER sys.path is set ---
try:
    from app.core.config import settings
    from app.db.base import Base  # imports Base + registers all models
    import app.models             # ensures all models are imported
except ImportError as e:
    raise RuntimeError(
        f"Failed to import application modules: {e}. "
        f"Verify PYTHONPATH and project structure."
    )

# --- Metadata Target ---
target_metadata = Base.metadata


# --- Async Engine Factory ---
def create_async_engine_safe() -> AsyncEngine:
    """Create async engine with production-ready settings."""
    db_url = str(settings.DATABASE_URL)

    if "://" not in db_url:
        raise ValueError("Invalid DATABASE_URL format")

    # Ensure async driver
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return create_async_engine(
        db_url,
        poolclass=pool.NullPool,
        connect_args={
            "server_settings": {
                "application_name": "alembic",
                "statement_timeout": "30000",
            }
        },
        future=True,
    )


# --- Migration Functions ---
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection)."""
    url = str(settings.DATABASE_URL)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an async engine."""
    engine = create_async_engine_safe()
    async with engine.connect() as connection:
        await connection.run_sync(
            lambda sync_conn: context.configure(
                connection=sync_conn,
                target_metadata=target_metadata,
                include_schemas=True,
                compare_type=True,
                compare_server_default=True,
                transaction_per_migration=True,
            )
        )
        await connection.run_sync(lambda _: context.run_migrations())

    await engine.dispose()


# --- Execution Guard ---
if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
