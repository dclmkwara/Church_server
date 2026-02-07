from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.api import deps
from app.models.user import User
from app.services.statistics_service import StatisticsService

router = APIRouter()

class PopulationResponse(BaseModel):
    adult_male: int
    adult_female: int
    youth_male: int
    youth_female: int
    boys: int
    girls: int
    total: int
    average_men: int
    average_women: int
    average_adults: int
    average_youths: int
    average_children: int
    percentage_adult_male: Optional[float] = None
    percentage_adult_female: Optional[float] = None
    percentage_youth_male: Optional[float] = None
    percentage_youth_female: Optional[float] = None
    percentage_boys: Optional[float] = None
    percentage_girls: Optional[float] = None
    percentage_men: Optional[float] = None
    percentage_women: Optional[float] = None
    percentage_adults: Optional[float] = None
    percentage_youths: Optional[float] = None
    percentage_children: Optional[float] = None

class ChurchStatistics(BaseModel):
    total_locations: int
    total_groups: int
    total_regions: int
    adult_male: int
    adult_female: int
    youth_male: int
    youth_female: int
    boys: int
    girls: int
    total: int
    date: Optional[date] = None

class UserStatistics(BaseModel):
    active_user: int
    inactive_user: int
    registered_user: int

@router.get("/read-population/", response_model=PopulationResponse)
async def get_population_statistics(
    program_domain: Optional[str] = Query(None),
    program_type: Optional[str] = Query(None),
    location_id: Optional[str] = Query(None),
    date_filter: Optional[date] = Query(None, alias="date"),
    start_month: Optional[int] = Query(None, ge=1, le=12),
    end_month: Optional[int] = Query(None, ge=1, le=12),
    start_year: Optional[int] = Query(None, ge=1900, le=2100),
    end_year: Optional[int] = Query(None, ge=1900, le=2100),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get aggregated population statistics with demographics.
    Returns totals, averages, and percentages by gender and age groups.
    """
    scope_path = str(current_user.path)
    
    stats = await StatisticsService.get_population_statistics(
        db, scope_path, program_domain, program_type, location_id,
        date_filter, start_month, end_month, start_year, end_year
    )
    
    if not stats:
        raise HTTPException(status_code=404, detail="No population data found for the specified criteria")
    
    return stats

@router.get("/church-statistics/", response_model=ChurchStatistics)
async def get_church_statistics(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get church overview statistics including locations, groups, regions, and last program data.
    """
    scope_path = str(current_user.path)
    stats = await StatisticsService.get_church_statistics(db, scope_path)
    return stats

@router.get("/get-user-statistics/", response_model=UserStatistics)
async def get_user_statistics(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
):
    """
    Get user activity statistics (active, inactive, registered counts).
    """
    scope_path = str(current_user.path)
    stats = await StatisticsService.get_user_statistics(db, scope_path)
    return stats
