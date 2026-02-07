"""
Fellowship Activities routes.
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_fellowship_activities import member as crud_member
from app.crud.crud_fellowship_activities import attendance as crud_attendance
from app.crud.crud_fellowship_activities import offering as crud_offering
from app.crud.crud_fellowship_activities import testimony as crud_testimony
from app.crud.crud_fellowship_activities import prayer_request as crud_prayer
from app.crud.crud_fellowship_activities import attendance_summary as crud_summary

from app.schemas.fellowship_activities import (
    FellowshipMemberCreate, FellowshipMemberResponse,
    FellowshipAttendanceCreate, FellowshipAttendanceResponse,
    FellowshipOfferingCreate, FellowshipOfferingResponse,
    TestimonyCreate, TestimonyResponse,
    PrayerRequestCreate, PrayerRequestResponse,
    AttendanceSummaryCreate, AttendanceSummaryResponse
)
from app.models.user import User

router = APIRouter()


# ==========================================
# MEMBERS
# ==========================================
@router.post("/members", response_model=FellowshipMemberResponse)
async def create_fellowship_member(
    *,
    db: AsyncSession = Depends(deps.get_db),
    member_in: FellowshipMemberCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Register a new fellowship member."""
    return await crud_member.create(db, obj_in=member_in)


@router.get("/members", response_model=List[FellowshipMemberResponse])
async def read_fellowship_members(
    db: AsyncSession = Depends(deps.get_db),
    fellowship_id: str = Query(..., description="Fellowship ID to list members for"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List members of a specific fellowship."""
    return await crud_member.get_by_fellowship(db, fellowship_id=fellowship_id, skip=skip, limit=limit)


# ==========================================
# ATTENDANCE
# ==========================================
@router.post("/attendance", response_model=FellowshipAttendanceResponse)
async def create_fellowship_attendance(
    *,
    db: AsyncSession = Depends(deps.get_db),
    attendance_in: FellowshipAttendanceCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit fellowship attendance."""
    return await crud_attendance.create(db, obj_in=attendance_in, user_id=current_user.user_id)


# ==========================================
# OFFERINGS
# ==========================================
@router.post("/offerings", response_model=FellowshipOfferingResponse)
async def create_fellowship_offering(
    *,
    db: AsyncSession = Depends(deps.get_db),
    offering_in: FellowshipOfferingCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit fellowship offering."""
    return await crud_offering.create(db, obj_in=offering_in, user_id=current_user.user_id)


# ==========================================
# TESTIMONIES
# ==========================================
@router.post("/testimonies", response_model=TestimonyResponse)
async def create_fellowship_testimony(
    *,
    db: AsyncSession = Depends(deps.get_db),
    testimony_in: TestimonyCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit fellowship testimony."""
    return await crud_testimony.create(db, obj_in=testimony_in, user_id=current_user.user_id)

@router.get("/testimonies", response_model=List[TestimonyResponse])
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


# ==========================================
# PRAYER REQUESTS
# ==========================================
@router.post("/prayers", response_model=PrayerRequestResponse)
async def create_fellowship_prayer(
    *,
    db: AsyncSession = Depends(deps.get_db),
    prayer_in: PrayerRequestCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit fellowship prayer request."""
    return await crud_prayer.create(db, obj_in=prayer_in, user_id=current_user.user_id)

@router.get("/prayers", response_model=List[PrayerRequestResponse])
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


# ==========================================
# ATTENDANCE SUMMARIES
# ==========================================
@router.post("/attendance-summaries", response_model=AttendanceSummaryResponse)
async def create_fellowship_summary(
    *,
    db: AsyncSession = Depends(deps.get_db),
    summary_in: AttendanceSummaryCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit fellowship attendance summary."""
    return await crud_summary.create(db, obj_in=summary_in, user_id=current_user.user_id)

@router.get("/attendance-summaries", response_model=List[AttendanceSummaryResponse])
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
