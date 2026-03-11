"""
Fellowship Activities routes.
"""
from typing import Any, List
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_fellowship_activities import member as crud_member
from app.crud.crud_fellowship_activities import attendance as crud_attendance
from app.crud.crud_fellowship_activities import offering as crud_offering
from app.crud.crud_fellowship_activities import testimony as crud_testimony
from app.crud.crud_fellowship_activities import prayer_request as crud_prayer
from app.crud.crud_fellowship_activities import attendance_summary as crud_summary

from app.schemas.fellowship_activities import (
    FellowshipMemberCreate, FellowshipMemberUpdate, FellowshipMemberResponse,
    FellowshipAttendanceCreate, FellowshipAttendanceUpdate, FellowshipAttendanceResponse,
    FellowshipOfferingCreate, FellowshipOfferingUpdate, FellowshipOfferingResponse,
    TestimonyCreate, TestimonyUpdate, TestimonyResponse,
    PrayerRequestCreate, PrayerRequestUpdate, PrayerRequestResponse,
    AttendanceSummaryCreate, AttendanceSummaryUpdate, AttendanceSummaryResponse
)
from app.models.user import User

router = APIRouter()


# ==========================================
# MEMBERS
# ==========================================
@router.post(
    "/members",
    response_model=FellowshipMemberResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:create"))],
)
async def create_fellowship_member(
    *,
    db: AsyncSession = Depends(deps.get_db),
    member_in: FellowshipMemberCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Register a new fellowship member."""
    return await crud_member.create(db, obj_in=member_in)


@router.get(
    "/members",
    response_model=List[FellowshipMemberResponse],
    dependencies=[Depends(deps.PermissionChecker("fellowship:read"))],
)
async def read_fellowship_members(
    db: AsyncSession = Depends(deps.get_db),
    fellowship_id: str = Query(..., description="Fellowship ID to list members for"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List members of a specific fellowship."""
    return await crud_member.get_by_fellowship(db, fellowship_id=fellowship_id, skip=skip, limit=limit)


@router.put(
    "/members/{member_id}",
    response_model=FellowshipMemberResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:update"))],
)
async def update_fellowship_member(
    *,
    db: AsyncSession = Depends(deps.get_db),
    member_id: UUID,
    member_in: FellowshipMemberUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a fellowship member."""
    member = await crud_member.get(db, id=member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return await crud_member.update(db, db_obj=member, obj_in=member_in)


@router.delete(
    "/members/{member_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("fellowship:delete"))],
)
async def delete_fellowship_member(
    *,
    db: AsyncSession = Depends(deps.get_db),
    member_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a fellowship member."""
    member = await crud_member.get(db, id=member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    await crud_member.update(
        db,
        db_obj=member,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None


# ==========================================
# ATTENDANCE
# ==========================================
@router.post(
    "/attendance",
    response_model=FellowshipAttendanceResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:create"))],
)
async def create_fellowship_attendance(
    *,
    db: AsyncSession = Depends(deps.get_db),
    attendance_in: FellowshipAttendanceCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit fellowship attendance."""
    return await crud_attendance.create(db, obj_in=attendance_in, user_id=current_user.user_id)


@router.get(
    "/attendance",
    response_model=List[FellowshipAttendanceResponse],
    dependencies=[Depends(deps.PermissionChecker("fellowship:read"))],
)
async def read_fellowship_attendance(
    db: AsyncSession = Depends(deps.get_db),
    fellowship_id: str = Query(..., description="Fellowship ID to list attendance for"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List attendance records of a specific fellowship."""
    from app.models.fellowship_activities import FellowshipAttendance
    from sqlalchemy import select
    query = select(FellowshipAttendance).where(FellowshipAttendance.fellowship_id == fellowship_id).offset(skip).limit(limit)
    return (await db.execute(query)).scalars().all()


@router.put(
    "/attendance/{attendance_id}",
    response_model=FellowshipAttendanceResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:update"))],
)
async def update_fellowship_attendance(
    *,
    db: AsyncSession = Depends(deps.get_db),
    attendance_id: UUID,
    attendance_in: FellowshipAttendanceUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a fellowship attendance record."""
    record = await crud_attendance.get(db, id=attendance_id)
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    updated = await crud_attendance.update(db, db_obj=record, obj_in=attendance_in)
    if any(
        v is not None for v in [
            attendance_in.men, attendance_in.women, attendance_in.youths, attendance_in.children
        ]
    ):
        updated.total = (updated.men or 0) + (updated.women or 0) + (updated.youths or 0) + (updated.children or 0)
        await db.commit()
        await db.refresh(updated)
    return updated


@router.delete(
    "/attendance/{attendance_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("fellowship:delete"))],
)
async def delete_fellowship_attendance(
    *,
    db: AsyncSession = Depends(deps.get_db),
    attendance_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a fellowship attendance record."""
    record = await crud_attendance.get(db, id=attendance_id)
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    await crud_attendance.update(
        db,
        db_obj=record,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None


# ==========================================
# OFFERINGS
# ==========================================
@router.post(
    "/offerings",
    response_model=FellowshipOfferingResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:create"))],
)
async def create_fellowship_offering(
    *,
    db: AsyncSession = Depends(deps.get_db),
    offering_in: FellowshipOfferingCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit fellowship offering."""
    return await crud_offering.create(db, obj_in=offering_in, user_id=current_user.user_id)


@router.get(
    "/offerings",
    response_model=List[FellowshipOfferingResponse],
    dependencies=[Depends(deps.PermissionChecker("fellowship:read"))],
)
async def read_fellowship_offerings(
    db: AsyncSession = Depends(deps.get_db),
    fellowship_id: str = Query(..., description="Fellowship ID to list offerings for"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List offerings of a specific fellowship."""
    from app.models.fellowship_activities import FellowshipOffering
    from sqlalchemy import select
    query = select(FellowshipOffering).where(FellowshipOffering.fellowship_id == fellowship_id).offset(skip).limit(limit)
    return (await db.execute(query)).scalars().all()


@router.put(
    "/offerings/{offering_id}",
    response_model=FellowshipOfferingResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:update"))],
)
async def update_fellowship_offering(
    *,
    db: AsyncSession = Depends(deps.get_db),
    offering_id: UUID,
    offering_in: FellowshipOfferingUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a fellowship offering record."""
    record = await crud_offering.get(db, id=offering_id)
    if not record:
        raise HTTPException(status_code=404, detail="Offering record not found")
    return await crud_offering.update(db, db_obj=record, obj_in=offering_in)


@router.delete(
    "/offerings/{offering_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("fellowship:delete"))],
)
async def delete_fellowship_offering(
    *,
    db: AsyncSession = Depends(deps.get_db),
    offering_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a fellowship offering record."""
    record = await crud_offering.get(db, id=offering_id)
    if not record:
        raise HTTPException(status_code=404, detail="Offering record not found")
    await crud_offering.update(
        db,
        db_obj=record,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None


# ==========================================
# TESTIMONIES
# ==========================================
@router.post(
    "/testimonies",
    response_model=TestimonyResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:create"))],
)
async def create_fellowship_testimony(
    *,
    db: AsyncSession = Depends(deps.get_db),
    testimony_in: TestimonyCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit fellowship testimony."""
    return await crud_testimony.create(db, obj_in=testimony_in, user_id=current_user.user_id)

@router.get(
    "/testimonies",
    response_model=List[TestimonyResponse],
    dependencies=[Depends(deps.PermissionChecker("fellowship:read"))],
)
async def read_fellowship_testimonies(
    db: AsyncSession = Depends(deps.get_db),
    fellowship_id: str = Query(..., description="Fellowship ID to list testimonies for"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List testimonies of a specific fellowship."""
    # Note: Basic filtering for now, enhancing with complex search later
    from app.models.fellowship_activities import Testimony
    from sqlalchemy import select
    query = select(Testimony).where(Testimony.fellowship_id == fellowship_id).offset(skip).limit(limit)
    return (await db.execute(query)).scalars().all()


@router.put(
    "/testimonies/{testimony_id}",
    response_model=TestimonyResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:update"))],
)
async def update_fellowship_testimony(
    *,
    db: AsyncSession = Depends(deps.get_db),
    testimony_id: UUID,
    testimony_in: TestimonyUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a fellowship testimony."""
    record = await crud_testimony.get(db, id=testimony_id)
    if not record:
        raise HTTPException(status_code=404, detail="Testimony not found")
    return await crud_testimony.update(db, db_obj=record, obj_in=testimony_in)


@router.delete(
    "/testimonies/{testimony_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("fellowship:delete"))],
)
async def delete_fellowship_testimony(
    *,
    db: AsyncSession = Depends(deps.get_db),
    testimony_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a fellowship testimony."""
    record = await crud_testimony.get(db, id=testimony_id)
    if not record:
        raise HTTPException(status_code=404, detail="Testimony not found")
    await crud_testimony.update(
        db,
        db_obj=record,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None


# ==========================================
# PRAYER REQUESTS
# ==========================================
@router.post(
    "/prayers",
    response_model=PrayerRequestResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:create"))],
)
async def create_fellowship_prayer(
    *,
    db: AsyncSession = Depends(deps.get_db),
    prayer_in: PrayerRequestCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit fellowship prayer request."""
    return await crud_prayer.create(db, obj_in=prayer_in, user_id=current_user.user_id)

@router.get(
    "/prayers",
    response_model=List[PrayerRequestResponse],
    dependencies=[Depends(deps.PermissionChecker("fellowship:read"))],
)
async def read_fellowship_prayers(
    db: AsyncSession = Depends(deps.get_db),
    fellowship_id: str = Query(..., description="Fellowship ID to list prayers for"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List prayer requests of a specific fellowship."""
    from app.models.fellowship_activities import PrayerRequest
    from sqlalchemy import select
    query = select(PrayerRequest).where(PrayerRequest.fellowship_id == fellowship_id).offset(skip).limit(limit)
    return (await db.execute(query)).scalars().all()


@router.put(
    "/prayers/{prayer_id}",
    response_model=PrayerRequestResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:update"))],
)
async def update_fellowship_prayer(
    *,
    db: AsyncSession = Depends(deps.get_db),
    prayer_id: UUID,
    prayer_in: PrayerRequestUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a fellowship prayer request."""
    record = await crud_prayer.get(db, id=prayer_id)
    if not record:
        raise HTTPException(status_code=404, detail="Prayer request not found")
    return await crud_prayer.update(db, db_obj=record, obj_in=prayer_in)


@router.delete(
    "/prayers/{prayer_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("fellowship:delete"))],
)
async def delete_fellowship_prayer(
    *,
    db: AsyncSession = Depends(deps.get_db),
    prayer_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a fellowship prayer request."""
    record = await crud_prayer.get(db, id=prayer_id)
    if not record:
        raise HTTPException(status_code=404, detail="Prayer request not found")
    await crud_prayer.update(
        db,
        db_obj=record,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None


# ==========================================
# ATTENDANCE SUMMARIES
# ==========================================
@router.post(
    "/attendance-summaries",
    response_model=AttendanceSummaryResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:create"))],
)
async def create_fellowship_summary(
    *,
    db: AsyncSession = Depends(deps.get_db),
    summary_in: AttendanceSummaryCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit fellowship attendance summary."""
    return await crud_summary.create(db, obj_in=summary_in, user_id=current_user.user_id)

@router.get(
    "/attendance-summaries",
    response_model=List[AttendanceSummaryResponse],
    dependencies=[Depends(deps.PermissionChecker("fellowship:read"))],
)
async def read_fellowship_summaries(
    db: AsyncSession = Depends(deps.get_db),
    fellowship_id: str = Query(..., description="Fellowship ID to list summaries for"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List attendance summaries of a specific fellowship."""
    from app.models.fellowship_activities import AttendanceSummary
    from sqlalchemy import select
    query = select(AttendanceSummary).where(AttendanceSummary.fellowship_id == fellowship_id).offset(skip).limit(limit)
    return (await db.execute(query)).scalars().all()


@router.put(
    "/attendance-summaries/{summary_id}",
    response_model=AttendanceSummaryResponse,
    dependencies=[Depends(deps.PermissionChecker("fellowship:update"))],
)
async def update_fellowship_summary(
    *,
    db: AsyncSession = Depends(deps.get_db),
    summary_id: UUID,
    summary_in: AttendanceSummaryUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a fellowship attendance summary."""
    record = await crud_summary.get(db, id=summary_id)
    if not record:
        raise HTTPException(status_code=404, detail="Attendance summary not found")
    return await crud_summary.update(db, db_obj=record, obj_in=summary_in)


@router.delete(
    "/attendance-summaries/{summary_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("fellowship:delete"))],
)
async def delete_fellowship_summary(
    *,
    db: AsyncSession = Depends(deps.get_db),
    summary_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a fellowship attendance summary."""
    record = await crud_summary.get(db, id=summary_id)
    if not record:
        raise HTTPException(status_code=404, detail="Attendance summary not found")
    await crud_summary.update(
        db,
        db_obj=record,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None
