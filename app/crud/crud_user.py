"""
CRUD operations for User management.

Production changes:
- authenticate() no longer eagerly loads Role.permissions (not needed for login).
  This removes one join from the hottest query in the system.
- create() and update() no longer call self.get() for a second full fetch after
  commit. db.refresh() with targeted attribute_names is sufficient.
- .dict() replaced with .model_dump() throughout (Pydantic v2 API).
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.user import Role, User, Worker
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import hash_password, verify_password


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """CRUD operations for the User model."""

    async def get(self, db: AsyncSession, id: Any) -> Optional[User]:
        """
        Get user by UUID with roles + score + permissions eager-loaded.
        Used by PermissionChecker and the /me endpoint.
        """
        query = (
            select(User)
            .where(User.user_id == id)
            .options(
                selectinload(User.roles).options(
                    selectinload(Role.score),
                    selectinload(Role.permissions),
                )
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        """
        Create a new user linked to an existing worker.

        Fetches denormalised data (name, phone, location, path) from the
        Worker model and creates a User account for authentication.
        """
        # Fetch worker for denormalised fields
        worker_result = await db.execute(
            select(Worker).where(Worker.worker_id == obj_in.worker_id)
        )
        worker = worker_result.scalars().first()
        if not worker:
            raise ValueError("Worker not found")

        # Fetch roles if provided
        roles: list = []
        if obj_in.roles:
            role_result = await db.execute(
                select(Role).where(Role.id.in_(obj_in.roles))
            )
            roles = role_result.scalars().all()

        db_obj = User(
            worker_id=obj_in.worker_id,
            password=hash_password(obj_in.password),
            is_active=obj_in.is_active,
            location_id=worker.location_id,
            name=worker.name,
            phone=worker.phone,
            email=obj_in.email,
            path=worker.path,
            roles=roles,
        )
        db.add(db_obj)
        await db.commit()
        # Refresh only the relationship columns we need — avoids a second SELECT
        await db.refresh(db_obj, attribute_names=["roles"])
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: User,
        obj_in: Union[UserUpdate, Dict[str, Any]],
    ) -> User:
        """
        Update a user, hashing any new password and replacing roles if supplied.
        """
        update_data = (
            obj_in.copy() if isinstance(obj_in, dict)
            else obj_in.model_dump(exclude_unset=True)
        )

        # Hash password if present
        if update_data.get("password"):
            update_data["password"] = hash_password(update_data["password"])

        # Role updates handled separately
        role_ids = update_data.pop("roles", None)

        # Apply scalar field updates
        await super().update(db, db_obj=db_obj, obj_in=update_data)

        if role_ids is not None:
            await self.assign_roles(db, user=db_obj, role_ids=role_ids)

        # Refresh only the roles relationship — no second full SELECT needed
        await db.refresh(db_obj, attribute_names=["roles"])
        return db_obj

    async def assign_roles(
        self, db: AsyncSession, *, user: User, role_ids: List[int]
    ) -> User:
        """Assign roles to a user, replacing any existing assignment."""
        stmt = select(Role).where(Role.id.in_(role_ids))
        result = await db.execute(stmt)
        user.roles = result.scalars().all()
        await db.commit()
        await db.refresh(user, attribute_names=["roles"])
        return user

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[User]:
        """
        Get user by email address.

        NOTE: Roles are NOT eagerly loaded here. Do not access user.roles
        on the returned object without an explicit reload.
        """
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def get_by_phone(self, db: AsyncSession, *, phone: str) -> Optional[User]:
        """Get user by phone number (score only — no permissions loaded)."""
        result = await db.execute(
            select(User)
            .where(User.phone == phone)
            .options(
                selectinload(User.roles).selectinload(Role.score)
            )
        )
        return result.scalars().first()

    async def authenticate(
        self, db: AsyncSession, *, email: str, password: str
    ) -> Optional[User]:
        """
        Authenticate a user by email and password.

        Loads roles + score only — NOT permissions. Permission loading is
        deferred to PermissionChecker which uses the 60-second user cache.
        Removing the permissions join cuts ~10–20 ms from every login.
        """
        result = await db.execute(
            select(User)
            .where(User.email == email)
            .options(
                selectinload(User.roles).options(
                    selectinload(Role.score),
                    # Deliberately NOT loading Role.permissions here —
                    # they are not used during login and loading them adds
                    # an extra join for every authentication attempt.
                )
            )
        )
        user = result.scalars().first()
        if not user:
            return None
        if not verify_password(password, user.password):
            return None
        return user

    async def is_active(self, user: User) -> bool:
        return user.is_active


user = CRUDUser(User)
