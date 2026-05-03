from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from uuid import UUID

class DailyCountSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

class MonthlyFinancialSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    month: datetime
    location_id: str
    location_name: str
    path: str
    total_amount: float
    transaction_count: int

class AttendanceTrend(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week: datetime
    location_id: str
    location_name: str
    path: str
    status: str
    worker_count: int

class ReportResponse(BaseModel):
    data: List[dict] # Generic wrapper or specific based on endpoint
    meta: dict
