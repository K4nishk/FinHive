from __future__ import annotations

from typing import Callable

from loan_manager.application.dtos.loan_dto import LoanCreateDTO
from loan_manager.application.dtos.report_dto import ApprovalResultDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import Clock, SystemClock
from loan_manager.application.use_cases.loans.create_loan import CreateLoan
from loan_manager.domain.events.loan_events import LoanCreated
from loan_manager.domain.events.report_events import ReportApproved
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.status import CalculationMode, ReportStatus
from loan_manager.infrastructure.recovery.backup_service import BackupService
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService


class ApproveReport:
    def __init__(
        self,
        uow_factory: Callable,
        recovery_service: RecoveryService,
        backup_service: BackupService,
        event_bus: EventBus,
        clock: Clock | None = None,
        ref_id_service: ReferenceIdService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._recovery_service = recovery_service
        self._backup_service = backup_service
        self._event_bus = event_bus
        self._clock = clock or SystemClock()
        # Reused only for its `stage()` -- CREATE-mode approval (KCH-242)
        # mints and saves each new loan on THIS use case's own `uow`, in the
        # same transaction as `mark_approved`, rather than reimplementing
        # reference-id minting here (Ponytail rung 2). `execute()` is never
        # called on this instance: `stage()` alone means no second commit
        # and no premature `LoanCreated` publish before the report itself is
        # durably approved.
        self._create_loan = CreateLoan(
            uow_factory, ref_id_service or ReferenceIdService(), event_bus, clock=self._clock
        )

    def execute(self, report_id: str, force: bool = False) -> ApprovalResultDTO:
        created_loan_ref_ids: list[str] = []

        with self._uow_factory() as uow:
            report = uow.reports.get_by_report_id(report_id)
            if report is None:
                raise ValueError(f"Report not found: {report_id}")

            # Idempotency guard (KCH-242 review, MAJOR): only a PENDING
            # report may be approved. Without this, re-invoking execute() on
            # a report already moved to Approved -- a double-click, a retry
            # after a UI timeout that actually succeeded -- re-runs the
            # CREATE branch below and mints a second, duplicate loan per
            # record; the other modes would similarly re-apply their bulk
            # updates. Reported the same way as duplicate/deleted refs
            # (`success=False` DTO), not an exception, since this is a
            # reachable double-submit, not a programmer error.
            if report.status != ReportStatus.PENDING:
                return ApprovalResultDTO(
                    success=False,
                    duplicate_ref_ids=[],
                    deleted_ref_ids=[],
                    requires_confirmation=False,
                )

            # None-filtered (KCH-242): a CREATE-mode record has no
            # reference_id yet (Report.__post_init__ requires it stay None
            # while Pending), so it must never be treated as one for the
            # duplicate/deleted checks below. This is also what "skips" those
            # checks for a CREATE report without a separate branch: an
            # all-None record set makes report_ref_ids empty, so `duplicates`
            # and `deleted` come out empty too.
            report_ref_ids = {
                r.reference_id for r in report.records if r.reference_id is not None
            }

            # Check for duplicate ref_ids in OTHER pending reports
            all_pending = uow.reports.get_all_pending()
            other_pending_refs: set[str] = set()
            for other in all_pending:
                if str(other.report_id) != report_id:
                    for rec in other.records:
                        if rec.reference_id is not None:
                            other_pending_refs.add(rec.reference_id)

            duplicates = report_ref_ids & other_pending_refs

            # Check for deleted loans (ref_ids in report that no longer exist).
            # Cache each fetched loan so the else-branch below can reuse it
            # for its current status instead of re-querying.
            loans_by_ref_id = {}
            for ref_id in report_ref_ids:
                loan = uow.loans.get_by_reference_id(ref_id)
                if loan is not None:
                    loans_by_ref_id[ref_id] = loan
            existing_ref_ids = set(loans_by_ref_id)
            deleted = report_ref_ids - existing_ref_ids

            if (duplicates or deleted) and not force:
                return ApprovalResultDTO(
                    success=False,
                    duplicate_ref_ids=sorted(duplicates),
                    deleted_ref_ids=sorted(deleted),
                    requires_confirmation=True,
                )

            # Proceed with approval
            self._recovery_service.write(
                "approve_report",
                {"report_id": report_id, "ref_ids": sorted(report_ref_ids)},
            )

            try:
                self._backup_service.create_backup()
            except Exception:
                pass  # Best-effort backup; don't block approval

            if report.report_mode == CalculationMode.CREATE:
                # Every record proposes a brand-new borrower: stage (mint a
                # reference_id for, and save) a loan per record on THIS
                # uow/transaction, then attach that reference_id back onto
                # the record it came from. A LoanCreateDTO failing to
                # validate (e.g. a corrupted negative amount) raises here,
                # before `mark_approved`/`commit` -- the `with` block's
                # `__exit__` rolls the whole transaction back, so a bad
                # record loses every loan staged before it too, not just
                # itself. CREATE row convention: pre-state is NULL, the
                # proposed values live in post_extension_giving_date/
                # post_extension_due_date.
                for rec in report.records:
                    loan_dto = LoanCreateDTO(
                        borrower_name=rec.borrower_name,
                        borrower_group=rec.borrower_group,
                        depositor_name=rec.depositor_name,
                        depositor_group=rec.depositor_group,
                        amount=rec.amount,
                        giving_date=rec.post_extension_giving_date,
                        due_period=rec.due_period,
                        due_date=rec.post_extension_due_date,
                    )
                    loan = self._create_loan.stage(uow, loan_dto)
                    uow.reports.assign_reference_id(rec.id, str(loan.reference_id))
                    created_loan_ref_ids.append(str(loan.reference_id))
            elif report.report_mode == CalculationMode.PAIDOFF:
                for rec in report.records:
                    if rec.reference_id in deleted:
                        continue  # Skip missing loans
                    loan = uow.loans.get_by_reference_id(rec.reference_id)
                    if loan:
                        uow.history.archive(loan, rec.paidoff_date)
                        uow.loans.set_inactive(rec.reference_id)
            else:
                # Normal reports: bulk update dates, then recompute status
                # against the post-extension dates so an approval doesn't
                # leave a loan showing its pre-approval status (stale) until
                # the next app-launch RecomputeAllStatuses sweep.
                today = self._clock.today()
                date_updates = []
                status_updates = []
                for rec in report.records:
                    if rec.reference_id in deleted:
                        continue
                    if rec.post_extension_giving_date and rec.post_extension_due_date:
                        date_updates.append({
                            "reference_id": rec.reference_id,
                            "giving_date": rec.post_extension_giving_date,
                            "due_date": rec.post_extension_due_date,
                        })
                        new_status = StatusEngine.compute(
                            rec.post_extension_giving_date,
                            rec.post_extension_due_date,
                            today,
                        )
                        loan = loans_by_ref_id.get(rec.reference_id)
                        # A loan paid off (and archived) after this report was
                        # generated is inactive: its dates and status stay as
                        # set by MarkPaidOff/history archival, never as a
                        # normal-report status recompute (KCH-233 review).
                        if (
                            loan is not None
                            and loan.is_active
                            and new_status != loan.status
                        ):
                            status_updates.append((rec.reference_id, new_status))
                if date_updates:
                    uow.loans.bulk_update_dates(date_updates)
                if status_updates:
                    uow.loans.bulk_update_status(status_updates)

            uow.reports.mark_approved(report_id)
            uow.commit()

            self._recovery_service.clear()

        # Published only after the commit above has actually succeeded --
        # each new loan's LoanCreated first, then ReportApproved, matching
        # the order every other mode already publishes in (its own mutation
        # event, then ReportApproved).
        for ref_id in created_loan_ref_ids:
            self._event_bus.publish(LoanCreated(reference_id=ref_id))
        self._event_bus.publish(ReportApproved(report_id=report_id))

        return ApprovalResultDTO(
            success=True,
            duplicate_ref_ids=sorted(duplicates),
            deleted_ref_ids=sorted(deleted),
            requires_confirmation=False,
        )
