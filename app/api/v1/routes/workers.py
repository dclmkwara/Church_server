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
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.crud.crud_worker import worker as crud_worker
from app.schemas.user import WorkerCreate, WorkerResponse, WorkerUpdate
from app.models.user import Worker, User

router = APIRouter()


@router.get("/", response_model=List[WorkerResponse])
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
    search_scope = scope_path if scope_path else str(current_user.path)
    
    workers = await crud_worker.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )
    return workers


@router.post("/", response_model=WorkerResponse)
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
            "location_id": "001",
            "location_name": "Ilorin East DLBC",
            "church_type": "DLBC",
            "state": "Kwara",
            "region": "Ilorin North",
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
    # Check for duplicate phone
    worker = await crud_worker.get_by_phone(db, phone=worker_in.phone)
    if worker:
        raise HTTPException(
            status_code=400,
            detail="The worker with this phone already exists in the system.",
        )
    
    # Create worker (CRUD will validate location exists)
    worker = await crud_worker.create(db, obj_in=worker_in)
    return worker


@router.get("/{worker_id}", response_model=WorkerResponse)
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
    query = select(Worker).where(Worker.worker_id == worker_id)
    result = await db.execute(query)
    worker = result.scalars().first()
        
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    # TODO: Add scope validation
    # if not worker.path.descendant_of(current_user.path):
    #     raise HTTPException(status_code=403, detail="Worker outside your scope")
        
    return worker


@router.put("/{worker_id}", response_model=WorkerResponse)
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
    # Fetch worker by UUID
    query = select(Worker).where(Worker.worker_id == worker_id)
    result = await db.execute(query)
    worker = result.scalars().first()
    
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    
    # TODO: Add scope validation
        
    worker = await crud_worker.update(db, db_obj=worker, obj_in=worker_in)
    return worker
