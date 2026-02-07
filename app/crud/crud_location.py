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
    org.234.KW.ILN.ILE.001.F001
    └── Nation: 234
        └── State: KW
            └── Region: ILN
                └── Group: ILE
                    └── Location: 001
                        └── Fellowship: F001
"""
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
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
        # Check if nation ID already exists
        if await self.get(db, obj_in.nation_id):
             raise HTTPException(status_code=400, detail="Nation ID already exists")

        # Create nation with generated path
        db_obj = Nation(
            nation_id=obj_in.nation_id,
            continent=obj_in.continent,
            country_name=obj_in.country_name,
            capital=obj_in.capital,
            address=obj_in.address,
            church_hq=obj_in.church_hq,
            national_pastor=obj_in.national_pastor,
            path=f"org.{obj_in.nation_id}"  # Root path format
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
        
        # Check for duplicate state ID
        if await self.get(db, obj_in.state_id):
             raise HTTPException(status_code=400, detail="State ID already exists")

        # Generate path: parent.path + "." + state_id
        new_path = f"{parent.path}.{obj_in.state_id}"

        db_obj = State(
            state_id=obj_in.state_id,
            nation_id=obj_in.nation_id,
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
        org.234.KW.ILN (Ilorin North Region in Kwara State)
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

        # Check for duplicate region ID
        if await self.get(db, obj_in.region_id):
             raise HTTPException(status_code=400, detail="Region ID already exists")

        new_path = f"{parent.path}.{obj_in.region_id}"

        db_obj = Region(
            region_id=obj_in.region_id,
            state_id=obj_in.state_id,
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
        org.234.KW.ILN.ILE (Ilorin East Group in Ilorin North Region)
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

        if await self.get(db, obj_in.group_id):
             raise HTTPException(status_code=400, detail="Group ID already exists")

        new_path = f"{parent.path}.{obj_in.group_id}"

        db_obj = Group(
            group_id=obj_in.group_id,
            region_id=obj_in.region_id,
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
        org.234.KW.ILN.ILE.001 (Location 001 in Ilorin East Group)
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

        if await self.get(db, obj_in.location_id):
             raise HTTPException(status_code=400, detail="Location ID already exists")

        new_path = f"{parent.path}.{obj_in.location_id}"

        db_obj = Location(
            location_id=obj_in.location_id,
            group_id=obj_in.group_id,
            location_name=obj_in.location_name,
            church_type=obj_in.church_type,
            address=obj_in.address,
            associate_cord=obj_in.associate_cord,
            path=new_path
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

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
        org.234.KW.ILN.ILE.001.F001 (Fellowship F001 in Location 001)
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

        if await self.get(db, obj_in.fellowship_id):
             raise HTTPException(status_code=400, detail="Fellowship ID already exists")

        new_path = f"{parent.path}.{obj_in.fellowship_id}"

        db_obj = Fellowship(
            fellowship_id=obj_in.fellowship_id,
            location_id=obj_in.location_id,
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
