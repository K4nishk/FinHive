# Backend QA: Test Plan — Loan Manager run_3
**Date:** 2026-04-03
**Run:** run_3 / Wave 2
**Author:** Backend QA Agent
**Scope:** Test implementation for CHG-02-EXT and BUG-02-REF

---

## 1. Test Infrastructure

### Existing Test Setup
- pytest.ini exists in `/src/Loan Manager/`
- Tests directory: `/src/Loan Manager/tests/`
- Framework: pytest + PySide6
- Pattern: Direct unit tests for pure functions; integration tests with CSV fixtures

### New Test Files Required

| File | Purpose |
|---|---|
| `tests/test_paidoff_dialog_r3.py` | PaidoffDialog new fields (CHG-02-EXT) |
| `tests/test_generate_paidoff_report.py` | _generate_paidoff_report() logic (CHG-02-EXT) |
| `tests/test_view_tab_colors_r3.py` | STATUS_COLORS constants (BUG-02-REF) |

---

## 2. Test Implementation Specs

### File: tests/test_paidoff_dialog_r3.py

```python
"""Tests for PaidoffDialog run_3 additions (CHG-02-EXT).

Tests T-R3-01 to T-R3-04.
Requires a QApplication instance — uses conftest.py fixture.
"""
import pytest
from datetime import date
from PySide6.QtWidgets import QApplication

from ui.dialogs.paidoff_dialog import PaidoffDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestPaidoffDialogDefaults:
    """T-R3-01: Dialog opens with correct default field values."""

    def test_interest_rate_default(self, qapp):
        dialog = PaidoffDialog("2026_03_001")
        assert dialog.interest_rate() == 0.0

    def test_commission_rate_default(self, qapp):
        dialog = PaidoffDialog("2026_03_001")
        assert dialog.commission_rate() == 0.0

    def test_tds_flag_default(self, qapp):
        dialog = PaidoffDialog("2026_03_001")
        assert dialog.tds_flag() is False

    def test_paidoff_date_default_is_today(self, qapp):
        dialog = PaidoffDialog("2026_03_001")
        assert dialog.paidoff_date() == date.today()


class TestPaidoffDialogAccessors:
    """T-R3-02: Accessors return programmatically set values."""

    def test_interest_rate_accessor(self, qapp):
        dialog = PaidoffDialog("2026_03_001")
        dialog._interest_rate_spin.setValue(12.5)
        assert dialog.interest_rate() == 12.5

    def test_commission_rate_accessor(self, qapp):
        dialog = PaidoffDialog("2026_03_001")
        dialog._commission_rate_spin.setValue(2.0)
        assert dialog.commission_rate() == 2.0

    def test_tds_flag_accessor_checked(self, qapp):
        dialog = PaidoffDialog("2026_03_001")
        dialog._tds_flag_cb.setChecked(True)
        assert dialog.tds_flag() is True

    def test_tds_flag_accessor_unchecked(self, qapp):
        dialog = PaidoffDialog("2026_03_001")
        dialog._tds_flag_cb.setChecked(False)
        assert dialog.tds_flag() is False

    def test_interest_rate_range_max(self, qapp):
        dialog = PaidoffDialog("2026_03_001")
        dialog._interest_rate_spin.setValue(100.0)
        assert dialog.interest_rate() == 100.0

    def test_commission_rate_range_zero(self, qapp):
        dialog = PaidoffDialog("2026_03_001")
        dialog._commission_rate_spin.setValue(0.0)
        assert dialog.commission_rate() == 0.0
```

---

### File: tests/test_generate_paidoff_report.py

```python
"""Tests for ViewTab._generate_paidoff_report() (CHG-02-EXT).

Tests T-R3-05 to T-R3-17.
Uses monkeypatching to avoid real CSV writes.
"""
import logging
import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch, call

from models.loan import Loan


def make_loan(due_date=date(2026, 3, 1), reference_id="2026_03_001"):
    return Loan(
        reference_id=reference_id,
        borrower_name="TestBorrower",
        borrower_group="BG1",
        amount=10000,
        giving_date=date(2026, 1, 1),
        depositor_name="TestDepositor",
        due_date=due_date,
        status="Active",
    )


def make_view_tab_with_method(qapp):
    """Minimal ViewTab instantiation to access _generate_paidoff_report."""
    from PySide6.QtWidgets import QApplication
    from ui.view_tab import ViewTab
    return ViewTab()


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestGeneratePaidoffReport:

    def test_no_due_date_skips_report(self, qapp, caplog):
        """T-R3-05: loan.due_date is None -> WARNING logged, returns early."""
        view_tab = make_view_tab_with_method(qapp)
        loan = make_loan(due_date=None)
        with caplog.at_level(logging.WARNING):
            with patch("ui.view_tab.write_report") as mock_write:
                view_tab._generate_paidoff_report(
                    loan, date(2026, 4, 1), 12.0, 2.0, False
                )
                mock_write.assert_not_called()
        assert "no due_date" in caplog.text

    def test_paidoff_equals_due_date_extension_zero(self, qapp):
        """T-R3-06: paidoff_date = due_date -> extension_days = 0, interest = 0.0."""
        view_tab = make_view_tab_with_method(qapp)
        loan = make_loan(due_date=date(2026, 4, 1))
        written_records = []
        with patch("ui.view_tab.generate_report_id", return_value="RPT_20260401_001"), \
             patch("ui.view_tab.write_report"), \
             patch("ui.view_tab.write_report_records", side_effect=lambda recs: written_records.extend(recs)):
            view_tab._generate_paidoff_report(loan, date(2026, 4, 1), 12.0, 2.0, False)
        assert len(written_records) == 1
        assert written_records[0].extension_period == 0
        assert written_records[0].interest_amount == 0.0
        assert written_records[0].commission_amount == 0.0

    def test_paidoff_after_due_date_positive_extension(self, qapp):
        """T-R3-07: paidoff_date > due_date -> positive extension_days, nonzero interest."""
        view_tab = make_view_tab_with_method(qapp)
        loan = make_loan(due_date=date(2026, 3, 1), reference_id="2026_03_001")
        loan.amount = 10000
        written_records = []
        with patch("ui.view_tab.generate_report_id", return_value="RPT_20260401_001"), \
             patch("ui.view_tab.write_report"), \
             patch("ui.view_tab.write_report_records", side_effect=lambda recs: written_records.extend(recs)):
            view_tab._generate_paidoff_report(loan, date(2026, 4, 1), 12.0, 2.0, False)
        record = written_records[0]
        assert record.extension_period == 31  # April 1 - March 1 = 31 days
        expected_interest = (10000 * 12.0 * 31) / (365 * 100)
        assert abs(record.interest_amount - expected_interest) < 0.001

    def test_paidoff_before_due_date_no_negative(self, qapp):
        """T-R3-08: paidoff_date < due_date -> extension_days = 0 (max(0,...))."""
        view_tab = make_view_tab_with_method(qapp)
        loan = make_loan(due_date=date(2026, 5, 1))
        written_records = []
        with patch("ui.view_tab.generate_report_id", return_value="RPT_20260401_001"), \
             patch("ui.view_tab.write_report"), \
             patch("ui.view_tab.write_report_records", side_effect=lambda recs: written_records.extend(recs)):
            view_tab._generate_paidoff_report(loan, date(2026, 4, 1), 12.0, 2.0, False)
        assert written_records[0].extension_period == 0
        assert written_records[0].interest_amount == 0.0

    def test_tds_flag_true(self, qapp):
        """T-R3-10: tds_flag=True -> tds_amount = 0.1 * interest_amount."""
        view_tab = make_view_tab_with_method(qapp)
        loan = make_loan(due_date=date(2026, 3, 1))
        loan.amount = 10000
        written_records = []
        with patch("ui.view_tab.generate_report_id", return_value="RPT_20260401_001"), \
             patch("ui.view_tab.write_report"), \
             patch("ui.view_tab.write_report_records", side_effect=lambda recs: written_records.extend(recs)):
            view_tab._generate_paidoff_report(loan, date(2026, 4, 1), 12.0, 2.0, True)
        record = written_records[0]
        assert abs(record.tds_amount - 0.1 * record.interest_amount) < 0.001

    def test_tds_flag_false(self, qapp):
        """T-R3-11: tds_flag=False -> tds_amount = 0.0."""
        view_tab = make_view_tab_with_method(qapp)
        loan = make_loan(due_date=date(2026, 3, 1))
        written_records = []
        with patch("ui.view_tab.generate_report_id", return_value="RPT_20260401_001"), \
             patch("ui.view_tab.write_report"), \
             patch("ui.view_tab.write_report_records", side_effect=lambda recs: written_records.extend(recs)):
            view_tab._generate_paidoff_report(loan, date(2026, 4, 1), 12.0, 2.0, False)
        assert written_records[0].tds_amount == 0.0

    def test_mode_is_paidoff(self, qapp):
        """T-R3-12: Report mode="Paidoff" written."""
        view_tab = make_view_tab_with_method(qapp)
        loan = make_loan(due_date=date(2026, 3, 1))
        written_reports = []
        with patch("ui.view_tab.generate_report_id", return_value="RPT_20260401_001"), \
             patch("ui.view_tab.write_report", side_effect=lambda r: written_reports.append(r)), \
             patch("ui.view_tab.write_report_records"):
            view_tab._generate_paidoff_report(loan, date(2026, 4, 1), 12.0, 2.0, False)
        assert written_reports[0].mode == "Paidoff"

    def test_invalid_interest_rate_aborts(self, qapp, caplog):
        """T-R3-14: SRE-R3-02 interest_rate out of range -> ERROR logged, no write."""
        view_tab = make_view_tab_with_method(qapp)
        loan = make_loan(due_date=date(2026, 3, 1))
        with caplog.at_level(logging.ERROR):
            with patch("ui.view_tab.write_report") as mock_write:
                view_tab._generate_paidoff_report(loan, date(2026, 4, 1), 101.0, 2.0, False)
                mock_write.assert_not_called()
        assert "Invalid interest_rate" in caplog.text

    def test_invalid_commission_rate_aborts(self, qapp, caplog):
        """T-R3-15: SRE-R3-02 commission_rate out of range -> ERROR logged, no write."""
        view_tab = make_view_tab_with_method(qapp)
        loan = make_loan(due_date=date(2026, 3, 1))
        with caplog.at_level(logging.ERROR):
            with patch("ui.view_tab.write_report") as mock_write:
                view_tab._generate_paidoff_report(loan, date(2026, 4, 1), 12.0, 150.0, False)
                mock_write.assert_not_called()
        assert "Invalid commission_rate" in caplog.text

    def test_debug_log_emitted(self, qapp, caplog):
        """T-R3-16: SRE-R3-01 DEBUG log emitted with params."""
        view_tab = make_view_tab_with_method(qapp)
        loan = make_loan(due_date=date(2026, 3, 1))
        with caplog.at_level(logging.DEBUG):
            with patch("ui.view_tab.generate_report_id", return_value="RPT_20260401_001"), \
                 patch("ui.view_tab.write_report"), \
                 patch("ui.view_tab.write_report_records"):
                view_tab._generate_paidoff_report(loan, date(2026, 4, 1), 12.0, 2.0, False)
        assert "interest_rate=12.00" in caplog.text
        assert "commission_rate=2.00" in caplog.text
```

---

### File: tests/test_view_tab_colors_r3.py

```python
"""Tests for STATUS_COLORS constants (BUG-02-REF).

Tests T-R3-21 to T-R3-25.
No QApplication needed for QColor constant tests.
"""
import pytest
from PySide6.QtGui import QColor


class TestStatusColors:
    """T-R3-21 to T-R3-25: Exact hex color values."""

    def test_active_color(self):
        from ui.view_tab import STATUS_COLORS
        assert STATUS_COLORS["Active"].name() == "#2d6a4f"

    def test_overdue_color(self):
        from ui.view_tab import STATUS_COLORS
        assert STATUS_COLORS["Overdue"].name() == "#9b2226"

    def test_pending_color(self):
        from ui.view_tab import STATUS_COLORS
        assert STATUS_COLORS["Pending"].name() == "#ca6702"

    def test_paidoff_color(self):
        from ui.view_tab import STATUS_COLORS
        assert STATUS_COLORS["Paidoff"].name() == "#495057"

    def test_text_color_white(self):
        from ui.view_tab import STATUS_TEXT_COLOR
        assert STATUS_TEXT_COLOR.name() == "#ffffff"
```

---

## 3. Test Execution Command

From `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/`:

```bash
# Run all run_3 tests
pytest tests/test_paidoff_dialog_r3.py tests/test_generate_paidoff_report.py tests/test_view_tab_colors_r3.py -v

# Run with coverage
pytest tests/test_paidoff_dialog_r3.py tests/test_generate_paidoff_report.py tests/test_view_tab_colors_r3.py --cov=ui --cov-report=term-missing
```

---

## 4. Backend QA [REVIEW REQUIRED] Items

| ID | Item | Priority | Impact |
|---|---|---|---|
| BC-301 | Warning label placement — affects T-R3-18 to T-R3-20 widget query path | Medium | Test assertions use label text content rather than widget position — low impact |
| TC-303 | pending_approval_tab.py must be read before writing tests T-R3-18 to T-R3-20 to locate the correct widget | High | Tests T-R3-18 to T-R3-20 cannot be written without reading the file |

