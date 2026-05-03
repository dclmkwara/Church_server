"""Program and Event management routes."""
from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, extract
from app.api import deps
from app.crud.crud_programs import program_domain, program_type, program_campaign, program_event, event_assignment
from app.schemas.programs import ProgramDomainCreate, ProgramDomainResponse, ProgramDomainUpdate, ProgramTypeCreate, ProgramTypeResponse, ProgramTypeUpdate, ProgramCampaignCreate, ProgramCampaignResponse, ProgramCampaignUpdate, ProgramEventCreate, ProgramEventResponse, ProgramEventUpdate, EventAssignmentCreate, EventAssignmentResponse
from app.models.programs import ProgramCampaign, ProgramEvent, ProgramType, ProgramDomain
from app.models.user import User, Worker

router = APIRouter()

def _ensure_min_score(current_user: User, min_score: int, detail: str) -> None:
    if max((role.score_value for role in current_user.roles), default=0) < min_score:
        raise HTTPException(status_code=403, detail=detail)

@router.get('/domains', response_model=List[ProgramDomainResponse], dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_domains(db: AsyncSession = Depends(deps.get_db), skip: int = 0, limit: int = 100, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return await program_domain.get_multi(db, skip=skip, limit=limit)

@router.post('/domains', response_model=ProgramDomainResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def create_program_domain(*, db: AsyncSession = Depends(deps.get_db), domain_in: ProgramDomainCreate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return await program_domain.create(db, obj_in=domain_in)

@router.put('/domains/{domain_id}', response_model=ProgramDomainResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def update_program_domain(*, db: AsyncSession = Depends(deps.get_db), domain_id: int, domain_in: ProgramDomainUpdate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    db_domain = await program_domain.get(db, id=domain_id)
    if not db_domain: raise HTTPException(status_code=404, detail='Program Domain not found')
    return await program_domain.update(db, db_obj=db_domain, obj_in=domain_in)

@router.get('/types', response_model=List[ProgramTypeResponse], dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_types(db: AsyncSession = Depends(deps.get_db), domain_id: int = Query(None), skip: int = 0, limit: int = 100, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    if domain_id: return await program_type.get_by_domain(db, domain_id=domain_id)
    return await program_type.get_multi(db, skip=skip, limit=limit)

@router.post('/types', response_model=ProgramTypeResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def create_program_type(*, db: AsyncSession = Depends(deps.get_db), type_in: ProgramTypeCreate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return await program_type.create(db, obj_in=type_in)

@router.put('/types/{type_id}', response_model=ProgramTypeResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def update_program_type(*, db: AsyncSession = Depends(deps.get_db), type_id: int, type_in: ProgramTypeUpdate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    db_type = await program_type.get(db, id=type_id)
    if not db_type: raise HTTPException(status_code=404, detail='Program Type not found')
    return await program_type.update(db, db_obj=db_type, obj_in=type_in)

@router.get('/campaigns', response_model=List[ProgramCampaignResponse], dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_campaigns(db: AsyncSession = Depends(deps.get_db), skip: int = 0, limit: int = 100, current_user: User = Depends(deps.get_current_active_user), scope_path: str = Query(None), domain: str = Query(None), event_mode: str = Query(None), status_value: str = Query(None, alias='status'), campaign_code: str = Query(None)) -> Any:
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    query = select(ProgramCampaign).where(text('CAST(path AS ltree) <@ CAST(:scope_path AS ltree)').bindparams(scope_path=search_scope), ProgramCampaign.is_deleted == False)
    if domain:
        query = query.join(ProgramDomain, ProgramDomain.id == ProgramCampaign.domain_id)
        query = query.where((ProgramDomain.slug == domain) | (ProgramDomain.name == domain))
    if event_mode: query = query.where(ProgramCampaign.event_mode == event_mode)
    if status_value: query = query.where(ProgramCampaign.status == status_value)
    if campaign_code: query = query.where(ProgramCampaign.campaign_code == campaign_code)
    result = await db.execute(query.order_by(ProgramCampaign.start_date.desc()).offset(skip).limit(limit))
    return result.scalars().all()

@router.post('/campaigns', response_model=ProgramCampaignResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def create_program_campaign(*, db: AsyncSession = Depends(deps.get_db), campaign_in: ProgramCampaignCreate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    _ensure_min_score(current_user, 9, 'Global admin access required to create crusade and retreat campaigns')
    deps.ensure_path_in_scope(current_user, campaign_in.path, detail='Campaign path outside your scope')
    if campaign_in.alpha_location_id:
        alpha_location = await deps.get_location_in_scope(db, current_user=current_user, location_id=campaign_in.alpha_location_id, detail='Alpha location outside your scope')
        alpha_check = select(text('CAST(:alpha_path AS ltree) <@ CAST(:campaign_path AS ltree)')).params(alpha_path=str(alpha_location.path), campaign_path=campaign_in.path)
        if not (await db.execute(alpha_check)).scalar(): raise HTTPException(status_code=400, detail='Alpha location must be within the campaign path')
    return await program_campaign.create_for_user(db, obj_in=campaign_in, user_id=current_user.user_id)

@router.get('/campaigns/{campaign_id}', response_model=ProgramCampaignResponse, dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_campaign(campaign_id: UUID, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    campaign = await program_campaign.get(db, id=campaign_id)
    if not campaign: raise HTTPException(status_code=404, detail='Campaign not found')
    deps.ensure_path_in_scope(current_user, campaign.path, detail='Campaign outside your scope')
    return campaign

@router.put('/campaigns/{campaign_id}', response_model=ProgramCampaignResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def update_program_campaign(*, db: AsyncSession = Depends(deps.get_db), campaign_id: UUID, campaign_in: ProgramCampaignUpdate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    _ensure_min_score(current_user, 9, 'Global admin access required to update crusade and retreat campaigns')
    db_campaign = await program_campaign.get(db, id=campaign_id)
    if not db_campaign: raise HTTPException(status_code=404, detail='Campaign not found')
    deps.ensure_path_in_scope(current_user, db_campaign.path, detail='Campaign outside your scope')
    return await program_campaign.update(db, db_obj=db_campaign, obj_in=campaign_in)

@router.get('/events', response_model=List[ProgramEventResponse], dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_events(db: AsyncSession = Depends(deps.get_db), skip: int = 0, limit: int = 100, current_user: User = Depends(deps.get_current_active_user), scope_path: str = Query(None), program_type: str = Query(None), program_domain: str = Query(None), title: str = Query(None), level: str = Query(None), location_id: str = Query(None), date: str = Query(None), start_month: int = Query(None, ge=1, le=12), end_month: int = Query(None, ge=1, le=12), start_year: int = Query(None, ge=1900, le=2100), end_year: int = Query(None, ge=1900, le=2100), event_mode: str = Query(None), reporting_scope: str = Query(None), audience_segment: str = Query(None), campaign_code: str = Query(None), alpha_location_id: str = Query(None), campaign_id: UUID = Query(None)) -> Any:
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    query = select(ProgramEvent).where(text('CAST(path AS ltree) <@ CAST(:scope_path AS ltree)').bindparams(scope_path=search_scope))
    if program_type or program_domain:
        query = query.join(ProgramType, ProgramType.id == ProgramEvent.program_type_id)
        if program_domain:
            query = query.join(ProgramDomain, ProgramDomain.id == ProgramType.domain_id)
            query = query.where((ProgramDomain.name == program_domain) | (ProgramDomain.slug == program_domain))
        if program_type:
            query = query.where((ProgramType.name == program_type) | (ProgramType.slug == program_type))
    if title: query = query.where(ProgramEvent.title.ilike(f'%{title}%'))
    if level:
        level_map = {'state': 3, 'region': 4, 'group': 5, 'location': 6, 'fellowship': 7}
        key = level.strip().lower()
        if key not in level_map: raise HTTPException(status_code=400, detail='Invalid level')
        query = query.where(text('nlevel(CAST(path AS ltree)) = :level').bindparams(level=level_map[key]))
    if location_id:
        location = await deps.get_location_in_scope(db, current_user=current_user, location_id=location_id, detail='Location outside your scope')
        query = query.where(text('CAST(path AS ltree) <@ CAST(:location_path AS ltree)').bindparams(location_path=str(location.path)))
    if date:
        from datetime import date as date_type
        try: date_val = date_type.fromisoformat(date)
        except ValueError: raise HTTPException(status_code=400, detail='Invalid date format (YYYY-MM-DD)')
        query = query.where(ProgramEvent.date == date_val)
    if start_month: query = query.where(extract('month', ProgramEvent.date) >= start_month)
    if end_month: query = query.where(extract('month', ProgramEvent.date) <= end_month)
    if start_year: query = query.where(extract('year', ProgramEvent.date) >= start_year)
    if end_year: query = query.where(extract('year', ProgramEvent.date) <= end_year)
    if event_mode: query = query.where(ProgramEvent.event_mode == event_mode)
    if reporting_scope: query = query.where(ProgramEvent.reporting_scope == reporting_scope)
    if audience_segment: query = query.where(ProgramEvent.audience_segment == audience_segment)
    if campaign_code: query = query.where(ProgramEvent.campaign_code == campaign_code)
    if alpha_location_id: query = query.where(ProgramEvent.alpha_location_id == alpha_location_id)
    if campaign_id: query = query.where(ProgramEvent.campaign_id == campaign_id)
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()

@router.post('/events', response_model=ProgramEventResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def create_program_event(*, db: AsyncSession = Depends(deps.get_db), event_in: ProgramEventCreate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    scope_check = select(text('CAST(:event_path AS ltree) <@ CAST(:scope_path AS ltree)')).params(event_path=event_in.path, scope_path=str(current_user.path))
    if not (await db.execute(scope_check)).scalar(): raise HTTPException(status_code=403, detail='Event path outside your scope')
    if event_in.campaign_id:
        campaign = await program_campaign.get(db, id=event_in.campaign_id)
        if not campaign: raise HTTPException(status_code=404, detail='Campaign not found')
        deps.ensure_path_in_scope(current_user, campaign.path, detail='Campaign outside your scope')
        campaign_check = select(text('CAST(:event_path AS ltree) <@ CAST(:campaign_path AS ltree)')).params(event_path=event_in.path, campaign_path=str(campaign.path))
        if not (await db.execute(campaign_check)).scalar(): raise HTTPException(status_code=400, detail='Event path must sit within the campaign scope')
    if event_in.alpha_location_id:
        alpha_location = await deps.get_location_in_scope(db, current_user=current_user, location_id=event_in.alpha_location_id, detail='Alpha location outside your scope')
        alpha_check = select(text('CAST(:alpha_path AS ltree) <@ CAST(:event_path AS ltree)')).params(alpha_path=str(alpha_location.path), event_path=event_in.path)
        if not (await db.execute(alpha_check)).scalar(): raise HTTPException(status_code=400, detail='Alpha location must be within the event path')
    return await program_event.create(db, obj_in=event_in)

@router.get('/events/{event_id}', response_model=ProgramEventResponse, dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_event(event_id: UUID, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    event = await program_event.get(db, id=event_id)
    if not event: raise HTTPException(status_code=404, detail='Program Event not found')
    deps.ensure_path_in_scope(current_user, event.path, detail='Event outside your scope')
    return event

@router.put('/events/{event_id}', response_model=ProgramEventResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def update_program_event(*, db: AsyncSession = Depends(deps.get_db), event_id: UUID, event_in: ProgramEventUpdate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    db_event = await program_event.get(db, id=event_id)
    if not db_event: raise HTTPException(status_code=404, detail='Program Event not found')
    deps.ensure_path_in_scope(current_user, db_event.path, detail='Event outside your scope')
    target_path = event_in.path or str(db_event.path)
    if event_in.campaign_id:
        campaign = await program_campaign.get(db, id=event_in.campaign_id)
        if not campaign: raise HTTPException(status_code=404, detail='Campaign not found')
        deps.ensure_path_in_scope(current_user, campaign.path, detail='Campaign outside your scope')
        campaign_check = select(text('CAST(:event_path AS ltree) <@ CAST(:campaign_path AS ltree)')).params(event_path=target_path, campaign_path=str(campaign.path))
        if not (await db.execute(campaign_check)).scalar(): raise HTTPException(status_code=400, detail='Event path must sit within the campaign scope')
    if event_in.alpha_location_id:
        alpha_location = await deps.get_location_in_scope(db, current_user=current_user, location_id=event_in.alpha_location_id, detail='Alpha location outside your scope')
        alpha_check = select(text('CAST(:alpha_path AS ltree) <@ CAST(:event_path AS ltree)')).params(alpha_path=str(alpha_location.path), event_path=target_path)
        if not (await db.execute(alpha_check)).scalar(): raise HTTPException(status_code=400, detail='Alpha location must be within the event path')
    return await program_event.update(db, db_obj=db_event, obj_in=event_in)

@router.get('/events/{event_id}/assignments', response_model=List[EventAssignmentResponse], dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def list_event_assignments(event_id: UUID, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    event = await program_event.get(db, id=event_id)
    if not event: raise HTTPException(status_code=404, detail='Program Event not found')
    deps.ensure_path_in_scope(current_user, event.path, detail='Event outside your scope')
    return await event_assignment.list_for_event(db, event_id=event_id, scope_path=str(current_user.path))

@router.post('/events/{event_id}/assignments', response_model=EventAssignmentResponse, dependencies=[Depends(deps.PermissionChecker('programs:assign_workers'))])
async def create_event_assignment(event_id: UUID, assignment_in: EventAssignmentCreate, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    _ensure_min_score(current_user, 6, 'State-level access required for officiating assignments')
    event = await program_event.get(db, id=event_id)
    if not event: raise HTTPException(status_code=404, detail='Program Event not found')
    deps.ensure_path_in_scope(current_user, event.path, detail='Event outside your scope')
    worker = await db.get(Worker, assignment_in.worker_id)
    if not worker: raise HTTPException(status_code=404, detail='Worker not found')
    deps.ensure_path_in_scope(current_user, worker.path, detail='Worker outside your scope')
    return await event_assignment.create_for_event(db, event=event, obj_in=assignment_in, assigned_by_id=current_user.user_id)

@router.post('/assignments/{assignment_id}/approve', response_model=EventAssignmentResponse, dependencies=[Depends(deps.PermissionChecker('programs:approve_assignments'))])
async def approve_event_assignment(assignment_id: UUID, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    _ensure_min_score(current_user, 6, 'State-overseer level approval required')
    db_assignment = await event_assignment.get(db, id=assignment_id)
    if not db_assignment: raise HTTPException(status_code=404, detail='Assignment not found')
    deps.ensure_path_in_scope(current_user, db_assignment.path, detail='Assignment outside your scope')
    return await event_assignment.approve(db, db_obj=db_assignment, approved_by_id=current_user.user_id)

@router.post('/assignments/{assignment_id}/reject', response_model=EventAssignmentResponse, dependencies=[Depends(deps.PermissionChecker('programs:approve_assignments'))])
async def reject_event_assignment(assignment_id: UUID, note: str = Query(None), db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    _ensure_min_score(current_user, 6, 'State-overseer level approval required')
    db_assignment = await event_assignment.get(db, id=assignment_id)
    if not db_assignment: raise HTTPException(status_code=404, detail='Assignment not found')
    deps.ensure_path_in_scope(current_user, db_assignment.path, detail='Assignment outside your scope')
    return await event_assignment.reject(db, db_obj=db_assignment, approved_by_id=current_user.user_id, note=note)
