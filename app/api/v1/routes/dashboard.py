from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, cast, func, select, Integer, DateTime, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core import analytics_cache
from app.db.filters import ltree_subpath as _ltree_subpath
from app.db.filters import scope_filter as _scope_filter
from app.models.core import _LTREE
from app.models.attendance import WorkerAttendance, WorkerAttendanceSubmission
from app.models.counts import Count
from app.models.expected_population import LocationExpectedPopulation
from app.models.audit import AuditLog
from app.models.location import Group, Location, Region, State
from app.models.offerings import Offering
from app.models.programs import ProgramEvent
from app.models.user import User, Worker
from app.services.dashboard_service import DashboardService
from app.services.statistics_service import StatisticsService
from app.services.analytics.sunday_worship import SundayWorshipAnalytics

_DASHBOARD_CACHE_TTL = 20.0

router = APIRouter()


class ExpectedPopulationVersionCreate(BaseModel):
    location_id: UUID
    expected_value: int = Field(ge=0, le=10_000_000)
    effective_from: date
    note: str | None = Field(default=None, max_length=2000)


def _is_state_overseer(current_user: User) -> bool:
    return (
        deps.highest_role_score(current_user) == 5
        and any(role.role_name == "State Overseer" and role.score_value == 5 for role in (current_user.roles or []))
    )

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
    expected_stmt = select(func.count(Worker.worker_id)).where(and_(*worker_filters)).scalar_subquery()
    attendance_stmt = attendance_stmt.subquery()
    submission_filters = [
        _scope_filter(WorkerAttendanceSubmission.program_scope_path, scope_path),
        WorkerAttendanceSubmission.is_deleted.is_(False),
    ]
    if location_id:
        submission_filters.append(WorkerAttendanceSubmission.location_id == location_id)
    submission_stmt = select(
        func.coalesce(func.sum(WorkerAttendanceSubmission.expected_workers_count), 0).label('opportunities'),
        func.coalesce(func.sum(WorkerAttendanceSubmission.present_count), 0).label('submitted_present'),
    ).where(and_(*submission_filters)).subquery()
    stmt = select(
        attendance_stmt.c.present, attendance_stmt.c.late, attendance_stmt.c.absent, attendance_stmt.c.excused,
        expected_stmt.label('current_roster'), submission_stmt.c.opportunities, submission_stmt.c.submitted_present,
    ).select_from(attendance_stmt.join(submission_stmt, true()))
    row = (await db.execute(stmt)).one()
    expected = int(row.current_roster or 0)
    present = int(row.present or 0)
    late = int(row.late or 0)
    absent = int(row.absent or 0)
    excused = int(row.excused or 0)
    # A current worker snapshot is not the denominator for a historical period.
    # Use the roster size captured with each usher submission so every meeting
    # contributes its own attendance opportunity count.
    opportunities = int(row.opportunities or 0)
    submitted_present = int(row.submitted_present or 0)
    rate = round((submitted_present / opportunities) * 100, 1) if opportunities else 0
    return {
        'expected': opportunities,
        'current_roster': expected,
        'opportunities': opportunities,
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
            Offering.status == "approved",
        ).group_by(period).order_by(period)
        rows = await db.execute(stmt)
        return [{'date': str(row.period.date()), 'value': float(row.total or 0)} for row in rows]
    period = func.date_trunc('day', WorkerAttendance.date).label('period')
    stmt = select(
        period,
        func.count(WorkerAttendance.id).label('total'),
    ).select_from(WorkerAttendance).where(
        WorkerAttendance.date >= start_date,
        _scope_filter(WorkerAttendance.path, scope_path),
        WorkerAttendance.is_deleted == False,
    ).group_by(period).order_by(period)
    rows = await db.execute(stmt)
    return [{'date': str(row.period.date()), 'value': int(row.total or 0)} for row in rows]


async def _get_scope_snapshot(db: AsyncSession, scope_path: str, *, date_filter: date) -> list[dict[str, Any]]:
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
        Count.date >= date_filter,
        _scope_filter(Count.path, scope_path),
        Count.is_deleted == False,
    ).group_by(group_expr).order_by(func.coalesce(func.sum(Count.total), 0).desc()).limit(5)
    rows = await db.execute(stmt)
    return [{'path': str(row.group_path), 'total': int(row.total or 0)} for row in rows]


def _period_start(period: str, today: date | None = None) -> date:
    today = today or date.today()
    if period == 'month':
        return today.replace(day=1)
    if period == 'quarter':
        return today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1)
    if period == 'year':
        return today.replace(month=1, day=1)
    return today - timedelta(days=29)


async def _get_scope_children(db: AsyncSession, scope_path: str) -> list[dict[str, str]]:
    kind = _scope_kind(scope_path)
    if kind == 'state':
        model, name, code = Region, Region.region_name, Region.region_code
    elif kind == 'region':
        model, name, code = Group, Group.group_name, Group.group_code
    elif kind == 'group':
        model, name, code = Location, Location.location_name, Location.location_code
    else:
        return []
    rows = await db.execute(
        select(model.path, name, code).where(
            _scope_filter(model.path, scope_path),
            func.nlevel(model.path) == len(scope_path.split('.')) + 1,
        ).order_by(name)
    )
    return [
        {'path': str(row.path), 'name': str(row[1]), 'code': str(row[2])}
        for row in rows
    ]


@router.get(
    '/bootstrap',
    dependencies=[Depends(deps.PermissionChecker('statistics:read'))],
)
async def get_dashboard_bootstrap(
    scope_path: Optional[str] = Query(None),
    location_id: Optional[str] = Query(None),
    months: int = Query(12, ge=1, le=24),
    period: str = Query('recent', pattern='^(recent|month|quarter|year)$'),
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
            'authorized_scope_path': deps.effective_scope_path(current_user),
            'scope_kind': _scope_kind(effective_scope),
            'population_period': period,
        }

        if 'summary' in requested_sections:
            payload['summary'] = await DashboardService.get_summary(db, effective_scope, location_id=effective_location_id)
            payload['worker_analytics'] = {
                'total': payload['summary']['workers_total'],
                'active': payload['summary']['active_workers'],
                'pending_verification': payload['summary']['pending_workers'],
                'suspended': payload['summary']['suspended_workers'],
            }
        if 'member_analytics' in requested_sections:
            payload['member_analytics'] = await DashboardService.get_member_analytics(
                db, effective_scope, location_id=effective_location_id, months=months,
            )
        if 'population_statistics' in requested_sections:
            payload['population_statistics'] = await StatisticsService.get_population_statistics(
                db,
                effective_scope,
                location_id=effective_location_id,
                date_filter=_period_start(period),
            )
        if 'worker_analytics' in requested_sections and 'worker_analytics' not in payload:
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
            payload['scope_snapshot'] = await _get_scope_snapshot(db, effective_scope, date_filter=_period_start(period))
        if 'scope_children' in requested_sections:
            payload['scope_children'] = await _get_scope_children(db, effective_scope)

        return payload

    return await _build_payload()



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
    '/sunday-worship',
    dependencies=[Depends(deps.PermissionChecker('statistics:read'))],
)
async def get_sunday_worship_overview(
    scope_path: Optional[str] = Query(None),
    occurrence_date: Optional[date] = Query(None),
    include_pending: bool = Query(False),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Return date-anchored Sunday Worship population coverage for an allowed scope."""
    effective_scope = _effective_scope(current_user, scope_path)
    if occurrence_date is not None and occurrence_date.weekday() != 6:
        raise HTTPException(status_code=422, detail="occurrence_date must be a Sunday")
    return await analytics_cache.get_or_set(
        ('dashboard', 'sunday-worship', effective_scope, occurrence_date, include_pending),
        lambda: SundayWorshipAnalytics.overview(
            db,
            effective_scope,
            occurrence_date=occurrence_date,
            include_pending=include_pending,
        ),
        ttl=_DASHBOARD_CACHE_TTL,
    )


@router.get(
    '/sunday-worship/series',
    dependencies=[Depends(deps.PermissionChecker('statistics:read'))],
)
async def get_sunday_worship_series(
    scope_path: Optional[str] = Query(None),
    weeks: int = Query(4, ge=4, le=8),
    latest_date: Optional[date] = Query(None),
    include_pending: bool = Query(False),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """Return weekly Sunday metrics for the scope and each direct child."""
    effective_scope = _effective_scope(current_user, scope_path)
    latest = latest_date or (date.today() - timedelta(days=(date.today().weekday() + 1) % 7))
    if latest.weekday() != 6:
        raise HTTPException(status_code=422, detail="latest_date must be a Sunday")
    occurrence_dates = [latest - timedelta(weeks=index) for index in reversed(range(weeks))]
    return await SundayWorshipAnalytics.series(
        db, effective_scope, occurrence_dates=occurrence_dates, include_pending=include_pending,
    )


@router.get(
    "/expected-population",
    dependencies=[Depends(deps.PermissionChecker("statistics:read"))],
)
async def list_expected_population(
    as_of: date | None = Query(None),
    include_history: bool = Query(False),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict[str, Any]:
    """Return scoped estimates; report calculations resolve the version effective on their date."""
    effective_scope = deps.effective_scope_path(current_user)
    date_limit = as_of or date.today()
    estimate_join = LocationExpectedPopulation.location_id == Location.location_id
    if not include_history:
        estimate_join = and_(estimate_join, LocationExpectedPopulation.effective_from <= date_limit)
    result = await db.execute(
        select(Location, LocationExpectedPopulation, User.name)
        .outerjoin(LocationExpectedPopulation, estimate_join)
        .outerjoin(User, User.user_id == LocationExpectedPopulation.set_by_id)
        .where(_scope_filter(Location.path, effective_scope))
        .order_by(
            Location.location_name,
            LocationExpectedPopulation.effective_from.desc().nullslast(),
            LocationExpectedPopulation.created_at.desc().nullslast(),
        )
    )
    grouped: dict[str, dict[str, Any]] = {}
    for location, version, set_by_name in result.all():
        location_id = str(location.location_id)
        item = grouped.setdefault(location_id, {
            "location_id": location_id,
            "location_name": location.location_name,
            "location_code": location.location_code,
            "path": str(location.path),
            "is_active": bool(location.is_active),
            "expected_value": None,
            "effective_from": None,
            "history": [],
        })
        if version is None:
            continue
        encoded = {
            "id": str(version.id),
            "expected_value": int(version.expected_value),
            "effective_from": version.effective_from.isoformat(),
            "set_by_id": str(version.set_by_id),
            "set_by": str(set_by_name or version.set_by_id),
            "note": version.note or "",
            "created_at": version.created_at.isoformat() if version.created_at else "",
        }
        if include_history:
            item["history"].append(encoded)
        if version.effective_from <= date_limit and item["effective_from"] is None:
            item["expected_value"] = int(version.expected_value)
            item["effective_from"] = version.effective_from.isoformat()
    return {"as_of": date_limit.isoformat(), "locations": list(grouped.values())}


@router.post(
    "/expected-population",
    dependencies=[Depends(deps.PermissionChecker("statistics:read"))],
)
async def create_expected_population_version(
    payload: ExpectedPopulationVersionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict[str, Any]:
    """Append a version; never overwrite a historical expectation."""
    if not _is_state_overseer(current_user):
        raise HTTPException(status_code=403, detail="Only the State Overseer can maintain expected Sunday attendance")
    scope_path = deps.effective_scope_path(current_user)
    if len([part for part in scope_path.split(".") if part]) != 3:
        raise HTTPException(status_code=403, detail="Expected Sunday attendance can only be maintained at State scope")
    location_result = await db.execute(
        select(Location).where(
            Location.location_id == str(payload.location_id),
            _scope_filter(Location.path, scope_path),
        )
    )
    location = location_result.scalar_one_or_none()
    if location is None:
        raise HTTPException(status_code=404, detail="Location not found in this State")
    if not location.is_active:
        raise HTTPException(status_code=409, detail="An estimate can only be set for an active location")
    version = LocationExpectedPopulation(
        location_id=location.location_id,
        path=str(location.path),
        expected_value=payload.expected_value,
        effective_from=payload.effective_from,
        set_by_id=current_user.user_id,
        note=payload.note.strip() if payload.note else None,
    )
    audit = AuditLog(
        user_id=current_user.user_id,
        action="SET_LOCATION_EXPECTED_POPULATION",
        resource_type="location_expected_population",
        resource_id=str(location.location_id),
        changes={
            "expected_value": payload.expected_value,
            "effective_from": payload.effective_from.isoformat(),
            "note": payload.note or "",
        },
    )
    db.add_all([version, audit])
    await db.commit()
    await db.refresh(version)
    return {
        "id": str(version.id),
        "location_id": str(version.location_id),
        "expected_value": int(version.expected_value),
        "effective_from": version.effective_from.isoformat(),
        "set_by_id": str(version.set_by_id),
        "note": version.note or "",
        "created_at": version.created_at.isoformat() if version.created_at else "",
    }


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
    program_type_slug: Optional[str] = Query(None, min_length=1, max_length=120),
    limit: int = Query(6, ge=1, le=12),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    effective_scope = _effective_scope(current_user, scope_path)
    effective_location_id = await _resolve_location_id(db, effective_scope, location_id)
    return await analytics_cache.get_or_set(
        ('dashboard', 'worker_meeting_comparison', effective_scope, effective_location_id, program_type_slug or '', limit),
        lambda: DashboardService.get_worker_meeting_comparison(
            db,
            effective_scope,
            location_id=effective_location_id,
            program_type_slug=program_type_slug,
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
