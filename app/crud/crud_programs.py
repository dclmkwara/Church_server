"""CRUD operations for Programs and Events."""
from typing import List, Optional, Any
from uuid import UUID
from datetime import datetime, UTC
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.crud.base import CRUDBase
from app.models.programs import ProgramDomain, ProgramType, ProgramCampaign, ProgramEvent, EventAssignment
from app.models.user import Worker
from app.schemas.programs import ProgramDomainCreate, ProgramDomainUpdate, ProgramTypeCreate, ProgramTypeUpdate, ProgramCampaignCreate, ProgramCampaignUpdate, ProgramEventCreate, ProgramEventUpdate, EventAssignmentCreate, EventAssignmentUpdate
from app.db.filters import scope_filter, scope_or_ancestor_filter
from app.crud.workflow_rules import validate_campaign_transition

EVENT_MODES = {"regular", "retreat", "crusade", "special"}
REPORTING_SCOPES = {"location", "group", "region", "state", "nation", "continent", "global"}
CAMPAIGN_STATUSES = {"draft", "active", "closed", "archived"}
ASSIGNMENT_TYPES = {"count", "convert", "attendance", "both", "all"}
SOURCE_ROLES = {"alpha", "satellite", "regular"}
ASSIGNMENT_STATUSES = {"pending", "approved", "rejected"}


async def get_worker_by_public_id(db: AsyncSession, worker_id: UUID) -> Optional[Worker]:
    """Resolve the worker UUID exposed by clients, not the integer ORM PK."""
    result = await db.execute(select(Worker).where(Worker.worker_id == worker_id))
    return result.scalars().first()
AUDIENCE_SEGMENTS = {"adult", "campus", "youth", "children"}

class CRUDProgramDomain(CRUDBase[ProgramDomain, ProgramDomainCreate, ProgramDomainUpdate]):
    async def create(self, db: AsyncSession, *, obj_in: ProgramDomainCreate) -> ProgramDomain:
        if await self.get_by_slug(db, slug=obj_in.slug):
            raise HTTPException(status_code=400, detail="Program Domain slug already exists")
        return await super().create(db, obj_in=obj_in)
    async def get_by_slug(self, db: AsyncSession, *, slug: str) -> Optional[ProgramDomain]:
        result = await db.execute(select(ProgramDomain).where(ProgramDomain.slug == slug))
        return result.scalars().first()
program_domain = CRUDProgramDomain(ProgramDomain)

class CRUDProgramType(CRUDBase[ProgramType, ProgramTypeCreate, ProgramTypeUpdate]):
    async def create(self, db: AsyncSession, *, obj_in: ProgramTypeCreate) -> ProgramType:
        domain = await program_domain.get(db, id=obj_in.domain_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Program Domain not found")
        if await self.get_by_slug(db, slug=obj_in.slug):
            raise HTTPException(status_code=400, detail="Program Type slug already exists")
        return await super().create(db, obj_in=obj_in)
    async def get_by_slug(self, db: AsyncSession, *, slug: str) -> Optional[ProgramType]:
        result = await db.execute(select(ProgramType).where(ProgramType.slug == slug))
        return result.scalars().first()
    async def get_by_domain(self, db: AsyncSession, *, domain_id: int, skip: int = 0, limit: int = 100) -> List[ProgramType]:
        result = await db.execute(select(ProgramType).where(ProgramType.domain_id == domain_id).offset(skip).limit(limit))
        return result.scalars().all()
program_type = CRUDProgramType(ProgramType)

class CRUDProgramCampaign(CRUDBase[ProgramCampaign, ProgramCampaignCreate, ProgramCampaignUpdate]):
    @staticmethod
    def _validate(*, event_mode: Optional[str], reporting_scope: Optional[str], status: Optional[str]) -> None:
        if event_mode is not None and event_mode not in EVENT_MODES:
            raise HTTPException(status_code=400, detail="Invalid event_mode")
        if reporting_scope is not None and reporting_scope not in REPORTING_SCOPES:
            raise HTTPException(status_code=400, detail="Invalid reporting_scope")
        if status is not None and status not in CAMPAIGN_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid campaign status")
    async def create_for_user(self, db: AsyncSession, *, obj_in: ProgramCampaignCreate, user_id: UUID) -> ProgramCampaign:
        domain = await program_domain.get(db, id=obj_in.domain_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Program Domain not found")
        existing = await db.execute(select(ProgramCampaign).where(ProgramCampaign.campaign_code == obj_in.campaign_code))
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="Campaign code already exists")
        self._validate(event_mode=obj_in.event_mode, reporting_scope=obj_in.reporting_scope, status=obj_in.status)
        self._validate_dates(
            start_date=obj_in.start_date, end_date=obj_in.end_date,
            window_start=obj_in.collection_window_start, window_end=obj_in.collection_window_end,
        )
        db_obj = ProgramCampaign(**obj_in.model_dump(), created_by_id=user_id)
        db.add(db_obj)
        await db.commit(); await db.refresh(db_obj); return db_obj
    async def update(self, db: AsyncSession, *, db_obj: ProgramCampaign, obj_in: ProgramCampaignUpdate | dict[str, Any]) -> ProgramCampaign:
        payload = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        for field in ("title", "reporting_scope", "status", "start_date", "end_date"):
            if field in payload and payload[field] is None:
                raise HTTPException(status_code=400, detail=f"{field} cannot be null")
        self._validate(event_mode=None, reporting_scope=payload.get('reporting_scope'), status=payload.get('status'))
        if payload.get("status") is not None:
            validate_campaign_transition(db_obj.status, payload["status"])
        self._validate_dates(
            start_date=payload.get('start_date', db_obj.start_date),
            end_date=payload.get('end_date', db_obj.end_date),
            window_start=payload.get('collection_window_start', db_obj.collection_window_start),
            window_end=payload.get('collection_window_end', db_obj.collection_window_end),
        )
        return await super().update(db, db_obj=db_obj, obj_in=obj_in)
    @staticmethod
    def _validate_dates(*, start_date, end_date, window_start, window_end) -> None:
        if start_date and end_date and start_date > end_date:
            raise HTTPException(status_code=400, detail="Campaign start_date must be on or before end_date")
        if window_start and window_end and window_start > window_end:
            raise HTTPException(status_code=400, detail="Collection window start must be on or before its end")
    async def list_by_scope(self, db: AsyncSession, *, scope_path: str, skip: int = 0, limit: int = 100) -> List[ProgramCampaign]:
        result = await db.execute(select(ProgramCampaign).where(scope_or_ancestor_filter(ProgramCampaign.path, scope_path), ProgramCampaign.is_deleted == False).order_by(ProgramCampaign.start_date.desc()).offset(skip).limit(limit))
        return result.scalars().all()
program_campaign = CRUDProgramCampaign(ProgramCampaign)

class CRUDProgramEvent(CRUDBase[ProgramEvent, ProgramEventCreate, ProgramEventUpdate]):
    @staticmethod
    def _validate_metadata(*, event_mode: Optional[str], reporting_scope: Optional[str], audience_segment: Optional[str]) -> None:
        if event_mode is not None and event_mode not in EVENT_MODES:
            raise HTTPException(status_code=400, detail="Invalid event_mode")
        if reporting_scope is not None and reporting_scope not in REPORTING_SCOPES:
            raise HTTPException(status_code=400, detail="Invalid reporting_scope")
        if audience_segment is not None and audience_segment not in AUDIENCE_SEGMENTS:
            raise HTTPException(status_code=400, detail="Invalid audience_segment")
    async def _validate_campaign(self, db: AsyncSession, *, obj: ProgramEventCreate | dict[str, Any], program_type_id: int) -> Optional[ProgramCampaign]:
        campaign_id = obj.campaign_id if hasattr(obj, 'campaign_id') else obj.get('campaign_id')
        if not campaign_id:
            return None
        campaign = await program_campaign.get(db, id=campaign_id)
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if campaign.is_deleted:
            raise HTTPException(status_code=400, detail="Campaign is deleted")
        p_type = await program_type.get(db, id=program_type_id)
        if not p_type:
            raise HTTPException(status_code=404, detail="Program Type not found")
        if p_type.domain_id != campaign.domain_id:
            raise HTTPException(status_code=400, detail="Program type must belong to the same domain as the campaign")
        return campaign
    async def create(self, db: AsyncSession, *, obj_in: ProgramEventCreate) -> ProgramEvent:
        p_type = await program_type.get(db, id=obj_in.program_type_id)
        if not p_type:
            raise HTTPException(status_code=404, detail="Program Type not found")
        self._validate_metadata(event_mode=obj_in.event_mode, reporting_scope=obj_in.reporting_scope, audience_segment=obj_in.audience_segment)
        self._validate_window(obj_in.collection_window_start, obj_in.collection_window_end)
        campaign = await self._validate_campaign(db, obj=obj_in, program_type_id=obj_in.program_type_id)
        payload = obj_in.model_dump()
        if campaign:
            payload['campaign_code'] = payload.get('campaign_code') or campaign.campaign_code
            payload['alpha_location_id'] = payload.get('alpha_location_id') or campaign.alpha_location_id
            payload['event_mode'] = payload.get('event_mode') or campaign.event_mode
            payload['reporting_scope'] = payload.get('reporting_scope') or campaign.reporting_scope
        # The generic CRUD base accepts Pydantic schemas, while event creation
        # enriches the validated schema with campaign defaults above. Pass the
        # enriched fields as a schema-shaped object instead of a raw dict.
        return await super().create(db, obj_in=ProgramEventCreate.model_validate(payload))
    async def update(self, db: AsyncSession, *, db_obj: ProgramEvent, obj_in: ProgramEventUpdate | dict[str, Any]) -> ProgramEvent:
        payload = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)
        for field in ("program_type_id", "date", "path", "event_mode", "reporting_scope", "is_public", "is_alpha_event"):
            if field in payload and payload[field] is None:
                raise HTTPException(status_code=400, detail=f"{field} cannot be null")
        self._validate_metadata(event_mode=payload.get('event_mode'), reporting_scope=payload.get('reporting_scope'), audience_segment=payload.get('audience_segment'))
        self._validate_window(
            payload.get('collection_window_start', db_obj.collection_window_start),
            payload.get('collection_window_end', db_obj.collection_window_end),
        )
        program_type_id = payload.get('program_type_id', db_obj.program_type_id)
        campaign = await self._validate_campaign(db, obj=payload, program_type_id=program_type_id)
        if campaign:
            payload.setdefault('campaign_code', campaign.campaign_code)
            payload.setdefault('alpha_location_id', campaign.alpha_location_id)
        return await super().update(db, db_obj=db_obj, obj_in=payload)
    @staticmethod
    def _validate_window(start, end) -> None:
        if start and end and start > end:
            raise HTTPException(status_code=400, detail="Event collection window start must be on or before its end")
    async def get_multi_by_scope(self, db: AsyncSession, *, scope_path: str, skip: int = 0, limit: int = 100) -> List[ProgramEvent]:
        result = await db.execute(select(ProgramEvent).where(scope_filter(ProgramEvent.path, scope_path)).offset(skip).limit(limit))
        return result.scalars().all()
program_event = CRUDProgramEvent(ProgramEvent)

class CRUDEventAssignment(CRUDBase[EventAssignment, EventAssignmentCreate, EventAssignmentUpdate]):
    @staticmethod
    def _validate(*, assignment_type: Optional[str], source_role: Optional[str], status: Optional[str]) -> None:
        if assignment_type and assignment_type not in ASSIGNMENT_TYPES:
            raise HTTPException(status_code=400, detail="Invalid assignment_type")
        if source_role and source_role not in SOURCE_ROLES:
            raise HTTPException(status_code=400, detail="Invalid source_role")
        if status and status not in ASSIGNMENT_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid assignment status")
    async def create_for_event(self, db: AsyncSession, *, event: ProgramEvent, obj_in: EventAssignmentCreate, assigned_by_id: UUID) -> EventAssignment:
        self._validate(assignment_type=obj_in.assignment_type, source_role=obj_in.source_role, status=None)
        if event.reporting_scope in {"group", "region", "state"} and obj_in.source_role != "regular":
            raise HTTPException(status_code=400, detail="Combined-meeting assignments must use the regular reporting source")
        worker = await get_worker_by_public_id(db, obj_in.worker_id)
        if not worker or worker.is_deleted:
            raise HTTPException(status_code=404, detail="Worker not found")
        if worker.approval_status != "approved":
            raise HTTPException(status_code=400, detail="Only an approved worker may receive an event assignment")
        if obj_in.source_role == "alpha" and not event.alpha_location_id:
            raise HTTPException(status_code=400, detail="Alpha assignment requires an event host location")
        if obj_in.source_role == "satellite" and event.event_mode != "crusade":
            raise HTTPException(status_code=400, detail="Satellite assignments are only valid for crusade events")
        if obj_in.source_role == "regular" and event.event_mode in {"crusade", "retreat"}:
            raise HTTPException(status_code=400, detail="Crusade and retreat assignments must identify alpha or satellite source")
        existing = await db.execute(select(EventAssignment).where(EventAssignment.event_id == event.id, EventAssignment.worker_id == obj_in.worker_id))
        if existing.scalars().first():
            raise HTTPException(status_code=400, detail="Worker already assigned to this event")
        db_obj = EventAssignment(event_id=event.id, worker_id=obj_in.worker_id, path=str(event.path), assignment_label=obj_in.assignment_label, assignment_type=obj_in.assignment_type, source_role=obj_in.source_role, note=obj_in.note, assigned_by_id=assigned_by_id, status="pending")
        db.add(db_obj)
        await db.commit(); await db.refresh(db_obj); return db_obj
    async def list_for_event(self, db: AsyncSession, *, event_id: UUID, scope_path: str) -> List[EventAssignment]:
        result = await db.execute(select(EventAssignment).where(EventAssignment.event_id == event_id, scope_filter(EventAssignment.path, scope_path), EventAssignment.is_deleted == False).order_by(EventAssignment.created_at.desc()))
        return result.scalars().all()
    async def approve(self, db: AsyncSession, *, db_obj: EventAssignment, approved_by_id: UUID) -> EventAssignment:
        db_obj.status = "approved"; db_obj.approved_by_id = approved_by_id; db_obj.approved_at = datetime.now(UTC)
        db.add(db_obj); await db.commit(); await db.refresh(db_obj); return db_obj
    async def reject(self, db: AsyncSession, *, db_obj: EventAssignment, approved_by_id: UUID, note: Optional[str]) -> EventAssignment:
        db_obj.status = "rejected"; db_obj.approved_by_id = approved_by_id; db_obj.approved_at = datetime.now(UTC); db_obj.note = note or db_obj.note
        db.add(db_obj); await db.commit(); await db.refresh(db_obj); return db_obj

event_assignment = CRUDEventAssignment(EventAssignment)
