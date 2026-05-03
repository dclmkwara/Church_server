"""CRUD operations for official appointments."""
from datetime import datetime, UTC
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.official_appointment import OfficialAppointment
from app.models.user import User, Worker
from app.schemas.official_appointment import OfficialAppointmentCreate, OfficialAppointmentUpdate

VALID_STATUSES = {"active", "revoked"}


class CRUDOfficialAppointment(CRUDBase[OfficialAppointment, OfficialAppointmentCreate, OfficialAppointmentUpdate]):
    @staticmethod
    def _validate_status(status: Optional[str]) -> None:
        if status and status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid appointment status")

    async def list_by_scope(
        self,
        db: AsyncSession,
        *,
        scope_path: str,
        search: str | None = None,
        status: str | None = None,
        appointed_role: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[OfficialAppointment]:
        self._validate_status(status)
        query = select(OfficialAppointment).where(
            text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path),
            OfficialAppointment.is_deleted == False,
        )
        if status:
            query = query.where(OfficialAppointment.status == status)
        if appointed_role:
            query = query.where(OfficialAppointment.appointed_role == appointed_role)
        if search:
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    OfficialAppointment.worker_name.ilike(term),
                    OfficialAppointment.appointed_role.ilike(term),
                    OfficialAppointment.assigned_scope_label.ilike(term),
                    OfficialAppointment.appointed_by_name.ilike(term),
                    OfficialAppointment.location_name.ilike(term),
                )
            )
        result = await db.execute(query.order_by(OfficialAppointment.appointment_date.desc(), OfficialAppointment.created_at.desc()).offset(skip).limit(limit))
        return result.scalars().all()

    async def create_for_user(
        self,
        db: AsyncSession,
        *,
        obj_in: OfficialAppointmentCreate,
        worker: Worker,
        current_user: User,
    ) -> OfficialAppointment:
        self._validate_status(obj_in.status)
        existing = await db.execute(
            select(OfficialAppointment).where(
                OfficialAppointment.worker_id == obj_in.worker_id,
                OfficialAppointment.appointed_role == obj_in.appointed_role,
                OfficialAppointment.path == obj_in.assigned_scope_path,
                OfficialAppointment.is_deleted == False,
            )
        )
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="An appointment already exists for this worker, role, and scope")
        db_obj = OfficialAppointment(
            worker_id=obj_in.worker_id,
            worker_name=worker.name,
            location_id=worker.location_id,
            location_name=worker.location_name,
            appointed_role=obj_in.appointed_role,
            assigned_scope_label=obj_in.assigned_scope_label,
            appointment_date=obj_in.appointment_date,
            status=obj_in.status,
            note=obj_in.note,
            appointed_by_id=current_user.user_id,
            appointed_by_name=current_user.name,
            path=obj_in.assigned_scope_path,
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update_for_user(
        self,
        db: AsyncSession,
        *,
        db_obj: OfficialAppointment,
        obj_in: OfficialAppointmentUpdate,
    ) -> OfficialAppointment:
        payload = obj_in.model_dump(exclude_unset=True)
        self._validate_status(payload.get("status"))
        if "assigned_scope_path" in payload:
            payload["path"] = payload.pop("assigned_scope_path")
        if payload.get("status") == "revoked" and db_obj.status != "revoked":
            payload.setdefault("revoked_at", datetime.now(UTC))
        return await super().update(db, db_obj=db_obj, obj_in=payload)

    async def revoke(
        self,
        db: AsyncSession,
        *,
        db_obj: OfficialAppointment,
        current_user: User,
        note: str | None = None,
    ) -> OfficialAppointment:
        db_obj.status = "revoked"
        db_obj.revoked_at = datetime.now(UTC)
        db_obj.revoked_by_id = current_user.user_id
        if note:
            db_obj.revoked_note = note
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


official_appointment = CRUDOfficialAppointment(OfficialAppointment)
