"""
Background jobs for database maintenance using APScheduler.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update
from app.db.session import AsyncSessionLocal
from app.services.report_service import ReportService
from app.models.announcement import Announcement
import logging

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

async def refresh_materialized_views():
    """
    Refresh all materialized views.
    Runs nightly at 2 AM.
    """
    logger.info("Starting materialized view refresh...")
    async with AsyncSessionLocal() as db:
        try:
            await ReportService.refresh_views(db)
            logger.info("Materialized views refreshed successfully")
        except Exception as e:
            logger.error(f"Failed to refresh materialized views: {e}")

async def deactivate_old_announcements():
    """
    Deactivate announcements older than 10 days.
    Runs daily.
    """
    cutoff_date = datetime.utcnow().date() - timedelta(days=10)
    async with AsyncSessionLocal() as db:
        try:
            stmt = (
                update(Announcement)
                .where(Announcement.date < cutoff_date, Announcement.is_active == True)
                .values(is_active=False)
            )
            await db.execute(stmt)
            await db.commit()
            logger.info("Old announcements deactivated")
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to deactivate old announcements: {e}")

def start_scheduler():
    """
    Start the background scheduler.
    """
    # Refresh materialized views nightly at 2 AM
    scheduler.add_job(
        refresh_materialized_views,
        trigger=CronTrigger(hour=2, minute=0),
        id="refresh_mv",
        name="Refresh Materialized Views",
        replace_existing=True
    )

    scheduler.add_job(
        deactivate_old_announcements,
        trigger=CronTrigger(hour=3, minute=0),
        id="deactivate_announcements",
        name="Deactivate Old Announcements",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Background scheduler started")

def shutdown_scheduler():
    """
    Shutdown the scheduler gracefully.
    """
    scheduler.shutdown()
    logger.info("Background scheduler shutdown")
