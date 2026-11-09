from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from sqlalchemy import String, and_, cast, func, or_, select, Integer, DateTime, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core import analytics_cache
from app.core.config import settings
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
from app.services.analytics.program_config import reporting_today
from app.services.worker_meeting_analytics import worker_meeting_analytics

_DASHBOARD_CACHE_TTL = 20.0

router = APIRouter()


class ExpectedPopulationVersionCreate(BaseModel):
    location_id: UUID
    expected_value: int = Field(ge=0, le=10_000_000)
    effective_from: date
    note: str | None = Field(default=None, max_length=2000)


class ExpectedPopulationBulkPreviewRequest(BaseModel):
    csv_text: str = Field(min_length=1, max_length=1_000_000)


class ExpectedPopulationBulkApplyRequest(BaseModel):
    preview_token: str = Field(min_length=1, max_length=2_000_000)


_EXPECTED_POPULATION_CSV_MAX_ROWS = 1000
_EXPECTED_POPULATION_PREVIEW_TTL_SECONDS = 600
_expected_population_preview_signer = URLSafeTimedSerializer(
    settings.SECRET_KEY,
    salt="expected-population-csv-preview-v1",
)


def _csv_header_key(value: Any) -> str:
    return re.sub(r"[\s-]+", "_", str(value or "").strip().lower())


def parse_expected_population_csv(csv_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse the documented CSV header and return row values with line numbers."""
    try:
        reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    except csv.Error as exc:
        return [], [f"Could not read CSV: {exc}"]
    headers = {_csv_header_key(value): value for value in (reader.fieldnames or [])}
    required = {"location_code", "expected_attendance", "effective_from"}
    missing = sorted(required - set(headers))
    if missing:
        return [], [f"Missing required CSV column(s): {', '.join(missing)}"]
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for line, raw in enumerate(reader, start=2):
        if len(rows) >= _EXPECTED_POPULATION_CSV_MAX_ROWS:
            errors.append(f"CSV may contain at most {_EXPECTED_POPULATION_CSV_MAX_ROWS} data rows.")
            break
        code = str(raw.get(headers["location_code"]) or "").strip()
        attendance_raw = str(raw.get(headers["expected_attendance"]) or "").strip()
        effective_raw = str(raw.get(headers["effective_from"]) or "").strip()
        note_header = headers.get("note")
        note = str(raw.get(note_header) or "").strip() if note_header else ""
        rows.append({
            "line": line,
            "location_code": code,
            "expected_attendance_raw": attendance_raw,
            "effective_from_raw": effective_raw,
            "note": note,
        })
    if not rows and not errors:
        errors.append("CSV contains a header but no data rows.")
    return rows, errors


async def _build_expected_population_bulk_preview(
    db: AsyncSession,
    current_user: User,
    csv_text: str,
    *,
    lock_locations: bool = False,
) -> dict[str, Any]:
    if not _can_manage_expected_population(current_user):
        raise HTTPException(status_code=403, detail="Only the State Overseer can maintain expected Sunday attendance")
    scope_path = deps.effective_scope_path(current_user)
    if len([part for part in scope_path.split(".") if part]) != 3:
        raise HTTPException(status_code=403, detail="Expected Sunday attendance can only be maintained at State scope")

    parsed, parse_errors = parse_expected_population_csv(csv_text)
    response_rows: list[dict[str, Any]] = []
    blocking_errors = list(parse_errors)
    if parse_errors and not parsed:
        return {
            "rows": response_rows,
            "errors": blocking_errors,
            "can_apply": False,
            "summary": {"matched_locations": 0, "unknown_codes": 0, "invalid_rows": 0, "locations_changing": 0, "versions_to_add": 0},
        }

    occurrences: dict[str, int] = {}
    for row in parsed:
        key = row["location_code"].casefold()
        occurrences[key] = occurrences.get(key, 0) + 1
    codes = sorted({row["location_code"].casefold() for row in parsed if row["location_code"]})
    location_rows = []
    if codes:
        location_stmt = select(Location).where(
                _scope_filter(Location.path, scope_path),
                or_(
                    func.lower(Location.location_code).in_(codes),
                    func.lower(cast(Location.path, String)).in_(codes),
                ),
            )
        if lock_locations:
            location_stmt = location_stmt.with_for_update()
        result = await db.execute(location_stmt)
        location_rows = list(result.scalars().all())
    locations_by_code: dict[str, list[Location]] = {}
    for location in location_rows:
        locations_by_code.setdefault(str(location.location_code).casefold(), []).append(location)
        locations_by_code.setdefault(str(location.path).casefold(), []).append(location)

    valid_inputs: list[dict[str, Any]] = []
    for row in parsed:
        item = {
            "line": row["line"],
            "location_code": row["location_code"],
            "location_name": "",
            "expected_attendance": None,
            "effective_from": row["effective_from_raw"],
            "note": row["note"],
            "old_value": None,
            "old_version_id": None,
            "new_value": None,
            "status": "invalid",
            "message": "",
            "would_change": False,
            "invalid_values": False,
        }
        row_errors: list[str] = []
        invalid_values = False
        if not row["location_code"]:
            row_errors.append("Location code is required.")
            invalid_values = True
        if row["location_code"] and occurrences.get(row["location_code"].casefold(), 0) > 1:
            row_errors.append("Location code appears more than once in this CSV.")
            invalid_values = True
        try:
            attendance = int(row["expected_attendance_raw"])
            if attendance < 0 or attendance > 10_000_000:
                raise ValueError
        except (TypeError, ValueError):
            attendance = None
            row_errors.append("Expected attendance must be a whole number from 0 to 10,000,000.")
            invalid_values = True
        try:
            effective = date.fromisoformat(row["effective_from_raw"])
        except (TypeError, ValueError):
            effective = None
            row_errors.append("Effective-from date must use YYYY-MM-DD.")
            invalid_values = True
        matches = locations_by_code.get(row["location_code"].casefold(), []) if row["location_code"] else []
        matches = list({str(location.location_id): location for location in matches}.values())
        if row["location_code"] and not matches:
            item["status"] = "unknown"
            row_errors.append("Location code is not in this State.")
        elif len(matches) > 1:
            row_errors.append("Location code is ambiguous in this State. Use the full location path shown in the hierarchy.")
            invalid_values = True
        elif matches and not matches[0].is_active:
            row_errors.append("Location is inactive; estimates can only be added for active locations.")
            invalid_values = True
        if row_errors:
            if item["status"] != "unknown":
                item["status"] = "invalid"
            item["invalid_values"] = invalid_values
            item["message"] = " ".join(row_errors)
            blocking_errors.extend([f"Row {row['line']}: {message}" for message in row_errors])
        else:
            location = matches[0]
            item.update({
                "location_id": str(location.location_id),
                "location_name": str(location.location_name),
                "path": str(location.path),
                "expected_attendance": attendance,
                "effective_from": effective.isoformat(),
                "new_value": attendance,
                "status": "matched",
            })
            valid_inputs.append({**item, "_effective_date": effective, "_path": str(location.path)})
        response_rows.append(item)

    history_by_location: dict[str, list[LocationExpectedPopulation]] = {}
    if valid_inputs:
        location_ids = [row["location_id"] for row in valid_inputs]
        date_limit = max(row["_effective_date"] for row in valid_inputs)
        history_result = await db.execute(
            select(LocationExpectedPopulation)
            .where(
                LocationExpectedPopulation.location_id.in_(location_ids),
                LocationExpectedPopulation.effective_from <= date_limit,
            )
            .order_by(
                LocationExpectedPopulation.location_id,
                LocationExpectedPopulation.effective_from.desc(),
                LocationExpectedPopulation.created_at.desc(),
            )
        )
        for version in history_result.scalars().all():
            history_by_location.setdefault(str(version.location_id), []).append(version)

    valid_by_line = {row["line"]: row for row in valid_inputs}
    locations_changing = 0
    for item in response_rows:
        valid = valid_by_line.get(item["line"])
        if valid is None:
            continue
        candidates = [
            version for version in history_by_location.get(item["location_id"], [])
            if version.effective_from <= valid["_effective_date"]
        ]
        previous = candidates[0] if candidates else None
        old_value = int(previous.expected_value) if previous is not None else None
        changed = old_value != item["new_value"]
        item["old_value"] = old_value
        item["old_version_id"] = str(previous.id) if previous is not None else None
        item["would_change"] = changed
        item["message"] = "Estimate will change." if changed else "Value is unchanged; a new version will still be added."
        if changed:
            locations_changing += 1
        valid["old_value"] = old_value
        valid["old_version_id"] = str(previous.id) if previous is not None else None
        valid["would_change"] = changed

    can_apply = bool(parsed) and not blocking_errors and len(valid_inputs) == len(parsed)
    preview_token = None
    if can_apply:
        signed_rows = [
            {
                "line": row["line"],
                "location_id": row["location_id"],
                "location_code": row["location_code"],
                "path": row["_path"],
                "expected_attendance": row["expected_attendance"],
                "effective_from": row["effective_from"],
                "note": row["note"],
                "old_version_id": row["old_version_id"],
            }
            for row in valid_inputs
        ]
        preview_token = _expected_population_preview_signer.dumps({
            "actor_id": str(current_user.user_id),
            "scope_path": scope_path,
            "csv_text": csv_text,
            "rows": signed_rows,
        })
    unknown_codes = sum(row["status"] == "unknown" for row in response_rows)
    return {
        "rows": response_rows,
        "errors": blocking_errors,
        "can_apply": can_apply,
        "preview_token": preview_token,
        "summary": {
            "matched_locations": len(valid_inputs),
            "unknown_codes": unknown_codes,
            "invalid_rows": sum(bool(row.get("invalid_values")) for row in response_rows),
            "locations_changing": locations_changing,
            "versions_to_add": len(valid_inputs),
        },
    }


def _can_manage_expected_population(current_user: User) -> bool:
    return deps.highest_role_score(current_user) == 5 and deps.has_permission(
        current_user, "population_estimates:manage"
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
    totals = await worker_meeting_analytics(db, scope_path, location_id=location_id)
    items = totals["ranking"]
    opportunities = sum(int(row.get("expected") or 0) for row in items)
    present = sum(int(row.get("present") or 0) for row in items)
    late = sum(int(row.get("late") or 0) for row in items)
    absent = sum(int(row.get("absent") or 0) for row in items)
    excused = sum(int(row.get("excused") or 0) for row in items)
    worker_filters = [_scope_filter(Worker.path, scope_path), Worker.is_deleted.is_(False)]
    if location_id:
        worker_filters.append(Worker.location_id == location_id)
    current_roster = int((await db.execute(select(func.count(Worker.worker_id)).where(and_(*worker_filters)))).scalar_one())
    rate = round(((present + late) / opportunities) * 100, 1) if opportunities else 0
    return {
        'expected': opportunities,
        'current_roster': current_roster,
        'opportunities': opportunities,
        'present': present,
        'late': late,
        'absent': absent,
        'excused': excused,
        'rate': rate,
        'meetings_reported': sum(int(row.get("meetings") or 0) for row in items),
        'legacy_roster_meetings': sum(int(row.get("legacy_roster_meetings") or 0) for row in items),
        'deduplicated': True,
    }


async def _get_timeseries(db: AsyncSession, scope_path: str, *, metric: str) -> list[dict[str, Any]]:
    start_date = reporting_today() - timedelta(days=90)
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
    today = today or reporting_today()
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
            payload['attendance_summary'] = (
                payload.get('summary', {}).get('attendance_summary')
                if isinstance(payload.get('summary'), dict)
                else await _get_attendance_summary(db, effective_scope, location_id=effective_location_id)
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
    today = reporting_today()
    latest = latest_date or (today - timedelta(days=(today.weekday() + 1) % 7))
    if latest.weekday() != 6:
        raise HTTPException(status_code=422, detail="latest_date must be a Sunday")
    occurrence_dates = [latest - timedelta(weeks=index) for index in reversed(range(weeks))]
    return await SundayWorshipAnalytics.series(
        db, effective_scope, occurrence_dates=occurrence_dates, include_pending=include_pending,
    )


@router.get(
    "/analytics/sunday-worship/dashboard",
    dependencies=[Depends(deps.PermissionChecker("statistics:read"))],
)
async def get_sunday_worship_dashboard_payload(
    scope_path: Optional[str] = Query(None),
    weeks: int = Query(4, ge=4, le=8),
    latest_date: Optional[date] = Query(None),
    include_pending: bool = Query(False),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict[str, Any]:
    """Fetch the headline summary and dashboard series under one auth/session."""
    effective_scope = _effective_scope(current_user, scope_path)
    today = reporting_today()
    latest = latest_date or (today - timedelta(days=(today.weekday() + 1) % 7))
    if latest.weekday() != 6:
        raise HTTPException(status_code=422, detail="latest_date must be a Sunday")
    occurrence_dates = [latest - timedelta(weeks=index) for index in reversed(range(weeks))]
    series = await SundayWorshipAnalytics.series(
        db, effective_scope, occurrence_dates=occurrence_dates, include_pending=include_pending,
    )
    summary = await DashboardService.get_summary(db, effective_scope, weeks=weeks, latest_date=latest)
    bootstrap = {
        "scope_path": effective_scope,
        "authorized_scope_path": deps.effective_scope_path(current_user),
        "scope_kind": _scope_kind(effective_scope),
        "population_period": "recent",
        "summary": summary,
        "worker_analytics": {
            "total": summary["workers_total"],
            "active": summary["active_workers"],
            "pending_verification": summary["pending_workers"],
            "suspended": summary["suspended_workers"],
        },
        "attendance_summary": summary.get("attendance_summary") or {},
    }
    return {"series": series, "bootstrap": bootstrap}


@router.get(
    "/analytics/sunday-worship/panels",
    dependencies=[Depends(deps.PermissionChecker("statistics:read"))],
)
async def get_sunday_worship_dashboard_panels(
    scope_path: Optional[str] = Query(None),
    weeks: int = Query(4, ge=4, le=8),
    latest_date: Optional[date] = Query(None),
    include_pending: bool = Query(False),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict[str, Any]:
    """Load the deferred trend/table and (when allowed) review queue together."""
    effective_scope = _effective_scope(current_user, scope_path)
    today = reporting_today()
    latest = latest_date or (today - timedelta(days=(today.weekday() + 1) % 7))
    if latest.weekday() != 6:
        raise HTTPException(status_code=422, detail="latest_date must be a Sunday")
    occurrence_dates = [latest - timedelta(weeks=index) for index in reversed(range(weeks))]
    series = await SundayWorshipAnalytics.series(
        db, effective_scope, occurrence_dates=occurrence_dates, include_pending=include_pending,
    )
    can_review = any(
        getattr(permission, "permission", None) == "counts:review"
        for role_row in (current_user.roles or [])
        for permission in (role_row.permissions or [])
    )
    review_groups: list[dict[str, Any]] = []
    if not can_review:
        return {"series": series, "can_review": False, "review_groups": []}
    if can_review:
        from app.api.v1.routes.counts import list_count_review_groups

        review_groups = await list_count_review_groups(db=db, current_user=current_user)
    return {"series": series, "can_review": can_review, "review_groups": review_groups}


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
    date_limit = as_of or reporting_today()
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
    dependencies=[Depends(deps.PermissionChecker("population_estimates:manage"))],
)
async def create_expected_population_version(
    payload: ExpectedPopulationVersionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict[str, Any]:
    """Append a version; never overwrite a historical expectation."""
    if not _can_manage_expected_population(current_user):
        raise HTTPException(status_code=403, detail="Expected Sunday attendance management is not permitted for this account")
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


@router.post(
    "/expected-population/bulk-preview",
    dependencies=[Depends(deps.PermissionChecker("population_estimates:manage"))],
)
async def preview_expected_population_bulk(
    payload: ExpectedPopulationBulkPreviewRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict[str, Any]:
    """Validate a CSV and return an expiring, signed preview without writing rows."""
    return await _build_expected_population_bulk_preview(db, current_user, payload.csv_text)


@router.post(
    "/expected-population/bulk-apply",
    dependencies=[Depends(deps.PermissionChecker("population_estimates:manage"))],
)
async def apply_expected_population_bulk(
    payload: ExpectedPopulationBulkApplyRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict[str, Any]:
    """Apply exactly the signed preview after rechecking scope and current versions."""
    if not _can_manage_expected_population(current_user):
        raise HTTPException(status_code=403, detail="Only the State Overseer can maintain expected Sunday attendance")
    try:
        signed = _expected_population_preview_signer.loads(
            payload.preview_token,
            max_age=_EXPECTED_POPULATION_PREVIEW_TTL_SECONDS,
        )
    except SignatureExpired as exc:
        raise HTTPException(status_code=410, detail="This preview expired; upload or paste the CSV again.") from exc
    except BadSignature as exc:
        raise HTTPException(status_code=400, detail="Preview token is invalid; create a new preview.") from exc

    scope_path = deps.effective_scope_path(current_user)
    if signed.get("actor_id") != str(current_user.user_id) or signed.get("scope_path") != scope_path:
        raise HTTPException(status_code=403, detail="Preview belongs to a different user or State scope")
    fresh = await _build_expected_population_bulk_preview(
        db, current_user, str(signed.get("csv_text") or ""), lock_locations=True,
    )
    if not fresh.get("can_apply"):
        raise HTTPException(status_code=409, detail="CSV validation changed; review a new preview before applying.")

    expected = [
        (row.get("line"), row.get("location_id"), row.get("path"), row.get("expected_attendance"), row.get("effective_from"), row.get("old_version_id"))
        for row in signed.get("rows", [])
    ]
    current = [
        (row.get("line"), row.get("location_id"), row.get("path"), row.get("expected_attendance"), row.get("effective_from"), row.get("old_version_id"))
        for row in fresh.get("rows", [])
    ]
    if not expected or expected != current:
        raise HTTPException(status_code=409, detail="An estimate changed after preview. Refresh the preview before applying.")

    versions: list[LocationExpectedPopulation] = []
    audits: list[AuditLog] = []
    for row in fresh["rows"]:
        version = LocationExpectedPopulation(
            location_id=row["location_id"],
            path=row["path"],
            expected_value=int(row["expected_attendance"]),
            effective_from=date.fromisoformat(row["effective_from"]),
            set_by_id=current_user.user_id,
            note=row.get("note") or None,
        )
        versions.append(version)
        audits.append(AuditLog(
            user_id=current_user.user_id,
            action="BULK_SET_LOCATION_EXPECTED_POPULATION",
            resource_type="location_expected_population",
            resource_id=str(row["location_id"]),
            changes={
                "source": "csv",
                "location_code": row["location_code"],
                "expected_value": int(row["expected_attendance"]),
                "effective_from": row["effective_from"],
                "note": row.get("note") or "",
            },
        ))
    db.add_all([*versions, *audits])
    await db.commit()
    return {"status": "applied", "versions_added": len(versions), "audit_entries": len(audits)}


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
