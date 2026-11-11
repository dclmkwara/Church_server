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
from app.services.analytics.reporting_policy import counted_status_clause, is_counted_status

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
        """Counted submissions, grouped only within a single count group/session.

        This deliberately reads the source rows instead of the daily materialized
        view: the view cannot distinguish review state or separate services.
        Legacy rows remain individual records; split parts are summed at read time.
        """
        return await ReportService.get_count_summary_rows(
            db, scope_path, start_date, end_date, include_pending=False
        )

    @staticmethod
    async def get_count_summary_rows(
        db: AsyncSession,
        scope_path: str,
        start_date: date,
        end_date: date,
        *,
        include_pending: bool = False,
    ) -> List[DailyCountSummary]:
        """Apply the common review policy and preserve each occurrence/session."""
        query = text(f"""
            SELECT c.id::text AS count_id, c.count_group_id::text AS count_group_id,
                   cg.state AS group_state, cg.service_id,
                   c.date::date AS day, c.event_id::text AS event_id,
                   COALESCE(pe.title, pt.name, c.program_type, c.program_domain, 'Unassigned program') AS event_title,
                   COALESCE(pt.name, c.program_type, '') AS program_type,
                   c.status, c.count_mode,
                   c.location_id::text AS location_id, l.location_name,
                   c.path::text AS path, c.total,
                   c.adult_male, c.adult_female, c.youth_male, c.youth_female,
                   c.boys, c.girls
            FROM counts c
            JOIN locations l ON l.location_id = c.location_id
            LEFT JOIN count_groups cg ON cg.id = c.count_group_id
            LEFT JOIN program_events pe ON pe.id = c.event_id
            LEFT JOIN program_types pt ON pt.id = COALESCE(c.program_type_id, pe.program_type_id)
            WHERE c.date >= :start_date
              AND c.date < (CAST(:end_date AS date) + INTERVAL '1 day')
              AND c.is_deleted IS NOT TRUE
              AND (c.path <@ CAST(:scope_path AS LTREE) OR c.path = CAST(:scope_path AS LTREE))
            ORDER BY c.date DESC, c.path ASC, cg.service_id ASC, c.id ASC
        """)
        result = await db.execute(query, {
            "start_date": start_date, "end_date": end_date, "scope_path": scope_path,
        })
        raw_rows = [dict(row) for row in result.mappings()]
        buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in raw_rows:
            group_id = row.get("count_group_id")
            key = ("group", str(group_id)) if group_id else ("legacy", str(row["count_id"]))
            buckets.setdefault(key, []).append(row)

        output: list[DailyCountSummary] = []
        for rows in buckets.values():
            statuses = {str(row.get("status") or "pending").lower() for row in rows}
            if len(statuses) != 1 or any(row.get("group_state") == "conflict" for row in rows):
                continue
            status = next(iter(statuses))
            if not is_counted_status(status, include_pending):
                continue
            categories = {
                key: sum(int(row.get(key) or 0) for row in rows)
                for key in ("adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls")
            }
            first = rows[0]
            output.append(DailyCountSummary(
                day=first["day"], event_id=str(first.get("event_id") or ""),
                event_title=str(first.get("event_title") or "Unassigned program"),
                location_id=str(first["location_id"]), location_name=str(first.get("location_name") or "Unknown location"),
                path=str(first["path"]), total_attendance=sum(int(row.get("total") or 0) for row in rows),
                total_men=categories["adult_male"], total_women=categories["adult_female"],
                total_youth_male=categories["youth_male"], total_youth_female=categories["youth_female"],
                total_boys=categories["boys"], total_girls=categories["girls"], record_count=len(rows),
                service_id=str(first.get("service_id") or "main"), program_type=str(first.get("program_type") or ""),
                status=status,
            ))
        return sorted(output, key=lambda item: (item.day, item.path, item.service_id or ""), reverse=True)

    @staticmethod
    async def get_financial_summary(
        db: AsyncSession,
        scope_path: str,
        start_month: date,
        end_month: date,
    ) -> List[MonthlyFinancialSummary]:
        """Approved monthly totals restricted to the exact selected date window."""
        query = text(f"""
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
              AND {counted_status_clause('o.status')}
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
        db: AsyncSession, scope_path: str, start_date: date, end_date: date, *, include_pending: bool = False
    ) -> StringIO:
        data = await ReportService.get_count_summary_rows(
            db, scope_path, start_date, end_date, include_pending=include_pending
        )
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
