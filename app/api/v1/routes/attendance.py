"""
Worker Attendance routes.
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_attendance import attendance as crud_attendance
from app.schemas.attendance import WorkerAttendanceCreate, WorkerAttendanceResponse, WorkerAttendanceUpdate
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=WorkerAttendanceResponse)
async def create_attendance(
    *,
    db: AsyncSession = Depends(deps.get_db),
    attendance_in: WorkerAttendanceCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit a worker attendance record."""
    return await crud_attendance.create(db, obj_in=attendance_in, user_id=current_user.user_id)


@router.get("/", response_model=List[WorkerAttendanceResponse])
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


@router.get("/{attendance_id}", response_model=WorkerAttendanceResponse)
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


@router.put("/{attendance_id}", response_model=WorkerAttendanceResponse)
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
