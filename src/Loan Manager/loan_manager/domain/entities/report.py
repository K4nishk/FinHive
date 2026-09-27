from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from loan_manager.domain.value_objects.status import ReportActor, ReportStatus, CalculationMode, ExtensionPeriodUnit
from loan_manager.domain.value_objects.report_id import ReportId


@dataclass
class ReportRecord:
    id: Optional[int]
    report_id: str
    # Optional (KCH-242): a CREATE-mode proposal names a borrower who has no
    # loan yet, so there is no reference_id to attach until ApproveReport
    # mints one and calls assign_reference_id. Every other mode still
    # requires one -- enforced by Report.__post_init__ below, not by the
    # type here.
    reference_id: Optional[str]
    borrower_name: str
    depositor_name: str
    depositor_group: Optional[str]
    amount: int
    # Optional for the same reason: a CREATE row has no pre-existing loan,
    # so there is no current giving_date to show.
    giving_date: Optional[date]
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
    # New in KCH-242, appended so every existing positional construction
    # (generate_report, mark_paidoff) keeps working unchanged.
    borrower_group: Optional[str] = None
    due_period: Optional[int] = None


@dataclass
class Report:
    id: Optional[int]
    report_id: ReportId
    report_mode: CalculationMode
    status: ReportStatus
    records: list[ReportRecord]
    created_at: datetime
    updated_at: datetime
    # New in KCH-242, appended so every existing positional construction
    # keeps working unchanged. actor distinguishes a human-filed report
    # (FORM, the only kind before this issue) from one the agent proposed
    # (AGENT); user_request/turn_id are set only for the latter.
    actor: ReportActor = ReportActor.FORM
    user_request: Optional[str] = None
    turn_id: Optional[str] = None

    def report_id_str(self) -> str:
        return str(self.report_id)

    def __post_init__(self) -> None:
        """CREATE row convention (KCH-242 plan): a CREATE-mode record names a
        prospective loan that does not exist yet, so it carries the OPPOSITE
        set of required fields to every other mode -- proposed dates in
        post_extension_giving_date/post_extension_due_date, borrower_group
        set, reference_id/giving_date NULL until approval mints a loan.
        Every other mode is the historical case: a reference_id and a
        giving_date for an existing loan are mandatory.
        """
        if self.report_mode != CalculationMode.CREATE:
            for record in self.records:
                if record.reference_id is None or record.giving_date is None:
                    raise ValueError(
                        f"{self.report_mode.value} report record must have "
                        "both reference_id and giving_date set"
                    )
        else:
            for record in self.records:
                if (
                    record.borrower_group is None
                    or record.post_extension_giving_date is None
                ):
                    raise ValueError(
                        "CREATE report record must have both borrower_group "
                        "and post_extension_giving_date set"
                    )
                if self.status == ReportStatus.PENDING and record.reference_id is not None:
                    raise ValueError(
                        "CREATE report record must have reference_id=None "
                        "while the report is Pending -- it is assigned only "
                        "on approval"
                    )
