"""Application-layer adapter for the pending reports workflow.

Architecture (ADR-001):
    This module (data/*) is the thin adapter layer used exclusively by UI code.
    It resolves paths from ./data/ and delegates all logic to
    loan_manager.CSVReportManager.

    Tests import from loan_manager.report_manager directly (injectable paths).
    UI code imports from this module only.
"""
import logging
from datetime import date, datetime
from pathlib import Path

from data.csv_manager import _data_dir
from loan_manager.report_manager import CSVReportManager
from models.report import PendingReport, ReportRecord

logger = logging.getLogger(__name__)

_manager = CSVReportManager()


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _reports_path() -> Path:
    return _data_dir() / "pending_reports.csv"


def _records_path() -> Path:
    return _data_dir() / "pending_report_records.csv"


def _reports_meta_path() -> Path:
    return _data_dir() / "reports_meta.csv"


# ---------------------------------------------------------------------------
# Public adapter API
# ---------------------------------------------------------------------------

def generate_report_id(report_date: date) -> str:
    """Generate the next report_id for the given date.

    Delegates to CSVReportManager.generate_report_id() with the
    resolved reports_meta.csv path.
    """
    return _manager.generate_report_id(_reports_meta_path(), report_date)


def write_report(report: PendingReport) -> None:
    """Append a PendingReport header row to pending_reports.csv."""
    _manager.write_report(_reports_path(), _reports_meta_path(), report)


def write_report_records(records: list[ReportRecord]) -> None:
    """Append ReportRecord line items to pending_report_records.csv."""
    _manager.write_report_records(_records_path(), records)


def read_pending_reports() -> list[PendingReport]:
    """Return all reports with status=Pending from pending_reports.csv."""
    return _manager.read_pending_reports(_reports_path())


def read_report_records(report_id: str) -> list[ReportRecord]:
    """Return all line items for the given report_id."""
    return _manager.read_report_records(_records_path(), report_id)


def update_report_status(
    report_id: str, new_status: str, update_dt: datetime
) -> None:
    """Update status and report_latest_update_dt for the given report_id."""
    _manager.update_report_status(
        _reports_path(), report_id, new_status, update_dt
    )


def update_report_records(report_id: str, records: list[ReportRecord]) -> None:
    """Replace all line items for the given report_id (used for inline edits)."""
    _manager.update_report_records(_records_path(), report_id, records)


def delete_report_records(report_id: str) -> None:
    """Remove all line items for the given report_id from pending_report_records.csv."""
    _manager.delete_report_records(_records_path(), report_id)


def get_active_reference_ids_in_queue() -> set[str]:
    """Return the set of reference_ids currently in any Pending report.

    Used for PD-19 duplicate detection at approval time.
    """
    return _manager.get_active_reference_ids_in_queue(
        _reports_path(), _records_path()
    )
