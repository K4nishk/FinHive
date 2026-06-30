from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


class CsvExportService:
    LOAN_FIELDS = [
        "reference_id", "borrower_name", "borrower_group",
        "depositor_name", "depositor_group", "amount",
        "giving_date", "due_date", "status", "is_active",
    ]

    REPORT_FIELDS = [
        "reference_id", "borrower_name", "depositor_name",
        "depositor_group", "amount", "giving_date", "due_date",
        "extension_period", "extension_period_unit",
        "interest_rate", "commission_rate", "tds_flag",
        "interest_amount", "commission_amount", "tds_amount", "chq_amount",
        "post_extension_giving_date", "post_extension_due_date", "paidoff_date",
    ]

    def write_loans(self, loans: list, path: str) -> None:
        """Write LoanDTO list to CSV."""
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.LOAN_FIELDS)
            writer.writeheader()
            for loan in loans:
                row = {}
                for field in self.LOAN_FIELDS:
                    val = getattr(loan, field, None)
                    row[field] = str(val) if val is not None else ""
                writer.writerow(row)

    def write_loans_xlsx(self, loans: list, path: str) -> None:
        """Write LoanDTO list to XLSX using openpyxl."""
        try:
            from openpyxl import Workbook
        except ImportError:
            raise ImportError("openpyxl is required for XLSX export")

        wb = Workbook()
        ws = wb.active
        ws.title = "Loans"
        ws.append(self.LOAN_FIELDS)

        for loan in loans:
            row = []
            for field in self.LOAN_FIELDS:
                val = getattr(loan, field, None)
                row.append(str(val) if val is not None else "")
            ws.append(row)

        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        wb.save(output)

    def write_report(self, report: Any, path: str) -> None:
        """Write ReportDTO to CSV."""
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)

        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.REPORT_FIELDS)
            writer.writeheader()
            for rec in report.records:
                row = {}
                for field in self.REPORT_FIELDS:
                    val = getattr(rec, field, None)
                    if hasattr(val, "value"):
                        val = val.value
                    row[field] = str(val) if val is not None else ""
                writer.writerow(row)
