"""CRUD operations for Record (newcomer/convert) records."""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, UTC
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.crud.base import CRUDBase
from app.models.records import Record
from app.schemas.records import RecordCreate, RecordUpdate
from app.crud.idempotency import commit_idempotent, mark_existing_submission
from app.db.filters import scope_filter
from app.crud.workflow_rules import ensure_collection_open, load_event_campaign, require_approved_worker_user, require_event_assignment, resolve_program_context, resolve_program_level, widen_scope_for_approved_event_submission

class CRUDRecord(CRUDBase[Record, RecordCreate, RecordUpdate]):
    async def create(self, db: AsyncSession, *, obj_in: RecordCreate, user_id: UUID, require_assignment: bool = False) -> Record:
        if obj_in.client_id:
            existing = await self.get_by_client_id(db, client_id=obj_in.client_id)
            if existing: return mark_existing_submission(existing)
        from app.crud.crud_programs import program_event
        from app.crud.crud_location import location as crud_location
        event = await program_event.get(db, id=obj_in.event_id) if obj_in.event_id else None
        if obj_in.event_id and not event: raise HTTPException(status_code=404, detail="Event not found")
        program_domain_id, program_type_id = await resolve_program_context(db, event=event, program_domain=obj_in.program_domain, program_type=obj_in.program_type)
        program_level = resolve_program_level(event=event, program_level=obj_in.program_level)
        if not event and str(obj_in.program_domain or "").lower() == "crusade":
            raise HTTPException(status_code=400, detail="Crusade registrations must be linked to the scheduled event")
        if event:
            campaign = await load_event_campaign(db, event)
            ensure_collection_open(event, campaign, kind="person entry")
        location = await crud_location.get(db, obj_in.location_id)
        if not location: raise HTTPException(status_code=404, detail="Location not found")
        event_path = str(event.path) if event else None; location_path = str(location.path)
        if event_path and not (location_path == event_path or location_path.startswith(f"{event_path}.")):
            raise HTTPException(status_code=400, detail="Location must fall within the selected event scope")
        is_alpha = bool(event and event.alpha_location_id and str(event.alpha_location_id) == str(obj_in.location_id))
        source_role = "alpha" if is_alpha else ("satellite" if event and event.event_mode == "crusade" else "regular")
        campaign_code = event.campaign_code if event else None
        current_user = await require_approved_worker_user(db, user_id)
        assignment = await require_event_assignment(
            db,
            user=current_user,
            event=event,
            assignment_id=obj_in.assignment_id,
            location_id=obj_in.location_id,
            submission_kind="record",
            required=require_assignment or bool(event and event.event_mode == "crusade" and is_alpha),
        )
        if assignment:
            await widen_scope_for_approved_event_submission(db, event)
        db_obj = Record(event_id=obj_in.event_id, location_id=obj_in.location_id, assignment_id=obj_in.assignment_id, path=location_path, program_scope_path=str(event.path) if event else location_path, date=event.date if event else obj_in.date, church_type=obj_in.church_type, program_level=program_level, program_domain_id=program_domain_id, program_type_id=program_type_id, program_domain=obj_in.program_domain if not event else None, program_type=obj_in.program_type if not event else None, client_id=obj_in.client_id, record_type=obj_in.record_type, name=obj_in.name, gender=obj_in.gender, phone=obj_in.phone, details=obj_in.details, note=obj_in.note, entered_by_id=user_id, status="pending", source_role=source_role, campaign_code=campaign_code, submission_channel=obj_in.submission_channel)
        db.add(db_obj)
        if assignment:
            assignment.submission_completed = True; assignment.submitted_at = datetime.now(UTC); db.add(assignment)
        return await commit_idempotent(
            db, db_obj, client_id=obj_in.client_id,
            lookup=lambda session, client_id: self.get_by_client_id(session, client_id=client_id),
        )
    async def get_by_client_id(self, db: AsyncSession, *, client_id: UUID) -> Optional[Record]:
        result = await db.execute(select(Record).where(Record.client_id == client_id)); return result.scalars().first()
    async def get_multi_by_scope(self, db: AsyncSession, *, scope_path: str, skip: int = 0, limit: int = 100) -> List[Record]:
        result = await db.execute(select(Record).where(scope_filter(Record.path, scope_path), Record.is_deleted == False).offset(skip).limit(limit).order_by(Record.created_at.desc()))
        return result.scalars().all()
record = CRUDRecord(Record)
