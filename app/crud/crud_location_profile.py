"""
CRUD operations for LocationProfile.
"""
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location_profile import LocationProfile
from app.schemas.location_profile import LocationProfileCreate, LocationProfileUpdate


async def get_by_location(db: AsyncSession, *, location_id: str) -> Optional[LocationProfile]:
    """Get location profile by location ID."""
    result = await db.execute(
        select(LocationProfile).where(LocationProfile.location_id == location_id)
    )
    return result.scalars().first()


async def create_or_update(
    db: AsyncSession,
    *,
    location_id: str,
    obj_in: LocationProfileCreate | LocationProfileUpdate,
) -> LocationProfile:
    """Create profile if it does not exist, otherwise update it."""
    existing = await get_by_location(db, location_id=location_id)

    if existing:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing, field, value)
        await db.commit()
        await db.refresh(existing)
        return existing

    db_obj = LocationProfile(
        location_id=location_id,
        **obj_in.model_dump(exclude_unset=True),
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def delete_by_location(db: AsyncSession, *, location_id: str) -> bool:
    """Delete the profile for a location."""
    profile = await get_by_location(db, location_id=location_id)
    if not profile:
        return False
    await db.delete(profile)
    await db.commit()
    return True
