"""
Main FastAPI application entrypoint.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging_config import setup_logging
import logging

# Set up logging
setup_logging("INFO" if not settings.DEBUG else "DEBUG")
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for Deeper Life Church Management System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (will be added as we build them)
# Include routers
from app.api.v1.routes import auth, users, workers, hierarchy, user_approval
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(users.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["Users"])
app.include_router(user_approval.router, prefix=f"{settings.API_V1_PREFIX}/users", tags=["User Approval"])
app.include_router(workers.router, prefix=f"{settings.API_V1_PREFIX}/workers", tags=["Workers"])

from app.api.v1.routes import fellowship_activities
app.include_router(fellowship_activities.router, prefix=f"{settings.API_V1_PREFIX}/fellowships", tags=["Fellowship Activities"])

app.include_router(hierarchy.router, prefix=f"{settings.API_V1_PREFIX}", tags=["Hierarchy"])

from app.api.v1.routes import programs
app.include_router(programs.router, prefix=f"{settings.API_V1_PREFIX}/programs", tags=["Programs"])

from app.api.v1.routes import counts
app.include_router(counts.router, prefix=f"{settings.API_V1_PREFIX}/counts", tags=["Counts"])

from app.api.v1.routes import offerings
app.include_router(offerings.router, prefix=f"{settings.API_V1_PREFIX}/offerings", tags=["Offerings"])

from app.api.v1.routes import records
app.include_router(records.router, prefix=f"{settings.API_V1_PREFIX}/records", tags=["Records"])

from app.api.v1.routes import attendance
app.include_router(attendance.router, prefix=f"{settings.API_V1_PREFIX}/attendance", tags=["Worker Attendance"])

from app.api.v1.routes import sync
app.include_router(sync.router, prefix=f"{settings.API_V1_PREFIX}/sync", tags=["Offline Sync"])

from app.api.v1.routes import reports
app.include_router(reports.router, prefix=f"{settings.API_V1_PREFIX}/reports", tags=["Reports"])

from app.api.v1.routes import announcements
app.include_router(announcements.router, prefix=f"{settings.API_V1_PREFIX}/announcements", tags=["Announcements"])

from app.api.v1.routes import system
app.include_router(system.router, prefix=f"{settings.API_V1_PREFIX}/system", tags=["System"])

from app.api.v1.routes import statistics
app.include_router(statistics.router, prefix=f"{settings.API_V1_PREFIX}/statistics", tags=["Statistics"])

from app.api.v1.routes import recovery
app.include_router(recovery.router, prefix=f"{settings.API_V1_PREFIX}/recovery", tags=["Recovery"])

from app.api.v1.routes import notifications
app.include_router(notifications.router, prefix=f"{settings.API_V1_PREFIX}/notifications", tags=["Notifications"])

from app.api.v1.routes import rbac
app.include_router(rbac.router, prefix=f"{settings.API_V1_PREFIX}/rbac", tags=["RBAC"])

from app.api.v1.routes import media
app.include_router(media.router, prefix=f"{settings.API_V1_PREFIX}/media", tags=["Media"])

from app.api.v1.routes import public
app.include_router(public.router, prefix=f"{settings.API_V1_PREFIX}/public", tags=["Public"])



@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("Starting DCLM API...")
    
    # Test database connection
    from app.db.session import test_connection
    if await test_connection():
        logger.info("✅ Database connection successful")
    else:
        logger.error("❌ Database connection failed")
    
    # Start background scheduler
    from app.core.scheduler import start_scheduler
    start_scheduler()
    logger.info("✅ Background scheduler started")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Shutting down DCLM API...")
    
    # Shutdown background scheduler
    from app.core.scheduler import shutdown_scheduler
    shutdown_scheduler()
    logger.info("✅ Background scheduler shutdown")


@app.get("/", tags=["Health"])
async def root():
    """
    Root endpoint - API health check.
    
    Returns:
        dict: Status message
    """
    return {
        "message": "DCLM Church Management API is running 🚀",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        dict: Health status
    """
    from app.db.session import test_connection
    
    db_status = await test_connection()
    
    return {
        "status": "healthy" if db_status else "unhealthy",
        "database": "connected" if db_status else "disconnected",
        "version": "1.0.0"
    }