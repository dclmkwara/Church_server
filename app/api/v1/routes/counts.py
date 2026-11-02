"""
Count submission and retrieval routes.

Handles population count data collection with offline sync support.
"""
from typing import Any, List, Optional
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, or_

from app.api import deps
from app.db.filters import ltree_subpath as _ltree_subpath
from app.db.filters import scope_filter as _scope_filter
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
    await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=count_in.location_id,
        detail="Count location outside your scope",
    )
    created = await crud_count.create(db, obj_in=count_in, user_id=current_user.user_id)
    deps.ensure_path_in_scope(current_user, created.path, detail="Existing count is outside your scope")
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
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """
    Retrieve counts with hierarchical scope filtering.
    """
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    
    rows = await crud_count.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )
    return deps.filter_rows_in_scope(rows, current_user)

@router.get(
    "/aggregate",
    dependencies=[Depends(deps.PermissionChecker("counts:read"))],
)
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
    scope_path = deps.effective_scope_path(current_user)
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
        deps.scope_condition(Count.path, current_user),
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
            query = query.where(or_(Count.program_domain == program_domain, ProgramDomain.name == program_domain, ProgramDomain.slug == program_domain))
        if program_type:
            query = query.where(or_(Count.program_type == program_type, ProgramType.name == program_type, ProgramType.slug == program_type))

    query = query.group_by(Count.location_id).order_by(Count.location_id)
    result = await db.execute(query)
    return [dict(row._mapping) for row in result.all()]


@router.get(
    "/aggregate-flex",
    dependencies=[Depends(deps.PermissionChecker("counts:read"))],
)
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

    scope_path = deps.effective_scope_path(current_user)
    segment_count = level_map[level_key]

    group_path = _ltree_subpath(Count.path, segment_count).label("group_path")

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
        deps.scope_condition(Count.path, current_user),
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
            query = query.where(or_(Count.program_domain == program_domain, ProgramDomain.name == program_domain, ProgramDomain.slug == program_domain))
        if program_type:
            query = query.where(or_(Count.program_type == program_type, ProgramType.name == program_type, ProgramType.slug == program_type))

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
    deps.ensure_path_in_scope(current_user, count.path, detail="Count outside your scope")
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
    deps.ensure_path_in_scope(current_user, count.path, detail="Count outside your scope")
    
    updated_count = await crud_count.update(db, db_obj=count, obj_in=count_in)
    
    # CRUD recalculates and commits the derived total in the same transaction.
    
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
    """
    Batch submit counts (offline sync convenience).

    Performance changes:
    - All client_id duplicates are resolved in a single WHERE IN query
      before the loop — was one DB round-trip per item.
    - All unique location IDs are scope-validated in a single batch call
      before the loop — was one DB round-trip per item.
    - Items for out-of-scope locations are rejected immediately without
      attempting an insert.
    """
    from sqlalchemy import select as _select
    from app.models.counts import Count as _Count
    from app.models.location import Location

    sync_result = SyncResult()
    details = []

    if not items:
        return sync_result
    if any(item.client_id is None for item in items):
        raise HTTPException(status_code=422, detail="Every count batch item requires a stable client_id")

    # ── 1. Pre-fetch existing client_ids in ONE query ─────────────────────
    client_ids_in = [i.client_id for i in items if i.client_id]
    existing_by_client_id: dict = {}
    if client_ids_in:
        rows = (await db.execute(
            _select(_Count.client_id, _Count.id).where(
                _Count.client_id.in_(client_ids_in)
            )
        )).all()
        existing_by_client_id = {str(row.client_id): str(row.id) for row in rows}

    # ── 2. Pre-validate all unique location IDs in scope ─────────────────
    unique_location_ids = {i.location_id for i in items}
    locations = (await db.execute(
        _select(Location.location_id, Location.path).where(
            Location.location_id.in_(unique_location_ids)
        )
    )).all()
    valid_location_ids: set = set()
    for loc in locations:
        try:
            deps.ensure_path_in_scope(
                current_user, loc.path, detail="Count location outside your scope"
            )
            valid_location_ids.add(str(loc.location_id))
        except Exception:
            pass  # location is out of scope — will be caught per item below

    # ── 3. Process items — only CRUD inserts remain in the loop ──────────
    for item in items:
        client_id_str = str(item.client_id) if item.client_id else None
        try:
            # Validate the submitted location before any idempotency lookup so
            # guessed client IDs cannot reveal records from another scope.
            if str(item.location_id) not in valid_location_ids:
                sync_result.errors += 1
                details.append({
                    "client_id": client_id_str,
                    "error": "Count location outside your scope",
                    "status": "error",
                })
                continue

            # Duplicate check (O(1) dict lookup, not a DB call)
            if client_id_str and client_id_str in existing_by_client_id:
                existing = await crud_count.get_by_client_id(db, client_id=item.client_id)
                if existing is None:
                    existing_by_client_id.pop(client_id_str, None)
                else:
                    try:
                        deps.ensure_path_in_scope(current_user, existing.path, detail="Existing count is outside your scope")
                    except HTTPException:
                        sync_result.errors += 1
                        details.append({"client_id": client_id_str, "error": "Existing count is outside your scope", "status": "error"})
                        continue
                    sync_result.duplicates += 1
                    details.append({
                        "client_id": client_id_str,
                        "id": str(existing.id),
                        "status": "duplicate",
                    })
                    continue

            # The only remaining DB call per item is the actual insert
            created = await crud_count.create(db, obj_in=item, user_id=current_user.user_id)
            if getattr(created, "_was_duplicate_submission", False):
                deps.ensure_path_in_scope(current_user, created.path, detail="Existing count is outside your scope")
                sync_result.duplicates += 1
                status_value = "duplicate"
            else:
                sync_result.synced += 1
                status_value = "synced"
            details.append({
                "client_id": client_id_str,
                "id": str(created.id),
                "status": status_value,
            })
        except HTTPException as exc:
            await db.rollback()
            sync_result.errors += 1
            details.append({
                "client_id": client_id_str,
                "error": exc.detail,
                "status": "error",
            })
        except Exception as exc:
            await db.rollback()
            sync_result.errors += 1
            details.append({
                "client_id": client_id_str,
                "error": str(exc),
                "status": "error",
            })

    sync_result.details = details
    return sync_result


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
    scope_path = deps.effective_scope_path(current_user)
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
    deps.ensure_path_in_scope(current_user, count.path, detail="Count outside your scope")
    
    await crud_count.update(
        db,
        db_obj=count,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.now(timezone.utc)}
    )
    return None
