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

router = APIRouter()


@router.post("/transfers", response_model=TransferRequestResponse, status_code=201)
async def create_transfer_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    payload: TransferRequestCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return await approvals.create_transfer(
        db,
        worker_id=payload.worker_id,
        to_location_id=payload.to_location_id,
        requested_by=current_user.user_id,
        reason=payload.reason,
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
    scope_path = str(current_user.path)
    return await approvals.list_transfers(db, scope_path=scope_path, status=status, skip=skip, limit=limit)


@router.post("/transfers/{request_id}/approve", response_model=TransferRequestResponse)
async def approve_transfer_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    scope_path = str(current_user.path)
    return await approvals.approve_transfer(
        db, request_id=request_id, approver_id=current_user.user_id, scope_path=scope_path
    )


@router.post("/transfers/{request_id}/reject", response_model=TransferRequestResponse)
async def reject_transfer_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request_id: UUID,
    reason: Optional[str] = None,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    scope_path = str(current_user.path)
    return await approvals.reject_transfer(
        db, request_id=request_id, approver_id=current_user.user_id, reason=reason, scope_path=scope_path
    )


@router.post("/status-changes", response_model=StatusChangeRequestResponse, status_code=201)
async def create_status_change_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    payload: StatusChangeRequestCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return await approvals.create_status_change(
        db,
        worker_id=payload.worker_id,
        new_status=payload.new_status,
        requested_by=current_user.user_id,
        reason=payload.reason,
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
    scope_path = str(current_user.path)
    return await approvals.list_status_changes(db, scope_path=scope_path, status=status, skip=skip, limit=limit)


@router.post("/status-changes/{request_id}/approve", response_model=StatusChangeRequestResponse)
async def approve_status_change_request(
    *,
    db: AsyncSession = Depends(deps.get_db),
    request_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    scope_path = str(current_user.path)
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
    scope_path = str(current_user.path)
    return await approvals.reject_status_change(
        db, request_id=request_id, approver_id=current_user.user_id, reason=reason, scope_path=scope_path
    )
