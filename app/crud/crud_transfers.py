from app.core.auth_cache import invalidate_user_cache
"""
CRUD operations for WorkerTransfer and WorkerAbsenceNotice.
"""
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Group, Location, Region, State
from app.models.transfers import WorkerTransfer
from app.models.attendance import WorkerAbsenceNotice
from app.models.user import User, Worker
from app.schemas.transfers import (
    WorkerTransferCreate,
    WorkerAbsenceNoticeCreate,
)


# ─────────────────────────────────────────────
# Worker Transfer
# ─────────────────────────────────────────────

async def create_transfer(
    db: AsyncSession,
    *,
    obj_in: WorkerTransferCreate,
    requested_by_id: UUID,
) -> WorkerTransfer:
    """Create a new transfer request."""
    worker_result = await db.execute(
        select(Worker).where(
            Worker.worker_id == obj_in.worker_id,
            Worker.is_deleted == False,
        )
    )
    worker = worker_result.scalars().first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    if worker.approval_status != "approved" or str(worker.status or "").lower() != "active":
        raise HTTPException(status_code=409, detail="Only active approved workers may be transferred")
    if worker.approval_status != "approved" or str(worker.status or "").lower() != "active":
        raise HTTPException(status_code=409, detail="Only active approved workers may be transferred")
    if worker.location_id != obj_in.from_location_id:
        raise HTTPException(status_code=400, detail="Origin location does not match the worker record")
    if obj_in.from_location_id == obj_in.to_location_id:
        raise HTTPException(status_code=400, detail="Origin and destination locations must be different")
    open_transfer = (await db.execute(select(WorkerTransfer.id).where(
        WorkerTransfer.worker_id == obj_in.worker_id,
        WorkerTransfer.status.notin_(("completed", "rejected")),
        WorkerTransfer.is_deleted.is_(False),
    ).limit(1))).scalar_one_or_none()
    if open_transfer:
        raise HTTPException(status_code=409, detail="This worker already has a transfer awaiting review")

    origin_context = await db.execute(
        select(Location).where(Location.location_id == obj_in.from_location_id)
    )
    destination_context = await db.execute(
        select(Location).where(Location.location_id == obj_in.to_location_id)
    )
    origin = origin_context.scalars().first()
    destination = destination_context.scalars().first()
    if not origin or not destination:
        raise HTTPException(status_code=404, detail="Transfer location not found")
    origin_state = (await db.execute(select(State.state_id).join(Region, Region.state_id == State.state_id).join(Group, Group.region_id == Region.region_id).join(Location, Location.group_id == Group.group_id).where(Location.location_id == origin.location_id))).scalar_one_or_none()
    destination_state = (await db.execute(select(State.state_id).join(Region, Region.state_id == State.state_id).join(Group, Group.region_id == Region.region_id).join(Location, Location.group_id == Group.group_id).where(Location.location_id == destination.location_id))).scalar_one_or_none()
    if not origin_state or str(origin_state) != str(destination_state):
        raise HTTPException(status_code=422, detail="Transfers are limited to locations within the same state")

    # Generate a collision-resistant reference number without table scans.
    year = datetime.now(timezone.utc).year
    ref_number = f"TRF-{year}-{uuid4().hex[:8].upper()}"

    db_obj = WorkerTransfer(
        worker_id=obj_in.worker_id,
        from_location_id=obj_in.from_location_id,
        to_location_id=obj_in.to_location_id,
        transfer_reason=obj_in.transfer_reason,
        effective_date=obj_in.effective_date,
        requested_by_id=requested_by_id,
        status="pending",
        current_level=3,
        workflow_stage="origin_group",
        reviews=[{"level": 2, "reviewer_id": str(requested_by_id), "action": "submit", "notes": obj_in.transfer_reason, "at": datetime.now(timezone.utc).isoformat()}],
        reference_number=ref_number,
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_transfer(db: AsyncSession, *, transfer_id: UUID) -> Optional[WorkerTransfer]:
    result = await db.execute(
        select(WorkerTransfer).where(
            WorkerTransfer.id == transfer_id,
            WorkerTransfer.is_deleted == False,
        )
    )
    return result.scalars().first()


async def get_transfers_for_worker(
    db: AsyncSession,
    *,
    worker_id: UUID,
) -> List[WorkerTransfer]:
    result = await db.execute(
        select(WorkerTransfer)
        .where(
            WorkerTransfer.worker_id == worker_id,
            WorkerTransfer.is_deleted == False,
        )
        .order_by(WorkerTransfer.created_at.desc())
    )
    return result.scalars().all()


async def get_transfers_by_location(
    db: AsyncSession,
    *,
    location_id: str,
    as_origin: bool = True,
) -> List[WorkerTransfer]:
    """Get pending transfers for a location (as origin or destination)."""
    if as_origin:
        condition = WorkerTransfer.from_location_id == location_id
    else:
        condition = WorkerTransfer.to_location_id == location_id

    result = await db.execute(
        select(WorkerTransfer)
        .where(condition, WorkerTransfer.is_deleted == False)
        .order_by(WorkerTransfer.created_at.desc())
    )
    return result.scalars().all()


async def approve_origin(
    db: AsyncSession,
    *,
    transfer: WorkerTransfer,
    approved_by_id: UUID,
    approver_score: int = 3,
    approver_path: Optional[str] = None,
    note: Optional[str] = None,
) -> WorkerTransfer:
    """Advance one governance stage of a worker transfer."""
    stage = transfer.workflow_stage or "origin_group"
    target_id = transfer.from_location_id if stage == "origin_group" else transfer.to_location_id
    target = (await db.execute(select(Location).where(Location.location_id == target_id))).scalars().first()
    if not target or (approver_path and not (str(target.path) == str(approver_path) or str(target.path).startswith(str(approver_path).rstrip(".") + "."))):
        raise HTTPException(status_code=403, detail="Reviewer is outside the location hierarchy required for this stage")
    now = datetime.now(timezone.utc)
    reviews = list(transfer.reviews or [])
    if stage == "origin_group" and approver_score == 3:
        transfer.origin_approved_by = transfer.group_approved_by = approved_by_id
        transfer.origin_approved_at = transfer.group_approved_at = now
        transfer.origin_note = transfer.group_note = note
        transfer.workflow_stage, transfer.current_level, transfer.status = "receiving_location", 2, "pending_receiving_location"
    elif stage == "receiving_location" and approver_score == 2:
        transfer.receiving_location_approved_by = approved_by_id
        transfer.receiving_location_approved_at = now
        transfer.receiving_location_note = note
        transfer.workflow_stage, transfer.current_level, transfer.status = "receiving_group", 3, "pending_receiving_group"
    elif stage == "receiving_group" and approver_score == 3:
        transfer.receiving_group_approved_by = approved_by_id
        transfer.receiving_group_approved_at = now
        transfer.receiving_group_note = note
        transfer.workflow_stage, transfer.current_level, transfer.status = "region", 4, "pending_region"
    elif stage == "region" and approver_score >= 4:
        return await _complete_transfer(db, transfer=transfer, approved_by_id=approved_by_id, note=note)
    else:
        raise HTTPException(status_code=403, detail="Your role cannot approve the current transfer stage")
    reviews.append({"level": approver_score, "reviewer_id": str(approved_by_id), "action": f"approve_{stage}", "notes": note, "at": now.isoformat()})
    transfer.reviews = reviews
    await db.commit()
    await db.refresh(transfer)
    return transfer


async def approve_destination(
    db: AsyncSession,
    *,
    transfer: WorkerTransfer,
    approved_by_id: UUID,
    note: Optional[str] = None,
) -> WorkerTransfer:
    """Compatibility wrapper for the receiving Location Pastor approval."""
    return await approve_origin(db, transfer=transfer, approved_by_id=approved_by_id,
                                approver_score=2, approver_path=transfer.to_location.path if transfer.to_location else "", note=note)


async def _complete_transfer(db: AsyncSession, *, transfer: WorkerTransfer, approved_by_id: UUID, note: Optional[str]) -> WorkerTransfer:
    """Complete transfer only after origin and receiving leadership approvals."""
    destination_result = await db.execute(
        select(Location, Group, Region, State)
        .join(Group, Group.group_id == Location.group_id)
        .join(Region, Region.region_id == Group.region_id)
        .join(State, State.state_id == Region.state_id)
        .where(Location.location_id == transfer.to_location_id)
    )
    destination_context = destination_result.first()
    if not destination_context:
        raise HTTPException(status_code=404, detail="Destination location not found")
    location, group, region, state = destination_context

    worker_result = await db.execute(
        select(Worker).where(
            Worker.worker_id == transfer.worker_id,
            Worker.is_deleted == False,
        )
    )
    worker = worker_result.scalars().first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    transfer.destination_approved_by = transfer.region_approved_by = approved_by_id
    transfer.destination_approved_at = transfer.region_approved_at = datetime.now(timezone.utc)
    transfer.destination_note = transfer.region_note = note
    transfer.status = "completed"

    worker.location_id = location.location_id
    worker.location_name = location.location_name
    worker.church_type = location.church_type
    worker.group = group.group_name
    worker.region = region.region_name
    worker.state = state.state_name
    worker.path = location.path

    user_result = await db.execute(
        select(User).where(
            User.worker_id == worker.worker_id,
            User.is_deleted == False,
        )
    )
    linked_user = user_result.scalars().first()
    if linked_user:
        linked_user.location_id = location.location_id
        linked_user.path = location.path
        invalidate_user_cache(str(linked_user.user_id))

    await db.commit()
    await db.refresh(transfer)
    return transfer


async def reject_transfer(
    db: AsyncSession,
    *,
    transfer: WorkerTransfer,
    rejected_by_id: UUID,
    approver_score: int = 3,
    approver_path: Optional[str] = None,
    rejection_reason: str,
) -> WorkerTransfer:
    if approver_score < transfer.current_level or (transfer.current_level == 2 and approver_score != 2):
        raise HTTPException(status_code=403, detail="Your role cannot reject at the current transfer stage")
    stage = transfer.workflow_stage or "origin_group"
    target_id = transfer.from_location_id if stage == "origin_group" else transfer.to_location_id
    target = (await db.execute(select(Location).where(Location.location_id == target_id))).scalars().first()
    if not target or (approver_path and not (str(target.path) == str(approver_path) or str(target.path).startswith(str(approver_path).rstrip(".") + "."))):
        raise HTTPException(status_code=403, detail="Reviewer is outside the location hierarchy required for this stage")
    transfer.status = "rejected"
    transfer.rejected_by = rejected_by_id
    transfer.rejected_at = datetime.now(timezone.utc)
    transfer.rejection_reason = rejection_reason
    reviews = list(transfer.reviews or [])
    reviews.append({"level": approver_score, "reviewer_id": str(rejected_by_id), "action": "reject", "notes": rejection_reason, "at": datetime.now(timezone.utc).isoformat()})
    transfer.reviews = reviews
    await db.commit()
    await db.refresh(transfer)
    return transfer


async def mark_letter_generated(
    db: AsyncSession,
    *,
    transfer: WorkerTransfer,
    letter_url: str,
) -> WorkerTransfer:
    transfer.letter_generated = True
    transfer.letter_url = letter_url
    await db.commit()
    await db.refresh(transfer)
    return transfer


# ─────────────────────────────────────────────
# Worker Absence Notice
# ─────────────────────────────────────────────

async def create_absence_notice(
    db: AsyncSession,
    *,
    obj_in: WorkerAbsenceNoticeCreate,
    worker_id: UUID,
) -> WorkerAbsenceNotice:
    worker_result = await db.execute(
        select(Worker).where(
            Worker.worker_id == worker_id,
            Worker.is_deleted == False,
        )
    )
    if not worker_result.scalars().first():
        raise HTTPException(status_code=404, detail="Worker not found")

    db_obj = WorkerAbsenceNotice(
        worker_id=worker_id,
        event_id=obj_in.event_id,
        reason=obj_in.reason,
        expected_return=obj_in.expected_return,
        status="noted",
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_absence_notices_for_event(
    db: AsyncSession,
    *,
    event_id: UUID,
) -> List[WorkerAbsenceNotice]:
    result = await db.execute(
        select(WorkerAbsenceNotice)
        .where(WorkerAbsenceNotice.event_id == event_id)
        .order_by(WorkerAbsenceNotice.created_at.desc())
    )
    return result.scalars().all()


async def get_absence_notices_for_worker(
    db: AsyncSession,
    *,
    worker_id: UUID,
) -> List[WorkerAbsenceNotice]:
    result = await db.execute(
        select(WorkerAbsenceNotice)
        .where(WorkerAbsenceNotice.worker_id == worker_id)
        .order_by(WorkerAbsenceNotice.created_at.desc())
    )
    return result.scalars().all()


async def acknowledge_notice(
    db: AsyncSession,
    *,
    notice_id: int,
    admin_id: UUID,
    status: str,  # acknowledged | rejected
    admin_note: Optional[str] = None,
) -> Optional[WorkerAbsenceNotice]:
    if status not in {"acknowledged", "rejected"}:
        raise HTTPException(status_code=400, detail="Invalid notice status")
    result = await db.execute(
        select(WorkerAbsenceNotice).where(WorkerAbsenceNotice.id == notice_id)
    )
    notice = result.scalars().first()
    if not notice:
        return None
    notice.status = status
    notice.acknowledged_by = admin_id
    notice.acknowledged_at = datetime.now(timezone.utc)
    notice.admin_note = admin_note
    await db.commit()
    await db.refresh(notice)
    return notice
