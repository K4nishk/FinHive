# Loan Manager — Backend Dev Specification
**Agent:** backend-dev-agent (Wave 2)
**Run:** run_6
**Date:** 2026-04-04
**Phase:** Phase 4 Implementation Spec

---

## Source Code Audit (Phase 3 Closure)

All Phase 3 implementation items are confirmed present and correct in source:

### ui/widgets.py
- `ClickableDateEdit`: `mousePressEvent` calls `self.showCalendarWidget()` — CORRECT (UTR1 fix)
- `focusInEvent` guarded by `TabFocusReason/BacktabFocusReason` — CORRECT (R1)
- `DatePickerDelegate.setModelData()` writes ISO 8601 `YYYY-MM-DD` — CORRECT (R8)

### ui/entry_tab.py
- `_due_period` QSpinBox with `_on_due_period_changed()` auto-calc — CORRECT (R1)
- `_on_giving_date_changed()` recalculates due_date when period > 0 — CORRECT (R1)
- `blockSignals()` guards prevent recursion — CORRECT

### ui/view_tab.py
- `STATUS_COLORS` dict: `(bg_hex, fg_hex)` tuples — CORRECT (R3)
- `_make_row()` applies `QColor(bg_hex)` and `QColor(fg_hex)` with bold font — CORRECT
- `DatePickerDelegate` applied to COL_GIVING_DATE and COL_DUE_DATE — CORRECT (R2)
- `_action_paidoff()`: no `mark_paidoff()` call at generation, only at approval — CORRECT (R3)
- `paidoff_action.setEnabled(loan.due_date is not None)` — CORRECT (R3)
- TC-05 guard: NOT yet implemented — needs Phase 4

### ui/pending_approval_tab.py
- `mark_paidoff()` called in `_on_approve()` for mode="Paidoff" reports — CORRECT
- `rec.new_due_date` used as paidoff_date — CURRENT BEHAVIOR (TC-08 field reuse)
- approval_recovery.tmp written before destructive writes — CORRECT (SRE)
- Shared ref-id warning — CORRECT (R5)
- Deleted loan warning — CORRECT (R5)

### ui/dialogs/calculation_dialog.py
- Modal dialog (`setModal(True)`, `exec()`) — CORRECT (PD-06)
- `_compute_chq_amt()` pure function — CORRECT (R5)
- `CalculationDialog` receives filtered_loans and global params from tab — CORRECT

### data/seed.py
- Guard: seed only when loans.csv absent or header-only — CORRECT (PD-01, R7)
- loans_meta.csv updated after seeding — CORRECT

### loan_manager/interest_calculator.py
- `calculate_monthly()`: Time = extension_period, not tenure — CORRECT (R5 authoritative)
- `calculate_daily()`: Time = extension_period — CORRECT
- `calculate_both()`: routes by extension_period_unit — CORRECT

---

## Phase 4 Implementation Specifications

### SPEC-TC05: has_pending_paidoff_report()

**Location:** `data/report_manager.py`

```python
def has_pending_paidoff_report(reference_id: str) -> bool:
    """Return True if a Paidoff-mode Pending report exists for this reference_id.

    Used by view_tab to disable/guard the 'Mark Paidoff' context menu action.
    Queries pending_reports.csv for Paidoff+Pending reports, then checks
    pending_report_records.csv for matching reference_id.
    """
    pending_reports = read_pending_reports()
    paidoff_pending_ids = {
        r.report_id
        for r in pending_reports
        if r.mode == "Paidoff" and r.status == "Pending"
    }
    if not paidoff_pending_ids:
        return False
    all_records = _read_all_report_records()
    return any(
        rec.report_id in paidoff_pending_ids and rec.reference_id == reference_id
        for rec in all_records
    )


def _read_all_report_records() -> List[ReportRecord]:
    """Read all report records from pending_report_records.csv."""
    path = _RECORDS_PATH
    if not path.exists():
        return []
    records = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rec = _parse_record_row(row)
            if rec is not None:
                records.append(rec)
    return records
```

**Caller update in `ui/view_tab.py`:**
```python
# In _show_context_menu():
from data.report_manager import has_pending_paidoff_report

paidoff_action = QAction("Mark Paidoff", self)
paidoff_action.triggered.connect(lambda: self._action_paidoff(loan))
# R3: Disable Mark Paidoff when loan has no due_date
has_due = loan.due_date is not None
# TC-05: Also disable when Paidoff report already pending
has_pending_paidoff = has_due and has_pending_paidoff_report(loan.reference_id)
paidoff_action.setEnabled(has_due and not has_pending_paidoff)
menu.addAction(paidoff_action)
```

This applies for TC-05 Option A. For Option B (warn), the check moves to `_action_paidoff()`.

---

### SPEC-TC08 (Option B): paidoff_date Column

**Location:** `models/report.py`

```python
@dataclass
class ReportRecord:
    report_id: str
    reference_id: str
    borrower_name: str
    amount: int
    depositor_name: Optional[str]
    giving_date: date
    due_date: Optional[date]
    interest_rate: float
    commission_rate: float
    extension_period: int
    extension_period_unit: str
    tds_flag: bool
    new_giving_date: Optional[date]
    new_due_date: Optional[date]
    interest_amount: float
    commission_amount: float
    tds_amount: float
    paidoff_date: Optional[date] = None  # NEW: populated for mode=Paidoff only
```

**Location:** `data/report_manager.py`
- `_RECORD_FIELDNAMES`: add `"paidoff_date"` to the field list
- `write_report_records()`: serialize `paidoff_date` as ISO string or empty
- `_parse_record_row()`: parse `paidoff_date` from `row.get("paidoff_date", "")` with `date.fromisoformat()` or `None`

**Location:** `ui/view_tab.py _action_paidoff()`
```python
record = ReportRecord(
    ...
    new_giving_date=None,
    new_due_date=None,          # cleared for Paidoff-mode (no longer dual-semantic)
    paidoff_date=paidoff_date,  # NEW: dedicated field
    ...
)
```

**Location:** `ui/pending_approval_tab.py _on_approve()`
```python
# For Paidoff-mode records:
paidoff_date = rec.paidoff_date if rec.paidoff_date else date.today()
mark_paidoff(rec.reference_id, paidoff_date)
```

---

### SPEC-TC03 (Option A): due_period Clear Guard

**Location:** `ui/entry_tab.py`

Add `_suppressing_date_signal: bool` instance flag. Set to True before programmatic due_date updates, False after. Connect `_due_date.dateChanged` to `_on_due_date_changed()` which clears due_period only when `_suppressing_date_signal` is False.

---

### SPEC-BC02 (Option B): Lowercase Normalization

**Location:** `data/csv_manager.py`

Add at module level:
```python
def _normalize_str(value: Optional[str]) -> Optional[str]:
    """BC-02 Option B: normalize string to lowercase at write time."""
    if value is None:
        return None
    return value.strip().lower()
```

Apply in `write_loan()` to: `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group`.

**Note:** `update_loan()` must also apply normalization. Check if `update_loan()` calls `write_loan()` or writes directly — normalize at both write points.

---

## Breaking Changes Checklist

| Change | Impact | Test Update Required |
|---|---|---|
| TC-08 Option B: ReportRecord gains paidoff_date field | additive | test_report_manager.py: update any record creation with explicit paidoff_date=None |
| TC-08 Option B: view_tab writes paidoff_date not new_due_date | logic | test_pending_approval.py: verify paidoff_date reads correctly |
| TC-05: has_pending_paidoff_report() added to report_manager | additive | test_view_tab_paidoff.py: new function tests |
| BC-02 Option B: write_loan normalizes to lowercase | write behavior | test_csv_manager.py: check case assertions — may need lowercase expected values |

---

## Implementation Dependencies

The following items from report_manager.py need to be confirmed before SPEC-TC05 can be implemented:
- Does `read_report_records(report_id: str)` exist? YES — confirmed in pending_approval_tab.py imports.
- Is there an existing `_read_all_report_records()` or do we need to add one? Check report_manager.py.
- Does `_RECORDS_PATH` exist as a module-level constant? Likely yes — confirm naming in report_manager.py.

[REVIEW REQUIRED] SPEC-TC05: Confirm `_RECORDS_PATH` constant name and `_parse_record_row()` function name in report_manager.py before implementing `has_pending_paidoff_report()`. These names are assumed from the pattern; actual names may differ.

---

## Python Patterns Compliance

- Pure functions: `has_pending_paidoff_report()` is pure (read-only) — correct
- `_compute_chq_amt()` already pure — confirmed
- `calculate_monthly/daily/both()` already pure — confirmed
- Error handling: all file operations wrapped in try/except with logging — confirmed throughout
- PEP8: no violations in Phase 3 files reviewed
- Type annotations: all new functions must include return type hints
- Optional[date] used correctly — consistent with existing dataclass patterns
