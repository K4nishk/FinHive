"""Sample data seeder — R7.

Seeds the 15 sample loan records from REQUIREMENTS.md into loans.csv on first
application launch (when loans.csv is absent or contains no data rows).

Guard condition:
    - loans.csv does not exist → seed
    - loans.csv exists but has no data rows (empty file or header-only) → seed
    - loans.csv has existing data rows → skip (protect user data)

After seeding, loans_meta.csv is updated with the correct high-water counters:
    2026_01 → 2  (b1, b2)
    2026_02 → 9  (b3 through b11)
    2026_03 → 4  (b12 through b15)

Statuses are auto-computed via compute_status() rather than hardcoded, so they
reflect the correct state for today's date.
"""
import csv
import logging
from datetime import date
from pathlib import Path
from typing import List

from loan_manager.ref_id_manager import RefIdManager
from loan_manager.status_engine import compute_status
from models.loan import CSV_FIELDNAMES, Loan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sample records from REQUIREMENTS.md
# ---------------------------------------------------------------------------

_SAMPLE_RECORDS = [
    # (ref_id, borrower_name, borrower_group, amount, giving_date, depositor_name, depositor_group, due_date)
    ("2026_01_001", "b1",  "bg1", 10000, date(2026, 1, 2),  "d1",  "dg1",  date(2026, 4, 2)),
    ("2026_01_002", "b2",  "bg2", 10000, date(2026, 1, 4),  "d2",  "dg1",  date(2026, 5, 4)),
    ("2026_02_001", "b3",  "bg3", 15000, date(2026, 2, 6),  "d3",  "dg1",  date(2026, 5, 6)),
    ("2026_02_002", "b4",  "bg3", 20000, date(2026, 2, 7),  "d4",  "dg2",  date(2026, 6, 7)),
    ("2026_02_003", "b5",  "bg4", 20000, date(2026, 2, 8),  "d5",  "dg2",  date(2026, 6, 8)),
    ("2026_02_004", "b6",  "bg4", 15000, date(2026, 2, 8),  "d6",  "dg3",  date(2026, 7, 8)),
    ("2026_02_005", "b7",  "bg5", 15000, date(2026, 2, 15), "d7",  "dg3",  date(2026, 7, 15)),
    ("2026_02_006", "b8",  "bg5", 20000, date(2026, 2, 18), "d8",  "dg3",  date(2026, 6, 18)),
    ("2026_02_007", "b9",  "bg1", 20000, date(2026, 2, 20), "d9",  "dg3",  date(2026, 6, 20)),
    ("2026_02_008", "b10", "bg6", 10000, date(2026, 2, 25), "d10", "dg1",  date(2026, 5, 25)),
    ("2026_02_009", "b11", "bg6", 15000, date(2026, 2, 28), "d11", "dg2",  date(2026, 5, 28)),
    ("2026_03_001", "b12", "bg7", 15000, date(2026, 3, 2),  "d12", "dg4",  date(2026, 7, 2)),
    ("2026_03_002", "b13", "bg7", 10000, date(2026, 3, 5),  "d13", "dg4",  date(2026, 7, 5)),
    ("2026_03_003", "b14", "bg8", 15000, date(2026, 3, 10), "d14", None,   date(2026, 7, 10)),
    ("2026_03_004", "b15", "bg8", 20000, date(2026, 3, 14), "d15", None,   date(2026, 7, 14)),
]

# High-water counters after seeding — maps YYYY_MM string to counter int
_SEED_META_COUNTERS = {
    "2026_01": 2,
    "2026_02": 9,
    "2026_03": 4,
}


def _is_empty(loans_path: Path) -> bool:
    """Return True if loans_path does not exist or has no data rows."""
    if not loans_path.exists():
        return True
    if loans_path.stat().st_size == 0:
        return True
    # Check for header-only file
    try:
        with loans_path.open("r", newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for _ in reader:
                return False  # at least one data row found
        return True  # no data rows
    except Exception:
        return True


def seed_sample_data(loans_path: Path, meta_path: Path) -> bool:
    """Seed 15 sample loan records into loans.csv if the file is absent or empty.

    Args:
        loans_path: Path to loans.csv
        meta_path:  Path to loans_meta.csv

    Returns:
        True if seeding occurred, False if skipped (existing data present).
    """
    if not _is_empty(loans_path):
        logger.debug("Seed skipped: loans.csv already has data.")
        return False

    today = date.today()
    loans_path.parent.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    for (
        ref_id, borrower_name, borrower_group, amount,
        giving_date, depositor_name, depositor_group, due_date,
    ) in _SAMPLE_RECORDS:
        status = compute_status(
            giving_date=giving_date,
            due_date=due_date,
            current_status="",
            today=today,
        )
        loan = Loan(
            reference_id=ref_id,
            borrower_name=borrower_name,
            borrower_group=borrower_group,
            amount=amount,
            giving_date=giving_date,
            depositor_name=depositor_name,
            depositor_group=depositor_group,
            due_date=due_date,
            status=status,
        )
        rows.append(loan.to_csv_row())

    # Write all sample records in a single batch write
    with loans_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Sample data seeded: %d records into %s", len(rows), loans_path)

    # Update loans_meta.csv with the correct high-water counters
    try:
        manager = RefIdManager(meta_path=meta_path)
        # Read existing meta and set counters for seeded months
        existing_meta = manager._read_meta()
        for ym, counter in _SEED_META_COUNTERS.items():
            existing_meta[ym] = counter
        manager._write_meta(existing_meta)
        logger.info("loans_meta.csv updated with seed counters: %s", _SEED_META_COUNTERS)
    except Exception as exc:
        logger.warning("Could not update loans_meta.csv after seeding: %s", exc)

    return True
