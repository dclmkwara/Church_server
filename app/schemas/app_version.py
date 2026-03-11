from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class AppVersionBase(BaseModel):
    app_name: str
    platform: str
    version_number: Optional[str] = None
    version_tag: Optional[str] = None
    release_date: Optional[date] = None
    description: Optional[str] = None
    file_name: Optional[str] = None
    download_url: Optional[str] = None
    min_os_version: Optional[str] = None
    build: Optional[str] = None
    is_active: bool = True


class AppVersionCreate(AppVersionBase):
    pass


class AppVersionUpdate(BaseModel):
    app_name: Optional[str] = None
    platform: Optional[str] = None
    version_number: Optional[str] = None
    version_tag: Optional[str] = None
    release_date: Optional[date] = None
    description: Optional[str] = None
    file_name: Optional[str] = None
    download_url: Optional[str] = None
    min_os_version: Optional[str] = None
    build: Optional[str] = None
    is_active: Optional[bool] = None


class AppVersionResponse(AppVersionBase):
    id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
