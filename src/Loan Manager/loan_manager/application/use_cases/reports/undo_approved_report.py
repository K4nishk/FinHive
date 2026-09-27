from __future__ import annotations

from typing import Callable

from loan_manager.application.dtos.report_dto import UndoResultDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import Clock, SystemClock
from loan_manager.application.use_cases.reports.approve_report import (
    record_to_loan_create_dto,
)
from loan_manager.domain.entities.report import Report, ReportRecord
from loan_manager.domain.events.report_events import ReportReverted
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.status import CalculationMode, ReportStatus

# CalculationMode members ApproveReport treats as "extend the loan's dates"
# (bulk_update_dates against post_extension_*, then a status recompute) --
# MONTHLY/DAILY/BOTH share one approval branch (approve_report.py's `else`),
# so they share one undo branch here too. CREATE and PAIDOFF each have their
# own explicit branch below; anything outside these five is refused rather
# than silently falling into this bucket (ORCHESTRATOR RULING).
_EXTEND_MODES = (CalculationMode.MONTHLY, CalculationMode.DAILY, CalculationMode.BOTH)


class UndoApprovedReport:
    """KCH-244: reverts an APPROVED report, restoring the loan state
    ApproveReport overwrote, using the report_records snapshot ApproveReport
    itself read at approval time (report_records.giving_date/due_date is
    never touched by approval -- see plan premise).

    Decisions (KCH-244 plan, orchestrator-accepted):
      - Only an APPROVED report is undoable; PENDING/DECLINED/already-
        REVERTED are refused identically (reason "not_approved") -- calling
        undo twice is a safe no-op on the second call, not an error.
      - A PAIDOFF report is refused outright (reason "paidoff_not_undoable")
        -- MarkPaidOff's archive-to-loan_history is one-way, by plan.
      - Conflict detection is check-all-first: every record the original
        approval actually wrote is checked BEFORE anything is undone, and if
        ANY of them conflicts, the WHOLE batch is refused, atomically,
        nothing written (reason "changed_since_approval",
        `conflict_ref_ids` lists every conflicting reference_id). This
        mirrors ApproveReport's own duplicate/deleted pre-check.
      - EXTEND compares identity + the exact dates approval wrote -- never
        status/updated_at (both legitimately change with time/
        RecomputeAllStatuses) and never amount/names (EXTEND's undo never
        writes those). CREATE compares EVERY field approval wrote -- undo
        there removes the whole loan from the book (`set_inactive`), so an
        edit to any field, not just dates, must block the undo (review
        cycle 1, MAJOR-1).
      - CREATE undo deactivates the minted loan (`set_inactive`) rather than
        deleting it -- keeps the audit trail, and its reference_id stays
        "taken" for CreateLoan.stage's skip-ahead.
      - EXTEND (MONTHLY/DAILY/BOTH) undo restores the record's own
        giving_date/due_date (the loan's PRIOR dates, never touched by
        approval) via bulk_update_dates, then recomputes status against
        those restored dates and `clock.today()`, same UoW/commit as
        mark_reverted.
      - An unknown report_id raises ValueError, matching Approve/DeclineReport.
      - ReportReverted is published only after a successful commit -- never
        on any refusal path.
    """

    def __init__(
        self,
        uow_factory: Callable,
        event_bus: EventBus,
        clock: Clock | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._event_bus = event_bus
        self._clock = clock or SystemClock()

    def execute(self, report_id: str) -> UndoResultDTO:
        with self._uow_factory() as uow:
            report = uow.reports.get_by_report_id(report_id)
            if report is None:
                raise ValueError(f"Report not found: {report_id}")

            if report.status != ReportStatus.APPROVED:
                return UndoResultDTO(success=False, reason="not_approved")

            if report.report_mode == CalculationMode.PAIDOFF:
                return UndoResultDTO(success=False, reason="paidoff_not_undoable")

            if report.report_mode == CalculationMode.CREATE:
                conflicts = self._create_conflicts(uow, report)
            elif report.report_mode in _EXTEND_MODES:
                conflicts = self._extend_conflicts(uow, report)
            else:
                # A future CalculationMode neither branch above knows how to
                # restore -- refuse loudly rather than guess (ORCHESTRATOR
                # RULING), never fall through to the EXTEND bucket.
                return UndoResultDTO(success=False, reason="unrecognized_report_mode")

            if conflicts:
                return UndoResultDTO(
                    success=False,
                    reason="changed_since_approval",
                    conflict_ref_ids=sorted(conflicts),
                )

            if report.report_mode == CalculationMode.CREATE:
                self._undo_create(uow, report)
            else:
                self._undo_extend(uow, report)

            uow.reports.mark_reverted(report_id)
            uow.commit()

        self._event_bus.publish(ReportReverted(report_id=report_id))
        return UndoResultDTO(success=True)

    # -- conflict detection -------------------------------------------------

    def _create_conflicts(self, uow, report: Report) -> set[str]:
        conflicts: set[str] = set()
        pending_refs = uow.reports.get_pending_reference_ids()
        for rec in report.records:
            ref = rec.reference_id
            loan = uow.loans.get_by_reference_id(ref)
            if loan is None or not loan.is_active:
                conflicts.add(ref)
                continue
            # Rebuild the SAME DTO approval minted the loan from -- including
            # `derive_due_date` -- so a due_period-only record (post_extension
            # _due_date=None, loan.due_date derived) is not a false conflict
            # (KCH-244 plan wrinkle).
            #
            # Review cycle 1, MAJOR-1: for CREATE, undo removes the loan from
            # the active book entirely (`set_inactive`), so "never compared
            # on amount/names" (true for EXTEND, which only ever touches
            # dates) does NOT hold here -- every field is lost. Compare every
            # field approval wrote, not just the dates, against the same
            # decrypted `dto` `stage()` built the loan from.
            dto = record_to_loan_create_dto(rec)
            if (
                loan.giving_date != dto.giving_date
                or loan.due_date != dto.due_date
                or loan.borrower_name != dto.borrower_name
                or loan.borrower_group != dto.borrower_group
                or loan.depositor_name != dto.depositor_name
                or loan.depositor_group != dto.depositor_group
                or int(loan.amount) != dto.amount
                or loan.due_period != dto.due_period
            ):
                conflicts.add(ref)
                continue
            if ref in pending_refs:
                conflicts.add(ref)
        return conflicts

    def _extend_conflicts(self, uow, report: Report) -> set[str]:
        conflicts: set[str] = set()
        pending_refs = uow.reports.get_pending_reference_ids()
        for rec in self._applied_extend_records(report):
            ref = rec.reference_id
            loan = uow.loans.get_by_reference_id(ref)
            if loan is None or not loan.is_active:
                conflicts.add(ref)
                continue
            if (
                loan.giving_date != rec.post_extension_giving_date
                or loan.due_date != rec.post_extension_due_date
            ):
                conflicts.add(ref)
                continue
            if ref in pending_refs:
                conflicts.add(ref)
        return conflicts

    @staticmethod
    def _applied_extend_records(report: Report) -> list[ReportRecord]:
        """Only the records approval actually wrote -- same skip predicate
        ApproveReport's own EXTEND branch uses (approve_report.py: `if
        rec.post_extension_giving_date and rec.post_extension_due_date`). A
        record either side of that predicate never had its loan dates
        touched by approval, so undo must leave it alone too."""
        return [
            rec
            for rec in report.records
            if rec.post_extension_giving_date and rec.post_extension_due_date
        ]

    # -- restoration ----------------------------------------------------

    def _undo_create(self, uow, report: Report) -> None:
        for rec in report.records:
            uow.loans.set_inactive(rec.reference_id)

    def _undo_extend(self, uow, report: Report) -> None:
        today = self._clock.today()
        date_updates = []
        status_updates = []
        for rec in self._applied_extend_records(report):
            date_updates.append(
                {
                    "reference_id": rec.reference_id,
                    "giving_date": rec.giving_date,
                    "due_date": rec.due_date,
                }
            )
            loan = uow.loans.get_by_reference_id(rec.reference_id)
            new_status = StatusEngine.compute(rec.giving_date, rec.due_date, today)
            if new_status != loan.status:
                status_updates.append((rec.reference_id, new_status))
        if date_updates:
            uow.loans.bulk_update_dates(date_updates)
        if status_updates:
            uow.loans.bulk_update_status(status_updates)
