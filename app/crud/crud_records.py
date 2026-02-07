"""
CRUD operations for Record (newcomer/convert) records.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.models.records import Record
from app.schemas.records import RecordCreate, RecordUpdate


class CRUDRecord(CRUDBase[Record, RecordCreate, RecordUpdate]):
    """CRUD operations for Record model with idempotency support."""
    
    async def create(self, db: AsyncSession, *, obj_in: RecordCreate, user_id: UUID) -> Record:
        """Create record with idempotency check."""
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
        
        db_obj = Record(
            event_id=obj_in.event_id,
            location_id=obj_in.location_id,
            path=path_str,
            client_id=obj_in.client_id,
            record_type=obj_in.record_type,
            name=obj_in.name,
            gender=obj_in.gender,
            phone=obj_in.phone,
            details=obj_in.details, # JSONB field
            note=obj_in.note,
            entered_by_id=user_id,
            status="pending"
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    
    async def get_by_client_id(self, db: AsyncSession, *, client_id: UUID) -> Optional[Record]:
        """Get record by client_id."""
        query = select(Record).where(Record.client_id == client_id)
        result = await db.execute(query)
        return result.scalars().first()
    
    async def get_multi_by_scope(
        self, 
        db: AsyncSession, 
        *, 
        scope_path: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Record]:
        """Get records within scope."""
        query = select(Record).where(
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
        ).offset(skip).limit(limit).order_by(Record.created_at.desc())
        
        result = await db.execute(query)
        return result.scalars().all()


record = CRUDRecord(Record)
