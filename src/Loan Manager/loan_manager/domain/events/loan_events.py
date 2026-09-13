from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class LoanCreated:
    reference_id: str


@dataclass(frozen=True)
class LoanExtended:
    reference_id: str
    new_giving_date: date
    new_due_date: date


@dataclass(frozen=True)
class LoanPaidOffRequested:
    reference_id: str
    report_id: str


@dataclass(frozen=True)
class LoanPaidOffApproved:
    reference_id: str
    paidoff_date: date
