"""
Authentication API routes.

Handles user login, token refresh, and current-user profile retrieval.

Security improvements over the original:
- Login returns HTTP 401 (not 400) for wrong credentials per RFC 6749.
- Brute-force protection via the in-process sliding-window rate limiter.
- Refresh tokens are now rotated on every use: old JTI is revoked in Postgres,
  a new token with a fresh JTI is issued.  Stealing a refresh token gives an
  attacker at most one use window before the legitimate holder invalidates it.
- Broad `except Exception` replaced with specific exception types.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.rate_limiter import check_rate_limit
from app.crud.crud_user import user as crud_user
from app.db.session import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.user import Token, UserResponse

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _best_role(user: User) -> tuple[int, str]:
    """Return (score, role_name) for the user's highest-ranked role."""
    score, role_name = 0, "Worker"
    if user.roles:
        best = max(user.roles, key=lambda r: r.score.score if r.score else 0)
        if best.score:
            score = best.score.score
            role_name = best.role_name
    return score, role_name


def _build_access_token(user: User, score: int, role_name: str, scope_path: str) -> str:
    return security.create_access_token(
        data={
            "sub": str(user.user_id),
            "email": user.email,
            "role": role_name,
            "score": score,
            "home_path": str(user.path),
            "scope_path": str(scope_path),
        },
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


async def _store_refresh_token(db: AsyncSession, user_id: str, jti: str) -> None:
    """Persist a newly issued refresh token JTI to Postgres."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    record = RefreshToken(
        jti=uuid.UUID(jti),
        user_id=uuid.UUID(user_id),
        expires_at=expires_at,
    )
    db.add(record)
    await db.commit()


async def _rotate_refresh_token(
    db: AsyncSession,
    old_jti: str,
    old_record: RefreshToken,
    user_id: str,
) -> tuple[str, str]:
    """
    Revoke old_record and issue a brand-new refresh token.

    Returns (new_token_string, new_jti).
    """
    # Revoke old token
    old_record.revoked = True
    old_record.revoked_at = datetime.now(timezone.utc)
    db.add(old_record)

    # Issue and persist new token
    new_token, new_jti = security.create_refresh_token(user_id=user_id)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    new_record = RefreshToken(
        jti=uuid.UUID(new_jti),
        user_id=uuid.UUID(user_id),
        expires_at=expires_at,
    )
    db.add(new_record)
    await db.commit()
    return new_token, new_jti


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=Token)
async def login_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    OAuth2 compatible token login.

    Rate limited to 5 attempts per minute per IP address.
    Returns access + refresh tokens on success.

    Raises:
        429 — rate limit exceeded.
        401 — incorrect credentials or inactive / unapproved account.
    """
    # ── Rate limit: 5 attempts / 60 s per IP ──────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(
        f"login:{client_ip}",
        max_requests=5,
        window_seconds=60,
    )

    # ── Authenticate ──────────────────────────────────────────────────────────
    user = await crud_user.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        # Use 401 (not 400) — per RFC 6749 §5.2 "invalid_client"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account has been deactivated. Please contact your administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.approval_status == "pending":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account is awaiting admin approval. Please contact your location pastor.",
        )
    if user.approval_status == "rejected":
        reason = user.rejection_reason or "No reason provided"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Your account was rejected. Reason: {reason}",
        )

    # ── Build tokens ──────────────────────────────────────────────────────────
    score, role_name = _best_role(user)
    scope_path = security.create_admin_access_id(user_path=str(user.path), score=score)

    access_token = _build_access_token(user, score, role_name, scope_path)
    refresh_token_str, jti = security.create_refresh_token(user_id=str(user.user_id))

    await _store_refresh_token(db, str(user.user_id), jti)

    logger.info("Login successful for user_id=%s scope=%s", user.user_id, scope_path)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token_str,
    }


@router.post("/refresh", response_model=Token)
async def refresh_token_endpoint(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Rotate a refresh token and issue a new access token.

    The refresh token must be passed in the Authorization header as
    ``Bearer <token>`` (same as access tokens).  On success the old token is
    revoked and a new refresh token is returned — stolen tokens become useless
    after the legitimate holder refreshes once.

    Raises:
        401 — missing / invalid / expired / already-revoked token.
        404 — user no longer exists.
    """
    auth_header = request.headers.get("Authorization", "")
    raw_token = ""
    if auth_header.lower().startswith("bearer "):
        raw_token = auth_header.split(" ", 1)[1].strip()
    else:
        try:
            body = await request.json()
        except Exception:
            body = {}
        if isinstance(body, dict):
            raw_token = str(body.get("refresh_token") or "").strip()

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token must be provided as a Bearer token or refresh_token body field",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Decode & validate claims ──────────────────────────────────────────────
    try:
        payload = security.verify_token(raw_token)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")
        user_id: str = payload["sub"]
        jti_str: str = payload["jti"]
    except (JWTError, KeyError, ValueError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Verify JTI against DB (rotation check) ────────────────────────────────
    try:
        jti_uuid = uuid.UUID(jti_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed refresh token",
        )

    token_record: RefreshToken | None = await db.get(RefreshToken, jti_uuid)
    if token_record is None or not token_record.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Load user (always fresh — no cache on refresh) ────────────────────────
    user = await crud_user.get(db, id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
        )

    # ── Rotate token ──────────────────────────────────────────────────────────
    score, role_name = _best_role(user)
    scope_path = security.create_admin_access_id(user_path=str(user.path), score=score)

    new_refresh_token, _ = await _rotate_refresh_token(db, jti_str, token_record, user_id)
    new_access_token = _build_access_token(user, score, role_name, scope_path)

    # Evict cached user so fresh role data is picked up immediately
    deps.invalidate_user_cache(user_id)

    logger.info("Token rotated for user_id=%s", user_id)

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "refresh_token": new_refresh_token,
    }


@router.get("/me", response_model=UserResponse)
async def read_users_me(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return the authenticated user's profile (roles and location included)."""
    return current_user
