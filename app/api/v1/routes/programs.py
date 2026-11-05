"""Program and Event management routes."""
from typing import Any, List
from datetime import date as date_type, datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, extract, exists, cast
from sqlalchemy.orm import selectinload, joinedload
from app.api import deps
from app.db.filters import scope_filter, scope_or_ancestor_filter
from app.crud.crud_programs import program_domain, program_type, program_campaign, program_event, event_assignment, get_worker_by_public_id
from app.schemas.programs import ProgramDomainCreate, ProgramDomainResponse, ProgramDomainUpdate, ProgramTypeCreate, ProgramTypeResponse, ProgramTypeUpdate, ProgramCampaignCreate, ProgramCampaignResponse, ProgramCampaignUpdate, ProgramEventCreate, ProgramEventResponse, ProgramEventUpdate, EventAssignmentCreate, EventAssignmentResponse
from app.schemas.attendance import WorkerLookupResponse
from app.models.programs import ProgramCampaign, ProgramEvent, ProgramType, ProgramDomain, EventAssignment
from app.models.user import User, Worker
from app.models.core import _LTREE
from app.crud.workflow_rules import collection_window_is_active, ensure_collection_open, load_event_campaign, widen_scope_for_approved_event_submission

router = APIRouter()

def _ensure_min_score(current_user: User, min_score: int, detail: str) -> None:
    if max((role.score_value for role in current_user.roles), default=0) < min_score:
        raise HTTPException(status_code=403, detail=detail)

_STATE_OR_HIGHER_ROLES = (
    'State Admin', 'State Overseer', 'Zonal Coordinator',
    'National Admin', 'National Overseer', 'Continental Admin',
    'Continental Overseer', 'Global Admin',
)

def _has_authoritative_role(current_user: User) -> bool:
    return any(role.role_name in _STATE_OR_HIGHER_ROLES for role in (current_user.roles or []))

@router.get('/domains', response_model=List[ProgramDomainResponse], dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_domains(db: AsyncSession = Depends(deps.get_db), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return await program_domain.get_multi(db, skip=skip, limit=limit)

@router.post('/domains', response_model=ProgramDomainResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def create_program_domain(*, db: AsyncSession = Depends(deps.get_db), domain_in: ProgramDomainCreate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return await program_domain.create(db, obj_in=domain_in)

@router.get('/domains/{domain_id}', response_model=ProgramDomainResponse, dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_domain(*, db: AsyncSession = Depends(deps.get_db), domain_id: int, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    db_domain = await program_domain.get(db, id=domain_id)
    if not db_domain: raise HTTPException(status_code=404, detail='Program Domain not found')
    return db_domain

@router.put('/domains/{domain_id}', response_model=ProgramDomainResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def update_program_domain(*, db: AsyncSession = Depends(deps.get_db), domain_id: int, domain_in: ProgramDomainUpdate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    db_domain = await program_domain.get(db, id=domain_id)
    if not db_domain: raise HTTPException(status_code=404, detail='Program Domain not found')
    return await program_domain.update(db, db_obj=db_domain, obj_in=domain_in)

@router.get('/types', response_model=List[ProgramTypeResponse], dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_types(db: AsyncSession = Depends(deps.get_db), domain_id: int = Query(None), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    if domain_id:
        return await program_type.get_by_domain(db, domain_id=domain_id, skip=skip, limit=limit)
    return await program_type.get_multi(db, skip=skip, limit=limit)

@router.get('/types/{type_id}', response_model=ProgramTypeResponse, dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_type(*, db: AsyncSession = Depends(deps.get_db), type_id: int, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    db_type = await program_type.get(db, id=type_id)
    if not db_type: raise HTTPException(status_code=404, detail='Program Type not found')
    return db_type

@router.post('/types', response_model=ProgramTypeResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def create_program_type(*, db: AsyncSession = Depends(deps.get_db), type_in: ProgramTypeCreate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    return await program_type.create(db, obj_in=type_in)

@router.put('/types/{type_id}', response_model=ProgramTypeResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def update_program_type(*, db: AsyncSession = Depends(deps.get_db), type_id: int, type_in: ProgramTypeUpdate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    db_type = await program_type.get(db, id=type_id)
    if not db_type: raise HTTPException(status_code=404, detail='Program Type not found')
    return await program_type.update(db, db_obj=db_type, obj_in=type_in)

@router.get('/campaigns', response_model=List[ProgramCampaignResponse], dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_campaigns(db: AsyncSession = Depends(deps.get_db), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), current_user: User = Depends(deps.get_current_active_user), scope_path: str = Query(None), domain: str = Query(None), event_mode: str = Query(None), status_value: str = Query(None, alias='status'), campaign_code: str = Query(None)) -> Any:
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    query = select(ProgramCampaign).where(scope_or_ancestor_filter(ProgramCampaign.path, search_scope), ProgramCampaign.is_deleted == False)
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
    _ensure_min_score(current_user, 5, 'State-level access required to create crusade and retreat campaigns')
    if 6 in [role.score_value for role in (current_user.roles or [])] and deps.highest_role_score(current_user) == 6:
        raise HTTPException(status_code=403, detail='Zonal scope mapping is not configured')
    if not _has_authoritative_role(current_user):
        raise HTTPException(status_code=403, detail='State or higher administration role required')
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
    _ensure_min_score(current_user, 5, 'State-level access required to update crusade and retreat campaigns')
    if 6 in [role.score_value for role in (current_user.roles or [])] and deps.highest_role_score(current_user) == 6:
        raise HTTPException(status_code=403, detail='Zonal scope mapping is not configured')
    if not _has_authoritative_role(current_user):
        raise HTTPException(status_code=403, detail='State or higher administration role required')
    db_campaign = await program_campaign.get(db, id=campaign_id)
    if not db_campaign: raise HTTPException(status_code=404, detail='Campaign not found')
    deps.ensure_path_in_scope(current_user, db_campaign.path, detail='Campaign outside your scope')
    return await program_campaign.update(db, db_obj=db_campaign, obj_in=campaign_in)

@router.get('/events', response_model=List[ProgramEventResponse], dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_events(db: AsyncSession = Depends(deps.get_db), skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500), current_user: User = Depends(deps.get_current_active_user), scope_path: str = Query(None), program_type: str = Query(None), program_domain: str = Query(None), title: str = Query(None), level: str = Query(None), location_id: str = Query(None), date: str = Query(None), start_month: int = Query(None, ge=1, le=12), end_month: int = Query(None, ge=1, le=12), start_year: int = Query(None, ge=1900, le=2100), end_year: int = Query(None, ge=1900, le=2100), event_mode: str = Query(None), reporting_scope: str = Query(None), audience_segment: str = Query(None), campaign_code: str = Query(None), alpha_location_id: str = Query(None), campaign_id: UUID = Query(None)) -> Any:
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    query_scope_filter = deps.scope_condition(ProgramEvent.path, current_user, scope_path)
    query = select(ProgramEvent).options(
        selectinload(ProgramEvent.program_type),
        selectinload(ProgramEvent.campaign),
    ).where(scope_or_ancestor_filter(ProgramEvent.path, search_scope))
    if deps.highest_role_score(current_user) == 8:
        query = query.where(query_scope_filter)
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
        query = query.where(
            cast(str(location.path), _LTREE()).op('<@')(cast(ProgramEvent.path, _LTREE()))
        )
        if deps.highest_role_score(current_user) == 1:
            if not current_user.worker_id:
                return []
            query = query.where(exists(select(EventAssignment.id).where(
                EventAssignment.event_id == ProgramEvent.id,
                EventAssignment.worker_id == current_user.worker_id,
                EventAssignment.status == 'approved',
                EventAssignment.is_deleted.is_(False),
            )))
    if date:
        try: date_val = date_type.fromisoformat(date)
        except ValueError: raise HTTPException(status_code=400, detail='Invalid date format (YYYY-MM-DD)')
        query = query.where(ProgramEvent.date == date_val)
    if start_year and end_year and start_year > end_year:
        raise HTTPException(status_code=400, detail='start_year must be less than or equal to end_year')
    if start_month and end_month and start_month > end_month:
        raise HTTPException(status_code=400, detail='start_month must be less than or equal to end_month')
    if start_month: query = query.where(extract('month', ProgramEvent.date) >= start_month)
    if end_month: query = query.where(extract('month', ProgramEvent.date) <= end_month)
    if start_year: query = query.where(ProgramEvent.date >= date_type(start_year, 1, 1))
    if end_year: query = query.where(ProgramEvent.date < date_type(end_year + 1, 1, 1))
    if event_mode: query = query.where(ProgramEvent.event_mode == event_mode)
    if reporting_scope: query = query.where(ProgramEvent.reporting_scope == reporting_scope)
    if audience_segment: query = query.where(ProgramEvent.audience_segment == audience_segment)
    if campaign_code: query = query.where(ProgramEvent.campaign_code == campaign_code)
    if alpha_location_id: query = query.where(ProgramEvent.alpha_location_id == alpha_location_id)
    if campaign_id: query = query.where(ProgramEvent.campaign_id == campaign_id)
    if deps.highest_role_score(current_user) == 1:
        query = query.where(ProgramEvent.approval_status == 'approved')
    result = await db.execute(query.offset(skip).limit(limit))
    return result.scalars().all()

@router.post('/events', response_model=ProgramEventResponse, dependencies=[Depends(deps.PermissionChecker('programs:create_event'))])
async def create_program_event(*, db: AsyncSession = Depends(deps.get_db), event_in: ProgramEventCreate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    score = deps.highest_role_score(current_user)
    _ensure_min_score(current_user, 2, 'Location governance or higher is required to schedule an event')
    scope_check = select(text('CAST(:event_path AS ltree) <@ CAST(:scope_path AS ltree)')).params(event_path=event_in.path, scope_path=deps.effective_scope_path(current_user))
    if not (await db.execute(scope_check)).scalar(): raise HTTPException(status_code=403, detail='Event path outside your scope')
    expected_depth = {'location': 6, 'group': 5, 'region': 4, 'state': 3}.get(event_in.reporting_scope)
    if expected_depth is None:
        raise HTTPException(status_code=422, detail='Scheduled events must use a location, group, region, or state scope')
    actual_depth = await db.scalar(select(text('nlevel(CAST(:event_path AS ltree))')).params(event_path=event_in.path))
    if actual_depth != expected_depth:
        raise HTTPException(status_code=422, detail='Reporting scope must match the hierarchy depth of the scheduled event path')
    if 2 <= score <= 5:
        allowed_scope = {2: 'location', 3: 'group', 4: 'region', 5: 'state'}[score]
        if event_in.reporting_scope != allowed_scope or event_in.path != deps.effective_scope_path(current_user):
            raise HTTPException(status_code=403, detail=f'Your role may schedule only at its own {allowed_scope} scope')
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
    if event_in.event_mode in {'crusade', 'retreat'} and not event_in.campaign_id:
        raise HTTPException(status_code=422, detail='Crusade and retreat sessions must be linked to a campaign/series with an active window')
    if event_in.event_mode == 'crusade' and not event_in.alpha_location_id:
        raise HTTPException(status_code=422, detail='Crusade sessions must identify their Alpha Location')
    if event_in.collection_window_start and event_in.collection_window_end:
        now = datetime.now(timezone.utc)
        if event_in.collection_window_start.tzinfo is None:
            event_start = event_in.collection_window_start.replace(tzinfo=timezone.utc)
        else:
            event_start = event_in.collection_window_start
        if event_in.collection_window_end.tzinfo is None:
            event_end = event_in.collection_window_end.replace(tzinfo=timezone.utc)
        else:
            event_end = event_in.collection_window_end
        if event_start <= now <= event_end:
            raise HTTPException(status_code=422, detail='New schedules cannot begin collecting immediately; set a future opening time')
    created = await program_event.create(db, obj_in=event_in)
    created.created_by_id = current_user.user_id
    if _is_event_pastor_for_scope(current_user, event_in.reporting_scope, str(event_in.path)):
        created.approval_status = 'approved'
        created.approved_by_id = current_user.user_id
        created.approved_at = datetime.now(timezone.utc)
        created.approval_note = None
    else:
        created.approval_status = 'pending'
    await db.commit()
    await db.refresh(created)
    result = await db.execute(
        select(ProgramEvent).options(
            selectinload(ProgramEvent.program_type),
            selectinload(ProgramEvent.campaign),
        ).where(ProgramEvent.id == created.id)
    )
    return result.scalar_one()


EVENT_PASTOR_SCOPE_ROLES = {
        'location': (2, {'Location Pastor'}),
        'group': (3, {'Group Pastor'}),
        'region': (4, {'Region Pastor'}),
        'state': (5, {'State Overseer'}),
}


def _is_event_pastor_for_scope(current_user: User, reporting_scope: str, event_path: str) -> bool:
    scope_role = EVENT_PASTOR_SCOPE_ROLES.get(reporting_scope)
    if not scope_role:
        return False
    score, pastor_roles = scope_role
    role_names = {role.role_name for role in (current_user.roles or [])}
    return (
        deps.highest_role_score(current_user) == score
        and bool(role_names & pastor_roles)
        and str(deps.effective_scope_path(current_user)) == str(event_path)
    )


def _require_event_pastor(current_user: User, event: ProgramEvent) -> None:
    if event.reporting_scope not in EVENT_PASTOR_SCOPE_ROLES:
        raise HTTPException(status_code=422, detail='Event has an unsupported approval scope')
    if not _is_event_pastor_for_scope(current_user, event.reporting_scope, str(event.path)):
        raise HTTPException(status_code=403, detail='Only the pastor at the event jurisdiction may approve this schedule')
    if getattr(event, 'created_by_id', None) and str(event.created_by_id) == str(current_user.user_id):
        raise HTTPException(status_code=403, detail='The event creator cannot approve their own schedule')


@router.post('/events/{event_id}/approve', response_model=ProgramEventResponse)
async def approve_program_event(
    event_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    event = await program_event.get(db, id=event_id)
    if not event or event.is_deleted:
        raise HTTPException(status_code=404, detail='Program Event not found')
    _require_event_pastor(current_user, event)
    if event.approval_status != 'pending':
        raise HTTPException(status_code=409, detail=f'Only pending events can be approved (current status: {event.approval_status})')
    event.approval_status = 'approved'
    event.approved_by_id = current_user.user_id
    event.approved_at = datetime.now(timezone.utc)
    event.approval_note = None
    await db.commit()
    await db.refresh(event)
    result = await db.execute(select(ProgramEvent).options(
        selectinload(ProgramEvent.program_type), selectinload(ProgramEvent.campaign),
    ).where(ProgramEvent.id == event.id))
    return result.scalar_one()


@router.post('/events/{event_id}/reject', response_model=ProgramEventResponse)
async def reject_program_event(
    event_id: UUID,
    note: str = Query(..., min_length=5, max_length=1000),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    event = await program_event.get(db, id=event_id)
    if not event or event.is_deleted:
        raise HTTPException(status_code=404, detail='Program Event not found')
    _require_event_pastor(current_user, event)
    if event.approval_status != 'pending':
        raise HTTPException(status_code=409, detail=f'Only pending events can be rejected (current status: {event.approval_status})')
    event.approval_status = 'rejected'
    event.approved_by_id = current_user.user_id
    event.approved_at = datetime.now(timezone.utc)
    event.approval_note = note.strip()
    await db.commit()
    await db.refresh(event)
    result = await db.execute(select(ProgramEvent).options(
        selectinload(ProgramEvent.program_type), selectinload(ProgramEvent.campaign),
    ).where(ProgramEvent.id == event.id))
    return result.scalar_one()

@router.get('/events/{event_id}', response_model=ProgramEventResponse, dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def read_program_event(event_id: UUID, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    result = await db.execute(
        select(ProgramEvent).options(
            selectinload(ProgramEvent.program_type),
            selectinload(ProgramEvent.campaign),
        ).where(ProgramEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event: raise HTTPException(status_code=404, detail='Program Event not found')
    deps.ensure_path_in_scope(current_user, event.path, detail='Event outside your scope')
    return event

@router.get('/assignments/me/active')
async def read_my_active_event_assignments(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return only this worker's approved event assignments whose collection window is open."""
    if not current_user.worker_id:
        raise HTTPException(status_code=403, detail='A linked worker account is required')
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(EventAssignment)
        .join(ProgramEvent, ProgramEvent.id == EventAssignment.event_id)
        .options(
            joinedload(EventAssignment.event).joinedload(ProgramEvent.program_type).joinedload(ProgramType.domain),
            joinedload(EventAssignment.event).joinedload(ProgramEvent.campaign),
        )
        .where(
            EventAssignment.worker_id == current_user.worker_id,
            EventAssignment.status == 'approved',
            EventAssignment.is_deleted.is_(False),
            ProgramEvent.is_deleted.is_(False),
            ProgramEvent.approval_status == 'approved',
        )
        .order_by(ProgramEvent.date.asc(), EventAssignment.created_at.desc())
        .limit(100)
    )
    rows = result.scalars().unique().all()
    active = []
    for assignment in rows:
        event = assignment.event
        campaign = event.campaign
        if campaign and campaign.status != 'active':
            continue
        if not collection_window_is_active(event, campaign, now=now):
            continue
        start = event.collection_window_start or campaign.collection_window_start
        end = event.collection_window_end or campaign.collection_window_end
        ptype = event.program_type
        active.append({
            'assignment_id': str(assignment.id),
            'assignment_type': assignment.assignment_type,
            'source_role': assignment.source_role,
            'event': {
                'id': str(event.id),
                'title': event.title or ptype.name,
                'date': event.date.isoformat(),
                'path': str(event.path),
                'event_mode': event.event_mode,
                'reporting_scope': event.reporting_scope,
                'alpha_location_id': getattr(event, 'alpha_location_id', None),
                'program_type': {'id': ptype.id, 'name': ptype.name, 'domain_id': ptype.domain_id,
                                 'domain': {'id': ptype.domain.id, 'name': ptype.domain.name,
                                            'slug': ptype.domain.slug}},
                'campaign': ({'id': str(campaign.id), 'status': campaign.status} if campaign else None),
                'collection_window_start': start.isoformat(),
                'collection_window_end': end.isoformat(),
            },
        })
    return active

@router.put('/events/{event_id}', response_model=ProgramEventResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def update_program_event(*, db: AsyncSession = Depends(deps.get_db), event_id: UUID, event_in: ProgramEventUpdate, current_user: User = Depends(deps.get_current_active_user)) -> Any:
    db_event = await program_event.get(db, id=event_id)
    if not db_event: raise HTTPException(status_code=404, detail='Program Event not found')
    deps.ensure_path_in_scope(current_user, db_event.path, detail='Event outside your scope')
    score = deps.highest_role_score(current_user)
    if 2 <= score <= 5:
        own_scope = {2: 'location', 3: 'group', 4: 'region', 5: 'state'}[score]
        if db_event.reporting_scope != own_scope or str(db_event.path) != deps.effective_scope_path(current_user):
            raise HTTPException(status_code=403, detail=f'Your role may manage only events at its own {own_scope} scope')
    target_path = event_in.path or str(db_event.path)
    target_scope = event_in.reporting_scope or db_event.reporting_scope
    expected_depth = {'location': 6, 'group': 5, 'region': 4, 'state': 3}.get(target_scope)
    actual_depth = await db.scalar(select(text('nlevel(CAST(:event_path AS ltree))')).params(event_path=target_path))
    if expected_depth is None or expected_depth != actual_depth:
        raise HTTPException(status_code=422, detail='Reporting scope must match the hierarchy depth of the scheduled event path')
    if 2 <= score <= 5:
        own_scope = {2: 'location', 3: 'group', 4: 'region', 5: 'state'}[score]
        if target_scope != own_scope or target_path != deps.effective_scope_path(current_user):
            raise HTTPException(status_code=403, detail=f'Your role may manage only events at its own {own_scope} scope')
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
    updated = await program_event.update(db, db_obj=db_event, obj_in=event_in)
    result = await db.execute(
        select(ProgramEvent).options(
            selectinload(ProgramEvent.program_type),
            selectinload(ProgramEvent.campaign),
        ).where(ProgramEvent.id == updated.id)
    )
    return result.scalar_one()

@router.post('/events/{event_id}/close-collection', response_model=ProgramEventResponse, dependencies=[Depends(deps.PermissionChecker('programs:manage'))])
async def close_event_collection(
    event_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """End event data collection immediately; assignment-based Utility setup expires with it."""
    event = await program_event.get(db, id=event_id)
    if not event or event.is_deleted:
        raise HTTPException(status_code=404, detail='Program Event not found')
    deps.ensure_path_in_scope(current_user, event.path, detail='Event outside your scope')
    _ensure_min_score(current_user, 2, 'Location governance or higher is required to close event collection')
    score = deps.highest_role_score(current_user)
    if 2 <= score <= 5:
        own_scope = {2: 'location', 3: 'group', 4: 'region', 5: 'state'}[score]
        if event.reporting_scope != own_scope or str(event.path) != deps.effective_scope_path(current_user):
            raise HTTPException(status_code=403, detail=f'Your role may close collection only at its own {own_scope} scope')
    now = datetime.now(timezone.utc)
    if event.collection_window_start and event.collection_window_start > now:
        raise HTTPException(status_code=409, detail='This scheduled collection window has not opened yet')
    await program_event.update(db, db_obj=event, obj_in={
        'collection_window_start': min(event.collection_window_start or now, now),
        'collection_window_end': now,
    })
    result = await db.execute(select(ProgramEvent).options(
        selectinload(ProgramEvent.program_type), selectinload(ProgramEvent.campaign),
    ).where(ProgramEvent.id == event.id))
    return result.scalar_one()

@router.get('/events/{event_id}/assignments', response_model=List[EventAssignmentResponse], dependencies=[Depends(deps.PermissionChecker('programs:read'))])
async def list_event_assignments(event_id: UUID, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    event = await program_event.get(db, id=event_id)
    if not event: raise HTTPException(status_code=404, detail='Program Event not found')
    deps.ensure_path_in_scope(current_user, event.path, detail='Event outside your scope')
    return await event_assignment.list_for_event(db, event_id=event_id, scope_path=deps.effective_scope_path(current_user))

@router.post('/events/{event_id}/assignments', response_model=EventAssignmentResponse, dependencies=[Depends(deps.PermissionChecker('programs:assign_workers'))])
async def create_event_assignment(event_id: UUID, assignment_in: EventAssignmentCreate, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    _ensure_min_score(current_user, 3, 'Group-level access required for event assignments')
    event = await program_event.get(db, id=event_id)
    if not event: raise HTTPException(status_code=404, detail='Program Event not found')
    deps.ensure_path_in_scope(current_user, event.path, detail='Event outside your scope')
    campaign = await load_event_campaign(db, event)
    window_start, window_end = event.collection_window_start or (campaign.collection_window_start if campaign else None), event.collection_window_end or (campaign.collection_window_end if campaign else None)
    if not window_start or not window_end:
        raise HTTPException(status_code=422, detail='Assigned events require an explicit collection start and end time for automatic Utility setup and expiry')
    if campaign and campaign.status != 'active':
        raise HTTPException(status_code=409, detail='Workers can be assigned only to an active campaign')
    now = datetime.now(timezone.utc)
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=timezone.utc)
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=timezone.utc)
    if window_end <= now:
        raise HTTPException(status_code=409, detail='Cannot assign workers to a session whose collection window has expired')
    if event.event_mode == 'crusade' and assignment_in.source_role == 'alpha':
        _ensure_min_score(current_user, 5, 'State-level access is required for Alpha Location assignments')
    worker = await get_worker_by_public_id(db, assignment_in.worker_id)
    if not worker: raise HTTPException(status_code=404, detail='Worker not found')
    deps.ensure_path_in_scope(current_user, worker.path, detail='Worker outside your scope')
    if not deps.path_in_scope(event.path, worker.path):
        raise HTTPException(status_code=403, detail='Worker is outside the event reporting scope')
    if event.reporting_scope in {'group', 'region', 'state'} and assignment_in.source_role == 'alpha':
        assignment_in = assignment_in.model_copy(update={'source_role': 'regular'})
    return await event_assignment.create_for_event(db, event=event, obj_in=assignment_in, assigned_by_id=current_user.user_id)


@router.get('/events/{event_id}/field-access')
async def check_event_field_access(event_id: UUID, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    """Report whether the signed-in event-field worker has an approved assignment."""
    event = await program_event.get(db, id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail='Program Event not found')
    if event.approval_status != 'approved':
        return {"event_id": str(event_id), "can_submit": False, "assignment_id": None, "reason": "event_not_approved"}
    if deps.highest_role_score(current_user) != 1:
        raise HTTPException(status_code=403, detail='Worker-level account required for event field access')
    assignment_query = select(EventAssignment).where(
        EventAssignment.event_id == event_id,
        EventAssignment.path == event.path,
        EventAssignment.status == 'approved',
        EventAssignment.is_deleted == False,
    )
    if current_user.worker_id is None:
        return {"event_id": str(event_id), "can_submit": False, "assignment_id": None}
    assignment_query = assignment_query.where(EventAssignment.worker_id == current_user.worker_id)
    assignment = (await db.execute(assignment_query)).scalars().first()
    if assignment is not None:
        campaign = await load_event_campaign(db, event)
        if (campaign and campaign.status != 'active') or not collection_window_is_active(event, campaign):
            assignment = None
    if assignment is not None and event.event_mode == "crusade" and assignment.source_role not in {"alpha", "satellite"}:
        assignment = None
    if assignment is not None and assignment.source_role == "alpha" and not event.alpha_location_id:
        assignment = None
    return {
        "event_id": str(event_id),
        "can_submit": assignment is not None,
        "assignment_id": str(assignment.id) if assignment else None,
        "source_role": assignment.source_role if assignment else None,
        "assignment_type": assignment.assignment_type if assignment else None,
    }


@router.get('/events/{event_id}/attendance-roster', response_model=List[WorkerLookupResponse])
async def get_event_attendance_roster(
    event_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return the approved roster for an assigned combined meeting."""
    event = await program_event.get(db, id=event_id)
    if not event or event.is_deleted:
        raise HTTPException(status_code=404, detail='Program Event not found')
    if deps.highest_role_score(current_user) != 1 or not current_user.worker_id:
        raise HTTPException(status_code=403, detail='Worker-level account required for field attendance')
    if event.reporting_scope not in {'group', 'region', 'state'}:
        raise HTTPException(status_code=400, detail='A combined reporting event is required')
    assignment_result = await db.execute(select(EventAssignment).where(
        EventAssignment.event_id == event.id,
        EventAssignment.worker_id == current_user.worker_id,
        EventAssignment.status == 'approved',
        EventAssignment.assignment_type.in_(['attendance', 'all']),
        EventAssignment.is_deleted.is_(False),
    ))
    assignment = assignment_result.scalars().first()
    if not assignment:
        raise HTTPException(status_code=403, detail='An approved attendance assignment is required for this meeting')
    campaign = await program_campaign.get(db, id=event.campaign_id) if event.campaign_id else None
    ensure_collection_open(event, campaign, kind='attendance')
    if campaign and campaign.status != 'active':
        raise HTTPException(status_code=403, detail='Attendance assignment campaign is not active')
    if not collection_window_is_active(event, campaign):
        raise HTTPException(status_code=403, detail='Attendance assignment is outside its active collection window')
    await widen_scope_for_approved_event_submission(db, event)
    roster_result = await db.execute(select(Worker).where(
        scope_filter(Worker.path, str(event.path)),
        Worker.approval_status == 'approved',
        Worker.is_deleted.is_(False),
    ).order_by(Worker.name.asc()).limit(5000))
    workers = roster_result.scalars().all()
    result = []
    for worker in workers:
        location = await db.get(__import__("app.models.location", fromlist=["Location"]).Location, worker.location_id)
        result.append({
            "worker_id": worker.worker_id,
            "user_id": str(worker.user_id or ""),
            "name": worker.name,
            "unit": worker.unit,
            "phone": str(worker.phone or ""),
            "location_id": worker.location_id,
            "location_name": location.location_name if location else "",
            "church_type": worker.church_type,
            "path": str(worker.path),
        })
    return result

@router.post('/assignments/{assignment_id}/approve', response_model=EventAssignmentResponse, dependencies=[Depends(deps.PermissionChecker('programs:approve_assignments'))])
async def approve_event_assignment(assignment_id: UUID, db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    _ensure_min_score(current_user, 3, 'Group-level access is required to approve event assignments')
    db_assignment = await event_assignment.get(db, id=assignment_id)
    if not db_assignment: raise HTTPException(status_code=404, detail='Assignment not found')
    deps.ensure_path_in_scope(current_user, db_assignment.path, detail='Assignment outside your scope')
    _ensure_min_score(current_user, 3, 'Group-level access is required to approve event assignments')
    return await event_assignment.approve(db, db_obj=db_assignment, approved_by_id=current_user.user_id)

@router.post('/assignments/{assignment_id}/reject', response_model=EventAssignmentResponse, dependencies=[Depends(deps.PermissionChecker('programs:approve_assignments'))])
async def reject_event_assignment(assignment_id: UUID, note: str = Query(None), db: AsyncSession = Depends(deps.get_db), current_user: User = Depends(deps.get_current_active_user)) -> Any:
    _ensure_min_score(current_user, 3, 'Group-level access is required to reject event assignments')
    db_assignment = await event_assignment.get(db, id=assignment_id)
    if not db_assignment: raise HTTPException(status_code=404, detail='Assignment not found')
    deps.ensure_path_in_scope(current_user, db_assignment.path, detail='Assignment outside your scope')
    _ensure_min_score(current_user, 3, 'Group-level access is required to reject event assignments')
    return await event_assignment.reject(db, db_obj=db_assignment, approved_by_id=current_user.user_id, note=note)

