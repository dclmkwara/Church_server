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
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.crud import crud_location
from app.schemas import location as schemas
from app.models.user import User

router = APIRouter()


# =============================================================================
# NATION ROUTES (Root Level)
# =============================================================================

@router.post("/nations/", response_model=schemas.NationResponse)
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
        - Only high-level admins should create nations (TODO: add permission check)
    """
    return await crud_location.nation.create(db=db, obj_in=nation_in)


@router.get("/nations/", response_model=List[schemas.NationResponse])
async def read_nations(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
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
    return await crud_location.nation.get_multi(db=db, skip=skip, limit=limit)


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
    return node


# =============================================================================
# STATE ROUTES
# =============================================================================

@router.post("/states/", response_model=schemas.StateResponse)
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
    skip: int = 0,
    limit: int = 100,
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
    return await crud_location.state.get_multi(db=db, skip=skip, limit=limit)


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
    return node


# =============================================================================
# REGION ROUTES
# =============================================================================

@router.post("/regions/", response_model=schemas.RegionResponse)
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
    skip: int = 0,
    limit: int = 100,
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
    return await crud_location.region.get_multi(db=db, skip=skip, limit=limit)


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
    return node


# =============================================================================
# GROUP ROUTES
# =============================================================================

@router.post("/groups/", response_model=schemas.GroupResponse)
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
    skip: int = 0,
    limit: int = 100,
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
    return await crud_location.group.get_multi(db=db, skip=skip, limit=limit)


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
    return node


# =============================================================================
# LOCATION ROUTES
# =============================================================================

@router.post("/locations/", response_model=schemas.LocationResponse)
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
    skip: int = 0,
    limit: int = 100,
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
        from app.models.location import Location
        query = select(Location).where(Location.group_id == group_id).offset(skip).limit(limit)
        res = await db.execute(query)
        return res.scalars().all()
    return await crud_location.location.get_multi(db=db, skip=skip, limit=limit)


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
    return loc


# =============================================================================
# FELLOWSHIP ROUTES (Leaf Level)
# =============================================================================

@router.post("/fellowships/", response_model=schemas.FellowshipResponse)
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
    skip: int = 0,
    limit: int = 100,
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
        from app.models.location import Fellowship
        query = select(Fellowship).where(Fellowship.location_id == location_id).offset(skip).limit(limit)
        res = await db.execute(query)
        return res.scalars().all()
    return await crud_location.fellowship.get_multi(db=db, skip=skip, limit=limit)


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
    return node


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
        - Fetches ALL nodes (use with caution on large datasets)
        - Consider adding scope filtering for production
        - Tree is constructed in-memory (efficient for <10k nodes)
    """
    from app.models.location import Nation, State, Region, Group, Location, Fellowship
    
    # Fetch all nodes from all levels
    nations = (await db.execute(select(Nation))).scalars().all()
    states = (await db.execute(select(State))).scalars().all()
    regions = (await db.execute(select(Region))).scalars().all()
    groups = (await db.execute(select(Group))).scalars().all()
    locations = (await db.execute(select(Location))).scalars().all()
    fellowships = (await db.execute(select(Fellowship))).scalars().all()

    # Map nodes into TreeNode objects
    nodes_map = {}  # path -> TreeNode
    result = []
    
    # Build tree from top to bottom
    for n in nations:
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
    query: str,
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
        - Searches across ALL hierarchy levels
        - Case-insensitive partial matching
        - Results are flat (children array is empty)
        - Consider adding scope filtering for production
    """
    from app.models.location import Nation, State, Region, Group, Location, Fellowship
    
    results = []
    
    # Search nations
    n_res = await db.execute(select(Nation).where(Nation.country_name.ilike(f"%{query}%")))
    for n in n_res.scalars().all():
        results.append(schemas.TreeNode(
            id=n.nation_id,
            name=n.country_name,
            type="nation",
            path=str(n.path),
            formatted_id=n.formatted_id,
            children=[]
        ))
        
    # Search states
    s_res = await db.execute(select(State).where(State.state_name.ilike(f"%{query}%")))
    for s in s_res.scalars().all():
        results.append(schemas.TreeNode(
            id=s.state_id,
            name=s.state_name,
            type="state",
            path=str(s.path),
            formatted_id=s.formatted_id,
            children=[]
        ))
        
    # Search regions
    r_res = await db.execute(select(Region).where(Region.region_name.ilike(f"%{query}%")))
    for r in r_res.scalars().all():
        results.append(schemas.TreeNode(
            id=r.region_id,
            name=r.region_name,
            type="region",
            path=str(r.path),
            formatted_id=r.formatted_id,
            children=[]
        ))
        
    # Search groups
    g_res = await db.execute(select(Group).where(Group.group_name.ilike(f"%{query}%")))
    for g in g_res.scalars().all():
        results.append(schemas.TreeNode(
            id=g.group_id,
            name=g.group_name,
            type="group",
            path=str(g.path),
            formatted_id=g.formatted_id,
            children=[]
        ))
        
    # Search locations
    l_res = await db.execute(select(Location).where(Location.location_name.ilike(f"%{query}%")))
    for l in l_res.scalars().all():
        results.append(schemas.TreeNode(
            id=l.location_id,
            name=l.location_name,
            type="location",
            path=str(l.path),
            formatted_id=l.formatted_id,
            children=[]
        ))
        
    # Search fellowships
    f_res = await db.execute(select(Fellowship).where(Fellowship.fellowship_name.ilike(f"%{query}%")))
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
