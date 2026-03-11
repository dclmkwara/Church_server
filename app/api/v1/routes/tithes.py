"""
Tithe routes (specialized Offering endpoints).
"""
from typing import Any, List
from datetime import datetime, date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_offerings import offering as crud_offering
from app.schemas.offerings import OfferingCreate, OfferingResponse, OfferingUpdate
from app.schemas.sync import SyncResult
from sqlalchemy import select, func, text
from app.models.user import User

router = APIRouter()


def _force_tithe(obj: OfferingCreate) -> OfferingCreate:
    return obj.model_copy(update={"fund_type": "tithe"})


@router.post(
    "/",
    response_model=OfferingResponse,
    dependencies=[Depends(deps.PermissionChecker("offerings:create"))],
)
async def create_tithe(
    *,
    db: AsyncSession = Depends(deps.get_db),
    tithe_in: OfferingCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Submit a new tithe record."""
    created = await crud_offering.create(
        db, obj_in=_force_tithe(tithe_in), user_id=current_user.user_id
    )
    return created


@router.get(
    "/",
    response_model=List[OfferingResponse],
    dependencies=[Depends(deps.PermissionChecker("offerings:read"))],
)
async def read_tithes(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
    location_id: str = Query(None, description="Filter by location id"),
    start_date: date = Query(None, description="Filter start date"),
    end_date: date = Query(None, description="Filter end date"),
    amount: float = Query(None, description="Filter by exact amount"),
) -> Any:
    """Retrieve tithes with scope filtering."""
    search_scope = scope_path if scope_path else str(current_user.path)
    return await crud_offering.get_multi_by_scope(
        db,
        scope_path=search_scope,
        fund_type="tithe",
        location_id=location_id,
        start_date=start_date,
        end_date=end_date,
        amount=amount,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{tithe_id}",
    response_model=OfferingResponse,
    dependencies=[Depends(deps.PermissionChecker("offerings:read"))],
)
async def read_tithe(
    *,
    db: AsyncSession = Depends(deps.get_db),
    tithe_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a specific tithe by ID."""
    tithe = await crud_offering.get(db, id=tithe_id)
    if not tithe or tithe.fund_type != "tithe":
        raise HTTPException(status_code=404, detail="Tithe not found")
    return tithe


@router.put(
    "/{tithe_id}",
    response_model=OfferingResponse,
    dependencies=[Depends(deps.PermissionChecker("offerings:update"))],
)
async def update_tithe(
    *,
    db: AsyncSession = Depends(deps.get_db),
    tithe_id: UUID,
    tithe_in: OfferingUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a tithe record."""
    tithe = await crud_offering.get(db, id=tithe_id)
    if not tithe or tithe.fund_type != "tithe":
        raise HTTPException(status_code=404, detail="Tithe not found")
    if tithe_in.fund_type and tithe_in.fund_type != "tithe":
        raise HTTPException(status_code=400, detail="fund_type must be tithe for this endpoint")
    tithe_in = tithe_in.model_copy(update={"fund_type": "tithe"})
    return await crud_offering.update(db, db_obj=tithe, obj_in=tithe_in)


@router.post(
    "/batch",
    response_model=SyncResult,
    dependencies=[Depends(deps.PermissionChecker("offerings:create"))],
)
async def batch_create_tithes(
    *,
    db: AsyncSession = Depends(deps.get_db),
    items: List[OfferingCreate],
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Batch submit tithes (offline sync convenience)."""
    result = SyncResult()
    details = []
    for item in items:
        try:
            item = _force_tithe(item)
            existing = None
            if item.client_id:
                existing = await crud_offering.get_by_client_id(db, client_id=item.client_id)
            if existing:
                result.duplicates += 1
                details.append({"client_id": item.client_id, "id": existing.id, "status": "duplicate"})
                continue
            created = await crud_offering.create(db, obj_in=item, user_id=current_user.user_id)
            result.synced += 1
            details.append({"client_id": item.client_id, "id": created.id, "status": "synced"})
        except Exception as e:
            result.errors += 1
            details.append({"client_id": item.client_id, "error": str(e), "status": "error"})
    result.details = details
    return result


@router.get(
    "/stats",
    dependencies=[Depends(deps.PermissionChecker("offerings:read"))],
)
async def get_tithe_stats(
    start_date: date = None,
    end_date: date = None,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return aggregate tithe stats within scope and date range."""
    scope_path = str(current_user.path)
    from app.models.offerings import Offering
    query = select(
        func.count(Offering.id).label("count"),
        func.coalesce(func.sum(Offering.amount), 0).label("total_amount")
    ).where(
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path),
        Offering.fund_type == "tithe"
    )
    if start_date:
        query = query.where(Offering.date >= start_date)
    if end_date:
        query = query.where(Offering.date <= end_date)
    result = await db.execute(query)
    row = result.first()
    return {"count": row.count if row else 0, "total_amount": str(row.total_amount if row else 0)}


@router.delete(
    "/{tithe_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("offerings:delete"))],
)
async def delete_tithe(
    *,
    db: AsyncSession = Depends(deps.get_db),
    tithe_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a tithe record."""
    tithe = await crud_offering.get(db, id=tithe_id)
    if not tithe or tithe.fund_type != "tithe":
        raise HTTPException(status_code=404, detail="Tithe not found")
    await crud_offering.update(
        db,
        db_obj=tithe,
        obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": datetime.utcnow()}
    )
    return None
