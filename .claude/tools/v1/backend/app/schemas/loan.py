"""Loan data schemas."""
from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from enum import Enum


class LoanStatus(str, Enum):
    """Loan status enumeration."""
    ACTIVE = "active"
    PAID_OFF = "paid_off"
    OVERDUE = "overdue"


class Currency(str, Enum):
    """Currency enumeration."""
    INR = "INR"
    CAD = "CAD"


class LoanBase(BaseModel):
    """Base schema with common loan fields."""
    borrower_name: str = Field(..., min_length=1, max_length=100, description="Name of the borrower")
    amount: Decimal = Field(..., gt=0, description="Loan amount")
    currency: Currency = Field(default=Currency.INR, description="Currency (INR or CAD)")
    depositor_name: str = Field(..., min_length=1, max_length=100, description="Name of the depositor/lender")
    giving_date: date = Field(..., description="Date when loan was given")
    due_date: date = Field(..., description="Due date for loan repayment")
    borrower_group: Optional[str] = Field(None, max_length=50, description="Borrower group/category")
    depositor_group: Optional[str] = Field(None, max_length=50, description="Depositor group/category")
    paidoff_date: Optional[date] = Field(None, description="Date when loan was paid off")

    @field_validator('due_date')
    @classmethod
    def due_date_after_giving_date(cls, v: date, info) -> date:
        """Ensure due date is after giving date."""
        # Allow 1970-01-01 as special "no due date" marker
        if v == date(1970, 1, 1):
            return v

        giving_date = info.data.get('giving_date')
        if giving_date and v < giving_date:
            raise ValueError('Due date must be after giving date')
        return v


class LoanCreate(LoanBase):
    """Schema for creating a loan."""
    pass


class LoanUpdate(BaseModel):
    """Schema for updating a loan (partial updates allowed)."""
    amount: Optional[Decimal] = None
    currency: Optional[Currency] = None
    borrower_name: Optional[str] = None
    depositor_name: Optional[str] = None
    giving_date: Optional[date] = None
    due_date: Optional[date] = None
    status: Optional[LoanStatus] = None
    borrower_group: Optional[str] = None
    depositor_group: Optional[str] = None
    paidoff_date: Optional[date] = None


class LoanResponse(LoanBase):
    """Schema for loan response."""
    id: str = Field(..., description="Unique loan identifier")
    status: LoanStatus = Field(default=LoanStatus.ACTIVE, description="Current loan status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class LoanFilters(BaseModel):
    """Schema for filtering loans."""
    borrower_name: Optional[str] = None
    depositor_name: Optional[str] = None
    status: Optional[LoanStatus] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class SystemConfig(BaseModel):
    """System configuration response."""
    storage_type: str
    encryption_enabled: bool
    csv_output_dir: str
    app_version: str
