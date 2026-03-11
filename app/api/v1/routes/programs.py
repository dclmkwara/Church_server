"""
Program and Event management routes.
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_programs import program_domain, program_type, program_event
from app.schemas.programs import (
    ProgramDomainCreate, ProgramDomainResponse, ProgramDomainUpdate,
    ProgramTypeCreate, ProgramTypeResponse, ProgramTypeUpdate,
    ProgramEventCreate, ProgramEventResponse, ProgramEventUpdate
)
from app.models.user import User

router = APIRouter()

# --- Program Domains ---

@router.get(
    "/domains",
    response_model=List[ProgramDomainResponse],
    dependencies=[Depends(deps.PermissionChecker("programs:read"))],
)
async def read_program_domains(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List program domains (categories)."""
    return await program_domain.get_multi(db, skip=skip, limit=limit)

@router.post(
    "/domains",
    response_model=ProgramDomainResponse,
    dependencies=[Depends(deps.PermissionChecker("programs:manage"))],
)
async def create_program_domain(
    *,
    db: AsyncSession = Depends(deps.get_db),
    domain_in: ProgramDomainCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create a new program domain."""
    return await program_domain.create(db, obj_in=domain_in)

@router.put(
    "/domains/{domain_id}",
    response_model=ProgramDomainResponse,
    dependencies=[Depends(deps.PermissionChecker("programs:manage"))],
)
async def update_program_domain(
    *,
    db: AsyncSession = Depends(deps.get_db),
    domain_id: int,
    domain_in: ProgramDomainUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a program domain."""
    db_domain = await program_domain.get(db, id=domain_id)
    if not db_domain:
        raise HTTPException(status_code=404, detail="Program Domain not found")
    return await program_domain.update(db, db_obj=db_domain, obj_in=domain_in)

@router.delete(
    "/domains/{domain_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("programs:manage"))],
)
async def delete_program_domain(
    *,
    db: AsyncSession = Depends(deps.get_db),
    domain_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete a program domain."""
    db_domain = await program_domain.get(db, id=domain_id)
    if not db_domain:
        raise HTTPException(status_code=404, detail="Program Domain not found")
    await program_domain.remove(db, id=domain_id)
    return None


# --- Program Types ---

@router.get(
    "/types",
    response_model=List[ProgramTypeResponse],
    dependencies=[Depends(deps.PermissionChecker("programs:read"))],
)
async def read_program_types(
    db: AsyncSession = Depends(deps.get_db),
    domain_id: int = Query(None),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List program types, optionally filtered by domain."""
    if domain_id:
        return await program_type.get_by_domain(db, domain_id=domain_id)
    return await program_type.get_multi(db, skip=skip, limit=limit)

@router.post(
    "/types",
    response_model=ProgramTypeResponse,
    dependencies=[Depends(deps.PermissionChecker("programs:manage"))],
)
async def create_program_type(
    *,
    db: AsyncSession = Depends(deps.get_db),
    type_in: ProgramTypeCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create a new program type."""
    return await program_type.create(db, obj_in=type_in)

@router.put(
    "/types/{type_id}",
    response_model=ProgramTypeResponse,
    dependencies=[Depends(deps.PermissionChecker("programs:manage"))],
)
async def update_program_type(
    *,
    db: AsyncSession = Depends(deps.get_db),
    type_id: int,
    type_in: ProgramTypeUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a program type."""
    db_type = await program_type.get(db, id=type_id)
    if not db_type:
        raise HTTPException(status_code=404, detail="Program Type not found")
    return await program_type.update(db, db_obj=db_type, obj_in=type_in)

@router.delete(
    "/types/{type_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("programs:manage"))],
)
async def delete_program_type(
    *,
    db: AsyncSession = Depends(deps.get_db),
    type_id: int,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete a program type."""
    db_type = await program_type.get(db, id=type_id)
    if not db_type:
        raise HTTPException(status_code=404, detail="Program Type not found")
    await program_type.remove(db, id=type_id)
    return None


# --- Program Events ---

@router.get(
    "/events",
    response_model=List[ProgramEventResponse],
    dependencies=[Depends(deps.PermissionChecker("programs:read"))],
)
async def read_program_events(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
    program_type: str = Query(None, description="Program type name or slug"),
    program_domain: str = Query(None, description="Program domain name or slug"),
    title: str = Query(None, description="Program event title (partial match)"),
    level: str = Query(None, description="state, region, group, location, or fellowship"),
    location_id: str = Query(None, description="Filter by location id"),
    date: str = Query(None, description="Filter by exact date (YYYY-MM-DD)"),
    start_month: int = Query(None, ge=1, le=12),
    end_month: int = Query(None, ge=1, le=12),
    start_year: int = Query(None, ge=1900, le=2100),
    end_year: int = Query(None, ge=1900, le=2100),
) -> Any:
    """
    List scheduled events with optional filters.
    Respects hierarchical scope.
    """
    from sqlalchemy import select, text, extract
    from datetime import date as date_type
    from app.models.programs import ProgramEvent, ProgramType, ProgramDomain
    from app.models.location import Location

    search_scope = scope_path if scope_path else str(current_user.path)
    query = select(ProgramEvent).where(
        text("path <@ CAST(:scope_path AS ltree)").bindparams(scope_path=search_scope)
    )

    if program_type or program_domain:
        query = query.join(ProgramType, ProgramType.id == ProgramEvent.program_type_id)
        if program_domain:
            query = query.join(ProgramDomain, ProgramDomain.id == ProgramType.domain_id)
            query = query.where(
                (ProgramDomain.name == program_domain) | (ProgramDomain.slug == program_domain)
            )
        if program_type:
            query = query.where(
                (ProgramType.name == program_type) | (ProgramType.slug == program_type)
            )

    if title:
        query = query.where(ProgramEvent.title.ilike(f"%{title}%"))

    if level:
        level_map = {
            "state": 3,
            "region": 4,
            "group": 5,
            "location": 6,
            "fellowship": 7,
        }
        level_key = level.strip().lower()
        if level_key not in level_map:
            raise HTTPException(status_code=400, detail="Invalid level")
        query = query.where(text("nlevel(path) = :level").bindparams(level=level_map[level_key]))

    if location_id:
        loc = await db.execute(select(Location).where(Location.location_id == location_id))
        location = loc.scalars().first()
        if not location:
            raise HTTPException(status_code=404, detail="Location not found")
        query = query.where(
            text("path <@ CAST(:location_path AS ltree)").bindparams(location_path=str(location.path))
        )

    if date:
        try:
            date_val = date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format (YYYY-MM-DD)")
        query = query.where(ProgramEvent.date == date_val)

    if start_month:
        query = query.where(extract("month", ProgramEvent.date) >= start_month)
    if end_month:
        query = query.where(extract("month", ProgramEvent.date) <= end_month)
    if start_year:
        query = query.where(extract("year", ProgramEvent.date) >= start_year)
    if end_year:
        query = query.where(extract("year", ProgramEvent.date) <= end_year)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get(
    "/events/{event_id}",
    response_model=ProgramEventResponse,
    dependencies=[Depends(deps.PermissionChecker("programs:read"))],
)
async def read_program_event(
    event_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get a specific event."""
    event = await program_event.get(db, id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Program Event not found")
    return event

@router.post(
    "/events",
    response_model=ProgramEventResponse,
    dependencies=[Depends(deps.PermissionChecker("programs:manage"))],
)
async def create_program_event(
    *,
    db: AsyncSession = Depends(deps.get_db),
    event_in: ProgramEventCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Schedule a new program event.
    """
    # Validate event path is within current user's scope
    from sqlalchemy import text, select
    scope_check = select(
        text("CAST(:event_path AS ltree) <@ CAST(:scope_path AS ltree)")
    ).params(event_path=event_in.path, scope_path=str(current_user.path))
    allowed = (await db.execute(scope_check)).scalar()
    if not allowed:
        raise HTTPException(status_code=403, detail="Event path outside your scope")
    return await program_event.create(db, obj_in=event_in)

@router.put(
    "/events/{event_id}",
    response_model=ProgramEventResponse,
    dependencies=[Depends(deps.PermissionChecker("programs:manage"))],
)
async def update_program_event(
    *,
    db: AsyncSession = Depends(deps.get_db),
    event_id: UUID,
    event_in: ProgramEventUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update a program event."""
    db_event = await program_event.get(db, id=event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Program Event not found")
    if event_in.path:
        from sqlalchemy import text, select
        scope_check = select(
            text("CAST(:event_path AS ltree) <@ CAST(:scope_path AS ltree)")
        ).params(event_path=event_in.path, scope_path=str(current_user.path))
        allowed = (await db.execute(scope_check)).scalar()
        if not allowed:
            raise HTTPException(status_code=403, detail="Event path outside your scope")
    return await program_event.update(db, db_obj=db_event, obj_in=event_in)

@router.delete(
    "/events/{event_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(deps.PermissionChecker("programs:manage"))],
)
async def delete_program_event(
    *,
    db: AsyncSession = Depends(deps.get_db),
    event_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete a program event."""
    db_event = await program_event.get(db, id=event_id)
    if not db_event:
        raise HTTPException(status_code=404, detail="Program Event not found")
    await program_event.remove(db, id=event_id)
    return None
