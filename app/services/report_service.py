"""
Report service — materialized view queries and CSV/Excel/PDF export helpers.

Production changes:
- Manual and scheduled view refreshes share an advisory lock and use
  REFRESH MATERIALIZED VIEW CONCURRENTLY without a blocking fallback.
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
              AND (path <@ CAST(:scope_path AS LTREE) OR path = CAST(:scope_path AS LTREE))
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
        """Approved monthly totals restricted to the exact selected date window."""
        query = text("""
            SELECT date_trunc('month', o.date) AS month,
                   o.location_id,
                   l.location_name,
                   o.path::text AS path,
                   COALESCE(SUM(o.amount), 0)::float AS total_amount,
                   COALESCE(SUM(o.amount), 0)::text AS total_amount_exact,
                   COUNT(*) AS transaction_count
            FROM offerings o
            JOIN locations l ON l.location_id = o.location_id
            WHERE o.date >= :start_month
              AND o.date < (CAST(:end_month AS date) + INTERVAL '1 day')
              AND o.is_deleted = FALSE
              AND o.status = 'approved'
              AND (o.path::ltree <@ CAST(:scope_path AS LTREE) OR o.path::ltree = CAST(:scope_path AS LTREE))
            GROUP BY date_trunc('month', o.date), o.location_id, l.location_name, o.path
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
              AND (path <@ CAST(:scope_path AS LTREE) OR path = CAST(:scope_path AS LTREE))
            ORDER BY week DESC, path ASC
        """)
        result = await db.execute(
            query, {"start_week": start_week, "end_week": end_week, "scope_path": scope_path}
        )
        return [AttendanceTrend.model_validate(row) for row in result.mappings()]

    # ── Materialized view refresh ──────────────────────────────────────────────

    @staticmethod
    async def refresh_views() -> dict[str, str]:
        """
        Refresh all three analytics materialized views.

        Manual and scheduled refreshes share the same PostgreSQL advisory lock
        and AUTOCOMMIT connection. Failed concurrent refreshes are reported;
        the code never falls back to a blocking refresh.
        """
        from app.core.scheduler import refresh_materialized_views
        return await refresh_materialized_views(raise_on_error=True)

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
