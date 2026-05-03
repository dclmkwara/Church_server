"""Alembic environment for migrations in DCLM backend.

This script configures Alembic to run both offline and online migrations using
the sync psycopg2 driver. Runtime app traffic remains async; migrations use
sync DB access because it is more reliable with Supabase/PgBouncer poolers.
"""

import os
import sys
from logging.config import fileConfig
from urllib.parse import quote

from sqlalchemy import create_engine, inspect, pool
from sqlalchemy.engine import make_url
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


def _quote_database_url_password(db_url: str) -> str:
    """Percent-encode userinfo so raw password characters like # do not break URL parsing."""
    scheme_sep = "://"
    if scheme_sep not in db_url or "@" not in db_url:
        return db_url
    scheme, rest = db_url.split(scheme_sep, 1)
    userinfo, host_and_path = rest.rsplit("@", 1)
    if ":" not in userinfo:
        return db_url
    username, password = userinfo.rsplit(":", 1)
    quoted_user = quote(username, safe="%")
    quoted_password = quote(password, safe="%")
    return f"{scheme}{scheme_sep}{quoted_user}:{quoted_password}@{host_and_path}"


def _migration_url() -> str:
    db_url = _quote_database_url_password(str(settings.sync_database_url))
    url_obj = make_url(db_url)
    query = dict(url_obj.query or {})
    if url_obj.host and "supabase.com" in url_obj.host:
        query.setdefault("sslmode", "require")
    if query != dict(url_obj.query or {}):
        url_obj = url_obj.set(query=query)
        db_url = url_obj.render_as_string(hide_password=False)
    return db_url


def _alembic_command_name() -> str | None:
    cmd_opts = getattr(config, "cmd_opts", None)
    cmd = getattr(cmd_opts, "cmd", None)
    if isinstance(cmd, tuple) and cmd:
        return getattr(cmd[0], "__name__", None)
    return None


def _create_reporting_views(sync_conn) -> None:
    sync_conn.exec_driver_sql("DROP MATERIALIZED VIEW IF EXISTS mv_daily_counts_by_location")
    sync_conn.exec_driver_sql(
        """
        CREATE MATERIALIZED VIEW mv_daily_counts_by_location AS
        SELECT
            DATE(c.date) AS day,
            c.location_id,
            l.location_name,
            c.path AS path,
            SUM(c.total) AS total_attendance,
            SUM(c.adult_male) AS total_men,
            SUM(c.adult_female) AS total_women,
            SUM(c.youth_male) AS total_youth_male,
            SUM(c.youth_female) AS total_youth_female,
            SUM(c.boys) AS total_boys,
            SUM(c.girls) AS total_girls,
            COUNT(*) AS record_count
        FROM counts c
        JOIN locations l ON l.location_id = c.location_id
        WHERE c.is_deleted = FALSE
        GROUP BY DATE(c.date), c.location_id, l.location_name, c.path
        """
    )
    sync_conn.exec_driver_sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_daily_counts_by_location
        ON mv_daily_counts_by_location (day, location_id)
        """
    )

    sync_conn.exec_driver_sql("DROP MATERIALIZED VIEW IF EXISTS mv_monthly_financial_summary")
    sync_conn.exec_driver_sql(
        """
        CREATE MATERIALIZED VIEW mv_monthly_financial_summary AS
        SELECT
            date_trunc('month', o.date) AS month,
            o.location_id,
            l.location_name,
            o.path AS path,
            COALESCE(SUM(o.amount), 0)::float AS total_amount,
            COUNT(*) AS transaction_count
        FROM offerings o
        JOIN locations l ON l.location_id = o.location_id
        WHERE o.is_deleted = FALSE
        GROUP BY date_trunc('month', o.date), o.location_id, l.location_name, o.path
        """
    )
    sync_conn.exec_driver_sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_monthly_financial_summary
        ON mv_monthly_financial_summary (month, location_id)
        """
    )

    sync_conn.exec_driver_sql("DROP MATERIALIZED VIEW IF EXISTS mv_attendance_trends")
    sync_conn.exec_driver_sql(
        """
        CREATE MATERIALIZED VIEW mv_attendance_trends AS
        SELECT
            date_trunc('week', wa.created_at) AS week,
            wa.location_id,
            l.location_name,
            wa.path AS path,
            wa.status,
            COUNT(*) AS worker_count
        FROM worker_attendance wa
        JOIN locations l ON l.location_id = wa.location_id
        WHERE wa.is_deleted = FALSE
        GROUP BY date_trunc('week', wa.created_at), wa.location_id, l.location_name, wa.path, wa.status
        """
    )
    sync_conn.exec_driver_sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_mv_attendance_trends
        ON mv_attendance_trends (week, location_id, status)
        """
    )


def _create_performance_indexes(sync_conn) -> None:
    # Empty-database bootstrap runs inside a transaction, so use regular CREATE INDEX.
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_workers_approval_status ON workers(approval_status) WHERE is_deleted = false",
        "CREATE INDEX IF NOT EXISTS ix_workers_email ON workers(email) WHERE is_deleted = false",
        "CREATE INDEX IF NOT EXISTS ix_users_approval_status ON users(approval_status)",
        "CREATE INDEX IF NOT EXISTS ix_counts_date ON counts(date) WHERE is_deleted = false",
        "CREATE INDEX IF NOT EXISTS ix_counts_created_at ON counts(created_at) WHERE is_deleted = false",
        "CREATE INDEX IF NOT EXISTS ix_offerings_date ON offerings(date) WHERE is_deleted = false",
        "CREATE INDEX IF NOT EXISTS ix_worker_attendance_status ON worker_attendance(status) WHERE is_deleted = false",
        "CREATE INDEX IF NOT EXISTS ix_records_record_type ON records(record_type) WHERE is_deleted = false",
        "CREATE INDEX IF NOT EXISTS ix_church_members_status ON church_members(status) WHERE is_deleted = false",
        "CREATE INDEX IF NOT EXISTS ix_announcements_is_active ON announcements(is_active)",
    ]
    for statement in indexes:
        sync_conn.exec_driver_sql(statement)


def _bootstrap_empty_database(sync_conn) -> bool:
    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())
    non_alembic_tables = {table for table in existing_tables if table != "alembic_version"}
    if non_alembic_tables:
        return False

    sync_conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS ltree")
    Base.metadata.create_all(bind=sync_conn)
    _create_reporting_views(sync_conn)
    _create_performance_indexes(sync_conn)

    context.configure(
        connection=sync_conn,
        target_metadata=target_metadata,
        include_schemas=True,
        compare_type=True,
        compare_server_default=True,
    )
    context.get_context().stamp(context.script, "head")
    return True


# --- Migration Functions ---
def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection)."""
    context.configure(
        url=_migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode with a sync psycopg2 engine."""
    engine = create_engine(
        _migration_url(),
        poolclass=pool.NullPool,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 30,
            "application_name": "alembic",
        },
        future=True,
    )
    try:
        with engine.begin() as connection:
            if _alembic_command_name() == "upgrade" and _bootstrap_empty_database(connection):
                return

        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_schemas=True,
                compare_type=True,
                compare_server_default=True,
                transaction_per_migration=True,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


# --- Execution Guard ---
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
