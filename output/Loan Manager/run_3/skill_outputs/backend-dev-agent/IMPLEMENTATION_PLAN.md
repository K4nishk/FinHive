# Backend Dev: Implementation Plan — Loan Manager run_3
**Date:** 2026-04-03
**Run:** run_3 / Wave 2
**Author:** Backend Developer Agent
**Scope:** Implementing CHG-02-EXT (PaidoffDialog + report generation) and BUG-02-REF (status colors)

---

## 1. Pre-Implementation Verification

### TC-302 Resolution
Confirmed: `data/report_manager.py` adapter shim exists with correct function signatures:
- `generate_report_id(report_date: date) -> str`
- `write_report(report: PendingReport) -> None`
- `write_report_records(records: list[ReportRecord]) -> None`

### Layer Architecture Verification
- UI layer (`ui/view_tab.py`, `ui/dialogs/paidoff_dialog.py`) may import from `data/` adapter layer only
- `data/report_manager.py` is the correct import source for report operations
- `loan_manager/interest_calculator.py` contains pure functions with no I/O — acceptable to import directly in UI (confirmed precedent: `interest_calculator_tab.py` already imports `calculate_daily` from `loan_manager.interest_calculator`)

### Existing _action_paidoff() Verification
Read from source (`ui/view_tab.py` lines 345-357): The method exists. Currently calls `mark_paidoff()` only. Does NOT yet call `_generate_paidoff_report()`. This is a run_2 plan item that was not yet implemented in source. Run_3 implements the full flow.

---

## 2. Implementation Specification

---

### IMPL-1: ui/dialogs/paidoff_dialog.py — Add 3 Fields

**Imports to add:**
```python
from PySide6.QtWidgets import (
    QCheckBox,      # ADD
    QDoubleSpinBox, # ADD
    QFormLayout,    # ADD
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)
```

**Class changes:**

Add instance variable declarations to `__init__`:
```python
self._interest_rate_spin: QDoubleSpinBox
self._commission_rate_spin: QDoubleSpinBox
self._tds_flag_cb: QCheckBox
```

**`_build_ui()` change — insert form block before buttons:**

After `layout.addWidget(self._date_edit)` and before `buttons = QDialogButtonBox(...)`:

```python
rate_form = QFormLayout()

self._interest_rate_spin = QDoubleSpinBox()
self._interest_rate_spin.setRange(0.0, 100.0)
self._interest_rate_spin.setSingleStep(0.5)
self._interest_rate_spin.setDecimals(2)
self._interest_rate_spin.setSuffix(" %")
self._interest_rate_spin.setValue(0.0)
rate_form.addRow("Interest Rate:", self._interest_rate_spin)

self._commission_rate_spin = QDoubleSpinBox()
self._commission_rate_spin.setRange(0.0, 100.0)
self._commission_rate_spin.setSingleStep(0.5)
self._commission_rate_spin.setDecimals(2)
self._commission_rate_spin.setSuffix(" %")
self._commission_rate_spin.setValue(0.0)
rate_form.addRow("Commission Rate:", self._commission_rate_spin)

self._tds_flag_cb = QCheckBox("Apply TDS")
self._tds_flag_cb.setChecked(False)
rate_form.addRow("", self._tds_flag_cb)

layout.addLayout(rate_form)
```

**New accessor methods (add below `paidoff_date()`):**
```python
def interest_rate(self) -> float:
    """Return the entered interest rate percentage."""
    return self._interest_rate_spin.value()

def commission_rate(self) -> float:
    """Return the entered commission rate percentage."""
    return self._commission_rate_spin.value()

def tds_flag(self) -> bool:
    """Return whether TDS should be applied."""
    return self._tds_flag_cb.isChecked()
```

**Minimum width:** Increase `self.setMinimumWidth(380)` to `self.setMinimumWidth(420)` to accommodate form layout labels without clipping.

---

### IMPL-2: ui/view_tab.py — Update _action_paidoff()

**Current (lines 345-357) must be replaced with:**

```python
def _action_paidoff(self, loan: Loan) -> None:
    dialog = PaidoffDialog(loan.reference_id, parent=self)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    paidoff_date = dialog.paidoff_date()
    interest_rate = dialog.interest_rate()
    commission_rate = dialog.commission_rate()
    tds_flag = dialog.tds_flag()
    try:
        mark_paidoff(loan.reference_id, paidoff_date)
        logger.info("Loan marked paidoff: %s", loan.reference_id)
        self.data_changed.emit()
        self._generate_paidoff_report(
            loan, paidoff_date, interest_rate, commission_rate, tds_flag
        )
    except Exception as exc:
        logger.error("Failed to mark paidoff %s: %s", loan.reference_id, exc)
        QMessageBox.critical(self, "Error", f"Could not mark loan as Paidoff: {exc}")
    finally:
        self.load_data()
```

---

### IMPL-3: ui/view_tab.py — Add _generate_paidoff_report()

**New imports required at top of `ui/view_tab.py`:**
```python
from loan_manager.interest_calculator import calculate_daily
from data.report_manager import generate_report_id, write_report, write_report_records
from models.report import PendingReport, ReportRecord
```

(Note: `datetime` is needed for `datetime.now()` — check if already imported. `date` is already imported.)

**Add import at top:**
```python
from datetime import date, datetime   # update if date is already imported alone
```

**New method added to ViewTab class (add after `_action_paidoff()`):**

```python
def _generate_paidoff_report(
    self,
    loan: Loan,
    paidoff_date: date,
    interest_rate: float,
    commission_rate: float,
    tds_flag: bool,
) -> None:
    """Generate a Daily interest report for a Paidoff loan and send to Pending Approval.

    This is non-blocking: exceptions are logged and shown as warnings.
    The Paidoff write (mark_paidoff) has already completed before this is called.
    SRE conditions: SRE-R3-01 (DEBUG log), SRE-R3-02 (range validation).
    """
    if loan.due_date is None:
        logger.warning(
            "Paidoff report skipped for %s: no due_date", loan.reference_id
        )
        return
    if not (0.0 <= interest_rate <= 100.0):
        logger.error(
            "Invalid interest_rate %.2f for %s — report aborted",
            interest_rate, loan.reference_id
        )
        return
    if not (0.0 <= commission_rate <= 100.0):
        logger.error(
            "Invalid commission_rate %.2f for %s — report aborted",
            commission_rate, loan.reference_id
        )
        return
    logger.debug(
        "Paidoff report params for %s: interest_rate=%.2f, commission_rate=%.2f, tds_flag=%s",
        loan.reference_id, interest_rate, commission_rate, tds_flag,
    )
    try:
        extension_days = max(0, (paidoff_date - loan.due_date).days)
        record = {
            "amount": loan.amount,
            "interest_rate": interest_rate,
            "commission_rate": commission_rate,
            "extension_period": extension_days,
            "tds_flag": tds_flag,
        }
        calc_result = calculate_daily(record)

        report_id = generate_report_id(paidoff_date)
        now = datetime.now()
        report = PendingReport(
            report_id=report_id,
            report_creation_date=paidoff_date,
            report_latest_update_dt=now,
            mode="Paidoff",
            status="Pending",
        )
        write_report(report)

        report_record = ReportRecord(
            report_id=report_id,
            reference_id=loan.reference_id,
            borrower_name=loan.borrower_name,
            amount=loan.amount,
            depositor_name=loan.depositor_name,
            giving_date=loan.giving_date,
            due_date=loan.due_date,
            interest_rate=interest_rate,
            commission_rate=commission_rate,
            extension_period=extension_days,
            extension_period_unit="days",
            tds_flag=tds_flag,
            new_giving_date=None,
            new_due_date=None,
            interest_amount=calc_result["interest_amount"],
            commission_amount=calc_result["commission_amount"],
            tds_amount=calc_result["tds_amount"],
        )
        write_report_records([report_record])
        logger.info(
            "Paidoff report generated: %s for loan %s", report_id, loan.reference_id
        )
    except Exception as exc:
        logger.error(
            "Paidoff report generation failed for %s: %s", loan.reference_id, exc
        )
        QMessageBox.warning(
            self,
            "Report Warning",
            f"Loan marked as Paidoff, but report generation failed:\n{exc}",
        )
```

---

### IMPL-4: ui/view_tab.py — STATUS_COLORS and Foreground Fix

**Replace lines 73-78:**
```python
STATUS_COLORS = {
    "Active": QColor("#d4edda"),
    "Overdue": QColor("#f8d7da"),
    "Pending": QColor("#fff3cd"),
    "Paidoff": QColor("#e2e3e5"),
}
```

**With:**
```python
STATUS_COLORS = {
    "Active": QColor("#2d6a4f"),
    "Overdue": QColor("#9b2226"),
    "Pending": QColor("#ca6702"),
    "Paidoff": QColor("#495057"),
}

STATUS_TEXT_COLOR = QColor("#ffffff")
```

**Update `item()` helper inside `_make_row()` (line ~171):**
```python
def item(text: str, editable: bool = True) -> QStandardItem:
    it = QStandardItem(text)
    it.setEditable(editable)
    it.setBackground(color)
    it.setForeground(STATUS_TEXT_COLOR)   # ADD THIS LINE
    return it
```

**Update `numeric_item()` helper inside `_make_row()` (line ~177):**
```python
def numeric_item(value: int, editable: bool = True) -> QStandardItem:
    it = QStandardItem()
    it.setData(value, Qt.ItemDataRole.DisplayRole)
    it.setEditable(editable)
    it.setBackground(color)
    it.setForeground(STATUS_TEXT_COLOR)   # ADD THIS LINE
    return it
```

---

### IMPL-5: ui/pending_approval_tab.py — Paidoff Warning Label

**Note:** `pending_approval_tab.py` has not been read in full. Backend dev must read the file to locate the correct insertion point for the warning label. The following is the implementation specification:

**Add to `__init__` (or widget build method):**
```python
self._paidoff_warning_label = QLabel(
    "This report was generated for a Paidoff loan. "
    "The loan has been moved to history. No extension was applied."
)
self._paidoff_warning_label.setWordWrap(True)
self._paidoff_warning_label.setStyleSheet(
    "background-color: #fff3cd; color: #856404; padding: 6px; border-radius: 4px;"
)
self._paidoff_warning_label.setVisible(False)
```

**In the report selection/display handler, add:**
```python
# When a report is loaded/selected:
is_paidoff = (selected_report.mode == "Paidoff")
self._paidoff_warning_label.setVisible(is_paidoff)
```

**Placement:** Insert the label widget above the report records table but below the report header (report_id, date, status display area). BC-301 placement pending user confirmation.

---

## 3. Backend Dev → Backend QA Sync

**Status:** Planning Complete

**What I'm building:**
- CHG-02-EXT: Extended PaidoffDialog with 3 new input fields; updated _action_paidoff() and new _generate_paidoff_report() in view_tab.py; paidoff warning label in pending_approval_tab.py
- BUG-02-REF: STATUS_COLORS updated to exact hex values; STATUS_TEXT_COLOR added; setForeground applied

**Data model changes:** None (mode="Paidoff" is a string value addition — confirmed non-breaking by DM)

**Key test hooks:**
- PaidoffDialog accessors: `interest_rate()`, `commission_rate()`, `tds_flag()` are pure property reads — easily testable
- `_generate_paidoff_report()` calls `calculate_daily()`, `write_report()`, `write_report_records()` — all monkeypatchable for unit tests
- STATUS_COLORS dict is a module-level constant — directly assertable in tests without a display

---

## 4. Backend Dev [REVIEW REQUIRED] Items

| ID | Item | Resolution Status |
|---|---|---|
| TC-302 | data/report_manager.py adapter shim existence | RESOLVED — shim confirmed, generate_report_id(report_date: date) signature verified |
| BC-301 | Paidoff warning label placement in pending_approval_tab.py | Open — defaulting to above records table; user to confirm |
| TC-303 | pending_approval_tab.py must be read before implementing IMPL-5 to locate correct insertion point for warning label | Dev action required — read file before coding |

