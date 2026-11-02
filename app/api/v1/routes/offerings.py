"""
Offering submission and retrieval routes.
"""
from typing import Any, List
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.db.filters import scope_filter
from app.crud.crud_offerings import offering as crud_offering
from app.schemas.offerings import OfferingCreate, OfferingResponse, OfferingUpdate, OfferingCorrection, OfferingReview, OfferingReversal
from app.schemas.sync import SyncResult
from sqlalchemy import select, func, text
from datetime import date
from decimal import Decimal
from app.models.user import User

router = APIRouter()


@router.post(
    "/",
    response_model=OfferingResponse,
    dependencies=[Depends(deps.PermissionChecker("offerings:create"))],
)
async def create_offering(
    *,
    db: AsyncSession = Depends(deps.get_db),
    offering_in: OfferingCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit a new offering/tithe record."""
    await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=offering_in.location_id,
        detail="Offering location outside your scope",
    )
    created = await crud_offering.create(db, obj_in=offering_in, user_id=current_user.user_id)
    deps.ensure_path_in_scope(current_user, created.path, detail="Existing offering is outside your scope")
    try:
        from app.api.v1.routes.websocket import manager
        import json
        await manager.broadcast(json.dumps({"type": "offering_created", "data": {"id": str(created.id), "location_id": created.location_id}}))
    except Exception:
        pass
    return created


@router.get(
    "/",
    response_model=List[OfferingResponse],
    dependencies=[Depends(deps.PermissionChecker("offerings:read"))],
)
async def read_offerings(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
    fund_type: str = Query(None, description="offering, tithe, seed, etc."),
    location_id: str = Query(None, description="Filter by location id"),
    start_date: date = Query(None, description="Filter start date"),
    end_date: date = Query(None, description="Filter end date"),
    amount: Decimal = Query(None, description="Filter by exact amount"),
) -> Any:
    """Retrieve offerings with scope filtering."""
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    rows = await crud_offering.get_multi_by_scope(
        db,
        scope_path=search_scope,
        fund_type=fund_type,
        location_id=location_id,
        start_date=start_date,
        end_date=end_date,
        amount=amount,
        skip=skip,
        limit=limit,
    )
    return deps.filter_rows_in_scope(rows, current_user)


@router.get(
    "/{offering_id}",
    response_model=OfferingResponse,
    dependencies=[Depends(deps.PermissionChecker("offerings:read"))],
)
async def read_offering(
    *,
    db: AsyncSession = Depends(deps.get_db),
    offering_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a specific offering by ID."""
    offering = await crud_offering.get(db, id=offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    deps.ensure_path_in_scope(current_user, offering.path, detail="Offering outside your scope")
    return offering


@router.put(
    "/{offering_id}",
    response_model=OfferingResponse,
    dependencies=[Depends(deps.PermissionChecker("offerings:update"))],
)
async def update_offering(
    *,
    db: AsyncSession = Depends(deps.get_db),
    offering_id: UUID,
    offering_in: OfferingUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update an offering record."""
    offering = await crud_offering.get(db, id=offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail="Offering not found")
    deps.ensure_path_in_scope(current_user, offering.path, detail="Offering outside your scope")
    
    return await crud_offering.update(db, db_obj=offering, obj_in=offering_in)


@router.post(
    "/{offering_id}/corrections",
    response_model=OfferingResponse,
    dependencies=[Depends(deps.PermissionChecker("offerings:update"))],
)
async def correct_offering(
    *, db: AsyncSession = Depends(deps.get_db), offering_id: UUID,
    correction: OfferingCorrection,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return await crud_offering.correct(
        db, offering_id=offering_id, correction=correction,
        actor_id=current_user.user_id, scope_path=deps.effective_scope_path(current_user),
    )


@router.post(
    "/{offering_id}/review",
    response_model=OfferingResponse,
    dependencies=[Depends(deps.PermissionChecker("offerings:review"))],
)
async def review_offering(
    *, db: AsyncSession = Depends(deps.get_db), offering_id: UUID,
    decision: str = Query(..., pattern="^(approved|rejected)$"),
    payload: OfferingReview = OfferingReview(),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return await crud_offering.review(
        db, offering_id=offering_id, actor_id=current_user.user_id,
        scope_path=deps.effective_scope_path(current_user), decision=decision,
        note=payload.note,
    )


@router.post(
    "/{offering_id}/reverse",
    response_model=OfferingResponse,
    dependencies=[Depends(deps.PermissionChecker("offerings:update"))],
)
async def reverse_offering(
    *, db: AsyncSession = Depends(deps.get_db), offering_id: UUID,
    reversal: OfferingReversal,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return await crud_offering.reverse(
        db, offering_id=offering_id, actor_id=current_user.user_id,
        scope_path=deps.effective_scope_path(current_user), reason=reversal.reason,
    )


@router.get(
    "/{offering_id}/audit",
    dependencies=[Depends(deps.PermissionChecker("offerings:read"))],
)
async def offering_audit_history(
    *, db: AsyncSession = Depends(deps.get_db), offering_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    row = await crud_offering.get(db, id=offering_id)
    if not row:
        raise HTTPException(status_code=404, detail="Offering not found")
    deps.ensure_path_in_scope(current_user, row.path, detail="Offering outside your scope")
    entries = await crud_offering.audit_history(
        db, offering_id=offering_id, scope_path=deps.effective_scope_path(current_user),
    )
    return [{
        "id": item.id, "action": item.action, "reason": item.reason,
        "actor_id": item.actor_id, "created_at": item.created_at,
        "before": item.before_values, "after": item.after_values,
    } for item in entries]


@router.post(
    "/batch",
    response_model=SyncResult,
    dependencies=[Depends(deps.PermissionChecker("offerings:create"))],
)
async def batch_create_offerings(
    *,
    db: AsyncSession = Depends(deps.get_db),
    items: List[OfferingCreate],
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Batch submit offerings (offline sync convenience)."""
    if any(item.client_id is None for item in items):
        raise HTTPException(status_code=422, detail="Every offering batch item requires a stable client_id")
    result = SyncResult()
    details = []
    for item in items:
        try:
            location = await deps.get_location_in_scope(
                db, current_user=current_user, location_id=item.location_id,
                detail="Offering location outside your scope",
            )
            existing = None
            if item.client_id:
                existing = await crud_offering.get_by_client_id(db, client_id=item.client_id)
            if existing:
                deps.ensure_path_in_scope(current_user, existing.path, detail="Existing offering is outside your scope")
                result.duplicates += 1
                details.append({"client_id": item.client_id, "id": existing.id, "status": "duplicate"})
                continue
            created = await crud_offering.create(db, obj_in=item, user_id=current_user.user_id)
            is_duplicate = bool(getattr(created, "_was_duplicate_submission", False))
            deps.ensure_path_in_scope(current_user, created.path, detail="Existing offering is outside your scope")
            result.duplicates += int(is_duplicate)
            result.synced += int(not is_duplicate)
            details.append({"client_id": item.client_id, "id": created.id, "status": "duplicate" if is_duplicate else "synced"})
        except Exception as e:
            await db.rollback()
            result.errors += 1
            details.append({"client_id": item.client_id, "error": str(e), "status": "error"})
    result.details = details
    return result


@router.get(
    "/stats",
    dependencies=[Depends(deps.PermissionChecker("offerings:read"))],
)
async def get_offering_stats(
    start_date: date = None,
    end_date: date = None,
    fund_type: str = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return aggregate offering stats within scope and date range."""
    scope_path = deps.effective_scope_path(current_user)
    from app.models.offerings import Offering
    query = select(
        func.count(Offering.id).label("count"),
        func.coalesce(func.sum(Offering.amount), 0).label("total_amount")
    ).where(
        scope_filter(Offering.path, scope_path),
        Offering.is_deleted == False,
        Offering.status == "approved",
    )
    if start_date:
        query = query.where(Offering.date >= start_date)
    if end_date:
        from datetime import timedelta
        query = query.where(Offering.date < end_date + timedelta(days=1))
    if fund_type:
        query = query.where(Offering.fund_type == fund_type)
    result = await db.execute(query)
    row = result.first()
    return {"count": row.count if row else 0, "total_amount": str(row.total_amount if row else 0)}


@router.delete(
    "/{offering_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("offerings:delete"))],
)
async def delete_offering(
    *,
    db: AsyncSession = Depends(deps.get_db),
    offering_id: UUID,
    reason: str = Query(..., min_length=20, max_length=1000),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete an offering record."""
    await crud_offering.soft_delete(db, offering_id=offering_id, actor_id=current_user.user_id,
        scope_path=deps.effective_scope_path(current_user), reason=reason)
    return None
