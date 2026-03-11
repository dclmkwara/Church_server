"""
Worker Attendance routes.
"""
from typing import Any, List
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_attendance import attendance as crud_attendance
from app.schemas.attendance import WorkerAttendanceCreate, WorkerAttendanceResponse, WorkerAttendanceUpdate
from app.schemas.user import WorkerResponse
from app.schemas.sync import SyncResult
from sqlalchemy import select, func, text, case
from datetime import date
from app.models.user import User

router = APIRouter()


@router.get(
    "/workers",
    response_model=List[WorkerResponse],
    dependencies=[Depends(deps.PermissionChecker("attendance:read"))],
)
async def list_workers_for_attendance(
    db: AsyncSession = Depends(deps.get_db),
    location_id: str = Query(..., description="Location ID to list workers for"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List workers eligible for attendance at a location."""
    from app.models.user import Worker
    query = select(Worker).where(Worker.location_id == location_id).offset(skip).limit(limit)
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
    created = await crud_attendance.create(db, obj_in=attendance_in, user_id=current_user.user_id)
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
    search_scope = scope_path if scope_path else str(current_user.path)
    return await crud_attendance.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )


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
    return record


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
    result = SyncResult()
    details = []
    for item in items:
        try:
            existing = None
            if item.client_id:
                existing = await crud_attendance.get_by_client_id(db, client_id=item.client_id)
            if existing:
                result.duplicates += 1
                details.append({"client_id": item.client_id, "id": existing.id, "status": "duplicate"})
                continue
            created = await crud_attendance.create(db, obj_in=item, user_id=current_user.user_id)
            result.synced += 1
            details.append({"client_id": item.client_id, "id": created.id, "status": "synced"})
        except Exception as e:
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
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return aggregate attendance stats within scope and date range."""
    scope_path = str(current_user.path)
    from app.models.attendance import WorkerAttendance
    query = select(
        func.count(WorkerAttendance.id).label("count"),
        func.sum(case((WorkerAttendance.status == "present", 1), else_=0)).label("present"),
        func.sum(case((WorkerAttendance.status == "absent", 1), else_=0)).label("absent"),
        func.sum(case((WorkerAttendance.status == "late", 1), else_=0)).label("late"),
        func.sum(case((WorkerAttendance.status == "excused", 1), else_=0)).label("excused"),
    ).where(
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
    )
    if start_date:
        query = query.where(WorkerAttendance.created_at >= start_date)
    if end_date:
        query = query.where(WorkerAttendance.created_at <= end_date)
    result = await db.execute(query)
    row = result.first()
    return {
        "count": row.count if row else 0,
        "present": row.present if row else 0,
        "absent": row.absent if row else 0,
        "late": row.late if row else 0,
        "excused": row.excused if row else 0,
    }


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
    
    await crud_attendance.update(
        db,
        db_obj=record,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None
