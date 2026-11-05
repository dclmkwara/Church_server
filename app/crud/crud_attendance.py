"""
CRUD operations for Worker Attendance.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.models.attendance import WorkerAttendance
from app.schemas.attendance import WorkerAttendanceCreate, WorkerAttendanceUpdate
from app.crud.idempotency import commit_idempotent, mark_existing_submission
from app.db.filters import scope_filter
from app.crud.workflow_rules import ensure_collection_open, load_event_campaign, require_approved_worker_user, resolve_program_context, resolve_program_level


class CRUDWorkerAttendance(CRUDBase[WorkerAttendance, WorkerAttendanceCreate, WorkerAttendanceUpdate]):
    """CRUD operations for Worker Attendance model."""
    
    async def create(self, db: AsyncSession, *, obj_in: WorkerAttendanceCreate, user_id: UUID) -> WorkerAttendance:
        """Create attendance record with idempotency check."""
        # Check for duplicate client_id
        if obj_in.client_id:
            existing = await self.get_by_client_id(db, client_id=obj_in.client_id)
            if existing:
                return mark_existing_submission(existing)
        await require_approved_worker_user(db, user_id)
        
        # Verify event exists
        from app.crud.crud_programs import program_event
        event = await program_event.get(db, id=obj_in.event_id) if obj_in.event_id else None
        if obj_in.event_id and not event:
            raise HTTPException(status_code=404, detail="Event not found")
        program_domain_id, program_type_id = await resolve_program_context(db, event=event, program_domain=obj_in.program_domain, program_type=obj_in.program_type)
        program_level = resolve_program_level(event=event, program_level=obj_in.program_level)
        if event:
            campaign = await load_event_campaign(db, event)
            ensure_collection_open(event, campaign, kind="attendance")
        elif str(obj_in.program_domain or "").lower() == "crusade":
            raise HTTPException(status_code=400, detail="Crusade attendance must be linked to the scheduled event")
            
        # Verify worker exists and get details
        from app.models.user import Worker
        worker_result = await db.execute(
            select(Worker).where(
                Worker.worker_id == obj_in.worker_id,
                Worker.is_deleted == False,
                Worker.is_active == True,
                Worker.approval_status == "approved",
            )
        )
        worker = worker_result.scalars().first()
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

        from app.crud.crud_location import location as crud_location
        location = await crud_location.get(db, obj_in.location_id)
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")

        if worker.location_id != obj_in.location_id:
            raise HTTPException(
                status_code=400,
                detail="Attendance location must match the worker's assigned location",
            )

        event_path = str(event.path) if event else None
        location_path = str(location.path)
        if event_path and not (location_path == event_path or location_path.startswith(f"{event_path}.")):
            raise HTTPException(
                status_code=400,
                detail="Location must fall within the selected event scope",
            )
        
        db_obj = WorkerAttendance(
            event_id=obj_in.event_id,
            date=event.date if event else obj_in.date,
            church_type=obj_in.church_type,
            program_level=program_level,
            program_domain_id=program_domain_id,
            program_type_id=program_type_id,
            program_domain=obj_in.program_domain if not event else None,
            program_type=obj_in.program_type if not event else None,
            location_id=obj_in.location_id,
            path=location_path,
            program_scope_path=str(event.path) if event else location_path,
            client_id=obj_in.client_id,
            worker_id=obj_in.worker_id,
            worker_name=worker.name,
            worker_phone=worker.phone,
            worker_unit=worker.unit,
            status=obj_in.status,
            reason=obj_in.reason,
            note=obj_in.note,
            entered_by_id=user_id
        )
        
        db.add(db_obj)
        duplicate_query = select(WorkerAttendance.id).where(
            WorkerAttendance.worker_id == obj_in.worker_id,
            WorkerAttendance.location_id == obj_in.location_id,
            WorkerAttendance.is_deleted == False,
        )
        duplicate_query = duplicate_query.where(
            WorkerAttendance.event_id == obj_in.event_id if obj_in.event_id
            else (WorkerAttendance.event_id.is_(None) & (WorkerAttendance.date == obj_in.date))
        ).limit(1)
        duplicate = await db.execute(duplicate_query)
        if duplicate.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Worker already has an attendance record for this event")
        try:
            return await commit_idempotent(
                db, db_obj, client_id=obj_in.client_id,
                lookup=lambda session, client_id: self.get_by_client_id(session, client_id=client_id),
            )
        except IntegrityError as exc:
            await db.rollback()
            # The unique index is the concurrency-safe authority if two requests race.
            if "uq_worker_attendance_active_event_worker" in str(exc.orig) or "uq_worker_attendance_eventless_worker_day" in str(exc.orig):
                raise HTTPException(status_code=409, detail="Worker already has an attendance record for this event") from exc
            raise
    
    async def get_by_client_id(self, db: AsyncSession, *, client_id: UUID) -> Optional[WorkerAttendance]:
        """Get record by client_id."""
        query = select(WorkerAttendance).where(WorkerAttendance.client_id == client_id)
        result = await db.execute(query)
        return result.scalars().first()
    
    async def get_multi_by_scope(
        self, 
        db: AsyncSession, 
        *, 
        scope_path: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[WorkerAttendance]:
        """Get records within scope."""
        query = select(WorkerAttendance).where(
            scope_filter(WorkerAttendance.path, scope_path),
            WorkerAttendance.is_deleted == False,
        ).offset(skip).limit(limit).order_by(WorkerAttendance.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()


attendance = CRUDWorkerAttendance(WorkerAttendance)
