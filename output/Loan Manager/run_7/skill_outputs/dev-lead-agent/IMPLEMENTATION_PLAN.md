# Loan Manager — Implementation Plan
**Agent:** dev-lead-agent (Wave 2)
**Run:** run_7
**Date:** 2026-04-05
**Phase:** Phase 3 Closure / Phase 4 MVP

---

## Dev Lead Assessment: Implementation State

All Phase 1, 2, and 3 requirements have been implemented and tested (237 tests passing). This document covers the Phase 4 remaining implementation tasks.

**Key architectural confirmation (carry-forward from run_2):**
- `loan_manager/status_engine.py` is canonical
- `data/status_engine.py` is the re-export shim only
- This layering is correct and stable

---

## TASK-1: TC-05 — Mark Paidoff Double Guard (PD-10 BINDING — Start Immediately)

**No user decision required. Implement now.**

### Step 1: Add `has_pending_paidoff_report()` to `loan_manager/report_manager.py`

Read the existing `CSVReportManager.get_active_reference_ids_in_queue()` method for reference. The new method follows the same read pattern.

```python
def has_pending_paidoff_report(
    self, reports_path: Path, records_path: Path, reference_id: str
) -> bool:
    """Return True if a Pending Paidoff-mode report exists for reference_id.

    Reads pending_reports.csv to find Paidoff-mode pending report IDs,
    then checks pending_report_records.csv for a matching reference_id.
    Returns False if no pending Paidoff reports exist (fast path).
    """
    pending_reports = self.read_pending_reports(reports_path)
    paidoff_report_ids = {
        r.report_id for r in pending_reports if r.mode == "Paidoff"
    }
    if not paidoff_report_ids:
        return False
    for row in self._read_raw(records_path):
        if (row.get("report_id", "").strip() in paidoff_report_ids
                and row.get("reference_id", "").strip() == reference_id):
            return True
    return False
```

### Step 2: Add adapter in `data/report_manager.py`

```python
def has_pending_paidoff_report(reference_id: str) -> bool:
    """Return True if a Pending Paidoff-mode report exists for this reference_id."""
    return _manager.has_pending_paidoff_report(
        _reports_path(), _records_path(), reference_id
    )
```

Update the import in `data/report_manager.py` header docstring to reflect new function.

### Step 3: Update `ui/view_tab.py` `_show_context_menu()`

Current code (line 326):
```python
paidoff_action.setEnabled(loan.due_date is not None)
```

Updated code:
```python
from data.report_manager import has_pending_paidoff_report

# In _show_context_menu():
already_pending = has_pending_paidoff_report(loan.reference_id)
paidoff_action.setEnabled(loan.due_date is not None and not already_pending)
if already_pending:
    paidoff_action.setToolTip(
        "A Paidoff report for this loan is already pending approval."
    )
```

Note: The `has_pending_paidoff_report` import should be added at module level (top of view_tab.py), not inside the method.

**Estimated effort:** 1 hour. Test with test_view_tab_paidoff.py.

---

## TASK-2: TC-08 — paidoff_date Field (PENDING USER DECISION)

### Option A: Accept Field Reuse (zero code change)
Add code comment to `ui/view_tab.py` `_action_paidoff()`:
```python
# R3: For Paidoff-mode reports, paidoff_date is stored in new_due_date field.
# This is field reuse accepted per TC-08 Option A decision.
```

### Option B: Dedicated paidoff_date Column (DM/SA/Dev Lead RECOMMENDED)

**Files to change:**

**1. `models/report.py`:**
Add to `ReportRecord` dataclass:
```python
paidoff_date: Optional[date] = None  # R3: set only for mode="Paidoff" records
```

Add to `REPORT_RECORD_FIELDNAMES`:
```python
REPORT_RECORD_FIELDNAMES = [
    # ... existing fields ...
    "paidoff_date",  # NEW: for mode="Paidoff" records
]
```

Add to `to_csv_row()`:
```python
"paidoff_date": self.paidoff_date.isoformat() if self.paidoff_date else "",
```

Add to `from_csv_row()`:
```python
paidoff_date_raw = row.get("paidoff_date", "").strip()
paidoff_date = date.fromisoformat(paidoff_date_raw) if paidoff_date_raw else None
# ...
paidoff_date=paidoff_date,
```

**2. `ui/view_tab.py` `_action_paidoff()`:**
Change `new_due_date=paidoff_date` to:
```python
paidoff_date=paidoff_date,
new_due_date=None,  # cleared for Paidoff-mode records
```

**3. `ui/pending_approval_tab.py` `_on_approve()`:**
In the Paidoff branch, change:
```python
paidoff_date = rec.new_due_date if rec.new_due_date else date.today()
```
To (backward-compatible read):
```python
paidoff_date = rec.paidoff_date or rec.new_due_date or date.today()
```

**Estimated effort:** 2 hours. No data migration needed.

**[REVIEW REQUIRED] TC-08:** User decision required.

---

## TASK-3: TC-03 — due_period Clear Behavior (PENDING USER DECISION)

### Option A: Clear Due Period on manual Due Date edit

Add signal connection in `ui/entry_tab.py` `_build_ui()`:
```python
self._due_date.dateChanged.connect(self._on_due_date_manually_changed)
```

Add method:
```python
def _on_due_date_manually_changed(self, q_date) -> None:
    """TC-03 Option A: Clear due_period when user manually edits due_date.

    Uses _suppressing_due_period flag to prevent recursion with
    _on_due_period_changed -> setDate -> dateChanged signal loop.
    """
    if self._suppressing_due_date_signal:
        return
    # User manually picked a date — clear the period to avoid stale display
    self._due_period.blockSignals(True)
    self._due_period.setValue(0)
    self._due_period.blockSignals(False)
```

Add `_suppressing_due_date_signal = False` instance variable in `__init__`.

In `_on_due_period_changed()`, wrap the `setDate` call:
```python
self._suppressing_due_date_signal = True
self._due_date.setDate(QDate(new_due.year, new_due.month, new_due.day))
self._suppressing_due_date_signal = False
```

### Option B: No change (current behavior — recommended by all agents)
Zero code change. Due period retained for display; has no effect on stored data.

**[REVIEW REQUIRED] TC-03:** User decision required.

---

## TASK-4: BC-02 — Case Normalization (PENDING USER DECISION)

### Option B: Lowercase at write time

Add to `data/csv_manager.py`:
```python
def _normalize_text_fields(loan: Loan) -> None:
    """BC-02 Option B: Normalize name/group fields to lowercase at write time."""
    loan.borrower_name = (loan.borrower_name or "").lower().strip()
    loan.borrower_group = (loan.borrower_group or "").lower().strip()
    loan.depositor_name = (loan.depositor_name or "").lower().strip() or None
    loan.depositor_group = (loan.depositor_group or "").lower().strip() or None
```

Call at start of `write_loan()`:
```python
def write_loan(loan: Loan) -> None:
    _normalize_text_fields(loan)
    # ... existing code
```

**[REVIEW REQUIRED] BC-02:** User decision required. Option C uses `.title()` instead of `.lower()`.

---

## TASK-5: SRE-01 — Startup Recovery Warning (ALREADY DONE)

Code review of `ui/main_window.py` confirms `approval_recovery.tmp` is already handled in `_check_recovery_file()`. No implementation needed. This task is CLOSED.

---

## TASK-6: Missing Test Files

All test files below can be created immediately. No blocking dependencies except where noted.

### test_view_tab_colors.py (no blockers — create now)
```python
"""Tests for STATUS_COLORS in ui.view_tab — pure import test, no QApplication needed."""
from ui.view_tab import STATUS_COLORS

def test_status_colors_active():
    assert STATUS_COLORS["Active"] == ("#025c33", "#ffffff")

def test_status_colors_overdue():
    assert STATUS_COLORS["Overdue"] == ("#6b0307", "#ffffff")

def test_status_colors_pending():
    assert STATUS_COLORS["Pending"] == ("#804001", "#ffffff")

def test_status_colors_paidoff():
    assert STATUS_COLORS["Paidoff"] == ("#022a52", "#ffffff")

def test_all_statuses_present():
    assert set(STATUS_COLORS.keys()) == {"Active", "Overdue", "Pending", "Paidoff"}

def test_all_foregrounds_are_white():
    for status, (bg, fg) in STATUS_COLORS.items():
        assert fg == "#ffffff", f"Expected white fg for {status}"
```

### test_entry_tab_logic.py (no blockers — create now)
```python
"""Tests for due_period calculation logic — isolated from QApplication."""
from datetime import date
from dateutil.relativedelta import relativedelta

def _calc_due_date(giving_date: date, due_period_months: int) -> date:
    """Replicate _on_due_period_changed calculation."""
    return giving_date + relativedelta(months=due_period_months)

def test_due_period_3_months():
    giving = date(2026, 1, 2)
    result = _calc_due_date(giving, 3)
    assert result == date(2026, 4, 2)

def test_due_period_1_month():
    giving = date(2026, 3, 31)
    result = _calc_due_date(giving, 1)
    assert result == date(2026, 4, 30)

def test_due_period_12_months():
    giving = date(2026, 1, 1)
    result = _calc_due_date(giving, 12)
    assert result == date(2027, 1, 1)

def test_due_period_zero_no_change():
    giving = date(2026, 1, 2)
    result = _calc_due_date(giving, 0)
    assert result == giving

def test_due_period_cross_year():
    giving = date(2026, 11, 15)
    result = _calc_due_date(giving, 3)
    assert result == date(2027, 2, 15)
```

### test_view_tab_paidoff.py (can create TC-05 portion now; TC-08 portion after user decision)
Tests for `has_pending_paidoff_report()` using injectable paths (no QApplication needed).

### test_pending_approval.py — batch_extend portion (create now)
Tests for `batch_extend_loans()` using injectable paths.

---

## QA Lead KT Handoff

### Feature: TC-05 — Mark Paidoff Guard
**Changed files:** `loan_manager/report_manager.py`, `data/report_manager.py`, `ui/view_tab.py`
**Test to write:** `tests/test_view_tab_paidoff.py` — test `has_pending_paidoff_report()` with mock CSV files
**Manual smoke test:** Right-click loan with pending Paidoff report → verify "Mark Paidoff" is grayed out

### Feature: TC-08 Option B (if chosen)
**Changed files:** `models/report.py`, `loan_manager/report_manager.py`, `ui/view_tab.py`, `ui/pending_approval_tab.py`
**Test to write:** `tests/test_pending_approval.py` — test paidoff_date column round-trip
**Manual smoke test:** Generate Paidoff report → verify paidoff_date stored correctly → approve → verify loan moved to history

### Feature: BC-02 Option B (if chosen)
**Changed files:** `data/csv_manager.py`
**Test to write:** add to `tests/test_csv_manager.py` — test normalization at write time
**Manual smoke test:** Enter loan with "BG1" → verify stored as "bg1" in loans.csv

---

## Implementation Priority Order

1. TASK-1 (TC-05): Implement immediately — PD-10 binding, no user input needed
2. TASK-6 (test_view_tab_colors.py, test_entry_tab_logic.py): Create immediately — no blockers
3. TASK-2 (TC-08): Implement after user decision
4. TASK-3 (TC-03): Implement after user decision (or confirm Option B = no change)
5. TASK-4 (BC-02): Implement after user decision
6. TASK-6 remaining test files: After TASK-2 decision
7. pytest gate: Run after all implementations complete
