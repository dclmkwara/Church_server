"""
Hierarchy management API routes.

This module provides CRUD operations for the church organizational hierarchy:
- Nations (root level)
- States (under nations)
- Regions (under states)
- Groups (under regions)
- Locations (under groups)
- Fellowships (leaf level)

The hierarchy uses PostgreSQL ltree for efficient path-based queries and
automatic path generation. Each level automatically inherits and extends
the path from its parent.

Example hierarchy path:
    org.234.KW.ILN.ILE.001.F001
    └── Nation: 234 (Nigeria)
        └── State: KW (Kwara)
            └── Region: ILN (Ilorin North)
                └── Group: ILE (Ilorin East)
                    └── Location: 001
                        └── Fellowship: F001
"""
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select

from app.api import deps
from app.crud import crud_location
from app.schemas import location as schemas
from app.models.user import User
from app.models.location import Fellowship, Location, Group, Nation, Region, State

router = APIRouter()


def _ensure_hierarchy_visible(current_user: User, node: Any, *, detail: str = "Hierarchy node outside your scope") -> None:
    node_path = getattr(node, "path", None)
    if not (
        deps.path_in_scope(current_user.path, node_path)
        or deps.path_in_scope(node_path, current_user.path)
    ):
        raise HTTPException(status_code=403, detail=detail)


def _ensure_hierarchy_mutable(current_user: User, node: Any, *, detail: str = "Hierarchy node outside your scope") -> None:
    deps.ensure_path_in_scope(current_user, getattr(node, "path", None), detail=detail)


def _hierarchy_visible_filter(path_column: Any, current_user: User):
    scope = str(current_user.path)
    return or_(path_column.op("<@")(scope), path_column.op("@>")(scope))


# =============================================================================
# NATION ROUTES (Root Level)
# =============================================================================

@router.post(
    "/nations/",
    response_model=schemas.NationResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:create_nation"))],
)
async def create_nation(
    *,
    db: AsyncSession = Depends(deps.get_db),
    nation_in: schemas.NationCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new nation (root level of hierarchy).
    
    Nations are the top-level organizational unit, typically representing
    countries. The system automatically generates the ltree path as 'org.{nation_id}'.
    
    Args:
        db: Database session dependency
        nation_in: Nation creation data (nation_id, continent, country_name, etc.)
        current_user: Currently authenticated user
        
    Returns:
        NationResponse: Created nation with auto-generated path and formatted_id
        
    Raises:
        HTTPException 400: Nation ID already exists
        HTTPException 401: User not authenticated
        
    Example:
        ```python
        POST /api/v1/nations/
        {
            "nation_id": "234",
            "continent": "Africa",
            "country_name": "Nigeria",
            "capital": "Abuja",
            "national_pastor": "Pastor John Doe"
        }
        
        Response:
        {
            "nation_id": "234",
            "path": "org.234",
            "formatted_id": "DCM-234",
            ...
        }
        ```
        
    Notes:
        - Path is auto-generated (do NOT provide in request)
        - Nation ID should be unique (e.g., country code)
        - Permission enforced via PermissionChecker ("hierarchy:create_nation")
    """
    return await crud_location.nation.create(db=db, obj_in=nation_in)


@router.get("/nations/", response_model=List[schemas.NationResponse])
async def read_nations(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve all nations with pagination.
    
    Args:
        db: Database session dependency
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        current_user: Currently authenticated user
        
    Returns:
        List[NationResponse]: List of nations with their paths and metadata
        
    Example:
        ```python
        GET /api/v1/nations/?skip=0&limit=50
        ```
        
    Notes:
        - Results are not filtered by scope (all nations visible)
        - Consider adding scope filtering for large deployments
    """
    result = await db.execute(
        select(Nation)
        .where(_hierarchy_visible_filter(Nation.path, current_user))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/nations/{nation_id}", response_model=schemas.NationResponse)
async def read_nation(
    *,
    db: AsyncSession = Depends(deps.get_db),
    nation_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get a specific nation by ID.
    
    Args:
        db: Database session dependency
        nation_id: Unique nation identifier (e.g., "234")
        current_user: Currently authenticated user
        
    Returns:
        NationResponse: Nation details with path and formatted_id
        
    Raises:
        HTTPException 404: Nation not found
        
    Example:
        ```python
        GET /api/v1/nations/234
        ```
    """
    node = await crud_location.nation.get(db=db, id=nation_id)
    if not node:
        raise HTTPException(status_code=404, detail="Nation not found")
    _ensure_hierarchy_visible(current_user, node, detail="Nation outside your scope")
    return node


@router.put(
    "/nations/{nation_id}",
    response_model=schemas.NationResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:update"))],
)
async def update_nation(
    *,
    db: AsyncSession = Depends(deps.get_db),
    nation_id: str,
    nation_in: schemas.NationUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a nation."""
    node = await crud_location.nation.get(db=db, id=nation_id)
    if not node:
        raise HTTPException(status_code=404, detail="Nation not found")
    _ensure_hierarchy_mutable(current_user, node, detail="Nation outside your scope")
    return await crud_location.nation.update(db, db_obj=node, obj_in=nation_in)


@router.delete(
    "/nations/{nation_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:delete"))],
)
async def delete_nation(
    *,
    db: AsyncSession = Depends(deps.get_db),
    nation_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete a nation."""
    node = await crud_location.nation.get(db=db, id=nation_id)
    if not node:
        raise HTTPException(status_code=404, detail="Nation not found")
    _ensure_hierarchy_mutable(current_user, node, detail="Nation outside your scope")
    await crud_location.nation.remove(db, id=nation_id)
    return None


# =============================================================================
# STATE ROUTES
# =============================================================================

@router.post(
    "/states/",
    response_model=schemas.StateResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:create_state"))],
)
async def create_state(
    *,
    db: AsyncSession = Depends(deps.get_db),
    state_in: schemas.StateCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new state under an existing nation.
    
    States are the second level of hierarchy. The system validates that the
    parent nation exists and automatically generates the path by appending
    the state_id to the nation's path.
    
    Args:
        db: Database session dependency
        state_in: State creation data (state_id, nation_id, state_name, etc.)
        current_user: Currently authenticated user
        
    Returns:
        StateResponse: Created state with auto-generated path
        
    Raises:
        HTTPException 400: State ID already exists
        HTTPException 404: Parent nation not found
        
    Example:
        ```python
        POST /api/v1/states/
        {
            "state_id": "KW",
            "nation_id": "234",
            "state_name": "Kwara",
            "city": "Ilorin"
        }
        
        Response:
        {
            "state_id": "KW",
            "path": "org.234.KW",
            "formatted_id": "DCM-234-KW",
            ...
        }
        ```
        
    Notes:
        - Parent nation must exist before creating state
        - Path automatically generated as: nation.path + "." + state_id
    """
    return await crud_location.state.create(db=db, obj_in=state_in)


@router.get("/states/", response_model=List[schemas.StateResponse])
async def read_states(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve all states with pagination.
    
    Args:
        db: Database session dependency
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Currently authenticated user
        
    Returns:
        List[StateResponse]: List of states with paths
        
    Example:
        ```python
        GET /api/v1/states/?skip=0&limit=100
        ```
    """
    result = await db.execute(
        select(State)
        .where(_hierarchy_visible_filter(State.path, current_user))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/states/{state_id}", response_model=schemas.StateResponse)
async def read_state(
    *,
    db: AsyncSession = Depends(deps.get_db),
    state_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get a specific state by ID.
    
    Args:
        db: Database session dependency
        state_id: Unique state identifier (e.g., "KW")
        current_user: Currently authenticated user
        
    Returns:
        StateResponse: State details with path
        
    Raises:
        HTTPException 404: State not found
        
    Example:
        ```python
        GET /api/v1/states/KW
        ```
    """
    node = await crud_location.state.get(db=db, id=state_id)
    if not node:
        raise HTTPException(status_code=404, detail="State not found")
    _ensure_hierarchy_visible(current_user, node, detail="State outside your scope")
    return node


@router.put(
    "/states/{state_id}",
    response_model=schemas.StateResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:update_state"))],
)
async def update_state(
    *,
    db: AsyncSession = Depends(deps.get_db),
    state_id: str,
    state_in: schemas.StateUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a state."""
    node = await crud_location.state.get(db=db, id=state_id)
    if not node:
        raise HTTPException(status_code=404, detail="State not found")
    _ensure_hierarchy_mutable(current_user, node, detail="State outside your scope")
    return await crud_location.state.update(db, db_obj=node, obj_in=state_in)


@router.delete(
    "/states/{state_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:delete_state"))],
)
async def delete_state(
    *,
    db: AsyncSession = Depends(deps.get_db),
    state_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete a state."""
    node = await crud_location.state.get(db=db, id=state_id)
    if not node:
        raise HTTPException(status_code=404, detail="State not found")
    _ensure_hierarchy_mutable(current_user, node, detail="State outside your scope")
    await crud_location.state.remove(db, id=state_id)
    return None


# =============================================================================
# REGION ROUTES
# =============================================================================

@router.post(
    "/regions/",
    response_model=schemas.RegionResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:create_region"))],
)
async def create_region(
    *,
    db: AsyncSession = Depends(deps.get_db),
    region_in: schemas.RegionCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new region under an existing state.
    
    Regions are the third level of hierarchy. Path is auto-generated by
    appending region_id to the parent state's path.
    
    Args:
        db: Database session dependency
        region_in: Region creation data (region_id, state_id, region_name, etc.)
        current_user: Currently authenticated user
        
    Returns:
        RegionResponse: Created region with auto-generated path
        
    Raises:
        HTTPException 400: Region ID already exists
        HTTPException 404: Parent state not found
        
    Example:
        ```python
        POST /api/v1/regions/
        {
            "region_id": "ILN",
            "state_id": "KW",
            "region_name": "Ilorin North"
        }
        
        Response:
        {
            "region_id": "ILN",
            "path": "org.234.KW.ILN",
            "formatted_id": "DCM-234-KW-ILN",
            ...
        }
        ```
    """
    return await crud_location.region.create(db=db, obj_in=region_in)


@router.get("/regions/", response_model=List[schemas.RegionResponse])
async def read_regions(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve all regions with pagination.
    
    Args:
        db: Database session dependency
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Currently authenticated user
        
    Returns:
        List[RegionResponse]: List of regions with paths
    """
    result = await db.execute(
        select(Region)
        .where(_hierarchy_visible_filter(Region.path, current_user))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/regions/{region_id}", response_model=schemas.RegionResponse)
async def read_region(
    *,
    db: AsyncSession = Depends(deps.get_db),
    region_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get a specific region by ID.
    
    Args:
        db: Database session dependency
        region_id: Unique region identifier
        current_user: Currently authenticated user
        
    Returns:
        RegionResponse: Region details with path
        
    Raises:
        HTTPException 404: Region not found
    """
    node = await crud_location.region.get(db=db, id=region_id)
    if not node:
        raise HTTPException(status_code=404, detail="Region not found")
    _ensure_hierarchy_visible(current_user, node, detail="Region outside your scope")
    return node


@router.put(
    "/regions/{region_id}",
    response_model=schemas.RegionResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:update_region"))],
)
async def update_region(
    *,
    db: AsyncSession = Depends(deps.get_db),
    region_id: str,
    region_in: schemas.RegionUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a region."""
    node = await crud_location.region.get(db=db, id=region_id)
    if not node:
        raise HTTPException(status_code=404, detail="Region not found")
    _ensure_hierarchy_mutable(current_user, node, detail="Region outside your scope")
    return await crud_location.region.update(db, db_obj=node, obj_in=region_in)


@router.delete(
    "/regions/{region_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:delete_region"))],
)
async def delete_region(
    *,
    db: AsyncSession = Depends(deps.get_db),
    region_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete a region."""
    node = await crud_location.region.get(db=db, id=region_id)
    if not node:
        raise HTTPException(status_code=404, detail="Region not found")
    _ensure_hierarchy_mutable(current_user, node, detail="Region outside your scope")
    await crud_location.region.remove(db, id=region_id)
    return None


# =============================================================================
# GROUP ROUTES
# =============================================================================

@router.post(
    "/groups/",
    response_model=schemas.GroupResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:create_group"))],
)
async def create_group(
    *,
    db: AsyncSession = Depends(deps.get_db),
    group_in: schemas.GroupCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new group under an existing region.
    
    Groups are the fourth level of hierarchy. Path is auto-generated by
    appending group_id to the parent region's path.
    
    Args:
        db: Database session dependency
        group_in: Group creation data (group_id, region_id, group_name, etc.)
        current_user: Currently authenticated user
        
    Returns:
        GroupResponse: Created group with auto-generated path
        
    Raises:
        HTTPException 400: Group ID already exists
        HTTPException 404: Parent region not found
        
    Example:
        ```python
        POST /api/v1/groups/
        {
            "group_id": "ILE",
            "region_id": "ILN",
            "group_name": "Ilorin East"
        }
        
        Response:
        {
            "group_id": "ILE",
            "path": "org.234.KW.ILN.ILE",
            "formatted_id": "DCM-234-KW-ILN-ILE",
            ...
        }
        ```
    """
    return await crud_location.group.create(db=db, obj_in=group_in)


@router.get("/groups/", response_model=List[schemas.GroupResponse])
async def read_groups(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve all groups with pagination.
    
    Args:
        db: Database session dependency
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Currently authenticated user
        
    Returns:
        List[GroupResponse]: List of groups with paths
    """
    result = await db.execute(
        select(Group)
        .where(_hierarchy_visible_filter(Group.path, current_user))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/groups/{group_id}", response_model=schemas.GroupResponse)
async def read_group(
    *,
    db: AsyncSession = Depends(deps.get_db),
    group_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get a specific group by ID.
    
    Args:
        db: Database session dependency
        group_id: Unique group identifier
        current_user: Currently authenticated user
        
    Returns:
        GroupResponse: Group details with path
        
    Raises:
        HTTPException 404: Group not found
    """
    node = await crud_location.group.get(db=db, id=group_id)
    if not node:
        raise HTTPException(status_code=404, detail="Group not found")
    _ensure_hierarchy_visible(current_user, node, detail="Group outside your scope")
    return node


@router.put(
    "/groups/{group_id}",
    response_model=schemas.GroupResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:update_group"))],
)
async def update_group(
    *,
    db: AsyncSession = Depends(deps.get_db),
    group_id: str,
    group_in: schemas.GroupUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a group."""
    node = await crud_location.group.get(db=db, id=group_id)
    if not node:
        raise HTTPException(status_code=404, detail="Group not found")
    _ensure_hierarchy_mutable(current_user, node, detail="Group outside your scope")
    return await crud_location.group.update(db, db_obj=node, obj_in=group_in)


@router.delete(
    "/groups/{group_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:delete_group"))],
)
async def delete_group(
    *,
    db: AsyncSession = Depends(deps.get_db),
    group_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete a group."""
    node = await crud_location.group.get(db=db, id=group_id)
    if not node:
        raise HTTPException(status_code=404, detail="Group not found")
    _ensure_hierarchy_mutable(current_user, node, detail="Group outside your scope")
    await crud_location.group.remove(db, id=group_id)
    return None


# =============================================================================
# LOCATION ROUTES
# =============================================================================

@router.post(
    "/locations/",
    response_model=schemas.LocationResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:create_location"))],
)
async def create_location(
    *,
    db: AsyncSession = Depends(deps.get_db),
    location_in: schemas.LocationCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new location under an existing group.
    
    Locations are the fifth level of hierarchy, representing physical church
    buildings (DLBC, DLCF, DLSO). Workers are assigned to locations.
    
    Args:
        db: Database session dependency
        location_in: Location creation data (location_id, group_id, location_name, church_type, etc.)
        current_user: Currently authenticated user
        
    Returns:
        LocationResponse: Created location with auto-generated path
        
    Raises:
        HTTPException 400: Location ID already exists
        HTTPException 404: Parent group not found
        
    Example:
        ```python
        POST /api/v1/locations/
        {
            "location_id": "001",
            "group_id": "ILE",
            "location_name": "Ilorin East DLBC",
            "church_type": "DLBC"
        }
        
        Response:
        {
            "location_id": "001",
            "path": "org.234.KW.ILN.ILE.001",
            "formatted_id": "DCM-234-KW-ILN-ILE-001",
            ...
        }
        ```
        
    Notes:
        - Workers MUST belong to a location (foreign key enforced)
        - Church types: DLBC (Bible Church), DLCF (Campus Fellowship), DLSO (Students Outreach)
    """
    return await crud_location.location.create(db=db, obj_in=location_in)


@router.get("/locations/", response_model=List[schemas.LocationResponse])
async def read_locations(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
    group_id: str = None,
) -> Any:
    """
    Retrieve locations with optional filtering by group.
    
    Args:
        db: Database session dependency
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Currently authenticated user
        group_id: Optional filter - only show locations in this group
        
    Returns:
        List[LocationResponse]: List of locations with paths
        
    Example:
        ```python
        # All locations
        GET /api/v1/locations/
        
        # Locations in specific group
        GET /api/v1/locations/?group_id=ILE
        ```
    """
    if group_id:
        query = (
            select(Location)
            .where(
                Location.group_id == group_id,
                _hierarchy_visible_filter(Location.path, current_user),
            )
            .offset(skip)
            .limit(limit)
        )
        res = await db.execute(query)
        return res.scalars().all()
    result = await db.execute(
        select(Location)
        .where(_hierarchy_visible_filter(Location.path, current_user))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/locations/{location_id}", response_model=schemas.LocationResponse)
async def read_location(
    *,
    db: AsyncSession = Depends(deps.get_db),
    location_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get a specific location by ID.
    
    Args:
        db: Database session dependency
        location_id: Unique location identifier
        current_user: Currently authenticated user
        
    Returns:
        LocationResponse: Location details with path
        
    Raises:
        HTTPException 404: Location not found
    """
    loc = await crud_location.location.get(db=db, id=location_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    _ensure_hierarchy_visible(current_user, loc, detail="Location outside your scope")
    return loc


@router.put(
    "/locations/{location_id}",
    response_model=schemas.LocationResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:update_location"))],
)
async def update_location(
    *,
    db: AsyncSession = Depends(deps.get_db),
    location_id: str,
    location_in: schemas.LocationUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a location."""
    loc = await crud_location.location.get(db=db, id=location_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    _ensure_hierarchy_mutable(current_user, loc, detail="Location outside your scope")
    return await crud_location.location.update(db, db_obj=loc, obj_in=location_in)


@router.delete(
    "/locations/{location_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:delete_location"))],
)
async def delete_location(
    *,
    db: AsyncSession = Depends(deps.get_db),
    location_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete a location."""
    loc = await crud_location.location.get(db=db, id=location_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    _ensure_hierarchy_mutable(current_user, loc, detail="Location outside your scope")
    await crud_location.location.remove(db, id=location_id)
    return None


@router.get("/locations/{location_id}/details", response_model=schemas.LocationDetailResponse)
async def get_location_details(
    *,
    db: AsyncSession = Depends(deps.get_db),
    location_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get location details with state/region/group names."""
    loc = await crud_location.location.get(db=db, id=location_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    _ensure_hierarchy_visible(current_user, loc, detail="Location outside your scope")
    stmt = (
        select(
            Location.location_id,
            Location.location_name,
            Location.church_type,
            Group.group_id,
            Group.group_name,
            Region.region_id,
            Region.region_name,
            State.state_id,
            State.state_name,
        )
        .join(Group, Group.group_id == Location.group_id)
        .join(Region, Region.region_id == Group.region_id)
        .join(State, State.state_id == Region.state_id)
        .where(Location.location_id == location_id)
    )
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Location not found")
    return schemas.LocationDetailResponse(**row._mapping)


# =============================================================================
# FELLOWSHIP ROUTES (Leaf Level)
# =============================================================================

@router.post(
    "/fellowships/",
    response_model=schemas.FellowshipResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:create_fellowship"))],
)
async def create_fellowship(
    *,
    db: AsyncSession = Depends(deps.get_db),
    fellowship_in: schemas.FellowshipCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Create a new fellowship under an existing location.
    
    Fellowships are the leaf level (sixth and final) of the hierarchy,
    representing small groups or house fellowships within a location.
    
    Args:
        db: Database session dependency
        fellowship_in: Fellowship creation data (fellowship_id, location_id, fellowship_name, etc.)
        current_user: Currently authenticated user
        
    Returns:
        FellowshipResponse: Created fellowship with auto-generated path
        
    Raises:
        HTTPException 400: Fellowship ID already exists
        HTTPException 404: Parent location not found
        
    Example:
        ```python
        POST /api/v1/fellowships/
        {
            "fellowship_id": "F001",
            "location_id": "001",
            "fellowship_name": "Youth Fellowship",
            "leader_in_charge": "Brother James"
        }
        
        Response:
        {
            "fellowship_id": "F001",
            "path": "org.234.KW.ILN.ILE.001.F001",
            "formatted_id": "DCM-234-KW-ILN-ILE-001-F001",
            ...
        }
        ```
        
    Notes:
        - Fellowships are the smallest organizational unit
        - Fellowship data includes denormalized location info for quick access
    """
    return await crud_location.fellowship.create(db=db, obj_in=fellowship_in)


@router.get("/fellowships/", response_model=List[schemas.FellowshipResponse])
async def read_fellowships(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(deps.get_current_active_user),
    location_id: str = None,
) -> Any:
    """
    Retrieve fellowships with optional filtering by location.
    
    Args:
        db: Database session dependency
        skip: Number of records to skip
        limit: Maximum number of records to return
        current_user: Currently authenticated user
        location_id: Optional filter - only show fellowships in this location
        
    Returns:
        List[FellowshipResponse]: List of fellowships with paths
        
    Example:
        ```python
        # All fellowships
        GET /api/v1/fellowships/
        
        # Fellowships in specific location
        GET /api/v1/fellowships/?location_id=001
        ```
    """
    if location_id:
        query = (
            select(Fellowship)
            .where(
                Fellowship.location_id == location_id,
                _hierarchy_visible_filter(Fellowship.path, current_user),
            )
            .offset(skip)
            .limit(limit)
        )
        res = await db.execute(query)
        return res.scalars().all()
    result = await db.execute(
        select(Fellowship)
        .where(_hierarchy_visible_filter(Fellowship.path, current_user))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/fellowships/{fellowship_id}", response_model=schemas.FellowshipResponse)
async def read_fellowship(
    *,
    db: AsyncSession = Depends(deps.get_db),
    fellowship_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get a specific fellowship by ID.
    
    Args:
        db: Database session dependency
        fellowship_id: Unique fellowship identifier
        current_user: Currently authenticated user
        
    Returns:
        FellowshipResponse: Fellowship details with path
        
    Raises:
        HTTPException 404: Fellowship not found
    """
    node = await crud_location.fellowship.get(db=db, id=fellowship_id)
    if not node:
        raise HTTPException(status_code=404, detail="Fellowship not found")
    _ensure_hierarchy_visible(current_user, node, detail="Fellowship outside your scope")
    return node


@router.put(
    "/fellowships/{fellowship_id}",
    response_model=schemas.FellowshipResponse,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:update_fellowship"))],
)
async def update_fellowship(
    *,
    db: AsyncSession = Depends(deps.get_db),
    fellowship_id: str,
    fellowship_in: schemas.FellowshipUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a fellowship."""
    node = await crud_location.fellowship.get(db=db, id=fellowship_id)
    if not node:
        raise HTTPException(status_code=404, detail="Fellowship not found")
    _ensure_hierarchy_mutable(current_user, node, detail="Fellowship outside your scope")
    return await crud_location.fellowship.update(db, db_obj=node, obj_in=fellowship_in)


@router.delete(
    "/fellowships/{fellowship_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("hierarchy:delete_fellowship"))],
)
async def delete_fellowship(
    *,
    db: AsyncSession = Depends(deps.get_db),
    fellowship_id: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete a fellowship."""
    node = await crud_location.fellowship.get(db=db, id=fellowship_id)
    if not node:
        raise HTTPException(status_code=404, detail="Fellowship not found")
    _ensure_hierarchy_mutable(current_user, node, detail="Fellowship outside your scope")
    await crud_location.fellowship.remove(db, id=fellowship_id)
    return None


# =============================================================================
# SPECIAL ROUTES - Tree View & Search
# =============================================================================

@router.get("/hierarchy/tree", response_model=List[schemas.TreeNode])
async def get_hierarchy_tree(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get the complete hierarchy as a nested tree structure.
    
    This endpoint fetches all hierarchy levels and constructs a recursive
    JSON tree, making it easy for frontends to display the organizational
    structure without multiple API calls.
    
    Args:
        db: Database session dependency
        current_user: Currently authenticated user
        
    Returns:
        List[TreeNode]: List of root nations, each containing nested children
        
    Example:
        ```python
        GET /api/v1/hierarchy/tree
        
        Response:
        [
            {
                "id": "234",
                "name": "Nigeria",
                "type": "nation",
                "path": "org.234",
                "formatted_id": "DCM-234",
                "children": [
                    {
                        "id": "KW",
                        "name": "Kwara",
                        "type": "state",
                        "path": "org.234.KW",
                        "formatted_id": "DCM-234-KW",
                        "children": [...]
                    }
                ]
            }
        ]
        ```
        
    Notes:
        - Fetches only nodes visible to the current user's scope
        - Tree is constructed in-memory (efficient for <10k nodes)
    """

    # Fetch only ancestors/descendants visible to this user's scope.
    nations = (await db.execute(
        select(Nation)
        .where(_hierarchy_visible_filter(Nation.path, current_user))
        .order_by(Nation.path)
    )).scalars().all()
    states = (await db.execute(
        select(State)
        .where(_hierarchy_visible_filter(State.path, current_user))
        .order_by(State.path)
    )).scalars().all()
    regions = (await db.execute(
        select(Region)
        .where(_hierarchy_visible_filter(Region.path, current_user))
        .order_by(Region.path)
    )).scalars().all()
    groups = (await db.execute(
        select(Group)
        .where(_hierarchy_visible_filter(Group.path, current_user))
        .order_by(Group.path)
    )).scalars().all()
    locations = (await db.execute(
        select(Location)
        .where(_hierarchy_visible_filter(Location.path, current_user))
        .order_by(Location.path)
    )).scalars().all()
    fellowships = (await db.execute(
        select(Fellowship)
        .where(_hierarchy_visible_filter(Fellowship.path, current_user))
        .order_by(Fellowship.path)
    )).scalars().all()

    def is_visible(path: object) -> bool:
        return deps.path_in_scope(current_user.path, path) or deps.path_in_scope(path, current_user.path)

    # Map nodes into TreeNode objects
    nodes_map = {}  # path -> TreeNode
    result = []
    
    # Build tree from top to bottom
    for n in nations:
        if not is_visible(n.path):
            continue
        node = schemas.TreeNode(
            id=n.nation_id,
            name=n.country_name,
            type="nation",
            path=str(n.path),
            formatted_id=n.formatted_id,
            children=[]
        )
        nodes_map[str(n.path)] = node
        result.append(node)
        
    for s in states:
        if not is_visible(s.path):
            continue
        node = schemas.TreeNode(
            id=s.state_id,
            name=s.state_name,
            type="state",
            path=str(s.path),
            formatted_id=s.formatted_id,
            children=[]
        )
        nodes_map[str(s.path)] = node
        parent_path = ".".join(str(s.path).split(".")[:-1])
        if parent_path in nodes_map:
            nodes_map[parent_path].children.append(node)

    for r in regions:
        if not is_visible(r.path):
            continue
        node = schemas.TreeNode(
            id=r.region_id,
            name=r.region_name,
            type="region",
            path=str(r.path),
            formatted_id=r.formatted_id,
            children=[]
        )
        nodes_map[str(r.path)] = node
        parent_path = ".".join(str(r.path).split(".")[:-1])
        if parent_path in nodes_map:
            nodes_map[parent_path].children.append(node)

    for g in groups:
        if not is_visible(g.path):
            continue
        node = schemas.TreeNode(
            id=g.group_id,
            name=g.group_name,
            type="group",
            path=str(g.path),
            formatted_id=g.formatted_id,
            children=[]
        )
        nodes_map[str(g.path)] = node
        parent_path = ".".join(str(g.path).split(".")[:-1])
        if parent_path in nodes_map:
            nodes_map[parent_path].children.append(node)

    for l in locations:
        if not is_visible(l.path):
            continue
        node = schemas.TreeNode(
            id=l.location_id,
            name=l.location_name,
            type="location",
            path=str(l.path),
            formatted_id=l.formatted_id,
            children=[]
        )
        nodes_map[str(l.path)] = node
        parent_path = ".".join(str(l.path).split(".")[:-1])
        if parent_path in nodes_map:
            nodes_map[parent_path].children.append(node)

    for f in fellowships:
        if not is_visible(f.path):
            continue
        node = schemas.TreeNode(
            id=f.fellowship_id,
            name=f.fellowship_name,
            type="fellowship",
            path=str(f.path),
            formatted_id=f.formatted_id,
            children=[]
        )
        parent_path = ".".join(str(f.path).split(".")[:-1])
        if parent_path in nodes_map:
            nodes_map[parent_path].children.append(node)

    return result


@router.get("/hierarchy/search", response_model=List[schemas.TreeNode])
async def search_hierarchy(
    *,
    db: AsyncSession = Depends(deps.get_db),
    query: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Search for hierarchy nodes by name across all levels.
    
    Performs a case-insensitive search across all hierarchy levels
    (nations, states, regions, groups, locations, fellowships) and
    returns matching nodes with their paths.
    
    Args:
        db: Database session dependency
        query: Search term (case-insensitive, partial match)
        current_user: Currently authenticated user
        
    Returns:
        List[TreeNode]: List of matching nodes from any level
        
    Example:
        ```python
        GET /api/v1/hierarchy/search?query=ilorin
        
        Response:
        [
            {
                "id": "ILN",
                "name": "Ilorin North",
                "type": "region",
                "path": "org.234.KW.ILN",
                "formatted_id": "DCM-234-KW-ILN",
                "children": []
            },
            {
                "id": "001",
                "name": "Ilorin East DLBC",
                "type": "location",
                "path": "org.234.KW.ILN.ILE.001",
                "formatted_id": "DCM-234-KW-ILN-ILE-001",
                "children": []
            }
        ]
        ```
        
    Notes:
        - Searches across hierarchy levels visible to the current user's scope
        - Case-insensitive partial matching
        - Results are flat (children array is empty)
    """
    search_term = f"%{query.strip()}%"
    results = []

    # Search nations
    n_res = await db.execute(
        select(Nation)
        .where(
            Nation.country_name.ilike(search_term),
            _hierarchy_visible_filter(Nation.path, current_user),
        )
        .order_by(Nation.country_name)
        .limit(limit)
    )
    for n in n_res.scalars().all():
        results.append(schemas.TreeNode(
            id=n.nation_id,
            name=n.country_name,
            type="nation",
            path=str(n.path),
            formatted_id=n.formatted_id,
            children=[]
        ))

    if len(results) >= limit:
        return results[:limit]

    # Search states
    remaining = limit - len(results)
    s_res = await db.execute(
        select(State)
        .where(
            State.state_name.ilike(search_term),
            _hierarchy_visible_filter(State.path, current_user),
        )
        .order_by(State.state_name)
        .limit(remaining)
    )
    for s in s_res.scalars().all():
        results.append(schemas.TreeNode(
            id=s.state_id,
            name=s.state_name,
            type="state",
            path=str(s.path),
            formatted_id=s.formatted_id,
            children=[]
        ))

    if len(results) >= limit:
        return results[:limit]

    # Search regions
    remaining = limit - len(results)
    r_res = await db.execute(
        select(Region)
        .where(
            Region.region_name.ilike(search_term),
            _hierarchy_visible_filter(Region.path, current_user),
        )
        .order_by(Region.region_name)
        .limit(remaining)
    )
    for r in r_res.scalars().all():
        results.append(schemas.TreeNode(
            id=r.region_id,
            name=r.region_name,
            type="region",
            path=str(r.path),
            formatted_id=r.formatted_id,
            children=[]
        ))

    if len(results) >= limit:
        return results[:limit]

    # Search groups
    remaining = limit - len(results)
    g_res = await db.execute(
        select(Group)
        .where(
            Group.group_name.ilike(search_term),
            _hierarchy_visible_filter(Group.path, current_user),
        )
        .order_by(Group.group_name)
        .limit(remaining)
    )
    for g in g_res.scalars().all():
        results.append(schemas.TreeNode(
            id=g.group_id,
            name=g.group_name,
            type="group",
            path=str(g.path),
            formatted_id=g.formatted_id,
            children=[]
        ))

    if len(results) >= limit:
        return results[:limit]

    # Search locations
    remaining = limit - len(results)
    l_res = await db.execute(
        select(Location)
        .where(
            Location.location_name.ilike(search_term),
            _hierarchy_visible_filter(Location.path, current_user),
        )
        .order_by(Location.location_name)
        .limit(remaining)
    )
    for l in l_res.scalars().all():
        results.append(schemas.TreeNode(
            id=l.location_id,
            name=l.location_name,
            type="location",
            path=str(l.path),
            formatted_id=l.formatted_id,
            children=[]
        ))

    if len(results) >= limit:
        return results[:limit]

    # Search fellowships
    remaining = limit - len(results)
    f_res = await db.execute(
        select(Fellowship)
        .where(
            Fellowship.fellowship_name.ilike(search_term),
            _hierarchy_visible_filter(Fellowship.path, current_user),
        )
        .order_by(Fellowship.fellowship_name)
        .limit(remaining)
    )
    for f in f_res.scalars().all():
        results.append(schemas.TreeNode(
            id=f.fellowship_id,
            name=f.fellowship_name,
            type="fellowship",
            path=str(f.path),
            formatted_id=f.formatted_id,
            children=[]
        ))

    return results
