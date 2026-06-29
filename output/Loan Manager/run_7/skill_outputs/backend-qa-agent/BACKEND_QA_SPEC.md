# Loan Manager — Backend QA Spec
**Agent:** backend-qa-agent (Wave 2)
**Run:** run_7
**Date:** 2026-04-05
**Phase:** Phase 3 Closure / Phase 4 MVP

---

## QA State — Run 7

**Test baseline:** 237 tests passing (pytest confirmed at run start).

---

## New Test Files — Phase 4

### TEST-1: tests/test_view_tab_colors.py (CREATE IMMEDIATELY)

No blockers. No QApplication needed. Pure import of module-level dict.

```python
"""Tests for STATUS_COLORS in ui.view_tab — pure import test, no QApplication needed.

PD-11 (run_6) confirmed: STATUS_COLORS is a module-level dict.
Importing from ui.view_tab does not instantiate QApplication.
"""
import sys
from pathlib import Path

# Ensure src/Loan Manager is on sys.path
_SRC = Path(__file__).parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from ui.view_tab import STATUS_COLORS


class TestStatusColors:
    def test_active_background(self):
        bg, fg = STATUS_COLORS["Active"]
        assert bg == "#025c33"

    def test_overdue_background(self):
        bg, fg = STATUS_COLORS["Overdue"]
        assert bg == "#6b0307"

    def test_pending_background(self):
        bg, fg = STATUS_COLORS["Pending"]
        assert bg == "#804001"

    def test_paidoff_background(self):
        bg, fg = STATUS_COLORS["Paidoff"]
        assert bg == "#022a52"

    def test_all_foregrounds_white(self):
        for status, (bg, fg) in STATUS_COLORS.items():
            assert fg == "#ffffff", f"Expected white fg for {status}, got {fg}"

    def test_all_statuses_present(self):
        assert set(STATUS_COLORS.keys()) == {"Active", "Overdue", "Pending", "Paidoff"}
```

---

### TEST-2: tests/test_entry_tab_logic.py (CREATE IMMEDIATELY)

No blockers. Tests pure date calculation isolated from QApplication.

```python
"""Tests for Entry Tab due_period calculation logic (R1).

Isolated from QApplication. Replicates _on_due_period_changed calculation.
"""
from datetime import date
from dateutil.relativedelta import relativedelta


def _calc_due_date(giving_date: date, due_period_months: int) -> date:
    """Replicate ui/entry_tab.py _on_due_period_changed calculation."""
    return giving_date + relativedelta(months=due_period_months)


class TestDuePeriodCalc:
    def test_3_months_standard(self):
        assert _calc_due_date(date(2026, 1, 2), 3) == date(2026, 4, 2)

    def test_1_month_month_end_february(self):
        # March 31 + 1 month = April 30 (relativedelta handles month-end)
        assert _calc_due_date(date(2026, 3, 31), 1) == date(2026, 4, 30)

    def test_12_months_same_day(self):
        assert _calc_due_date(date(2026, 1, 1), 12) == date(2027, 1, 1)

    def test_cross_year(self):
        assert _calc_due_date(date(2026, 11, 15), 3) == date(2027, 2, 15)

    def test_0_months_returns_giving_date(self):
        giving = date(2026, 1, 2)
        assert _calc_due_date(giving, 0) == giving

    def test_sample_data_b1(self):
        """R7 sample data: b1 giving=2026-01-02, due=2026-04-02 (3 months)"""
        assert _calc_due_date(date(2026, 1, 2), 3) == date(2026, 4, 2)

    def test_sample_data_b2(self):
        """R7 sample data: b2 giving=2026-01-04, due=2026-05-04 (4 months)"""
        assert _calc_due_date(date(2026, 1, 4), 4) == date(2026, 5, 4)
```

---

### TEST-3: tests/test_view_tab_paidoff.py (CREATE AFTER TASK-1)

Tests `has_pending_paidoff_report()` using injectable paths. No QApplication.

```python
"""Tests for has_pending_paidoff_report() — R3 TC-05 PD-10.

Uses CSVReportManager with tmp paths for isolation.
"""
import pytest
from datetime import date, datetime
from pathlib import Path

from loan_manager.report_manager import CSVReportManager
from models.report import PendingReport, ReportRecord


@pytest.fixture
def tmp_reports(tmp_path):
    return tmp_path / "pending_reports.csv"


@pytest.fixture
def tmp_records(tmp_path):
    return tmp_path / "pending_report_records.csv"


@pytest.fixture
def manager():
    return CSVReportManager()


def _make_paidoff_report(report_id: str) -> PendingReport:
    return PendingReport(
        report_id=report_id,
        report_creation_date=date(2026, 4, 5),
        report_latest_update_dt=datetime(2026, 4, 5, 10, 0, 0),
        mode="Paidoff",
        status="Pending",
    )


def _make_regular_report(report_id: str) -> PendingReport:
    return PendingReport(
        report_id=report_id,
        report_creation_date=date(2026, 4, 5),
        report_latest_update_dt=datetime(2026, 4, 5, 10, 0, 0),
        mode="Monthly",
        status="Pending",
    )


def _make_record(report_id: str, ref_id: str) -> ReportRecord:
    return ReportRecord(
        report_id=report_id,
        reference_id=ref_id,
        borrower_name="b1",
        amount=10000,
        depositor_name=None,
        giving_date=date(2026, 1, 2),
        due_date=date(2026, 4, 2),
        interest_rate=12.0,
        commission_rate=2.0,
        extension_period=30,
        extension_period_unit="days",
        tds_flag=False,
        new_giving_date=None,
        new_due_date=date(2026, 4, 2),
        interest_amount=9.86,
        commission_amount=1.64,
        tds_amount=0.0,
    )


class TestHasPendingPaidoffReport:
    def test_returns_false_when_no_reports(
        self, manager, tmp_reports, tmp_records
    ):
        result = manager.has_pending_paidoff_report(
            tmp_reports, tmp_records, "2026_01_001"
        )
        assert result is False

    def test_returns_false_when_only_monthly_reports(
        self, manager, tmp_reports, tmp_records
    ):
        rpt = _make_regular_report("RPT_20260405_001")
        meta = tmp_reports.parent / "reports_meta.csv"
        manager.write_report(tmp_reports, meta, rpt)
        rec = _make_record("RPT_20260405_001", "2026_01_001")
        manager.write_report_records(tmp_records, [rec])

        result = manager.has_pending_paidoff_report(
            tmp_reports, tmp_records, "2026_01_001"
        )
        assert result is False

    def test_returns_true_when_pending_paidoff_report_exists(
        self, manager, tmp_reports, tmp_records
    ):
        rpt = _make_paidoff_report("RPT_20260405_001")
        meta = tmp_reports.parent / "reports_meta.csv"
        manager.write_report(tmp_reports, meta, rpt)
        rec = _make_record("RPT_20260405_001", "2026_01_001")
        manager.write_report_records(tmp_records, [rec])

        result = manager.has_pending_paidoff_report(
            tmp_reports, tmp_records, "2026_01_001"
        )
        assert result is True

    def test_returns_false_for_different_loan(
        self, manager, tmp_reports, tmp_records
    ):
        rpt = _make_paidoff_report("RPT_20260405_001")
        meta = tmp_reports.parent / "reports_meta.csv"
        manager.write_report(tmp_reports, meta, rpt)
        rec = _make_record("RPT_20260405_001", "2026_01_001")
        manager.write_report_records(tmp_records, [rec])

        result = manager.has_pending_paidoff_report(
            tmp_reports, tmp_records, "2026_01_002"  # different loan
        )
        assert result is False

    def test_returns_false_when_paidoff_report_approved(
        self, manager, tmp_reports, tmp_records
    ):
        rpt = _make_paidoff_report("RPT_20260405_001")
        meta = tmp_reports.parent / "reports_meta.csv"
        manager.write_report(tmp_reports, meta, rpt)
        rec = _make_record("RPT_20260405_001", "2026_01_001")
        manager.write_report_records(tmp_records, [rec])
        # Approve the report
        manager.update_report_status(
            tmp_reports, "RPT_20260405_001", "Approved", datetime(2026, 4, 5, 11, 0, 0)
        )

        result = manager.has_pending_paidoff_report(
            tmp_reports, tmp_records, "2026_01_001"
        )
        assert result is False  # Approved reports not in pending queue
```

---

### TEST-4: tests/test_pending_approval.py — batch_extend portion (CREATE IMMEDIATELY)

```python
"""Tests for batch_extend_loans() — R5 batch approval single-pass rewrite."""
import pytest
from datetime import date
from pathlib import Path

from loan_manager.csv_manager import CSVManager
from models.loan import CSV_FIELDNAMES, Loan


@pytest.fixture
def sample_loans():
    return [
        Loan(
            reference_id="2026_01_001",
            borrower_name="b1",
            borrower_group="bg1",
            amount=10000,
            giving_date=date(2026, 1, 2),
            due_date=date(2026, 4, 2),
            status="Active",
        ),
        Loan(
            reference_id="2026_01_002",
            borrower_name="b2",
            borrower_group="bg2",
            amount=15000,
            giving_date=date(2026, 1, 4),
            due_date=date(2026, 5, 4),
            status="Active",
        ),
    ]


@pytest.fixture
def loans_csv(tmp_path, sample_loans):
    import csv
    path = tmp_path / "loans.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows([l.to_csv_row() for l in sample_loans])
    return path


class TestBatchExtendLoans:
    def test_extends_two_loans(self, loans_csv):
        manager = CSVManager()
        extensions = [
            {
                "reference_id": "2026_01_001",
                "new_giving_date": date(2026, 4, 2),
                "new_due_date": date(2026, 7, 2),
            },
            {
                "reference_id": "2026_01_002",
                "new_giving_date": date(2026, 5, 4),
                "new_due_date": date(2026, 8, 4),
            },
        ]
        manager.batch_extend_loans(loans_csv, extensions)

        import csv
        with loans_csv.open("r", newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        row1 = next(r for r in rows if r["reference_id"] == "2026_01_001")
        assert row1["giving_date"] == "2026-04-02"
        assert row1["due_date"] == "2026-07-02"

        row2 = next(r for r in rows if r["reference_id"] == "2026_01_002")
        assert row2["giving_date"] == "2026-05-04"
        assert row2["due_date"] == "2026-08-04"

    def test_skips_missing_reference_id(self, loans_csv):
        manager = CSVManager()
        extensions = [
            {
                "reference_id": "2026_99_999",  # does not exist
                "new_giving_date": date(2026, 4, 2),
                "new_due_date": date(2026, 7, 2),
            },
        ]
        # Should not raise — unknown IDs are silently skipped
        manager.batch_extend_loans(loans_csv, extensions)

        import csv
        with loans_csv.open("r", newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        # Original data unchanged
        assert len(rows) == 2
        assert rows[0]["giving_date"] == "2026-01-02"
```

---

## QA Regression Checklist — Run 7

Verified by re-running pytest at run start:

| Test Suite | Count | Status |
|---|---|---|
| test_calculation_dialog_logic.py | ~30 | PASS |
| test_csv_manager.py | ~25 | PASS |
| test_filter_logic.py | ~20 | PASS |
| test_interest_calculator.py | ~25 | PASS |
| test_ref_id_manager.py | ~30 | PASS |
| test_report_manager.py | ~40 | PASS |
| test_seed.py | ~15 | PASS |
| test_status_engine.py | ~52 | PASS |
| **TOTAL** | **237** | **PASS** |

---

## QA Sign-Off Conditions

Phase 4 QA will sign off when:
1. TC-05 implemented and test_view_tab_paidoff.py (5 tests) passing
2. test_view_tab_colors.py (6 tests) passing
3. test_entry_tab_logic.py (7 tests) passing
4. test_pending_approval.py batch_extend (2 tests) passing
5. TC-08 Option B tests (if chosen): 3 tests passing
6. BC-02 Option B tests (if chosen): 2 tests passing
7. Full pytest suite: 0 failures
8. Manual smoke tests confirmed by Mac tester
