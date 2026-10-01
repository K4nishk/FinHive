from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel

from loan_manager.domain.value_objects.status import ReportActor, ReportStatus, CalculationMode, ExtensionPeriodUnit


class ReportRecordDTO(BaseModel):
    id: Optional[int]
    report_id: str
    # Optional (KCH-242): NULL on a CREATE-mode record until approval mints
    # a loan and assigns one -- see Report.__post_init__.
    reference_id: Optional[str]
    borrower_name: str
    depositor_name: str
    depositor_group: Optional[str]
    amount: int
    # Optional (KCH-242): a CREATE-mode record has no existing loan, so no
    # current giving_date -- the proposed one is post_extension_giving_date.
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
    borrower_group: Optional[str] = None
    due_period: Optional[int] = None

    model_config = {"from_attributes": True}


class ReportDTO(BaseModel):
    id: Optional[int]
    report_id: str
    report_mode: CalculationMode
    status: ReportStatus
    records: list[ReportRecordDTO]
    created_at: datetime
    updated_at: datetime
    # Required, no default (KCH-242 review, MAJOR): a defaulted FORM here let
    # a call site that forgot to map `actor` silently mislabel an AGENT
    # report as FORM instead of failing loudly (GetPendingReports did
    # exactly this). user_request/turn_id stay optional -- both are
    # genuinely absent for a FORM report.
    actor: ReportActor
    user_request: Optional[str] = None
    turn_id: Optional[str] = None
    # KCH-245: reference_ids this report shares with ANOTHER pending report
    # (computed by GetPendingReports, empty for GetRecentlyApprovedReports --
    # a conflict is only meaningful while both reports are still PENDING).
    # Defaulted, not required: every existing call site that builds a
    # ReportDTO without this issue's conflict computation still works.
    conflict_ref_ids: list[str] = []

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
    # Required, no default (KCH-243, mirrors ReportDTO.actor above): every
    # caller -- the FORM tab and every PROPOSE tool -- must say who is
    # generating this report; a defaulted FORM here is the same silent
    # mislabelling risk the KCH-242 review closed on ReportDTO itself.
    actor: ReportActor
    user_request: Optional[str] = None
    turn_id: Optional[str] = None


class ApprovalResultDTO(BaseModel):
    success: bool
    duplicate_ref_ids: list[str] = []
    deleted_ref_ids: list[str] = []
    # Review cycle 2, MAJOR-1 (ORCHESTRATOR RULING): an UPDATE-mode ref
    # whose loan is inactive (paid off/archived) since the proposal was
    # made -- deliberately kept OUT of `deleted_ref_ids` (the loan still
    # exists, it just isn't live) and refused regardless of `force`, so the
    # UI's "records have been deleted -- proceed anyway?" prompt never
    # covers it, and a future message for this field can say "paid off"
    # rather than "deleted".
    inactive_ref_ids: list[str] = []
    requires_confirmation: bool = False


class UndoResultDTO(BaseModel):
    """KCH-244. `reason` is one of "not_approved" (report is PENDING,
    DECLINED or already REVERTED), "paidoff_not_undoable", "changed_since_approval"
    (see `conflict_ref_ids`), or "unrecognized_report_mode" (orchestrator
    ruling: a future CalculationMode this use case does not know how to
    restore is refused, never silently no-opped)."""
    success: bool
    reason: Optional[str] = None
    conflict_ref_ids: list[str] = []
