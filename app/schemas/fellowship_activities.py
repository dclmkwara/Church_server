"""
Pydantic schemas for Fellowship Activities.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# ==========================================
# Fellowship Member Schemas
# ==========================================
class FellowshipMemberBase(BaseModel):
    fellowship_id: str
    name: str = Field(..., min_length=1)
    phone: Optional[str] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    role: str = "member"
    client_id: Optional[UUID] = None

class FellowshipMemberCreate(FellowshipMemberBase):
    pass

class FellowshipMemberResponse(FellowshipMemberBase):
    id: UUID
    path: str
    is_active: bool
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Fellowship Attendance Schemas
# ==========================================
class FellowshipAttendanceBase(BaseModel):
    fellowship_id: str
    date: datetime
    
    men: int = 0
    women: int = 0
    youths: int = 0
    children: int = 0
    
    topic: Optional[str] = None
    note: Optional[str] = None
    client_id: Optional[UUID] = None

class FellowshipAttendanceCreate(FellowshipAttendanceBase):
    pass

class FellowshipAttendanceResponse(FellowshipAttendanceBase):
    id: UUID
    path: str
    total: int
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Fellowship Offering Schemas
# ==========================================
class FellowshipOfferingBase(BaseModel):
    fellowship_id: str
    date: datetime
    amount: Decimal = Field(..., gt=0)
    note: Optional[str] = None
    client_id: Optional[UUID] = None

class FellowshipOfferingCreate(FellowshipOfferingBase):
    pass

class FellowshipOfferingResponse(FellowshipOfferingBase):
    id: UUID
    path: str
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Fellowship Testimony Schemas
# ==========================================
class TestimonyBase(BaseModel):
    fellowship_id: str
    date: datetime
    testifier_name: Optional[str] = None
    content: str = Field(..., min_length=1)
    note: Optional[str] = None
    client_id: Optional[UUID] = None

class TestimonyCreate(TestimonyBase):
    pass

class TestimonyUpdate(BaseModel):
    testifier_name: Optional[str] = None
    content: Optional[str] = None
    note: Optional[str] = None
    date: Optional[datetime] = None

class TestimonyResponse(TestimonyBase):
    id: UUID
    path: str
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Fellowship Prayer Request Schemas
# ==========================================
class PrayerRequestBase(BaseModel):
    fellowship_id: str
    date: datetime
    requestor_name: Optional[str] = None
    content: str = Field(..., min_length=1)
    status: str = "pending"
    client_id: Optional[UUID] = None

class PrayerRequestCreate(PrayerRequestBase):
    pass

class PrayerRequestUpdate(BaseModel):
    requestor_name: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    date: Optional[datetime] = None

class PrayerRequestResponse(PrayerRequestBase):
    id: UUID
    path: str
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Fellowship Attendance Summary Schemas
# ==========================================
class AttendanceSummaryBase(BaseModel):
    fellowship_id: str
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=1900, le=2100)
    
    total_meetings: int = 0
    avg_attendance: int = 0
    total_offering: Decimal = 0
    client_id: Optional[UUID] = None

class AttendanceSummaryCreate(AttendanceSummaryBase):
    pass

class AttendanceSummaryUpdate(BaseModel):
    total_meetings: Optional[int] = None
    avg_attendance: Optional[int] = None
    total_offering: Optional[Decimal] = None

class AttendanceSummaryResponse(AttendanceSummaryBase):
    id: UUID
    path: str
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
