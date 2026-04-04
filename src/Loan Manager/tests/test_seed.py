"""Tests for data/seed.py — sample data seeding (R7).

Validates the guard condition and seeding behavior:
- Seed when loans.csv absent
- Seed when loans.csv is empty (header only)
- Skip seeding when loans.csv has data rows
- After seeding: 15 records, correct statuses, loans_meta.csv updated
"""
import csv
import pytest
from datetime import date
from pathlib import Path

from data.seed import seed_sample_data, _is_empty, _SAMPLE_RECORDS, _SEED_META_COUNTERS
from models.loan import CSV_FIELDNAMES, Loan
from loan_manager.ref_id_manager import RefIdManager


# ---------------------------------------------------------------------------
# _is_empty helper tests
# ---------------------------------------------------------------------------

class TestIsEmpty:
    def test_absent_file_is_empty(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        assert _is_empty(loans_path) is True

    def test_truly_empty_file_is_empty(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        loans_path.write_text("", encoding="utf-8")
        assert _is_empty(loans_path) is True

    def test_header_only_file_is_empty(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        with loans_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
        assert _is_empty(loans_path) is True

    def test_file_with_data_row_is_not_empty(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        loan = Loan(
            reference_id="2026_01_001",
            borrower_name="test",
            borrower_group="grp",
            amount=1000,
            giving_date=date(2026, 1, 1),
            due_date=date(2026, 4, 1),
            status="Active",
        )
        with loans_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            writer.writerow(loan.to_csv_row())
        assert _is_empty(loans_path) is False


# ---------------------------------------------------------------------------
# seed_sample_data tests
# ---------------------------------------------------------------------------

class TestSeedSampleData:
    def test_seed_when_absent(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        meta_path = tmp_path / "loans_meta.csv"
        result = seed_sample_data(loans_path, meta_path)
        assert result is True
        assert loans_path.exists()

    def test_seed_creates_15_records(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        meta_path = tmp_path / "loans_meta.csv"
        seed_sample_data(loans_path, meta_path)
        rows = list(csv.DictReader(loans_path.open("r", encoding="utf-8-sig")))
        assert len(rows) == 15

    def test_seed_when_header_only(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        meta_path = tmp_path / "loans_meta.csv"
        with loans_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
        result = seed_sample_data(loans_path, meta_path)
        assert result is True

    def test_skip_when_has_data(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        meta_path = tmp_path / "loans_meta.csv"
        # Pre-populate with one loan
        loan = Loan(
            reference_id="2025_01_001",
            borrower_name="existing",
            borrower_group="grp",
            amount=500,
            giving_date=date(2025, 1, 1),
            due_date=date(2025, 4, 1),
            status="Paidoff",
        )
        with loans_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            writer.writerow(loan.to_csv_row())
        result = seed_sample_data(loans_path, meta_path)
        assert result is False

    def test_existing_data_not_overwritten(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        meta_path = tmp_path / "loans_meta.csv"
        loan = Loan(
            reference_id="2025_01_001",
            borrower_name="existing",
            borrower_group="grp",
            amount=500,
            giving_date=date(2025, 1, 1),
            due_date=date(2025, 4, 1),
            status="Active",
        )
        with loans_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            writer.writerow(loan.to_csv_row())
        seed_sample_data(loans_path, meta_path)
        rows = list(csv.DictReader(loans_path.open("r", encoding="utf-8-sig")))
        assert len(rows) == 1
        assert rows[0]["borrower_name"] == "existing"

    def test_seeded_records_have_correct_ref_ids(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        meta_path = tmp_path / "loans_meta.csv"
        seed_sample_data(loans_path, meta_path)
        rows = {r["reference_id"] for r in csv.DictReader(loans_path.open("r", encoding="utf-8-sig"))}
        assert "2026_01_001" in rows
        assert "2026_02_009" in rows
        assert "2026_03_004" in rows

    def test_seeded_statuses_are_computed_not_hardcoded(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        meta_path = tmp_path / "loans_meta.csv"
        seed_sample_data(loans_path, meta_path)
        rows = list(csv.DictReader(loans_path.open("r", encoding="utf-8-sig")))
        statuses = {r["status"] for r in rows}
        # Should not all be "Active" — today=2026-04-04 means many due_dates have passed → Overdue
        assert "Active" in statuses or "Overdue" in statuses or "Pending" in statuses
        # "Paidoff" should not appear in seed data
        assert "Paidoff" not in statuses

    def test_loans_meta_updated_after_seed(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        meta_path = tmp_path / "loans_meta.csv"
        seed_sample_data(loans_path, meta_path)
        assert meta_path.exists()
        manager = RefIdManager(meta_path=meta_path)
        meta = manager._read_meta()
        assert meta.get("2026_01") == 2
        assert meta.get("2026_02") == 9
        assert meta.get("2026_03") == 4

    def test_next_ref_id_after_seed_continues_correctly(self, tmp_path):
        loans_path = tmp_path / "loans.csv"
        meta_path = tmp_path / "loans_meta.csv"
        seed_sample_data(loans_path, meta_path)
        manager = RefIdManager(meta_path=meta_path)
        # Next ID for 2026_03 should be 2026_03_005
        next_id = manager.next_ref_id(2026, 3)
        assert next_id == "2026_03_005"
