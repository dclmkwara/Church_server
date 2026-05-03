from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PublicContactSubmissionResponse(BaseModel):
    id: UUID
    name: str
    email: str
    phone: Optional[str] = None
    subject: str
    message: str
    status: str
    review_note: Optional[str] = None
    reviewed_by_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PublicPrayerSubmissionResponse(BaseModel):
    id: UUID
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    request: str
    is_urgent: bool
    status: str
    review_note: Optional[str] = None
    reviewed_by_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class PublicIntakeReviewUpdate(BaseModel):
    status: str
    review_note: Optional[str] = None
