"""
CRUD operations for Programs and Events.
"""
from typing import List, Optional, Any
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.models.programs import ProgramDomain, ProgramType, ProgramEvent
from app.schemas.programs import (
    ProgramDomainCreate, ProgramDomainUpdate,
    ProgramTypeCreate, ProgramTypeUpdate,
    ProgramEventCreate, ProgramEventUpdate
)

class CRUDProgramDomain(CRUDBase[ProgramDomain, ProgramDomainCreate, ProgramDomainUpdate]):
    async def create(self, db: AsyncSession, *, obj_in: ProgramDomainCreate) -> ProgramDomain:
        # Check if slug exists
        if await self.get_by_slug(db, slug=obj_in.slug):
            raise HTTPException(status_code=400, detail="Program Domain slug already exists")
            
        return await super().create(db, obj_in=obj_in)

    async def get_by_slug(self, db: AsyncSession, *, slug: str) -> Optional[ProgramDomain]:
        query = select(ProgramDomain).where(ProgramDomain.slug == slug)
        result = await db.execute(query)
        return result.scalars().first()

program_domain = CRUDProgramDomain(ProgramDomain)


class CRUDProgramType(CRUDBase[ProgramType, ProgramTypeCreate, ProgramTypeUpdate]):
    async def create(self, db: AsyncSession, *, obj_in: ProgramTypeCreate) -> ProgramType:
        # Check domain exists
        domain = await program_domain.get(db, id=obj_in.domain_id)
        if not domain:
            raise HTTPException(status_code=404, detail="Program Domain not found")
            
        # Check if slug exists
        if await self.get_by_slug(db, slug=obj_in.slug):
            raise HTTPException(status_code=400, detail="Program Type slug already exists")
            
        return await super().create(db, obj_in=obj_in)

    async def get_by_slug(self, db: AsyncSession, *, slug: str) -> Optional[ProgramType]:
        query = select(ProgramType).where(ProgramType.slug == slug)
        result = await db.execute(query)
        return result.scalars().first()
        
    async def get_by_domain(self, db: AsyncSession, *, domain_id: int) -> List[ProgramType]:
        query = select(ProgramType).where(ProgramType.domain_id == domain_id)
        result = await db.execute(query)
        return result.scalars().all()

program_type = CRUDProgramType(ProgramType)


class CRUDProgramEvent(CRUDBase[ProgramEvent, ProgramEventCreate, ProgramEventUpdate]):
    async def create(self, db: AsyncSession, *, obj_in: ProgramEventCreate) -> ProgramEvent:
        # Check if type exists
        p_type = await program_type.get(db, id=obj_in.program_type_id)
        if not p_type:
            raise HTTPException(status_code=404, detail="Program Type not found")
            
        # Create event
        return await super().create(db, obj_in=obj_in)

    async def get_multi_by_scope(
        self, 
        db: AsyncSession, 
        *, 
        scope_path: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[ProgramEvent]:
        # Filter by path <@ scope_path
        query = select(ProgramEvent).where(
            text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path)
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()

program_event = CRUDProgramEvent(ProgramEvent)
