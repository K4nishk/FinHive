"""
Tests for CSVReportManager.

Public API under test (loan_manager.report_manager.CSVReportManager):
    generate_report_id(reports_meta_path: Path, report_date: date) -> str
        Returns next available report_id for the given date.
        Format: RPT_YYYYMMDD_<order> (zero-padded to 3 digits minimum).
        Counter is stored in reports_meta.csv (report_date, counter columns).
        First report of a day -> RPT_YYYYMMDD_001
        Second report same day -> RPT_YYYYMMDD_002
        New calendar day resets to _001.

    write_report(reports_path, reports_meta_path, report) -> None
        Appends a PendingReport row to pending_reports.csv.
        Creates file with header on first write.

    write_report_records(records_path, records) -> None
        Appends a list of ReportRecord rows to pending_report_records.csv.
        Creates file with header on first write.

    read_pending_reports(reports_path) -> list[PendingReport]
        Returns only rows with status=Pending from pending_reports.csv.
        Returns empty list when file absent or header-only.

    update_report_status(reports_path, report_id, new_status, update_dt) -> None
        Rewrites pending_reports.csv with updated status for the given report_id.
        Also updates report_latest_update_dt to update_dt.
        No-op when report_id not found (PD-32).

    read_report_records(records_path, report_id) -> list[ReportRecord]
        Returns all line items for report_id from pending_report_records.csv.
        Returns empty list when file absent or no matching rows.

    get_active_reference_ids_in_queue(reports_path, records_path) -> set[str]
        Returns deduplicated reference_ids from all Pending-status reports.
        Approved and Declined reports are excluded.

    delete_report_records(records_path, report_id) -> None
        Removes all line items for report_id from pending_report_records.csv.
        No-op when file absent or no matching rows.

Storage rules (from PD-06, PD-07, PD-15, PD-16, run_4 DATA_MODEL.md):
  - reports_meta.csv: columns report_date (YYYYMMDD string), counter (integer)
  - pending_reports.csv columns (5 fields, exact production order):
      report_id, report_creation_date, report_latest_update_dt, mode, status
  - pending_report_records.csv columns (17 fields, exact production order):
      report_id, reference_id, borrower_name, amount, depositor_name,
      giving_date, due_date, interest_rate, commission_rate,
      extension_period, extension_period_unit, tds_flag,
      new_giving_date, new_due_date, interest_amount, commission_amount, tds_amount
  - Dates stored as ISO 8601 (YYYY-MM-DD)
  - tds_flag stored as lowercase "true" or "false"
  - Declined reports retain header row; line items hard-deleted (PD-16)
  - read_pending_reports returns Pending-status only (not all statuses)
"""

import csv
import pytest
from datetime import date, datetime
from pathlib import Path

from loan_manager.report_manager import CSVReportManager  # type: ignore[import]
from models.report import (
    PENDING_REPORT_FIELDNAMES,
    REPORT_RECORD_FIELDNAMES,
    PendingReport,
    ReportRecord,
)

TODAY: date = date(2026, 3, 22)
TODAY_DT: datetime = datetime(2026, 3, 22, 0, 0, 0)

META_FIELDNAMES = ["report_date", "counter"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_reports_csv(path: Path, reports: list) -> None:
    """Write PendingReport objects (or dicts) to pending_reports.csv for test setup."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=PENDING_REPORT_FIELDNAMES)
        writer.writeheader()
        for item in reports:
            if isinstance(item, PendingReport):
                writer.writerow(item.to_csv_row())
            else:
                writer.writerow(item)


def _write_records_csv(path: Path, records: list) -> None:
    """Write ReportRecord objects (or dicts) to pending_report_records.csv for test setup."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_RECORD_FIELDNAMES)
        writer.writeheader()
        for item in records:
            if isinstance(item, ReportRecord):
                writer.writerow(item.to_csv_row())
            else:
                writer.writerow(item)


def _write_meta_csv(path: Path, rows: list) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=META_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv_raw(path: Path) -> list:
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _make_pending_report(
    report_id: str = "RPT_20260322_001",
    mode: str = "Monthly",
    status: str = "Pending",
    creation_date: date = TODAY,
    update_dt: datetime = TODAY_DT,
) -> PendingReport:
    """Factory helper returning a PendingReport object."""
    return PendingReport(
        report_id=report_id,
        report_creation_date=creation_date,
        report_latest_update_dt=update_dt,
        mode=mode,
        status=status,
    )


def _make_report_record(
    report_id: str = "RPT_20260322_001",
    reference_id: str = "2026_01_001",
    borrower_name: str = "b1",
    amount: int = 10000,
    depositor_name: str = "d1",
    giving_date: date = date(2026, 1, 2),
    due_date: date = date(2026, 4, 2),
    interest_rate: float = 12.0,
    commission_rate: float = 2.0,
    extension_period: int = 3,
    extension_period_unit: str = "months",
    tds_flag: bool = False,
    new_giving_date: date = date(2026, 4, 2),
    new_due_date: date = date(2026, 7, 2),
    interest_amount: float = 300.0,
    commission_amount: float = 50.0,
    tds_amount: float = 0.0,
) -> ReportRecord:
    """Factory helper returning a ReportRecord object."""
    return ReportRecord(
        report_id=report_id,
        reference_id=reference_id,
        borrower_name=borrower_name,
        amount=amount,
        depositor_name=depositor_name,
        giving_date=giving_date,
        due_date=due_date,
        interest_rate=interest_rate,
        commission_rate=commission_rate,
        extension_period=extension_period,
        extension_period_unit=extension_period_unit,
        tds_flag=tds_flag,
        new_giving_date=new_giving_date,
        new_due_date=new_due_date,
        interest_amount=interest_amount,
        commission_amount=commission_amount,
        tds_amount=tds_amount,
    )


# ---------------------------------------------------------------------------
# generate_report_id
# ---------------------------------------------------------------------------

class TestGenerateReportId:
    def test_first_report_of_day_returns_001(self, data_dir: Path) -> None:
        """No existing reports for 2026-03-22 -> RPT_20260322_001."""
        meta_path = data_dir / "reports_meta.csv"
        manager = CSVReportManager()
        result = manager.generate_report_id(meta_path, TODAY)
        assert result == "RPT_20260322_001"

    def test_second_report_same_day_returns_002(self, data_dir: Path) -> None:
        """Counter at 1 for 20260322 -> next is RPT_20260322_002."""
        meta_path = data_dir / "reports_meta.csv"
        _write_meta_csv(meta_path, [{"report_date": "20260322", "counter": "1"}])
        manager = CSVReportManager()
        result = manager.generate_report_id(meta_path, TODAY)
        assert result == "RPT_20260322_002"

    def test_tenth_report_same_day_returns_010(self, data_dir: Path) -> None:
        meta_path = data_dir / "reports_meta.csv"
        _write_meta_csv(meta_path, [{"report_date": "20260322", "counter": "9"}])
        manager = CSVReportManager()
        result = manager.generate_report_id(meta_path, TODAY)
        assert result == "RPT_20260322_010"

    def test_new_calendar_day_resets_to_001(self, data_dir: Path) -> None:
        """Counter for 20260321 exists; new day 20260322 resets to 001."""
        meta_path = data_dir / "reports_meta.csv"
        _write_meta_csv(meta_path, [{"report_date": "20260321", "counter": "5"}])
        manager = CSVReportManager()
        result = manager.generate_report_id(meta_path, TODAY)
        assert result == "RPT_20260322_001"

    def test_meta_created_on_first_call(self, data_dir: Path) -> None:
        """reports_meta.csv must be created when it does not exist."""
        meta_path = data_dir / "reports_meta.csv"
        assert not meta_path.exists()
        manager = CSVReportManager()
        manager.generate_report_id(meta_path, TODAY)
        assert meta_path.exists()

    def test_counter_persists_after_call(self, data_dir: Path) -> None:
        """Counter written to meta CSV must reflect the new high-water mark."""
        meta_path = data_dir / "reports_meta.csv"
        manager = CSVReportManager()
        manager.generate_report_id(meta_path, TODAY)
        manager2 = CSVReportManager()
        second = manager2.generate_report_id(meta_path, TODAY)
        assert second == "RPT_20260322_002"

    def test_different_dates_have_independent_counters(self, data_dir: Path) -> None:
        """Counter for 20260321 and 20260322 are independent."""
        meta_path = data_dir / "reports_meta.csv"
        _write_meta_csv(meta_path, [
            {"report_date": "20260321", "counter": "3"},
            {"report_date": "20260322", "counter": "2"},
        ])
        manager = CSVReportManager()
        result = manager.generate_report_id(meta_path, TODAY)
        assert result == "RPT_20260322_003"

    @pytest.mark.parametrize("call_count,expected_order", [
        (1, "001"),
        (2, "002"),
        (5, "005"),
    ])
    def test_sequential_calls_increment_correctly(
        self, data_dir: Path, call_count: int, expected_order: str
    ) -> None:
        meta_path = data_dir / "reports_meta.csv"
        manager = CSVReportManager()
        result = None
        for _ in range(call_count):
            result = manager.generate_report_id(meta_path, TODAY)
        assert result == f"RPT_20260322_{expected_order}"

    def test_999th_report_gives_999(self, data_dir: Path) -> None:
        meta_path = data_dir / "reports_meta.csv"
        _write_meta_csv(meta_path, [{"report_date": "20260322", "counter": "998"}])
        manager = CSVReportManager()
        result = manager.generate_report_id(meta_path, TODAY)
        assert result == "RPT_20260322_999"

    def test_1000th_report_no_zero_padding_rollover(self, data_dir: Path) -> None:
        """After 999, counter extends beyond 3 digits without rollover."""
        meta_path = data_dir / "reports_meta.csv"
        _write_meta_csv(meta_path, [{"report_date": "20260322", "counter": "999"}])
        manager = CSVReportManager()
        result = manager.generate_report_id(meta_path, TODAY)
        assert result == "RPT_20260322_1000"


# ---------------------------------------------------------------------------
# write_report + read_pending_reports (round-trip)
# ---------------------------------------------------------------------------

class TestWriteAndReadPendingReports:
    def test_write_report_creates_file_on_first_write(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        meta_path = data_dir / "reports_meta.csv"
        manager = CSVReportManager()
        report = _make_pending_report()
        manager.write_report(reports_path, meta_path, report)
        assert reports_path.exists()

    def test_write_report_file_has_header_row(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        meta_path = data_dir / "reports_meta.csv"
        manager = CSVReportManager()
        manager.write_report(reports_path, meta_path, _make_pending_report())
        raw = _read_csv_raw(reports_path)
        assert len(raw) == 1
        assert "report_id" in raw[0]

    def test_read_pending_reports_empty_file_returns_empty_list(
        self, data_dir: Path
    ) -> None:
        reports_path = data_dir / "pending_reports.csv"
        reports_path.write_text("", encoding="utf-8")
        manager = CSVReportManager()
        result = manager.read_pending_reports(reports_path)
        assert result == []

    def test_read_pending_reports_file_absent_returns_empty_list(
        self, data_dir: Path
    ) -> None:
        reports_path = data_dir / "pending_reports.csv"
        assert not reports_path.exists()
        manager = CSVReportManager()
        result = manager.read_pending_reports(reports_path)
        assert result == []

    def test_write_read_round_trip_single_report(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        meta_path = data_dir / "reports_meta.csv"
        manager = CSVReportManager()
        report = _make_pending_report(report_id="RPT_20260322_001", status="Pending")
        manager.write_report(reports_path, meta_path, report)
        result = manager.read_pending_reports(reports_path)
        assert len(result) == 1
        assert result[0].report_id == "RPT_20260322_001"
        assert result[0].status == "Pending"

    def test_write_report_appends_second_report(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        meta_path = data_dir / "reports_meta.csv"
        manager = CSVReportManager()
        manager.write_report(reports_path, meta_path, _make_pending_report("RPT_20260322_001"))
        manager.write_report(reports_path, meta_path, _make_pending_report("RPT_20260322_002"))
        result = manager.read_pending_reports(reports_path)
        assert len(result) == 2
        ids = [r.report_id for r in result]
        assert "RPT_20260322_001" in ids
        assert "RPT_20260322_002" in ids

    def test_read_pending_reports_returns_only_pending_status(self, data_dir: Path) -> None:
        """read_pending_reports returns Pending rows only (not Approved or Declined)."""
        reports_path = data_dir / "pending_reports.csv"
        _write_reports_csv(reports_path, [
            _make_pending_report("RPT_20260322_001", status="Pending"),
            _make_pending_report("RPT_20260322_002", status="Approved"),
            _make_pending_report("RPT_20260322_003", status="Declined"),
        ])
        manager = CSVReportManager()
        result = manager.read_pending_reports(reports_path)
        assert len(result) == 1
        assert result[0].report_id == "RPT_20260322_001"
        assert result[0].status == "Pending"

    def test_write_report_header_only_returns_empty_list(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        _write_reports_csv(reports_path, [])
        manager = CSVReportManager()
        result = manager.read_pending_reports(reports_path)
        assert result == []

    def test_write_report_stores_report_id_correctly(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        meta_path = data_dir / "reports_meta.csv"
        manager = CSVReportManager()
        manager.write_report(reports_path, meta_path, _make_pending_report("RPT_20260322_007"))
        raw = _read_csv_raw(reports_path)
        assert raw[0]["report_id"] == "RPT_20260322_007"

    def test_write_report_stores_dates_as_iso8601(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        meta_path = data_dir / "reports_meta.csv"
        manager = CSVReportManager()
        manager.write_report(
            reports_path,
            meta_path,
            _make_pending_report(
                creation_date=date(2026, 3, 22),
                update_dt=datetime(2026, 3, 22, 0, 0, 0),
            ),
        )
        raw = _read_csv_raw(reports_path)
        assert raw[0]["report_creation_date"] == "2026-03-22"
        assert "2026-03-22" in raw[0]["report_latest_update_dt"]

    def test_write_report_stores_mode_correctly(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        meta_path = data_dir / "reports_meta.csv"
        manager = CSVReportManager()
        manager.write_report(reports_path, meta_path, _make_pending_report(mode="Daily"))
        raw = _read_csv_raw(reports_path)
        assert raw[0]["mode"] == "Daily"


# ---------------------------------------------------------------------------
# update_report_status
# ---------------------------------------------------------------------------

class TestUpdateReportStatus:
    def test_update_status_pending_to_approved(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        _write_reports_csv(reports_path, [_make_pending_report("RPT_20260322_001")])
        manager = CSVReportManager()
        manager.update_report_status(reports_path, "RPT_20260322_001", "Approved", TODAY_DT)
        raw = _read_csv_raw(reports_path)
        assert raw[0]["status"] == "Approved"

    def test_update_status_pending_to_declined(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        _write_reports_csv(reports_path, [_make_pending_report("RPT_20260322_001")])
        manager = CSVReportManager()
        manager.update_report_status(reports_path, "RPT_20260322_001", "Declined", TODAY_DT)
        raw = _read_csv_raw(reports_path)
        assert raw[0]["status"] == "Declined"

    def test_update_status_updates_latest_update_dt(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        old_dt = datetime(2026, 3, 20, 0, 0, 0)
        _write_reports_csv(reports_path, [
            _make_pending_report("RPT_20260322_001", update_dt=old_dt)
        ])
        manager = CSVReportManager()
        new_dt = datetime(2026, 3, 22, 0, 0, 0)
        manager.update_report_status(
            reports_path, "RPT_20260322_001", "Approved", new_dt
        )
        raw = _read_csv_raw(reports_path)
        assert "2026-03-22" in raw[0]["report_latest_update_dt"]

    def test_update_status_preserves_other_reports(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        _write_reports_csv(reports_path, [
            _make_pending_report("RPT_20260322_001", status="Pending"),
            _make_pending_report("RPT_20260322_002", status="Pending"),
        ])
        manager = CSVReportManager()
        manager.update_report_status(reports_path, "RPT_20260322_001", "Approved", TODAY_DT)
        raw = _read_csv_raw(reports_path)
        assert len(raw) == 2
        statuses = {r["report_id"]: r["status"] for r in raw}
        assert statuses["RPT_20260322_001"] == "Approved"
        assert statuses["RPT_20260322_002"] == "Pending"

    def test_update_status_nonexistent_report_id_is_noop(
        self, data_dir: Path
    ) -> None:
        """PD-32: no exception raised for missing report_id; existing rows unchanged."""
        reports_path = data_dir / "pending_reports.csv"
        _write_reports_csv(reports_path, [_make_pending_report("RPT_20260322_001")])
        manager = CSVReportManager()
        # Should NOT raise; is a no-op
        manager.update_report_status(
            reports_path, "RPT_99999999_999", "Approved", TODAY_DT
        )
        raw = _read_csv_raw(reports_path)
        assert raw[0]["status"] == "Pending"

    def test_update_status_preserves_creation_date(self, data_dir: Path) -> None:
        """report_creation_date must not change on status update."""
        reports_path = data_dir / "pending_reports.csv"
        _write_reports_csv(reports_path, [
            _make_pending_report("RPT_20260322_001", creation_date=date(2026, 3, 20))
        ])
        manager = CSVReportManager()
        manager.update_report_status(
            reports_path, "RPT_20260322_001", "Approved", TODAY_DT
        )
        raw = _read_csv_raw(reports_path)
        assert raw[0]["report_creation_date"] == "2026-03-20"

    def test_declined_report_row_retained_after_decline(self, data_dir: Path) -> None:
        """PD-16: declined reports are retained in CSV, not physically deleted."""
        reports_path = data_dir / "pending_reports.csv"
        _write_reports_csv(reports_path, [
            _make_pending_report("RPT_20260322_001", status="Pending"),
        ])
        manager = CSVReportManager()
        manager.update_report_status(
            reports_path, "RPT_20260322_001", "Declined", TODAY_DT
        )
        raw = _read_csv_raw(reports_path)
        assert len(raw) == 1
        assert raw[0]["status"] == "Declined"


# ---------------------------------------------------------------------------
# read_report_records
# ---------------------------------------------------------------------------

class TestReadReportRecords:
    def test_read_report_records_file_absent_returns_empty_list(
        self, data_dir: Path
    ) -> None:
        records_path = data_dir / "pending_report_records.csv"
        manager = CSVReportManager()
        result = manager.read_report_records(records_path, "RPT_20260322_001")
        assert result == []

    def test_read_report_records_returns_matching_rows_only(
        self, data_dir: Path
    ) -> None:
        records_path = data_dir / "pending_report_records.csv"
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", reference_id="2026_01_001"),
            _make_report_record("RPT_20260322_001", reference_id="2026_01_002"),
            _make_report_record("RPT_20260322_002", reference_id="2026_01_003"),
        ])
        manager = CSVReportManager()
        result = manager.read_report_records(records_path, "RPT_20260322_001")
        assert len(result) == 2
        ids = [r.reference_id for r in result]
        assert "2026_01_001" in ids
        assert "2026_01_002" in ids
        assert "2026_01_003" not in ids

    def test_read_report_records_no_matching_report_id_returns_empty_list(
        self, data_dir: Path
    ) -> None:
        records_path = data_dir / "pending_report_records.csv"
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001"),
        ])
        manager = CSVReportManager()
        result = manager.read_report_records(records_path, "RPT_20260322_999")
        assert result == []

    def test_read_report_records_returns_correct_reference_ids(
        self, data_dir: Path
    ) -> None:
        records_path = data_dir / "pending_report_records.csv"
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", reference_id="2026_03_001"),
            _make_report_record("RPT_20260322_001", reference_id="2026_03_002"),
        ])
        manager = CSVReportManager()
        result = manager.read_report_records(records_path, "RPT_20260322_001")
        ids = [r.reference_id for r in result]
        assert ids == ["2026_03_001", "2026_03_002"]

    def test_read_report_records_header_only_file_returns_empty_list(
        self, data_dir: Path
    ) -> None:
        records_path = data_dir / "pending_report_records.csv"
        _write_records_csv(records_path, [])
        manager = CSVReportManager()
        result = manager.read_report_records(records_path, "RPT_20260322_001")
        assert result == []


# ---------------------------------------------------------------------------
# write_report_records + read_report_records (round-trip)
# ---------------------------------------------------------------------------

class TestWriteAndReadReportRecords:
    def test_write_records_creates_file_on_first_write(self, data_dir: Path) -> None:
        records_path = data_dir / "pending_report_records.csv"
        manager = CSVReportManager()
        manager.write_report_records(records_path, [_make_report_record()])
        assert records_path.exists()

    def test_write_records_appends_to_existing_file(self, data_dir: Path) -> None:
        records_path = data_dir / "pending_report_records.csv"
        manager = CSVReportManager()
        manager.write_report_records(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
        ])
        manager.write_report_records(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_002"),
        ])
        raw = _read_csv_raw(records_path)
        assert len(raw) == 2

    def test_write_read_round_trip_single_record(self, data_dir: Path) -> None:
        records_path = data_dir / "pending_report_records.csv"
        manager = CSVReportManager()
        record = _make_report_record(
            report_id="RPT_20260322_001",
            reference_id="2026_01_001",
            borrower_name="b1",
            amount=10000,
        )
        manager.write_report_records(records_path, [record])
        result = manager.read_report_records(records_path, "RPT_20260322_001")
        assert len(result) == 1
        assert result[0].reference_id == "2026_01_001"
        assert result[0].borrower_name == "b1"

    def test_write_read_round_trip_multiple_records(self, data_dir: Path) -> None:
        records_path = data_dir / "pending_report_records.csv"
        manager = CSVReportManager()
        rows = [
            _make_report_record("RPT_20260322_001", f"2026_01_00{i}")
            for i in range(1, 6)
        ]
        manager.write_report_records(records_path, rows)
        result = manager.read_report_records(records_path, "RPT_20260322_001")
        assert len(result) == 5


# ---------------------------------------------------------------------------
# get_active_reference_ids_in_queue
# ---------------------------------------------------------------------------

class TestGetActiveReferenceIdsInQueue:
    def test_pending_reports_reference_ids_are_included(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        records_path = data_dir / "pending_report_records.csv"
        _write_reports_csv(reports_path, [
            _make_pending_report("RPT_20260322_001", status="Pending"),
        ])
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
            _make_report_record("RPT_20260322_001", "2026_01_002"),
        ])
        manager = CSVReportManager()
        result = manager.get_active_reference_ids_in_queue(reports_path, records_path)
        assert "2026_01_001" in result
        assert "2026_01_002" in result

    def test_approved_reports_are_excluded(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        records_path = data_dir / "pending_report_records.csv"
        _write_reports_csv(reports_path, [
            _make_pending_report("RPT_20260322_001", status="Approved"),
        ])
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
        ])
        manager = CSVReportManager()
        result = manager.get_active_reference_ids_in_queue(reports_path, records_path)
        assert "2026_01_001" not in result

    def test_declined_reports_are_excluded(self, data_dir: Path) -> None:
        """PD-16: Declined reports stay in CSV but are excluded from active queue."""
        reports_path = data_dir / "pending_reports.csv"
        records_path = data_dir / "pending_report_records.csv"
        _write_reports_csv(reports_path, [
            _make_pending_report("RPT_20260322_001", status="Declined"),
        ])
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
        ])
        manager = CSVReportManager()
        result = manager.get_active_reference_ids_in_queue(reports_path, records_path)
        assert "2026_01_001" not in result

    def test_only_pending_report_reference_ids_are_included(
        self, data_dir: Path
    ) -> None:
        """Mixed statuses: only Pending report's records appear in result."""
        reports_path = data_dir / "pending_reports.csv"
        records_path = data_dir / "pending_report_records.csv"
        _write_reports_csv(reports_path, [
            _make_pending_report("RPT_20260322_001", status="Pending"),
            _make_pending_report("RPT_20260322_002", status="Approved"),
            _make_pending_report("RPT_20260322_003", status="Declined"),
        ])
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
            _make_report_record("RPT_20260322_002", "2026_01_002"),
            _make_report_record("RPT_20260322_003", "2026_01_003"),
        ])
        manager = CSVReportManager()
        result = manager.get_active_reference_ids_in_queue(reports_path, records_path)
        assert "2026_01_001" in result
        assert "2026_01_002" not in result
        assert "2026_01_003" not in result

    def test_duplicate_reference_ids_across_pending_reports_are_deduplicated(
        self, data_dir: Path
    ) -> None:
        """Same reference_id in two Pending reports appears once in result set."""
        reports_path = data_dir / "pending_reports.csv"
        records_path = data_dir / "pending_report_records.csv"
        _write_reports_csv(reports_path, [
            _make_pending_report("RPT_20260322_001", status="Pending"),
            _make_pending_report("RPT_20260322_002", status="Pending"),
        ])
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
            _make_report_record("RPT_20260322_002", "2026_01_001"),
        ])
        manager = CSVReportManager()
        result = manager.get_active_reference_ids_in_queue(reports_path, records_path)
        assert isinstance(result, set)
        assert len([r for r in result if r == "2026_01_001"]) == 1

    def test_empty_queue_returns_empty_set(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        records_path = data_dir / "pending_report_records.csv"
        assert not reports_path.exists()
        assert not records_path.exists()
        manager = CSVReportManager()
        result = manager.get_active_reference_ids_in_queue(reports_path, records_path)
        assert isinstance(result, set)
        assert len(result) == 0

    def test_no_pending_reports_returns_empty_set(self, data_dir: Path) -> None:
        reports_path = data_dir / "pending_reports.csv"
        records_path = data_dir / "pending_report_records.csv"
        _write_reports_csv(reports_path, [
            _make_pending_report("RPT_20260322_001", status="Approved"),
        ])
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
        ])
        manager = CSVReportManager()
        result = manager.get_active_reference_ids_in_queue(reports_path, records_path)
        assert isinstance(result, set)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# delete_report_records
# ---------------------------------------------------------------------------

class TestDeleteReportRecords:
    def test_delete_removes_records_for_report_id(self, data_dir: Path) -> None:
        records_path = data_dir / "pending_report_records.csv"
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
            _make_report_record("RPT_20260322_001", "2026_01_002"),
            _make_report_record("RPT_20260322_002", "2026_01_003"),
        ])
        manager = CSVReportManager()
        manager.delete_report_records(records_path, "RPT_20260322_001")
        raw = _read_csv_raw(records_path)
        remaining_ids = [r["reference_id"] for r in raw]
        assert "2026_01_001" not in remaining_ids
        assert "2026_01_002" not in remaining_ids
        assert "2026_01_003" in remaining_ids

    def test_delete_preserves_other_reports_records(self, data_dir: Path) -> None:
        records_path = data_dir / "pending_report_records.csv"
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
            _make_report_record("RPT_20260322_002", "2026_01_002"),
        ])
        manager = CSVReportManager()
        manager.delete_report_records(records_path, "RPT_20260322_001")
        raw = _read_csv_raw(records_path)
        assert len(raw) == 1
        assert raw[0]["reference_id"] == "2026_01_002"

    def test_delete_file_absent_is_noop(self, data_dir: Path) -> None:
        records_path = data_dir / "pending_report_records.csv"
        assert not records_path.exists()
        manager = CSVReportManager()
        manager.delete_report_records(records_path, "RPT_20260322_001")
        # No exception expected

    def test_delete_nonexistent_report_id_is_noop(self, data_dir: Path) -> None:
        records_path = data_dir / "pending_report_records.csv"
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
        ])
        manager = CSVReportManager()
        manager.delete_report_records(records_path, "RPT_99999999_999")
        raw = _read_csv_raw(records_path)
        assert len(raw) == 1

    def test_delete_header_retained_when_all_records_deleted(
        self, data_dir: Path
    ) -> None:
        """PD-16: report header row in pending_reports.csv is NOT touched by delete_report_records.
        This test verifies the records CSV is left with header only after deleting all rows."""
        records_path = data_dir / "pending_report_records.csv"
        _write_records_csv(records_path, [
            _make_report_record("RPT_20260322_001", "2026_01_001"),
        ])
        manager = CSVReportManager()
        manager.delete_report_records(records_path, "RPT_20260322_001")
        raw = _read_csv_raw(records_path)
        assert raw == []
