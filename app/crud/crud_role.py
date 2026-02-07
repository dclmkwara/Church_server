"""
CRUD operations for Role and Permission models.
"""
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.user import Role, Permission, RoleScore
from app.schemas.user import RoleCreate, RoleBase


class CRUDRole(CRUDBase[Role, RoleCreate, RoleBase]):
    async def get_by_name(self, db: AsyncSession, *, name: str) -> Optional[Role]:
        """Get role by name."""
        query = select(Role).where(Role.role_name == name)
        result = await db.execute(query)
        return result.scalars().first()

    async def get_score_by_value(self, db: AsyncSession, *, score: int) -> Optional[RoleScore]:
        """Get role score object by integer value."""
        query = select(RoleScore).where(RoleScore.score == score)
        result = await db.execute(query)
        return result.scalars().first()
        
    async def create_with_score(
        self, db: AsyncSession, *, obj_in: RoleCreate
    ) -> Role:
        """
        Create a new role, linking it to the correct Score ID or value.
        """
        # If obj_in.score_id is actually a score value (1-9), find the ID
        # For MVP we assume the frontend passes the correct database ID for the score
        # But a helper here is useful
        
        db_obj = Role(
            role_name=obj_in.role_name,
            description=obj_in.description,
            score_id=obj_in.score_id
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj


role = CRUDRole(Role)
