import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.models.user import PasswordResetToken, User
from app.schemas.recovery import PasswordResetRequest, PasswordResetConfirm
from app.core.security import hash_password

class CRUDRecovery:
    async def create_token(self, db: AsyncSession, email: str) -> Optional[PasswordResetToken]:
        # Check if user exists
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalars().first()
        
        if not user:
            return None # Don't reveal if user exists or not, but return None to controller
            
        token = secrets.token_urlsafe(32)
        expiration = int((datetime.now() + timedelta(hours=1)).timestamp())
        
        db_obj = PasswordResetToken(
            user_id=user.user_id,
            token=token,
            expiration=expiration,
            is_used=False
        )
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def verify_token(self, db: AsyncSession, token: str) -> Optional[PasswordResetToken]:
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token == token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expiration > int(datetime.now().timestamp())
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def reset_password(self, db: AsyncSession, token: str, new_password: str) -> bool:
        reset_token = await self.verify_token(db, token)
        if not reset_token:
            return False
            
        # Get user
        stmt = select(User).where(User.user_id == reset_token.user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        
        if not user:
            return False
            
        # Update password
        user.password = hash_password(new_password)
        reset_token.is_used = True
        
        db.add(user)
        db.add(reset_token)
        await db.commit()
        return True

recovery = CRUDRecovery()
