from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from loan_manager.domain.value_objects.status import ReportStatus, CalculationMode, ExtensionPeriodUnit
from loan_manager.domain.value_objects.report_id import ReportId


@dataclass
class ReportRecord:
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


@dataclass
class Report:
    id: Optional[int]
    report_id: ReportId
    report_mode: CalculationMode
    status: ReportStatus
    records: list[ReportRecord]
    created_at: datetime
    updated_at: datetime

    def report_id_str(self) -> str:
        return str(self.report_id)
