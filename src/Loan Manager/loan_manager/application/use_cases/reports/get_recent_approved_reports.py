from __future__ import annotations

from collections.abc import Callable

from loan_manager.application.dtos.report_dto import ReportDTO
from loan_manager.application.use_cases.reports.get_reports import report_to_dto


class GetRecentlyApprovedReports:
    """KCH-245: read-only feed for the approvals tab's "Recently Approved"
    panel, which offers Undo. No conflict_ref_ids here -- a conflict is only
    meaningful between two still-PENDING reports (see GetPendingReports);
    an APPROVED report has already been applied, so it never carries one."""

    def __init__(self, uow_factory: Callable) -> None:
        self._uow_factory = uow_factory

    def execute(self, limit: int = 20) -> list[ReportDTO]:
        with self._uow_factory() as uow:
            reports = uow.reports.get_recent_approved(limit)
        return [report_to_dto(r) for r in reports]
