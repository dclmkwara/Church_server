"""CRUD operations for Count records."""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, UTC
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.crud.base import CRUDBase
from app.models.counts import Count
from app.models.programs import EventAssignment
from app.schemas.counts import CountCreate, CountUpdate
from app.crud.idempotency import commit_idempotent, mark_existing_submission
from app.db.filters import scope_filter
from app.crud.workflow_rules import ensure_collection_open, load_event_campaign, require_approved_worker_user

class CRUDCount(CRUDBase[Count, CountCreate, CountUpdate]):
    async def create(self, db: AsyncSession, *, obj_in: CountCreate, user_id: UUID) -> Count:
        if obj_in.client_id:
            existing = await self.get_by_client_id(db, client_id=obj_in.client_id)
            if existing:
                return mark_existing_submission(existing)
        from app.crud.crud_programs import program_event
        from app.crud.crud_location import location as crud_location
        event = await program_event.get(db, id=obj_in.event_id) if obj_in.event_id else None
        if obj_in.event_id and not event: raise HTTPException(status_code=404, detail="Event not found")
        if not event and str(obj_in.program_domain or "").lower() == "crusade":
            raise HTTPException(status_code=400, detail="Crusade counts must be linked to the scheduled event")
        if event:
            campaign = await load_event_campaign(db, event)
            ensure_collection_open(event, campaign, kind="count")
        location = await crud_location.get(db, obj_in.location_id)
        if not location: raise HTTPException(status_code=404, detail="Location not found")
        event_path = str(event.path) if event else None; location_path = str(location.path)
        if event_path and not (location_path == event_path or location_path.startswith(f"{event_path}.")):
            raise HTTPException(status_code=400, detail="Location must fall within the selected event scope")
        # Source classification and campaign identity come from the event/location,
        # never from a submitting client. Separate usher rows remain independent.
        is_alpha = bool(event and event.alpha_location_id and str(event.alpha_location_id) == str(obj_in.location_id))
        source_role = "alpha" if is_alpha else ("satellite" if event and event.event_mode == "crusade" else "regular")
        campaign_code = event.campaign_code if event else None
        assignment = None
        current_user = await require_approved_worker_user(db, user_id)
        if obj_in.assignment_id:
            assignment = await db.get(EventAssignment, obj_in.assignment_id)
            if not assignment: raise HTTPException(status_code=404, detail="Assignment not found")
            if assignment.event_id != obj_in.event_id: raise HTTPException(status_code=400, detail="Assignment does not belong to this event")
            if assignment.status != "approved": raise HTTPException(status_code=400, detail="Assignment is not approved")
            if assignment.assignment_type not in {"count", "both"}: raise HTTPException(status_code=400, detail="Assignment is not enabled for count submission")
            if not current_user or current_user.worker_id != assignment.worker_id: raise HTTPException(status_code=403, detail="Assignment belongs to a different worker")
        elif event and event.event_mode == "crusade" and is_alpha:
            raise HTTPException(status_code=400, detail="Alpha crusade submissions require an approved assignment")
        if obj_in.assignment_id and not event:
            raise HTTPException(status_code=400, detail="Assigned count submissions require a scheduled event")
        db_obj = Count(event_id=obj_in.event_id, location_id=obj_in.location_id, assignment_id=obj_in.assignment_id, path=location_path, date=event.date if event else obj_in.date, church_type=obj_in.church_type, program_domain=obj_in.program_domain if not event else None, program_type=obj_in.program_type if not event else None, client_id=obj_in.client_id, adult_male=obj_in.adult_male, adult_female=obj_in.adult_female, youth_male=obj_in.youth_male, youth_female=obj_in.youth_female, boys=obj_in.boys, girls=obj_in.girls, note=obj_in.note, entered_by_id=user_id, status="pending", source_role=source_role, campaign_code=campaign_code, submission_channel=obj_in.submission_channel)
        db_obj.calculate_total(); db.add(db_obj)
        if assignment:
            assignment.submission_completed = True; assignment.submitted_at = datetime.now(UTC); db.add(assignment)
        return await commit_idempotent(
            db, db_obj, client_id=obj_in.client_id,
            lookup=lambda session, client_id: self.get_by_client_id(session, client_id=client_id),
        )
    async def get_by_client_id(self, db: AsyncSession, *, client_id: UUID) -> Optional[Count]:
        result = await db.execute(select(Count).where(Count.client_id == client_id)); return result.scalars().first()
    async def update(self, db: AsyncSession, *, db_obj: Count, obj_in: CountUpdate | dict) -> Count:
        payload = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        allowed = {"adult_male", "adult_female", "youth_male", "youth_female", "boys", "girls", "note"}
        for field, value in payload.items():
            if field in allowed:
                setattr(db_obj, field, value)
        db_obj.calculate_total()
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    async def get_multi_by_scope(self, db: AsyncSession, *, scope_path: str, skip: int = 0, limit: int = 100) -> List[Count]:
        result = await db.execute(select(Count).where(scope_filter(Count.path, scope_path), Count.is_deleted == False).offset(skip).limit(limit).order_by(Count.created_at.desc()))
        return result.scalars().all()
count = CRUDCount(Count)
