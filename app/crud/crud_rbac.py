from typing import List, Optional, Any, Union, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi.encoders import jsonable_encoder

from app.crud.base import CRUDBase
from app.models.user import Role, Permission, RoleScore
from app.schemas.rbac import (
    RoleCreate, RoleUpdate, 
    PermissionCreate, PermissionUpdate,
    RoleScoreCreate, RoleScoreUpdate
)

class CRUDRole(CRUDBase[Role, RoleCreate, RoleUpdate]):
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
        await db.refresh(db_obj)
        return db_obj

    async def update_with_permissions(
        self, db: AsyncSession, *, db_obj: Role, obj_in: Union[RoleUpdate, Dict[str, Any]]
    ) -> Role:
        obj_data = jsonable_encoder(db_obj)
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
                db_obj.permissions = list(permissions)

        return await super().update(db, db_obj=db_obj, obj_in=update_data)

class CRUDPermission(CRUDBase[Permission, PermissionCreate, PermissionUpdate]):
    pass

class CRUDRoleScore(CRUDBase[RoleScore, RoleScoreCreate, RoleScoreUpdate]):
    pass

role = CRUDRole(Role)
permission = CRUDPermission(Permission)
role_score = CRUDRoleScore(RoleScore)
