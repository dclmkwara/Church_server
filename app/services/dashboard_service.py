"""
Dashboard service — aggregated analytics for the admin dashboard.

Production changes:
- Shared scope_filter imported from app.db.filters.
- Queries are kept sequential on the request AsyncSession; SQLAlchemy does not
  support concurrent operations on one AsyncSession.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, cast, extract, func, select, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.filters import scope_filter as _scope_filter
from app.models.approvals import StatusChangeRequest, TransferRequest, WorkerRemovalRequest
from app.models.attendance import WorkerAttendance
from app.models.church_member import ChurchMember
from app.models.counts import Count
from app.models.offerings import Offering
from app.models.programs import ProgramDomain, ProgramEvent, ProgramType
from app.models.records import Record
from app.models.user import User, Worker
from app.services.worker_meeting_analytics import worker_meeting_analytics


def _status_case(column, expected: str):
    return cast(case((column == expected, 1), else_=0), Integer)


class DashboardService:

    @staticmethod
    async def get_summary(db, scope_path: str, *, location_id=None, weeks: int = 4, latest_date: date | None = None) -> dict[str, Any]:
        mf = [_scope_filter(ChurchMember.path, scope_path), ChurchMember.is_deleted == False]
        wf = [_scope_filter(Worker.path, scope_path), Worker.is_deleted == False]
        rf = [_scope_filter(Record.path, scope_path), Record.is_deleted == False]
        cf = [_scope_filter(Count.path, scope_path), Count.is_deleted == False]
        uf = [_scope_filter(User.path, scope_path), User.is_deleted == False]
        tf = [_scope_filter(TransferRequest.path, scope_path), TransferRequest.status.in_(("pending", "pending_region"))]
        sf = [_scope_filter(StatusChangeRequest.path, scope_path), StatusChangeRequest.status == "pending"]
        rmf = [_scope_filter(WorkerRemovalRequest.path, scope_path), WorkerRemovalRequest.status.in_(("pending", "escalated"))]
        of = [_scope_filter(Offering.path, scope_path), Offering.is_deleted == False, Offering.status == "approved"]
        pending_count_filters = [_scope_filter(Count.path, scope_path), Count.is_deleted == False, Count.status.in_(("pending", "corrected"))]
        pending_offering_filters = [_scope_filter(Offering.path, scope_path), Offering.is_deleted == False, Offering.status.in_(("pending", "corrected"))]
        from app.services.analytics.program_config import reporting_now, reporting_today
        today = latest_date or reporting_today()
        latest_sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        weeks = weeks if weeks in {4, 8} else 4
        current_start = latest_sunday - timedelta(weeks=weeks - 1)
        previous_start = current_start - timedelta(weeks=weeks)
        period_end = latest_sunday + timedelta(days=1)
        lagos = ZoneInfo("Africa/Lagos")
        current_start_at = datetime.combine(current_start, time.min, tzinfo=lagos)
        period_end_at = datetime.combine(period_end, time.min, tzinfo=lagos)
        previous_start_at = datetime.combine(previous_start, time.min, tzinfo=lagos)
        if location_id:
            mf.append(ChurchMember.location_id == location_id)
            wf.append(Worker.location_id == location_id)
            rf.append(Record.location_id == location_id)
            cf.append(Count.location_id == location_id)
            uf.append(User.location_id == location_id)
            tf.append(TransferRequest.from_location_id == location_id)
            of.append(Offering.location_id == location_id)
            pending_count_filters.append(Count.location_id == location_id)
            pending_offering_filters.append(Offering.location_id == location_id)

        # Single round-trip consolidated query: executes all summary aggregates in 1 database trip.
        # Worker status totals are included here so the dashboard does not issue
        # a second independent worker aggregate for the same scope.
        stmt = select(
            select(func.count(ChurchMember.id)).where(and_(*mf)).scalar_subquery().label("members_total"),
            select(func.coalesce(func.sum(_status_case(ChurchMember.status, "active")), 0)).where(and_(*mf)).scalar_subquery().label("active_members"),
            select(func.count(Worker.worker_id)).where(and_(*wf)).scalar_subquery().label("workers_total"),
            select(func.coalesce(func.sum(_status_case(Worker.status, "Active")), 0)).where(and_(*wf)).scalar_subquery().label("active_workers"),
            select(func.coalesce(func.sum(_status_case(Worker.approval_status, "pending_verification")), 0)).where(and_(*wf)).scalar_subquery().label("pending_workers"),
            select(func.coalesce(func.sum(cast(case((and_(func.lower(Worker.status) == "suspended", Worker.approval_status == "approved"), 1), else_=0), Integer)), 0)).where(and_(*wf)).scalar_subquery().label("suspended_workers"),
            select(func.coalesce(func.sum(_status_case(Record.record_type, "newcomer")), 0)).where(and_(*rf)).scalar_subquery().label("newcomers_total"),
            select(func.coalesce(func.sum(_status_case(Record.record_type, "convert")), 0)).where(and_(*rf)).scalar_subquery().label("converts_total"),
            select(func.coalesce(func.max(Count.total), 0)).where(and_(*cf)).scalar_subquery().label("latest_total"),
            select(func.count(func.distinct(Count.location_id))).where(and_(*cf)).scalar_subquery().label("locations_reporting"),
            select(func.count(User.user_id)).where(and_(*uf, User.approval_status == "pending")).scalar_subquery().label("pending_users"),
            select(func.count(TransferRequest.id)).where(and_(*tf)).scalar_subquery().label("pending_transfers"),
            select(func.count(StatusChangeRequest.id)).where(and_(*sf)).scalar_subquery().label("pending_status_changes"),
            select(func.count(WorkerRemovalRequest.id)).where(and_(*rmf)).scalar_subquery().label("pending_removals"),
            select(func.coalesce(func.sum(case((and_(Offering.date >= current_start_at, Offering.date < period_end_at), Offering.amount), else_=0)), 0)).where(and_(*of)).scalar_subquery().label("offerings_current_total"),
            select(func.count(Offering.id)).where(and_(*of, Offering.date >= current_start_at, Offering.date < period_end_at)).scalar_subquery().label("offerings_current_records"),
            select(func.coalesce(func.sum(case((and_(Offering.date >= previous_start_at, Offering.date < current_start_at), Offering.amount), else_=0)), 0)).where(and_(*of)).scalar_subquery().label("offerings_previous_total"),
            select(func.count(Offering.id)).where(and_(*of, Offering.date >= previous_start_at, Offering.date < current_start_at)).scalar_subquery().label("offerings_previous_records"),
            select(func.sum(case((and_(Record.date >= current_start_at, Record.date < period_end_at, func.lower(Record.record_type) == "newcomer"), 1), else_=0))).where(and_(*rf)).scalar_subquery().label("newcomers_current"),
            select(func.sum(case((and_(Record.date >= current_start_at, Record.date < period_end_at, func.lower(Record.record_type) == "convert"), 1), else_=0))).where(and_(*rf)).scalar_subquery().label("converts_current"),
            select(func.sum(case((and_(Record.date >= previous_start_at, Record.date < current_start_at, func.lower(Record.record_type) == "newcomer"), 1), else_=0))).where(and_(*rf)).scalar_subquery().label("newcomers_previous"),
            select(func.sum(case((and_(Record.date >= previous_start_at, Record.date < current_start_at, func.lower(Record.record_type) == "convert"), 1), else_=0))).where(and_(*rf)).scalar_subquery().label("converts_previous"),
            select(func.count(Record.id)).where(and_(*rf, Record.date >= current_start_at, Record.date < period_end_at)).scalar_subquery().label("records_current"),
            select(func.count(Record.id)).where(and_(*rf, Record.date >= previous_start_at, Record.date < current_start_at)).scalar_subquery().label("records_previous"),
            select(func.count(func.distinct(func.coalesce(Count.count_group_id, Count.id)))).where(and_(*pending_count_filters)).scalar_subquery().label("pending_count_reports"),
            select(func.min(Count.created_at)).where(and_(*pending_count_filters)).scalar_subquery().label("oldest_pending_count_at"),
            select(func.count(Offering.id)).where(and_(*pending_offering_filters)).scalar_subquery().label("pending_offering_reports"),
            select(func.min(Offering.created_at)).where(and_(*pending_offering_filters)).scalar_subquery().label("oldest_pending_offering_at"),
            select(func.min(Worker.created_at)).where(and_(*wf, Worker.approval_status == "pending_verification")).scalar_subquery().label("oldest_pending_worker_at"),
            select(func.min(User.created_at)).where(and_(*uf, User.approval_status == "pending")).scalar_subquery().label("oldest_pending_user_at"),
            select(func.min(TransferRequest.created_at)).where(and_(*tf)).scalar_subquery().label("oldest_pending_transfer_at"),
            select(func.min(StatusChangeRequest.created_at)).where(and_(*sf)).scalar_subquery().label("oldest_pending_status_at"),
            select(func.min(WorkerRemovalRequest.created_at)).where(and_(*rmf)).scalar_subquery().label("oldest_pending_removal_at"),
        )
        row = (await db.execute(stmt)).one()
        pending_items = (
            int(row.pending_workers or 0)
            + int(row.pending_users or 0)
            + int(row.pending_transfers or 0)
            + int(row.pending_status_changes or 0)
            + int(row.pending_removals or 0)
        )
        now = reporting_now()
        def pending_item(label: str, count: Any, oldest: Any) -> dict[str, Any]:
            if oldest is not None and oldest.tzinfo is None:
                oldest = oldest.replace(tzinfo=timezone.utc)
            age = max(int((now - oldest).total_seconds() // 3600), 0) if oldest else None
            return {"label": label, "count": int(count or 0), "oldest_age_hours": age}

        pending_approvals = [
            pending_item("Worker registrations", row.pending_workers, row.oldest_pending_worker_at),
            pending_item("User access requests", row.pending_users, row.oldest_pending_user_at),
            pending_item("Count groups", row.pending_count_reports, row.oldest_pending_count_at),
            pending_item("Offerings", row.pending_offering_reports, row.oldest_pending_offering_at),
            pending_item("Transfers", row.pending_transfers, row.oldest_pending_transfer_at),
            pending_item("Status changes", row.pending_status_changes, row.oldest_pending_status_at),
            pending_item("Worker removals", row.pending_removals, row.oldest_pending_removal_at),
        ]
        pending_approvals = [item for item in pending_approvals if item["count"]]
        attendance = await worker_meeting_analytics(db, scope_path, location_id=str(location_id) if location_id else None)
        attendance_rows = attendance["ranking"]
        opportunities = sum(int(item.get("expected") or 0) for item in attendance_rows)
        present = sum(int(item.get("present") or 0) for item in attendance_rows)
        late = sum(int(item.get("late") or 0) for item in attendance_rows)
        absent = sum(int(item.get("absent") or 0) for item in attendance_rows)
        excused = sum(int(item.get("excused") or 0) for item in attendance_rows)
        return {
            "members_total": int(row.members_total or 0), "active_members": int(row.active_members or 0),
            "workers_total": int(row.workers_total or 0), "active_workers": int(row.active_workers or 0),
            "pending_workers": int(row.pending_workers or 0),
            "suspended_workers": int(row.suspended_workers or 0),
            "pending_users": int(row.pending_users or 0),
            "pending_transfers": int(row.pending_transfers or 0),
            "pending_status_changes": int(row.pending_status_changes or 0),
            "pending_removals": int(row.pending_removals or 0),
            "pending_items": pending_items,
            "pending_approvals": pending_approvals,
            "reporting_window_weeks": weeks,
            "approved_offerings": {
                "current_total": float(row.offerings_current_total or 0),
                "current_records": int(row.offerings_current_records or 0),
                "previous_total": float(row.offerings_previous_total or 0),
                "previous_records": int(row.offerings_previous_records or 0),
            },
            "newcomer_period": {
                "newcomers_current": int(row.newcomers_current or 0),
                "newcomers_previous": int(row.newcomers_previous or 0),
                "converts_current": int(row.converts_current or 0),
                "converts_previous": int(row.converts_previous or 0),
                "records_current": int(row.records_current or 0),
                "records_previous": int(row.records_previous or 0),
            },
            "newcomers_total": int(row.newcomers_total or 0), "converts_total": int(row.converts_total or 0),
            "latest_total": int(row.latest_total or 0), "locations_reporting": int(row.locations_reporting or 0),
            "attendance_summary": {
                "expected": opportunities,
                "opportunities": opportunities,
                "current_roster": int(row.workers_total or 0),
                "present": present,
                "late": late,
                "absent": absent,
                "excused": excused,
                "rate": round((present + late) * 100 / opportunities, 1) if opportunities else 0,
                "meetings_reported": sum(int(item.get("meetings") or 0) for item in attendance_rows),
                "legacy_roster_meetings": sum(int(item.get("legacy_roster_meetings") or 0) for item in attendance_rows),
                "deduplicated": True,
            },
        }

    @staticmethod
    async def get_member_analytics(db, scope_path: str, *, location_id=None, months: int = 12) -> dict[str, Any]:
        filters = [_scope_filter(ChurchMember.path, scope_path), ChurchMember.is_deleted == False]
        if location_id:
            filters.append(ChurchMember.location_id == location_id)
        from app.services.analytics.program_config import reporting_today
        today = reporting_today()
        adult_cutoff = today.replace(year=today.year - 18)
        youth_cutoff = today.replace(year=today.year - 13)

        summary_r = await db.execute(select(
            func.count(ChurchMember.id).label("total"),
            func.coalesce(func.sum(_status_case(ChurchMember.gender, "Male")), 0).label("male"),
            func.coalesce(func.sum(_status_case(ChurchMember.gender, "Female")), 0).label("female"),
            func.coalesce(func.sum(cast(case((ChurchMember.date_of_birth <= adult_cutoff, 1), else_=0), Integer)), 0).label("adults"),
            func.coalesce(func.sum(cast(case((and_(ChurchMember.date_of_birth > adult_cutoff, ChurchMember.date_of_birth <= youth_cutoff), 1), else_=0), Integer)), 0).label("youths"),
            func.coalesce(func.sum(cast(case((ChurchMember.date_of_birth > youth_cutoff, 1), else_=0), Integer)), 0).label("children"),
        ).where(and_(*filters)))
        trend_r = await db.execute(select(
            extract("year", ChurchMember.member_since).label("year"),
            extract("month", ChurchMember.member_since).label("month"),
            func.count(ChurchMember.id).label("total"),
        ).where(and_(*filters, ChurchMember.member_since.is_not(None),
                     ChurchMember.member_since >= today - timedelta(days=months * 31)))
        .group_by("year", "month").order_by("year", "month"))
        row = summary_r.one()
        trend = [{"period": f"{int(i.year)}-{int(i.month):02d}", "value": int(i.total or 0)} for i in trend_r]
        return {
            "total": int(row.total or 0), "male": int(row.male or 0), "female": int(row.female or 0),
            "adults": int(row.adults or 0), "youths": int(row.youths or 0), "children": int(row.children or 0),
            "trend": trend,
        }

    @staticmethod
    async def get_worker_analytics(db, scope_path: str, *, location_id=None) -> dict[str, Any]:
        filters = [_scope_filter(Worker.path, scope_path), Worker.is_deleted == False]
        if location_id:
            filters.append(Worker.location_id == location_id)
        stmt = select(
            func.count(Worker.worker_id).label("total"),
            func.coalesce(func.sum(_status_case(Worker.gender, "Male")), 0).label("male"),
            func.coalesce(func.sum(_status_case(Worker.gender, "Female")), 0).label("female"),
            func.coalesce(func.sum(cast(case((and_(func.lower(Worker.status) == "active", Worker.approval_status == "approved"), 1), else_=0), Integer)), 0).label("active"),
            func.coalesce(func.sum(cast(case((and_(func.lower(Worker.status) == "suspended", Worker.approval_status == "approved"), 1), else_=0), Integer)), 0).label("suspended"),
            func.coalesce(func.sum(_status_case(Worker.approval_status, "pending_verification")), 0).label("pending_verification"),
        ).where(and_(*filters))
        row = (await db.execute(stmt)).one()
        data = {k: int(getattr(row, k) or 0) for k in ("total", "male", "female", "active", "suspended", "pending_verification")}
        # Keep the dashboard status categories mutually exclusive and complete;
        # inactive, rejected, and other legacy statuses are the remainder.
        data["inactive"] = max(data["total"] - data["active"] - data["suspended"] - data["pending_verification"], 0)
        return data

    @staticmethod
    async def get_program_comparison(db, scope_path: str, *, location_id=None, limit: int = 6) -> dict[str, Any]:
        filters = [_scope_filter(Count.path, scope_path), Count.is_deleted == False]
        if location_id:
            filters.append(Count.location_id == location_id)
        from app.services.analytics.program_config import reporting_today
        today = reporting_today()
        year_start = date(today.year, 1, 1)
        month_start = date(today.year, today.month, 1)

        ranking_r = await db.execute(
            select(ProgramType.slug.label("program_type"), ProgramType.name.label("program_label"),
                   ProgramDomain.slug.label("domain_slug"), ProgramDomain.name.label("domain_name"),
                   func.coalesce(func.sum(Count.total), 0).label("total"), func.count(Count.id).label("records"))
            .select_from(Count)
            .join(ProgramEvent, ProgramEvent.id == Count.event_id)
            .join(ProgramType, ProgramType.id == ProgramEvent.program_type_id)
            .join(ProgramDomain, ProgramDomain.id == ProgramType.domain_id)
            .where(and_(*filters))
            .group_by(ProgramType.slug, ProgramType.name, ProgramDomain.slug, ProgramDomain.name)
            .order_by(func.coalesce(func.sum(Count.total), 0).desc()).limit(limit)
        )
        special_r = await db.execute(
            select(
                func.coalesce(func.sum(cast(case((ProgramEvent.date >= month_start, 1), else_=0), Integer)), 0).label("month_events"),
                func.coalesce(func.sum(cast(case((ProgramEvent.date >= year_start, 1), else_=0), Integer)), 0).label("year_events"),
                func.coalesce(func.sum(case((ProgramEvent.date >= month_start, Count.total), else_=0)), 0).label("month_turnout"),
                func.coalesce(func.sum(case((ProgramEvent.date >= year_start, Count.total), else_=0)), 0).label("year_turnout"),
            )
            .select_from(Count)
            .join(ProgramEvent, ProgramEvent.id == Count.event_id)
            .join(ProgramType, ProgramType.id == ProgramEvent.program_type_id)
            .join(ProgramDomain, ProgramDomain.id == ProgramType.domain_id)
            .where(and_(*filters, ProgramDomain.slug != "regular_service"))
        )
        ranking = [{"program_type": i.program_type, "label": i.program_label, "domain": i.domain_slug,
                    "domain_name": i.domain_name, "total": int(i.total or 0), "records": int(i.records or 0)} for i in ranking_r]
        s = special_r.one()
        return {"ranking": ranking, "special_programs": {"month_events": int(s.month_events or 0),
                "year_events": int(s.year_events or 0), "month_turnout": int(s.month_turnout or 0), "year_turnout": int(s.year_turnout or 0)}}

    @staticmethod
    async def get_worker_meeting_comparison(db, scope_path: str, *, location_id=None, program_type_slug: str | None = None, limit: int = 6) -> dict[str, Any]:
        return await worker_meeting_analytics(
            db, scope_path, location_id=str(location_id) if location_id else None,
            program_type_slug=program_type_slug,
        )

    @staticmethod
    async def get_newcomer_analytics(db, scope_path: str, *, location_id=None, months: int = 12) -> dict[str, Any]:
        filters = [_scope_filter(Record.path, scope_path), Record.is_deleted == False]
        if location_id:
            filters.append(Record.location_id == location_id)
        from app.services.analytics.program_config import reporting_today
        from app.services.analytics.program_config import reporting_today
        trend_start = reporting_today() - timedelta(days=months * 31)

        summary_r = await db.execute(select(
            func.coalesce(func.sum(_status_case(Record.record_type, "newcomer")), 0).label("newcomers_total"),
            func.coalesce(func.sum(_status_case(Record.record_type, "convert")), 0).label("converts_total"),
            func.coalesce(func.sum(_status_case(Record.gender, "Male")), 0).label("male"),
            func.coalesce(func.sum(_status_case(Record.gender, "Female")), 0).label("female"),
        ).where(and_(*filters)))
        trend_r = await db.execute(select(
            extract("year", Record.created_at).label("year"),
            extract("month", Record.created_at).label("month"),
            func.coalesce(func.sum(_status_case(Record.record_type, "newcomer")), 0).label("newcomers"),
            func.coalesce(func.sum(_status_case(Record.record_type, "convert")), 0).label("converts"),
        ).where(and_(*filters, Record.created_at >= trend_start)).group_by("year", "month").order_by("year", "month"))
        row = summary_r.one()
        trend = [{"period": f"{int(i.year)}-{int(i.month):02d}", "newcomers": int(i.newcomers or 0), "converts": int(i.converts or 0)} for i in trend_r]
        return {"newcomers_total": int(row.newcomers_total or 0), "converts_total": int(row.converts_total or 0),
                "male": int(row.male or 0), "female": int(row.female or 0), "trend": trend}
