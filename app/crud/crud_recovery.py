import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.crud.base import CRUDBase
from app.core.config import settings
from app.models.user import PasswordResetToken, User
from app.schemas.recovery import PasswordResetRequest, PasswordResetConfirm, RecoveryQuestionSetup, RecoveryQuestionUpdate
from app.core.security import hash_password
from app.core.auth_cache import invalidate_user_cache
from app.models.refresh_token import RefreshToken
from app.db.session import inject_auth_email, inject_auth_user, inject_reset_token

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
        await inject_auth_email(db, email)
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalars().first()
        
        if not user:
            return None # Don't reveal if user exists or not, but return None to controller

        await inject_auth_user(db, str(user.user_id))
            
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
        await inject_reset_token(db, token)
        stmt = select(PasswordResetToken).where(
            PasswordResetToken.token == token,
            PasswordResetToken.is_used == False,
            PasswordResetToken.expiration > int(datetime.now().timestamp())
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def reset_password(self, db: AsyncSession, token: str, new_password: str) -> bool:
        await inject_reset_token(db, token)
        now = datetime.now(timezone.utc)
        claim = await db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.token == token,
                PasswordResetToken.is_used.is_(False),
                PasswordResetToken.expiration > int(now.timestamp()),
            )
            .values(is_used=True)
            .returning(PasswordResetToken.user_id)
        )
        user_id = claim.scalar_one_or_none()
        if user_id is None:
            await db.rollback()
            return False

        await inject_auth_user(db, str(user_id))
            
        # Get user
        stmt = select(User).where(User.user_id == user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()
        
        if not user:
            await db.rollback()
            return False
            
        # Update password
        user.password = hash_password(new_password)

        # A password reset ends all persisted refresh sessions for this user.
        await db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user.user_id,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True, revoked_at=datetime.now(timezone.utc))
        )
        
        db.add(user)
        await db.commit()
        invalidate_user_cache(str(user.user_id))
        return True

recovery = CRUDRecovery()
