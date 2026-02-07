"""
Statistics service for aggregated analytics.
"""
from typing import Optional
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, extract, cast, Integer
from app.models.counts import Count
from app.models.location import Location, Group, Region
from app.models.user import User

class StatisticsService:
    @staticmethod
    async def get_population_statistics(
        db: AsyncSession,
        scope_path: str,
        program_domain: Optional[str] = None,
        program_type: Optional[str] = None,
        location_id: Optional[str] = None,
        date_filter: Optional[date] = None,
        start_month: Optional[int] = None,
        end_month: Optional[int] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None
    ) -> dict:
        """
        Get aggregated population statistics with demographics.
        Returns totals, averages, and percentages.
        """
        # Build filters
        filters = [
            (Count.path.op('<@')(scope_path)) | (Count.path == scope_path),
            Count.is_deleted == False
        ]
        
        if program_domain:
            filters.append(Count.program_domain == program_domain)
        if program_type:
            filters.append(Count.program_type == program_type)
        if location_id:
            filters.append(Count.location_id == location_id)
        if date_filter:
            filters.append(Count.created_at >= date_filter)
        if start_year:
            filters.append(extract('year', Count.created_at) >= start_year)
        if end_year:
            filters.append(extract('year', Count.created_at) <= end_year)
        if start_month:
            filters.append(extract('month', Count.created_at) >= start_month)
        if end_month:
            filters.append(extract('month', Count.created_at) <= end_month)
        
        # Execute aggregation query
        stmt = select(
            func.coalesce(func.sum(Count.adult_male), 0).label("adult_male"),
            func.coalesce(func.sum(Count.adult_female), 0).label("adult_female"),
            func.coalesce(func.sum(Count.youth_male), 0).label("youth_male"),
            func.coalesce(func.sum(Count.youth_female), 0).label("youth_female"),
            func.coalesce(func.sum(Count.boys), 0).label("boys"),
            func.coalesce(func.sum(Count.girls), 0).label("girls"),
            func.coalesce(func.sum(Count.total), 0).label("total"),
            func.count().label("program_count")
        ).where(and_(*filters))
        
        result = await db.execute(stmt)
        row = result.one_or_none()
        
        if not row or row.program_count == 0:
            return {}
        
        # Calculate averages
        avg_data = {
            "adult_male": int(round(row.adult_male / row.program_count, 0)),
            "adult_female": int(round(row.adult_female / row.program_count, 0)),
            "youth_male": int(round(row.youth_male / row.program_count, 0)),
            "youth_female": int(round(row.youth_female / row.program_count, 0)),
            "boys": int(round(row.boys / row.program_count, 0)),
            "girls": int(round(row.girls / row.program_count, 0)),
            "total": int(round(row.total / row.program_count, 0)),
            "average_men": int(round((row.adult_male + row.youth_male + row.boys) / row.program_count, 0)),
            "average_women": int(round((row.adult_female + row.youth_female + row.girls) / row.program_count, 0)),
            "average_adults": int(round((row.adult_male + row.adult_female) / row.program_count, 0)),
            "average_youths": int(round((row.youth_male + row.youth_female) / row.program_count, 0)),
            "average_children": int(round((row.boys + row.girls) / row.program_count, 0))
        }
        
        # Calculate percentages
        if row.total > 0:
            percentages = {
                "percentage_adult_male": round((row.adult_male / row.total) * 100, 1),
                "percentage_adult_female": round((row.adult_female / row.total) * 100, 1),
                "percentage_youth_male": round((row.youth_male / row.total) * 100, 1),
                "percentage_youth_female": round((row.youth_female / row.total) * 100, 1),
                "percentage_boys": round((row.boys / row.total) * 100, 1),
                "percentage_girls": round((row.girls / row.total) * 100, 1),
                "percentage_men": round(((row.adult_male + row.youth_male + row.boys) / row.total) * 100, 1),
                "percentage_women": round(((row.adult_female + row.youth_female + row.girls) / row.total) * 100, 1),
                "percentage_adults": round(((row.adult_male + row.adult_female) / row.total) * 100, 1),
                "percentage_youths": round(((row.youth_male + row.youth_female) / row.total) * 100, 1),
                "percentage_children": round(((row.boys + row.girls) / row.total) * 100, 1)
            }
        else:
            percentages = {}
        
        return {**avg_data, **percentages}
    
    @staticmethod
    async def get_church_statistics(db: AsyncSession, scope_path: str) -> dict:
        """
        Get church overview statistics.
        """
        # Count locations
        loc_stmt = select(func.count(Location.location_id.distinct())).where(
            (Location.path.op('<@')(scope_path)) | (Location.path == scope_path)
        )
        loc_result = await db.execute(loc_stmt)
        total_locations = loc_result.scalar() or 0
        
        # Count groups
        grp_stmt = select(func.count(Group.group_id.distinct())).where(
            (Group.path.op('<@')(scope_path)) | (Group.path == scope_path)
        )
        grp_result = await db.execute(grp_stmt)
        total_groups = grp_result.scalar() or 0
        
        # Count regions
        reg_stmt = select(func.count(Region.region_id.distinct())).where(
            (Region.path.op('<@')(scope_path)) | (Region.path == scope_path)
        )
        reg_result = await db.execute(reg_stmt)
        total_regions = reg_result.scalar() or 0
        
        # Get last program data
        last_stmt = select(Count).where(
            (Count.path.op('<@')(scope_path)) | (Count.path == scope_path),
            Count.is_deleted == False
        ).order_by(Count.created_at.desc()).limit(1)
        
        last_result = await db.execute(last_stmt)
        last_program = last_result.scalar_one_or_none()
        
        return {
            "total_locations": total_locations,
            "total_groups": total_groups,
            "total_regions": total_regions,
            "adult_male": last_program.adult_male if last_program else 0,
            "adult_female": last_program.adult_female if last_program else 0,
            "youth_male": last_program.youth_male if last_program else 0,
            "youth_female": last_program.youth_female if last_program else 0,
            "boys": last_program.boys if last_program else 0,
            "girls": last_program.girls if last_program else 0,
            "total": last_program.total if last_program else 0,
            "date": last_program.created_at if last_program else None
        }
    
    @staticmethod
    async def get_user_statistics(db: AsyncSession, scope_path: str) -> dict:
        """
        Get user activity statistics.
        """
        stmt = select(
            func.coalesce(func.sum(cast(User.is_active == True, Integer)), 0).label("active_user"),
            func.coalesce(func.sum(cast(User.is_active == False, Integer)), 0).label("inactive_user"),
            func.count(User.user_id).label("registered_user")
        ).where(
            (User.path.op('<@')(scope_path)) | (User.path == scope_path),
            User.is_deleted == False
        )
        
        result = await db.execute(stmt)
        row = result.one_or_none()
        
        if not row:
            return {"active_user": 0, "inactive_user": 0, "registered_user": 0}
        
        return {
            "active_user": row.active_user,
            "inactive_user": row.inactive_user,
            "registered_user": row.registered_user
        }
