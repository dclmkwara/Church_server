"""
Dashboard service — aggregated analytics for the admin dashboard.

Production changes:
- Shared scope_filter imported from app.db.filters.
- Queries are kept sequential on the request AsyncSession; SQLAlchemy does not
  support concurrent operations on one AsyncSession.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import and_, case, cast, extract, func, select, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.filters import scope_filter as _scope_filter
from app.models.approvals import StatusChangeRequest, TransferRequest, WorkerRemovalRequest
from app.models.attendance import WorkerAttendance
from app.models.church_member import ChurchMember
from app.models.counts import Count
from app.models.programs import ProgramDomain, ProgramEvent, ProgramType
from app.models.records import Record
from app.models.user import User, Worker


def _status_case(column, expected: str):
    return cast(case((column == expected, 1), else_=0), Integer)


class DashboardService:

    @staticmethod
    async def get_summary(db, scope_path: str, *, location_id=None) -> dict[str, Any]:
        mf = [_scope_filter(ChurchMember.path, scope_path), ChurchMember.is_deleted == False]
        wf = [_scope_filter(Worker.path, scope_path), Worker.is_deleted == False]
        rf = [_scope_filter(Record.path, scope_path), Record.is_deleted == False]
        cf = [_scope_filter(Count.path, scope_path), Count.is_deleted == False]
        uf = [_scope_filter(User.path, scope_path), User.is_deleted == False]
        tf = [_scope_filter(TransferRequest.path, scope_path), TransferRequest.status == "pending"]
        sf = [_scope_filter(StatusChangeRequest.path, scope_path), StatusChangeRequest.status == "pending"]
        rmf = [_scope_filter(WorkerRemovalRequest.path, scope_path), WorkerRemovalRequest.status.in_(("pending", "escalated"))]
        if location_id:
            mf.append(ChurchMember.location_id == location_id)
            wf.append(Worker.location_id == location_id)
            rf.append(Record.location_id == location_id)
            cf.append(Count.location_id == location_id)
            uf.append(User.location_id == location_id)
            tf.append(TransferRequest.from_location_id == location_id)

        member_r = await db.execute(select(
            func.count(ChurchMember.id).label("members_total"),
            func.coalesce(func.sum(_status_case(ChurchMember.status, "active")), 0).label("active_members"),
        ).where(and_(*mf)))
        worker_r = await db.execute(select(
            func.count(Worker.worker_id).label("workers_total"),
            func.coalesce(func.sum(_status_case(Worker.status, "Active")), 0).label("active_workers"),
            func.coalesce(func.sum(_status_case(Worker.approval_status, "pending_verification")), 0).label("pending_workers"),
        ).where(and_(*wf)))
        record_r = await db.execute(select(
            func.coalesce(func.sum(_status_case(Record.record_type, "newcomer")), 0).label("newcomers_total"),
            func.coalesce(func.sum(_status_case(Record.record_type, "convert")), 0).label("converts_total"),
        ).where(and_(*rf)))
        count_r = await db.execute(select(
            func.coalesce(func.max(Count.total), 0).label("latest_total"),
            func.count(func.distinct(Count.location_id)).label("locations_reporting"),
        ).where(and_(*cf)))
        pending_user_r = await db.execute(select(func.count(User.user_id).label("pending_users")).where(and_(*uf, User.approval_status == "pending")))
        pending_transfer_r = await db.execute(select(func.count(TransferRequest.id).label("pending_transfers")).where(and_(*tf)))
        pending_status_r = await db.execute(select(func.count(StatusChangeRequest.id).label("pending_status_changes")).where(and_(*sf)))
        pending_removal_r = await db.execute(select(func.count(WorkerRemovalRequest.id).label("pending_removals")).where(and_(*rmf)))
        mr, wr, rr, cr = member_r.one(), worker_r.one(), record_r.one(), count_r.one()
        pur = pending_user_r.one()
        ptr = pending_transfer_r.one()
        psr = pending_status_r.one()
        pmr = pending_removal_r.one()
        pending_items = (
            int(wr.pending_workers or 0)
            + int(pur.pending_users or 0)
            + int(ptr.pending_transfers or 0)
            + int(psr.pending_status_changes or 0)
            + int(pmr.pending_removals or 0)
        )
        return {
            "members_total": int(mr.members_total or 0), "active_members": int(mr.active_members or 0),
            "workers_total": int(wr.workers_total or 0), "active_workers": int(wr.active_workers or 0),
            "pending_workers": int(wr.pending_workers or 0),
            "pending_users": int(pur.pending_users or 0),
            "pending_transfers": int(ptr.pending_transfers or 0),
            "pending_status_changes": int(psr.pending_status_changes or 0),
            "pending_removals": int(pmr.pending_removals or 0),
            "pending_items": pending_items,
            "newcomers_total": int(rr.newcomers_total or 0), "converts_total": int(rr.converts_total or 0),
            "latest_total": int(cr.latest_total or 0), "locations_reporting": int(cr.locations_reporting or 0),
        }

    @staticmethod
    async def get_member_analytics(db, scope_path: str, *, location_id=None, months: int = 12) -> dict[str, Any]:
        filters = [_scope_filter(ChurchMember.path, scope_path), ChurchMember.is_deleted == False]
        if location_id:
            filters.append(ChurchMember.location_id == location_id)
        today = date.today()
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
            func.coalesce(func.sum(_status_case(Worker.status, "Active")), 0).label("active"),
            func.coalesce(func.sum(_status_case(Worker.status, "Inactive")), 0).label("inactive"),
            func.coalesce(func.sum(_status_case(Worker.status, "Suspended")), 0).label("suspended"),
            func.coalesce(func.sum(_status_case(Worker.approval_status, "pending_verification")), 0).label("pending_verification"),
        ).where(and_(*filters))
        row = (await db.execute(stmt)).one()
        return {k: int(getattr(row, k) or 0) for k in ("total", "male", "female", "active", "inactive", "suspended", "pending_verification")}

    @staticmethod
    async def get_program_comparison(db, scope_path: str, *, location_id=None, limit: int = 6) -> dict[str, Any]:
        filters = [_scope_filter(Count.path, scope_path), Count.is_deleted == False]
        if location_id:
            filters.append(Count.location_id == location_id)
        today = date.today()
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
    async def get_worker_meeting_comparison(db, scope_path: str, *, location_id=None, limit: int = 6) -> dict[str, Any]:
        filters = [_scope_filter(WorkerAttendance.path, scope_path), WorkerAttendance.is_deleted == False]
        if location_id:
            filters.append(WorkerAttendance.location_id == location_id)
        rows = (await db.execute(
            select(ProgramType.slug.label("program_type"), ProgramType.name.label("program_label"),
                   func.coalesce(func.sum(_status_case(WorkerAttendance.status, "present")), 0).label("present"),
                   func.coalesce(func.sum(_status_case(WorkerAttendance.status, "late")), 0).label("late"),
                   func.coalesce(func.sum(_status_case(WorkerAttendance.status, "absent")), 0).label("absent"),
                   func.count(WorkerAttendance.id).label("records"))
            .select_from(WorkerAttendance)
            .join(ProgramEvent, ProgramEvent.id == WorkerAttendance.event_id)
            .join(ProgramType, ProgramType.id == ProgramEvent.program_type_id)
            .where(and_(*filters))
            .group_by(ProgramType.slug, ProgramType.name)
            .order_by((func.coalesce(func.sum(_status_case(WorkerAttendance.status, "present")), 0)
                       + func.coalesce(func.sum(_status_case(WorkerAttendance.status, "late")), 0)).desc())
            .limit(limit)
        ))
        ranking = []
        for item in rows:
            p, l, a, r = int(item.present or 0), int(item.late or 0), int(item.absent or 0), int(item.records or 0)
            ranking.append({"program_type": item.program_type, "label": item.program_label,
                            "present": p, "late": l, "absent": a, "records": r,
                            "attendance_rate": round(((p + l) / r) * 100, 1) if r else 0.0})
        return {"ranking": ranking}

    @staticmethod
    async def get_newcomer_analytics(db, scope_path: str, *, location_id=None, months: int = 12) -> dict[str, Any]:
        filters = [_scope_filter(Record.path, scope_path), Record.is_deleted == False]
        if location_id:
            filters.append(Record.location_id == location_id)
        trend_start = date.today() - timedelta(days=months * 31)

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
