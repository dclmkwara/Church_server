"""
Sync Schemas.

Defines the structure for batch uploads from offline clients.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel

from app.schemas.counts import CountCreate, CountResponse
from app.schemas.offerings import OfferingCreate, OfferingResponse
from app.schemas.records import RecordCreate, RecordResponse
from app.schemas.attendance import WorkerAttendanceCreate, WorkerAttendanceResponse
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
    counts: List[CountCreate] = []
    offerings: List[OfferingCreate] = []
    records: List[RecordCreate] = []
    worker_attendance: List[WorkerAttendanceCreate] = []
    
    # Fellowship items
    fellowship_members: List[FellowshipMemberCreate] = []
    fellowship_attendance: List[FellowshipAttendanceCreate] = []
    fellowship_offerings: List[FellowshipOfferingCreate] = []


class SyncResult(BaseModel):
    """Result for a single record type."""
    synced: int = 0
    duplicates: int = 0
    errors: int = 0
    details: List[Dict[str, Any]] = [] # [{client_id: ..., status: 'synced', id: ...}, ...]

class SyncBatchResponse(BaseModel):
    """Response summary for the batch upload."""
    counts: SyncResult
    offerings: SyncResult
    records: SyncResult
    worker_attendance: SyncResult
    
    fellowship_members: SyncResult
    fellowship_attendance: SyncResult
    fellowship_offerings: SyncResult
