"""
Statistics service for aggregated analytics.

Production changes:
- get_church_statistics(): aggregate queries stay sequential on the request
  AsyncSession, avoiding unsafe concurrent session use.
- get_church_statistics(): last-program fetch now uses a column projection
  instead of SELECT * — avoids transferring unused columns.
- get_population_statistics(): two separate program-domain filters collapsed
  into one join condition.
- _scope_filter imported from shared app.db.filters (was duplicated locally).
"""
from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, case, cast, extract, func, select, Integer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.filters import scope_filter as _scope_filter
from app.models.counts import Count
from app.models.location import Location, Group, Region
from app.models.user import User
from app.models.programs import ProgramEvent, ProgramType, ProgramDomain


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
        end_year: Optional[int] = None,
    ) -> dict:
        """Aggregated population statistics with demographics, averages, and percentages."""
        filters = [_scope_filter(Count.path, scope_path), Count.is_deleted == False]

        join_programs = bool(program_domain or program_type)
        if location_id:
            filters.append(Count.location_id == location_id)
        if date_filter:
            filters.append(Count.date >= date_filter)
        if start_year:
            filters.append(extract("year", Count.date) >= start_year)
        if end_year:
            filters.append(extract("year", Count.date) <= end_year)
        if start_month:
            filters.append(extract("month", Count.date) >= start_month)
        if end_month:
            filters.append(extract("month", Count.date) <= end_month)

        # Roll up location submissions into a program occurrence first. Without
        # this layer, a parent scope's average is divided by its number of
        # reporting locations, understating attendance whenever multiple
        # locations report for the same service/date.
        occurrence_stmt = select(
            func.sum(Count.adult_male).label("adult_male"),
            func.sum(Count.adult_female).label("adult_female"),
            func.sum(Count.youth_male).label("youth_male"),
            func.sum(Count.youth_female).label("youth_female"),
            func.sum(Count.boys).label("boys"),
            func.sum(Count.girls).label("girls"),
            func.sum(Count.total).label("total"),
        ).select_from(Count)

        if join_programs:
            occurrence_stmt = occurrence_stmt.join(ProgramEvent, Count.event_id == ProgramEvent.id)
            occurrence_stmt = occurrence_stmt.join(ProgramType, ProgramEvent.program_type_id == ProgramType.id)
            occurrence_stmt = occurrence_stmt.join(ProgramDomain, ProgramType.domain_id == ProgramDomain.id)
            if program_domain:
                filters.append(
                    (ProgramDomain.slug == program_domain) | (ProgramDomain.name == program_domain)
                )
            if program_type:
                filters.append(
                    (ProgramType.slug == program_type) | (ProgramType.name == program_type)
                )

        legacy_unclassified_record = case(
            (
                and_(
                    Count.event_id.is_(None),
                    Count.program_domain_id.is_(None),
                    Count.program_type_id.is_(None),
                    Count.program_domain.is_(None),
                    Count.program_type.is_(None),
                ),
                Count.id,
            ),
            else_=None,
        )
        occurrence_stmt = occurrence_stmt.where(and_(*filters)).group_by(
            func.date(Count.date),
            Count.event_id,
            Count.program_domain_id,
            Count.program_type_id,
            Count.program_domain,
            Count.program_type,
            Count.program_level,
            legacy_unclassified_record,
        ).subquery()
        stmt = select(
            func.coalesce(func.sum(occurrence_stmt.c.adult_male), 0).label("adult_male"),
            func.coalesce(func.sum(occurrence_stmt.c.adult_female), 0).label("adult_female"),
            func.coalesce(func.sum(occurrence_stmt.c.youth_male), 0).label("youth_male"),
            func.coalesce(func.sum(occurrence_stmt.c.youth_female), 0).label("youth_female"),
            func.coalesce(func.sum(occurrence_stmt.c.boys), 0).label("boys"),
            func.coalesce(func.sum(occurrence_stmt.c.girls), 0).label("girls"),
            func.coalesce(func.sum(occurrence_stmt.c.total), 0).label("total"),
            func.count().label("program_count"),
        ).select_from(occurrence_stmt)
        result = await db.execute(stmt)
        row = result.one_or_none()

        if not row or row.program_count == 0:
            return {}

        pc = row.program_count
        avg_data = {
            "adult_male": int(round(row.adult_male / pc)),
            "adult_female": int(round(row.adult_female / pc)),
            "youth_male": int(round(row.youth_male / pc)),
            "youth_female": int(round(row.youth_female / pc)),
            "boys": int(round(row.boys / pc)),
            "girls": int(round(row.girls / pc)),
            "total": int(round(row.total / pc)),
            "average_men": int(round((row.adult_male + row.youth_male + row.boys) / pc)),
            "average_women": int(round((row.adult_female + row.youth_female + row.girls) / pc)),
            "average_adults": int(round((row.adult_male + row.adult_female) / pc)),
            "average_youths": int(round((row.youth_male + row.youth_female) / pc)),
            "average_children": int(round((row.boys + row.girls) / pc)),
        }

        if row.total > 0:
            t = row.total
            percentages = {
                "percentage_adult_male": round((row.adult_male / t) * 100, 1),
                "percentage_adult_female": round((row.adult_female / t) * 100, 1),
                "percentage_youth_male": round((row.youth_male / t) * 100, 1),
                "percentage_youth_female": round((row.youth_female / t) * 100, 1),
                "percentage_boys": round((row.boys / t) * 100, 1),
                "percentage_girls": round((row.girls / t) * 100, 1),
                "percentage_men": round(((row.adult_male + row.youth_male + row.boys) / t) * 100, 1),
                "percentage_women": round(((row.adult_female + row.youth_female + row.girls) / t) * 100, 1),
                "percentage_adults": round(((row.adult_male + row.adult_female) / t) * 100, 1),
                "percentage_youths": round(((row.youth_male + row.youth_female) / t) * 100, 1),
                "percentage_children": round(((row.boys + row.girls) / t) * 100, 1),
            }
        else:
            percentages = {}

        return {**avg_data, **percentages}

    @staticmethod
    async def get_church_statistics(db: AsyncSession, scope_path: str) -> dict:
        """
        Church overview statistics.

        Runs aggregate queries sequentially on the request session, and the
        last-program query uses a column projection instead of SELECT *.
        """
        loc_stmt = select(func.count(Location.location_id.distinct())).where(
            _scope_filter(Location.path, scope_path)
        )
        grp_stmt = select(func.count(Group.group_id.distinct())).where(
            _scope_filter(Group.path, scope_path)
        )
        reg_stmt = select(func.count(Region.region_id.distinct())).where(
            _scope_filter(Region.path, scope_path)
        )
        # Column projection — fetch only what we use, not SELECT *
        last_stmt = (
            select(
                Count.adult_male,
                Count.adult_female,
                Count.youth_male,
                Count.youth_female,
                Count.boys,
                Count.girls,
                Count.total,
                Count.created_at,
            )
            .where(_scope_filter(Count.path, scope_path), Count.is_deleted == False)
            .order_by(Count.created_at.desc())
            .limit(1)
        )

        loc_r = await db.execute(loc_stmt)
        grp_r = await db.execute(grp_stmt)
        reg_r = await db.execute(reg_stmt)
        last_r = await db.execute(last_stmt)

        total_locations = loc_r.scalar() or 0
        total_groups = grp_r.scalar() or 0
        total_regions = reg_r.scalar() or 0
        last = last_r.one_or_none()

        return {
            "total_locations": total_locations,
            "total_groups": total_groups,
            "total_regions": total_regions,
            "adult_male": last.adult_male if last else 0,
            "adult_female": last.adult_female if last else 0,
            "youth_male": last.youth_male if last else 0,
            "youth_female": last.youth_female if last else 0,
            "boys": last.boys if last else 0,
            "girls": last.girls if last else 0,
            "total": last.total if last else 0,
            "date": (
                last.created_at.date()
                if last and isinstance(last.created_at, datetime)
                else last.created_at if last else None
            ),
        }

    @staticmethod
    async def get_user_statistics(db: AsyncSession, scope_path: str) -> dict:
        """User activity statistics."""
        stmt = select(
            func.coalesce(func.sum(cast(User.is_active == True, Integer)), 0).label("active_user"),
            func.coalesce(func.sum(cast(User.is_active == False, Integer)), 0).label("inactive_user"),
            func.count(User.user_id).label("registered_user"),
        ).where(
            _scope_filter(User.path, scope_path),
            User.is_deleted == False,
        )
        result = await db.execute(stmt)
        row = result.one_or_none()
        if not row:
            return {"active_user": 0, "inactive_user": 0, "registered_user": 0}
        return {
            "active_user": int(row.active_user or 0),
            "inactive_user": int(row.inactive_user or 0),
            "registered_user": int(row.registered_user or 0),
        }
