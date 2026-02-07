"""
CRUD operations for User management.

This module handles database operations for the User model, including:
- Creating users linked to Workers
- Authenticating users via phone/password
- Managing user roles and permissions
- Updating user profile information
- Hash password handling

Users are the authentication entity, while Workers contain the profile data.
"""
from typing import List, Optional, Any, Dict, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.user import User, Role
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import hash_password, verify_password


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """
    CRUD operations for User model.
    """
    
    async def get(self, db: AsyncSession, id: Any) -> Optional[User]:
        """
        Get user by ID with eager loaded roles.
        
        Args:
            db: Database session dependency
            id: User UUID
            
        Returns:
            Optional[User]: User object with roles loaded if found, else None
            
        Example:
            ```python
            user = await crud_user.get(db, id=user_id)
            ```
        """
        query = select(User).where(User.user_id == id).options(
            selectinload(User.roles).options(
                selectinload(Role.score),
                selectinload(Role.permissions)
            )
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        """
        Create a new user linked to an existing worker.
        
        Fetches denormalized data (name, phone, location, path) from the
        Worker model and creates a User account for authentication.
        
        Args:
            db: Database session
            obj_in: User creation data (worker_id, password, etc.)
            
        Returns:
            User: Created user object
            
        Raises:
            ValueError: If worker is not found
            
        Example:
            ```python
            user_in = UserCreate(
                worker_id=worker_uuid,
                password="secret_password",
                email="user@example.com"
            )
            user = await crud_user.create(db, obj_in=user_in)
            ```
        """
        # 1. Fetch worker to get denormalized data
        # We import here to avoid circular dependencies at module level
        from app.models.user import Worker
        
        query = select(Worker).where(Worker.worker_id == obj_in.worker_id)
        result = await db.execute(query)
        worker = result.scalars().first()
        
        if not worker:
            raise ValueError("Worker not found")

        # 2. Fetch roles if provided
        roles = []
        if obj_in.roles:
            stmt = select(Role).where(Role.id.in_(obj_in.roles))
            result = await db.execute(stmt)
            roles = result.scalars().all()

        # 3. Create User with hashed password
        db_obj = User(
            worker_id=obj_in.worker_id,
            password=hash_password(obj_in.password),
            is_active=obj_in.is_active,
            
            # Denormalized fields from Worker
            location_id=worker.location_id,
            name=worker.name,
            phone=worker.phone,
            email=obj_in.email,
            path=worker.path,
            
            # Relationships
            roles=roles
        )
        
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        
        # Re-fetch to ensure eager loading
        return await self.get(db, id=db_obj.user_id)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: User,
        obj_in: Union[UserUpdate, Dict[str, Any]]
    ) -> User:
        """
        Update a user.
        
        Handles password hashing if a new password is provided. Also manages
        role updates if 'roles' list of IDs is included.
        
        Args:
            db: Database session
            db_obj: Existing User object
            obj_in: Update data (schema or dict)
            
        Returns:
            User: Updated user object
            
        Example:
            ```python
            update_data = {"is_active": False, "roles": [1, 2]}
            user = await crud_user.update(db, db_obj=user, obj_in=update_data)
            ```
        """
        if isinstance(obj_in, dict):
            update_data = obj_in.copy()
        else:
            update_data = obj_in.dict(exclude_unset=True)
            
        # Hash password if present
        if "password" in update_data and update_data["password"]:
            update_data["password"] = hash_password(update_data["password"])
            
        # Handle role updates separately
        role_ids = update_data.pop("roles", None)
        
        # Update standard fields
        await super().update(db, db_obj=db_obj, obj_in=update_data)
        
        # Update roles if provided
        if role_ids is not None:
            await self.assign_roles(db, user=db_obj, role_ids=role_ids)
            
        return await self.get(db, id=db_obj.user_id)

    async def assign_roles(self, db: AsyncSession, *, user: User, role_ids: List[int]) -> User:
        """
        Assign roles to a user (replaces existing roles).
        
        Args:
            db: Database session
            user: User object
            role_ids: List of Role IDs to assign
            
        Returns:
            User: Updated user with new roles
            
        Example:
            ```python
            await crud_user.assign_roles(db, user=user, role_ids=[1, 2])
            ```
        """
        # Fetch roles
        stmt = select(Role).where(Role.id.in_(role_ids))
        result = await db.execute(stmt)
        roles = result.scalars().all()
        
        # Set roles (SQLAlchemy handles the association table update)
        user.roles = roles
        await db.commit()
        await db.refresh(user)
        return await self.get(db, id=user.user_id)

    async def get_by_email(self, db: AsyncSession, *, email: str) -> Optional[User]:
        """
        Get user by email address.
        
        Args:
            db: Database session
            email: Email address
            
        Returns:
            Optional[User]: User object if found
        """
        query = select(User).where(User.email == email)
        result = await db.execute(query)
        return result.scalars().first()
    
    async def get_by_phone(self, db: AsyncSession, *, phone: str) -> Optional[User]:
        """
        Get user by phone number with roles eager loaded.
        
        Args:
            db: Database session
            phone: Phone number
            
        Returns:
            Optional[User]: User object if found
        """
        query = select(User).where(User.phone == phone).options(
            selectinload(User.roles).selectinload(Role.score)
        )
        result = await db.execute(query)
        return result.scalars().first()

    async def authenticate(self, db: AsyncSession, *, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user by email and password.
        
        Args:
            db: Database session
            email: User's email address
            password: Plain text password
            
        Returns:
            Optional[User]: User object if authentication succeeds, else None
            
        Example:
            ```python
            user = await crud_user.authenticate(db, email="user@example.com", password="pass")
            ```
        """
        # Query user by email with eager loaded roles
        query = select(User).where(User.email == email).options(
            selectinload(User.roles).options(
                selectinload(Role.score),
                selectinload(Role.permissions)
            )
        )
        result = await db.execute(query)
        user = result.scalars().first()
        
        if not user:
            return None
        if not verify_password(password, user.password):
            return None
        return user

    async def is_active(self, user: User) -> bool:
        """
        Check if user is active.
        
        Args:
            user: User object
            
        Returns:
            bool: True if active
        """
        return user.is_active


user = CRUDUser(User)
