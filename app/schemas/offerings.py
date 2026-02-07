"""
Pydantic schemas for Offering models.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

class OfferingBase(BaseModel):
    event_id: UUID
    location_id: str
    
    amount: Decimal = Field(..., gt=0, description="Amount in currency")
    payment_method: str = Field(..., description="cash, bank_transfer, mobile_money, check")
    
    note: Optional[str] = None
    client_id: Optional[UUID] = None # For offline sync

class OfferingCreate(OfferingBase):
    pass

class OfferingUpdate(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0)
    payment_method: Optional[str] = None
    note: Optional[str] = None
    status: Optional[str] = None # For admin approval

class OfferingResponse(OfferingBase):
    id: UUID
    path: str
    status: str
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
