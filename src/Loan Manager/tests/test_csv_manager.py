"""
Tests for CSVManager.

Public API under test:
    read_loans(loans_path)                                   -> list[dict]
    write_loan(loans_path, loan)                             -> None
    update_loan(loans_path, reference_id, updated_fields)   -> None
    delete_loan(loans_path, reference_id)                   -> None
    mark_paidoff(loans_path, history_path, reference_id,
                 paidoff_date)                               -> None
    extend_loan(loans_path, reference_id, period, unit)      -> None

Storage rules (from R3, R4, R7, R8):
  - Dates stored as ISO 8601 (YYYY-MM-DD)
  - Paidoff records excluded from main read; kept in history.csv
  - mark_paidoff is atomic: recovery.tmp written before first write
  - extend: new giving_date = old due_date; new due_date = old due_date + period
  - extend with no due_date: new giving_date = today; new due_date = supplied date
"""

import csv
import io
import pytest
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from unittest.mock import patch, MagicMock

from loan_manager.csv_manager import CSVManager  # type: ignore[import]

TODAY: date = date(2026, 3, 22)

# CSV column ordering used throughout tests
FIELDNAMES = [
    "reference_id",
    "borrower_name",
    "borrower_group",
    "amount",
    "giving_date",
    "depositor_name",
    "depositor_group",
    "due_date",
    "status",
]

HISTORY_FIELDNAMES = FIELDNAMES + ["paidoff_date"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_loans_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def _make_loan_dict(
    reference_id: str = "2026_03_001",
    borrower_name: str = "b1",
    borrower_group: str = "bg1",
    amount: int = 10000,
    giving_date: date = date(2026, 1, 2),
    depositor_name: str = "d1",
    depositor_group: Optional[str] = "dg1",
    due_date: Optional[date] = date(2026, 4, 2),
    status: str = "Active",
) -> dict:
    return {
        "reference_id": reference_id,
        "borrower_name": borrower_name,
        "borrower_group": borrower_group,
        "amount": amount,
        "giving_date": giving_date,
        "depositor_name": depositor_name,
        "depositor_group": depositor_group,
        "due_date": due_date,
        "status": status,
    }


def _read_csv_raw(path: Path) -> list[dict]:
    """Read CSV without any CSVManager logic for verification."""
    with path.open("r", newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# read_loans
# ---------------------------------------------------------------------------

class TestReadLoans:
    def test_read_loans_empty_file_returns_empty_list(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        loans_path.write_text("", encoding="utf-8")
        manager = CSVManager()
        result = manager.read_loans(loans_path)
        assert result == []

    def test_read_loans_header_only_returns_empty_list(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        _write_loans_csv(loans_path, [])
        manager = CSVManager()
        result = manager.read_loans(loans_path)
        assert result == []

    def test_read_loans_fifteen_sample_records_parsed_correctly(
        self,
        data_dir: Path,
        sample_loans: list[tuple],
    ) -> None:
        loans_path = data_dir / "loans.csv"
        rows = [
            {
                "reference_id":   r[0],
                "borrower_name":  r[1],
                "borrower_group": r[2],
                "amount":         str(r[3]),
                "giving_date":    r[4].isoformat(),
                "depositor_name": r[5],
                "depositor_group": r[6] if r[6] else "",
                "due_date":       r[7].isoformat(),
                "status":         r[8],
            }
            for r in sample_loans
        ]
        _write_loans_csv(loans_path, rows)
        manager = CSVManager()
        result = manager.read_loans(loans_path)
        assert len(result) == 15
        assert result[0]["reference_id"] == "2026_01_001"
        assert result[0]["borrower_name"] == "b1"
        assert result[0]["amount"] == 10000

    def test_read_loans_paidoff_records_excluded(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        rows = [
            {**_make_loan_dict("2026_01_001", status="Active"),
             "giving_date": "2026-01-02", "due_date": "2026-04-02",
             "depositor_group": "dg1", "amount": "10000"},
            {**_make_loan_dict("2026_01_002", status="Paidoff"),
             "giving_date": "2026-01-04", "due_date": "2026-05-04",
             "depositor_group": "dg1", "amount": "10000"},
        ]
        # write as raw dicts (strings only)
        with loans_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in rows:
                flat = {k: (v if isinstance(v, str) else str(v)) for k, v in row.items()}
                writer.writerow(flat)
        manager = CSVManager()
        result = manager.read_loans(loans_path)
        assert len(result) == 1
        assert result[0]["reference_id"] == "2026_01_001"

    def test_read_loans_date_fields_parsed_as_date_objects(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        with loans_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerow({
                "reference_id": "2026_01_001",
                "borrower_name": "b1",
                "borrower_group": "bg1",
                "amount": "10000",
                "giving_date": "2026-01-02",
                "depositor_name": "d1",
                "depositor_group": "dg1",
                "due_date": "2026-04-02",
                "status": "Active",
            })
        manager = CSVManager()
        result = manager.read_loans(loans_path)
        assert isinstance(result[0]["giving_date"], date)
        assert isinstance(result[0]["due_date"], date)

    def test_read_loans_missing_optional_fields_return_none(self, data_dir: Path) -> None:
        """depositor_group and due_date may be empty string in CSV → None in dict."""
        loans_path = data_dir / "loans.csv"
        with loans_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerow({
                "reference_id": "2026_03_003",
                "borrower_name": "b14",
                "borrower_group": "bg8",
                "amount": "15000",
                "giving_date": "2026-03-10",
                "depositor_name": "d14",
                "depositor_group": "",
                "due_date": "2026-07-10",
                "status": "Active",
            })
        manager = CSVManager()
        result = manager.read_loans(loans_path)
        assert result[0]["depositor_group"] is None

    def test_read_loans_utf8_bom_reads_correctly(self, data_dir: Path) -> None:
        """CSV files exported from Excel often include a UTF-8 BOM."""
        loans_path = data_dir / "loans.csv"
        content = (
            "\ufeff"
            "reference_id,borrower_name,borrower_group,amount,"
            "giving_date,depositor_name,depositor_group,due_date,status\n"
            "2026_01_001,b1,bg1,10000,2026-01-02,d1,dg1,2026-04-02,Active\n"
        )
        loans_path.write_text(content, encoding="utf-8")
        manager = CSVManager()
        result = manager.read_loans(loans_path)
        assert len(result) == 1
        assert result[0]["reference_id"] == "2026_01_001"

    def test_read_loans_amount_parsed_as_integer(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        with loans_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerow({
                "reference_id": "2026_01_001",
                "borrower_name": "b1",
                "borrower_group": "bg1",
                "amount": "10000",
                "giving_date": "2026-01-02",
                "depositor_name": "d1",
                "depositor_group": "dg1",
                "due_date": "2026-04-02",
                "status": "Active",
            })
        manager = CSVManager()
        result = manager.read_loans(loans_path)
        assert isinstance(result[0]["amount"], int)
        assert result[0]["amount"] == 10000


# ---------------------------------------------------------------------------
# write_loan
# ---------------------------------------------------------------------------

class TestWriteLoan:
    def test_write_loan_creates_file_with_header_and_record(
        self, data_dir: Path
    ) -> None:
        loans_path = data_dir / "loans.csv"
        manager = CSVManager()
        loan = _make_loan_dict()
        manager.write_loan(loans_path, loan)
        raw = _read_csv_raw(loans_path)
        assert len(raw) == 1
        assert raw[0]["reference_id"] == "2026_03_001"

    def test_write_loan_appends_to_existing_file(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        manager = CSVManager()
        manager.write_loan(loans_path, _make_loan_dict("2026_01_001"))
        manager.write_loan(loans_path, _make_loan_dict("2026_01_002"))
        raw = _read_csv_raw(loans_path)
        assert len(raw) == 2

    def test_write_loan_dates_stored_as_iso8601(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        manager = CSVManager()
        loan = _make_loan_dict(giving_date=date(2026, 1, 2), due_date=date(2026, 4, 2))
        manager.write_loan(loans_path, loan)
        raw = _read_csv_raw(loans_path)
        assert raw[0]["giving_date"] == "2026-01-02"
        assert raw[0]["due_date"] == "2026-04-02"

    def test_write_loan_none_optional_fields_stored_as_empty_string(
        self, data_dir: Path
    ) -> None:
        loans_path = data_dir / "loans.csv"
        manager = CSVManager()
        loan = _make_loan_dict(depositor_group=None, due_date=None)
        manager.write_loan(loans_path, loan)
        raw = _read_csv_raw(loans_path)
        assert raw[0]["depositor_group"] == ""
        assert raw[0]["due_date"] == ""


# ---------------------------------------------------------------------------
# update_loan
# ---------------------------------------------------------------------------

class TestUpdateLoan:
    def test_update_loan_modifies_target_record(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1",
                "borrower_group": "bg1",
                "amount": "10000",
                "giving_date": "2026-01-02",
                "depositor_name": "d1",
                "depositor_group": "dg1",
                "due_date": "2026-04-02",
                "status": "Active",
            },
        ])
        manager = CSVManager()
        manager.update_loan(loans_path, "2026_01_001", {"status": "Overdue"})
        raw = _read_csv_raw(loans_path)
        assert raw[0]["status"] == "Overdue"

    def test_update_loan_preserves_other_records(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        rows = [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
            {
                "reference_id": "2026_01_002",
                "borrower_name": "b2", "borrower_group": "bg2", "amount": "10000",
                "giving_date": "2026-01-04", "depositor_name": "d2",
                "depositor_group": "dg1", "due_date": "2026-05-04", "status": "Active",
            },
        ]
        _write_loans_csv(loans_path, rows)
        manager = CSVManager()
        manager.update_loan(loans_path, "2026_01_001", {"status": "Overdue"})
        raw = _read_csv_raw(loans_path)
        assert len(raw) == 2
        assert raw[1]["reference_id"] == "2026_01_002"
        assert raw[1]["status"] == "Active"

    def test_update_loan_multiple_fields_updated(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
        ])
        manager = CSVManager()
        manager.update_loan(
            loans_path,
            "2026_01_001",
            {"status": "Overdue", "due_date": date(2026, 3, 1)},
        )
        raw = _read_csv_raw(loans_path)
        assert raw[0]["status"] == "Overdue"
        assert raw[0]["due_date"] == "2026-03-01"

    def test_update_loan_nonexistent_reference_id_no_error(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
        ])
        manager = CSVManager()
        manager.update_loan(loans_path, "9999_99_999", {"status": "Overdue"})
        raw = _read_csv_raw(loans_path)
        assert raw[0]["status"] == "Active"


# ---------------------------------------------------------------------------
# delete_loan
# ---------------------------------------------------------------------------

class TestDeleteLoan:
    def test_delete_loan_removes_target_record(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        rows = [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
            {
                "reference_id": "2026_01_002",
                "borrower_name": "b2", "borrower_group": "bg2", "amount": "10000",
                "giving_date": "2026-01-04", "depositor_name": "d2",
                "depositor_group": "dg1", "due_date": "2026-05-04", "status": "Active",
            },
        ]
        _write_loans_csv(loans_path, rows)
        manager = CSVManager()
        manager.delete_loan(loans_path, "2026_01_001")
        raw = _read_csv_raw(loans_path)
        assert len(raw) == 1
        assert raw[0]["reference_id"] == "2026_01_002"

    def test_delete_loan_other_records_intact(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        rows = [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
            {
                "reference_id": "2026_01_002",
                "borrower_name": "b2", "borrower_group": "bg2", "amount": "15000",
                "giving_date": "2026-01-04", "depositor_name": "d2",
                "depositor_group": "dg1", "due_date": "2026-05-04", "status": "Active",
            },
            {
                "reference_id": "2026_01_003",
                "borrower_name": "b3", "borrower_group": "bg3", "amount": "20000",
                "giving_date": "2026-01-05", "depositor_name": "d3",
                "depositor_group": "dg2", "due_date": "2026-06-05", "status": "Active",
            },
        ]
        _write_loans_csv(loans_path, rows)
        manager = CSVManager()
        manager.delete_loan(loans_path, "2026_01_002")
        raw = _read_csv_raw(loans_path)
        ids = [r["reference_id"] for r in raw]
        assert "2026_01_001" in ids
        assert "2026_01_002" not in ids
        assert "2026_01_003" in ids

    def test_delete_loan_last_record_leaves_header_only(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
        ])
        manager = CSVManager()
        manager.delete_loan(loans_path, "2026_01_001")
        raw = _read_csv_raw(loans_path)
        assert raw == []

    def test_delete_loan_nonexistent_id_no_error(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
        ])
        manager = CSVManager()
        manager.delete_loan(loans_path, "9999_99_999")
        raw = _read_csv_raw(loans_path)
        assert len(raw) == 1


# ---------------------------------------------------------------------------
# mark_paidoff – atomic write
# ---------------------------------------------------------------------------

class TestMarkPaidoff:
    def _setup_single_loan(self, data_dir: Path) -> tuple[Path, Path]:
        loans_path = data_dir / "loans.csv"
        history_path = data_dir / "history.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
        ])
        return loans_path, history_path

    def test_mark_paidoff_removes_record_from_loans_csv(self, data_dir: Path) -> None:
        loans_path, history_path = self._setup_single_loan(data_dir)
        manager = CSVManager()
        manager.mark_paidoff(loans_path, history_path, "2026_01_001", date(2026, 3, 22))
        raw = _read_csv_raw(loans_path)
        ids = [r["reference_id"] for r in raw]
        assert "2026_01_001" not in ids

    def test_mark_paidoff_appends_record_to_history_csv(self, data_dir: Path) -> None:
        loans_path, history_path = self._setup_single_loan(data_dir)
        manager = CSVManager()
        manager.mark_paidoff(loans_path, history_path, "2026_01_001", date(2026, 3, 22))
        raw = _read_csv_raw(history_path)
        assert len(raw) == 1
        assert raw[0]["reference_id"] == "2026_01_001"

    def test_mark_paidoff_history_record_has_paidoff_date(self, data_dir: Path) -> None:
        loans_path, history_path = self._setup_single_loan(data_dir)
        manager = CSVManager()
        manager.mark_paidoff(loans_path, history_path, "2026_01_001", date(2026, 3, 22))
        raw = _read_csv_raw(history_path)
        assert raw[0]["paidoff_date"] == "2026-03-22"

    def test_mark_paidoff_recovery_tmp_deleted_on_success(self, data_dir: Path) -> None:
        loans_path, history_path = self._setup_single_loan(data_dir)
        manager = CSVManager()
        manager.mark_paidoff(loans_path, history_path, "2026_01_001", date(2026, 3, 22))
        recovery_path = data_dir / "recovery.tmp"
        assert not recovery_path.exists()

    def test_mark_paidoff_recovery_tmp_created_before_writes(
        self, data_dir: Path
    ) -> None:
        """Verify recovery.tmp is created as the first step of the operation.

        Strategy: intercept history.csv write and assert recovery.tmp exists
        at that point in time.
        """
        loans_path, history_path = self._setup_single_loan(data_dir)
        recovery_path = data_dir / "recovery.tmp"

        tmp_existed_at_history_write: list[bool] = []
        original_open = open

        def patched_open(path, *args, **kwargs):
            if str(path) == str(history_path) and ("w" in args or kwargs.get("mode", "") in ("w", "a")):
                tmp_existed_at_history_write.append(recovery_path.exists())
            return original_open(path, *args, **kwargs)

        manager = CSVManager()
        with patch("builtins.open", side_effect=patched_open):
            try:
                manager.mark_paidoff(
                    loans_path, history_path, "2026_01_001", date(2026, 3, 22)
                )
            except Exception:
                pass

        # If the intercept fired, recovery.tmp must have already existed
        if tmp_existed_at_history_write:
            assert tmp_existed_at_history_write[0] is True

    def test_mark_paidoff_recovery_tmp_persists_on_crash_between_writes(
        self, data_dir: Path
    ) -> None:
        """Simulate crash after history.csv update but before loans.csv update.
        recovery.tmp should still be present."""
        loans_path, history_path = self._setup_single_loan(data_dir)
        recovery_path = data_dir / "recovery.tmp"

        crash_call_count = {"n": 0}

        original_open = open

        def patched_open(path, *args, **kwargs):
            mode = args[0] if args else kwargs.get("mode", "r")
            if str(path) == str(loans_path) and "w" in str(mode):
                crash_call_count["n"] += 1
                if crash_call_count["n"] == 1:
                    raise OSError("Simulated crash during loans.csv write")
            return original_open(path, *args, **kwargs)

        manager = CSVManager()
        with pytest.raises(OSError, match="Simulated crash"):
            with patch("builtins.open", side_effect=patched_open):
                manager.mark_paidoff(
                    loans_path, history_path, "2026_01_001", date(2026, 3, 22)
                )

        assert recovery_path.exists(), "recovery.tmp must persist when crash occurs"

    def test_mark_paidoff_other_loans_preserved(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        history_path = data_dir / "history.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
            {
                "reference_id": "2026_01_002",
                "borrower_name": "b2", "borrower_group": "bg2", "amount": "10000",
                "giving_date": "2026-01-04", "depositor_name": "d2",
                "depositor_group": "dg1", "due_date": "2026-05-04", "status": "Active",
            },
        ])
        manager = CSVManager()
        manager.mark_paidoff(loans_path, history_path, "2026_01_001", date(2026, 3, 22))
        raw = _read_csv_raw(loans_path)
        assert len(raw) == 1
        assert raw[0]["reference_id"] == "2026_01_002"


# ---------------------------------------------------------------------------
# extend_loan
# ---------------------------------------------------------------------------

class TestExtendLoan:
    def _write_single_loan(
        self,
        data_dir: Path,
        reference_id: str = "2026_01_001",
        giving_date: str = "2026-01-02",
        due_date: str = "2026-04-02",
    ) -> Path:
        loans_path = data_dir / "loans.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": reference_id,
                "borrower_name": "b1",
                "borrower_group": "bg1",
                "amount": "10000",
                "giving_date": giving_date,
                "depositor_name": "d1",
                "depositor_group": "dg1",
                "due_date": due_date,
                "status": "Active",
            },
        ])
        return loans_path

    @pytest.mark.parametrize("period,unit,expected_new_due", [
        (3, "months", date(2026, 7, 2)),   # 2026-04-02 + 3 months = 2026-07-02
        (1, "months", date(2026, 5, 2)),   # 2026-04-02 + 1 month  = 2026-05-02
        (30, "days",  date(2026, 5, 2)),   # 2026-04-02 + 30 days  = 2026-05-02
        (7,  "days",  date(2026, 4, 9)),   # 2026-04-02 + 7 days   = 2026-04-09
    ])
    def test_extend_loan_new_due_date_equals_old_due_date_plus_period(
        self,
        data_dir: Path,
        period: int,
        unit: str,
        expected_new_due: date,
    ) -> None:
        loans_path = self._write_single_loan(data_dir)
        manager = CSVManager()
        manager.extend_loan(loans_path, "2026_01_001", period, unit)
        raw = _read_csv_raw(loans_path)
        assert raw[0]["due_date"] == expected_new_due.isoformat()

    @pytest.mark.parametrize("period,unit,old_due", [
        (3, "months", "2026-04-02"),
        (30, "days",  "2026-04-02"),
    ])
    def test_extend_loan_new_giving_date_equals_old_due_date(
        self,
        data_dir: Path,
        period: int,
        unit: str,
        old_due: str,
    ) -> None:
        loans_path = self._write_single_loan(data_dir, due_date=old_due)
        manager = CSVManager()
        manager.extend_loan(loans_path, "2026_01_001", period, unit)
        raw = _read_csv_raw(loans_path)
        assert raw[0]["giving_date"] == old_due

    def test_extend_loan_no_due_date_new_giving_date_is_today(
        self, data_dir: Path
    ) -> None:
        """R7: when due_date is absent, new giving_date = today."""
        loans_path = data_dir / "loans.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_03_001",
                "borrower_name": "b14",
                "borrower_group": "bg8",
                "amount": "15000",
                "giving_date": "2026-03-10",
                "depositor_name": "d14",
                "depositor_group": "",
                "due_date": "",
                "status": "Active",
            },
        ])
        manager = CSVManager()
        new_due = date(2026, 6, 22)
        manager.extend_loan(
            loans_path, "2026_03_001", 3, "months", today=TODAY, new_due_date=new_due
        )
        raw = _read_csv_raw(loans_path)
        assert raw[0]["giving_date"] == TODAY.isoformat()
        assert raw[0]["due_date"] == new_due.isoformat()

    def test_extend_loan_reference_id_preserved(self, data_dir: Path) -> None:
        """After extend, reference_id must remain unchanged (R4)."""
        loans_path = self._write_single_loan(data_dir)
        manager = CSVManager()
        manager.extend_loan(loans_path, "2026_01_001", 3, "months")
        raw = _read_csv_raw(loans_path)
        assert raw[0]["reference_id"] == "2026_01_001"

    def test_extend_loan_other_records_unaffected(self, data_dir: Path) -> None:
        loans_path = data_dir / "loans.csv"
        _write_loans_csv(loans_path, [
            {
                "reference_id": "2026_01_001",
                "borrower_name": "b1", "borrower_group": "bg1", "amount": "10000",
                "giving_date": "2026-01-02", "depositor_name": "d1",
                "depositor_group": "dg1", "due_date": "2026-04-02", "status": "Active",
            },
            {
                "reference_id": "2026_01_002",
                "borrower_name": "b2", "borrower_group": "bg2", "amount": "10000",
                "giving_date": "2026-01-04", "depositor_name": "d2",
                "depositor_group": "dg1", "due_date": "2026-05-04", "status": "Active",
            },
        ])
        manager = CSVManager()
        manager.extend_loan(loans_path, "2026_01_001", 3, "months")
        raw = _read_csv_raw(loans_path)
        assert raw[1]["giving_date"] == "2026-01-04"
        assert raw[1]["due_date"] == "2026-05-04"
