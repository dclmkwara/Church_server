"""CRUD operations for Count records."""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, UTC
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.crud.base import CRUDBase
from app.models.counts import Count, CountGroup
from app.schemas.counts import CountCreate, CountUpdate
from app.crud.idempotency import commit_idempotent, mark_existing_submission
from app.db.filters import scope_filter
from app.crud.workflow_rules import ensure_collection_open, load_event_campaign, require_approved_worker_user, require_event_assignment, resolve_program_context, resolve_program_level, widen_scope_for_approved_event_submission
from app.utils.count_groups import require_count_mode, require_section_label_available


def _calendar_date(value):
    return value.date() if hasattr(value, "date") else value

class CRUDCount(CRUDBase[Count, CountCreate, CountUpdate]):
    async def create(self, db: AsyncSession, *, obj_in: CountCreate, user_id: UUID, require_assignment: bool = False) -> Count:
        if obj_in.client_id:
            existing = await self.get_by_client_id(db, client_id=obj_in.client_id)
            if existing:
                return mark_existing_submission(existing)
        from app.crud.crud_programs import program_event
        from app.crud.crud_location import location as crud_location
        event = await program_event.get(db, id=obj_in.event_id) if obj_in.event_id else None
        if obj_in.event_id and not event: raise HTTPException(status_code=404, detail="Event not found")
        program_domain_id, program_type_id = await resolve_program_context(db, event=event, program_domain=obj_in.program_domain, program_type=obj_in.program_type)
        program_level = resolve_program_level(event=event, program_level=obj_in.program_level)
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
        current_user = await require_approved_worker_user(db, user_id)
        assignment = await require_event_assignment(
            db,
            user=current_user,
            event=event,
            assignment_id=obj_in.assignment_id,
            location_id=obj_in.location_id,
            submission_kind="count",
            required=require_assignment or bool(event and event.event_mode == "crusade" and is_alpha),
        )
        if assignment:
            await widen_scope_for_approved_event_submission(db, event)
        scope_segments = {"Local": 6, "Group": 5, "Region": 4, "State": 3}
        segment_count = scope_segments.get(program_level, len(location_path.split(".")))
        report_scope_path = str(event.path) if event else ".".join(location_path.split(".")[:segment_count])
        submitted_date = event.date if event else obj_in.date
        superseded = None
        if obj_in.supersedes_id:
            superseded = await db.get(Count, obj_in.supersedes_id)
            if not superseded or superseded.is_deleted or str(superseded.status).lower() != "rejected":
                raise HTTPException(status_code=422, detail="A correction must reference a rejected count")
            if (
                str(superseded.location_id) != str(obj_in.location_id)
                or _calendar_date(superseded.date) != _calendar_date(submitted_date)
                or str(superseded.event_id or "") != str(obj_in.event_id or "")
                or superseded.program_domain_id != program_domain_id
                or superseded.program_type_id != program_type_id
                or str(superseded.program_level or "").lower() != str(program_level).lower()
                or str(superseded.program_scope_path or "") != report_scope_path
            ):
                raise HTTPException(status_code=422, detail="A correction must retain the rejected report's program, date, location, and reporting scope")
        auto_accepted = str(program_level).lower() == "state"
        accepted_at = datetime.now(UTC) if auto_accepted else None
        requested_mode = obj_in.count_mode or "single"
        program_key = str(program_type_id or (obj_in.program_type or "").strip().lower().replace(" ", "_"))
        service_id = str(obj_in.service_id or "").strip() or "main"
        event_key = str(event.id) if event else "none"
        group_key = f"{obj_in.location_id}:{program_key}:{_calendar_date(submitted_date).isoformat()}:{event_key}:{service_id}"
        # Serialize competing offline submissions for the same occurrence so
        # the first mode and section-label uniqueness are enforced atomically.
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:group_key))").bindparams(group_key=group_key))
        group = (await db.execute(select(CountGroup).where(CountGroup.group_key == group_key))).scalar_one_or_none()
        if group is None:
            group = CountGroup(
                group_key=group_key, location_id=obj_in.location_id,
                program_type_key=program_key, occurrence_date=_calendar_date(submitted_date),
                reporting_scope_path=report_scope_path, service_id=service_id,
                lead_usher_id=user_id,
                count_mode=requested_mode, state="open",
            )
            db.add(group)
            await db.flush()
        elif group.finalized_at or group.auto_closed_at:
            raise HTTPException(status_code=409, detail="This count group is finalized and no longer accepts submissions")
        if requested_mode:
            prior_rows = list((await db.execute(select(Count).where(
                Count.count_group_id == group.id, Count.is_deleted.is_(False),
                Count.status.in_(["pending", "approved"]),
            ))).scalars().all())
            prior_modes = {str(row.count_mode).lower() for row in prior_rows if row.count_mode}
            established_mode = group.count_mode or next(iter(prior_modes), None)
            require_count_mode(established_mode, requested_mode)
            group.count_mode = requested_mode
            duplicate_single = requested_mode == "single" and any(row.count_mode == "single" for row in prior_rows)
            if requested_mode == "section":
                require_section_label_available([row.section_label for row in prior_rows if row.count_mode == "section"], obj_in.section_label or "")
            if duplicate_single:
                group.state = "conflict"
            elif requested_mode == "single":
                group.state = "complete"
            elif group.state != "conflict":
                group.state = "open"
        section_label = (obj_in.section_label or "").strip() or None if requested_mode == "section" else None
        db_obj = Count(event_id=obj_in.event_id, location_id=obj_in.location_id, assignment_id=obj_in.assignment_id, count_group_id=group.id, count_mode=requested_mode, section_label=section_label, path=location_path, program_scope_path=report_scope_path, date=submitted_date, church_type=obj_in.church_type, program_level=program_level, program_domain_id=program_domain_id, program_type_id=program_type_id, program_domain=obj_in.program_domain if not event else None, program_type=obj_in.program_type if not event else None, client_id=obj_in.client_id, supersedes_id=obj_in.supersedes_id, adult_male=obj_in.adult_male, adult_female=obj_in.adult_female, youth_male=obj_in.youth_male, youth_female=obj_in.youth_female, boys=obj_in.boys, girls=obj_in.girls, note=obj_in.note, entered_by_id=user_id, status="approved" if auto_accepted else "pending", approved_at=accepted_at, auto_accepted=auto_accepted, source_role=source_role, campaign_code=campaign_code, submission_channel=obj_in.submission_channel)
        db_obj.calculate_total()
        if obj_in.total is not None:
            db_obj.total = obj_in.total
        db.add(db_obj)
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
