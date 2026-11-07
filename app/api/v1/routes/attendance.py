"""
Worker Attendance routes.
"""
from typing import Any, List
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.filters import scope_filter
from app.crud.crud_attendance import attendance as crud_attendance
from app.schemas.attendance import (
    WorkerAttendanceCreate, WorkerAttendanceResponse, WorkerAttendanceUpdate,
    WorkerLookupResponse, WorkerAttendanceSubmissionResponse,
)
from app.schemas.user import WorkerResponse
from app.schemas.sync import SyncResult
from sqlalchemy import select, func, text, case
from datetime import date
from app.models.user import User
from app.models.attendance import WorkerAttendanceSubmission

router = APIRouter()


@router.get(
    "/workers",
    response_model=List[WorkerResponse],
    dependencies=[Depends(deps.PermissionChecker("attendance:read"))],
)
async def list_workers_for_attendance(
    db: AsyncSession = Depends(deps.get_db),
    location_id: str = Query(..., description="Location ID to list workers for"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List workers eligible for attendance at a location."""
    from app.models.user import Worker
    await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=location_id,
        detail="Attendance location outside your scope",
    )
    query = select(Worker).where(
        Worker.location_id == location_id,
        Worker.approval_status == "approved",
        Worker.is_deleted == False,
    ).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get(
    "/workers/search",
    response_model=List[WorkerLookupResponse],
    dependencies=[Depends(deps.PermissionChecker("attendance:read"))],
)
async def search_workers_for_attendance(
    db: AsyncSession = Depends(deps.get_db),
    prefix: str = Query(..., min_length=1, description="Prefix search (e.g., 'A' for A-names)"),
    scope_path: str = Query(None, description="Optional scope path (must be within your scope)"),
    location_id: str = Query(None, description="Optional location filter"),
    limit: int = 20,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Prefix search for workers within scope, optimized for attendance UI."""
    effective_scope = deps.resolve_scope_path(current_user, scope_path)

    from app.models.user import Worker
    query = select(Worker).where(
        scope_filter(Worker.path, effective_scope),
        Worker.approval_status == "approved",
        Worker.is_deleted == False,
        Worker.name.ilike(f"{prefix}%"),
    )
    if location_id:
        query = query.where(Worker.location_id == location_id)
    query = query.order_by(Worker.name.asc()).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.post(
    "/",
    response_model=WorkerAttendanceResponse,
    dependencies=[Depends(deps.PermissionChecker("attendance:create"))],
)
async def create_attendance(
    *,
    db: AsyncSession = Depends(deps.get_db),
    attendance_in: WorkerAttendanceCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit a worker attendance record."""
    await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=attendance_in.location_id,
        detail="Attendance location outside your scope",
    )
    created = await crud_attendance.create(db, obj_in=attendance_in, user_id=current_user.user_id)
    deps.ensure_path_in_scope(current_user, created.path, detail="Existing attendance is outside your scope")
    try:
        from app.api.v1.routes.websocket import manager
        import json
        await manager.broadcast(json.dumps({"type": "attendance_created", "data": {"id": str(created.id), "location_id": created.location_id}}))
    except Exception:
        pass
    return created


@router.get(
    "/",
    response_model=List[WorkerAttendanceResponse],
    dependencies=[Depends(deps.PermissionChecker("attendance:read"))],
)
async def read_attendance(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """Retrieve attendance records with scope filtering."""
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    rows = await crud_attendance.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )
    return deps.filter_rows_in_scope(rows, current_user)


@router.get(
    "/submissions",
    response_model=List[WorkerAttendanceSubmissionResponse],
    dependencies=[Depends(deps.PermissionChecker("attendance:read"))],
)
async def read_attendance_submissions(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    scope_path: str = Query(None, description="Optional narrower scope path"),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Read complete usher captures, including the roster and authenticated submitter."""
    query = select(WorkerAttendanceSubmission).where(
        deps.scope_condition(WorkerAttendanceSubmission.path, current_user, scope_path),
        WorkerAttendanceSubmission.is_deleted.is_(False),
    ).order_by(WorkerAttendanceSubmission.date.desc(), WorkerAttendanceSubmission.created_at.desc())
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()


@router.put(
    "/{attendance_id}",
    response_model=WorkerAttendanceResponse,
    dependencies=[Depends(deps.PermissionChecker("attendance:update"))],
)
async def update_attendance_record(
    *,
    db: AsyncSession = Depends(deps.get_db),
    attendance_id: UUID,
    attendance_in: WorkerAttendanceUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update an attendance record."""
    record = await crud_attendance.get(db, id=attendance_id)
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    deps.ensure_path_in_scope(current_user, record.path, detail="Attendance record outside your scope")
    
    return await crud_attendance.update(db, db_obj=record, obj_in=attendance_in)


@router.post(
    "/batch",
    response_model=SyncResult,
    dependencies=[Depends(deps.PermissionChecker("attendance:create"))],
)
async def batch_create_attendance(
    *,
    db: AsyncSession = Depends(deps.get_db),
    items: List[WorkerAttendanceCreate],
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Batch submit worker attendance (offline sync convenience)."""
    if any(item.client_id is None for item in items):
        raise HTTPException(status_code=422, detail="Every attendance batch item requires a stable client_id")
    result = SyncResult()
    details = []
    for item in items:
        try:
            await deps.get_location_in_scope(
                db, current_user=current_user, location_id=item.location_id,
                detail="Attendance location outside your scope",
            )
            existing = None
            if item.client_id:
                existing = await crud_attendance.get_by_client_id(db, client_id=item.client_id)
            if existing:
                deps.ensure_path_in_scope(current_user, existing.path, detail="Existing attendance is outside your scope")
                result.duplicates += 1
                details.append({"client_id": item.client_id, "id": existing.id, "status": "duplicate"})
                continue
            created = await crud_attendance.create(db, obj_in=item, user_id=current_user.user_id)
            is_duplicate = bool(getattr(created, "_was_duplicate_submission", False))
            deps.ensure_path_in_scope(current_user, created.path, detail="Existing attendance is outside your scope")
            result.duplicates += int(is_duplicate)
            result.synced += int(not is_duplicate)
            details.append({"client_id": item.client_id, "id": created.id, "status": "duplicate" if is_duplicate else "synced"})
        except Exception as e:
            await db.rollback()
            result.errors += 1
            details.append({"client_id": item.client_id, "error": str(e), "status": "error"})
    result.details = details
    return result


@router.get(
    "/stats",
    dependencies=[Depends(deps.PermissionChecker("attendance:read"))],
)
async def get_attendance_stats(
    start_date: date = None,
    end_date: date = None,
    scope_path: str | None = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return aggregate attendance stats within scope and date range."""
    scope_path = deps.resolve_scope_path(current_user, scope_path)
    from app.models.attendance import WorkerAttendance
    query = select(
        func.count(WorkerAttendance.id).label("count"),
        func.sum(case((WorkerAttendance.status == "present", 1), else_=0)).label("present"),
        func.sum(case((WorkerAttendance.status == "absent", 1), else_=0)).label("absent"),
        func.sum(case((WorkerAttendance.status == "late", 1), else_=0)).label("late"),
        func.sum(case((WorkerAttendance.status == "excused", 1), else_=0)).label("excused"),
    ).where(
        scope_filter(WorkerAttendance.path, scope_path)
    )
    if start_date:
        query = query.where(WorkerAttendance.date >= start_date)
    if end_date:
        query = query.where(WorkerAttendance.date < end_date + timedelta(days=1))
    query = query.where(WorkerAttendance.is_deleted.is_(False))
    result = await db.execute(query)
    row = result.first()
    opportunity_filters = [
        scope_filter(WorkerAttendanceSubmission.program_scope_path, scope_path),
        WorkerAttendanceSubmission.is_deleted.is_(False),
        *([WorkerAttendanceSubmission.date >= datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)] if start_date else []),
        *([WorkerAttendanceSubmission.date < datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)] if end_date else []),
    ]
    opportunity_result = await db.execute(select(
        func.coalesce(func.sum(WorkerAttendanceSubmission.expected_workers_count), 0).label("opportunities"),
        func.coalesce(func.sum(WorkerAttendanceSubmission.present_count), 0).label("submitted_present"),
    ).where(*opportunity_filters))
    opportunities = opportunity_result.one()
    expected_opportunities = int(opportunities.opportunities or 0)
    submitted_present = int(opportunities.submitted_present or 0)
    return {
        "count": row.count if row else 0,
        "present": row.present if row else 0,
        "absent": row.absent if row else 0,
        "late": row.late if row else 0,
        "excused": row.excused if row else 0,
        "expected": expected_opportunities,
        "opportunities": expected_opportunities,
        "rate": round(submitted_present * 100 / expected_opportunities, 1) if expected_opportunities else 0,
    }


@router.get(
    "/{attendance_id}",
    response_model=WorkerAttendanceResponse,
    dependencies=[Depends(deps.PermissionChecker("attendance:read"))],
)
async def read_attendance_record(
    *,
    db: AsyncSession = Depends(deps.get_db),
    attendance_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a specific attendance record by ID."""
    record = await crud_attendance.get(db, id=attendance_id)
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    deps.ensure_path_in_scope(current_user, record.path, detail="Attendance record outside your scope")
    return record


@router.delete(
    "/{attendance_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("attendance:delete"))],
)
async def delete_attendance_record(
    *,
    db: AsyncSession = Depends(deps.get_db),
    attendance_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete an attendance record."""
    record = await crud_attendance.get(db, id=attendance_id)
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    deps.ensure_path_in_scope(current_user, record.path, detail="Attendance record outside your scope")
    
    await crud_attendance.update(
        db,
        db_obj=record,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None
