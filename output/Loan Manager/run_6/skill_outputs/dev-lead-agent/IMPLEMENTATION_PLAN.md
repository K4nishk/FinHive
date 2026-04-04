# Loan Manager — Implementation Plan
**Agent:** dev-lead-agent (Wave 2)
**Run:** run_6
**Date:** 2026-04-04
**Phase:** Phase 4 Implementation Planning

---

## Implementation Status Summary

Phase 3 is fully implemented. The codebase is clean and well-structured. All Phase 3 features are confirmed present in source. This plan focuses on the 4 Phase 4 implementation items (TC-05, TC-08, TC-03, BC-02), remaining test files, and the SRE-01 startup recovery warning.

---

## Pre-Resolved Decisions (From Wave 1)

| Item | SA Decision | DM Decision | Implementation Target |
|---|---|---|---|
| TC-05 location | Data layer: has_pending_paidoff_report() in report_manager.py | N/A | report_manager.py + view_tab.py |
| TC-08 schema | Option B recommended (additive paidoff_date column) | Option B recommended | models/report.py + report_manager.py |
| TC-03 approach | Guard flag pattern: _suppressing_date_change bool | N/A (UI only) | ui/entry_tab.py |
| BC-02 normalization | .lower() or .title() at write time | Option B recommended | data/csv_manager.py |
| SRE-01 startup check | Low-effort warning | N/A | main.py |

---

## Task Breakdown — Waiting on User Decisions

### TASK-TC05 (HIGH PRIORITY)
**Condition:** Execute after user chooses Option A or Option B
**File:** `data/report_manager.py`
**Add function:**
```python
def has_pending_paidoff_report(reference_id: str) -> bool:
    """Return True if a Paidoff-mode Pending report exists for reference_id."""
    pending = read_pending_reports()
    paidoff_report_ids = {
        r.report_id for r in pending
        if r.mode == "Paidoff" and r.status == "Pending"
    }
    if not paidoff_report_ids:
        return False
    records = _read_all_report_records()
    for rec in records:
        if rec.report_id in paidoff_report_ids and rec.reference_id == reference_id:
            return True
    return False
```

**File:** `ui/view_tab.py`
**Modify `_show_context_menu()`:**
```python
from data.report_manager import has_pending_paidoff_report
# After: paidoff_action.setEnabled(loan.due_date is not None)
# Add:
if loan.due_date is not None:
    paidoff_action.setEnabled(not has_pending_paidoff_report(loan.reference_id))
```

If Option B (warn instead): replace with a check in `_action_paidoff()` that queries `has_pending_paidoff_report()` and shows a warning QMessageBox before opening PaidoffDialog.

**Test file:** `tests/test_view_tab_paidoff.py`
- T-TC05-01: `has_pending_paidoff_report()` returns True when pending Paidoff report exists
- T-TC05-02: `has_pending_paidoff_report()` returns False when no pending Paidoff report
- T-TC05-03: `has_pending_paidoff_report()` returns False when Paidoff report exists but is Approved/Declined

---

### TASK-TC08 (HIGH PRIORITY — if Option B chosen)
**Condition:** Execute only if user chooses Option B
**File:** `models/report.py`
**Modify ReportRecord dataclass:**
```python
@dataclass
class ReportRecord:
    # ... existing fields ...
    paidoff_date: Optional[date] = None  # NEW — populated only for mode=Paidoff reports
```

**File:** `data/report_manager.py`
**Modify `write_report_records()`:** Include `paidoff_date` column in CSV row dict.
**Modify `read_report_records()`:** Parse `paidoff_date` column from CSV row.

**File:** `ui/view_tab.py`
**Modify `_action_paidoff()`:** Write `paidoff_date=paidoff_date` to ReportRecord, set `new_due_date=None` for Paidoff-mode reports.

**File:** `ui/pending_approval_tab.py`
**Modify `_on_approve()`:** Read `rec.paidoff_date` instead of `rec.new_due_date` for Paidoff-mode records.

**Test:** `tests/test_pending_approval.py`
- T-TC08-01: ReportRecord with paidoff_date survives CSV round-trip
- T-TC08-02: Approval reads paidoff_date correctly for Paidoff-mode records

---

### TASK-TC03 (MEDIUM PRIORITY — if Option A chosen)
**Condition:** Execute only if user chooses Option A
**File:** `ui/entry_tab.py`
**Add guard flag and slot:**
```python
def __init__(self, ...):
    ...
    self._suppressing_date_signal = False  # guard flag for TC-03
    ...
    self._due_date.dateChanged.connect(self._on_due_date_changed)

def _on_due_period_changed(self, value: int) -> None:
    ...
    self._suppressing_date_signal = True
    self._due_date.blockSignals(True)
    self._due_date.setDate(QDate(...))
    self._due_date.blockSignals(False)
    self._suppressing_date_signal = False

def _on_due_date_changed(self, q_date) -> None:
    """TC-03 Option A: clear due_period when user manually edits due_date."""
    if not self._suppressing_date_signal:
        self._due_period.blockSignals(True)
        self._due_period.setValue(0)
        self._due_period.blockSignals(False)
```

**Test:** `tests/test_entry_tab_logic.py`
- T-TC03-01: due_period clears when due_date manually edited (Option A)

---

### TASK-BC02 (LOW PRIORITY — if Option B or C chosen)
**Condition:** Execute only if user chooses Option B or Option C
**File:** `data/csv_manager.py`
**Modify `write_loan()`:**
```python
def _normalize_name(value: Optional[str]) -> Optional[str]:
    """BC-02: normalize name at write time."""
    if value is None:
        return None
    return value.lower()  # Option B: lowercase; use .title() for Option C
```
Apply to: `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group` before writing row.

---

### TASK-SRE01 (LOW PRIORITY — recommended addition)
**File:** `main.py`
**Add startup check:**
```python
_RECOVERY_PATH = Path(__file__).parent / "data" / "approval_recovery.tmp"

def _check_recovery_on_startup() -> None:
    if _RECOVERY_PATH.exists():
        logging.getLogger(__name__).warning(
            "approval_recovery.tmp found — an approval may have been interrupted"
        )
        # Show non-blocking warning after window is shown
```

---

## Remaining Test Files

### tests/test_entry_tab_logic.py
Pure logic tests — no QApplication required for due_period auto-calc (if extracted to helper function).
- T-R1-01: due_date = giving_date + due_period months
- T-R1-02: due_period=0 → due_date unchanged
- T-TC03-01: (Option A only) due_period cleared after manual due_date edit

### tests/test_view_tab_paidoff.py
Data-layer tests (no UI required):
- T-TC05-01 through T-TC05-03: has_pending_paidoff_report() correctness
- T-R3-01: mark_paidoff() removes from loans.csv, adds to history.csv
- T-R3-02: mark_paidoff() raises ValueError if ref_id not found

### tests/test_pending_approval.py
Data-layer tests:
- T-TC08-01 through T-TC08-02: paidoff_date round-trip (Option B only)
- T-R5-01: batch_extend_loans() updates giving_date and due_date correctly
- T-R5-02: batch_extend_loans() skips deleted ref_ids gracefully

### tests/test_view_tab_colors.py
Pure data tests (STATUS_COLORS dict, no UI required):
- T-R3-COLOR-01: STATUS_COLORS['Active'] = ('#025c33', '#ffffff')
- T-R3-COLOR-02: STATUS_COLORS['Overdue'] = ('#6b0307', '#ffffff')
- T-R3-COLOR-03: STATUS_COLORS['Pending'] = ('#804001', '#ffffff')
- T-R3-COLOR-04: STATUS_COLORS['Paidoff'] = ('#022a52', '#ffffff')

---

## Implementation Order

1. Receive user decisions (TC-05, TC-08, TC-03, BC-02) — BLOCKING
2. TASK-TC08 (if Option B) — schema change first, before any Paidoff-related tests
3. TASK-TC05 — add has_pending_paidoff_report() + view_tab guard
4. TASK-TC03 (if Option A) — entry_tab UX fix
5. TASK-BC02 (if Option B/C) — write normalization
6. TASK-SRE01 — startup warning (low effort, low risk)
7. Write test_view_tab_paidoff.py, test_pending_approval.py, test_entry_tab_logic.py, test_view_tab_colors.py
8. Run `pytest --tb=short` from `src/Loan Manager/` — must pass with 0 failures
9. Handoff to QA for manual smoke tests

---

## Breaking Changes in Phase 4

| Change | Type | Test Impact |
|---|---|---|
| TC-08 Option B: paidoff_date column added to ReportRecord | Schema | test_pending_approval.py assertions on ReportRecord fields |
| TC-08 Option B: view_tab writes paidoff_date, not new_due_date for Paidoff | Logic | test_view_tab_paidoff.py |
| BC-02 Option B: write_loan normalizes to lowercase | Write behavior | test_csv_manager.py may need update if it asserts exact case |

---

## Phase 4 Readiness

**Status:** READY to implement once user decisions received.
**Estimated effort:** 1 implementation session (3-5 hours) after decisions.
**Dependency:** All 4 user decisions required before any implementation begins to avoid re-work.

---

## Layering Confirmation (run_2 Resolution Maintained)

`loan_manager/status_engine.py` = canonical implementation
`data/status_engine.py` = re-export shim: `from loan_manager.status_engine import *`
No circular imports. All imports from `data.status_engine` and `loan_manager.status_engine` resolve correctly.
