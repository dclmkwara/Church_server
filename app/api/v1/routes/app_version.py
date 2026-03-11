from typing import Any, List
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud.crud_app_version import app_version as crud_app_version
from app.schemas.app_version import AppVersionCreate, AppVersionUpdate, AppVersionResponse
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=AppVersionResponse, status_code=status.HTTP_201_CREATED)
async def create_app_version(
    *,
    db: AsyncSession = Depends(deps.get_db),
    version_in: AppVersionCreate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Create app version metadata."""
    return await crud_app_version.create(db, obj_in=version_in)


@router.get("/", response_model=List[AppVersionResponse])
async def list_app_versions(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    app_name: str = None,
    platform: str = None,
    version_number: str = None,
    release_date: date = None,
    is_active: bool = None,
    get_last: bool = False,
) -> Any:
    """List app versions."""
    from sqlalchemy import select
    from app.models.app_version import AppVersion
    query = select(AppVersion)
    if app_name:
        query = query.where(AppVersion.app_name == app_name)
    if platform:
        query = query.where(AppVersion.platform == platform)
    if version_number:
        query = query.where(AppVersion.version_number == version_number)
    if release_date:
        query = query.where(AppVersion.release_date == release_date)
    if is_active is not None:
        query = query.where(AppVersion.is_active == is_active)
    if get_last:
        query = query.order_by(AppVersion.created_at.desc()).limit(1)
    else:
        query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{version_id}", response_model=AppVersionResponse)
async def get_app_version(
    version_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Get app version by id."""
    version = await crud_app_version.get(db, id=version_id)
    if not version:
        raise HTTPException(status_code=404, detail="App version not found")
    return version


@router.put("/{version_id}", response_model=AppVersionResponse)
async def update_app_version(
    *,
    db: AsyncSession = Depends(deps.get_db),
    version_id: UUID,
    version_in: AppVersionUpdate,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Update app version."""
    version = await crud_app_version.get(db, id=version_id)
    if not version:
        raise HTTPException(status_code=404, detail="App version not found")
    return await crud_app_version.update(db, db_obj=version, obj_in=version_in)


@router.delete("/{version_id}", status_code=status.HTTP_200_OK)
async def delete_app_version(
    *,
    db: AsyncSession = Depends(deps.get_db),
    version_id: UUID,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Delete app version."""
    version = await crud_app_version.get(db, id=version_id)
    if not version:
        raise HTTPException(status_code=404, detail="App version not found")
    await crud_app_version.remove(db, id=version_id)
    return None
