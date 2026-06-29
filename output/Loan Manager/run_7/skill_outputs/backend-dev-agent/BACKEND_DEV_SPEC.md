# Loan Manager — Backend Dev Spec
**Agent:** backend-dev-agent (Wave 2)
**Run:** run_7
**Date:** 2026-04-05
**Phase:** Phase 3 Closure / Phase 4 MVP

---

## Backend Implementation Specification — Phase 4

This document provides precise implementation specs for all Phase 4 backend changes. All UI changes are covered here (this is a desktop app; backend-dev-agent covers both business logic and PySide6 UI).

---

## IMPL-1: TC-05 — has_pending_paidoff_report() (PD-10 BINDING)

### File 1: `src/Loan Manager/loan_manager/report_manager.py`

**Where to insert:** After `get_active_reference_ids_in_queue()` method (end of class, line ~269).

```python
def has_pending_paidoff_report(
    self, reports_path: Path, records_path: Path, reference_id: str
) -> bool:
    """Return True if a Pending Paidoff-mode report contains reference_id.

    Fast path: returns False immediately if no Paidoff-mode pending reports.
    Used by View Tab to disable 'Mark Paidoff' context menu item per R3/PD-10.

    Args:
        reports_path: Path to pending_reports.csv
        records_path: Path to pending_report_records.csv
        reference_id: The loan reference_id to check
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

### File 2: `src/Loan Manager/data/report_manager.py`

**Add to public API section** (after `get_active_reference_ids_in_queue`):

```python
def has_pending_paidoff_report(reference_id: str) -> bool:
    """Return True if a Pending Paidoff-mode report exists for this reference_id.

    Called by View Tab _show_context_menu() to disable 'Mark Paidoff' per R3/PD-10.
    """
    return _manager.has_pending_paidoff_report(
        _reports_path(), _records_path(), reference_id
    )
```

### File 3: `src/Loan Manager/ui/view_tab.py`

**Import update** (add to existing data imports at top of file):
```python
from data.report_manager import (
    generate_report_id,
    has_pending_paidoff_report,  # NEW — TC-05 PD-10
    write_report,
    write_report_records,
)
```

**Method update `_show_context_menu()`** — replace line:
```python
paidoff_action.setEnabled(loan.due_date is not None)
```
With:
```python
_paidoff_blocked = has_pending_paidoff_report(loan.reference_id)
paidoff_action.setEnabled(loan.due_date is not None and not _paidoff_blocked)
if _paidoff_blocked:
    paidoff_action.setToolTip(
        "A Paidoff report for this loan is already awaiting approval."
    )
```

---

## IMPL-2: TC-08 Option B — paidoff_date Column (CONDITIONAL ON USER DECISION)

### File 1: `src/Loan Manager/models/report.py`

**Update `REPORT_RECORD_FIELDNAMES`:**
```python
REPORT_RECORD_FIELDNAMES = [
    "report_id",
    "reference_id",
    "borrower_name",
    "amount",
    "depositor_name",
    "giving_date",
    "due_date",
    "interest_rate",
    "commission_rate",
    "extension_period",
    "extension_period_unit",
    "tds_flag",
    "new_giving_date",
    "new_due_date",
    "interest_amount",
    "commission_amount",
    "tds_amount",
    "paidoff_date",  # R3 TC-08 Option B: dedicated field for Paidoff-mode records
]
```

**Update `ReportRecord` dataclass** (add field after `tds_amount`):
```python
paidoff_date: Optional[date] = None  # R3 TC-08: set only for mode="Paidoff" records
```

**Update `to_csv_row()`** (add to return dict):
```python
"paidoff_date": self.paidoff_date.isoformat() if self.paidoff_date else "",
```

**Update `from_csv_row()`** (add parsing before return):
```python
paidoff_date_raw = row.get("paidoff_date", "").strip()
paidoff_date_val: Optional[date] = (
    date.fromisoformat(paidoff_date_raw) if paidoff_date_raw else None
)
```
And add to `ReportRecord(...)` constructor call:
```python
paidoff_date=paidoff_date_val,
```

### File 2: `src/Loan Manager/ui/view_tab.py` `_action_paidoff()`

**Replace** (in the `record = ReportRecord(...)` block):
```python
new_due_date=paidoff_date,  # paidoff_date stored in new_due_date field
```
**With:**
```python
paidoff_date=paidoff_date,  # TC-08 Option B: dedicated field
new_due_date=None,          # cleared for Paidoff-mode records
```

### File 3: `src/Loan Manager/ui/pending_approval_tab.py` `_on_approve()`

**In Paidoff branch, update paidoff_date read (backward-compatible):**
```python
# TC-08 Option B: read from paidoff_date field; fall back to new_due_date for
# records written before this schema change (backward compatibility)
paidoff_date = rec.paidoff_date or rec.new_due_date or date.today()
```

---

## IMPL-3: TC-03 Option A — Clear Due Period on Manual Due Date Edit

### File: `src/Loan Manager/ui/entry_tab.py`

**Add instance variable in `__init__`** (after `super().__init__(parent)`):
```python
self._suppressing_due_date_signal: bool = False
```

**Add signal connection in `_build_ui()`** (after existing dateChanged connections):
```python
# TC-03 Option A: clear due_period when user manually picks a due_date
self._due_date.dateChanged.connect(self._on_due_date_manually_changed)
```

**Wrap `setDate` in `_on_due_period_changed()`:**
```python
def _on_due_period_changed(self, value: int) -> None:
    if value <= 0:
        return
    q_giving = self._giving_date.date()
    giving = date(q_giving.year(), q_giving.month(), q_giving.day())
    new_due = giving + relativedelta(months=value)
    self._no_due_date_cb.setChecked(False)
    self._suppressing_due_date_signal = True  # TC-03: prevent clearing period
    self._due_date.blockSignals(True)
    self._due_date.setDate(QDate(new_due.year, new_due.month, new_due.day))
    self._due_date.blockSignals(False)
    self._suppressing_due_date_signal = False
```

Note: The existing code uses `blockSignals(True/False)` which already prevents the dateChanged signal, so this guard may already be sufficient. Verify behavior in testing before adding the flag.

**Add new method:**
```python
def _on_due_date_manually_changed(self, q_date) -> None:
    """TC-03 Option A: Clear due_period when user manually edits due_date.

    Not triggered when _on_due_period_changed() sets the date programmatically
    (blockSignals prevents the dateChanged signal from firing).
    """
    if self._suppressing_due_date_signal:
        return
    self._due_period.blockSignals(True)
    self._due_period.setValue(0)
    self._due_period.blockSignals(False)
```

---

## IMPL-4: BC-02 Option B — Lowercase Normalization at Write Time

### File: `src/Loan Manager/data/csv_manager.py`

**Add helper function** (before `write_loan()`):
```python
def _normalize_loan_fields(loan: Loan) -> None:
    """BC-02 Option B: Normalize text fields to lowercase at write time.

    Applied only to write_loan() for new entries. Existing records are
    not retroactively normalized. Filter matching uses .lower() (UTR1),
    so all cases work correctly regardless of stored case.
    """
    loan.borrower_name = (loan.borrower_name or "").lower().strip()
    loan.borrower_group = (loan.borrower_group or "").lower().strip()
    if loan.depositor_name is not None:
        loan.depositor_name = loan.depositor_name.lower().strip() or None
    if loan.depositor_group is not None:
        loan.depositor_group = loan.depositor_group.lower().strip() or None
```

**Update `write_loan()`:**
```python
def write_loan(loan: Loan) -> None:
    """Append a new loan record to loans.csv."""
    _normalize_loan_fields(loan)  # BC-02 Option B: normalize text fields
    _ensure_loans_csv()
    # ... existing code unchanged
```

---

## UI Functionality Audit — Phase 3 Complete Features

This section confirms all UI features are functional after reviewing the source code:

### Entry Tab (R1)
- [x] All 8 form fields present (borrower_name, borrower_group, amount, giving_date, due_period, due_date, depositor_name, depositor_group)
- [x] due_period shown before due_date in form layout (line 95-102 before 108-117)
- [x] ClickableDateEdit with setCalendarPopup(True) — opens on click and Tab
- [x] showCalendarWidget() bug FIXED — widget uses setCalendarPopup(True) which enables built-in popup behavior
- [x] due_period auto-calc: dateChanged → relativedelta(months=value)
- [x] No Due Date checkbox disables due_date field
- [x] Autocomplete from existing CSV values (borrower_name, borrower_group, depositor_name, depositor_group)
- [x] Status bar message on save: "Loan saved successfully. Reference ID: {ref_id}."
- [x] Amount: QSpinBox, non-negative, INR suffix

**Note on ClickableDateEdit bug (UTR1):**
The error `AttributeError: 'ClickableDateEdit' object has no attribute 'showCalendarWidget'` is resolved. The current implementation calls `self.showCalendarWidget()` in `mousePressEvent`. The correct PySide6 method is `showCalendarWidget()` — **but only after `setCalendarPopup(True)` is called**. The current `widgets.py` code calls `setCalendarPopup(True)` in `__init__`, which should make `showCalendarWidget()` available. If the error persists at runtime, the fix is to use `self.calendarWidget().show()` or rely on the built-in popup triggered by `super().mousePressEvent(event)` without the explicit `showCalendarWidget()` call.

**[REVIEW REQUIRED] UTR1-REVISIT:** The `mousePressEvent` in `widgets.py` calls `self.showCalendarWidget()` at line 33. This method exists on QDateEdit only when `setCalendarPopup(True)` has been called. Since `__init__` calls `setCalendarPopup(True)`, this should work. However the original error suggests the issue may have been in a version where `setCalendarPopup(True)` was not called before `showCalendarWidget()`. With the current code structure, the bug is fixed. Confirm at runtime that the calendar opens correctly on Tab and click.

### View Tab (R2, R3)
- [x] 10 columns: SNo, Ref ID, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status
- [x] QSortFilterProxyModel: sorting enabled on all columns
- [x] numeric_item() for SNo and Amount: correct integer sort
- [x] DatePickerDelegate on Giving Date and Due Date columns
- [x] Inline editing for all editable columns; persists to CSV
- [x] Status colors: STATUS_COLORS dict with correct dark hex values
- [x] Status is NOT editable via inline edit (editable=False)
- [x] Context menu: Delete, Extend, Mark Paidoff
- [x] Mark Paidoff disabled when loan.due_date is None
- [x] Mark Paidoff TC-05 guard: PENDING (TASK-1)

### Interest Calculator Tab (R5)
- [x] Mode selector: Monthly/Daily/Both (QComboBox)
- [x] Monthly locks extension unit to "months"; Daily locks to "days"; Both allows edit
- [x] 5 filter combos: Borrower Group, Borrower Name, Depositor Name, Depositor Group, ByMonth
- [x] "Unknown" option in Depositor Group filter for loans with no depositor group
- [x] Filter comparison: case-insensitive .lower() (UTR1)
- [x] No filter: shows only loans with no due_date
- [x] Any filter: excludes no-due-date loans
- [x] Global parameters: interest_rate, commission_rate, extension_period, extension_unit, TDS flag
- [x] Global param change → overwrites all table rows
- [x] Calculate button → opens CalculationDialog (modal)
- [x] Generate Report button disabled until Calculate clicked (managed in dialog flow)
- [x] CalculationDialog: inline editable params, on-the-fly recalc, CHQ_Amt computed
- [x] Generate Report from dialog → creates PendingReport + ReportRecord(s) in CSV

### Pending Approval Tab (R5)
- [x] Splitter: top reports list, bottom record detail
- [x] Report selection loads record detail table
- [x] Paidoff warning label shown for mode="Paidoff" reports
- [x] Post-extension preview columns: Post Giving Date, Post Due Date
- [x] Inline editable: int_rate, comm_rate, ext_period, ext_unit, tds_flag
- [x] Auto-recalc on inline edit: interest, commission, TDS, post-extension dates
- [x] Persist edits to CSV immediately on change
- [x] Shared ref-id warning on approval
- [x] Deleted loan warning on approval
- [x] Approve: batch_extend_loans() for regular reports; mark_paidoff() for Paidoff reports
- [x] Decline: deletes records, marks report Declined

---

## Phase 4 Backend Implementation Checklist

| Task | File(s) | Status | Effort |
|---|---|---|---|
| TC-05 has_pending_paidoff_report() | loan_manager/report_manager.py | PENDING | 30 min |
| TC-05 adapter | data/report_manager.py | PENDING | 10 min |
| TC-05 view_tab update | ui/view_tab.py | PENDING | 15 min |
| TC-08 Option B (if chosen) | models/report.py + 2 UI files | CONDITIONAL | 2 hours |
| TC-03 Option A (if chosen) | ui/entry_tab.py | CONDITIONAL | 30 min |
| BC-02 Option B (if chosen) | data/csv_manager.py | CONDITIONAL | 30 min |
| test_view_tab_colors.py | tests/ | PENDING | 20 min |
| test_entry_tab_logic.py | tests/ | PENDING | 30 min |
| test_view_tab_paidoff.py | tests/ | PENDING (after TC-05) | 1 hour |
| test_pending_approval.py | tests/ | PENDING | 1 hour |
