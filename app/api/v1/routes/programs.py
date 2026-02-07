"""
Program and Event management routes.
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
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

@router.get("/domains", response_model=List[ProgramDomainResponse])
async def read_program_domains(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """List program domains (categories)."""
    return await program_domain.get_multi(db, skip=skip, limit=limit)

@router.post("/domains", response_model=ProgramDomainResponse)
async def create_program_domain(
    *,
    db: AsyncSession = Depends(deps.get_db),
    domain_in: ProgramDomainCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create a new program domain."""
    # TODO: Check admin permissions
    return await program_domain.create(db, obj_in=domain_in)


# --- Program Types ---

@router.get("/types", response_model=List[ProgramTypeResponse])
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

@router.post("/types", response_model=ProgramTypeResponse)
async def create_program_type(
    *,
    db: AsyncSession = Depends(deps.get_db),
    type_in: ProgramTypeCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create a new program type."""
    # TODO: Check admin permissions
    return await program_type.create(db, obj_in=type_in)


# --- Program Events ---

@router.get("/events", response_model=List[ProgramEventResponse])
async def read_program_events(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    scope_path: str = Query(None, description="Filter by scope path"),
) -> Any:
    """
    List scheduled events.
    Respects hierarchical scope.
    """
    search_scope = scope_path if scope_path else str(current_user.path)
    
    # We should use get_multi_by_scope
    return await program_event.get_multi_by_scope(
        db, scope_path=search_scope, skip=skip, limit=limit
    )

@router.post("/events", response_model=ProgramEventResponse)
async def create_program_event(
    *,
    db: AsyncSession = Depends(deps.get_db),
    event_in: ProgramEventCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Schedule a new program event.
    """
    # TODO: Validate user permission to create event at this path/scope
    return await program_event.create(db, obj_in=event_in)
