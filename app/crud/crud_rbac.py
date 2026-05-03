from typing import List, Optional, Any, Union, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.user import Role, Permission, RoleScore
from app.schemas.rbac import (
    RoleCreate, RoleUpdate, 
    PermissionCreate, PermissionUpdate,
    RoleScoreCreate, RoleScoreUpdate
)

class CRUDRole(CRUDBase[Role, RoleCreate, RoleUpdate]):
    async def get_with_permissions(self, db: AsyncSession, id: int) -> Optional[Role]:
        stmt = (
            select(Role)
            .where(Role.id == id)
            .options(selectinload(Role.permissions), selectinload(Role.score))
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create_with_permissions(
        self, db: AsyncSession, *, obj_in: RoleCreate
    ) -> Role:
        # Create role
        db_obj = Role(
            role_name=obj_in.role_name,
            description=obj_in.description,
            score_id=obj_in.score_id
        )
        
        # Add permissions if provided
        if obj_in.permission_ids:
            stmt = select(Permission).where(Permission.id.in_(obj_in.permission_ids))
            permissions = (await db.execute(stmt)).scalars().all()
            db_obj.permissions = list(permissions)
            
        db.add(db_obj)
        await db.commit()
        role_with_permissions = await self.get_with_permissions(db, db_obj.id)
        return role_with_permissions or db_obj

    async def update_with_permissions(
        self, db: AsyncSession, *, db_obj: Role, obj_in: Union[RoleUpdate, Dict[str, Any]]
    ) -> Role:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
            
        # Handle permissions update separate from main update
        if "permission_ids" in update_data:
            permission_ids = update_data.pop("permission_ids")
            if permission_ids is not None:
                stmt = select(Permission).where(Permission.id.in_(permission_ids))
                permissions = (await db.execute(stmt)).scalars().all()
                await db.refresh(db_obj, attribute_names=["permissions"])
                db_obj.permissions = list(permissions)

        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        role_with_permissions = await self.get_with_permissions(db, db_obj.id)
        return role_with_permissions or db_obj

class CRUDPermission(CRUDBase[Permission, PermissionCreate, PermissionUpdate]):
    pass

class CRUDRoleScore(CRUDBase[RoleScore, RoleScoreCreate, RoleScoreUpdate]):
    pass

role = CRUDRole(Role)
permission = CRUDPermission(Permission)
role_score = CRUDRoleScore(RoleScore)
