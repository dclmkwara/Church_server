"""
Connect to Postgres using PG* environment variables.

Expected env vars:
  PGHOST, PGDATABASE, PGUSER, PGPASSWORD, PGSSLMODE, PGCHANNELBINDING

Note: asyncpg does not support channel_binding; it is ignored here.

Usage:
  python scripts/db_connect_env_vars.py
"""
from __future__ import annotations

import os
import sys
import asyncio
import asyncpg


def _get(name: str, required: bool = True) -> str:
    val = os.getenv(name)
    if required and not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val or ""


def _ssl_required(sslmode: str) -> bool:
    return sslmode.lower() in {"require", "verify-full", "verify-ca"}


async def main() -> int:
    host = _get("PGHOST")
    db = _get("PGDATABASE")
    user = _get("PGUSER")
    password = _get("PGPASSWORD")
    sslmode = _get("PGSSLMODE", required=False) or "disable"
    # PGCHANNELBINDING is ignored by asyncpg

    print(f"host={host}, db={db}, user={user}, sslmode={sslmode}")
    try:
        conn = await asyncpg.connect(
            host=host,
            database=db,
            user=user,
            password=password,
            ssl=True if _ssl_required(sslmode) else None,
        )
        try:
            val = await conn.fetchval("SELECT 1")
            print(f"OK (SELECT 1 -> {val})")
        finally:
            await conn.close()
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        return 1
    return 0


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(main()))
