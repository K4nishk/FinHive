from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from loan_manager.domain.value_objects.status import ReportStatus, CalculationMode, ExtensionPeriodUnit


class ReportRecordDTO(BaseModel):
    id: Optional[int]
    report_id: str
    reference_id: str
    borrower_name: str
    depositor_name: str
    depositor_group: Optional[str]
    amount: int
    giving_date: date
    due_date: Optional[date]
    extension_period: int
    extension_period_unit: ExtensionPeriodUnit
    interest_rate: Decimal
    commission_rate: Decimal
    tds_flag: bool
    interest_amount: Optional[Decimal]
    commission_amount: Optional[Decimal]
    tds_amount: Optional[Decimal]
    chq_amount: Optional[Decimal]
    post_extension_giving_date: Optional[date]
    post_extension_due_date: Optional[date]
    paidoff_date: Optional[date]

    model_config = {"from_attributes": True}


class ReportDTO(BaseModel):
    id: Optional[int]
    report_id: str
    report_mode: CalculationMode
    status: ReportStatus
    records: list[ReportRecordDTO]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportRecordUpdateDTO(BaseModel):
    extension_period: Optional[int] = None
    extension_period_unit: Optional[ExtensionPeriodUnit] = None
    interest_rate: Optional[Decimal] = None
    commission_rate: Optional[Decimal] = None
    tds_flag: Optional[bool] = None


class GenerateReportDTO(BaseModel):
    mode: CalculationMode
    records: list[ReportRecordDTO]


class ApprovalResultDTO(BaseModel):
    success: bool
    duplicate_ref_ids: list[str] = []
    deleted_ref_ids: list[str] = []
    requires_confirmation: bool = False
