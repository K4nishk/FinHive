"""CSVReportManager — injectable-path class API for pending reports workflow.

Architecture (ADR-001):
    loan_manager/* = class-based, injectable-path units — used exclusively by tests.
    data/*         = application-layer adapter functions — used exclusively by UI code.

PD-06: Two-file normalised storage:
    pending_reports.csv       — report header metadata (PendingReport rows)
    pending_report_records.csv — per-loan line items (ReportRecord rows)

PD-07: report_id format: RPT_YYYYMMDD_<order> e.g. RPT_20260320_001
PD-15: report_id day-counter stored in separate reports_meta.csv
PD-16: Declined reports retained with status=Declined (not physically deleted)
PD-18: Batch approval single-write model
PD-19: Duplicate reference_id detection at approval time
"""
import csv
import logging
from datetime import date, datetime
from pathlib import Path

from models.report import (
    PENDING_REPORT_FIELDNAMES,
    REPORT_RECORD_FIELDNAMES,
    PendingReport,
    ReportRecord,
)

logger = logging.getLogger(__name__)

_REPORTS_META_FIELDNAMES = ["report_date", "counter"]


class CSVReportManager:
    """Manages pending_reports.csv, pending_report_records.csv, and reports_meta.csv.

    All paths are injected — no implicit path resolution. This makes the class
    fully testable without touching the real ./data/ directory.
    """

    # ------------------------------------------------------------------
    # Internal CSV helpers
    # ------------------------------------------------------------------

    def _read_raw(self, path: Path) -> list[dict]:
        """Read all rows from a CSV file; return empty list if absent or empty."""
        if not path.exists() or path.stat().st_size == 0:
            return []
        with path.open("r", newline="", encoding="utf-8-sig") as fh:
            return list(csv.DictReader(fh))

    def _write_raw(
        self, path: Path, rows: list[dict], fieldnames: list[str]
    ) -> None:
        """Overwrite a CSV file with the given rows."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def _append_raw(
        self, path: Path, row: dict, fieldnames: list[str]
    ) -> None:
        """Append a single row; write header if file is new/empty."""
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists() or path.stat().st_size == 0
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow(row)

    # ------------------------------------------------------------------
    # reports_meta.csv helpers  (PD-15)
    # ------------------------------------------------------------------

    def _read_reports_meta(self, reports_meta_path: Path) -> dict[str, int]:
        """Read reports_meta.csv; return mapping of YYYYMMDD -> counter int."""
        rows = self._read_raw(reports_meta_path)
        result: dict[str, int] = {}
        for row in rows:
            report_date = (row.get("report_date") or "").strip()
            raw_counter = (row.get("counter") or "").strip()
            if not report_date:
                continue
            try:
                result[report_date] = int(raw_counter) if raw_counter else 0
            except ValueError:
                result[report_date] = 0
        return result

    def _write_reports_meta(
        self, reports_meta_path: Path, meta: dict[str, int]
    ) -> None:
        """Overwrite reports_meta.csv with the provided mapping."""
        rows = [
            {"report_date": rd, "counter": str(ctr)}
            for rd, ctr in sorted(meta.items())
        ]
        self._write_raw(reports_meta_path, rows, _REPORTS_META_FIELDNAMES)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_report_id(self, reports_meta_path: Path, report_date: date) -> str:
        """Generate the next report_id for the given date.

        Format: RPT_YYYYMMDD_<order> e.g. RPT_20260320_001
        Order is zero-padded to 3 digits for values 001-999.
        Beyond 999 the order is written without zero-padding (e.g. 1000).
        """
        date_key = report_date.strftime("%Y%m%d")
        meta = self._read_reports_meta(reports_meta_path)
        current = meta.get(date_key, 0)
        next_order = current + 1

        order_str = f"{next_order:03d}" if next_order <= 999 else str(next_order)
        report_id = f"RPT_{date_key}_{order_str}"

        meta[date_key] = next_order
        self._write_reports_meta(reports_meta_path, meta)

        logger.info("Generated report_id: %s", report_id)
        return report_id

    def write_report(
        self,
        reports_path: Path,
        reports_meta_path: Path,
        report: PendingReport,
    ) -> None:
        """Append a PendingReport header row to pending_reports.csv.

        reports_meta_path is accepted for API symmetry; the counter has
        already been incremented by generate_report_id().
        """
        self._append_raw(reports_path, report.to_csv_row(), PENDING_REPORT_FIELDNAMES)
        logger.info("Report written: %s (status=%s)", report.report_id, report.status)

    def write_report_records(
        self, records_path: Path, records: list[ReportRecord]
    ) -> None:
        """Append multiple ReportRecord line items to pending_report_records.csv."""
        for record in records:
            self._append_raw(
                records_path, record.to_csv_row(), REPORT_RECORD_FIELDNAMES
            )
        logger.info(
            "Wrote %d record(s) for report_id=%s",
            len(records),
            records[0].report_id if records else "n/a",
        )

    def read_pending_reports(self, reports_path: Path) -> list[PendingReport]:
        """Read pending_reports.csv and return only rows with status=Pending.

        Declined and Approved reports are retained in storage (PD-16) but are
        filtered from the active queue returned by this method.
        """
        rows = self._read_raw(reports_path)
        result: list[PendingReport] = []
        for row in rows:
            try:
                report = PendingReport.from_csv_row(row)
                if report.status == "Pending":
                    result.append(report)
            except Exception as exc:
                logger.warning("Skipping malformed report row %s: %s", row, exc)
        return result

    def read_report_records(
        self, records_path: Path, report_id: str
    ) -> list[ReportRecord]:
        """Return all ReportRecord line items for the given report_id."""
        rows = self._read_raw(records_path)
        result: list[ReportRecord] = []
        for row in rows:
            if row.get("report_id", "").strip() != report_id:
                continue
            try:
                result.append(ReportRecord.from_csv_row(row))
            except Exception as exc:
                logger.warning(
                    "Skipping malformed record row for %s: %s", report_id, exc
                )
        return result

    def update_report_status(
        self,
        reports_path: Path,
        report_id: str,
        new_status: str,
        update_dt: datetime,
    ) -> None:
        """Update status and report_latest_update_dt for the given report_id.

        No-op if report_id is not found.
        """
        rows = self._read_raw(reports_path)
        found = False
        for row in rows:
            if row.get("report_id", "").strip() == report_id:
                row["status"] = new_status
                row["report_latest_update_dt"] = update_dt.isoformat()
                found = True
        if not found:
            logger.warning(
                "update_report_status: report_id not found: %s", report_id
            )
        self._write_raw(reports_path, rows, PENDING_REPORT_FIELDNAMES)
        logger.info(
            "Report status updated: %s -> %s", report_id, new_status
        )

    def delete_report_records(
        self, records_path: Path, report_id: str
    ) -> None:
        """Remove all line items for the given report_id from pending_report_records.csv.

        Note: report headers are retained with status=Declined per PD-16.
        This method is used to clean up line items when a report is declined.
        """
        rows = self._read_raw(records_path)
        remaining = [
            r for r in rows if r.get("report_id", "").strip() != report_id
        ]
        self._write_raw(records_path, remaining, REPORT_RECORD_FIELDNAMES)
        logger.info("Deleted record lines for report_id: %s", report_id)

    def update_report_records(
        self, records_path: Path, report_id: str, records: list[ReportRecord]
    ) -> None:
        """Replace all line items for the given report_id in pending_report_records.csv.

        Used when a user inline-edits parameters in the Pending Approval Tab (PD-25/R5).
        """
        all_rows = self._read_raw(records_path)
        other_rows = [
            r for r in all_rows if r.get("report_id", "").strip() != report_id
        ]
        new_rows = other_rows + [rec.to_csv_row() for rec in records]
        self._write_raw(records_path, new_rows, REPORT_RECORD_FIELDNAMES)
        logger.info(
            "Updated %d record(s) for report_id=%s", len(records), report_id
        )

    def get_active_reference_ids_in_queue(
        self, reports_path: Path, records_path: Path
    ) -> set[str]:
        """Return the set of reference_ids currently in any Pending report.

        Used by PD-19 duplicate detection at approval time: before approving
        a report, the caller checks whether its reference_ids overlap with
        those returned here (excluding the report being approved).
        """
        pending_reports = self.read_pending_reports(reports_path)
        pending_ids = {r.report_id for r in pending_reports}

        all_record_rows = self._read_raw(records_path)
        result: set[str] = set()
        for row in all_record_rows:
            if row.get("report_id", "").strip() in pending_ids:
                ref_id = row.get("reference_id", "").strip()
                if ref_id:
                    result.add(ref_id)
        return result
