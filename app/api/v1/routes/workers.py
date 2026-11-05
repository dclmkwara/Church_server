"""
Worker management API routes.

This module handles church worker registration and management. Workers are
the primary entity that must exist before user accounts can be created.

Key concepts:
- Workers represent all church members who serve in any capacity
- Workers MUST belong to a location (foreign key enforced)
- Workers can exist without user accounts (not all workers need app access)
- User accounts are created separately and linked to workers

All operations respect hierarchical scope based on the current user's role.
"""
from typing import Any, List, Optional
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.api import deps
from app.db.filters import scope_filter
from app.crud.crud_worker import worker as crud_worker
from app.schemas.user import WorkerCreate, WorkerResponse, WorkerUpdate
from app.models.user import Worker, User
from app.models.approvals import StatusChangeRequest

router = APIRouter()


async def _get_worker_or_404(db: AsyncSession, worker_id: UUID) -> Worker:
    """Fetch a Worker by UUID or raise HTTP 404."""
    result = await db.execute(select(Worker).where(Worker.worker_id == worker_id))
    worker = result.scalars().first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    return worker


@router.get(
    "/",
    response_model=List[WorkerResponse],
    dependencies=[Depends(deps.PermissionChecker("workers:read"))],
)
async def read_workers(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path (must be within your permissions)"),
) -> Any:
    """
    Retrieve workers with hierarchical scope filtering.
    
    Returns workers within the current user's scope. Admins with higher
    scores can see workers across broader hierarchies.
    
    Args:
        db: Database session dependency
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        current_user: Currently authenticated user
        scope_path: Optional custom scope path (defaults to current user's scope)
        
    Returns:
        List[WorkerResponse]: List of workers within scope
        
    Example:
        ```python
        # Get all workers in my scope
        GET /api/v1/workers/
        
        # Get workers with custom scope
        GET /api/v1/workers/?scope_path=org.234.KW
        
        # Pagination
        GET /api/v1/workers/?skip=0&limit=100
        ```
        
    Notes:
        - Uses ltree for efficient hierarchical filtering
        - Scope defaults to current user's path if not specified
        - Results limited by user's role score
        - Workers include location information (denormalized)
    """
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    
    workers = await crud_worker.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )
    return deps.filter_rows_in_scope(workers, current_user)


@router.get(
    "/search",
    response_model=List[WorkerResponse],
    dependencies=[Depends(deps.PermissionChecker("workers:read"))],
)
async def search_workers(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
    user_id: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    name: Optional[str] = None,
    unit: Optional[str] = None,
    gender: Optional[str] = None,
    status: Optional[str] = None,
    location_id: Optional[str] = None,
) -> Any:
    """Search workers with optional filters."""
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    query = select(Worker).where(
        scope_filter(Worker.path, search_scope),
        Worker.is_deleted == False,
    )
    if user_id:
        query = query.where(Worker.user_id == user_id)
    if phone:
        query = query.where(Worker.phone == phone)
    if email:
        query = query.where(Worker.email == email)
    if name:
        query = query.where(Worker.name.ilike(f"%{name}%"))
    if unit:
        query = query.where(Worker.unit.ilike(f"%{unit}%"))
    if gender:
        query = query.where(Worker.gender == gender)
    if status:
        query = query.where(Worker.status == status)
    if location_id:
        query = query.where(Worker.location_id == location_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return deps.filter_rows_in_scope(result.scalars().all(), current_user)


@router.get(
    "/pending",
    response_model=List[WorkerResponse],
    dependencies=[Depends(deps.PermissionChecker("workers:approve"))],
)
async def list_pending_workers(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """List pending worker registrations within scope."""
    if deps.highest_role_score(current_user) < 3:
        raise HTTPException(status_code=403, detail="Group Pastor approval is required to review registrations")
    search_scope = deps.resolve_scope_path(current_user, scope_path)
    query = select(Worker).where(
        Worker.approval_status == "pending_verification",
        scope_filter(Worker.path, search_scope),
        Worker.is_deleted == False,
    ).offset(skip).limit(limit)
    result = await db.execute(query)
    return deps.filter_rows_in_scope(result.scalars().all(), current_user)


@router.post(
    "/",
    response_model=WorkerResponse,
    dependencies=[Depends(deps.PermissionChecker("workers:create"))],
)
async def create_worker(
    *,
    db: AsyncSession = Depends(deps.get_db),
    worker_in: WorkerCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Register a new church worker.
    
    Creates a worker record with required location assignment. This is the
    first step before a worker can request user account access.
    
    Args:
        db: Database session dependency
        worker_in: Worker registration data (location_id, name, phone, email, etc.)
        current_user: Currently authenticated user
        
    Returns:
        WorkerResponse: Created worker with auto-generated worker_id and user_id
        
    Raises:
        HTTPException 400: Phone number or email already exists
        HTTPException 404: Location not found (foreign key constraint)
        
    Example:
        ```python
        POST /api/v1/workers/
        {
            "location_id": "9d4ff678-4284-4798-b438-d8a7f54a8351",
            "location_name": "DLCF Living Spring",
            "church_type": "DLCF",
            "state": "Kwara",
            "region": "Ilorin Region",
            "group": "Ilorin East",
            "name": "John Doe",
            "gender": "Male",
            "phone": "+2349012345678",
            "email": "john@example.com",
            "unit": "Ushering",
            "status": "Active"
        }
        
        Response:
        {
            "worker_id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "W001",
            ...
        }
        ```
        
    Notes:
        - Phone and email must be unique
        - Location must exist (foreign key enforced)
        - worker_id (UUID) is auto-generated
        - user_id (string) is auto-generated (e.g., W001, W002)
        - Worker can request user account after registration
    """
    await deps.get_location_in_scope(
        db, current_user=current_user, location_id=worker_in.location_id,
        detail="You can only create workers within your scope",
    )
    if deps.highest_role_score(current_user) != 2 or not any(role.role_name == "Location Pastor" for role in (current_user.roles or [])):
        raise HTTPException(status_code=403, detail="Worker registration is initiated by the Location Pastor")
    if str(worker_in.location_id) != str(current_user.location_id):
        raise HTTPException(status_code=403, detail="Location Pastors may register workers only at their assigned location")
    try:
        worker = await crud_worker.create(db, obj_in=worker_in)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="A worker with this phone number or email already exists.",
        )
    return worker


@router.get(
    "/{worker_id}",
    response_model=WorkerResponse,
    dependencies=[Depends(deps.PermissionChecker("workers:read"))],
)
async def read_worker_by_id(
    worker_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get a specific worker by UUID.
    
    Args:
        worker_id: Worker's UUID (not the user_id string)
        db: Database session dependency
        current_user: Currently authenticated user
        
    Returns:
        WorkerResponse: Worker details
        
    Raises:
        HTTPException 404: Worker not found
        HTTPException 403: Worker outside current user's scope
        
    Example:
        ```python
        GET /api/v1/workers/550e8400-e29b-41d4-a716-446655440000
        ```
        
    Notes:
        - Uses worker_id (UUID), not the user_id (string like "W001")
        - Validates worker is within current user's scope
    """
    worker = await _get_worker_or_404(db, worker_id)
    deps.ensure_path_in_scope(current_user, worker.path, detail="Worker outside your scope")
    return worker


@router.put(
    "/{worker_id}",
    response_model=WorkerResponse,
    dependencies=[Depends(deps.PermissionChecker("workers:update"))],
)
async def update_worker(
    *,
    db: AsyncSession = Depends(deps.get_db),
    worker_id: UUID,
    worker_in: WorkerUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Update an existing worker's information.
    
    Allows updating worker details including location transfer. All fields
    are optional (partial update).
    
    Args:
        db: Database session dependency
        worker_id: Worker's UUID
        worker_in: Update data (all fields optional)
        current_user: Currently authenticated user
        
    Returns:
        WorkerResponse: Updated worker
        
    Raises:
        HTTPException 404: Worker not found
        HTTPException 403: Worker outside current user's scope
        HTTPException 400: Invalid location_id (if updating location)
        
    Example:
        ```python
        PUT /api/v1/workers/550e8400-e29b-41d4-a716-446655440000
        {
            "location_id": "002",  # Transfer to new location
            "status": "Inactive",
            "unit": "Choir"
        }
        ```
        
    Notes:
        - Only provided fields are updated
        - Updating location_id transfers the worker
        - Phone and email must remain unique
        - Cannot update worker outside your scope
    """
    worker = await _get_worker_or_404(db, worker_id)
    deps.ensure_path_in_scope(current_user, worker.path, detail="Worker outside your scope")
    update_data = worker_in.model_dump(exclude_unset=True)
    if "status" in update_data or "approval_status" in update_data:
        raise HTTPException(status_code=403, detail="Worker status changes require the approval workflow")
    if "location_id" in update_data and update_data["location_id"] != str(worker.location_id):
        raise HTTPException(status_code=403, detail="Worker transfers must use the transfer workflow")
    if not any(role.role_name in {"Location Pastor", "Location Admin"} for role in (current_user.roles or [])):
        raise HTTPException(status_code=403, detail="Worker profile edits are limited to location administrators")
    worker = await crud_worker.update(db, db_obj=worker, obj_in=worker_in)
    return worker


@router.post(
    "/{worker_id}/approve",
    response_model=WorkerResponse,
    dependencies=[Depends(deps.PermissionChecker("workers:approve"))],
)
async def approve_worker_registration(
    *,
    db: AsyncSession = Depends(deps.get_db),
    worker_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Approve a pending worker registration."""
    worker = await _get_worker_or_404(db, worker_id)
    deps.ensure_path_in_scope(current_user, worker.path, detail="Worker outside your scope")
    if deps.highest_role_score(current_user) < 3:
        raise HTTPException(status_code=403, detail="Group Pastor approval is required for worker registration")
    if worker.approval_status != "pending_verification":
        raise HTTPException(status_code=400, detail=f"Worker is already {worker.approval_status}")
    worker.approval_status = "approved"
    worker.status = "Active"
    worker.approved_by = current_user.user_id
    worker.approved_at = datetime.now(timezone.utc)
    worker.rejection_reason = None
    await db.commit()
    await db.refresh(worker)
    return worker


@router.post(
    "/{worker_id}/reject",
    response_model=WorkerResponse,
    dependencies=[Depends(deps.PermissionChecker("workers:approve"))],
)
async def reject_worker_registration(
    *,
    db: AsyncSession = Depends(deps.get_db),
    worker_id: UUID,
    reason: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Reject a pending worker registration."""
    if not reason or len(reason.strip()) < 10:
        raise HTTPException(status_code=400, detail="Rejection reason must be at least 10 characters")

    worker = await _get_worker_or_404(db, worker_id)
    deps.ensure_path_in_scope(current_user, worker.path, detail="Worker outside your scope")
    if deps.highest_role_score(current_user) < 3:
        raise HTTPException(status_code=403, detail="Group Pastor review is required for worker registration")
    if worker.approval_status != "pending_verification":
        raise HTTPException(status_code=400, detail=f"Worker is already {worker.approval_status}")
    worker.approval_status = "rejected"
    worker.status = "Rejected"
    worker.rejection_reason = reason
    worker.approved_by = current_user.user_id
    worker.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(worker)
    return worker


@router.post(
    "/{worker_id}/suspend",
    response_model=WorkerResponse,
    dependencies=[Depends(deps.PermissionChecker("workers:update"))],
)
async def suspend_worker(
    *,
    db: AsyncSession = Depends(deps.get_db),
    worker_id: UUID,
    note: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Allow the assigned Location Pastor to suspend a worker pending review."""
    if deps.highest_role_score(current_user) < 2:
        raise HTTPException(status_code=403, detail="Location Pastor or higher authority is required to suspend a worker")
    worker = await _get_worker_or_404(db, worker_id)
    deps.ensure_path_in_scope(current_user, worker.path, detail="Worker outside your scope")
    if worker.is_deleted or worker.approval_status != "approved" or str(worker.status or "").lower() != "active":
        raise HTTPException(status_code=400, detail="Only an active approved worker can be suspended")
    if str(worker.status or "").lower() == "suspended":
        raise HTTPException(status_code=400, detail="Worker is already suspended")
    if note and len(note.strip()) < 10:
        raise HTTPException(status_code=400, detail="Suspension note must be at least 10 characters")
    now = datetime.now(timezone.utc)
    db.add(StatusChangeRequest(
        worker_id=worker.worker_id,
        old_status=worker.status,
        new_status="Suspended",
        status="approved",
        reason=note.strip() if note else "Suspended by the assigned Location Pastor",
        requested_by=current_user.user_id,
        approved_by=current_user.user_id,
        approved_at=now,
        path=worker.path,
    ))
    worker.status = "Suspended"
    linked_user = (await db.execute(select(User).where(
        User.worker_id == worker.worker_id, User.is_deleted.is_(False)
    ))).scalars().first()
    if linked_user:
        linked_user.is_active = False
        from app.core.auth_cache import invalidate_user_cache
        invalidate_user_cache(str(linked_user.user_id))
    await db.commit()
    await db.refresh(worker)
    return worker


@router.delete(
    "/{worker_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("workers:delete"))],
)
async def delete_worker(
    *,
    db: AsyncSession = Depends(deps.get_db),
    worker_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Soft delete a worker."""
    if deps.highest_role_score(current_user) < 3:
        raise HTTPException(status_code=403, detail="Group Pastor approval or higher is required to remove a worker")
    worker = await _get_worker_or_404(db, worker_id)
    deps.ensure_path_in_scope(current_user, worker.path, detail="Worker outside your scope")
    linked_user_result = await db.execute(
        select(User).where(User.worker_id == worker.worker_id, User.is_deleted.is_(False))
    )
    linked_user = linked_user_result.scalars().first()
    now = datetime.now(timezone.utc)
    await crud_worker.update(db, db_obj=worker, obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": now})
    if linked_user:
        from app.crud.crud_user import user as crud_user
        await crud_user.update(db, db_obj=linked_user, obj_in={"is_deleted": True, "operation": "DELETE", "last_modify": now})
    return None
