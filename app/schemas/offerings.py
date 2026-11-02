"""
Pydantic schemas for Offering models.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_AMOUNT = Decimal("9999999999.99")


def _validate_amount_precision(value: Optional[Decimal]) -> Optional[Decimal]:
    if value is not None and value.quantize(Decimal("0.01")) != value:
        raise ValueError("Amount cannot have more than two decimal places")
    return value

class OfferingBase(BaseModel):
    event_id: UUID
    location_id: str
    
    amount: Decimal = Field(..., gt=0, le=MAX_AMOUNT, description="Amount in currency")
    payment_method: str = Field(..., description="cash, bank_transfer, mobile_money, check")
    fund_type: Optional[str] = Field("offering", description="offering, tithe, seed, etc.")
    
    note: Optional[str] = None
    client_id: Optional[UUID] = None # For offline sync

class OfferingCreate(OfferingBase):
    _amount_precision = field_validator("amount")(_validate_amount_precision)

class OfferingUpdate(BaseModel):
    """Non-financial metadata edit; amounts require a reasoned correction."""
    note: Optional[str] = None


class OfferingCorrection(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0, le=MAX_AMOUNT)
    payment_method: Optional[str] = None
    fund_type: Optional[str] = None
    note: Optional[str] = None
    reason: str = Field(..., min_length=20, max_length=1000)

    _amount_precision = field_validator("amount")(_validate_amount_precision)

    @field_validator("reason")
    @classmethod
    def reason_must_be_meaningful(cls, value: str) -> str:
        if len(value.strip()) < 20:
            raise ValueError("Correction reason must contain at least 20 non-space characters")
        return value.strip()


class OfferingReview(BaseModel):
    note: Optional[str] = Field(None, max_length=1000)


class OfferingReversal(BaseModel):
    reason: str = Field(..., min_length=20, max_length=1000)

    @field_validator("reason")
    @classmethod
    def reversal_reason_must_be_meaningful(cls, value: str) -> str:
        if len(value.strip()) < 20:
            raise ValueError("Reversal reason must contain at least 20 non-space characters")
        return value.strip()

class OfferingResponse(OfferingBase):
    id: UUID
    path: str
    status: str
    reviewed_by_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    review_note: Optional[str] = None
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
