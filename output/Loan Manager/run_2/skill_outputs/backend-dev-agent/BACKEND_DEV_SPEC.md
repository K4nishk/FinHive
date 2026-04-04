# Backend Dev: Implementation Spec — Loan Manager run_2
**Date:** 2026-04-03
**Run:** run_2 / Wave 2
**Author:** Backend Dev Agent
**Scope:** All change items are backend (service layer + desktop UI layer — single agent per desktop-app agent selection matrix)

---

## Backend Dev → Backend QA Sync: Loan Manager run_2

**Status:** Planning

**What I'm building:**
Seven change items for a PySide6 desktop loan management app. Changes span UI widget behaviour, a new interest report generation path on Paidoff, a filter ordering fix, a color palette update, a shared date picker widget, and an import date parsing fix.

**Service/module changes:**

| Module | Change |
|---|---|
| `ui/entry_tab.py` | CHG-01: setChecked(True) at init and reset_form |
| `ui/view_tab.py` | CHG-02: _generate_paidoff_report(); BUG-02: STATUS_COLORS; BUG-03: context menu verify |
| `ui/interest_calculator_tab.py` | BUG-01: filter capture/restore ordering |
| `ui/widgets/clickable_date_edit.py` | BUG-04: new ClickableDateEdit subclass |
| `ui/dialogs/paidoff_dialog.py` | BUG-04: replace QDateEdit with ClickableDateEdit |
| `ui/dialogs/extend_dialog.py` | BUG-04: replace QDateEdit if present |
| `data/import_service.py` | DOC-01: _parse_flexible_date() helper |

**Data model changes:** None (confirmed by DM agent)

**Error conditions to test:**
- CHG-02: loan.due_date is None → no report, WARNING log
- CHG-02: _generate_paidoff_report() raises Exception → loan write preserved, ERROR logged, QMessageBox shown
- DOC-01: invalid date string → _parse_flexible_date returns None → row skipped, WARNING logged

**Ready for QA review:** Yes

---

## Feature Implementation Plans

---

### CHG-01 — No Due Date Default Checked

**What was built:** Two-line fix to `entry_tab.py`. The `_no_due_date_cb` checkbox is set to `checked=True` at widget initialisation and in `_reset_form()`. The existing `_toggle_due_date()` slot automatically disables the due_date field when the checkbox is checked, so no additional logic is required.

**Files changed:**
- `ui/entry_tab.py` — line ~89: `setChecked(False)` → `setChecked(True)`
- `ui/entry_tab.py` — `_reset_form()`: same change

**Design decisions:**
- The toggle slot driven by `stateChanged` signal handles all downstream effects. The fix is purely at the two initialisation points.

**Open questions for Dev Lead:** None — straightforward fix per PD-R2-01.

---

### BUG-01 — Interest Calculator Filter Reset

**What was built:** `_on_apply_filters()` in `interest_calculator_tab.py` modified to capture all five combo box current values before calling `_load_loans()`, then restore them after reload.

**Implementation:**
```python
def _on_apply_filters(self) -> None:
    # Capture selections before _populate_filters() clears combos
    saved_bg = self._borrower_group_combo.currentText()
    saved_bn = self._borrower_name_combo.currentText()
    saved_dg = self._depositor_group_combo.currentText()
    saved_dn = self._depositor_name_combo.currentText()
    saved_status = self._status_combo.currentText()

    self._load_loans()  # internally calls _populate_filters() which clears all combos

    # Restore — setCurrentText("All") if value no longer present (no-op safety)
    self._borrower_group_combo.setCurrentText(saved_bg)
    self._borrower_name_combo.setCurrentText(saved_bn)
    self._depositor_group_combo.setCurrentText(saved_dg)
    self._depositor_name_combo.setCurrentText(saved_dn)
    self._status_combo.setCurrentText(saved_status)
```

**Note:** `setCurrentText()` is a no-op if the text is not found in the combo — it leaves the combo at its current index (which after `_populate_filters()` is index 0 = "All"). This provides the correct graceful fallback for deleted filter values.

**Design decisions:**
- Capture before reload: only reliable approach. Alternative of skipping `_populate_filters()` would prevent new values from appearing when data is refreshed.

---

### BUG-02 — View Tab Color Palette

**What was built:** `STATUS_COLORS` dict in `view_tab.py` updated to high-contrast dark palette. Row-coloring loop updated to set both `Qt.BackgroundRole` and `Qt.ForegroundRole`.

**Implementation:**
```python
from PySide6.QtGui import QBrush, QColor
from PySide6.QtCore import Qt

STATUS_COLORS = {
    "Active":  {"bg": "#2d6a4f", "fg": "#ffffff"},
    "Overdue": {"bg": "#9b2226", "fg": "#ffffff"},
    "Pending": {"bg": "#ca6702", "fg": "#ffffff"},
    "Paidoff": {"bg": "#495057", "fg": "#ffffff"},
}

# In row-coloring loop (wherever STATUS_COLORS is consumed):
status = loan.status  # or row_data["status"]
if status in STATUS_COLORS:
    colors = STATUS_COLORS[status]
    bg_brush = QBrush(QColor(colors["bg"]))
    fg_brush = QBrush(QColor(colors["fg"]))
    for item in row_items:
        item.setData(bg_brush, Qt.BackgroundRole)
        item.setData(fg_brush, Qt.ForegroundRole)
```

**Design decisions:**
- `setData(..., Qt.BackgroundRole)` is preferred over `setBackground()` to ensure role is set, not just visual background.
- White foreground (#ffffff) on all status colors ensures readability regardless of OS theme.

---

### BUG-03 — Paidoff Context Menu Verify

**Verification result:** The context menu path in `view_tab.py` creates a "Mark Paidoff" `QAction` and connects it to `self._action_paidoff`. No disconnection found. This item is a verification-only change. If BUG-02 (readable rows) is fixed, the right-click path becomes fully testable.

**No code change required** (barring inspection finding a disconnected signal, which was not found in source review).

---

### BUG-04 — Windows Date Picker Click Behavior

**What was built:** New `ClickableDateEdit` subclass + replacement of `QDateEdit` instances in three files.

**New file: `ui/widgets/clickable_date_edit.py`**
```python
"""ClickableDateEdit — QDateEdit subclass that opens the calendar popup on any mouse press.

On Windows, the default QDateEdit with setCalendarPopup(True) only opens the popup when the
dropdown arrow button is clicked. This subclass overrides mousePressEvent to open the popup
on any click in the field, improving usability across platforms.
"""
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QDateEdit


class ClickableDateEdit(QDateEdit):
    """Opens the calendar popup when the user clicks anywhere in the date field."""

    def mousePressEvent(self, event: QEvent) -> None:  # type: ignore[override]
        super().mousePressEvent(event)
        self.showPopup()
```

**Consumer changes:**
- `ui/entry_tab.py`: `from ui.widgets.clickable_date_edit import ClickableDateEdit` — replace both `QDateEdit(...)` instantiations
- `ui/dialogs/paidoff_dialog.py`: same import — replace `QDateEdit` for paidoff_date field
- `ui/dialogs/extend_dialog.py`: inspect for any `QDateEdit` — replace if present

**Design decisions:**
- `showPopup()` is idempotent (safe to call when popup is already open). No conditional guard needed.
- Placed in `ui/widgets/` to establish a shared widget layer — avoids duplication if more custom widgets are needed in Phase 4.

---

### CHG-02 — Paidoff Generates Daily Interest Report

**What was built:** New private method `_generate_paidoff_report(loan, paidoff_date)` in `view_tab.py`, called from `_action_paidoff()` after `mark_paidoff()` succeeds.

**New method:**
```python
def _generate_paidoff_report(self, loan: "Loan", paidoff_date: "date") -> None:
    """Generate a Daily interest report for a paidoff loan.

    Called after mark_paidoff() succeeds. Report generation is best-effort:
    failure does NOT rollback the Paidoff write (per PD-R2-02 / ADR-001).
    """
    from loan_manager.interest_calculator import calculate_daily
    from loan_manager.report_manager import (
        CSVReportManager,
        write_report,
        write_report_records,
    )
    from data.csv_manager import _data_dir

    if loan.due_date is None:
        logger.warning(
            "Paidoff report skipped for %s: loan has no due_date",
            loan.reference_id,
        )
        return

    extension_days = max(0, (paidoff_date - loan.due_date).days)

    record = {
        "reference_id": loan.reference_id,
        "borrower_name": loan.borrower_name,
        "amount": loan.amount,
        "extension_period": extension_days,
        "extension_period_unit": "days",
        "interest_rate": 12.0,    # TODO BC-05: use per-loan rate when available
        "commission_rate": 2.0,   # TODO BC-05: use per-loan rate when available
        "tds_flag": False,
        "mode": "Daily",
    }
    calc_result = calculate_daily(record)

    reports_meta_path = _data_dir() / "reports_meta.csv"
    report_id = CSVReportManager.generate_report_id(reports_meta_path, paidoff_date)

    report_row = {
        "report_id": report_id,
        "report_date": paidoff_date.isoformat(),
        "mode": "Daily",
        "status": "Pending",
    }
    write_report(report_row)
    write_report_records([{**record, **calc_result, "report_id": report_id}])

    logger.info(
        "Paidoff report %s generated for loan %s (extension=%d days, interest=%.2f)",
        report_id,
        loan.reference_id,
        extension_days,
        calc_result.get("interest_amount", 0),
    )
```

**Caller change in `_action_paidoff()`:**
```python
# After mark_paidoff(loan.reference_id, paidoff_date) succeeds:
try:
    self._generate_paidoff_report(loan, paidoff_date)
except Exception as exc:
    logger.error(
        "Paidoff report generation failed for %s: %s",
        loan.reference_id,
        exc,
        exc_info=True,
    )
    from PySide6.QtWidgets import QMessageBox
    QMessageBox.warning(
        self,
        "Report Generation Warning",
        f"Loan {loan.reference_id} was marked as Paidoff successfully.\n\n"
        f"The interest report could not be generated automatically:\n{exc}\n\n"
        "You can create the report manually using the Interest Calculator tab.",
    )
```

**Design decisions:**
- Import of `calculate_daily`, `CSVReportManager`, `write_report`, `write_report_records` from `loan_manager.*` is correct — these are the canonical injectable implementations. The `data/` shims wrap these for the app; either import path works here since ViewTab is in the UI layer and these are internal app calls.
- `TODO BC-05` comment marks the hardcoded rates for PO resolution.
- `exc_info=True` in the ERROR log ensures the full traceback is captured in the log file for diagnosis.

**Open questions:**
- BC-05: should `interest_rate` and `commission_rate` be collected from the user at Paidoff time? Currently using global defaults. Pending PO decision.

---

### DOC-01 — Import Parser DD-MM-YYYY

**What was built:** `_parse_flexible_date()` helper added to `import_service.py`. Both date fields in `_row_to_loan()` updated to use it.

**New helper:**
```python
def _parse_flexible_date(s: str) -> Optional[date]:
    """Parse a date string in YYYY-MM-DD (ISO 8601) or DD-MM-YYYY format.

    Returns None and logs a WARNING on parse failure.
    Storage remains ISO 8601 regardless of input format (per R8).
    """
    s = s.strip()
    if not s:
        return None
    # ISO 8601 first — canonical internal format, backward compatible
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    # DD-MM-YYYY — sample input documentation format
    try:
        from datetime import datetime
        return datetime.strptime(s, "%d-%m-%Y").date()
    except ValueError:
        logger.warning("Cannot parse date %r — expected YYYY-MM-DD or DD-MM-YYYY", s)
        return None
```

**Updated `_row_to_loan()` lines:**
```python
giving_raw = (row.get("giving_date") or "").strip()
due_raw = (row.get("due_date") or "").strip()

giving_date_val = _parse_flexible_date(giving_raw)
if giving_date_val is None:
    # giving_date is required — treat as parse failure, return None → row skipped
    logger.warning("Invalid giving_date in row %s — skipping", row)
    return None

return Loan(
    reference_id=ref_id,
    borrower_name=(row.get("borrower_name") or "").strip(),
    borrower_group=(row.get("borrower_group") or "").strip() or None,
    amount=int((row.get("amount") or "0").strip()),
    giving_date=giving_date_val,
    depositor_name=(row.get("depositor_name") or "").strip() or None,
    depositor_group=(row.get("depositor_group") or "").strip() or None,
    due_date=_parse_flexible_date(due_raw) if due_raw else None,
    status=(row.get("status") or "Active").strip() or "Active",
)
```

**Design decisions:**
- Explicit `None` check on `giving_date_val` rather than relying on the downstream `Loan()` constructor to fail — this produces a cleaner WARNING log message.
- `due_date` remains optional — `None` is valid and is the "No Due Date" state.
- `datetime` import placed locally in the fallback branch to avoid importing `datetime` at module top level for a fallback path (minor; can be moved to top if preferred by code reviewer).

---

## Backend Dev Code Review Items for Dev Lead

| Snippet | Status | Notes |
|---|---|---|
| `_generate_paidoff_report()` — import paths | Needs Dev Lead review | Confirm `loan_manager.*` vs `data.*` import preference for view_tab.py callers |
| `_generate_paidoff_report()` — `calculate_daily()` input dict shape | Needs Dev Lead review | Confirm all required keys are present in the record dict |
| `_parse_flexible_date()` — `datetime` local import | Needs Dev Lead review | Suggest moving to module-level import for consistency |
| `ClickableDateEdit` — `QEvent` type hint override | Low priority | `type: ignore[override]` comment needed due to PySide6 stubs — confirm acceptable |
