"""Export service for loan data to CSV and XLSX files.

Atomic write protocol (TC-18 / PD-36):
    Write to temp file, then os.replace() for atomic swap on both POSIX and Windows NTFS.

Export scope: active loans only (status != PaidOff) per PD-28 / BC-10.
"""
import csv
import logging
import os
from pathlib import Path
from typing import List

from models.loan import CSV_FIELDNAMES, Loan

logger = logging.getLogger(__name__)


def export_to_csv(file_path: Path, loans: List[Loan]) -> None:
    """Export active loans to a CSV file.

    Args:
        file_path: Destination path for the CSV file.
        loans: List of Loan objects to export (caller must filter out PaidOff records).

    Raises:
        IOError: If the parent directory does not exist (PD-36).
    """
    if not file_path.parent.exists():
        raise IOError(f"Export directory does not exist: {file_path.parent}")
    temp_path = file_path.with_suffix(".tmp")
    try:
        with temp_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            for loan in loans:
                writer.writerow(loan.to_csv_row())
        os.replace(str(temp_path), str(file_path))
        logger.info("Exported %d loans to CSV: %s", len(loans), file_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def export_to_xlsx(file_path: Path, loans: List[Loan]) -> None:
    """Export active loans to an XLSX file.

    Args:
        file_path: Destination path for the XLSX file.
        loans: List of Loan objects to export (caller must filter out PaidOff records).

    Raises:
        IOError: If the parent directory does not exist (PD-36).
    """
    import openpyxl

    if not file_path.parent.exists():
        raise IOError(f"Export directory does not exist: {file_path.parent}")
    temp_path = file_path.with_suffix(".tmp.xlsx")
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Loans"
        ws.append(CSV_FIELDNAMES)
        for loan in loans:
            row = loan.to_csv_row()
            ws.append([row.get(f, "") for f in CSV_FIELDNAMES])
        wb.save(str(temp_path))
        os.replace(str(temp_path), str(file_path))
        logger.info("Exported %d loans to XLSX: %s", len(loans), file_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
