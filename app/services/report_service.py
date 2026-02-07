from datetime import date, datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.schemas.report import DailyCountSummary, MonthlyFinancialSummary, AttendanceTrend

class ReportService:
    @staticmethod
    async def get_daily_counts(
        db: AsyncSession, 
        scope_path: str, 
        start_date: date, 
        end_date: date
    ) -> List[DailyCountSummary]:
        """
        Get daily count summaries filtered by scope and date range.
        Uses materialized view for performance.
        """
        query = text("""
            SELECT * FROM mv_daily_counts_by_location
            WHERE day >= :start_date AND day <= :end_date
            AND (path <@ :scope_path::ltree OR path = :scope_path::ltree)
            ORDER BY day DESC, path ASC
        """)
        
        result = await db.execute(query, {
            "start_date": start_date,
            "end_date": end_date,
            "scope_path": scope_path
        })
        
        return [DailyCountSummary.model_validate(row) for row in result.mappings()]

    @staticmethod
    async def get_financial_summary(
        db: AsyncSession, 
        scope_path: str, 
        start_month: date, 
        end_month: date
    ) -> List[MonthlyFinancialSummary]:
        """
        Get monthly financial keys filtered by scope.
        """
        query = text("""
            SELECT * FROM mv_monthly_financial_summary
            WHERE month >= :start_month AND month <= :end_month
            AND (path <@ :scope_path::ltree OR path = :scope_path::ltree)
            ORDER BY month DESC, path ASC
        """)
        
        # Ensure dates are compatible with timestamp if needed
        # Postgres can usually compare date and timestamp
        result = await db.execute(query, {
            "start_month": start_month,
            "end_month": end_month,
            "scope_path": scope_path
        })
        
        return [MonthlyFinancialSummary.model_validate(row) for row in result.mappings()]

    @staticmethod
    async def get_attendance_trends(
        db: AsyncSession, 
        scope_path: str, 
        start_week: date, 
        end_week: date
    ) -> List[AttendanceTrend]:
        """
        Get worker attendance trends filtered by scope.
        """
        query = text("""
            SELECT * FROM mv_attendance_trends
            WHERE week >= :start_week AND week <= :end_week
            AND (path <@ :scope_path::ltree OR path = :scope_path::ltree)
            ORDER BY week DESC, path ASC
        """)
        
        result = await db.execute(query, {
            "start_week": start_week,
            "end_week": end_week,
            "scope_path": scope_path
        })
        
        return [AttendanceTrend.model_validate(row) for row in result.mappings()]

    @staticmethod
    async def refresh_views(db: AsyncSession):
        """
        Refresh all materialized views concurrently.
        """
        try:
             # Concurrent refresh cannot run in transaction block in some scenarios, 
             # but SQLAlchemy usually handles execution fine if not explicitly in a block unless config prevents
             # If asyncpg complains, we might need isolation level autocommit.
            await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_counts_by_location"))
            await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_monthly_financial_summary"))
            await db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_attendance_trends"))
            await db.commit() # Ensure it persists
        except Exception as e:
            # If concurrent fails (e.g. no unique index which we should have, or not populated yet)
            print(f"Concurrent refresh failed: {e}. Trying non-concurrent.")
            await db.execute(text("REFRESH MATERIALIZED VIEW mv_daily_counts_by_location"))
            await db.execute(text("REFRESH MATERIALIZED VIEW mv_monthly_financial_summary"))
            await db.execute(text("REFRESH MATERIALIZED VIEW mv_attendance_trends"))
            await db.commit()

    @staticmethod
    def generate_csv_buffer(data: List[dict], headers: List[str]) -> Any:
        """
        Generate CSV buffer from data.
        """
        import io
        import csv
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        for row in data:
            writer.writerow(row)
        output.seek(0)
        return output

    @staticmethod
    async def export_counts_csv(
        db: AsyncSession, 
        scope_path: str, 
        start_date: date, 
        end_date: date
    ):
        """
        Export counts to CSV.
        """
        data = await ReportService.get_daily_counts(db, scope_path, start_date, end_date)
        # Convert pydantic to dicts
        rows = [item.model_dump() for item in data]
        if not rows:
            return ReportService.generate_csv_buffer([], [])
            
        headers = list(rows[0].keys())
        return ReportService.generate_csv_buffer(rows, headers)
