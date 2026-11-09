"""
Approval workflow routes for transfers and status changes.
"""
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_approvals import approvals
from app.schemas.approvals import (
    TransferRequestCreate,
    TransferRequestResponse,
    StatusChangeRequestCreate,
    StatusChangeRequestResponse,
)
from app.models.user import User
from fastapi import HTTPException

router = APIRouter()


def _require_worker_change_requester(current_user: User) -> None:
    if deps.highest_role_score(current_user) < 2 or not deps.has_permission(current_user, "workers:request_changes"):
        raise HTTPException(status_code=403, detail="Worker-change request permission is required")


@router.post("/transfers", response_model=TransferRequestResponse, status_code=201)
async def create_transfer_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    payload: TransferRequestCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    _require_worker_change_requester(current_user)
    from app.models.user import Worker
    worker = await db.get(Worker, payload.worker_id)
    if not worker or worker.is_deleted:
        raise HTTPException(status_code=404, detail="Worker not found")
    await deps.get_location_in_scope(
        db, current_user=current_user, location_id=worker.location_id,
        detail="Worker is outside your assigned scope",
    )
    return await approvals.create_transfer(
        db,
        worker_id=payload.worker_id,
        to_location_id=payload.to_location_id,
        requested_by=current_user.user_id,
        reason=payload.reason,
        scope_path=deps.effective_scope_path(current_user),
    )


@router.get("/transfers", response_model=List[TransferRequestResponse])
async def list_transfer_requests(
    *,
    db: AsyncSession = Depends(deps.get_db),
    status: Optional[str] = Query(None, description="pending, approved, rejected"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if deps.highest_role_score(current_user) < 2 or not deps.has_permission(current_user, "workers:approve"):
        raise HTTPException(status_code=403, detail="A church leadership role is required to review transfers")
    scope_path = deps.effective_scope_path(current_user)
    return await approvals.list_transfers(db, scope_path=scope_path, status=status, skip=skip, limit=limit)


@router.post("/transfers/{request_id}/approve", response_model=TransferRequestResponse)
async def approve_transfer_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if deps.highest_role_score(current_user) < 2 or not deps.has_permission(current_user, "workers:approve"):
        raise HTTPException(status_code=403, detail="A church leadership role is required to review transfers")
    scope_path = deps.effective_scope_path(current_user)
    return await approvals.approve_transfer(
        db, request_id=request_id, approver_id=current_user.user_id,
        approver_score=deps.highest_role_score(current_user), approver_path=current_user.path, scope_path=scope_path
    )


@router.post("/transfers/{request_id}/reject", response_model=TransferRequestResponse)
async def reject_transfer_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request_id: UUID,
    reason: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if deps.highest_role_score(current_user) < 2 or not deps.has_permission(current_user, "workers:approve"):
        raise HTTPException(status_code=403, detail="A pastor with worker-approval authority is required to reject transfers")
    scope_path = deps.effective_scope_path(current_user)
    return await approvals.reject_transfer(
        db, request_id=request_id, approver_id=current_user.user_id,
        approver_score=deps.highest_role_score(current_user), approver_path=current_user.path,
        reason=reason, scope_path=scope_path
    )


@router.post("/status-changes", response_model=StatusChangeRequestResponse, status_code=201)
async def create_status_change_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    payload: StatusChangeRequestCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    _require_worker_change_requester(current_user)
    from app.models.user import Worker
    worker = await db.get(Worker, payload.worker_id)
    if not worker or worker.is_deleted:
        raise HTTPException(status_code=404, detail="Worker not found")
    await deps.get_location_in_scope(
        db, current_user=current_user, location_id=worker.location_id,
        detail="Worker is outside your assigned scope",
    )
    return await approvals.create_status_change(
        db,
        worker_id=payload.worker_id,
        new_status=payload.new_status,
        requested_by=current_user.user_id,
        reason=payload.reason,
        scope_path=deps.effective_scope_path(current_user),
    )


@router.get("/status-changes", response_model=List[StatusChangeRequestResponse])
async def list_status_change_requests(
    *,
    db: AsyncSession = Depends(deps.get_db),
    status: Optional[str] = Query(None, description="pending, approved, rejected"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if deps.highest_role_score(current_user) < 3 or not deps.has_permission(current_user, "workers:approve"):
        raise HTTPException(status_code=403, detail="Group Pastor approval or higher is required for status changes")
    scope_path = deps.effective_scope_path(current_user)
    return await approvals.list_status_changes(db, scope_path=scope_path, status=status, skip=skip, limit=limit)


@router.post("/status-changes/{request_id}/approve", response_model=StatusChangeRequestResponse)
async def approve_status_change_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if deps.highest_role_score(current_user) < 3 or not deps.has_permission(current_user, "workers:approve"):
        raise HTTPException(status_code=403, detail="Group Pastor approval or higher is required for status changes")
    scope_path = deps.effective_scope_path(current_user)
    return await approvals.approve_status_change(
        db, request_id=request_id, approver_id=current_user.user_id, scope_path=scope_path
    )


@router.post("/status-changes/{request_id}/reject", response_model=StatusChangeRequestResponse)
async def reject_status_change_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request_id: UUID,
    reason: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    if deps.highest_role_score(current_user) < 3 or not deps.has_permission(current_user, "workers:approve"):
        raise HTTPException(status_code=403, detail="Group Pastor approval or higher is required for status changes")
    scope_path = deps.effective_scope_path(current_user)
    return await approvals.reject_status_change(
        db, request_id=request_id, approver_id=current_user.user_id, reason=reason, scope_path=scope_path
    )


# ──────────────────────────────────────────────────────────────
# Worker Removal Requests (Escalation Workflow)
# ──────────────────────────────────────────────────────────────

from app.crud.crud_approvals import removal
from app.schemas.approvals import (
    RemovalRequestCreate,
    RemovalRequestResponse,
    RemovalActionPayload,
)
from fastapi import HTTPException


@router.post("/removals", response_model=RemovalRequestResponse, status_code=201)
async def create_removal_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    payload: RemovalRequestCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit a worker removal request (starts at Group Pastor / score 3)."""
    _require_worker_change_requester(current_user)
    if len(payload.reason.strip()) < 20:
        raise HTTPException(status_code=400, detail="Reason must be at least 20 characters")

    from app.models.user import Worker
    worker = await db.get(Worker, payload.worker_id)
    if not worker or worker.is_deleted:
        raise HTTPException(status_code=404, detail="Worker not found")
    await deps.get_location_in_scope(
        db, current_user=current_user, location_id=worker.location_id,
        detail="Worker is outside your assigned scope",
    )
    return await removal.submit(
        db,
        worker_id=payload.worker_id,
        reason=payload.reason,
        requested_by=current_user.user_id,
        scope_path=deps.effective_scope_path(current_user),
    )


@router.get("/removals", response_model=List[RemovalRequestResponse])
async def list_removal_requests(
    *,
    db: AsyncSession = Depends(deps.get_db),
    status: Optional[str] = Query(None, description="pending, approved, rejected, escalated"),
    current_level: Optional[int] = Query(None, description="Filter by reviewing score (3=group, 4=region, 5=state)"),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List removal requests in the current user's scope."""
    if deps.highest_role_score(current_user) < 3 or not deps.has_permission(current_user, "workers:approve"):
        raise HTTPException(status_code=403, detail="Group Pastor or higher authority is required to review removal requests")
    scope_path = deps.effective_scope_path(current_user)
    return await removal.list_requests(
        db,
        scope_path=scope_path,
        status=status,
        current_level=current_level,
        skip=skip,
        limit=limit,
    )


@router.post("/removals/{request_id}/approve", response_model=RemovalRequestResponse)
async def approve_removal_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request_id: UUID,
    payload: RemovalActionPayload,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Approve request and soft-delete the worker."""
    if deps.highest_role_score(current_user) < 3 or not deps.has_permission(current_user, "workers:approve"):
        raise HTTPException(status_code=403, detail="Group Pastor or higher authority is required to approve removal requests")
    scope_path = deps.effective_scope_path(current_user)

    from app.models.user import Role, RoleScore
    from sqlalchemy import select
    res = await db.execute(
        select(RoleScore.score)
        .join(Role, Role.score_id == RoleScore.id)
        .join(Role.users)
        .where(User.user_id == current_user.user_id)
        .order_by(RoleScore.score.desc())
        .limit(1)
    )
    db_score = res.scalar() or 1

    return await removal.approve(
        db,
        request_id=request_id,
        approver_id=current_user.user_id,
        approver_score=db_score,
        scope_path=scope_path,
        notes=payload.notes,
    )


@router.post("/removals/{request_id}/reject", response_model=RemovalRequestResponse)
async def reject_removal_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request_id: UUID,
    payload: RemovalActionPayload,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Reject the removal request."""
    scope_path = deps.effective_scope_path(current_user)

    from app.models.user import Role, RoleScore
    from sqlalchemy import select
    res = await db.execute(
        select(RoleScore.score)
        .join(Role, Role.score_id == RoleScore.id)
        .join(Role.users)
        .where(User.user_id == current_user.user_id)
        .order_by(RoleScore.score.desc())
        .limit(1)
    )
    db_score = res.scalar() or 1

    return await removal.reject(
        db,
        request_id=request_id,
        approver_id=current_user.user_id,
        approver_score=db_score,
        scope_path=scope_path,
        notes=payload.notes,
    )


@router.post("/removals/{request_id}/escalate", response_model=RemovalRequestResponse)
async def escalate_removal_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request_id: UUID,
    payload: RemovalActionPayload,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Escalate the request to the next level."""
    if not payload.notes or len(payload.notes.strip()) < 10:
        raise HTTPException(status_code=400, detail="Escalation notes are required (min 10 chars)")

    scope_path = deps.effective_scope_path(current_user)

    from app.models.user import Role, RoleScore
    from sqlalchemy import select
    res = await db.execute(
        select(RoleScore.score)
        .join(Role, Role.score_id == RoleScore.id)
        .join(Role.users)
        .where(User.user_id == current_user.user_id)
        .order_by(RoleScore.score.desc())
        .limit(1)
    )
    db_score = res.scalar() or 1

    return await removal.escalate(
        db,
        request_id=request_id,
        escalator_id=current_user.user_id,
        escalator_score=db_score,
        scope_path=scope_path,
        notes=payload.notes,
    )
