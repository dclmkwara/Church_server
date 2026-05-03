"""
API routes for LocationProfile.

GET    /api/v1/locations/{location_id}/profile  — Get profile
POST   /api/v1/locations/{location_id}/profile  — Create or update profile
DELETE /api/v1/locations/{location_id}/profile  — Delete profile
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud import crud_location_profile
from app.models.user import User
from app.schemas.location_profile import LocationProfileCreate, LocationProfileUpdate, LocationProfileResponse

router = APIRouter()


def _has_location_admin_access(current_user: User) -> bool:
    return bool(current_user.roles) and max(role.score_value for role in current_user.roles) >= 3


@router.get("/{location_id}/profile", response_model=LocationProfileResponse, tags=["Hierarchy"])
async def get_location_profile(
    location_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get the extended profile for a church location/branch."""
    await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=location_id,
        detail="Location outside your scope",
    )
    profile = await crud_location_profile.get_by_location(db, location_id=location_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Location profile not found")
    return profile


@router.post("/{location_id}/profile", response_model=LocationProfileResponse, tags=["Hierarchy"])
async def upsert_location_profile(
    location_id: str,
    profile_in: LocationProfileCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create or update the profile for a church location/branch."""
    if not _has_location_admin_access(current_user):
        raise HTTPException(status_code=403, detail="Location admin access required")
    await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=location_id,
        detail="Location outside your scope",
    )
    return await crud_location_profile.create_or_update(
        db, location_id=location_id, obj_in=profile_in
    )


@router.delete("/{location_id}/profile", status_code=204, tags=["Hierarchy"])
async def delete_location_profile(
    location_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> None:
    """Delete the profile for a church location/branch."""
    if not _has_location_admin_access(current_user):
        raise HTTPException(status_code=403, detail="Location admin access required")
    await deps.get_location_in_scope(
        db,
        current_user=current_user,
        location_id=location_id,
        detail="Location outside your scope",
    )
    deleted = await crud_location_profile.delete_by_location(db, location_id=location_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Location profile not found")
    return None
