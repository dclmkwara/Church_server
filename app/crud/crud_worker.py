"""
CRUD operations for Worker management.

This module handles database operations for the Worker model, including:
- Registering new workers
- Managing worker profiles (transfers, unit assignment)
- Scoped worker retrieval (hierarchical filtering)
- Searching workers by phone/email

Workers are the base entity for all church members serving in any capacity.
They must belong to a valid location.
"""
from typing import List, Optional, Any
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.models.user import Worker
from app.schemas.user import WorkerCreate, WorkerUpdate
from app.models.core import generate_public_person_code


class CRUDWorker(CRUDBase[Worker, WorkerCreate, WorkerUpdate]):
    """
    CRUD operations for Worker model.
    """
    
    async def create(self, db: AsyncSession, *, obj_in: WorkerCreate) -> Worker:
        """
        Create a new worker with auto-generated ID and ltree path.
        
        The worker's path is automatically derived from the location_id.
        Public-facing IDs (for example, KW9029952120) are generated from the worker's state and phone number.
        
        Args:
            db: Database session
            obj_in: Worker creation data
            
        Returns:
            Worker: Created worker object
            
        Example:
            ```python
            worker = await crud_worker.create(db, obj_in=worker_data)
            ```
        """
        # Generate the public worker code from state + phone (for example, KW9029952120).
        base_code = generate_public_person_code(obj_in.state, obj_in.phone)
        generated_user_id = None
        for index in range(1, 100):
            candidate = base_code if index == 1 else f"{base_code}{index:02d}"
            exists = (await db.execute(select(Worker).where(Worker.user_id == candidate))).scalars().first()
            if not exists:
                generated_user_id = candidate
                break
        if not generated_user_id:
            raise HTTPException(status_code=500, detail="Failed to generate unique worker ID")
        
        # Derive ltree path from location_id
        # Assumes parse_display_id returns correct ltree string or look up location
        # NOTE: Ideally we should fetch the Location object to get its path strictly,
        # but parse_display_id is a helper if location_id is structured.
        # However, location_id is likely just "001" or UUID.
        # We really need to fetch the location to get the correct path inheritance.
        # But 'parse_display_id' was used in previous code. Let's keep existing logic request but improve safety.
        
        # IMPROVEMENT: Fetch location to ensure we inherit correct path
        from app.crud.crud_location import location
        loc = await location.get(db, obj_in.location_id)
        if not loc:
            raise HTTPException(status_code=404, detail="Invalid Location ID")
            
        path_str = str(loc.path)
        
        db_obj = Worker(
            # Standard fields
            location_id=obj_in.location_id,
            location_name=obj_in.location_name,
            church_type=obj_in.church_type,
            state=obj_in.state,
            region=obj_in.region,
            group=obj_in.group,
            name=obj_in.name,
            gender=obj_in.gender,
            phone=obj_in.phone,
            email=obj_in.email,
            address=obj_in.address,
            occupation=obj_in.occupation,
            marital_status=obj_in.marital_status,
            unit=obj_in.unit,
            status=obj_in.status,
            
            # Generated fields
            user_id=generated_user_id,
            path=path_str,
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_by_phone(self, db: AsyncSession, *, phone: str) -> Optional[Worker]:
        """
        Get worker by phone number.
        
        Args:
            db: Database session
            phone: Phone number string
            
        Returns:
            Optional[Worker]: Worker object if found
        """
        query = select(Worker).where(Worker.phone == phone)
        result = await db.execute(query)
        return result.scalars().first()

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[Worker]:
        """
        Get worker by email address.
        
        Args:
            db: Database session
            email: Email address string
            
        Returns:
            Optional[Worker]: Worker object if found
        """
        query = select(Worker).where(Worker.email == email)
        result = await db.execute(query)
        return result.scalars().first()

    async def get_multi_by_scope(
        self, 
        db: AsyncSession, 
        *, 
        scope_path: str, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Worker]:
        """
        Get all workers within a specific hierarchical scope.
        
        Uses PostgreSQL ltree '<@' operator to find all descendants of the scope path.
        
        Args:
            db: Database session
            scope_path: ltree path string (e.g., 'org.234.KW')
            skip: Pagination skip
            limit: Pagination limit
            
        Returns:
            List[Worker]: List of workers within the scope
            
        Example:
            ```python
            workers = await crud_worker.get_multi_by_scope(db, scope_path="org.234.KW")
            ```
        """
        query = select(Worker).where(
            text("CAST(path AS ltree) <@ CAST(:scope_path AS ltree)").bindparams(scope_path=scope_path),
            Worker.is_deleted == False,
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        result = result.scalars().all()
        return list(result)


worker = CRUDWorker(Worker)
