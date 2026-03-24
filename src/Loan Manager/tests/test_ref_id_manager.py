"""
Tests for RefIdManager.

Public API under test:
    next_ref_id(year: int, month: int, meta_path: Path) -> str

Reference ID format: YYYY_MM_<order>
  - order is zero-padded to 3 digits for values 001-999
  - order is NOT zero-padded beyond 3 digits (i.e. 1000 stays 1000)

Counter rules (R4):
  - Increments per YYYY_MM bucket independently
  - If all records for a YYYY_MM are deleted, counter resets to 001 for next entry
  - If loans_meta.csv missing or corrupted, recover gracefully
"""

import csv
import pytest
from pathlib import Path

from loan_manager.ref_id_manager import RefIdManager  # type: ignore[import]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_meta(meta_path: Path, rows: list[dict]) -> None:
    """Write a loans_meta.csv with given rows."""
    fieldnames = ["year_month", "counter"]
    with meta_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Basic counter generation
# ---------------------------------------------------------------------------

class TestNextRefIdFirstEntry:
    def test_next_ref_id_first_loan_in_month_generates_001(self, data_dir: Path) -> None:
        meta_path = data_dir / "loans_meta.csv"
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_001"

    def test_next_ref_id_meta_csv_created_when_missing(self, data_dir: Path) -> None:
        meta_path = data_dir / "loans_meta.csv"
        assert not meta_path.exists()
        manager = RefIdManager(meta_path=meta_path)
        manager.next_ref_id(2026, 3)
        assert meta_path.exists()

    def test_next_ref_id_first_entry_january(self, data_dir: Path) -> None:
        meta_path = data_dir / "loans_meta.csv"
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 1)
        assert result == "2026_01_001"

    def test_next_ref_id_first_entry_december(self, data_dir: Path) -> None:
        meta_path = data_dir / "loans_meta.csv"
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 12)
        assert result == "2026_12_001"


class TestNextRefIdSequentialIncrement:
    def test_next_ref_id_second_loan_same_month_generates_002(self, data_dir: Path) -> None:
        meta_path = data_dir / "loans_meta.csv"
        _write_meta(meta_path, [{"year_month": "2026_03", "counter": "1"}])
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_002"

    def test_next_ref_id_tenth_loan_generates_010(self, data_dir: Path) -> None:
        meta_path = data_dir / "loans_meta.csv"
        _write_meta(meta_path, [{"year_month": "2026_03", "counter": "9"}])
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_010"

    def test_next_ref_id_999th_loan_generates_999(self, data_dir: Path) -> None:
        meta_path = data_dir / "loans_meta.csv"
        _write_meta(meta_path, [{"year_month": "2026_03", "counter": "998"}])
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_999"

    def test_next_ref_id_counter_increments_to_1000_no_rollover(self, data_dir: Path) -> None:
        """After 999, the 1000th entry must be 1000, not roll over to 001."""
        meta_path = data_dir / "loans_meta.csv"
        _write_meta(meta_path, [{"year_month": "2026_03", "counter": "999"}])
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_1000"

    def test_next_ref_id_counter_persists_after_call(self, data_dir: Path) -> None:
        """Counter written to meta CSV must reflect the new value."""
        meta_path = data_dir / "loans_meta.csv"
        manager = RefIdManager(meta_path=meta_path)
        manager.next_ref_id(2026, 3)
        manager2 = RefIdManager(meta_path=meta_path)
        second = manager2.next_ref_id(2026, 3)
        assert second == "2026_03_002"

    @pytest.mark.parametrize("call_count,expected_order", [
        (1, "001"),
        (2, "002"),
        (3, "003"),
        (5, "005"),
    ])
    def test_next_ref_id_sequential_calls_increment_correctly(
        self,
        data_dir: Path,
        call_count: int,
        expected_order: str,
    ) -> None:
        meta_path = data_dir / "loans_meta.csv"
        manager = RefIdManager(meta_path=meta_path)
        result = None
        for _ in range(call_count):
            result = manager.next_ref_id(2026, 3)
        assert result == f"2026_03_{expected_order}"


class TestNextRefIdNewMonth:
    def test_next_ref_id_new_month_resets_to_001(self, data_dir: Path) -> None:
        meta_path = data_dir / "loans_meta.csv"
        _write_meta(meta_path, [{"year_month": "2026_02", "counter": "5"}])
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_001"

    def test_next_ref_id_concurrent_months_independent(self, data_dir: Path) -> None:
        """Counters for 2026_01 and 2026_03 must be independent."""
        meta_path = data_dir / "loans_meta.csv"
        manager = RefIdManager(meta_path=meta_path)
        jan = manager.next_ref_id(2026, 1)
        mar = manager.next_ref_id(2026, 3)
        assert jan == "2026_01_001"
        assert mar == "2026_03_001"

    def test_next_ref_id_existing_month_unaffected_by_new_month(self, data_dir: Path) -> None:
        """Adding a new month entry must not reset existing month counters."""
        meta_path = data_dir / "loans_meta.csv"
        manager = RefIdManager(meta_path=meta_path)
        manager.next_ref_id(2026, 1)
        manager.next_ref_id(2026, 3)
        jan_second = manager.next_ref_id(2026, 1)
        assert jan_second == "2026_01_002"


# ---------------------------------------------------------------------------
# Delete reset
# ---------------------------------------------------------------------------

class TestNextRefIdDeleteReset:
    def test_next_ref_id_all_records_deleted_resets_counter_to_001(
        self,
        data_dir: Path,
    ) -> None:
        """If all records for a month are deleted, next entry gets 001 (R4)."""
        meta_path = data_dir / "loans_meta.csv"
        _write_meta(meta_path, [{"year_month": "2026_03", "counter": "5"}])
        manager = RefIdManager(meta_path=meta_path)
        manager.reset_counter(2026, 3)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_001"

    def test_next_ref_id_reset_one_month_does_not_affect_other(
        self,
        data_dir: Path,
    ) -> None:
        """Resetting 2026_03 must not touch 2026_01 counter."""
        meta_path = data_dir / "loans_meta.csv"
        _write_meta(meta_path, [
            {"year_month": "2026_01", "counter": "3"},
            {"year_month": "2026_03", "counter": "5"},
        ])
        manager = RefIdManager(meta_path=meta_path)
        manager.reset_counter(2026, 3)
        jan_next = manager.next_ref_id(2026, 1)
        assert jan_next == "2026_01_004"


# ---------------------------------------------------------------------------
# Recovery from corrupted / missing meta
# ---------------------------------------------------------------------------

class TestRefIdManagerRecovery:
    def test_next_ref_id_missing_meta_csv_recovers_gracefully(
        self,
        data_dir: Path,
    ) -> None:
        meta_path = data_dir / "loans_meta.csv"
        assert not meta_path.exists()
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_001"

    def test_next_ref_id_corrupted_meta_csv_recovers_gracefully(
        self,
        data_dir: Path,
    ) -> None:
        meta_path = data_dir / "loans_meta.csv"
        meta_path.write_text("NOT_VALID_CSV\x00\x01\x02", encoding="utf-8")
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_001"

    def test_next_ref_id_empty_meta_csv_recovers_gracefully(
        self,
        data_dir: Path,
    ) -> None:
        meta_path = data_dir / "loans_meta.csv"
        meta_path.write_text("", encoding="utf-8")
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_001"

    def test_next_ref_id_header_only_meta_csv_recovers_gracefully(
        self,
        data_dir: Path,
    ) -> None:
        meta_path = data_dir / "loans_meta.csv"
        meta_path.write_text("year_month,counter\n", encoding="utf-8")
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_001"

    def test_next_ref_id_partial_row_in_meta_csv_recovers(
        self,
        data_dir: Path,
    ) -> None:
        """A row with missing counter field should not crash; treat as 0."""
        meta_path = data_dir / "loans_meta.csv"
        meta_path.write_text("year_month,counter\n2026_03,\n", encoding="utf-8")
        manager = RefIdManager(meta_path=meta_path)
        result = manager.next_ref_id(2026, 3)
        assert result == "2026_03_001"
