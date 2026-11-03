"""
Sync Schemas.

Defines the structure for batch uploads from offline clients.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, model_validator

from app.schemas.counts import CountCreate, CountResponse
from app.schemas.offerings import OfferingCreate, OfferingResponse
from app.schemas.records import RecordCreate, RecordResponse
from app.schemas.attendance import WorkerAttendanceCreate, WorkerAttendanceResponse, WorkerAttendanceSubmissionCreate
from app.schemas.fellowship_activities import (
    FellowshipMemberCreate, FellowshipMemberResponse,
    FellowshipAttendanceCreate, FellowshipAttendanceResponse,
    FellowshipOfferingCreate, FellowshipOfferingResponse
)

class SyncBatchRequest(BaseModel):
    """
    Batch upload request containing lists of new records.
    Each record must have a client_id.
    """
    counts: List[CountCreate] = Field(default_factory=list)
    offerings: List[OfferingCreate] = Field(default_factory=list)
    records: List[RecordCreate] = Field(default_factory=list)
    worker_attendance: List[WorkerAttendanceCreate] = Field(default_factory=list)
    worker_attendance_submissions: List[WorkerAttendanceSubmissionCreate] = Field(default_factory=list)
    
    # Fellowship items
    fellowship_members: List[FellowshipMemberCreate] = Field(default_factory=list)
    fellowship_attendance: List[FellowshipAttendanceCreate] = Field(default_factory=list)
    fellowship_offerings: List[FellowshipOfferingCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_stable_client_ids(self):
        """Offline retries must carry stable IDs to be safely idempotent."""
        for resource_name in (
            "counts", "offerings", "records", "worker_attendance", "worker_attendance_submissions",
            "fellowship_members", "fellowship_attendance", "fellowship_offerings",
        ):
            missing = [index for index, item in enumerate(getattr(self, resource_name)) if item.client_id is None]
            if missing:
                raise ValueError(f"{resource_name} items require client_id; missing at indexes {missing}")
        return self


class SyncResult(BaseModel):
    """Result for a single record type."""
    synced: int = 0
    duplicates: int = 0
    errors: int = 0
    details: List[Dict[str, Any]] = Field(default_factory=list) # [{client_id: ..., status: 'synced', id: ...}, ...]

class SyncBatchResponse(BaseModel):
    """Response summary for the batch upload."""
    counts: SyncResult
    offerings: SyncResult
    records: SyncResult
    worker_attendance: SyncResult
    worker_attendance_submissions: SyncResult = Field(default_factory=SyncResult)
    
    fellowship_members: SyncResult
    fellowship_attendance: SyncResult
    fellowship_offerings: SyncResult
