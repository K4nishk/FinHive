# Dev Lead: Implementation Plan — Loan Manager run_4
**Date:** 2026-04-04
**Run:** run_4 (Phase 3 Closure)
**Agent:** dev-lead-agent (Wave 2)
**DM contract:** Confirmed — zero schema changes required
**SRE reliability review:** Reviewed — BUG-UTR-2 Fix B and BUG-UTR-3 Refresh log are SRE-mandated
**Frontend agents:** Not applicable — PySide6 desktop app

---

## Scope Summary

| ID | File(s) | Priority | Effort |
|---|---|---|---|
| BUG-UTR-1 | ui/interest_calculator_tab.py | P1 | 0.5 day |
| BUG-UTR-2 | data/ref_id_manager.py + loan_manager/ref_id_manager.py | P1 | 1 day |
| BUG-UTR-3 | ui/view_tab.py | P1 | 0.5 day |
| BUG-UTR-4 | ui/widgets.py (NEW) + ui/entry_tab.py + ui/dialogs/paidoff_dialog.py | P2 | 0.5 day |
| BC-301 | ui/pending_approval_tab.py | LOW | 0.5 day |
| CHG-02-EXT | ui/dialogs/paidoff_dialog.py + ui/view_tab.py | P2 | 1 day |

**Total estimated effort:** 4 days
**Test baseline to preserve:** 197 tests passing (confirmed pre-run)

---

## TASK 1 — BUG-UTR-1: Interest Calculator Filter Reset

**File:** `ui/interest_calculator_tab.py`
**Method:** `_on_apply_filters()` (line 264)

**Root cause confirmed from source:**
`_on_apply_filters()` calls `self._load_loans()` → `self._populate_filters()` which calls `combo.clear()` on all four named filter combos via `_reset_combo()`. `_get_filtered_loans()` then reads `currentText()` from the now-cleared combos — all returning "All" — so every filter application is effectively a no-filter.

**Exact fix — replace `_on_apply_filters()` body:**

```python
def _on_apply_filters(self) -> None:
    """Apply current filter selections and populate the records table."""
    # Capture filter values BEFORE _load_loans() clears the combos
    bg = self._filter_borrower_group.currentText()
    bn = self._filter_borrower_name.currentText()
    dn = self._filter_depositor_name.currentText()
    dg = self._filter_depositor_group.currentText()
    mo = self._filter_by_month.currentText()

    self._load_loans()  # clears combos via _populate_filters()

    # Restore captured values so _get_filtered_loans() reads them correctly
    self._filter_borrower_group.setCurrentText(bg)
    self._filter_borrower_name.setCurrentText(bn)
    self._filter_depositor_name.setCurrentText(dn)
    self._filter_depositor_group.setCurrentText(dg)
    self._filter_by_month.setCurrentText(mo)

    self._filtered_loans = self._get_filtered_loans()
    self._populate_table(self._filtered_loans)
    self._calculated = False
    self._btn_generate.setEnabled(False)
```

**Preservation constraint:** `_populate_filters()` must NOT be removed or bypassed — it correctly refreshes combo contents on initial tab load and on new data. The fix is ordering only.

**Edge case:** If a previously selected filter value no longer exists in the combo after reload (loan deleted), `setCurrentText()` silently falls back to "All" — acceptable behaviour, consistent with user expectations.

**Test coverage target:** 2 unit tests (filter retained after apply; filter resets to All when value no longer exists).

---

## TASK 2 — BUG-UTR-2: Duplicate Reference IDs

Two independent sub-fixes. Both must ship together.

### Fix A — `data/ref_id_manager.py` `_active_year_months()`

**Current code (line 28):**
```python
ym = f"{loan.giving_date.year:04d}_{loan.giving_date.month:02d}"
```

**Problem:** Uses `giving_date` as the year_month bucket source. A back-dated loan entered in April 2026 with giving_date in March 2026 is bucketed as 2026_03. When the next April 2026 entry is made, `_active_year_months()` does not find 2026_04, calls `reset_counter(2026, 4)`, and the next loan gets 2026_04_001 — a duplicate.

**Exact fix — replace the `_active_year_months()` function body:**

```python
def _active_year_months() -> set:
    """Return the set of YYYY_MM strings that currently have any loan records.

    Derives YYYY_MM from the reference_id field (first two underscore-separated
    segments), not from giving_date. This correctly maps each loan to its entry
    month, not its giving month.
    """
    loans = read_all_loans_including_paidoff()
    ym_set = set()
    for loan in loans:
        parts = loan.reference_id.split("_")
        if len(parts) >= 2:
            ym = f"{parts[0]}_{parts[1]}"
            ym_set.add(ym)
    return ym_set
```

**Guard:** Skip loans with malformed reference_ids (fewer than 2 underscore-separated segments). Such records are from imports with non-standard IDs — they should not corrupt the counter.

**Note on history.csv scope:** `read_all_loans_including_paidoff()` reads loans.csv only (including Paidoff-status rows not yet archived). It does NOT read history.csv. DM flagged SA-401 — months where all loans are archived to history.csv will have zero rows in loans.csv, causing incorrect counter reset. This is a known gap; resolution deferred to Phase 4 unless the user confirms history.csv must be included. See [REVIEW REQUIRED — SA-401] at end of this plan.

### Fix B — `loan_manager/ref_id_manager.py` `_write_meta()`

**Current code (lines 105-115):**
```python
def _write_meta(self, meta: Dict[str, int]) -> None:
    self._meta_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [...]
    with self._meta_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_META_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
```

**Problem:** `open("w")` truncates the file immediately. Windows crash between truncation and writerows completion leaves loans_meta.csv with header only — all counters lost — causing duplicate IDs on next startup.

**Exact fix — replace `_write_meta()` body:**

```python
def _write_meta(self, meta: Dict[str, int]) -> None:
    """Atomically overwrite loans_meta.csv via write-to-temp + rename.

    Uses pathlib.Path.replace() which maps to os.replace():
    - POSIX: rename(2) syscall — atomic
    - Windows NTFS: MoveFileEx with MOVEFILE_REPLACE_EXISTING — atomic
    If the process crashes before replace(), the original file is intact.
    """
    self._meta_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = self._meta_path.with_suffix(".tmp")
    rows = [
        {"year_month": ym, "counter": str(order)}
        for ym, order in sorted(meta.items())
    ]
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_META_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(self._meta_path)
```

**Test coverage target:** 3 unit tests — (1) atomic write produces correct content; (2) orphaned .tmp on startup does not block next write; (3) 10 consecutive rapid `next_ref_id()` calls produce unique sequential IDs with no duplicates.

---

## TASK 3 — BUG-UTR-3: View Tab Refresh Overwrites All Records

**File:** `ui/view_tab.py`
**Method:** `load_data()` (line 135)

**Root cause confirmed from source (lines 135-149):**
```python
loans = recompute_all(loans, date.today())
for loan in loans:
    update_loan(loan)   # full CSV rewrite per loan — always, even if status unchanged
```

**Critical implementation note — mutation behaviour confirmed:**
From `loan_manager/status_engine.py` `recompute_all()` (lines 95-103): for Loan dataclass objects, `loan.status = new_status` mutates the object IN PLACE and returns the same object in the result list. The snapshot must therefore be taken from the loan list BEFORE `recompute_all()` is called, capturing the pre-mutation status values.

**Exact fix — replace `load_data()` body:**

```python
def load_data(self) -> None:
    """Reload loans from CSV, recompute status, persist only changed statuses."""
    try:
        loans = read_loans()
        # Snapshot status BEFORE recompute_all() mutates Loan objects in place
        snapshot = {loan.reference_id: loan.status for loan in loans}
        loans = recompute_all(loans, date.today())
        # Only write loans whose status genuinely changed
        changed = [l for l in loans if l.status != snapshot.get(l.reference_id)]
        for loan in changed:
            update_loan(loan)
        # SRE-mandated log line for operational verification
        if changed:
            logger.info("Refresh: %d loan(s) status changed — persisted", len(changed))
        else:
            logger.debug("Refresh: no status changes — skipping all writes")
    except Exception as exc:
        logger.error("Failed to load loans: %s", exc)
        QMessageBox.critical(self, "Error", f"Could not load loan data: {exc}")
        return

    self._loans = loans
    self._populate_model()
```

**Test coverage target:** 2 unit/integration tests — (1) Refresh with no status changes emits zero `update_loan()` calls; (2) Refresh where one loan transitions Active→Overdue emits exactly one `update_loan()` call for that loan.

---

## TASK 4 — BUG-UTR-4: ClickableDateEdit Widget

**New file:** `ui/widgets.py`
**Modified files:** `ui/entry_tab.py`, `ui/dialogs/paidoff_dialog.py`

### Step 4a — Create `ui/widgets.py`

```python
"""Shared custom PySide6 widgets (ADR-005)."""
from PySide6.QtWidgets import QDateEdit


class ClickableDateEdit(QDateEdit):
    """QDateEdit subclass that opens the calendar popup on any mouse click.

    Addresses BUG-UTR-4: the default QDateEdit only triggers the calendar
    popup when the small dropdown arrow on the right edge is clicked.
    Overriding mousePressEvent ensures the calendar opens on any click
    within the field area.

    setCalendarPopup(True) is called in __init__ so this widget is
    self-contained — callers do not need to call it separately.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(True)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self.showCalendarWidget()
```

### Step 4b — Update `ui/entry_tab.py`

**Import change:** Replace `QDateEdit` import with `ClickableDateEdit`:
```python
# Remove QDateEdit from PySide6.QtWidgets import list
# Add:
from ui.widgets import ClickableDateEdit
```

**Line 71 — giving_date field:**
```python
# Before:
self._giving_date = QDateEdit()
self._giving_date.setCalendarPopup(True)
# After:
self._giving_date = ClickableDateEdit()
# Remove the setCalendarPopup(True) call — ClickableDateEdit sets it in __init__
```

**Line 82 — due_date field:**
```python
# Before:
self._due_date = QDateEdit()
self._due_date.setCalendarPopup(True)
# After:
self._due_date = ClickableDateEdit()
# Remove the setCalendarPopup(True) call
```

### Step 4c — Update `ui/dialogs/paidoff_dialog.py`

**Import change:** Replace `QDateEdit` with `ClickableDateEdit`:
```python
# Remove QDateEdit from PySide6.QtWidgets import
# Add:
from ui.widgets import ClickableDateEdit
```

**Line 49 — date_edit field:**
```python
# Before:
self._date_edit = QDateEdit()
self._date_edit.setCalendarPopup(True)
# After:
self._date_edit = ClickableDateEdit()
# Remove setCalendarPopup(True) — self-contained in ClickableDateEdit
```

**Cross-platform note:** `mousePressEvent` + `showCalendarWidget()` is pure Qt — no platform-specific code path. Behaviour must be verified on both Windows and Mac per User-Testing Req 1 constraint.

**Test coverage target:** Manual test on Windows and Mac — single click opens calendar popup on giving_date, due_date, and paidoff_date fields.

---

## TASK 5 — BC-301: Paidoff Warning Label in Pending Approval Tab

**File:** `ui/pending_approval_tab.py`

**Layout confirmed from source (lines 170-205):**
```
bottom_widget (QWidget)
  bottom_layout (QVBoxLayout)
    detail_header (QHBoxLayout)   — Approve/Decline buttons
    [INSERT HERE]                  — warning label position
    self._rec_table (QTableWidget) — records table
```

### Step 5a — `_build_ui()`: Insert warning label

Insert after `bottom_layout.addLayout(detail_header)` (line 190) and before `bottom_layout.addWidget(self._rec_table)` (line 202):

```python
# BC-301: Paidoff warning label — hidden by default, shown for mode="Paidoff" reports
self._paidoff_warning = QLabel(
    "This report was generated for a Paidoff loan. "
    "The loan has been moved to history. No extension was applied."
)
self._paidoff_warning.setWordWrap(True)
self._paidoff_warning.setStyleSheet(
    "background-color: #ca6702; color: white; padding: 6px; font-weight: bold;"
)
self._paidoff_warning.setVisible(False)
bottom_layout.addWidget(self._paidoff_warning)
```

**Import addition required:** `QLabel` is already imported (line 38 of source — confirmed).

### Step 5b — `_on_report_selection_changed()`: Toggle visibility

In `_on_report_selection_changed()` (line 258), after `self._populate_record_table(records)` at end of the method body, add:

```python
# BC-301: Show warning only for Paidoff-mode reports
report = next(
    (r for r in self._reports if r.report_id == self._selected_report_id),
    None,
)
self._paidoff_warning.setVisible(
    report is not None and report.mode == "Paidoff"
)
```

Also add `self._paidoff_warning.setVisible(False)` in the early-return branch (line 261-266 where `not selected_rows`) to ensure the label is hidden when no report is selected.

**Test coverage target:** 2 manual tests — (1) Paidoff-mode report selected → warning visible; (2) Monthly/Daily report selected → warning hidden.

---

## TASK 6 — CHG-02-EXT: PaidoffDialog Rate Fields + Report Pipeline

Two sub-tasks: extend the dialog, then wire the caller.

### Step 6a — Extend `ui/dialogs/paidoff_dialog.py`

**New imports to add:**
```python
from PySide6.QtWidgets import (
    QCheckBox,          # tds_flag
    QDoubleSpinBox,     # interest_rate, commission_rate
    QFormLayout,        # form layout for new fields
    ...existing imports...
)
```

**New instance variables initialised in `__init__`:**
```python
self._interest_rate_val: float = 12.0
self._commission_rate_val: float = 2.0
self._tds_flag_val: bool = False
```

**New fields in `_build_ui()` — insert after the date_edit block, before the buttons:**

```python
form = QFormLayout()

self._interest_rate_spin = QDoubleSpinBox()
self._interest_rate_spin.setRange(0.0, 100.0)
self._interest_rate_spin.setDecimals(2)
self._interest_rate_spin.setValue(12.0)
self._interest_rate_spin.setSuffix(" %")
form.addRow("Interest Rate:", self._interest_rate_spin)

self._commission_rate_spin = QDoubleSpinBox()
self._commission_rate_spin.setRange(0.0, 100.0)
self._commission_rate_spin.setDecimals(2)
self._commission_rate_spin.setValue(2.0)
self._commission_rate_spin.setSuffix(" %")
form.addRow("Commission Rate:", self._commission_rate_spin)

self._tds_checkbox = QCheckBox("Apply TDS (10% of Interest)")
self._tds_checkbox.setChecked(False)
form.addRow("TDS:", self._tds_checkbox)

layout.addLayout(form)
```

**Update `_on_accept()` to capture new values:**
```python
def _on_accept(self) -> None:
    q = self._date_edit.date()
    self._paidoff_date = date(q.year(), q.month(), q.day())
    self._interest_rate_val = self._interest_rate_spin.value()
    self._commission_rate_val = self._commission_rate_spin.value()
    self._tds_flag_val = self._tds_checkbox.isChecked()
    logger.debug(
        "Paidoff confirmed: date=%s ir=%.2f cr=%.2f tds=%s",
        self._paidoff_date, self._interest_rate_val,
        self._commission_rate_val, self._tds_flag_val,
    )
    self.accept()
```

**New getter methods:**
```python
def interest_rate(self) -> float:
    """Return the entered interest rate percentage."""
    return self._interest_rate_val

def commission_rate(self) -> float:
    """Return the entered commission rate percentage."""
    return self._commission_rate_val

def tds_flag(self) -> bool:
    """Return whether TDS is applied."""
    return self._tds_flag_val
```

### Step 6b — Update `ui/view_tab.py` `_action_paidoff()`

**Confirmed imports already present in view_tab.py:**
- `mark_paidoff` from `data.csv_manager` — confirmed (line 350)
- `PaidoffDialog` from `ui.dialogs.paidoff_dialog` — confirmed (line 346)

**New imports to add to view_tab.py:**
```python
from datetime import datetime
from data.report_manager import generate_report_id, write_report, write_report_records
from models.report import PendingReport, ReportRecord
```

**Replace `_action_paidoff()` body:**

```python
def _action_paidoff(self, loan: Loan) -> None:
    dialog = PaidoffDialog(loan.reference_id, parent=self)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return
    try:
        paidoff_date = dialog.paidoff_date()
        interest_rate = dialog.interest_rate()
        commission_rate = dialog.commission_rate()
        tds_flag = dialog.tds_flag()

        # Step 1: archive loan (existing, with recovery.tmp crash safety)
        mark_paidoff(loan.reference_id, paidoff_date)
        logger.info("Loan marked paidoff: %s", loan.reference_id)

        # Step 2: compute extension period (TC-401: 0 if no due_date)
        if loan.due_date is not None:
            extension_period = (paidoff_date - loan.due_date).days
        else:
            extension_period = 0
            logger.debug(
                "Paidoff report for %s: no due_date, extension_period=0",
                loan.reference_id,
            )

        # Step 3: compute interest amounts
        if extension_period > 0:
            interest_amount = (
                loan.amount * interest_rate * extension_period
            ) / (365 * 100)
            commission_amount = (
                loan.amount * commission_rate * extension_period
            ) / (365 * 100)
        else:
            interest_amount = 0.0
            commission_amount = 0.0

        tds_amount = round(0.1 * interest_amount, 4) if tds_flag else 0.0
        interest_amount = round(interest_amount, 4)
        commission_amount = round(commission_amount, 4)

        # Step 4: generate report and send to Pending Approval queue
        try:
            today = date.today()
            report_id = generate_report_id(today)
            now = datetime.now()

            report = PendingReport(
                report_id=report_id,
                report_creation_date=today,
                report_latest_update_dt=now,
                mode="Paidoff",
                status="Pending",
            )
            write_report(report)

            record = ReportRecord(
                report_id=report_id,
                reference_id=loan.reference_id,
                borrower_name=loan.borrower_name,
                amount=loan.amount,
                depositor_name=loan.depositor_name,
                giving_date=loan.giving_date,
                due_date=loan.due_date,
                interest_rate=interest_rate,
                commission_rate=commission_rate,
                extension_period=extension_period,
                extension_period_unit="days",
                tds_flag=tds_flag,
                new_giving_date=None,   # no extension for Paidoff
                new_due_date=None,
                interest_amount=interest_amount,
                commission_amount=commission_amount,
                tds_amount=tds_amount,
            )
            write_report_records([record])
            logger.info(
                "Paidoff report generated: %s for loan %s",
                report_id, loan.reference_id,
            )
        except Exception as report_exc:
            # Report generation failure does NOT undo the paidoff archival.
            # Log error and notify user — loan is safely in history.csv.
            logger.error(
                "Paidoff report generation failed for %s: %s",
                loan.reference_id, report_exc,
            )
            QMessageBox.warning(
                self,
                "Report Generation Failed",
                f"Loan {loan.reference_id} has been marked as Paidoff "
                f"and moved to history.\n\n"
                f"However, the interest report could not be generated: "
                f"{report_exc}\n\n"
                f"You can manually generate the report from the Interest "
                f"Calculator Tab.",
            )

        self.data_changed.emit()
    except Exception as exc:
        logger.error("Failed to mark paidoff %s: %s", loan.reference_id, exc)
        QMessageBox.critical(
            self, "Error", f"Could not mark loan as Paidoff: {exc}"
        )
    finally:
        self.load_data()
```

**Test coverage target:** 3 tests — (1) Dialog collects all 4 fields and getters return correct values; (2) Report with mode="Paidoff" appears in Pending Approval after action; (3) No-due-date loan produces extension_period=0, interest=0 in report record.

---

## QA Lead KT Package

**What was built:**
Six targeted fixes for Phase 3 closure. Five are logic/UI fixes to existing methods; one adds a new shared widget class (`ui/widgets.py`). No schema changes. No new dependencies. All fixes are additive — no existing public API signatures were removed.

**Backend changes (service/data layer):**
- `data/ref_id_manager.py` `_active_year_months()`: bucket derivation changed from giving_date to reference_id
- `loan_manager/ref_id_manager.py` `_write_meta()`: write path changed to atomic temp+rename

**UI changes:**
- `ui/interest_calculator_tab.py` `_on_apply_filters()`: filter capture order fix
- `ui/view_tab.py` `load_data()`: status snapshot + conditional write + SRE log line
- `ui/widgets.py` (NEW): `ClickableDateEdit` subclass
- `ui/entry_tab.py`: `QDateEdit` → `ClickableDateEdit` (giving_date, due_date)
- `ui/dialogs/paidoff_dialog.py`: `QDateEdit` → `ClickableDateEdit` + 3 new input fields + 3 new getters
- `ui/pending_approval_tab.py`: new `_paidoff_warning` QLabel + visibility toggle
- `ui/view_tab.py` `_action_paidoff()`: extended to collect rate fields and generate Paidoff report

**Happy paths to test:**
1. Select Borrower Group filter "bg1", click Apply Filters → table shows only bg1 loans; combo retains "bg1"
2. Enter 5 loans back-to-back → IDs are 2026_04_001 through 2026_04_005, no duplicates
3. Click Refresh in View Tab with no status changes → app.log shows "Refresh: no status changes"
4. Click anywhere on giving_date field in Entry Tab → calendar opens
5. Mark loan as Paidoff: enter rate fields → report appears in Pending Approval with mode="Paidoff"
6. Select Paidoff report in Pending Approval → warning label visible above records table

**Edge cases / known risks:**
- BUG-UTR-2: back-dated loans (giving_date in prior month) — counter bucket must use reference_id month
- BUG-UTR-3: snapshot must be taken before recompute_all() mutates Loan objects — order is critical
- CHG-02-EXT: report generation failure after paidoff archival — handled gracefully with user warning
- TC-401: Paidoff loan with no due_date → extension_period=0, interest=0 (PO default)
- BC-301: warning hidden when no report selected — guarded in selection change handler

**Out of scope for run_4:**
- R6 import/export (Phase 4)
- R9 alternate themes (Phase 4)
- Startup recovery.tmp detection (Phase 4 per SRE)
- history.csv inclusion in _active_year_months() (SA-401, deferred)

**Deployment notes:**
- No migration steps — zero schema changes
- No new pip dependencies — PySide6 QDoubleSpinBox, QCheckBox, QFormLayout are built-in
- Run test suite after implementation: `cd "src/Loan Manager" && python -m pytest tests/ -v`
- Baseline: 197 tests. Post-fix target: 197+ (new tests for BUG-UTR-2 and BUG-UTR-3 added)

---

## Open Items

### [REVIEW REQUIRED — SA-401]
**Item:** Should `_active_year_months()` include history.csv records?
**Impact:** If a month's last loan is paid off and archived to history.csv, that month has zero rows in loans.csv. The next entry for that month resets the counter to 001, potentially generating a reference_id that collides with an archived record in history.csv. `read_all_loans_including_paidoff()` currently reads loans.csv only.
**Options:** (a) extend `_active_year_months()` to also read history.csv; (b) accept that archived reference_ids can be reused.
**PO default:** Deferred to Phase 4 unless user confirms option (a) is required. Proceeding with current scope (loans.csv only).
