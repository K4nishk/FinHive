from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from loan_manager.domain.value_objects.status import LoanStatus
from loan_manager.domain.value_objects.reference_id import ReferenceId
from loan_manager.domain.value_objects.money import Money


@dataclass
class Loan:
    id: Optional[int]
    reference_id: ReferenceId
    borrower_name: str
    borrower_group: str
    depositor_name: str
    depositor_group: Optional[str]
    amount: Money
    giving_date: date
    due_period: Optional[int]
    due_date: Optional[date]
    status: LoanStatus
    is_active: bool
    created_at: datetime
    updated_at: datetime

    def is_paidoff(self) -> bool:
        return self.status == LoanStatus.PAIDOFF

    def ref_id_str(self) -> str:
        return str(self.reference_id)
