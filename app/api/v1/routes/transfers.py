"""
API routes for WorkerTransfer and WorkerAbsenceNotice.

Worker Transfers:
  POST   /api/v1/transfers                              — Request transfer
  GET    /api/v1/transfers                              — List transfers in scope
  GET    /api/v1/transfers/{transfer_id}                — Get single transfer
  POST   /api/v1/transfers/{transfer_id}/approve-origin — Origin pastor approves
  POST   /api/v1/transfers/{transfer_id}/approve-dest   — Destination pastor approves
  POST   /api/v1/transfers/{transfer_id}/reject         — Reject transfer
  GET    /api/v1/transfers/{transfer_id}/letter         — Download PDF letter

Worker Absence Notices:
  POST   /api/v1/attendance/absence-notices                   — Worker submits notice
  GET    /api/v1/attendance/absence-notices                   — List notices (for pastor)
  POST   /api/v1/attendance/absence-notices/{id}/acknowledge  — Pastor acknowledges
"""
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud import crud_transfers
from app.models.user import User
from app.schemas.transfers import (
    WorkerTransferCreate,
    WorkerTransferResponse,
    WorkerTransferApproveOrigin,
    WorkerTransferApproveDestination,
    WorkerTransferReject,
    WorkerAbsenceNoticeCreate,
    WorkerAbsenceNoticeResponse,
    WorkerAbsenceNoticeAcknowledge,
)

router = APIRouter()


async def _ensure_transfer_access(db: AsyncSession, current_user: User, transfer) -> None:
    for location_id in (transfer.from_location_id, transfer.to_location_id):
        try:
            await deps.get_location_in_scope(
                db,
                current_user=current_user,
                location_id=location_id,
                detail="Transfer outside your scope",
            )
            return
        except HTTPException:
            continue
    raise HTTPException(status_code=403, detail="Transfer outside your scope")


# ─────────────────────────────────────────────
# Worker Transfers
# ─────────────────────────────────────────────

@router.post(
    "",
    response_model=WorkerTransferResponse,
    status_code=201,
    tags=["Workers"],
    dependencies=[Depends(deps.PermissionChecker("workers:update"))],
)
async def request_transfer(
    *,
    db: AsyncSession = Depends(deps.get_db),
    transfer_in: WorkerTransferCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Request a formal worker transfer from one location to another.
    Creates a pending transfer with a unique reference number (TRF-YYYY-NNNN).
    """
    deps.ensure_path_in_scope(current_user, current_user.path, detail="Current user has no scope")
    await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=transfer_in.from_location_id,
        detail="Origin location outside your scope",
    )
    return await crud_transfers.create_transfer(
        db, obj_in=transfer_in, requested_by_id=current_user.user_id
    )


@router.get(
    "",
    response_model=List[WorkerTransferResponse],
    tags=["Workers"],
    dependencies=[Depends(deps.PermissionChecker("workers:read"))],
)
async def list_transfers(
    *,
    db: AsyncSession = Depends(deps.get_db),
    worker_id: Optional[UUID] = Query(None),
    location_id: Optional[str] = Query(None),
    as_origin: bool = Query(True, description="True = transfers leaving location, False = transfers arriving"),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List worker transfers filtered by worker or location."""
    if worker_id:
        return await crud_transfers.get_transfers_for_worker(db, worker_id=worker_id)
    if location_id:
        await deps.get_location_in_scope(
            db,
            current_user=current_user,
            location_id=location_id,
            detail="Location outside your scope",
        )
        return await crud_transfers.get_transfers_by_location(
            db, location_id=location_id, as_origin=as_origin
        )
    # Default: show transfers for user's location
    return await crud_transfers.get_transfers_by_location(
        db, location_id=current_user.location_id, as_origin=as_origin
    )


@router.get(
    "/{transfer_id}",
    response_model=WorkerTransferResponse,
    tags=["Workers"],
    dependencies=[Depends(deps.PermissionChecker("workers:read"))],
)
async def get_transfer(
    transfer_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    transfer = await crud_transfers.get_transfer(db, transfer_id=transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    await _ensure_transfer_access(db, current_user, transfer)
    return transfer


@router.post(
    "/{transfer_id}/approve-origin",
    response_model=WorkerTransferResponse,
    tags=["Workers"],
    dependencies=[Depends(deps.PermissionChecker("workers:update"))],
)
async def approve_origin(
    transfer_id: UUID,
    payload: WorkerTransferApproveOrigin,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Origin pastor approves and releases the worker for transfer.
    Transfer status moves to 'approved_by_origin'.
    """
    transfer = await crud_transfers.get_transfer(db, transfer_id=transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    await _ensure_transfer_access(db, current_user, transfer)
    if current_user.location_id != transfer.from_location_id:
        raise HTTPException(status_code=403, detail="Only the origin location can approve this transfer")
    if transfer.status != "pending":
        raise HTTPException(status_code=400, detail=f"Transfer cannot be approved in status '{transfer.status}'")
    return await crud_transfers.approve_origin(
        db, transfer=transfer, approved_by_id=current_user.user_id, note=payload.note
    )


@router.post(
    "/{transfer_id}/approve-dest",
    response_model=WorkerTransferResponse,
    tags=["Workers"],
    dependencies=[Depends(deps.PermissionChecker("workers:update"))],
)
async def approve_destination(
    transfer_id: UUID,
    payload: WorkerTransferApproveDestination,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Destination pastor accepts the worker.
    Automatically updates the worker's location and marks transfer 'completed'.
    """
    transfer = await crud_transfers.get_transfer(db, transfer_id=transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    await _ensure_transfer_access(db, current_user, transfer)
    if current_user.location_id != transfer.to_location_id:
        raise HTTPException(status_code=403, detail="Only the destination location can approve this transfer")
    if transfer.status != "approved_by_origin":
        raise HTTPException(
            status_code=400,
            detail=f"Transfer must be approved by origin first. Current status: '{transfer.status}'"
        )
    return await crud_transfers.approve_destination(
        db, transfer=transfer, approved_by_id=current_user.user_id, note=payload.note
    )


@router.post(
    "/{transfer_id}/reject",
    response_model=WorkerTransferResponse,
    tags=["Workers"],
    dependencies=[Depends(deps.PermissionChecker("workers:update"))],
)
async def reject_transfer(
    transfer_id: UUID,
    payload: WorkerTransferReject,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Reject a transfer at any stage."""
    transfer = await crud_transfers.get_transfer(db, transfer_id=transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    await _ensure_transfer_access(db, current_user, transfer)
    if transfer.status in ("completed", "rejected"):
        raise HTTPException(status_code=400, detail=f"Cannot reject a transfer with status '{transfer.status}'")
    return await crud_transfers.reject_transfer(
        db,
        transfer=transfer,
        rejected_by_id=current_user.user_id,
        rejection_reason=payload.rejection_reason,
    )


@router.get(
    "/{transfer_id}/letter",
    tags=["Workers"],
    dependencies=[Depends(deps.PermissionChecker("workers:read"))],
)
async def download_transfer_letter(
    transfer_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Generate and download the official PDF transfer letter.
    Only available for completed transfers.
    """
    transfer = await crud_transfers.get_transfer(db, transfer_id=transfer_id)
    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found")
    await _ensure_transfer_access(db, current_user, transfer)
    if transfer.status != "completed":
        raise HTTPException(
            status_code=400,
            detail="Transfer letter is only available for completed transfers."
        )

    # Generate letter if not yet generated
    if not transfer.letter_generated:
        from app.services.transfer_letter import generate_transfer_letter
        letter_path = await generate_transfer_letter(db, transfer=transfer)
        transfer = await crud_transfers.mark_letter_generated(
            db, transfer=transfer, letter_url=letter_path
        )

    return FileResponse(
        path=transfer.letter_url,
        filename=f"transfer_letter_{transfer.reference_number}.pdf",
        media_type="application/pdf",
    )


# ─────────────────────────────────────────────
# Worker Absence Notices
# ─────────────────────────────────────────────

absence_router = APIRouter()


@absence_router.post(
    "",
    response_model=WorkerAbsenceNoticeResponse,
    status_code=201,
    tags=["Worker Attendance"],
    dependencies=[Depends(deps.PermissionChecker("attendance:create"))],
)
async def submit_absence_notice(
    *,
    db: AsyncSession = Depends(deps.get_db),
    notice_in: WorkerAbsenceNoticeCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Worker proactively reports an expected absence for a specific event.
    The pastor will see this when marking attendance.
    """
    # Get associated worker record
    worker_id = current_user.worker.worker_id if current_user.worker else None
    if not worker_id:
        raise HTTPException(status_code=400, detail="User has no associated worker record")
    return await crud_transfers.create_absence_notice(
        db, obj_in=notice_in, worker_id=worker_id
    )


@absence_router.get(
    "",
    response_model=List[WorkerAbsenceNoticeResponse],
    tags=["Worker Attendance"],
    dependencies=[Depends(deps.PermissionChecker("attendance:read"))],
)
async def list_absence_notices(
    *,
    db: AsyncSession = Depends(deps.get_db),
    event_id: Optional[UUID] = Query(None, description="Filter by event"),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List absence notices — filtered by event (for pastors marking attendance)."""
    if event_id:
        return await crud_transfers.get_absence_notices_for_event(db, event_id=event_id)
    worker_id = current_user.worker.worker_id if current_user.worker else None
    if not worker_id:
        return []
    return await crud_transfers.get_absence_notices_for_worker(db, worker_id=worker_id)


@absence_router.post(
    "/{notice_id}/acknowledge",
    response_model=WorkerAbsenceNoticeResponse,
    tags=["Worker Attendance"],
    dependencies=[Depends(deps.PermissionChecker("attendance:update"))],
)
async def acknowledge_absence_notice(
    notice_id: int,
    payload: WorkerAbsenceNoticeAcknowledge,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Pastor acknowledges or rejects a worker's absence notice."""
    notice = await crud_transfers.acknowledge_notice(
        db,
        notice_id=notice_id,
        admin_id=current_user.user_id,
        status=payload.status,
        admin_note=payload.admin_note,
    )
    if not notice:
        raise HTTPException(status_code=404, detail="Absence notice not found")
    return notice
