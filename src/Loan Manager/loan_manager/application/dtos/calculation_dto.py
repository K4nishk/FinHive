from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from loan_manager.application.dtos.loan_dto import LoanFilterDTO
from loan_manager.domain.value_objects.status import CalculationMode, ExtensionPeriodUnit


class CalculationRequestDTO(BaseModel):
    mode: CalculationMode
    filters: LoanFilterDTO
    interest_rate: Decimal
    commission_rate: Decimal
    extension_period: int
    extension_period_unit: ExtensionPeriodUnit
    tds_flag: bool = False


class CalculationLineDTO(BaseModel):
    reference_id: str
    borrower_name: str
    depositor_name: str
    amount: int
    giving_date: date
    due_date: Optional[date]
    extension_period: int
    extension_period_unit: ExtensionPeriodUnit
    interest_rate: Decimal
    commission_rate: Decimal
    tds_flag: bool
    interest_amount: Decimal
    commission_amount: Decimal
    tds_amount: Decimal
    chq_amount: Decimal
    post_extension_giving_date: Optional[date]
    post_extension_due_date: Optional[date]


class CalculationResultDTO(BaseModel):
    mode: CalculationMode
    lines: list[CalculationLineDTO]
    total_amount: int
    total_interest: Decimal
    total_commission: Decimal
    total_tds: Decimal
