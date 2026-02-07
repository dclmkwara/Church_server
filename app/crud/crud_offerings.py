"""
CRUD operations for Offering records.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.models.offerings import Offering
from app.schemas.offerings import OfferingCreate, OfferingUpdate


class CRUDOffering(CRUDBase[Offering, OfferingCreate, OfferingUpdate]):
    """CRUD operations for Offering model with idempotency support."""
    
    async def create(self, db: AsyncSession, *, obj_in: OfferingCreate, user_id: UUID) -> Offering:
        """Create offering with idempotency check."""
        # Check for duplicate client_id
        if obj_in.client_id:
            existing = await self.get_by_client_id(db, client_id=obj_in.client_id)
            if existing:
                return existing
        
        # Verify event exists
        from app.crud.crud_programs import program_event
        event = await program_event.get(db, id=obj_in.event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        path_str = str(event.path)
        
        db_obj = Offering(
            event_id=obj_in.event_id,
            location_id=obj_in.location_id,
            path=path_str,
            date=event.date,
            client_id=obj_in.client_id,
            amount=obj_in.amount,
            payment_method=obj_in.payment_method,
            # Removed separate payer fields per user request
            note=obj_in.note,
            entered_by_id=user_id,
            status="pending"
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def get_by_client_id(self, db: AsyncSession, *, client_id: UUID) -> Optional[Offering]:
        """Get offering by client_id."""
        query = select(Offering).where(Offering.client_id == client_id)
        result = await db.execute(query)
        return result.scalars().first()
    
    async def get_multi_by_scope(
        self, 
        db: AsyncSession, 
        *, 
        scope_path: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Offering]:
        """Get offerings within scope."""
        query = select(Offering).where(
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
        ).offset(skip).limit(limit).order_by(Offering.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()


offering = CRUDOffering(Offering)
