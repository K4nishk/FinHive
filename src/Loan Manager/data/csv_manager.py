"""CSV I/O manager for loans.csv, history.csv, and recovery.tmp."""
import csv
import logging
import os
import shutil
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from models.loan import CSV_FIELDNAMES, Loan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _data_dir() -> Path:
    """Return the ./data directory, creating it if absent."""
    here = Path(__file__).parent.parent
    data = here / "data"
    data.mkdir(parents=True, exist_ok=True)
    return data


def _loans_path() -> Path:
    return _data_dir() / "loans.csv"


def _history_path() -> Path:
    return _data_dir() / "history.csv"


def _recovery_path() -> Path:
    return _data_dir() / "recovery.tmp"


# ---------------------------------------------------------------------------
# History CSV fieldnames (includes paidoff_date)
# ---------------------------------------------------------------------------
HISTORY_FIELDNAMES = CSV_FIELDNAMES + ["paidoff_date"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ensure_loans_csv() -> None:
    """Create loans.csv with header if it does not exist."""
    path = _loans_path()
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()


def _ensure_history_csv() -> None:
    """Create history.csv with header if it does not exist."""
    path = _history_path()
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=HISTORY_FIELDNAMES)
            writer.writeheader()


def _read_all_rows(path: Path) -> List[dict]:
    """Read all rows from a CSV file; returns empty list if file absent."""
    if not path.exists():
        return []
    try:
        with path.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            return [dict(row) for row in reader]
    except Exception as exc:
        logger.error("Failed to read %s: %s", path, exc)
        return []


def _write_rows(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    """Overwrite a CSV file with the provided rows."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def read_loans() -> List[Loan]:
    """Read all non-Paidoff loans from loans.csv."""
    _ensure_loans_csv()
    rows = _read_all_rows(_loans_path())
    loans: List[Loan] = []
    for row in rows:
        try:
            loan = Loan.from_csv_row(row)
            if loan.status != "Paidoff":
                loans.append(loan)
        except Exception as exc:
            logger.warning("Skipping malformed row %s: %s", row, exc)
    return loans


def read_all_loans_including_paidoff() -> List[Loan]:
    """Read ALL loans from loans.csv (including Paidoff rows)."""
    _ensure_loans_csv()
    rows = _read_all_rows(_loans_path())
    loans: List[Loan] = []
    for row in rows:
        try:
            loans.append(Loan.from_csv_row(row))
        except Exception as exc:
            logger.warning("Skipping malformed row %s: %s", row, exc)
    return loans


def write_loan(loan: Loan) -> None:
    """Append a new loan record to loans.csv."""
    _ensure_loans_csv()
    try:
        with _loans_path().open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
            writer.writerow(loan.to_csv_row())
        logger.info("Loan written: %s", loan.reference_id)
    except Exception as exc:
        logger.error("Failed to write loan %s: %s", loan.reference_id, exc)
        raise


def update_loan(loan: Loan) -> None:
    """Update an existing loan record by reference_id (in-place rewrite)."""
    rows = _read_all_rows(_loans_path())
    updated = False
    new_rows: List[dict] = []
    for row in rows:
        if row.get("reference_id", "").strip() == loan.reference_id:
            new_rows.append(loan.to_csv_row())
            updated = True
        else:
            new_rows.append(row)
    if not updated:
        logger.warning("update_loan: reference_id not found: %s", loan.reference_id)
    _write_rows(_loans_path(), new_rows, CSV_FIELDNAMES)
    logger.info("Loan updated: %s", loan.reference_id)


def delete_loan(reference_id: str) -> bool:
    """Remove a loan record from loans.csv by reference_id.

    Returns True if a record was removed, False if not found.
    Eagerly resets the ref_id counter for the year_month if no records remain
    for that period after deletion (PD-17).
    """
    from loan_manager.ref_id_manager import RefIdManager

    rows = _read_all_rows(_loans_path())
    original_count = len(rows)

    deleted_row = next(
        (r for r in rows if r.get("reference_id", "").strip() == reference_id), None
    )
    if deleted_row is None:
        logger.warning("delete_loan: reference_id not found: %s", reference_id)
        return False

    new_rows = [r for r in rows if r.get("reference_id", "").strip() != reference_id]
    _write_rows(_loans_path(), new_rows, CSV_FIELDNAMES)
    logger.info("Loan deleted: %s", reference_id)

    # Eager counter reset: if no records remain for this year_month, reset counter (PD-17)
    ref_parts = reference_id.split("_")
    if len(ref_parts) >= 2:
        ym = f"{ref_parts[0]}_{ref_parts[1]}"
        remaining_for_ym = [
            r for r in new_rows
            if r.get("reference_id", "").startswith(ym + "_")
        ]
        if not remaining_for_ym:
            try:
                year, month = int(ref_parts[0]), int(ref_parts[1])
                manager = RefIdManager(meta_path=_data_dir() / "loans_meta.csv")
                manager.reset_counter(year, month)
                logger.info("Counter reset for %s after last record deleted", ym)
            except Exception as exc:
                logger.warning("Could not reset counter for %s: %s", ym, exc)

    return True


def mark_paidoff(reference_id: str, paidoff_date: date) -> None:
    """Atomic two-write protocol to mark a loan as Paidoff.

    Steps:
    1. Write target row to recovery.tmp
    2. Append to history.csv
    3. Remove from loans.csv
    4. Delete recovery.tmp on success
    """
    _ensure_history_csv()
    rows = _read_all_rows(_loans_path())
    target_row: Optional[dict] = None
    remaining_rows: List[dict] = []
    for row in rows:
        if row.get("reference_id", "").strip() == reference_id:
            target_row = row
        else:
            remaining_rows.append(row)

    if target_row is None:
        raise ValueError(f"reference_id not found: {reference_id}")

    recovery = _recovery_path()
    # Step 1: Write recovery file — reference_id only (PD-14)
    try:
        recovery.write_text(reference_id, encoding="utf-8")
        logger.info("Recovery file written for %s", reference_id)
    except Exception as exc:
        logger.error("Failed to write recovery file: %s", exc)
        raise

    # Step 2: Append to history.csv
    try:
        history_row = dict(target_row)
        history_row["status"] = "Paidoff"
        history_row["paidoff_date"] = paidoff_date.isoformat()
        with _history_path().open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=HISTORY_FIELDNAMES)
            writer.writerow(history_row)
        logger.info("Loan appended to history.csv: %s", reference_id)
    except Exception as exc:
        logger.error("Failed to append to history.csv: %s", exc)
        raise

    # Step 3: Remove from loans.csv
    try:
        _write_rows(_loans_path(), remaining_rows, CSV_FIELDNAMES)
        logger.info("Loan removed from loans.csv: %s", reference_id)
    except Exception as exc:
        logger.error("Failed to remove from loans.csv: %s", exc)
        raise

    # Step 4: Delete recovery.tmp
    try:
        recovery.unlink()
        logger.info("Recovery file deleted for %s", reference_id)
    except Exception as exc:
        logger.warning("Could not delete recovery.tmp: %s", exc)


def extend_loan(reference_id: str, new_giving_date: date, new_due_date: date) -> None:
    """Update giving_date and due_date for a loan extension (reuses reference_id)."""
    rows = _read_all_rows(_loans_path())
    updated = False
    new_rows: List[dict] = []
    for row in rows:
        if row.get("reference_id", "").strip() == reference_id:
            row["giving_date"] = new_giving_date.isoformat()
            row["due_date"] = new_due_date.isoformat()
            updated = True
        new_rows.append(row)
    if not updated:
        raise ValueError(f"reference_id not found: {reference_id}")
    _write_rows(_loans_path(), new_rows, CSV_FIELDNAMES)
    logger.info("Loan extended: %s -> giving=%s due=%s", reference_id, new_giving_date, new_due_date)


def read_autocomplete_values() -> Dict[str, List[str]]:
    """Return sorted unique values for autocomplete fields from active loans."""
    loans = read_loans()
    fields: Dict[str, set] = {
        "borrower_name": set(),
        "borrower_group": set(),
        "depositor_name": set(),
        "depositor_group": set(),
    }
    for loan in loans:
        if loan.borrower_name:
            fields["borrower_name"].add(loan.borrower_name)
        if loan.borrower_group:
            fields["borrower_group"].add(loan.borrower_group)
        if loan.depositor_name:
            fields["depositor_name"].add(loan.depositor_name)
        if loan.depositor_group:
            fields["depositor_group"].add(loan.depositor_group)

    return {k: sorted(v) for k, v in fields.items()}


def batch_extend_loans(extensions: List[dict]) -> None:
    """Batch-extend multiple loans in a single CSV rewrite.

    Per PD-30 (batch approval single-pass CSV rewrite).

    Args:
        extensions: list of dicts with keys:
            reference_id: str
            new_giving_date: date
            new_due_date: date or None
    """
    from loan_manager.csv_manager import CSVManager
    CSVManager().batch_extend_loans(_loans_path(), extensions)
    logger.info("Batch extended %d loans", len(extensions))
