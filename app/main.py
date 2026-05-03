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
else:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    # Never send credentials with a wildcard origin — browsers reject it anyway
    allow_credentials=allowed_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(announcements.router, prefix=f"{settings.API_V1_PREFIX}/announcements", tags=["Announcements"])

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


# ── Health endpoints ───────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    """API health check — always public."""
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
