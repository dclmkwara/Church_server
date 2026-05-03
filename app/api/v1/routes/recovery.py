import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.api import deps
from app.crud.crud_recovery import recovery
from app.schemas.recovery import (
    PasswordResetRequest, PasswordResetConfirm, PasswordResetResponse, PasswordResetVerify,
    RecoveryQuestionSetup, RecoveryQuestionUpdate, RecoveryQuestionResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/request-reset", response_model=PasswordResetResponse)
async def request_password_reset(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Request a password reset token.
    """
    token = await recovery.create_token(db, email=request.email)
    
    if token:
        logger.info("Password reset token created for email=%s", request.email)
    
    # Always return success to prevent user enumeration
    return {"message": "If an account exists with this email, a reset link has been sent."}

@router.post("/verify-token", response_model=PasswordResetResponse)
async def verify_reset_token(
    verify: PasswordResetVerify,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Verify if a reset token is valid.
    """
    token = await recovery.verify_token(db, token=verify.token)
    if not token:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
        
    return {"message": "Token is valid"}

@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(
    confirm: PasswordResetConfirm,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Reset password using a valid token.
    """
    success = await recovery.reset_password(db, token=confirm.token, new_password=confirm.new_password)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
        
    return {"message": "Password reset successfully"}


@router.post("/set-recovery-question", response_model=RecoveryQuestionResponse)
async def set_recovery_question(
    data: RecoveryQuestionSetup,
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    """Set recovery questions for a user."""
    deps.ensure_same_user(current_user, data.user_id)
    user = await recovery.set_recovery_questions(db, data)
    return RecoveryQuestionResponse(
        user_id=str(user.user_id),
        recovery_question_one=user.recovery_question_one,
        recovery_question_two=user.recovery_question_two
    )


@router.get("/read-recovery-question", response_model=RecoveryQuestionResponse)
async def read_recovery_question(
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    """Read recovery questions for the current user."""
    user = await recovery.get_recovery_questions(db, current_user.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return RecoveryQuestionResponse(
        user_id=str(user.user_id),
        recovery_question_one=user.recovery_question_one,
        recovery_question_two=user.recovery_question_two
    )


@router.patch("/update-recovery-question", response_model=RecoveryQuestionResponse)
async def update_recovery_question(
    data: RecoveryQuestionUpdate,
    db: AsyncSession = Depends(deps.get_db),
    current_user=Depends(deps.get_current_active_user),
) -> Any:
    """Update recovery questions for the current user."""
    user = await recovery.update_recovery_questions(db, current_user.user_id, data)
    return RecoveryQuestionResponse(
        user_id=str(user.user_id),
        recovery_question_one=user.recovery_question_one,
        recovery_question_two=user.recovery_question_two
    )
