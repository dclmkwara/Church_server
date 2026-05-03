"""Official appointment routes."""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_official_appointment import official_appointment
from app.models.official_appointment import OfficialAppointment
from app.models.user import User, Worker
from app.schemas.official_appointment import (
    OfficialAppointmentCreate,
    OfficialAppointmentResponse,
    OfficialAppointmentRevoke,
    OfficialAppointmentUpdate,
)

router = APIRouter()


def _ensure_min_score(current_user: User, min_score: int, detail: str) -> None:
    if max((role.score_value for role in current_user.roles), default=0) < min_score:
        raise HTTPException(status_code=403, detail=detail)


async def _get_appointment_in_scope(db: AsyncSession, appointment_id: UUID, current_user: User) -> OfficialAppointment:
    appointment = await official_appointment.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Official appointment not found")
    deps.ensure_path_in_scope(current_user, appointment.path, detail="Official appointment outside your scope")
    return appointment


@router.get(
    "/",
    response_model=List[OfficialAppointmentResponse],
    dependencies=[Depends(deps.PermissionChecker("officials:read"))],
)
async def list_official_appointments(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str | None = Query(None),
    search: str | None = Query(None),
    status: str | None = Query(None),
    appointed_role: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    _ensure_min_score(current_user, 4, "Group-level access required for official appointments")
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    return await official_appointment.list_by_scope(
        db,
        scope_path=search_scope,
        search=search,
        status=status,
        appointed_role=appointed_role,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/",
    response_model=OfficialAppointmentResponse,
    dependencies=[Depends(deps.PermissionChecker("officials:manage"))],
)
async def create_official_appointment(
    appointment_in: OfficialAppointmentCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    _ensure_min_score(current_user, 4, "Group-level access required for official appointments")
    assigned_scope_path = deps.resolve_scope_path(current_user, appointment_in.assigned_scope_path)
    worker = await db.execute(select(Worker).where(Worker.worker_id == appointment_in.worker_id, Worker.is_deleted == False))
    worker = worker.scalars().first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    deps.ensure_path_in_scope(current_user, worker.path, detail="Worker outside your scope")
    if not deps.path_in_scope(assigned_scope_path, worker.path):
        raise HTTPException(status_code=400, detail="Worker must belong to the assigned scope or one of its child locations")
    payload = appointment_in.model_copy(update={"assigned_scope_path": assigned_scope_path})
    return await official_appointment.create_for_user(db, obj_in=payload, worker=worker, current_user=current_user)


@router.get(
    "/{appointment_id}",
    response_model=OfficialAppointmentResponse,
    dependencies=[Depends(deps.PermissionChecker("officials:read"))],
)
async def get_official_appointment(
    appointment_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    _ensure_min_score(current_user, 4, "Group-level access required for official appointments")
    return await _get_appointment_in_scope(db, appointment_id, current_user)


@router.put(
    "/{appointment_id}",
    response_model=OfficialAppointmentResponse,
    dependencies=[Depends(deps.PermissionChecker("officials:manage"))],
)
async def update_official_appointment(
    appointment_id: UUID,
    appointment_in: OfficialAppointmentUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    _ensure_min_score(current_user, 4, "Group-level access required for official appointments")
    appointment = await _get_appointment_in_scope(db, appointment_id, current_user)
    payload = appointment_in.model_dump(exclude_unset=True)
    assigned_scope_path = payload.get("assigned_scope_path")
    if assigned_scope_path:
        payload["assigned_scope_path"] = deps.resolve_scope_path(current_user, assigned_scope_path)
    updated = OfficialAppointmentUpdate(**payload)
    return await official_appointment.update_for_user(db, db_obj=appointment, obj_in=updated)


@router.post(
    "/{appointment_id}/revoke",
    response_model=OfficialAppointmentResponse,
    dependencies=[Depends(deps.PermissionChecker("officials:manage"))],
)
async def revoke_official_appointment(
    appointment_id: UUID,
    revoke_in: OfficialAppointmentRevoke,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    _ensure_min_score(current_user, 4, "Group-level access required for official appointments")
    appointment = await _get_appointment_in_scope(db, appointment_id, current_user)
    return await official_appointment.revoke(db, db_obj=appointment, current_user=current_user, note=revoke_in.note)
