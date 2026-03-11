"""
Count submission and retrieval routes.

Handles population count data collection with offline sync support.
"""
from typing import Any, List, Optional
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.api import deps
from app.crud.crud_counts import count as crud_count
from app.schemas.counts import CountCreate, CountResponse, CountUpdate
from app.schemas.sync import SyncResult
from app.services.statistics_service import StatisticsService
from app.models.user import User
from app.models.counts import Count
from app.models.programs import ProgramEvent, ProgramType, ProgramDomain

router = APIRouter()


@router.post(
    "/",
    response_model=CountResponse,
    dependencies=[Depends(deps.PermissionChecker("counts:create"))],
)
async def create_count(
    *,
    db: AsyncSession = Depends(deps.get_db),
    count_in: CountCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Submit a new population count.
    
    Supports offline sync via client_id for idempotency.
    If a count with the same client_id already exists, returns the existing record.
    """
    created = await crud_count.create(db, obj_in=count_in, user_id=current_user.user_id)
    await _broadcast_event("count_created", {"id": str(created.id), "location_id": created.location_id})
    return created


async def _broadcast_event(event_type: str, payload: dict) -> None:
    try:
        from app.api.v1.routes.websocket import manager
        import json
        await manager.broadcast(json.dumps({"type": event_type, "data": payload}))
    except Exception:
        # Avoid failing request if broadcast fails
        pass


@router.get(
    "/",
    response_model=List[CountResponse],
    dependencies=[Depends(deps.PermissionChecker("counts:read"))],
)
async def read_counts(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """
    Retrieve counts with hierarchical scope filtering.
    """
    search_scope = scope_path if scope_path else str(current_user.path)
    
    return await crud_count.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )

@router.get("/aggregate")
async def aggregate_counts(
    program_domain: Optional[str] = Query(None, description="Program domain name or slug"),
    program_type: Optional[str] = Query(None, description="Program type name or slug"),
    location_id: Optional[str] = Query(None, description="Filter by location id"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Aggregate counts within scope, grouped by location_id.
    """
    scope_path = str(current_user.path)
    query = select(
        Count.location_id.label("location_id"),
        func.sum(Count.adult_male).label("adult_male"),
        func.sum(Count.adult_female).label("adult_female"),
        func.sum(Count.youth_male).label("youth_male"),
        func.sum(Count.youth_female).label("youth_female"),
        func.sum(Count.boys).label("boys"),
        func.sum(Count.girls).label("girls"),
        func.sum(Count.total).label("total"),
    ).where(
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path),
        Count.is_deleted == False
    )

    if start_date:
        query = query.where(Count.date >= start_date)
    if end_date:
        query = query.where(Count.date <= end_date)
    if location_id:
        query = query.where(Count.location_id == location_id)

    if program_domain or program_type:
        query = query.join(ProgramEvent, ProgramEvent.id == Count.event_id, isouter=True)
        query = query.join(ProgramType, ProgramType.id == ProgramEvent.program_type_id, isouter=True)
        query = query.join(ProgramDomain, ProgramDomain.id == ProgramType.domain_id, isouter=True)
        if program_domain:
            query = query.where((ProgramDomain.name == program_domain) | (ProgramDomain.slug == program_domain))
        if program_type:
            query = query.where((ProgramType.name == program_type) | (ProgramType.slug == program_type))

    query = query.group_by(Count.location_id).order_by(Count.location_id)
    result = await db.execute(query)
    return [dict(row._mapping) for row in result.all()]


@router.get("/aggregate-flex")
async def aggregate_counts_flexible(
    view_level: str = Query(..., description="state, region, group, location"),
    program_domain: Optional[str] = Query(None, description="Program domain name or slug"),
    program_type: Optional[str] = Query(None, description="Program type name or slug"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Aggregate counts by hierarchy level using ltree subpath grouping.
    """
    level_map = {
        "state": 3,
        "region": 4,
        "group": 5,
        "location": 6,
    }
    level_key = view_level.strip().lower()
    if level_key not in level_map:
        raise HTTPException(status_code=400, detail="Invalid view_level")

    scope_path = str(current_user.path)
    segment_count = level_map[level_key]

    group_path = func.subpath(Count.path, 0, segment_count).label("group_path")

    query = select(
        group_path,
        func.sum(Count.adult_male).label("adult_male"),
        func.sum(Count.adult_female).label("adult_female"),
        func.sum(Count.youth_male).label("youth_male"),
        func.sum(Count.youth_female).label("youth_female"),
        func.sum(Count.boys).label("boys"),
        func.sum(Count.girls).label("girls"),
        func.sum(Count.total).label("total"),
    ).where(
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path),
        Count.is_deleted == False
    )

    if start_date:
        query = query.where(Count.date >= start_date)
    if end_date:
        query = query.where(Count.date <= end_date)

    if program_domain or program_type:
        query = query.join(ProgramEvent, ProgramEvent.id == Count.event_id, isouter=True)
        query = query.join(ProgramType, ProgramType.id == ProgramEvent.program_type_id, isouter=True)
        query = query.join(ProgramDomain, ProgramDomain.id == ProgramType.domain_id, isouter=True)
        if program_domain:
            query = query.where((ProgramDomain.name == program_domain) | (ProgramDomain.slug == program_domain))
        if program_type:
            query = query.where((ProgramType.name == program_type) | (ProgramType.slug == program_type))

    query = query.group_by(group_path).order_by(group_path)
    result = await db.execute(query)
    return [dict(row._mapping) for row in result.all()]


@router.get(
    "/{count_id}",
    response_model=CountResponse,
    dependencies=[Depends(deps.PermissionChecker("counts:read"))],
)
async def read_count(
    *,
    db: AsyncSession = Depends(deps.get_db),
    count_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a specific count by ID."""
    count = await crud_count.get(db, id=count_id)
    if not count:
        raise HTTPException(status_code=404, detail="Count not found")
    return count


@router.put(
    "/{count_id}",
    response_model=CountResponse,
    dependencies=[Depends(deps.PermissionChecker("counts:update"))],
)
async def update_count(
    *,
    db: AsyncSession = Depends(deps.get_db),
    count_id: UUID,
    count_in: CountUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a count record."""
    count = await crud_count.get(db, id=count_id)
    if not count:
        raise HTTPException(status_code=404, detail="Count not found")
    
    updated_count = await crud_count.update(db, db_obj=count, obj_in=count_in)
    
    # Recalculate total if demographics changed
    if any([
        count_in.adult_male is not None,
        count_in.adult_female is not None,
        count_in.youth_male is not None,
        count_in.youth_female is not None,
        count_in.boys is not None,
        count_in.girls is not None,
    ]):
        updated_count.calculate_total()
        await db.commit()
        await db.refresh(updated_count)
    
    return updated_count


@router.post(
    "/batch",
    response_model=SyncResult,
    dependencies=[Depends(deps.PermissionChecker("counts:create"))],
)
async def batch_create_counts(
    *,
    db: AsyncSession = Depends(deps.get_db),
    items: List[CountCreate],
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Batch submit counts (offline sync convenience)."""
    result = SyncResult()
    details = []
    for item in items:
        try:
            existing = None
            if item.client_id:
                existing = await crud_count.get_by_client_id(db, client_id=item.client_id)
            if existing:
                result.duplicates += 1
                details.append({"client_id": item.client_id, "id": existing.id, "status": "duplicate"})
                continue
            created = await crud_count.create(db, obj_in=item, user_id=current_user.user_id)
            result.synced += 1
            details.append({"client_id": item.client_id, "id": created.id, "status": "synced"})
        except Exception as e:
            result.errors += 1
            details.append({"client_id": item.client_id, "error": str(e), "status": "error"})
    result.details = details
    return result


@router.get(
    "/stats",
    dependencies=[Depends(deps.PermissionChecker("counts:read"))],
)
async def get_count_stats(
    program_domain: str = None,
    program_type: str = None,
    location_id: str = None,
    start_month: int = None,
    end_month: int = None,
    start_year: int = None,
    end_year: int = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return aggregated population stats (wrapper around statistics service)."""
    scope_path = str(current_user.path)
    stats = await StatisticsService.get_population_statistics(
        db,
        scope_path,
        program_domain,
        program_type,
        location_id,
        None,
        start_month,
        end_month,
        start_year,
        end_year,
    )
    return stats

@router.delete(
    "/{count_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("counts:delete"))],
)
async def delete_count(
    *,
    db: AsyncSession = Depends(deps.get_db),
    count_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a count record."""
    count = await crud_count.get(db, id=count_id)
    if not count:
        raise HTTPException(status_code=404, detail="Count not found")
    
    await crud_count.update(
        db,
        db_obj=count,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None
