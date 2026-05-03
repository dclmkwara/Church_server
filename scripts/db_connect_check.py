"""
Simple database connectivity check using asyncpg.

Two modes:
1) Use DATABASE_URL from app.core.config
2) Use a direct DSN passed with --dsn

Examples:
  python scripts/db_connect_check.py
  python scripts/db_connect_check.py --dsn "postgresql+asyncpg://user:pass@host:6543/postgres?sslmode=require"
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import asyncpg
from sqlalchemy.engine import make_url

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app.core.config import settings  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check DB connectivity with asyncpg.")
    parser.add_argument(
        "--dsn",
        help="Optional database URL to test directly (overrides env).",
    )
    return parser.parse_args()


def _normalize_dsn(raw_url: str) -> tuple[str, bool]:
    """
    Return (dsn, ssl_required).
    - strips +asyncpg
    - removes sslmode/channel_binding from query
    - sets ssl_required if sslmode requires SSL
    """
    url_obj = make_url(raw_url)
    query = url_obj.query or {}
    sslmode = query.get("sslmode")
    ssl_required = str(sslmode).lower() in {"require", "verify-full", "verify-ca"} if sslmode else False
    filtered_query = {k: v for k, v in query.items() if k not in {"sslmode", "channel_binding"}}
    if filtered_query != query:
        url_obj = url_obj.set(query=filtered_query)
    dsn = url_obj.render_as_string(hide_password=False).replace("+asyncpg", "")
    return dsn, ssl_required


def _safe_url_info(raw_url: str) -> str:
    try:
        url_obj = make_url(raw_url)
        return f"user={url_obj.username}, host={url_obj.host}, port={url_obj.port}, db={url_obj.database}"
    except Exception:
        return "url=parse_failed"


async def _check(raw_url: str, label: str) -> None:
    dsn, ssl_required = _normalize_dsn(raw_url)
    print(f"[{label}] { _safe_url_info(raw_url) }, ssl_required={ssl_required}")
    try:
        conn = await asyncpg.connect(dsn, ssl=True if ssl_required else None)
        try:
            val = await conn.fetchval("SELECT 1")
            print(f"[{label}] OK (SELECT 1 -> {val})")
        finally:
            await conn.close()
    except Exception as e:
        print(f"[{label}] FAIL: {type(e).__name__}: {e}")


def main() -> int:
    args = _parse_args()
    env_url = str(settings.DATABASE_URL)
    raw_env = os.getenv("DATABASE_URL")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    if raw_env:
        print(f"[ENVVAR] DATABASE_URL is set in the shell ({_safe_url_info(raw_env)})")
    else:
        print("[ENVVAR] DATABASE_URL is not set in the shell")

    asyncio.run(_check(env_url, "ENV"))
    if args.dsn:
        asyncio.run(_check(args.dsn, "DSN"))
    else:
        print("[DSN] Skipped (no --dsn provided)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
