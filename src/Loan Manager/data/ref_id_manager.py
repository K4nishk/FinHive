"""Reference ID generation for the application layer.

Wraps loan_manager.RefIdManager with path resolution and reset logic
tied to actual CSV contents.
"""
import logging
from pathlib import Path

from data.csv_manager import _data_dir, read_all_loans_including_paidoff
from loan_manager.ref_id_manager import RefIdManager

logger = logging.getLogger(__name__)


def _meta_path() -> Path:
    return _data_dir() / "loans_meta.csv"


def _get_manager() -> RefIdManager:
    return RefIdManager(meta_path=_meta_path())


def _active_year_months() -> set:
    """Return the set of YYYY_MM strings that currently have any loan records.

    Derives YYYY_MM from the reference_id field (first two underscore-separated
    segments), not from giving_date. This correctly maps each loan to its entry
    month, not its giving month.

    Guard: loans with malformed reference_ids (fewer than 2 underscore-separated
    segments) are skipped to avoid corrupting the counter.
    """
    loans = read_all_loans_including_paidoff()
    ym_set = set()
    for loan in loans:
        parts = loan.reference_id.split("_")
        if len(parts) >= 2:
            ym = f"{parts[0]}_{parts[1]}"
            ym_set.add(ym)
    return ym_set


def generate_ref_id(year: int, month: int) -> str:
    """Generate the next reference_id for a given year and month.

    If all records for YYYY_MM have been deleted (none remain in loans.csv),
    the counter is reset before generating the next ID, so 001 is returned.
    """
    manager = _get_manager()
    ym = f"{year:04d}_{month:02d}"
    active_yms = _active_year_months()

    if ym not in active_yms:
        # All records for this month are gone — reset counter so next ID is 001
        manager.reset_counter(year, month)

    return manager.next_ref_id(year, month)
