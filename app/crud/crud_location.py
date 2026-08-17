"""
CRUD operations for hierarchical location management.

This module provides database operations for the 6-level church hierarchy:
Nation → State → Region → Group → Location → Fellowship

Each CRUD class handles:
- Automatic ltree path generation based on parent hierarchy
- Parent existence validation
- Duplicate ID prevention
- Standard CRUD operations (create, read, update, delete)

The path generation follows the pattern:
    org.{nation_id}.{state_id}.{region_id}.{group_id}.{location_id}.{fellowship_id}

Example:
    org.234.KW.ILR.ILE.003.F001
    └── Nation: 234
        └── State: KW
            └── Region: ILR
                └── Group: ILE
                    └── Location: 003
                        └── Fellowship: F001
"""
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.models.location import Nation, State, Region, Group, Location, Fellowship
from app.schemas.location import (
    NationCreate, NationUpdate,
    StateCreate, StateUpdate,
    RegionCreate, RegionUpdate,
    GroupCreate, GroupUpdate,
    LocationCreate, LocationUpdate,
    FellowshipCreate, FellowshipUpdate
)


# =============================================================================
# NATION CRUD (Root Level)
# =============================================================================

class CRUDNation(CRUDBase[Nation, NationCreate, NationUpdate]):
    """
    CRUD operations for Nation (root level of hierarchy).
    
    Nations represent countries and are the top-level organizational unit.
    Path format: org.{nation_id}
    
    Example:
        org.234 (Nigeria)
    """
    
    async def create(self, db: AsyncSession, *, obj_in: NationCreate) -> Nation:
        """
        Create a new nation with auto-generated ltree path.
        
        Generates the root path as 'org.{nation_id}' and validates that
        the nation_id is unique.
        
        Args:
            db: Database session
            obj_in: Nation creation data
            
        Returns:
            Nation: Created nation with generated path
            
        Raises:
            HTTPException 400: Nation ID already exists
            
        Example:
            ```python
            nation_data = NationCreate(
                nation_id="234",
                continent="Africa",
                country_name="Nigeria"
            )
            nation = await crud_nation.create(db, obj_in=nation_data)
            # nation.path = "org.234"
            ```
        """
        existing = await db.execute(select(Nation).where(Nation.nation_code == obj_in.nation_code))
        if existing.scalars().first():
             raise HTTPException(status_code=400, detail="Nation code already exists")

        # Create nation with generated path
        db_obj = Nation(
            nation_code=obj_in.nation_code,
            continent=obj_in.continent,
            country_name=obj_in.country_name,
            capital=obj_in.capital,
            address=obj_in.address,
            church_hq=obj_in.church_hq,
            national_pastor=obj_in.national_pastor,
            path=f"org.{obj_in.nation_code}"  # Root path format
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

nation = CRUDNation(Nation)


# =============================================================================
# STATE CRUD
# =============================================================================

class CRUDState(CRUDBase[State, StateCreate, StateUpdate]):
    """
    CRUD operations for State (second level of hierarchy).
    
    States belong to nations and inherit their parent's path.
    Path format: {nation.path}.{state_id}
    
    Example:
        org.234.KW (Kwara State in Nigeria)
    """
    
    async def create(self, db: AsyncSession, *, obj_in: StateCreate) -> State:
        """
        Create a new state under an existing nation.
        
        Validates that the parent nation exists and generates the path by
        appending state_id to the nation's path.
        
        Args:
            db: Database session
            obj_in: State creation data (must include nation_id)
            
        Returns:
            State: Created state with generated path
            
        Raises:
            HTTPException 404: Parent nation not found
            HTTPException 400: State ID already exists
            
        Example:
            ```python
            state_data = StateCreate(
                state_id="KW",
                nation_id="234",
                state_name="Kwara"
            )
            state = await crud_state.create(db, obj_in=state_data)
            # state.path = "org.234.KW"
            ```
        """
        # Validate parent nation exists
        parent = await nation.get(db, obj_in.nation_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent Nation not found")
        
        existing = await db.execute(
            select(State).where(State.nation_id == obj_in.nation_id, State.state_code == obj_in.state_code)
        )
        if existing.scalars().first():
             raise HTTPException(status_code=400, detail="State code already exists in this nation")

        # Generate path: parent.path + "." + state_id
        new_path = f"{parent.path}.{obj_in.state_code}"

        db_obj = State(
            nation_id=obj_in.nation_id,
            state_code=obj_in.state_code,
            state_name=obj_in.state_name,
            city=obj_in.city,
            address=obj_in.address,
            state_hq=obj_in.state_hq,
            state_pastor=obj_in.state_pastor,
            path=new_path
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

state = CRUDState(State)


# =============================================================================
# REGION CRUD
# =============================================================================

class CRUDRegion(CRUDBase[Region, RegionCreate, RegionUpdate]):
    """
    CRUD operations for Region (third level of hierarchy).
    
    Regions belong to states and inherit their parent's path.
    Path format: {state.path}.{region_id}
    
    Example:
        org.234.KW.ILR (Ilorin Region in Kwara State)
    """
    
    async def create(self, db: AsyncSession, *, obj_in: RegionCreate) -> Region:
        """
        Create a new region under an existing state.
        
        Validates that the parent state exists and generates the path by
        appending region_id to the state's path.
        
        Args:
            db: Database session
            obj_in: Region creation data (must include state_id)
            
        Returns:
            Region: Created region with generated path
            
        Raises:
            HTTPException 404: Parent state not found
            HTTPException 400: Region ID already exists
        """
        # Validate parent state exists
        parent = await state.get(db, obj_in.state_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent State not found")

        existing = await db.execute(
            select(Region).where(Region.state_id == obj_in.state_id, Region.region_code == obj_in.region_code)
        )
        if existing.scalars().first():
             raise HTTPException(status_code=400, detail="Region code already exists in this state")

        new_path = f"{parent.path}.{obj_in.region_code}"

        db_obj = Region(
            state_id=obj_in.state_id,
            region_code=obj_in.region_code,
            region_name=obj_in.region_name,
            region_head=obj_in.region_head,
            regional_pastor=obj_in.regional_pastor,
            path=new_path
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

region = CRUDRegion(Region)


# =============================================================================
# GROUP CRUD
# =============================================================================

class CRUDGroup(CRUDBase[Group, GroupCreate, GroupUpdate]):
    """
    CRUD operations for Group (fourth level of hierarchy).
    
    Groups belong to regions and inherit their parent's path.
    Path format: {region.path}.{group_id}
    
    Example:
        org.234.KW.ILR.ILE (Ilorin East Group in Ilorin Region)
    """
    
    async def create(self, db: AsyncSession, *, obj_in: GroupCreate) -> Group:
        """
        Create a new group under an existing region.
        
        Validates that the parent region exists and generates the path by
        appending group_id to the region's path.
        
        Args:
            db: Database session
            obj_in: Group creation data (must include region_id)
            
        Returns:
            Group: Created group with generated path
            
        Raises:
            HTTPException 404: Parent region not found
            HTTPException 400: Group ID already exists
        """
        parent = await region.get(db, obj_in.region_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent Region not found")

        existing = await db.execute(
            select(Group).where(Group.region_id == obj_in.region_id, Group.group_code == obj_in.group_code)
        )
        if existing.scalars().first():
             raise HTTPException(status_code=400, detail="Group code already exists in this region")

        new_path = f"{parent.path}.{obj_in.group_code}"

        db_obj = Group(
            region_id=obj_in.region_id,
            group_code=obj_in.group_code,
            group_name=obj_in.group_name,
            group_head=obj_in.group_head,
            group_pastor=obj_in.group_pastor,
            path=new_path
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

group = CRUDGroup(Group)


# =============================================================================
# LOCATION CRUD
# =============================================================================

class CRUDLocation(CRUDBase[Location, LocationCreate, LocationUpdate]):
    """
    CRUD operations for Location (fifth level of hierarchy).
    
    Locations represent physical church buildings (DLBC, DLCF, DLSO).
    Workers are assigned to locations (foreign key enforced).
    Path format: {group.path}.{location_id}
    
    Example:
        org.234.KW.ILR.ILE.003 (Location 003 in Ilorin East Group)
    """
    
    async def create(self, db: AsyncSession, *, obj_in: LocationCreate) -> Location:
        """
        Create a new location under an existing group.
        
        Validates that the parent group exists and generates the path by
        appending location_id to the group's path.
        
        Args:
            db: Database session
            obj_in: Location creation data (must include group_id)
            
        Returns:
            Location: Created location with generated path
            
        Raises:
            HTTPException 404: Parent group not found
            HTTPException 400: Location ID already exists
            
        Notes:
            - Workers MUST belong to a location (foreign key enforced)
            - Church types: DLBC, DLCF, DLSO
        """
        parent = await group.get(db, obj_in.group_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent Group not found")

        location_code = obj_in.location_code or await self.next_location_code(db, group_id=obj_in.group_id)
        existing = await db.execute(
            select(Location).where(Location.group_id == obj_in.group_id, Location.location_code == location_code)
        )
        if existing.scalars().first():
             raise HTTPException(status_code=400, detail="Location code already exists in this group")

        new_path = f"{parent.path}.{location_code}"

        db_obj = Location(
            group_id=obj_in.group_id,
            location_code=location_code,
            location_name=obj_in.location_name,
            church_type=obj_in.church_type,
            address=obj_in.address,
            associate_cord=obj_in.associate_cord,
            latitude=obj_in.latitude,
            longitude=obj_in.longitude,
            path=new_path
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def next_location_code(self, db: AsyncSession, *, group_id: Any) -> str:
        result = await db.execute(
            select(func.max(Location.location_code)).where(Location.group_id == group_id)
        )
        current_max = result.scalar_one_or_none()
        if not current_max:
            return "001"
        try:
            next_number = int(current_max) + 1
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Existing location codes must be numeric") from exc
        return f"{next_number:03d}"

location = CRUDLocation(Location)


# =============================================================================
# FELLOWSHIP CRUD (Leaf Level)
# =============================================================================

class CRUDFellowship(CRUDBase[Fellowship, FellowshipCreate, FellowshipUpdate]):
    """
    CRUD operations for Fellowship (sixth and final level of hierarchy).
    
    Fellowships are small groups or house fellowships within locations.
    They are the leaf nodes of the hierarchy tree.
    Path format: {location.path}.{fellowship_id}
    
    Example:
        org.234.KW.ILR.ILE.003.F001 (Fellowship F001 in Location 003)
    """
    
    async def create(self, db: AsyncSession, *, obj_in: FellowshipCreate) -> Fellowship:
        """
        Create a new fellowship under an existing location.
        
        Validates that the parent location exists and generates the path by
        appending fellowship_id to the location's path.
        
        Args:
            db: Database session
            obj_in: Fellowship creation data (must include location_id)
            
        Returns:
            Fellowship: Created fellowship with generated path
            
        Raises:
            HTTPException 404: Parent location not found
            HTTPException 400: Fellowship ID already exists
            
        Notes:
            - Fellowships are the smallest organizational unit
            - Fellowship data includes denormalized location info
        """
        parent = await location.get(db, obj_in.location_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent Location not found")

        existing = await db.execute(
            select(Fellowship).where(
                Fellowship.location_id == obj_in.location_id,
                Fellowship.fellowship_code == obj_in.fellowship_code,
            )
        )
        if existing.scalars().first():
             raise HTTPException(status_code=400, detail="Fellowship code already exists in this location")

        new_path = f"{parent.path}.{obj_in.fellowship_code}"

        db_obj = Fellowship(
            location_id=obj_in.location_id,
            fellowship_code=obj_in.fellowship_code,
            fellowship_name=obj_in.fellowship_name,
            fellowship_address=obj_in.fellowship_address,
            associate_church=obj_in.associate_church,
            leader_in_charge=obj_in.leader_in_charge,
            leader_contact=obj_in.leader_contact,
            path=new_path
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

fellowship = CRUDFellowship(Fellowship)
