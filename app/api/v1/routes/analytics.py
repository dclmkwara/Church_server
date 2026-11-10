"""Read-only analytics endpoints shared by the admin and field reporting views."""
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.services.analytics.program_occurrences import get_program_occurrences
from app.services.analytics.program_config import STANDING_PROGRAMS, reporting_today
from app.services.analytics.sunday_worship import SundayWorshipAnalytics

router = APIRouter()

_POPULATION_PROGRAM_KEYS = {
    "sunday_worship_service", "house_caring_fellowship",
    "monday_bible_study", "thursday_revival_hour",
}


@router.get("/standing-programs/series", dependencies=[Depends(deps.PermissionChecker("statistics:read"))])
async def read_standing_program_series(
    scope_path: str | None = Query(None),
    program_key: str = Query("sunday_worship_service"),
    weeks: int = Query(4, ge=4, le=8),
    latest_date: date | None = Query(None),
    include_pending: bool = Query(False),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict[str, Any]:
    """Return one standing population program through the shared occurrence calculator."""
    if program_key not in _POPULATION_PROGRAM_KEYS:
        raise HTTPException(status_code=422, detail="Choose Sunday Worship, House Caring Fellowship, Monday Bible Study, or Thursday Revival Hour")
    program = STANDING_PROGRAMS[program_key]
    scope = deps.resolve_scope_path(current_user, scope_path)
    today = reporting_today()
    latest = latest_date or (today - timedelta(days=(today.weekday() - int(program.weekday)) % 7))
    if latest.weekday() != program.weekday:
        raise HTTPException(status_code=422, detail=f"latest_date must fall on {program.label}'s configured day")
    occurrence_dates = [latest - timedelta(weeks=index) for index in reversed(range(weeks))]
    result = await SundayWorshipAnalytics.series(
        db, scope, occurrence_dates=occurrence_dates,
        include_pending=include_pending, program_key=program_key,
    )
    result["program_type"] = program_key
    result["program_label"] = program.label
    result["include_pending"] = include_pending
    return result


@router.get("/programs/occurrences", dependencies=[Depends(deps.PermissionChecker("statistics:read"))])
async def read_program_occurrences(
    scope_path: str | None = Query(None),
    domain: str | None = Query(None),
    program_type: str | None = Query(None),
    program_level: str | None = Query(None),
    event_id: UUID | None = Query(None),
    campaign_id: UUID | None = Query(None),
    compare_campaign_id: UUID | None = Query(None),
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
        compare_campaign_id=compare_campaign_id,
        date_from=date_from, date_to=date_to, include_pending=include_pending,
    )
