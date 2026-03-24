"""Import service for loan data from CSV and XLSX files.

Atomic write protocol (RR-001 / TC-17):
    1. Write import_recovery.tmp with source file path before batch begins.
    2. Upsert all records.
    3. Delete import_recovery.tmp on success (in finally block).

On startup: main_window._check_recovery_file() must also check import_recovery.tmp.
Per PD-35: malformed rows are skipped with a WARNING log entry.
Per R6: imported data with matching reference_id overwrites existing record completely.
"""
import csv
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import List, Optional, Set

from data.csv_manager import (
    _data_dir,
    read_all_loans_including_paidoff,
    update_loan,
    write_loan,
)
from data.ref_id_manager import generate_ref_id
from models.loan import Loan

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"borrower_name", "amount", "giving_date"}


@dataclass
class ImportResult:
    """Summary of an import operation."""

    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    overwritten_ref_ids: List[str] = field(default_factory=list)


def _recovery_path() -> Path:
    return _data_dir() / "import_recovery.tmp"


def import_loans(file_path: Path) -> ImportResult:
    """Import loans from a CSV or XLSX file.

    Behaviour:
    - Records with no reference_id: auto-assigned using generate_ref_id().
    - Records with a reference_id that exists: upsert (overwrite).
    - Records with a reference_id that does not exist: insert with that id.
    - Malformed rows (missing required fields): skipped with WARNING log (PD-35).
    - Atomic write: import_recovery.tmp written before batch; deleted on completion.

    Returns an ImportResult with counts of inserted, updated, and skipped rows.
    """
    rows = _parse_rows(file_path)
    existing_loans = read_all_loans_including_paidoff()
    existing_ref_ids: Set[str] = {loan.reference_id for loan in existing_loans}

    result = ImportResult()
    valid_rows: List[dict] = []

    for row in rows:
        if not _is_valid(row):
            logger.warning("Skipping malformed import row (missing required field): %s", row)
            result.skipped += 1
            continue
        valid_rows.append(row)

    if not valid_rows:
        return result

    # Write recovery sentinel before batch begins (RR-001)
    recovery = _recovery_path()
    recovery.write_text(str(file_path), encoding="utf-8")

    try:
        today = date.today()
        for row in valid_rows:
            ref_id = (row.get("reference_id") or "").strip()

            if ref_id and ref_id in existing_ref_ids:
                # Upsert: imported data takes priority per R6
                loan = _row_to_loan(row, ref_id)
                if loan is not None:
                    update_loan(loan)
                    result.updated += 1
                    result.overwritten_ref_ids.append(ref_id)
                else:
                    result.skipped += 1
            elif ref_id:
                # Has ref_id but not in existing — insert with that id
                loan = _row_to_loan(row, ref_id)
                if loan is not None:
                    write_loan(loan)
                    existing_ref_ids.add(ref_id)
                    result.inserted += 1
                else:
                    result.skipped += 1
            else:
                # No ref_id — auto-assign, loop until non-colliding (PD-26)
                new_ref_id = _assign_unique_ref_id(today, existing_ref_ids)
                existing_ref_ids.add(new_ref_id)
                loan = _row_to_loan(row, new_ref_id)
                if loan is not None:
                    write_loan(loan)
                    result.inserted += 1
                else:
                    result.skipped += 1
    finally:
        # Always delete recovery file, even on exception
        if recovery.exists():
            recovery.unlink()

    return result


def detect_conflicts(rows: List[dict], existing_ref_ids: Set[str]) -> List[str]:
    """Return list of reference_ids in rows that conflict with existing records.

    Used by the UI to show a preview dialog before destructive overwrites (R6 / PD-22).
    """
    conflicts: List[str] = []
    for row in rows:
        ref = (row.get("reference_id") or "").strip()
        if ref and ref in existing_ref_ids:
            conflicts.append(ref)
    return conflicts


def parse_rows(file_path: Path) -> List[dict]:
    """Parse rows from a CSV or XLSX file. Returns list of raw string dicts.

    Public interface for the UI preview dialog (to show row counts before import).
    """
    return _parse_rows(file_path)


def _assign_unique_ref_id(today: date, existing_ref_ids: Set[str]) -> str:
    """Generate a unique ref_id, incrementing the counter until non-colliding (PD-26)."""
    ref_id = generate_ref_id(today.year, today.month)
    while ref_id in existing_ref_ids:
        ref_id = generate_ref_id(today.year, today.month)
    return ref_id


def _is_valid(row: dict) -> bool:
    """Return True if the row has all required fields with non-empty values."""
    for required in REQUIRED_FIELDS:
        if not (row.get(required) or "").strip():
            return False
    return True


def _row_to_loan(row: dict, ref_id: str) -> Optional[Loan]:
    """Convert a raw CSV row dict to a Loan object. Returns None on parse failure."""
    try:
        giving_raw = (row.get("giving_date") or "").strip()
        due_raw = (row.get("due_date") or "").strip()
        return Loan(
            reference_id=ref_id,
            borrower_name=(row.get("borrower_name") or "").strip(),
            borrower_group=(row.get("borrower_group") or "").strip() or None,
            amount=int((row.get("amount") or "0").strip()),
            giving_date=date.fromisoformat(giving_raw),
            depositor_name=(row.get("depositor_name") or "").strip() or None,
            depositor_group=(row.get("depositor_group") or "").strip() or None,
            due_date=date.fromisoformat(due_raw) if due_raw else None,
            status=(row.get("status") or "Active").strip() or "Active",
        )
    except Exception as exc:
        logger.warning("Failed to construct Loan from row %s: %s", row, exc)
        return None


def _parse_rows(file_path: Path) -> List[dict]:
    """Dispatch to CSV or XLSX parser based on file extension."""
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return _parse_csv(file_path)
    elif suffix in (".xlsx", ".xls"):
        return _parse_xlsx(file_path)
    else:
        raise ValueError(f"Unsupported import file format: {suffix!r}")


def _parse_csv(file_path: Path) -> List[dict]:
    with file_path.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _parse_xlsx(file_path: Path) -> List[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(file_path, read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.close()
        return []
    headers = [str(h).strip() if h is not None else "" for h in rows[0]]
    result: List[dict] = []
    for row in rows[1:]:
        result.append(
            {
                headers[i]: (str(v).strip() if v is not None else "")
                for i, v in enumerate(row)
            }
        )
    wb.close()
    return result
