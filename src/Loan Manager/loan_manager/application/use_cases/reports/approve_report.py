from __future__ import annotations

from typing import Callable

from loan_manager.application.dtos.report_dto import ApprovalResultDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.domain.events.loan_events import LoanPaidOffApproved
from loan_manager.domain.events.report_events import ReportApproved
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
    ) -> None:
        self._uow_factory = uow_factory
        self._recovery_service = recovery_service
        self._backup_service = backup_service
        self._event_bus = event_bus

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

            # Check for deleted loans (ref_ids in report that no longer exist)
            existing_ref_ids = set()
            for ref_id in report_ref_ids:
                loan = uow.loans.get_by_reference_id(ref_id)
                if loan is not None:
                    existing_ref_ids.add(ref_id)
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
                # Normal reports: bulk update dates
                date_updates = []
                for rec in report.records:
                    if rec.reference_id in deleted:
                        continue
                    if rec.post_extension_giving_date and rec.post_extension_due_date:
                        date_updates.append({
                            "reference_id": rec.reference_id,
                            "giving_date": rec.post_extension_giving_date,
                            "due_date": rec.post_extension_due_date,
                        })
                if date_updates:
                    uow.loans.bulk_update_dates(date_updates)

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
