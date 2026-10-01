from abc import ABC, abstractmethod
from typing import Optional

from loan_manager.domain.entities.report import Report, ReportRecord


class IReportRepository(ABC):
    @abstractmethod
    def get_by_report_id(self, report_id: str) -> Optional[Report]: ...

    @abstractmethod
    def get_all_pending(self) -> list[Report]: ...

    @abstractmethod
    def get_recent_approved(self, limit: int) -> list[Report]: ...

    @abstractmethod
    def save(self, report: Report) -> Report: ...

    @abstractmethod
    def mark_approved(self, report_id: str) -> None: ...

    @abstractmethod
    def mark_declined(self, report_id: str) -> None: ...

    @abstractmethod
    def mark_reverted(self, report_id: str) -> None: ...

    @abstractmethod
    def get_pending_reference_ids(self) -> set[str]: ...

    @abstractmethod
    def assign_reference_id(self, record_id: int, ref_id: str) -> None: ...
