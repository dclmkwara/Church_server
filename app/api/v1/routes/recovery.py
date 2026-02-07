from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from app.api import deps
from app.crud.crud_recovery import recovery
from app.schemas.recovery import PasswordResetRequest, PasswordResetConfirm, PasswordResetResponse, PasswordResetVerify

router = APIRouter()

@router.post("/request-reset", response_model=PasswordResetResponse)
async def request_password_reset(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Request a password reset token. 
    In production, this would send an email. For now, it logs the token (mock behavior).
    """
    token = await recovery.create_token(db, email=request.email)
    
    if token:
        # MOCK EMAIL SENDING
        print(f"============================================")
        print(f"MOCK EMAIL TO: {request.email}")
        print(f"RESET TOKEN: {token.token}")
        print(f"============================================")
    
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
