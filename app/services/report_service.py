"""
Report service — materialized view queries and CSV/Excel/PDF export helpers.

Production changes:
- refresh_views() now uses engine.connect() with isolation_level="AUTOCOMMIT"
  so REFRESH MATERIALIZED VIEW CONCURRENTLY can run outside a transaction block.
  The original approach (refreshing inside a SQLAlchemy session with
  autocommit=False) caused the CONCURRENT variant to silently fail and fall
  back to a blocking refresh that locked readers.
- All print() calls replaced with logger.error()/logger.warning().
- Per-view exception handling so a failure on one view doesn't abort the others.
"""
import logging
from datetime import date
from io import BytesIO, StringIO
from typing import Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.schemas.report import DailyCountSummary, MonthlyFinancialSummary, AttendanceTrend

logger = logging.getLogger(__name__)


class ReportService:

    # ── Materialized view queries ──────────────────────────────────────────────

    @staticmethod
    async def get_daily_counts(
        db: AsyncSession,
        scope_path: str,
        start_date: date,
        end_date: date,
    ) -> List[DailyCountSummary]:
        """Daily count summaries from the mv_daily_counts_by_location view."""
        query = text("""
            SELECT * FROM mv_daily_counts_by_location
            WHERE day >= :start_date AND day <= :end_date
              AND (path <@ :scope_path::ltree OR path = :scope_path::ltree)
            ORDER BY day DESC, path ASC
        """)
        result = await db.execute(
            query, {"start_date": start_date, "end_date": end_date, "scope_path": scope_path}
        )
        return [DailyCountSummary.model_validate(row) for row in result.mappings()]

    @staticmethod
    async def get_financial_summary(
        db: AsyncSession,
        scope_path: str,
        start_month: date,
        end_month: date,
    ) -> List[MonthlyFinancialSummary]:
        """Monthly financial summary from the mv_monthly_financial_summary view."""
        query = text("""
            SELECT * FROM mv_monthly_financial_summary
            WHERE month >= :start_month AND month <= :end_month
              AND (path <@ :scope_path::ltree OR path = :scope_path::ltree)
            ORDER BY month DESC, path ASC
        """)
        result = await db.execute(
            query, {"start_month": start_month, "end_month": end_month, "scope_path": scope_path}
        )
        return [MonthlyFinancialSummary.model_validate(row) for row in result.mappings()]

    @staticmethod
    async def get_attendance_trends(
        db: AsyncSession,
        scope_path: str,
        start_week: date,
        end_week: date,
    ) -> List[AttendanceTrend]:
        """Worker attendance trends from the mv_attendance_trends view."""
        query = text("""
            SELECT * FROM mv_attendance_trends
            WHERE week >= :start_week AND week <= :end_week
              AND (path <@ :scope_path::ltree OR path = :scope_path::ltree)
            ORDER BY week DESC, path ASC
        """)
        result = await db.execute(
            query, {"start_week": start_week, "end_week": end_week, "scope_path": scope_path}
        )
        return [AttendanceTrend.model_validate(row) for row in result.mappings()]

    # ── Materialized view refresh ──────────────────────────────────────────────

    @staticmethod
    async def refresh_views(db: AsyncSession) -> None:
        """
        Refresh all three analytics materialized views.

        This method is kept for compatibility with the /reports/refresh route.
        The scheduled nightly refresh (scheduler.py) uses its own AUTOCOMMIT
        connection with an advisory lock.

        For manual refreshes triggered through the API we also use AUTOCOMMIT
        so CONCURRENT refresh can execute outside a transaction.  Each view is
        handled independently so a failure on one doesn't abort the others.
        """
        from app.db.session import engine

        views = [
            "mv_daily_counts_by_location",
            "mv_monthly_financial_summary",
            "mv_attendance_trends",
        ]

        async with engine.connect() as conn:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            for view in views:
                try:
                    await conn.execute(
                        text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
                    )
                    logger.info("Refreshed materialized view: %s", view)
                except Exception as exc:
                    # CONCURRENT requires a unique index on the view.
                    # If the index doesn't exist yet, fall back to blocking refresh
                    # and log clearly so the developer knows what needs fixing.
                    logger.warning(
                        "CONCURRENT refresh failed for %s — ensure a unique index exists. "
                        "Falling back to blocking refresh. Error: %s",
                        view, exc,
                    )
                    try:
                        await conn.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))
                        logger.info("Blocking refresh completed for %s", view)
                    except Exception as fallback_exc:
                        logger.error(
                            "Both CONCURRENT and blocking refresh failed for %s: %s",
                            view, fallback_exc, exc_info=True,
                        )

    # ── CSV helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_csv(rows: List[dict], headers: List[str]) -> StringIO:
        import csv
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        output.seek(0)
        return output

    @staticmethod
    async def export_counts_csv(
        db: AsyncSession, scope_path: str, start_date: date, end_date: date
    ) -> StringIO:
        data = await ReportService.get_daily_counts(db, scope_path, start_date, end_date)
        rows = [item.model_dump() for item in data]
        if not rows:
            return ReportService._generate_csv([], [])
        return ReportService._generate_csv(rows, list(rows[0].keys()))

    @staticmethod
    async def export_financial_csv(
        db: AsyncSession, scope_path: str, start_date: date, end_date: date
    ) -> StringIO:
        data = await ReportService.get_financial_summary(db, scope_path, start_date, end_date)
        rows = [item.model_dump() for item in data]
        if not rows:
            return ReportService._generate_csv([], [])
        return ReportService._generate_csv(rows, list(rows[0].keys()))

    @staticmethod
    async def export_attendance_csv(
        db: AsyncSession, scope_path: str, start_date: date, end_date: date
    ) -> StringIO:
        data = await ReportService.get_attendance_trends(db, scope_path, start_date, end_date)
        rows = [item.model_dump() for item in data]
        if not rows:
            return ReportService._generate_csv([], [])
        return ReportService._generate_csv(rows, list(rows[0].keys()))
