from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, List, Any

from app.api import deps
from app.models.user import User
from app.services.notification_service import NotificationService

router = APIRouter()

@router.get("/poll", response_model=Dict[str, List[Any]])
async def poll_notifications(
    since: datetime = Query(..., description="Timestamp to check for new data since"),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Poll for new data (counts, offerings, attendance, etc.) created since the provided timestamp.
    Used for client-side notifications.
    """
    scope_path = str(current_user.path)
    return await NotificationService.poll_new_data(db, scope_path, since)
