# Dev Lead: Implementation Plan — Loan Manager run_3
**Date:** 2026-04-03
**Run:** run_3 / Wave 2
**Author:** Dev Lead Agent
**Scope:** 2 change items (CHG-02-EXT, BUG-02-REF). BUG-03 removed. Priority doc section removed.

---

## 1. DM Contract and SRE Review Status

**DM contract received:** Yes — DATA_MODEL.md v3 confirms no schema changes. mode="Paidoff" adopted as reserved string (non-breaking). REPORT_RECORD_FIELDNAMES already contains interest_rate, commission_rate, tds_flag.

**SRE reliability review:** Received — 4 SRE conditions issued (SRE-R3-01 to SRE-R3-04). All conditions are dev-resolvable. No user input required for SRE items.

**SA architecture review:** Received — _generate_paidoff_report() signature change confirmed. mode="Paidoff" resolves TC-301.

**BSA requirements:** Received — FR-R3-01 to FR-R3-07 and FR-R6-01 to FR-R6-04 defined.

**Prior run open items check:** Run_2 open items BC-04 and BC-05 are now resolved by requirements update. BC-02 is resolved by exact hex codes. The hardcoded `interest_rate=12.0`, `commission_rate=2.0`, `tds_flag=False` in the run_2 pseudocode for `_generate_paidoff_report()` are superseded by CHG-02-EXT.

---

## 2. Implementation Decomposition

---

### CHG-02-EXT — Paidoff Dialog Extended + Report Warning

**DM contract:** No schema changes
**SRE conditions:** SRE-R3-01 (DEBUG log), SRE-R3-02 (range validation), SRE-R3-03 (passive warning)

#### Task 1: PaidoffDialog — Add 3 New Fields

**File:** `ui/dialogs/paidoff_dialog.py`

**Current state:** Dialog has 1 input field (QDateEdit for paidoff_date). Warning label, ref label, date label, and OK/Cancel buttons present.

**Change:**
- Add `QFormLayout` for the 3 new fields, inserted between the date edit and the buttons
- Add `QDoubleSpinBox` for `interest_rate`: range 0.0–100.0, step 0.5, decimals 2, suffix " %", default 0.0
- Add `QDoubleSpinBox` for `commission_rate`: range 0.0–100.0, step 0.5, decimals 2, suffix " %", default 0.0
- Add `QCheckBox` for `tds_flag`: label "Apply TDS", default unchecked (False)
- Add 3 accessor methods: `interest_rate() -> float`, `commission_rate() -> float`, `tds_flag() -> bool`

**Code contract (implementation spec):**

```python
# In __init__, store refs:
self._interest_rate_spin: QDoubleSpinBox
self._commission_rate_spin: QDoubleSpinBox
self._tds_flag_cb: QCheckBox

# In _build_ui(), after the date_label/date_edit block and before buttons:
form = QFormLayout()
self._interest_rate_spin = QDoubleSpinBox()
self._interest_rate_spin.setRange(0.0, 100.0)
self._interest_rate_spin.setSingleStep(0.5)
self._interest_rate_spin.setDecimals(2)
self._interest_rate_spin.setSuffix(" %")
self._interest_rate_spin.setValue(0.0)
form.addRow("Interest Rate:", self._interest_rate_spin)

self._commission_rate_spin = QDoubleSpinBox()
self._commission_rate_spin.setRange(0.0, 100.0)
self._commission_rate_spin.setSingleStep(0.5)
self._commission_rate_spin.setDecimals(2)
self._commission_rate_spin.setSuffix(" %")
self._commission_rate_spin.setValue(0.0)
form.addRow("Commission Rate:", self._commission_rate_spin)

self._tds_flag_cb = QCheckBox("Apply TDS")
self._tds_flag_cb.setChecked(False)
form.addRow("", self._tds_flag_cb)
layout.addLayout(form)

# New accessor methods:
def interest_rate(self) -> float:
    return self._interest_rate_spin.value()

def commission_rate(self) -> float:
    return self._commission_rate_spin.value()

def tds_flag(self) -> bool:
    return self._tds_flag_cb.isChecked()
```

**Imports to add:** `QDoubleSpinBox`, `QCheckBox`, `QFormLayout` from `PySide6.QtWidgets`

---

#### Task 2: view_tab.py — Update _action_paidoff() to Pass New Values

**File:** `ui/view_tab.py`

**Current state (from source, lines 345-357):**
```python
def _action_paidoff(self, loan: Loan) -> None:
    dialog = PaidoffDialog(loan.reference_id, parent=self)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    try:
        mark_paidoff(loan.reference_id, dialog.paidoff_date())
        logger.info("Loan marked paidoff: %s", loan.reference_id)
        self.data_changed.emit()
    except Exception as exc:
        logger.error("Failed to mark paidoff %s: %s", loan.reference_id, exc)
        QMessageBox.critical(self, "Error", f"Could not mark loan as Paidoff: {exc}")
    finally:
        self.load_data()
```

**Change:** After `mark_paidoff()` succeeds, call `_generate_paidoff_report()` with 3 additional parameters from dialog:

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
        self._generate_paidoff_report(loan, paidoff_date, interest_rate, commission_rate, tds_flag)
    except Exception as exc:
        logger.error("Failed to mark paidoff %s: %s", loan.reference_id, exc)
        QMessageBox.critical(self, "Error", f"Could not mark loan as Paidoff: {exc}")
    finally:
        self.load_data()
```

**Note:** `_generate_paidoff_report()` is called inside the try block AFTER mark_paidoff succeeds, consistent with the non-blocking report pattern from run_2.

---

#### Task 3: view_tab.py — Update _generate_paidoff_report() Signature and Body

**File:** `ui/view_tab.py`

This method was specified in run_2 pseudocode but may not yet be implemented in source (source review shows `_action_paidoff()` does not call it — it was a run_2 plan item). The backend-dev-agent is responsible for implementing it.

**Updated signature and implementation spec:**

```python
def _generate_paidoff_report(
    self,
    loan: Loan,
    paidoff_date: date,
    interest_rate: float,
    commission_rate: float,
    tds_flag: bool,
) -> None:
    """Generate a Daily interest report for a Paidoff loan.

    Non-blocking: errors are logged and shown as a warning — they do NOT
    rollback the Paidoff write. (SRE-R3-01, SRE-R3-02)
    """
    if loan.due_date is None:
        logger.warning("Paidoff report skipped for %s: no due_date", loan.reference_id)
        return
    # SRE-R3-02: range validation
    if not (0.0 <= interest_rate <= 100.0):
        logger.error("Invalid interest_rate %.2f for %s — report aborted", interest_rate, loan.reference_id)
        return
    if not (0.0 <= commission_rate <= 100.0):
        logger.error("Invalid commission_rate %.2f for %s — report aborted", commission_rate, loan.reference_id)
        return
    # SRE-R3-01: log params at DEBUG
    logger.debug(
        "Paidoff report params for %s: interest_rate=%.2f, commission_rate=%.2f, tds_flag=%s",
        loan.reference_id, interest_rate, commission_rate, tds_flag
    )
    try:
        extension_days = max(0, (paidoff_date - loan.due_date).days)
        record = {
            "reference_id": loan.reference_id,
            "borrower_name": loan.borrower_name,
            "amount": loan.amount,
            "depositor_name": loan.depositor_name,
            "giving_date": loan.giving_date,
            "due_date": loan.due_date,
            "extension_period": extension_days,
            "extension_period_unit": "days",
            "interest_rate": interest_rate,
            "commission_rate": commission_rate,
            "tds_flag": tds_flag,
        }
        from loan_manager.interest_calculator import calculate_daily
        calc_result = calculate_daily(record)

        from data.report_manager import generate_report_id, write_report, write_report_records
        report_date = paidoff_date
        report_id = generate_report_id(report_date)

        from models.report import PendingReport, ReportRecord
        from datetime import datetime
        report = PendingReport(
            report_id=report_id,
            report_creation_date=report_date,
            report_latest_update_dt=datetime.now(),
            mode="Paidoff",   # TC-301 resolution: reserved mode string
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
            new_giving_date=None,   # no extension for paidoff
            new_due_date=None,
            interest_amount=calc_result["interest_amount"],
            commission_amount=calc_result["commission_amount"],
            tds_amount=calc_result["tds_amount"],
        )
        write_report_records([report_record])
        logger.info("Paidoff report generated: %s for loan %s", report_id, loan.reference_id)
    except Exception as exc:
        logger.error("Paidoff report generation failed for %s: %s", loan.reference_id, exc)
        QMessageBox.warning(
            self,
            "Report Warning",
            f"Loan marked as Paidoff, but report generation failed: {exc}"
        )
```

**Import check:** `data/report_manager.py` must expose `generate_report_id`, `write_report`, `write_report_records` as module-level functions (adapter shims). Verify these exist in `data/report_manager.py` before implementation.

**[REVIEW REQUIRED — TC-302]:** Source code shows `data/` directory for CSV managers but `data/report_manager.py` existence is not confirmed from directory listing. The `loan_manager/report_manager.py` exists (read confirmed). Backend-dev-agent must verify whether `data/report_manager.py` (adapter shim) exists, and if not, either create it or import directly from `loan_manager/report_manager.py` with injectable paths. This is a real code verification step — not an assumption.

---

#### Task 4: pending_approval_tab.py — Paidoff Warning Message Display

**File:** `ui/pending_approval_tab.py`

**Change:** When a report with `mode="Paidoff"` is selected in the Pending Approval Tab, display the warning message as a `QLabel` that is shown/hidden based on selection.

**Recommended location:** Below the report header info (report_id, date, status) and above the records table, as a styled warning label (orange or amber background to match the Pending color theme — or system warning palette).

**Warning text (exact, from R3):**
```
"This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied."
```

**[REVIEW REQUIRED — BC-301]:** User to confirm placement (below report header vs other location). Implementation will default to below report header label. If user prefers a different location, this is a 1-line widget placement change.

**Implementation approach:**
- Add a `QLabel self._paidoff_warning_label` to the pending approval tab UI, initially hidden (`setVisible(False)`)
- When a report is selected and loaded, check `if report.mode == "Paidoff": self._paidoff_warning_label.setVisible(True)` else `setVisible(False)`

---

### BUG-02-REF — Exact Status Colors + White Foreground

**DM contract:** No schema impact
**SRE conditions:** SRE-R3-04 (test constant values)

#### Task 5: view_tab.py — Replace STATUS_COLORS and Add Foreground

**File:** `ui/view_tab.py`

**Current state (from source, lines 73-78):**
```python
STATUS_COLORS = {
    "Active": QColor("#d4edda"),
    "Overdue": QColor("#f8d7da"),
    "Pending": QColor("#fff3cd"),
    "Paidoff": QColor("#e2e3e5"),
}
```

**Change:**
```python
STATUS_COLORS = {
    "Active": QColor("#2d6a4f"),
    "Overdue": QColor("#9b2226"),
    "Pending": QColor("#ca6702"),
    "Paidoff": QColor("#495057"),
}

STATUS_TEXT_COLOR = QColor("#ffffff")
```

**Change in _make_row() item() and numeric_item() helpers:**

Current `item()` helper (line ~171):
```python
def item(text: str, editable: bool = True) -> QStandardItem:
    it = QStandardItem(text)
    it.setEditable(editable)
    it.setBackground(color)
    return it
```

Change to:
```python
def item(text: str, editable: bool = True) -> QStandardItem:
    it = QStandardItem(text)
    it.setEditable(editable)
    it.setBackground(color)
    it.setForeground(STATUS_TEXT_COLOR)
    return it
```

Same change applies to `numeric_item()` helper.

---

## 3. Interface Contracts

### PaidoffDialog New Public API

```python
class PaidoffDialog(QDialog):
    def paidoff_date(self) -> date: ...      # existing
    def interest_rate(self) -> float: ...    # NEW — returns QDoubleSpinBox.value()
    def commission_rate(self) -> float: ...  # NEW — returns QDoubleSpinBox.value()
    def tds_flag(self) -> bool: ...          # NEW — returns QCheckBox.isChecked()
```

### _generate_paidoff_report() Updated Signature

```python
def _generate_paidoff_report(
    self,
    loan: Loan,
    paidoff_date: date,
    interest_rate: float,      # NEW
    commission_rate: float,    # NEW
    tds_flag: bool,            # NEW
) -> None: ...
```

---

## 4. Code Reviewer Checklist

- [x] PaidoffDialog follows existing widget pattern (QVBoxLayout with nested QFormLayout for new fields)
- [x] No hardcoded defaults for interest_rate/commission_rate in _generate_paidoff_report()
- [x] SRE-R3-01: DEBUG log present for dialog-supplied params
- [x] SRE-R3-02: Range validation present in _generate_paidoff_report()
- [x] SRE-R3-03: Warning in Pending Approval Tab is passive label (not modal)
- [x] mode="Paidoff" used (DM ruling accepted) — no schema migration needed
- [x] STATUS_COLORS and STATUS_TEXT_COLOR use exact hex values from requirements
- [x] setForeground(STATUS_TEXT_COLOR) applied to both item() and numeric_item() helpers
- [x] No console.logs (Python print() calls) — only logger.* calls
- [x] PEP8 compliance expected

---

## 5. KT to QA Lead

### Dev Lead → QA Lead KT: CHG-02-EXT and BUG-02-REF

**What was built:**
CHG-02-EXT extends the PaidoffDialog to collect `interest_rate`, `commission_rate`, and `tds_flag` per paidoff event, replacing previously hardcoded defaults. BUG-02-REF replaces the STATUS_COLORS dict with the user-specified high-contrast hex values and adds explicit white foreground text to all status rows.

**Backend changes:**
- `ui/dialogs/paidoff_dialog.py`: 3 new fields + 3 new accessor methods
- `ui/view_tab.py`: _action_paidoff() reads new dialog values; _generate_paidoff_report() uses per-event params; STATUS_COLORS updated; STATUS_TEXT_COLOR added; setForeground applied
- `ui/pending_approval_tab.py`: Paidoff warning label added (mode=="Paidoff" detection)

**Happy paths to test:**
1. Right-click loan → Mark Paidoff → dialog shows 4 fields (date, interest_rate, commission_rate, TDS) → fill all → OK → loan archived, report in pending approval with correct values
2. Right-click loan → Mark Paidoff → dialog → Cancel → no action, loan remains in View Tab
3. View Tab loads → Active row has #2d6a4f background with white text
4. View Tab loads → Overdue row has #9b2226 background with white text
5. Paidoff report selected in Pending Approval → warning message visible

**Edge cases / known risks:**
- paidoff_date < due_date → extension_days=0 → interest=0.0 (verify report still generated)
- loan.due_date is None → WARNING logged, no report generated (no dialog shown for this — dialog still opens, just report is skipped post-accept)
- interest_rate=0.0, commission_rate=0.0 → report with all zero amounts → must still be written to pending_reports.csv

**Out of scope for run_3:**
- QComboBox StatusDelegate for Paidoff toggle (Phase 4)
- ClickableDateEdit for PaidoffDialog date picker (was in run_2 scope — verify if implemented)

**Deployment notes:**
- No CSV migration required
- No new dependencies
- Run tests with `pytest` from `/src/Loan Manager/` directory

---

## 6. Test Coverage Targets

| Module | Scenario | Coverage Target |
|---|---|---|
| `ui/dialogs/paidoff_dialog.py` | Default field values (date=today, rate=0.0, tds=False) | 100% accessors |
| `ui/dialogs/paidoff_dialog.py` | Non-default values set and retrieved | 100% accessors |
| `ui/view_tab.py` | STATUS_COLORS hex values correct | 4 assertions |
| `ui/view_tab.py` | STATUS_TEXT_COLOR = #ffffff | 1 assertion |
| `ui/view_tab.py` | _generate_paidoff_report() with loan.due_date=None | WARNING log, returns early |
| `ui/view_tab.py` | _generate_paidoff_report() extension_days calculation | Various paidoff_date scenarios |
| `loan_manager/interest_calculator.py` | calculate_daily() with dialog-supplied rates | Existing tests cover formula |

---

## 7. Dev Lead [REVIEW REQUIRED] Items

| ID | Item | Priority | Impact |
|---|---|---|---|
| TC-302 | Verify data/report_manager.py adapter shim exists (generate_report_id, write_report, write_report_records module-level functions) | High | Implementation will fail at import if shim does not exist |
| BC-301 | Paidoff warning placement in Pending Approval Tab | Medium | UX placement; defaulting to below report header |

