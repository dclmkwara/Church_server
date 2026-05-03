"""
Database setup script.

Creates the target database if it does not exist, then runs Alembic migrations.

Usage:
    python scripts/setup_db.py
"""
from __future__ import annotations

import argparse
import asyncio
import socket
import ssl
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import asyncpg
from sqlalchemy.engine import make_url

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.core.config import settings  # noqa: E402


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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create database (optional) and run migrations.")
    parser.add_argument(
        "--skip-create-db",
        action="store_true",
        help="Skip database creation and only run migrations.",
    )
    parser.add_argument(
        "--seed-rbac",
        action="store_true",
        help="Seed default permissions, role scores, and roles after migrations.",
    )
    return parser.parse_args()


def _build_asyncpg_dsn(url) -> tuple[str, ssl.SSLContext | bool | None]:
    """Return (dsn, ssl) for asyncpg based on URL."""
    dsn_url = url
    ssl_required = False
    ssl_verify = False
    host = url.host or ""
    query = dsn_url.query or {}
    if "supabase.com" in host:
        ssl_required = True
    sslmode = query.get("sslmode")
    if sslmode:
        sslmode_value = str(sslmode).lower()
        ssl_required = sslmode_value in {"require", "verify-full", "verify-ca"}
        ssl_verify = sslmode_value in {"verify-full", "verify-ca"}
    filtered_query = {k: v for k, v in query.items() if k not in {"sslmode", "channel_binding"}}
    if filtered_query != query:
        dsn_url = dsn_url.set(query=filtered_query)
    dsn = dsn_url.render_as_string(hide_password=False).replace("+asyncpg", "")
    if not ssl_required:
        return dsn, None
    if ssl_verify:
        return dsn, True
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return dsn, ssl_context


async def ensure_database_exists() -> None:
    url = make_url(_quote_database_url_password(str(settings.DATABASE_URL)))
    db_name = url.database
    if not db_name:
        raise RuntimeError("DATABASE_URL does not include a database name.")
    if url.host and "supabase.com" in url.host:
        print("Supabase database detected; skipping CREATE DATABASE.")
        return

    # Connect to admin database to create target db if missing
    admin_db = "postgres"
    admin_url = url.set(database=admin_db)

    # asyncpg expects a standard postgres DSN without "+asyncpg"
    dsn, ssl_arg = _build_asyncpg_dsn(admin_url)

    try:
        conn = await asyncpg.connect(dsn, ssl=ssl_arg)
    except socket.gaierror as e:
        raise RuntimeError(
            f"DNS resolution failed for host '{url.host}'. "
            "Check DATABASE_URL host, internet connectivity, or DNS settings."
        ) from e
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            db_name,
        )
        if exists:
            print(f"Database '{db_name}' already exists.")
            return

        # CREATE DATABASE cannot be parametrized; quote the identifier safely
        await conn.execute(f'CREATE DATABASE "{db_name}"')
        print(f"Database '{db_name}' created.")
    finally:
        await conn.close()


async def maybe_stamp_base_if_empty() -> None:
    """If DB has only alembic_version at placeholder, stamp base to re-run bootstrap."""
    url = make_url(_quote_database_url_password(str(settings.DATABASE_URL)))
    dsn, ssl_arg = _build_asyncpg_dsn(url)
    conn = await asyncpg.connect(dsn, ssl=ssl_arg)
    try:
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )
        table_names = {row["tablename"] for row in tables}
        if not table_names:
            return
        non_alembic = {t for t in table_names if t != "alembic_version"}
        if non_alembic:
            return
        if "alembic_version" not in table_names:
            return
        rev = await conn.fetchval("SELECT version_num FROM alembic_version")
        if rev == "4f7eda7933f7":
            print("Empty schema detected with placeholder revision. Stamping base to bootstrap.")
            subprocess.run(["alembic", "stamp", "base"], check=False)
    finally:
        await conn.close()


def run_migrations() -> int:
    print("Running Alembic migrations...")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=False,
    )
    if result.returncode == 0:
        print("Migrations applied successfully.")
    else:
        print("Migration failed.")
    return result.returncode


async def seed_rbac() -> None:
    from app.db.init_rbac import init_rbac  # noqa: PLC0415
    from app.db.session import AsyncSessionLocal, engine  # noqa: PLC0415

    try:
        async with AsyncSessionLocal() as db:
            await init_rbac(db)
            await db.commit()
    finally:
        await engine.dispose()


def main() -> int:
    args = _parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if not args.skip_create_db:
        asyncio.run(ensure_database_exists())
    # If DB was stamped to placeholder without schema, reset to base for bootstrap
    asyncio.run(maybe_stamp_base_if_empty())
    result = run_migrations()
    if result != 0:
        return result
    if args.seed_rbac:
        asyncio.run(seed_rbac())
    return result


if __name__ == "__main__":
    raise SystemExit(main())
