from __future__ import annotations

from datetime import datetime
from typing import Callable

from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.infrastructure.csv.export_service import CsvExportService
from loan_manager.config import EXPORT_DIR


class ExportLoans:
    def __init__(self, uow_factory: Callable) -> None:
        self._get_loans = GetAllLoans(uow_factory)
        self._export_service = CsvExportService()

    def execute(self, format: str = "csv", output_path: str | None = None) -> str:
        """Export all active loans to CSV or XLSX. Returns the output path."""
        loans = self._get_loans.execute()

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            output_path = str(EXPORT_DIR / f"loans_export_{timestamp}.{format}")

        if format == "xlsx":
            self._export_service.write_loans_xlsx(loans, output_path)
        else:
            self._export_service.write_loans(loans, output_path)

        return output_path
