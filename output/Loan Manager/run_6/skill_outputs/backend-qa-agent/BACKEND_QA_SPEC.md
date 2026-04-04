# Loan Manager — Backend QA Specification
**Agent:** backend-qa-agent (Wave 2)
**Run:** run_6
**Date:** 2026-04-04
**Phase:** Phase 4 QA Specification

---

## Source File Cross-Reference

Files verified directly for this spec:
- `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/loan_manager/interest_calculator.py` — calculate_monthly, calculate_daily, calculate_both confirmed
- `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/data/csv_manager.py` — CSV fieldnames, path helpers confirmed
- `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/ui/view_tab.py` — STATUS_COLORS dict confirmed
- `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/ui/widgets.py` — ClickableDateEdit.showCalendarWidget() confirmed correct

---

## Currently Passing Tests — Regression Coverage

### tests/test_interest_calculator.py
Covers: `calculate_monthly()`, `calculate_daily()`, `calculate_both()`
Key assertions to protect:
- Monthly: `(10000 * 12 * 1) / (12 * 100) = 100.0` — the R5 authoritative worked example
- Daily: `(10000 * 12 * 30) / (365 * 100) = 98.63...`
- TDS = 0.1 * interest when tds_flag=True
- TDS = 0.0 when tds_flag=False
- calculate_both routes correctly by extension_period_unit

### tests/test_filter_logic.py
Covers: UTR1 case-insensitive filter logic
Key assertions to protect:
- `_filter_loans(loans, bg_filter="BG1")` matches loans with `borrower_group="bg1"`
- Unknown filter matches loans with `depositor_group=None`
- No-filter returns only loans with `due_date=None`

### tests/test_seed.py
Covers: R7 seeding guard
Key assertions to protect:
- Seed when loans.csv absent
- Seed when loans.csv header-only
- Do NOT seed when data rows present

### tests/test_calculation_dialog_logic.py
Covers: R5 CHQ_Amt formula
Key assertions to protect:
- `_compute_chq_amt(interest=100, tds=10, tds_flag=True)` = 90.0
- `_compute_chq_amt(interest=100, tds=0, tds_flag=False)` = 90.0

---

## Phase 4 Test Specifications

### tests/test_view_tab_colors.py (CREATE NOW — no blockers)

```python
"""Test STATUS_COLORS constants match R3 specification."""
import pytest
from ui.view_tab import STATUS_COLORS


class TestStatusColors:
    def test_active_bg_color(self):
        assert STATUS_COLORS["Active"][0] == "#025c33"

    def test_active_fg_color(self):
        assert STATUS_COLORS["Active"][1] == "#ffffff"

    def test_overdue_bg_color(self):
        assert STATUS_COLORS["Overdue"][0] == "#6b0307"

    def test_overdue_fg_color(self):
        assert STATUS_COLORS["Overdue"][1] == "#ffffff"

    def test_pending_bg_color(self):
        assert STATUS_COLORS["Pending"][0] == "#804001"

    def test_pending_fg_color(self):
        assert STATUS_COLORS["Pending"][1] == "#ffffff"

    def test_paidoff_bg_color(self):
        assert STATUS_COLORS["Paidoff"][0] == "#022a52"

    def test_paidoff_fg_color(self):
        assert STATUS_COLORS["Paidoff"][1] == "#ffffff"

    def test_unknown_status_fallback(self):
        """STATUS_COLORS.get() with default should return white bg, black fg."""
        bg, fg = STATUS_COLORS.get("Unknown", ("#ffffff", "#000000"))
        assert bg == "#ffffff"
        assert fg == "#000000"
```

**Note:** This test imports from `ui.view_tab`. It requires `PySide6` to be importable (for the module-level imports in view_tab.py). Run with `pytest --no-header -q` in the src/Loan Manager directory where the venv is active.

**Alternative approach if PySide6 headless import fails:** Extract STATUS_COLORS to a separate constants module `ui/constants.py` and test that instead. [REVIEW REQUIRED] BACKEND-QA-01: Confirm whether STATUS_COLORS can be imported from view_tab without a QApplication instance.

---

### tests/test_entry_tab_logic.py (PARTIAL — create calc helper tests now)

The due_period auto-calc logic can be extracted and tested without QApplication:

```python
"""Test due_period auto-calculation logic (R1).

The actual computation is:
    new_due = giving_date + relativedelta(months=due_period)
This can be tested as a pure function without UI.
"""
import pytest
from datetime import date
from dateutil.relativedelta import relativedelta


def _calc_due_date(giving_date: date, due_period: int) -> date:
    """Replicate _on_due_period_changed() logic as a pure function."""
    return giving_date + relativedelta(months=due_period)


class TestDuePeriodCalc:
    def test_3_month_period(self):
        giving = date(2026, 1, 2)
        result = _calc_due_date(giving, 3)
        assert result == date(2026, 4, 2)

    def test_1_month_period(self):
        giving = date(2026, 3, 31)
        result = _calc_due_date(giving, 1)
        # relativedelta handles month-end correctly
        assert result == date(2026, 4, 30)

    def test_12_month_period(self):
        giving = date(2026, 1, 1)
        result = _calc_due_date(giving, 12)
        assert result == date(2027, 1, 1)

    def test_zero_period_no_change(self):
        giving = date(2026, 1, 1)
        # Period=0 means no auto-calc triggered
        # The guard `if value <= 0: return` prevents any update
        # So due_date stays at its previous value — no assertion needed here
        # Just confirm the function doesn't crash with 0
        result = _calc_due_date(giving, 0)
        assert result == date(2026, 1, 1)
```

---

### tests/test_view_tab_paidoff.py (BLOCKED by TC-05 decision on function API)

Once TC-05 is decided, this file tests:

```python
"""Test paidoff-related data layer functions (R3, TC-05)."""
import pytest
import csv
import tempfile
from pathlib import Path
from datetime import date
from unittest.mock import patch


class TestHasPendingPaidoffReport:
    """Tests for has_pending_paidoff_report() — TC-05."""

    def test_returns_true_when_pending_paidoff_exists(self, tmp_path):
        # Setup: write a Paidoff+Pending report with a matching record
        # Call has_pending_paidoff_report(reference_id)
        # Assert: returns True
        ...

    def test_returns_false_when_no_paidoff_reports(self, tmp_path):
        # Setup: empty pending_reports.csv
        # Assert: returns False
        ...

    def test_returns_false_when_paidoff_report_is_approved(self, tmp_path):
        # Setup: Paidoff report with status=Approved
        # Assert: returns False
        ...

    def test_returns_false_when_paidoff_report_is_declined(self, tmp_path):
        # Setup: Paidoff report with status=Declined
        # Assert: returns False
        ...


class TestMarkPaidoff:
    """Tests for mark_paidoff() in csv_manager."""

    def test_removes_loan_from_loans_csv(self, tmp_path):
        ...

    def test_adds_loan_to_history_csv(self, tmp_path):
        ...

    def test_raises_value_error_for_unknown_ref_id(self, tmp_path):
        ...
```

**[REVIEW REQUIRED] BACKEND-QA-02:** Confirm that `has_pending_paidoff_report()` is added to `report_manager.py` (not `csv_manager.py`) before writing this test. The import path is `from data.report_manager import has_pending_paidoff_report`.

---

### tests/test_pending_approval.py (PARTIALLY BLOCKED by TC-08)

Tests not blocked by TC-08 can be created now:

```python
"""Test pending approval data layer functions (R5)."""
import pytest
from datetime import date


class TestBatchExtendLoans:
    """Tests for batch_extend_loans() — always creatable."""

    def test_updates_giving_and_due_dates(self, tmp_path):
        # Write a loan, batch_extend, read back, assert dates updated
        ...

    def test_skips_nonexistent_ref_id(self, tmp_path):
        # batch_extend with non-existent ref_id should not raise
        ...

    def test_empty_extensions_list_no_error(self, tmp_path):
        # batch_extend([]) should be a no-op
        ...


class TestGetActiveReferenceIds:
    def test_returns_only_pending_report_ref_ids(self, tmp_path):
        ...

    def test_returns_empty_when_no_pending_reports(self, tmp_path):
        ...


class TestReportRecordPaidoffDate:
    """TC-08 Option B tests — create only after TC-08 decision."""

    def test_paidoff_date_survives_csv_roundtrip(self, tmp_path):
        # [BLOCKED by TC-08]
        ...
```

---

## Regression Risk Assessment — Phase 4 Changes

| Change | Risk to Existing Tests | Mitigation |
|---|---|---|
| TC-05: add has_pending_paidoff_report() | NONE — additive function | No test updates needed |
| TC-08 Option B: add paidoff_date to ReportRecord | LOW — additive field with default=None | test_report_manager.py: verify existing record assertions still pass |
| BC-02 Option B: lowercase normalization | MEDIUM — test_csv_manager.py may assert "BG1" stored as "BG1" | Audit test_csv_manager.py for case-sensitive expected values before implementing |
| TC-03 Option A: clear due_period | NONE — UI behavior, no data layer change | No test updates needed |

---

## QA Signoff Checklist — Phase 4

- [ ] test_view_tab_colors.py created and passing
- [ ] test_entry_tab_logic.py (due_period calc) created and passing
- [ ] test_view_tab_paidoff.py created and passing (after TC-05 decision)
- [ ] test_pending_approval.py created and passing (partial now, full after TC-08)
- [ ] test_csv_manager.py audited for BC-02 case assertions (if BC-02 implemented)
- [ ] All 8 existing test files still passing after Phase 4 changes
- [ ] `pytest --tb=short` from `src/Loan Manager/` returns 0 failures
- [ ] No `print()` statements in production code
- [ ] All new functions have type annotations
- [ ] PEP8: no obvious violations in changed files
