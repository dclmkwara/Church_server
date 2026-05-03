"""
Database session management with async SQLAlchemy.
"""
import logging
import ssl
from typing import AsyncGenerator
from urllib.parse import quote

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)


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


# URL normalisation
# Cloud database providers often provide postgresql:// but asyncpg needs postgresql+asyncpg://
_db_url = _quote_database_url_password(settings.DATABASE_URL)
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql+asyncpg://", 1)

# Strip query-string keys that asyncpg doesn't accept (sslmode, channel_binding)
_ssl_required = False
_ssl_verify = False
_uses_pooler = False
try:
    _url_obj = make_url(_db_url)
    _query = dict(_url_obj.query or {})
    _host = _url_obj.host or ""
    _uses_pooler = "pooler.supabase" in _host
    if "supabase.com" in _host:
        _ssl_required = True
    _sslmode = _query.get("sslmode")
    if _sslmode:
        _sslmode_value = str(_sslmode).lower()
        _ssl_required = _sslmode_value in {"require", "verify-full", "verify-ca"}
        _ssl_verify = _sslmode_value in {"verify-full", "verify-ca"}
    if _uses_pooler:
        _query.setdefault("prepared_statement_cache_size", "0")
    _filtered_query = {k: v for k, v in _query.items() if k not in {"sslmode", "channel_binding"}}
    if _filtered_query != _query:
        _url_obj = _url_obj.set(query=_filtered_query)
        _db_url = _url_obj.render_as_string(hide_password=False)
except Exception:
    _ssl_required = False

_ssl_context = None
if _ssl_required:
    _ssl_context = ssl.create_default_context()
    if not _ssl_verify:
        _ssl_context.check_hostname = False
        _ssl_context.verify_mode = ssl.CERT_NONE


# Async engine
# Pool sizes come from settings so they can be tuned per deployment without a
# code change; just set DB_POOL_SIZE / DB_MAX_OVERFLOW in .env.
engine = create_async_engine(
    _db_url,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    pool_timeout=30,
    connect_args={
        "timeout": 30,
        "command_timeout": 60,
        **({"ssl": _ssl_context} if _ssl_context else {}),
        **({"statement_cache_size": 0} if _uses_pooler else {}),
    },
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.
    The async context manager already closes the session on exit.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def inject_scope(session: AsyncSession, scope_path: str) -> None:
    """
    Inject scope path into the session for Row-Level Security.

    Args:
        session: Database session
        scope_path: ltree path for scope filtering (e.g., 'org.234.kw.iln.ile')
    """
    await session.execute(
        text("SELECT set_config('app.scope_path', :path, true)"),
        {"path": scope_path},
    )


async def test_connection() -> bool:
    """
    Test database connectivity. Used at startup.

    Returns:
        bool: True if a basic query succeeds.
    """
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as exc:
        logger.error("Database connection failed: %s", exc)
        return False
