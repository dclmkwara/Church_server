from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, cast, func, select, Integer, DateTime
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core import analytics_cache
from app.db.filters import ltree_subpath as _ltree_subpath
from app.db.filters import scope_filter as _scope_filter
from app.models.core import _LTREE
from app.models.attendance import WorkerAttendance
from app.models.counts import Count
from app.models.location import Location
from app.models.offerings import Offering
from app.models.programs import ProgramEvent
from app.models.user import User, Worker
from app.services.dashboard_service import DashboardService
from app.services.statistics_service import StatisticsService

router = APIRouter()
_DASHBOARD_CACHE_TTL = 20.0

DEFAULT_BOOTSTRAP_SECTIONS = (
    'summary',
    'member_analytics',
    'population_statistics',
    'worker_analytics',
    'program_comparison',
    'worker_meeting_comparison',
    'newcomer_analytics',
    'church_statistics',
    'user_statistics',
    'attendance_summary',
    'trend_series',
    'scope_snapshot',
)


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


async def _resolve_location_id(
    db: AsyncSession,
    scope_path: str,
    location_id: Optional[str],
) -> Optional[str]:
    """Accept either a UUID location_id or the human location_code for dashboard filters."""
    if not location_id:
        return None
    raw = str(location_id).strip()
    if not raw:
        return None
    try:
        UUID(raw)
        return raw
    except ValueError:
        pass

    result = await db.execute(
        select(Location.location_id).where(
            Location.location_code == raw,
            _scope_filter(Location.path, scope_path),
        )
    )
    resolved = result.scalars().first()
    return str(resolved) if resolved else None



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
    group_expr = _ltree_subpath(Count.path, segment_count).label('group_path')
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
    sections: Optional[list[str]] = Query(None),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    effective_scope = _effective_scope(current_user, scope_path)
    effective_location_id = await _resolve_location_id(db, effective_scope, location_id)
    requested_sections = tuple(dict.fromkeys(sections or list(DEFAULT_BOOTSTRAP_SECTIONS)))

    async def _build_payload() -> dict[str, Any]:
        payload: dict[str, Any] = {
            'scope_path': effective_scope,
            'scope_kind': _scope_kind(effective_scope),
        }

        if 'summary' in requested_sections:
            payload['summary'] = await DashboardService.get_summary(db, effective_scope, location_id=effective_location_id)
        if 'member_analytics' in requested_sections:
            payload['member_analytics'] = await DashboardService.get_member_analytics(
                db,
                effective_scope,
                location_id=effective_location_id,
                months=months,
            )
        if 'population_statistics' in requested_sections:
            payload['population_statistics'] = await StatisticsService.get_population_statistics(
                db,
                effective_scope,
                location_id=effective_location_id,
            )
        if 'worker_analytics' in requested_sections:
            payload['worker_analytics'] = await DashboardService.get_worker_analytics(
                db,
                effective_scope,
                location_id=effective_location_id,
            )
        if 'program_comparison' in requested_sections:
            payload['program_comparison'] = await DashboardService.get_program_comparison(
                db,
                effective_scope,
                location_id=effective_location_id,
                limit=6,
            )
        if 'worker_meeting_comparison' in requested_sections:
            payload['worker_meeting_comparison'] = await DashboardService.get_worker_meeting_comparison(
                db,
                effective_scope,
                location_id=effective_location_id,
                limit=6,
            )
        if 'newcomer_analytics' in requested_sections:
            payload['newcomer_analytics'] = await DashboardService.get_newcomer_analytics(
                db,
                effective_scope,
                location_id=effective_location_id,
                months=months,
            )
        if 'church_statistics' in requested_sections:
            payload['church_statistics'] = await StatisticsService.get_church_statistics(db, effective_scope)
        if 'user_statistics' in requested_sections:
            payload['user_statistics'] = await StatisticsService.get_user_statistics(db, effective_scope)
        if 'attendance_summary' in requested_sections:
            payload['attendance_summary'] = await _get_attendance_summary(
                db,
                effective_scope,
                location_id=effective_location_id,
            )
        if 'trend_series' in requested_sections:
            payload['trend_series'] = {
                'counts': await _get_timeseries(db, effective_scope, metric='counts'),
                'finance': await _get_timeseries(db, effective_scope, metric='offerings'),
                'attendance': await _get_timeseries(db, effective_scope, metric='attendance'),
            }
        if 'scope_snapshot' in requested_sections:
            payload['scope_snapshot'] = await _get_scope_snapshot(db, effective_scope)

        return payload

    return await analytics_cache.get_or_set(
        ('dashboard', 'bootstrap', effective_scope, effective_location_id, months, requested_sections),
        _build_payload,
        ttl=_DASHBOARD_CACHE_TTL,
    )



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
    effective_location_id = await _resolve_location_id(db, effective_scope, location_id)
    return await analytics_cache.get_or_set(
        ('dashboard', 'summary', effective_scope, effective_location_id),
        lambda: DashboardService.get_summary(db, effective_scope, location_id=effective_location_id),
        ttl=_DASHBOARD_CACHE_TTL,
    )


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
    effective_location_id = await _resolve_location_id(db, effective_scope, location_id)
    return await analytics_cache.get_or_set(
        ('dashboard', 'member_analytics', effective_scope, effective_location_id, months),
        lambda: DashboardService.get_member_analytics(
            db,
            effective_scope,
            location_id=effective_location_id,
            months=months,
        ),
        ttl=_DASHBOARD_CACHE_TTL,
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
    effective_location_id = await _resolve_location_id(db, effective_scope, location_id)
    return await analytics_cache.get_or_set(
        ('dashboard', 'worker_analytics', effective_scope, effective_location_id),
        lambda: DashboardService.get_worker_analytics(db, effective_scope, location_id=effective_location_id),
        ttl=_DASHBOARD_CACHE_TTL,
    )


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
    effective_location_id = await _resolve_location_id(db, effective_scope, location_id)
    return await analytics_cache.get_or_set(
        ('dashboard', 'program_comparison', effective_scope, effective_location_id, limit),
        lambda: DashboardService.get_program_comparison(
            db,
            effective_scope,
            location_id=effective_location_id,
            limit=limit,
        ),
        ttl=_DASHBOARD_CACHE_TTL,
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
    effective_location_id = await _resolve_location_id(db, effective_scope, location_id)
    return await analytics_cache.get_or_set(
        ('dashboard', 'worker_meeting_comparison', effective_scope, effective_location_id, limit),
        lambda: DashboardService.get_worker_meeting_comparison(
            db,
            effective_scope,
            location_id=effective_location_id,
            limit=limit,
        ),
        ttl=_DASHBOARD_CACHE_TTL,
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
    effective_location_id = await _resolve_location_id(db, effective_scope, location_id)
    return await analytics_cache.get_or_set(
        ('dashboard', 'newcomer_analytics', effective_scope, effective_location_id, months),
        lambda: DashboardService.get_newcomer_analytics(
            db,
            effective_scope,
            location_id=effective_location_id,
            months=months,
        ),
        ttl=_DASHBOARD_CACHE_TTL,
    )
