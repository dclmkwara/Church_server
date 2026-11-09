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
from app.models.location import Fellowship
from app.models.user import User
from app.models.counts import SubmissionEditRevision
from app.models.fellowship_activities import FellowshipAttendance, FellowshipOffering
from app.schemas.counts import CountEditRequest
from app.services.submission_editing import edit_own_submission
from app.services.analytics.program_config import SUBMISSION_EDIT_WINDOW_HOURS, SUBMISSION_MAX_EDITS
from sqlalchemy import select
from datetime import timezone, timedelta

router = APIRouter()


async def _list_my_editable_records(db: AsyncSession, actor: User, model: Any, kind: str) -> list[dict[str, Any]]:
    rows = list((await db.execute(select(model).where(
        model.entered_by_id == actor.user_id, model.is_deleted.is_(False),
    ).order_by(model.created_at.desc()).limit(100))).scalars().all())
    if not rows:
        return []
    histories = list((await db.execute(select(SubmissionEditRevision).where(
        SubmissionEditRevision.submission_type == kind,
        SubmissionEditRevision.submission_id.in_([row.id for row in rows]),
    ).order_by(SubmissionEditRevision.revision_no))).scalars().all())
    by_id: dict[str, list[Any]] = {}
    for item in histories:
        by_id.setdefault(str(item.submission_id), []).append(item)
    now = datetime.now(timezone.utc)
    result = []
    for row in rows:
        history = by_id.get(str(row.id), [])
        last_return = next((item for item in reversed(history) if item.action == "returned"), None)
        opened = last_return.created_at if last_return else row.created_at
        remaining = max(0, SUBMISSION_EDIT_WINDOW_HOURS * 3600 - (now - opened).total_seconds()) if opened else 0
        used = sum(item.action == "edit" for item in history)
        limit = SUBMISSION_MAX_EDITS + (1 if last_return else 0)
        result.append({
            "id": str(row.id), "date": row.date.isoformat(), "revision": history[-1].revision_no if history else 0,
            "values": ({
                "men": row.men, "women": row.women, "youths": row.youths, "children": row.children,
                "adult_male": row.adult_male, "adult_female": row.adult_female,
                "youth_male": row.youth_male, "youth_female": row.youth_female,
                "boys": row.boys, "girls": row.girls,
                "total": row.total, "topic": row.topic, "note": row.note,
            }
                       if kind == "fellowship_attendance" else {"amount": str(row.amount), "note": row.note}),
            "edits_remaining": max(0, limit - used), "hours_remaining": round(remaining / 3600, 1),
            "locked": remaining <= 0 or used >= limit,
            "locked_message": "The 24-hour edit window has closed." if remaining <= 0 else "The edit limit has been reached." if used >= limit else "",
        })
    return result


@router.get("/attendance/mine/editable")
async def list_my_editable_fellowship_attendance(db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return await _list_my_editable_records(db, current_user, FellowshipAttendance, "fellowship_attendance")


@router.post("/attendance/{attendance_id}/edit")
async def edit_own_fellowship_attendance(attendance_id: UUID, payload: CountEditRequest,
        db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return await edit_own_submission(db, model=FellowshipAttendance, submission_type="fellowship_attendance",
        submission_id=attendance_id, edit_id=payload.edit_id, base_revision=payload.base_revision,
        values=payload.values, actor=current_user,
        allowed_fields={"men", "women", "youths", "children", "adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls", "topic", "note"})


@router.get("/offerings/mine/editable")
async def list_my_editable_fellowship_offerings(db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return await _list_my_editable_records(db, current_user, FellowshipOffering, "fellowship_offering")


@router.post("/offerings/{offering_id}/edit")
async def edit_own_fellowship_offering(offering_id: UUID, payload: CountEditRequest,
        db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return await edit_own_submission(db, model=FellowshipOffering, submission_type="fellowship_offering",
        submission_id=offering_id, edit_id=payload.edit_id, base_revision=payload.base_revision,
        values=payload.values, actor=current_user, allowed_fields={"amount", "note"})


async def _ensure_fellowship_in_scope(db: AsyncSession, current_user: User, fellowship_id: str) -> Fellowship:
    fellowship = await db.get(Fellowship, fellowship_id)
    if not fellowship:
        raise HTTPException(status_code=404, detail="Fellowship not found")
    deps.ensure_path_in_scope(current_user, fellowship.path, detail="Fellowship outside your scope")
    return fellowship


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
    await _ensure_fellowship_in_scope(db, current_user, member_in.fellowship_id)
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
    await _ensure_fellowship_in_scope(db, current_user, fellowship_id)
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
    deps.ensure_path_in_scope(current_user, member.path, detail="Fellowship member outside your scope")
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
    deps.ensure_path_in_scope(current_user, member.path, detail="Fellowship member outside your scope")
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
    await _ensure_fellowship_in_scope(db, current_user, attendance_in.fellowship_id)
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
    await _ensure_fellowship_in_scope(db, current_user, fellowship_id)
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
    deps.ensure_path_in_scope(current_user, record.path, detail="Fellowship attendance outside your scope")
    raise HTTPException(status_code=409, detail="Submitted fellowship attendance is locked to the original report. Use the submitter edit window for corrections.")


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
    deps.ensure_path_in_scope(current_user, record.path, detail="Fellowship attendance outside your scope")
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
    await _ensure_fellowship_in_scope(db, current_user, offering_in.fellowship_id)
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
    await _ensure_fellowship_in_scope(db, current_user, fellowship_id)
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
    deps.ensure_path_in_scope(current_user, record.path, detail="Fellowship offering outside your scope")
    raise HTTPException(status_code=409, detail="Submitted fellowship offerings are locked to the original report. Use the submitter edit window for corrections.")


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
    deps.ensure_path_in_scope(current_user, record.path, detail="Fellowship offering outside your scope")
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
    await _ensure_fellowship_in_scope(db, current_user, testimony_in.fellowship_id)
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
    await _ensure_fellowship_in_scope(db, current_user, fellowship_id)
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
    deps.ensure_path_in_scope(current_user, record.path, detail="Fellowship testimony outside your scope")
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
    deps.ensure_path_in_scope(current_user, record.path, detail="Fellowship testimony outside your scope")
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
    await _ensure_fellowship_in_scope(db, current_user, prayer_in.fellowship_id)
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
    await _ensure_fellowship_in_scope(db, current_user, fellowship_id)
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
    deps.ensure_path_in_scope(current_user, record.path, detail="Fellowship prayer outside your scope")
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
    deps.ensure_path_in_scope(current_user, record.path, detail="Fellowship prayer outside your scope")
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
    await _ensure_fellowship_in_scope(db, current_user, summary_in.fellowship_id)
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
    await _ensure_fellowship_in_scope(db, current_user, fellowship_id)
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
    deps.ensure_path_in_scope(current_user, record.path, detail="Fellowship summary outside your scope")
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
    deps.ensure_path_in_scope(current_user, record.path, detail="Fellowship summary outside your scope")
    await crud_summary.update(
        db,
        db_obj=record,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None
