from __future__ import annotations

from typing import Callable

from loan_manager.application.dtos.report_dto import ApprovalResultDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import Clock, SystemClock
from loan_manager.domain.events.loan_events import LoanPaidOffApproved
from loan_manager.domain.events.report_events import ReportApproved
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.status import CalculationMode
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
    ) -> None:
        self._uow_factory = uow_factory
        self._recovery_service = recovery_service
        self._backup_service = backup_service
        self._event_bus = event_bus
        self._clock = clock or SystemClock()

    def execute(self, report_id: str, force: bool = False) -> ApprovalResultDTO:
        with self._uow_factory() as uow:
            report = uow.reports.get_by_report_id(report_id)
            if report is None:
                raise ValueError(f"Report not found: {report_id}")

            report_ref_ids = {r.reference_id for r in report.records}

            # Check for duplicate ref_ids in OTHER pending reports
            all_pending = uow.reports.get_all_pending()
            other_pending_refs: set[str] = set()
            for other in all_pending:
                if str(other.report_id) != report_id:
                    for rec in other.records:
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

            if report.report_mode == CalculationMode.PAIDOFF:
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

        self._event_bus.publish(ReportApproved(report_id=report_id))

        return ApprovalResultDTO(
            success=True,
            duplicate_ref_ids=sorted(duplicates),
            deleted_ref_ids=sorted(deleted),
            requires_confirmation=False,
        )
