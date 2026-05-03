from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.services.notification_service import NotificationService

router = APIRouter()


class NotificationHistoryItem(BaseModel):
    notification_key: str
    source_id: str
    kind: str
    title: str
    body: str
    priority: str
    status: str
    created_at: datetime | None = None
    read_at: datetime | None = None


class NotificationStatusResponse(BaseModel):
    notification_key: str
    status: str
    read_at: datetime | None = None

@router.get(
    "/poll",
    response_model=Dict[str, List[Any]],
    dependencies=[Depends(deps.PermissionChecker("notifications:read"))],
)
async def poll_notifications(
    since: datetime = Query(..., description="Timestamp to check for new data since"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return per notification bucket"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Poll for new data (counts, offerings, attendance, etc.) created since the provided timestamp.
    Used for client-side notifications.
    """
    scope_path = str(current_user.path)
    return await NotificationService.poll_new_data(db, scope_path, since, per_bucket_limit=limit)


@router.get(
    "/history",
    response_model=List[NotificationHistoryItem],
    dependencies=[Depends(deps.PermissionChecker("notifications:read"))],
)
async def list_notification_history(
    since: datetime | None = Query(None, description="Timestamp to check notification history from"),
    days: int = Query(14, ge=1, le=90, description="Fallback day window when since is not supplied"),
    kind: str = Query("all", description="Filter by notification bucket kind"),
    limit: int = Query(200, ge=1, le=500, description="Maximum items to return"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Get a flat notification history feed for the current user and scope.
    """
    effective_since = since or (datetime.now(timezone.utc) - timedelta(days=days))
    return await NotificationService.history(
        db,
        scope_path=str(current_user.path),
        user_id=current_user.user_id,
        since=effective_since,
        kind=kind,
        limit=limit,
    )


@router.post(
    "/{notification_key}/read",
    response_model=NotificationStatusResponse,
    dependencies=[Depends(deps.PermissionChecker("notifications:read"))],
)
async def mark_notification_read(
    notification_key: str = Path(..., description="Notification item key"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Mark a notification item as read for the current user.
    """
    return await NotificationService.set_read_state(
        db,
        user_id=current_user.user_id,
        notification_key=notification_key,
        read=True,
    )


@router.post(
    "/{notification_key}/unread",
    response_model=NotificationStatusResponse,
    dependencies=[Depends(deps.PermissionChecker("notifications:read"))],
)
async def mark_notification_unread(
    notification_key: str = Path(..., description="Notification item key"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Mark a notification item as unread for the current user.
    """
    return await NotificationService.set_read_state(
        db,
        user_id=current_user.user_id,
        notification_key=notification_key,
        read=False,
    )
