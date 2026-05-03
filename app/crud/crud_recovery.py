import secrets
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.core.config import settings
from app.models.user import PasswordResetToken, User
from app.schemas.recovery import PasswordResetRequest, PasswordResetConfirm, RecoveryQuestionSetup, RecoveryQuestionUpdate
from app.core.security import hash_password

class CRUDRecovery:
    async def set_recovery_questions(self, db: AsyncSession, data: RecoveryQuestionSetup) -> User:
        """Set recovery questions and hashed answers for a user."""
        stmt = select(User).where(User.user_id == data.user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.recovery_question_one = data.recovery_question_one
        user.recovery_question_two = data.recovery_question_two
        user.recovery_answer_one = hash_password(data.recovery_answer_one)
        user.recovery_answer_two = hash_password(data.recovery_answer_two)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def get_recovery_questions(self, db: AsyncSession, user_id: UUID | str) -> Optional[User]:
        """Get recovery questions (without answers)."""
        stmt = select(User).where(User.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def update_recovery_questions(self, db: AsyncSession, user_id: UUID | str, data: RecoveryQuestionUpdate) -> User:
        """Update recovery questions and answers."""
        stmt = select(User).where(User.user_id == user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if data.recovery_question_one is not None:
            user.recovery_question_one = data.recovery_question_one
        if data.recovery_question_two is not None:
            user.recovery_question_two = data.recovery_question_two
        if data.recovery_answer_one is not None:
            user.recovery_answer_one = hash_password(data.recovery_answer_one)
        if data.recovery_answer_two is not None:
            user.recovery_answer_two = hash_password(data.recovery_answer_two)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user
    async def create_token(self, db: AsyncSession, email: str) -> Optional[PasswordResetToken]:
        # Check if user exists
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalars().first()
        
        if not user:
            return None # Don't reveal if user exists or not, but return None to controller
            
        token = secrets.token_urlsafe(32)
        expiration = int(
            (
                datetime.now()
                + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
            ).timestamp()
        )
        
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
