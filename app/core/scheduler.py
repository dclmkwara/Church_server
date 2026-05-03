"""
Background jobs for database maintenance using APScheduler.

Production changes:
- Postgres advisory lock prevents duplicate job execution across multiple
  uvicorn workers — no Redis or external coordinator required.
- datetime.utcnow() replaced with datetime.now(timezone.utc) (deprecated in Python 3.12+).
- Materialized view refresh uses a dedicated AUTOCOMMIT connection so that
  CONCURRENT refresh can run outside of a transaction block.
"""
import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal, engine
from app.models.announcement import Announcement

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

# Arbitrary stable integer keys for Postgres advisory locks.
# Use unique values per job so they don't interfere with each other.
_LOCK_REFRESH_MV = 20260501_01
_LOCK_DEACTIVATE = 20260501_02


async def _try_advisory_lock(conn, lock_id: int) -> bool:
    """Attempt to acquire a session-level Postgres advisory lock.

    Returns True if the lock was acquired, False if another session holds it.
    This is the multi-worker guard — if worker-2 fires the same job at the
    same time as worker-1, worker-2 will see False and skip gracefully.
    """
    result = await conn.execute(
        text("SELECT pg_try_advisory_lock(:id)"), {"id": lock_id}
    )
    return bool(result.scalar())


async def _release_advisory_lock(conn, lock_id: int) -> None:
    """Release a previously acquired advisory lock."""
    await conn.execute(
        text("SELECT pg_advisory_unlock(:id)"), {"id": lock_id}
    )


async def _try_advisory_xact_lock(db: AsyncSession, lock_id: int) -> bool:
    """Attempt to acquire a transaction-scoped Postgres advisory lock."""
    result = await db.execute(
        text("SELECT pg_try_advisory_xact_lock(:id)"), {"id": lock_id}
    )
    return bool(result.scalar())


async def refresh_materialized_views() -> None:
    """
    Refresh all analytics materialized views.

    Scheduled: nightly at 02:00.

    Uses a Postgres advisory lock so only one worker in a multi-process
    deployment actually performs the refresh. The AUTOCOMMIT isolation level
    is required because REFRESH MATERIALIZED VIEW CONCURRENTLY cannot run
    inside a transaction block.
    """
    # Use a raw connection with AUTOCOMMIT so CONCURRENT refresh is allowed
    async with engine.connect() as base_conn:
        conn = await base_conn.execution_options(isolation_level="AUTOCOMMIT")

        if not await _try_advisory_lock(conn, _LOCK_REFRESH_MV):
            logger.info("refresh_materialized_views: skipped — another worker holds the lock")
            return

        try:
            logger.info("Starting materialized view refresh...")
            for view in (
                "mv_daily_counts_by_location",
                "mv_monthly_financial_summary",
                "mv_attendance_trends",
            ):
                try:
                    await conn.execute(
                        text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
                    )
                    logger.info("Refreshed %s", view)
                except Exception as exc:
                    # CONCURRENT requires a unique index — fall back to blocking refresh
                    logger.warning(
                        "CONCURRENT refresh failed for %s (%s). "
                        "Ensure a unique index exists on the view. "
                        "Falling back to blocking refresh.",
                        view, exc,
                    )
                    await conn.execute(
                        text(f"REFRESH MATERIALIZED VIEW {view}")
                    )
                    logger.info("Blocking refresh completed for %s", view)

            logger.info("All materialized views refreshed successfully")
        except Exception as exc:
            logger.error("Materialized view refresh failed: %s", exc, exc_info=True)
        finally:
            await _release_advisory_lock(conn, _LOCK_REFRESH_MV)


async def deactivate_old_announcements() -> None:
    """
    Set is_active=False on announcements older than 10 days.

    Scheduled: daily at 03:00.

    Protected by a Postgres advisory lock to prevent duplicate updates across
    multiple workers.
    """
    cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=10)

    # Run the actual update in a transactional session
    async with AsyncSessionLocal() as db:
        try:
            if not await _try_advisory_xact_lock(db, _LOCK_DEACTIVATE):
                logger.info("deactivate_old_announcements: skipped - another worker holds the lock")
                return

            stmt = (
                update(Announcement)
                .where(
                    Announcement.date < cutoff_date,
                    Announcement.is_active == True,  # noqa: E712
                )
                .values(is_active=False)
            )
            result = await db.execute(stmt)
            await db.commit()
            logger.info(
                "Deactivated %d old announcements (cutoff: %s)",
                result.rowcount, cutoff_date,
            )
        except Exception as exc:
            await db.rollback()
            logger.error("Failed to deactivate old announcements: %s", exc, exc_info=True)


def start_scheduler() -> None:
    """Register jobs and start the APScheduler instance."""
    if scheduler.running:
        logger.info("Background scheduler already running")
        return

    scheduler.add_job(
        refresh_materialized_views,
        trigger=CronTrigger(hour=2, minute=0),
        id="refresh_mv",
        name="Refresh Materialized Views",
        replace_existing=True,
    )
    scheduler.add_job(
        deactivate_old_announcements,
        trigger=CronTrigger(hour=3, minute=0),
        id="deactivate_announcements",
        name="Deactivate Old Announcements",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Background scheduler started")


def shutdown_scheduler() -> None:
    """Shut down the scheduler gracefully on application exit."""
    if not scheduler.running:
        logger.info("Background scheduler already stopped")
        return

    scheduler.shutdown()
    logger.info("Background scheduler shut down")
