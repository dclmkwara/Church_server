from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, cast, func, select, Integer, DateTime
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.filters import scope_filter as _scope_filter
from app.models.attendance import WorkerAttendance
from app.models.counts import Count
from app.models.offerings import Offering
from app.models.programs import ProgramEvent
from app.models.user import User, Worker
from app.services.dashboard_service import DashboardService
from app.services.statistics_service import StatisticsService

router = APIRouter()


def _effective_scope(current_user: User, scope_path: Optional[str]) -> str:
    return deps.resolve_scope_path(current_user, scope_path)


def _scope_kind(scope_path: str) -> str:
    depth = max(len([part for part in scope_path.split('.') if part]) - 1, 0)
    mapping = {
        0: 'global',
        1: 'nation',
        2: 'state',
        3: 'region',
        4: 'group',
        5: 'location',
        6: 'fellowship',
    }
    return mapping.get(depth, 'location')


def _breakdown_level(scope_path: str) -> str:
    kind = _scope_kind(scope_path)
    mapping = {
        'global': 'state',
        'continent': 'state',
        'nation': 'state',
        'state': 'region',
        'region': 'group',
        'group': 'location',
        'location': 'location',
    }
    return mapping.get(kind, 'location')




async def _get_attendance_summary(db: AsyncSession, scope_path: str, *, location_id: Optional[str] = None) -> dict[str, Any]:
    filters = [_scope_filter(WorkerAttendance.path, scope_path), WorkerAttendance.is_deleted == False]
    worker_filters = [_scope_filter(Worker.path, scope_path), Worker.is_deleted == False]
    if location_id:
        filters.append(WorkerAttendance.location_id == location_id)
        worker_filters.append(Worker.location_id == location_id)

    attendance_stmt = select(
        func.coalesce(func.sum(cast(WorkerAttendance.status == 'present', Integer)), 0).label('present'),
        func.coalesce(func.sum(cast(WorkerAttendance.status == 'late', Integer)), 0).label('late'),
        func.coalesce(func.sum(cast(WorkerAttendance.status == 'absent', Integer)), 0).label('absent'),
        func.coalesce(func.sum(cast(WorkerAttendance.status == 'excused', Integer)), 0).label('excused'),
    ).where(and_(*filters))
    expected_stmt = select(func.count(Worker.worker_id)).where(and_(*worker_filters))

    attendance_row = (await db.execute(attendance_stmt)).one()
    expected = int((await db.execute(expected_stmt)).scalar() or 0)
    present = int(attendance_row.present or 0)
    late = int(attendance_row.late or 0)
    absent = int(attendance_row.absent or 0)
    excused = int(attendance_row.excused or 0)
    rate = round((present / expected) * 100) if expected else 0
    return {
        'expected': expected,
        'present': present,
        'late': late,
        'absent': absent,
        'excused': excused,
        'rate': rate,
    }


async def _get_timeseries(db: AsyncSession, scope_path: str, *, metric: str) -> list[dict[str, Any]]:
    start_date = date.today() - timedelta(days=90)
    if metric == 'counts':
        period = func.date_trunc('day', Count.date).label('period')
        stmt = select(
            period,
            func.coalesce(func.sum(Count.total), 0).label('total'),
        ).where(
            Count.date >= start_date,
            _scope_filter(Count.path, scope_path),
            Count.is_deleted == False,
        ).group_by(period).order_by(period)
        rows = await db.execute(stmt)
        return [{'date': str(row.period.date()), 'value': int(row.total or 0)} for row in rows]
    if metric == 'offerings':
        period = func.date_trunc('day', Offering.date).label('period')
        stmt = select(
            period,
            func.coalesce(func.sum(Offering.amount), 0).label('total'),
        ).where(
            Offering.date >= start_date,
            _scope_filter(Offering.path, scope_path),
            Offering.is_deleted == False,
        ).group_by(period).order_by(period)
        rows = await db.execute(stmt)
        return [{'date': str(row.period.date()), 'value': float(row.total or 0)} for row in rows]
    period = func.date_trunc('day', cast(ProgramEvent.date, DateTime)).label('period')
    stmt = select(
        period,
        func.count(WorkerAttendance.id).label('total'),
    ).select_from(WorkerAttendance).join(ProgramEvent, ProgramEvent.id == WorkerAttendance.event_id).where(
        ProgramEvent.date >= start_date,
        _scope_filter(WorkerAttendance.path, scope_path),
        WorkerAttendance.is_deleted == False,
    ).group_by(period).order_by(period)
    rows = await db.execute(stmt)
    return [{'date': str(row.period.date()), 'value': int(row.total or 0)} for row in rows]


async def _get_scope_snapshot(db: AsyncSession, scope_path: str) -> list[dict[str, Any]]:
    level = _breakdown_level(scope_path)
    segment_count = {
        'location': 6,
        'group': 5,
        'region': 4,
        'state': 3,
    }.get(level, 6)
    group_expr = func.subpath(cast(Count.path, _LTREE()), 0, segment_count).label('group_path')
    stmt = select(
        group_expr,
        func.coalesce(func.sum(Count.total), 0).label('total'),
    ).where(
        Count.date >= date.today() - timedelta(days=30),
        _scope_filter(Count.path, scope_path),
        Count.is_deleted == False,
    ).group_by(group_expr).order_by(func.coalesce(func.sum(Count.total), 0).desc()).limit(5)
    rows = await db.execute(stmt)
    return [{'path': str(row.group_path), 'total': int(row.total or 0)} for row in rows]


@router.get(
    '/bootstrap',
    dependencies=[Depends(deps.PermissionChecker('statistics:read'))],
)
async def get_dashboard_bootstrap(
    scope_path: Optional[str] = Query(None),
    location_id: Optional[str] = Query(None),
    months: int = Query(12, ge=1, le=24),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    effective_scope = _effective_scope(current_user, scope_path)

    summary = await DashboardService.get_summary(db, effective_scope, location_id=location_id)
    member_analytics = await DashboardService.get_member_analytics(db, effective_scope, location_id=location_id, months=months)
    worker_analytics = await DashboardService.get_worker_analytics(db, effective_scope, location_id=location_id)
    program_comparison = await DashboardService.get_program_comparison(db, effective_scope, location_id=location_id, limit=6)
    worker_meeting_comparison = await DashboardService.get_worker_meeting_comparison(db, effective_scope, location_id=location_id, limit=6)
    newcomer_analytics = await DashboardService.get_newcomer_analytics(db, effective_scope, location_id=location_id, months=months)
    population_statistics = await StatisticsService.get_population_statistics(db, effective_scope, location_id=location_id)
    church_statistics = await StatisticsService.get_church_statistics(db, effective_scope)
    user_statistics = await StatisticsService.get_user_statistics(db, effective_scope)
    attendance_summary = await _get_attendance_summary(db, effective_scope, location_id=location_id)
    ts_counts = await _get_timeseries(db, effective_scope, metric='counts')
    ts_finance = await _get_timeseries(db, effective_scope, metric='offerings')
    ts_attendance = await _get_timeseries(db, effective_scope, metric='attendance')
    scope_snapshot = await _get_scope_snapshot(db, effective_scope)

    return {
        'scope_path': effective_scope,
        'scope_kind': _scope_kind(effective_scope),
        'summary': summary,
        'member_analytics': member_analytics,
        'population_statistics': population_statistics,
        'worker_analytics': worker_analytics,
        'program_comparison': program_comparison,
        'worker_meeting_comparison': worker_meeting_comparison,
        'newcomer_analytics': newcomer_analytics,
        'church_statistics': church_statistics,
        'user_statistics': user_statistics,
        'attendance_summary': attendance_summary,
        'trend_series': {
            'counts': ts_counts,
            'finance': ts_finance,
            'attendance': ts_attendance,
        },
        'scope_snapshot': scope_snapshot,
    }



@router.get(
    '/summary',
    dependencies=[Depends(deps.PermissionChecker('statistics:read'))],
)
async def get_dashboard_summary(
    scope_path: Optional[str] = Query(None),
    location_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    effective_scope = _effective_scope(current_user, scope_path)
    return await DashboardService.get_summary(db, effective_scope, location_id=location_id)


@router.get(
    '/member-analytics',
    dependencies=[Depends(deps.PermissionChecker('statistics:read'))],
)
async def get_member_analytics(
    scope_path: Optional[str] = Query(None),
    location_id: Optional[str] = Query(None),
    months: int = Query(12, ge=1, le=24),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    effective_scope = _effective_scope(current_user, scope_path)
    return await DashboardService.get_member_analytics(
        db,
        effective_scope,
        location_id=location_id,
        months=months,
    )


@router.get(
    '/worker-analytics',
    dependencies=[Depends(deps.PermissionChecker('statistics:read'))],
)
async def get_worker_analytics(
    scope_path: Optional[str] = Query(None),
    location_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    effective_scope = _effective_scope(current_user, scope_path)
    return await DashboardService.get_worker_analytics(db, effective_scope, location_id=location_id)


@router.get(
    '/program-comparison',
    dependencies=[Depends(deps.PermissionChecker('reports:read'))],
)
async def get_program_comparison(
    scope_path: Optional[str] = Query(None),
    location_id: Optional[str] = Query(None),
    limit: int = Query(6, ge=1, le=12),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    effective_scope = _effective_scope(current_user, scope_path)
    return await DashboardService.get_program_comparison(
        db,
        effective_scope,
        location_id=location_id,
        limit=limit,
    )


@router.get(
    '/worker-meeting-comparison',
    dependencies=[Depends(deps.PermissionChecker('reports:read'))],
)
async def get_worker_meeting_comparison(
    scope_path: Optional[str] = Query(None),
    location_id: Optional[str] = Query(None),
    limit: int = Query(6, ge=1, le=12),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    effective_scope = _effective_scope(current_user, scope_path)
    return await DashboardService.get_worker_meeting_comparison(
        db,
        effective_scope,
        location_id=location_id,
        limit=limit,
    )


@router.get(
    '/newcomer-analytics',
    dependencies=[Depends(deps.PermissionChecker('statistics:read'))],
)
async def get_newcomer_analytics(
    scope_path: Optional[str] = Query(None),
    location_id: Optional[str] = Query(None),
    months: int = Query(12, ge=1, le=24),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    effective_scope = _effective_scope(current_user, scope_path)
    return await DashboardService.get_newcomer_analytics(
        db,
        effective_scope,
        location_id=location_id,
        months=months,
    )
