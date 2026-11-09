"""
Pydantic schemas for Offering models.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_AMOUNT = Decimal("9999999999.99")


def _validate_amount_precision(value: Optional[Decimal]) -> Optional[Decimal]:
    if value is not None and value.quantize(Decimal("0.01")) != value:
        raise ValueError("Amount cannot have more than two decimal places")
    return value

class OfferingBase(BaseModel):
    event_id: Optional[UUID] = None
    location_id: str
    date: Optional[datetime] = None
    church_type: Optional[str] = Field(None, max_length=40)
    program_level: Optional[str] = Field(None, pattern="^(Local|Group|Region|State|National|Global)$", description="Local, Group, Region, State, National, or Global")
    program_domain: Optional[str] = Field(None, max_length=80)
    program_type: Optional[str] = Field(None, max_length=120)
    
    amount: Decimal = Field(..., gt=0, le=MAX_AMOUNT, description="Amount in currency")
    payment_method: str = Field(..., description="cash, bank_transfer, mobile_money, check")
    fund_type: Optional[str] = Field("offering", description="offering, tithe, seed, etc.")
    
    note: Optional[str] = None
    client_id: Optional[UUID] = None # For offline sync

class OfferingCreate(OfferingBase):
    _amount_precision = field_validator("amount")(_validate_amount_precision)

    @model_validator(mode="after")
    def require_context_without_event(self):
        if self.event_id is None:
            if not self.date or not self.church_type or not self.program_level or not self.program_domain or not self.program_type:
                raise ValueError("Eventless offerings require service date, church section, program level, program domain, and program type")
            if self.program_domain.lower() == "crusade":
                raise ValueError("Crusade offerings require a scheduled event")
        return self

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


class OfferingEditValues(BaseModel):
    amount: Optional[Decimal] = Field(None, gt=0, le=MAX_AMOUNT)
    payment_method: Optional[str] = Field(None, max_length=80)
    fund_type: Optional[str] = Field(None, max_length=80)
    note: Optional[str] = Field(None, max_length=4000)

    _amount_precision = field_validator("amount")(_validate_amount_precision)


class SubmissionEditRequest(BaseModel):
    edit_id: UUID
    base_revision: int = Field(ge=0)
    values: OfferingEditValues


class OfferingReturnRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


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
    program_scope_path: Optional[str] = None
    status: str
    reviewed_by_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    review_note: Optional[str] = None
    entered_by_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
