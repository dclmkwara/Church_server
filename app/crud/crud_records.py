"""CRUD operations for Record (newcomer/convert) records."""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, UTC
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.crud.base import CRUDBase
from app.models.records import Record
from app.models.programs import EventAssignment
from app.models.user import User
from app.schemas.records import RecordCreate, RecordUpdate

class CRUDRecord(CRUDBase[Record, RecordCreate, RecordUpdate]):
    async def create(self, db: AsyncSession, *, obj_in: RecordCreate, user_id: UUID) -> Record:
        if obj_in.client_id:
            existing = await self.get_by_client_id(db, client_id=obj_in.client_id)
            if existing: return existing
        from app.crud.crud_programs import program_event
        from app.crud.crud_location import location as crud_location
        event = await program_event.get(db, id=obj_in.event_id)
        if not event: raise HTTPException(status_code=404, detail="Event not found")
        location = await crud_location.get(db, obj_in.location_id)
        if not location: raise HTTPException(status_code=404, detail="Location not found")
        event_path = str(event.path); location_path = str(location.path)
        if not (location_path == event_path or location_path.startswith(f"{event_path}.")):
            raise HTTPException(status_code=400, detail="Location must fall within the selected event scope")
        source_role = obj_in.source_role or ("alpha" if event.alpha_location_id and event.alpha_location_id == obj_in.location_id else ("satellite" if event.event_mode == "crusade" else "regular"))
        campaign_code = obj_in.campaign_code or event.campaign_code
        assignment = None
        if obj_in.assignment_id:
            assignment = await db.get(EventAssignment, obj_in.assignment_id)
            if not assignment: raise HTTPException(status_code=404, detail="Assignment not found")
            if assignment.event_id != obj_in.event_id: raise HTTPException(status_code=400, detail="Assignment does not belong to this event")
            if assignment.status != "approved": raise HTTPException(status_code=400, detail="Assignment is not approved")
            needed = 'convert' if obj_in.record_type == 'convert' else 'both'
            if obj_in.record_type == 'convert' and assignment.assignment_type not in {"convert", "both"}:
                raise HTTPException(status_code=400, detail="Assignment is not enabled for convert submission")
            current_user = await db.get(User, user_id)
            if not current_user or current_user.worker_id != assignment.worker_id: raise HTTPException(status_code=403, detail="Assignment belongs to a different worker")
        elif event.event_mode == "crusade" and source_role == "alpha" and obj_in.record_type == "convert":
            raise HTTPException(status_code=400, detail="Alpha crusade convert submissions require an approved assignment")
        db_obj = Record(event_id=obj_in.event_id, location_id=obj_in.location_id, assignment_id=obj_in.assignment_id, path=location_path, client_id=obj_in.client_id, record_type=obj_in.record_type, name=obj_in.name, gender=obj_in.gender, phone=obj_in.phone, details=obj_in.details, note=obj_in.note, entered_by_id=user_id, status="pending", source_role=source_role, campaign_code=campaign_code, submission_channel=obj_in.submission_channel)
        db.add(db_obj)
        if assignment:
            assignment.submission_completed = True; assignment.submitted_at = datetime.now(UTC); db.add(assignment)
        await db.commit(); await db.refresh(db_obj); return db_obj
    async def get_by_client_id(self, db: AsyncSession, *, client_id: UUID) -> Optional[Record]:
        result = await db.execute(select(Record).where(Record.client_id == client_id)); return result.scalars().first()
    async def get_multi_by_scope(self, db: AsyncSession, *, scope_path: str, skip: int = 0, limit: int = 100) -> List[Record]:
        result = await db.execute(select(Record).where(text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path), Record.is_deleted == False).offset(skip).limit(limit).order_by(Record.created_at.desc()))
        return result.scalars().all()
record = CRUDRecord(Record)
