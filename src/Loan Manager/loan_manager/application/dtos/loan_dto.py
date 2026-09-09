from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from dateutil.relativedelta import relativedelta

from loan_manager.domain.value_objects.status import LoanStatus


class LoanCreateDTO(BaseModel):
    borrower_name: str
    borrower_group: str
    depositor_name: str
    depositor_group: Optional[str] = None
    amount: int = Field(ge=0)
    giving_date: date
    due_period: Optional[int] = None
    due_date: Optional[date] = None

    @field_validator("borrower_name", "borrower_group", "depositor_name", mode="before")
    @classmethod
    def to_lowercase(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("depositor_group", mode="before")
    @classmethod
    def depositor_group_lowercase(cls, v: Optional[str]) -> Optional[str]:
        return v.lower().strip() if v else None

    @model_validator(mode="after")
    def derive_due_date(self) -> "LoanCreateDTO":
        if self.due_period is not None and self.due_date is None:
            self.due_date = self.giving_date + relativedelta(months=self.due_period)
        return self


class LoanUpdateDTO(BaseModel):
    borrower_name: Optional[str] = None
    borrower_group: Optional[str] = None
    depositor_name: Optional[str] = None
    depositor_group: Optional[str] = None
    amount: Optional[int] = Field(default=None, ge=0)
    giving_date: Optional[date] = None
    due_period: Optional[int] = None
    due_date: Optional[date] = None
    status: Optional[LoanStatus] = None

    @field_validator("borrower_name", "borrower_group", "depositor_name", mode="before")
    @classmethod
    def to_lowercase(cls, v: Optional[str]) -> Optional[str]:
        return v.lower().strip() if v else None

    @field_validator("depositor_group", mode="before")
    @classmethod
    def depositor_group_lowercase(cls, v: Optional[str]) -> Optional[str]:
        return v.lower().strip() if v else None


class LoanDTO(BaseModel):
    id: Optional[int]
    reference_id: str
    borrower_name: str
    borrower_group: str
    depositor_name: str
    depositor_group: Optional[str]
    amount: int
    giving_date: date
    due_period: Optional[int]
    due_date: Optional[date]
    status: LoanStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LoanFilterDTO(BaseModel):
    borrower_group: Optional[str] = None
    borrower_name: Optional[str] = None
    depositor_name: Optional[str] = None
    depositor_group: Optional[str] = None
    by_months: Optional[list[int]] = None

    @field_validator("by_months")
    @classmethod
    def validate_by_months(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        if v is None:
            return v
        for month in v:
            if not (1 <= month <= 12):
                raise ValueError(f"by_months entries must be in 1..12, got {month}")
        return v


class ExtendLoanDTO(BaseModel):
    extension_period: int = Field(ge=1)
    extension_period_unit: str = "months"
    new_due_date: Optional[date] = None  # for no-due-date loans


class PaidOffRequestDTO(BaseModel):
    paidoff_date: date
    interest_rate: Decimal
    commission_rate: Decimal
    tds_flag: bool = False
