"""Read-only analytics endpoints shared by the admin and field reporting views."""
from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.services.analytics.program_occurrences import get_program_occurrences

router = APIRouter()


@router.get("/programs/occurrences", dependencies=[Depends(deps.PermissionChecker("statistics:read"))])
async def read_program_occurrences(
    scope_path: str | None = Query(None),
    domain: str | None = Query(None),
    program_type: str | None = Query(None),
    program_level: str | None = Query(None),
    event_id: UUID | None = Query(None),
    campaign_id: UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    include_pending: bool = Query(False),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict[str, Any]:
    effective_scope = deps.resolve_scope_path(current_user, scope_path)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=400, detail="date_from must be on or before date_to")
    if program_level and program_level.lower() not in {"location", "group", "region", "state"}:
        raise HTTPException(status_code=400, detail="Invalid program_level")
    return await get_program_occurrences(
        db, scope_path=effective_scope, domain=domain, program_type=program_type,
        program_level=program_level, event_id=event_id, campaign_id=campaign_id,
        date_from=date_from, date_to=date_to, include_pending=include_pending,
    )
