"""
Database session management with async SQLAlchemy.
"""
import logging
import ssl
import time
import uuid
from typing import AsyncGenerator
from urllib.parse import quote

from sqlalchemy import event, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session
from sqlalchemy import inspect as sa_inspect

from app.core.config import settings

logger = logging.getLogger(__name__)

# Operational setup changes are captured centrally so API and admin-UI paths
# cannot accidentally bypass the audit trail. Only non-sensitive fields are
# included; free-text reasons, contact data and announcement bodies are never
# copied into this general-purpose log.
_AUDITED_FIELDS = {
    "program_campaigns": ("title", "campaign_code", "domain_id", "event_mode", "reporting_scope", "status", "start_date", "end_date", "path"),
    "program_events": ("title", "campaign_id", "program_type_id", "date", "event_mode", "reporting_scope", "approval_status", "path"),
    "event_assignments": ("event_id", "worker_id", "assignment_type", "source_role", "status", "path"),
    "worker_transfers": ("from_location_id", "to_location_id", "status", "workflow_stage", "current_level"),
    "worker_removal_requests": ("worker_id", "status", "current_level", "path"),
    "status_change_requests": ("worker_id", "old_status", "new_status", "status", "current_level", "path"),
    "transfer_requests": ("worker_id", "from_location_id", "to_location_id", "status", "current_level", "workflow_stage", "path"),
    "nations": ("country_name", "nation_code", "continent", "path"),
    "states": ("state_name", "state_code", "path", "nation_id"),
    "regions": ("region_name", "region_code", "path", "state_id"),
    "dclm_groups": ("group_name", "group_code", "path", "region_id"),
    "locations": ("location_name", "location_code", "path", "group_id", "is_active"),
    "fellowships": ("fellowship_name", "fellowship_code", "path", "location_id"),
}


def _audit_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@event.listens_for(Session, "before_flush")
def _audit_governance_setup_changes(session: Session, flush_context, instances) -> None:
    actor = session.info.get("audit_actor")
    if not actor or session.info.get("_adding_governance_audit"):
        return
    from app.models.audit import AuditLog

    pending = []
    for obj in tuple(session.new) + tuple(session.dirty) + tuple(session.deleted):
        table = getattr(getattr(obj, "__table__", None), "name", "")
        fields = _AUDITED_FIELDS.get(table)
        if not fields:
            continue
        state = sa_inspect(obj)
        if obj in session.deleted:
            action = "DELETE"
            changed = {key: _audit_value(getattr(obj, key, None)) for key in fields if hasattr(obj, key)}
        elif obj in session.new:
            action = "CREATE"
            changed = {key: _audit_value(getattr(obj, key, None)) for key in fields if hasattr(obj, key)}
        else:
            changed = {}
            for key in fields:
                if key not in state.attrs:
                    continue
                history = state.attrs[key].history
                if history.has_changes():
                    changed[key] = {
                        "before": _audit_value(history.deleted[0] if history.deleted else None),
                        "after": _audit_value(history.added[0] if history.added else getattr(obj, key, None)),
                    }
            if not changed:
                continue
            action = "UPDATE"
        try:
            resource_id = getattr(obj, "id", None)
            if resource_id is None and table in {"program_campaigns", "program_events", "event_assignments"}:
                resource_id = uuid.uuid4()
                setattr(obj, "id", resource_id)
            if resource_id is None:
                resource_id = getattr(obj, "worker_id", None) or getattr(obj, "location_id", None)
        except Exception:
            resource_id = None
        scope_path = getattr(obj, "path", None) or actor.get("scope_path", "")
        details = {
            "actor_name": actor.get("actor_name", "User"),
            "role_name": actor.get("role_name", ""),
            "role_score": actor.get("role_score", 0),
            "scope_path": str(scope_path or ""),
            "actor_scope_path": actor.get("scope_path", ""),
            "fields": changed,
        }
        pending.append(AuditLog(
            user_id=actor.get("user_id"), action=f"{action}_{table.upper()}",
            resource_type=table, resource_id=str(resource_id or ""), changes=details,
        ))
    if pending:
        session.info["_adding_governance_audit"] = True
        session.add_all(pending)
        session.info.pop("_adding_governance_audit", None)


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


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def _dashboard_query_timer_start(conn, cursor, statement, parameters, context, executemany) -> None:
    # Do not retain SQL or pay timing overhead outside the explicitly enabled
    # dashboard trace. SQL text is recorded only for these development timings.
    try:
        from app.core.program_page_perf import current_trace as current_program_trace
        if current_program_trace() is not None:
            context._dclm_program_page_query_started = time.perf_counter()
    except Exception:
        pass
    try:
        from app.core.dashboard_perf import current_trace
        if current_trace() is not None:
            context._dclm_dashboard_query_started = time.perf_counter()
    except Exception:
        return


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def _dashboard_query_timer_finish(conn, cursor, statement, parameters, context, executemany) -> None:
    program_started = getattr(context, "_dclm_program_page_query_started", None)
    if program_started is not None:
        try:
            from app.core.program_page_perf import record_database_query
            record_database_query((time.perf_counter() - program_started) * 1000)
        finally:
            context._dclm_program_page_query_started = None
    started = getattr(context, "_dclm_dashboard_query_started", None)
    if started is None:
        return
    try:
        from app.core.dashboard_perf import record_database_query
        record_database_query(statement, (time.perf_counter() - started) * 1000)
    finally:
        context._dclm_dashboard_query_started = None

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@event.listens_for(Session, "after_begin")
def _restore_rls_context(session: Session, transaction, connection) -> None:
    """Reapply request RLS settings after any route-level commit starts a new transaction."""
    context = session.info.get("_rls_context")
    if not context:
        return
    connection.execute(
        text(
            "SELECT set_config('app.scope_path', :scope_path, true), "
            "set_config('app.role_score', :role_score, true), "
            "set_config('app.continent', :continent, true), "
            "set_config('app.user_id', :user_id, true), "
            "set_config('app.nation_paths', :nation_paths, true), "
            "set_config('app.auth_email', :auth_email, true), "
            "set_config('app.reset_token', :reset_token, true)"
        ),
        context,
    )


async def _set_rls_values(session: AsyncSession, **values: str) -> None:
    context = session.sync_session.info.setdefault("_rls_context", {
        "scope_path": "",
        "role_score": "0",
        "continent": "",
        "user_id": "",
        "nation_paths": "",
        "auth_email": "",
        "reset_token": "",
    })
    context.update(values)
    # When context is installed before the first statement, SQLAlchemy's
    # ``after_begin`` hook applies it on the connection. Executing this query
    # too would send the identical settings twice. If the transaction already
    # has a checked-out connection, update that transaction immediately.
    transaction = session.sync_session.get_transaction()
    if transaction is None or not transaction._connections:
        return
    await session.execute(
        text(
            "SELECT set_config('app.scope_path', :scope_path, true), "
            "set_config('app.role_score', :role_score, true), "
            "set_config('app.continent', :continent, true), "
            "set_config('app.user_id', :user_id, true), "
            "set_config('app.nation_paths', :nation_paths, true), "
            "set_config('app.auth_email', :auth_email, true), "
            "set_config('app.reset_token', :reset_token, true)"
        ),
        context,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session.
    The async context manager already closes the session on exit.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def inject_scope(
    session: AsyncSession,
    scope_path: str,
    *,
    role_score: int,
    continent: str | None = None,
    user_id: str | None = None,
    nation_paths: tuple[str, ...] = (),
) -> None:
    """
    Inject scope path into the session for Row-Level Security.

    Args:
        session: Database session
        scope_path: ltree path for scope filtering (e.g., 'org.234.kw.iln.ile')
    """
    await _set_rls_values(
        session,
        scope_path=scope_path,
        role_score=str(role_score),
        continent=(continent or "").strip(),
        user_id=str(user_id or ""),
        # `|` cannot occur in an ltree label; the policy migration splits
        # this value and fails closed when it is empty for enterprise scope.
        nation_paths="|".join(nation_paths),
        auth_email="",
        reset_token="",
    )


async def inject_auth_user(session: AsyncSession, user_id: str) -> None:
    """Set the verified token subject before the first RLS-protected user read."""
    await _set_rls_values(session, user_id=str(user_id))


async def inject_auth_email(session: AsyncSession, email: str) -> None:
    """Permit a single email row during password authentication/reset lookup."""
    await _set_rls_values(session, auth_email=email.strip().lower())


async def inject_continent(session: AsyncSession, continent: str) -> None:
    """Set the continent resolved from a level-8 user's home Nation."""
    await _set_rls_values(session, continent=continent.strip())


async def inject_reset_token(session: AsyncSession, token: str) -> None:
    """Limit anonymous reset-token operations to the presented token row."""
    await _set_rls_values(session, reset_token=token)


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
        # Driver exceptions can contain connection URLs. Keep the failure
        # observable without ever writing credentials or URL details to logs.
        logger.error("Database connection failed (exception_type=%s)", type(exc).__name__)
        return False
