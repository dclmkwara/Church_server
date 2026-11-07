"""
Main FastAPI application entrypoint.

Production changes:
- @app.on_event("startup/shutdown") replaced with lifespan context manager
  (deprecated in FastAPI >= 0.93, silently breaks on future upgrades).
- API docs (Swagger / ReDoc) are disabled when DEBUG=False so they are not
  publicly accessible in production.
- RefreshToken model is imported at startup so SQLAlchemy includes the table
  in any Base.metadata.create_all() call (needed for the token rotation feature).
"""
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging

# ── Logging ────────────────────────────────────────────────────────────────────
setup_logging("DEBUG" if settings.DEBUG else "INFO")
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Runs startup tasks before `yield` and shutdown tasks after.
    Replaces the deprecated @app.on_event("startup/shutdown") pattern.
    """
    logger.info("Starting DCLM API (version %s, debug=%s)...", settings.VERSION, settings.DEBUG)

    # Ensure the RefreshToken table is registered with SQLAlchemy metadata
    # (it is imported here so Alembic autogenerate picks it up too)
    import app.models.refresh_token  # noqa: F401

    # Test database connectivity
    from app.db.session import test_connection
    if await test_connection():
        logger.info("✅ Database connection successful")
    else:
        logger.error(
            "❌ Database connection failed — check DATABASE_URL and network access"
        )

    # Start background scheduler (nightly MV refresh, announcement cleanup)
    from app.core.scheduler import start_scheduler
    start_scheduler()
    logger.info("✅ Background scheduler started")

    yield  # Application is running

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("Shutting down DCLM API...")
    from app.core.scheduler import shutdown_scheduler
    shutdown_scheduler()
    try:
        from app.frontend.dclm_admin.backend import close_async_http_client
        await close_async_http_client()
    except Exception:
        pass
    logger.info("✅ Shutdown complete")


# ── Application ────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for Deeper Life Church Management System",
    version=settings.VERSION,
    lifespan=lifespan,
    # Disable interactive docs in production — they expose all endpoints and
    # schema details publicly. Set DEBUG=True in .env for local development.
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)


@app.middleware("http")
async def clear_request_scope_context(request, call_next):
    """Keep authorization scope metadata isolated to one HTTP request."""
    from app.db.filters import reset_scope_context

    context_token = reset_scope_context()
    try:
        return await call_next(request)
    finally:
        reset_scope_context(context_token)


@app.middleware("http")
async def trace_dashboard_api_request(request, call_next):
    """Collect per-query details for dashboard API calls across process hops."""
    request_id = request.headers.get("x-dclm-request-id")
    if not request_id or not request.url.path.startswith(settings.API_V1_PREFIX):
        return await call_next(request)
    from app.core import dashboard_perf

    trace, token = dashboard_perf.begin_correlated_api_trace(request_id)
    if trace is None:
        return await call_next(request)
    started = __import__("time").perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        dashboard_perf.finish_trace(trace, token, render_ms=(__import__("time").perf_counter() - started) * 1000)

# ── CORS ───────────────────────────────────────────────────────────────────────
raw_origins = settings.BACKEND_CORS_ORIGINS
if raw_origins:
    try:
        allowed_origins = (
            json.loads(raw_origins)
            if raw_origins.strip().startswith("[")
            else [o.strip() for o in raw_origins.split(",") if o.strip()]
        )
    except json.JSONDecodeError:
        allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    if "*" in allowed_origins:
        raise ValueError("BACKEND_CORS_ORIGINS must list explicit origins; wildcard is not allowed")
else:
    # No configured browser origins means cross-origin browser requests are
    # denied. Set BACKEND_CORS_ORIGINS explicitly for the deployed frontend.
    allowed_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    # Never send credentials with a wildcard origin — browsers reject it anyway
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-DCLM-Request-ID"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
from app.api.v1.routes import auth, users, workers, hierarchy, user_approval
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(user_approval.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["User Approval"])
app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["Users"])
app.include_router(workers.router, prefix=f"{settings.API_V1_PREFIX}/workers", tags=["Workers"])

from app.api.v1.routes import fellowship_activities
app.include_router(fellowship_activities.router, prefix=f"{settings.API_V1_PREFIX}/fellowships", tags=["Fellowship Activities"])

app.include_router(hierarchy.router, prefix=f"{settings.API_V1_PREFIX}", tags=["Hierarchy"])

from app.api.v1.routes import programs
app.include_router(programs.router, prefix=f"{settings.API_V1_PREFIX}/programs", tags=["Programs"])

from app.api.v1.routes import official_appointments
app.include_router(official_appointments.router, prefix=f"{settings.API_V1_PREFIX}/official-appointments", tags=["Officials"])

from app.api.v1.routes import counts
app.include_router(counts.router, prefix=f"{settings.API_V1_PREFIX}/counts", tags=["Counts"])

from app.api.v1.routes import offerings
app.include_router(offerings.router, prefix=f"{settings.API_V1_PREFIX}/offerings", tags=["Offerings"])

from app.api.v1.routes import tithes
app.include_router(tithes.router, prefix=f"{settings.API_V1_PREFIX}/tithes", tags=["Tithes"])

from app.api.v1.routes import records, newcomers, converts
app.include_router(records.router, prefix=f"{settings.API_V1_PREFIX}/records", tags=["Records"])
app.include_router(newcomers.router, prefix=f"{settings.API_V1_PREFIX}/newcomers", tags=["Newcomers"])
app.include_router(converts.router, prefix=f"{settings.API_V1_PREFIX}/converts", tags=["Converts"])

from app.api.v1.routes import attendance
app.include_router(attendance.router, prefix=f"{settings.API_V1_PREFIX}/attendance", tags=["Worker Attendance"])

from app.api.v1.routes import sync
app.include_router(sync.router, prefix=f"{settings.API_V1_PREFIX}/sync", tags=["Offline Sync"])

from app.api.v1.routes import reports
app.include_router(reports.router, prefix=f"{settings.API_V1_PREFIX}/reports", tags=["Reports"])

from app.api.v1.routes import announcements
from app.api.v1.routes import broadcasts
app.include_router(announcements.router, prefix=f"{settings.API_V1_PREFIX}/announcements", tags=["Announcements"])
app.include_router(broadcasts.router, prefix=f"{settings.API_V1_PREFIX}/broadcasts", tags=["Broadcasts"])

from app.api.v1.routes import information
app.include_router(information.router, prefix=f"{settings.API_V1_PREFIX}/information", tags=["Information"])

from app.api.v1.routes import system
app.include_router(system.router, prefix=f"{settings.API_V1_PREFIX}/system", tags=["System"])

from app.api.v1.routes import statistics
app.include_router(statistics.router, prefix=f"{settings.API_V1_PREFIX}/statistics", tags=["Statistics"])

from app.api.v1.routes import dashboard
app.include_router(dashboard.router, prefix=f"{settings.API_V1_PREFIX}/dashboard", tags=["Dashboard"])

from app.api.v1.routes import recovery
app.include_router(recovery.router, prefix=f"{settings.API_V1_PREFIX}/recovery", tags=["Recovery"])

from app.api.v1.routes import notifications
app.include_router(notifications.router, prefix=f"{settings.API_V1_PREFIX}/notifications", tags=["Notifications"])

from app.api.v1.routes import rbac
app.include_router(rbac.router, prefix=f"{settings.API_V1_PREFIX}/rbac", tags=["RBAC"])

from app.api.v1.routes import approvals
app.include_router(approvals.router, prefix=f"{settings.API_V1_PREFIX}/approvals", tags=["Approvals"])

from app.api.v1.routes import app_version
app.include_router(app_version.router, prefix=f"{settings.API_V1_PREFIX}/app-versions", tags=["App Versions"])

from app.api.v1.routes import media
app.include_router(media.router, prefix=f"{settings.API_V1_PREFIX}/media", tags=["Media"])

from app.api.v1.routes import public
app.include_router(public.router, prefix=f"{settings.API_V1_PREFIX}/public", tags=["Public"])

from app.api.v1.routes import websocket as websocket_routes
app.include_router(websocket_routes.router, tags=["WebSocket"])

from app.api.v1.routes import location_profile
app.include_router(location_profile.router, prefix=f"{settings.API_V1_PREFIX}/locations", tags=["Hierarchy"])

from app.api.v1.routes import church_members
app.include_router(church_members.router, prefix=f"{settings.API_V1_PREFIX}/members", tags=["Records"])

from app.api.v1.routes.transfers import router as transfers_router, absence_router
app.include_router(transfers_router, prefix=f"{settings.API_V1_PREFIX}/transfers", tags=["Workers"])
app.include_router(absence_router, prefix=f"{settings.API_V1_PREFIX}/attendance/absence-notices", tags=["Worker Attendance"])

from app.api.v1.routes import bulk_import
app.include_router(bulk_import.router, prefix=f"{settings.API_V1_PREFIX}/bulk", tags=["Bulk Import"])


# ── Health & API Info endpoints ────────────────────────────────────────────────

@app.get("/api", tags=["Health"])
async def api_info():
    """API health and version info — always public."""
    return {
        "message": "DCLM Church Management API is running 🚀",
        "version": settings.VERSION,
        # Only advertise docs URL when they are actually enabled
        **({"docs": "/docs"} if settings.DEBUG else {}),
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check — database connectivity included."""
    from app.db.session import test_connection
    db_ok = await test_connection()
    return {
        "status": "healthy" if db_ok else "unhealthy",
        "database": "connected" if db_ok else "disconnected",
        "version": settings.VERSION,
    }


@app.get("/live", tags=["Health"])
async def liveness_check():
    """Process liveness probe; independent of database availability."""
    return {"status": "alive", "version": settings.VERSION}


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe for serving API traffic, including database access."""
    from fastapi.responses import JSONResponse
    from app.db.session import test_connection

    db_ok = await test_connection()
    payload = {
        "status": "ready" if db_ok else "not_ready",
        "database": "connected" if db_ok else "disconnected",
        "version": settings.VERSION,
    }
    return JSONResponse(status_code=200 if db_ok else 503, content=payload)


# ── Mount Faststrap Frontend for Single-Instance Deployment ────────────────────
try:
    from app.frontend.dclm_admin.app_factory import app as frontend_app
    from app.frontend.dclm_admin.components.error_pages import not_found_response, server_error_response
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    @app.exception_handler(404)
    async def custom_404_handler(request: Request, exc: Exception):
        if request.url.path.startswith(settings.API_V1_PREFIX) or request.url.path.startswith("/api"):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        return not_found_response(request, exc)

    @app.exception_handler(500)
    async def custom_500_handler(request: Request, exc: Exception):
        logger.error("Unhandled error: %s", exc, exc_info=True)
        if request.url.path.startswith(settings.API_V1_PREFIX) or request.url.path.startswith("/api"):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        return server_error_response(request, exc)

    app.mount("/", frontend_app)
    logger.info("✅ Faststrap Admin Frontend successfully mounted at root /")
except Exception as exc:
    logger.error("Could not mount Faststrap frontend: %s", exc, exc_info=True)
