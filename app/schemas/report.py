from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel
from uuid import UUID

class DailyCountSummary(BaseModel):
    day: date
    location_id: str
    location_name: str
    path: str
    total_attendance: int
    total_men: int
    total_women: int
    total_youth_male: int
    total_youth_female: int
    total_boys: int
    total_girls: int
    record_count: int

    class Config:
        from_attributes = True

class MonthlyFinancialSummary(BaseModel):
    month: datetime
    location_id: str
    location_name: str
    path: str
    total_amount: float
    transaction_count: int

    class Config:
        from_attributes = True

class AttendanceTrend(BaseModel):
    week: datetime
    location_id: str
    location_name: str
    path: str
    status: str
    worker_count: int

    class Config:
        from_attributes = True

class ReportResponse(BaseModel):
    data: List[dict] # Generic wrapper or specific based on endpoint
    meta: dict
