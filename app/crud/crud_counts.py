"""
CRUD operations for Count records.

Handles population count submission with offline sync support via client_id.
"""
from typing import List, Optional, Any
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.models.counts import Count
from app.schemas.counts import CountCreate, CountUpdate


class CRUDCount(CRUDBase[Count, CountCreate, CountUpdate]):
    """
    CRUD operations for Count model.
    
    Includes idempotency checking for offline sync.
    """
    
    async def create(self, db: AsyncSession, *, obj_in: CountCreate, user_id: UUID) -> Count:
        """
        Create a new count record.
        
        Checks for duplicate client_id to prevent duplicate submissions during offline sync.
        
        Args:
            db: Database session
            obj_in: Count creation data
            user_id: ID of user submitting the count
            
        Returns:
            Count: Created count record
            
        Raises:
            HTTPException 400: Duplicate client_id (already submitted)
            HTTPException 404: Event not found
        """
        # Check for duplicate client_id (idempotency)
        if obj_in.client_id:
            existing = await self.get_by_client_id(db, client_id=obj_in.client_id)
            if existing:
                # Return existing record instead of creating duplicate
                return existing
        
        # Verify event exists
        from app.crud.crud_programs import program_event
        event = await program_event.get(db, id=obj_in.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Derive path from event
        path_str = str(event.path)
        
        # Create count record
        db_obj = Count(
            event_id=obj_in.event_id,
            location_id=obj_in.location_id,
            path=path_str,
            date=event.date,
            client_id=obj_in.client_id,
            adult_male=obj_in.adult_male,
            adult_female=obj_in.adult_female,
            youth_male=obj_in.youth_male,
            youth_female=obj_in.youth_female,
            boys=obj_in.boys,
            girls=obj_in.girls,
            note=obj_in.note,
            entered_by_id=user_id,
            status="pending"
        )
        
        # Calculate total
        db_obj.calculate_total()
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def get_by_client_id(self, db: AsyncSession, *, client_id: UUID) -> Optional[Count]:
        """Get count by client_id (for idempotency check)."""
        query = select(Count).where(Count.client_id == client_id)
        result = await db.execute(query)
        return result.scalars().first()
    
    async def get_multi_by_scope(
        self, 
        db: AsyncSession, 
        *, 
        scope_path: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Count]:
        """
        Get counts within a hierarchical scope.
        
        Args:
            db: Database session
            scope_path: ltree path for scope filtering
            skip: Pagination offset
            limit: Pagination limit
            
        Returns:
            List[Count]: Counts within scope
        """
        query = select(Count).where(
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
        ).offset(skip).limit(limit).order_by(Count.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()


count = CRUDCount(Count)
