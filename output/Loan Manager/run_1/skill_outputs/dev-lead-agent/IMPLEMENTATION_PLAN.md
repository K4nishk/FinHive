# Development Lead — Implementation Plan
# Loan Manager Prototype | Run 1 | Wave 2
**Date:** 2026-04-03
**Branch:** development

---

## Part 1: User-Testing Requirement 1 — Bug Fix Plan (HIGHEST PRIORITY)

---

### Bug 1: Interest Calculator Filter Not Sticking (BorrowerGroup / BorrowerName / DepositorName / DepositorGroup reverts to "All")

**Root Cause:**

In `ui/interest_calculator_tab.py`, `_on_apply_filters()` at line 265 calls `self._load_loans()` first, which internally calls `_populate_filters()`. Inside `_populate_filters()` (line 250–262), all four affected combo boxes are cleared and repopulated using `blockSignals(True)` then `blockSignals(False)`. The problem is that `combo.clear()` followed by `combo.addItem("All")` resets the combo's current index to 0 ("All") before the previously-selected value is restored — and it is never restored. Because `_load_loans()` runs before the filter values are read, the `currentText()` calls in `_get_filtered_loans()` (line 274–278) read "All" for all four combos instead of the user's selection.

The ByMonth filter is not affected because `_filter_by_month` is not repopulated inside `_populate_filters()`.

**Fix Approach:**

Capture the user's current selections for all five filters before calling `_load_loans()` (which repopulates the combos), then restore those selections after `_populate_filters()` completes. The fix must happen in `_on_apply_filters()`:

1. Before calling `self._load_loans()`, snapshot the current text of all five filter combos into local variables.
2. After `_load_loans()` returns (which triggers `_populate_filters()`), restore each combo's selection using `setCurrentText(snapshot_value)` while `blockSignals` is True.
3. Then call `_get_filtered_loans()` which will now read the restored values.

Alternatively, decouple data reload from filter population: call `self._loans = read_loans()` directly in `_on_apply_filters()` (skip calling `_populate_filters()` on filter-apply), and move `_populate_filters()` to `showEvent()` only. This is the cleaner approach that avoids the snapshot-restore pattern.

**Files to Modify:**
- `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/ui/interest_calculator_tab.py`
  - Method: `_on_apply_filters()` — snapshot filter values before reload, or decouple reload from filter population
  - Method: `_load_loans()` — optionally split into `_reload_loan_data()` (data only) and `_refresh_filter_options()` (UI only)

**Test Scenario:**
1. Launch app. Navigate to Interest Calculator tab.
2. Wait for tab to load (loans are populated into filter combos).
3. Select "bg1" in the Borrower Group dropdown.
4. Click "Apply Filters".
5. Verify: Borrower Group filter still shows "bg1" after apply, and the table shows only loans with borrower_group == "bg1".
6. Repeat for BorrowerName, DepositorName, DepositorGroup filters.
7. Combine two filters (e.g., BorrowerGroup = "bg1" AND ByMonth = "April") and apply — verify both selections persist.

---

### Bug 2: View Tab Color Palette — Light Background + White Text = Poor Visibility

**Root Cause:**

In `ui/view_tab.py` at line 73–78, `STATUS_COLORS` is defined as:

```python
STATUS_COLORS = {
    "Active":  QColor("#d4edda"),   # very light green
    "Overdue": QColor("#f8d7da"),   # very light red/pink
    "Pending": QColor("#fff3cd"),   # very light yellow
    "Paidoff": QColor("#e2e3e5"),   # very light grey
}
```

These are Bootstrap-style alert background colors designed for use with dark text. However, `_make_row()` at line 168 sets `item.setBackground(color)` but does NOT set a foreground (text) color. Qt's default alternating row color or system theme on Windows may render text in white or near-white, making the light-pastel background and white text combination illegible.

Additionally, `setAlternatingRowColors(True)` at line 119 may interact unexpectedly with per-cell background colors on certain platforms.

**Fix Approach:**

Two changes are needed:
1. Explicitly set a dark foreground color on every status-colored item. Add a `QColor` constant for dark text (e.g., `QColor("#212529")`) and call `it.setForeground(dark_text)` inside the `item()` and `numeric_item()` inner functions in `_make_row()`.
2. Optionally replace the pastel background colors with higher-contrast alternatives that are visually distinct but still gentle enough for a business UI. Recommended replacements:
   - Active: `#1a7a3c` (dark green) with white text
   - Overdue: `#c0392b` (dark red) with white text
   - Pending: `#b7860b` (dark amber) with white text
   - Paidoff: `#5a6268` (medium grey) with white text

   OR keep the light backgrounds but always force black text:
   - STATUS_COLORS stays as light pastels
   - foreground always set to `QColor("#000000")`

The simpler fix (forcing black foreground) is lower risk. The improved contrast option is better UX. Both are valid — this is flagged as a preference decision.

[REVIEW REQUIRED] Which direction does the user prefer: (a) keep light pastel backgrounds with forced dark text, or (b) switch to dark/saturated backgrounds with white text?

**Files to Modify:**
- `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/ui/view_tab.py`
  - `STATUS_COLORS` dict — update color values
  - `_make_row()` — add `it.setForeground(text_color)` calls in both `item()` and `numeric_item()` inner functions

**Test Scenario:**
1. Load the app with sample data containing all four statuses (Active, Overdue, Pending, one Paidoff row if visible).
2. Navigate to View Tab.
3. Visually verify that text in all rows is clearly legible against the row's background color.
4. Test on both dark and light system themes (especially Windows default light theme).

---

### Bug 3: User Unable to Test Paidoff — Paidoff Flow Not Reachable

**Root Cause (multi-factor):**

After reviewing the source code, the Paidoff flow is architecturally complete (`PaidoffDialog` exists, `_action_paidoff()` exists in `view_tab.py`, `mark_paidoff()` exists in `data/csv_manager.py`). However, there are two plausible failure modes based on the user report:

**Factor A — Context menu not discoverable:** The "Mark Paidoff" option is only accessible via a right-click context menu on a row in the View Tab (line 297–299 in `view_tab.py`). There is no button, no Status column dropdown, and no keyboard shortcut. Users expect the Status column to be editable via `QComboBox` per the requirements ("User can toggle in between these states for any record in the tab. Leverage `QComboBox` for simplicity"). The Status column is currently marked `editable=False` (line 199) with no QComboBox delegate. The user likely tried clicking or double-clicking the Status cell, found it non-editable, and concluded Paidoff was unavailable.

**Factor B — R3 requirement gap:** R3 specifies that status transitions (including Paidoff) should be available via a `QComboBox` in the Status column. The current implementation deviates: "Mark Paidoff" lives only in the right-click context menu, not in the Status column. When the user toggles to Paidoff via a combo, a dialog for `paidoff_date` should appear. This Status-column-as-QComboBox delegate is not implemented.

**Fix Approach:**

Two complementary fixes:

**Fix 3A (Immediate / Low risk):** Add a "Mark Paidoff" button to the View Tab toolbar so the action is visible without requiring knowledge of the right-click context menu. The button should be enabled only when a row is selected, and should call the same `_action_paidoff()` logic.

**Fix 3B (Correct / R3 compliance):** Implement a `QStyledItemDelegate` for the Status column that presents a `QComboBox` on click. The combobox should list `["Active", "Overdue", "Pending", "Paidoff"]`. When the user selects "Paidoff", intercept in `_on_item_changed()` (or via a delegate commit signal), open `PaidoffDialog`, then call `mark_paidoff()`. When the user selects "Active" from a non-Active status, open `ExtendDialog` (per R3: "Manual Active override always prompts for a new due date, same as Extend"). This is the full R3-compliant fix but requires a custom delegate.

For the prototype bug fix, Fix 3A is the minimum viable change. Fix 3B is the correct long-term implementation.

**Files to Modify:**
- `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/ui/view_tab.py`
  - `_build_ui()` — add a "Mark Paidoff" QPushButton to the toolbar; connect to a new `_on_paidoff_btn_clicked()` slot
  - New method `_on_paidoff_btn_clicked()` — get selected row's loan, call `_action_paidoff(loan)`
  - New method `_on_selection_changed()` — enable/disable the Paidoff button based on row selection
  - [Fix 3B only] New class `StatusDelegate(QStyledItemDelegate)` — inside `view_tab.py` or new `ui/delegates/status_delegate.py`

**Test Scenario:**
1. Open app with sample data.
2. Navigate to View Tab.
3. Select a loan row (e.g., an Active loan).
4. Verify the "Mark Paidoff" button is enabled.
5. Click "Mark Paidoff". Verify `PaidoffDialog` opens showing the correct Reference ID.
6. Enter a paidoff date (e.g., today). Click OK.
7. Verify the row disappears from the View Tab.
8. Open `data/history.csv` and verify the row appears there with `paidoff_date` set.
9. Verify `data/loans.csv` no longer contains the row.
10. Restart the app. Verify the row is still absent from the View Tab (not re-added by startup recompute).

---

### Bug 4: Date Picker on Windows — Should Open on Click, Not via Dropdown Button

**Root Cause:**

`QDateEdit` with `setCalendarPopup(True)` renders a small dropdown arrow button on the right edge of the widget. On Windows, the calendar popup only opens when the user clicks that specific arrow button, not when they click the text area of the widget. This is the default Qt/Windows behavior for `QDateEdit` and is unintuitive compared to the user's expectation that clicking anywhere on the date field opens the calendar.

This affects:
- `ui/entry_tab.py` line 72–74 (`_giving_date`) and lines 82–85 (`_due_date`)
- `ui/dialogs/paidoff_dialog.py` line 49–52 (`_date_edit`)
- `ui/dialogs/extend_dialog.py` does NOT use `QDateEdit` — it uses spinboxes + preview label, so not affected

**Fix Approach:**

Create a `ClickableDateEdit` subclass of `QDateEdit` that overrides `mousePressEvent` to programmatically call `self.calendarWidget().show()` or trigger the popup via `QDateEdit`'s calendar display mechanism when any part of the widget is clicked. The correct Qt approach is:

```python
class ClickableDateEdit(QDateEdit):
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.calendarWidget()  # ensure calendar is initialized
        # Open the popup regardless of where the click lands
        # The cleanest approach: call showPopup() which is inherited from QAbstractSpinBox
        # but not exposed directly. Use the calendar popup approach:
```

The cleanest implementation: subclass `QDateEdit`, override `mousePressEvent`, and use `QApplication.sendEvent` with a synthetic click on the button, or use the `showPopup()` method that QAbstractSpinBox exposes. Note: `QDateEdit` inherits from `QAbstractSpinBox` which does have `showPopup()` but it is not documented as a calendar-specific popup. The reliable approach is:

```python
class ClickableDateEdit(QDateEdit):
    def mousePressEvent(self, event: QMouseEvent) -> None:
        super().mousePressEvent(event)
        if not self.calendarPopup():
            return
        # Force the calendar to open on any click
        # showPopup() is available but may not be the calendar popup
        # Safest: find and click the calendar button child
        for child in self.children():
            if hasattr(child, "click"):
                child.click()
                break
```

[REVIEW REQUIRED] The exact mechanism for forcing the QDateEdit calendar popup open from any click area is platform-sensitive. If the subclass approach does not work on the target Windows environment, the fallback is to use a `QToolButton` that shows a `QCalendarWidget` in a `QDialog`, replacing `QDateEdit` entirely. This is more work but fully reliable cross-platform.

**Files to Modify:**
- New file: `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/ui/widgets/clickable_date_edit.py` — `ClickableDateEdit` class
- `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/ui/entry_tab.py` — replace `QDateEdit(...)` instantiations for `_giving_date` and `_due_date` with `ClickableDateEdit(...)`
- `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/ui/dialogs/paidoff_dialog.py` — replace `QDateEdit(...)` for `_date_edit` with `ClickableDateEdit(...)`

**Test Scenario (Windows target):**
1. Launch the app on Windows.
2. Navigate to Entry Tab.
3. Click anywhere on the "Giving Date" field (on the text area, not on the arrow button).
4. Verify the calendar popup opens.
5. Select a date from the calendar.
6. Verify the date field updates.
7. Repeat steps 3–6 for "Due Date".
8. Navigate to View Tab. Right-click a row, select "Mark Paidoff". Click anywhere on the paidoff date field. Verify calendar opens.

---

## Part 2: Feature Implementation Plan by Requirement

Priority order: R5 > R4 > R1 > R2 > R3 > R6 > R8 > R7 > R10 > R9

---

## Dev Lead Decomposition: R5 — Interest Calculator

**Status:** Partially implemented

**What is implemented:**
- Monthly / Daily / Both modes with correct BC-05 formulas
- Global parameter panel (interest_rate, commission_rate, extension_period, extension_period_unit, TDS)
- Filter panel with five filters; filter logic in `_get_filtered_loans()`
- Table with inline-editable parameter cells; result columns populated on Calculate
- Summary row (total amount, interest, commission, TDS)
- Generate Report button (disabled until Calculate clicked)
- Report generation -> PendingReport + ReportRecord written to CSV
- PendingApprovalTab: approve/decline workflow, inline editing with auto-recalc, shared ref-id warning, deleted-loan warning, crash safety via `approval_recovery.tmp`

**What is NOT implemented / broken:**
- Bug 1 (filter revert) — see above
- Status column `QComboBox` delegate for Paidoff/Active toggle (R3, not R5, but impacts test flow)
- No "Unknown" blank option visible in Depositor Group filter when there are no-depositor loans (partially done: "Unknown" is added in `_populate_filters()` but only after `blockSignals` — verify this actually renders)
- R5 spec: "ByMonth filter shows records whose due_date is in the selected month for the CURRENT CALENDAR YEAR including Overdue records" — currently implemented at lines 321–328; confirm correct
- No "fill all rows / copy down" shortcut (deferred per R5)
- "Both" mode: per-record `extension_period_unit` is editable in table but the global extension_unit sets a single default — this is per spec; confirm both-mode per-record unit works end-to-end

**Backend Tasks:**
- [ ] No new backend tasks needed for R5 core logic — `interest_calculator.py` is complete

**Frontend/UI Tasks:**
- [ ] Fix Bug 1 (filter not sticking) — `ui/interest_calculator_tab.py`
- [ ] Verify "Unknown" option is visible in Depositor Group dropdown for records with no depositor — `ui/interest_calculator_tab.py` `_populate_filters()`
- [ ] Verify ByMonth filter correctly includes overdue records for the current year — `ui/interest_calculator_tab.py` `_get_filtered_loans()`
- [ ] Add `showEvent` reload validation — already done at line 634; verify it works when switching tabs with unsaved filter state

**Interface Contract:**
- `calculate_monthly(record: dict) -> dict` — in `loan_manager/interest_calculator.py`
- `calculate_daily(record: dict) -> dict`
- `calculate_both(record: dict) -> dict`
- `generate_report_id(report_date: date) -> str` — in `data/report_manager.py`
- `write_report(report: PendingReport) -> None`
- `write_report_records(records: list[ReportRecord]) -> None`

**Dependency Order:** Bug 1 fix first, then verify end-to-end filter -> calculate -> generate report -> pending approval -> approve flow

---

## Dev Lead Decomposition: R4 — Extend / Delete / Reference ID

**Status:** Implemented

**What is implemented:**
- `extend_loan(reference_id, new_giving_date, new_due_date)` in `data/csv_manager.py`
- `delete_loan(reference_id)` in `data/csv_manager.py` with eager counter reset
- `RefIdManager` class in `loan_manager/ref_id_manager.py` — next_ref_id, reset_counter
- `data/ref_id_manager.py` shim — `generate_ref_id(year, month)`
- `ExtendDialog` in `ui/dialogs/extend_dialog.py`
- Context menu in View Tab: Delete, Extend, Mark Paidoff
- Collision avoidance not explicitly implemented (legacy import scenario deferred per R6)

**What is NOT implemented:**
- Legacy import collision: when an imported record with a non-standard ref_id collides after auto-assignment, increment until non-colliding (R4 / R6 interaction) — low priority per user note
- `batch_extend_loans()` exists in `data/csv_manager.py` but delegates to `loan_manager/csv_manager.py` CSVManager — need to verify this module exists

**Backend Tasks:**
- [ ] Verify `loan_manager/csv_manager.py` exists and exports `CSVManager.batch_extend_loans()` — if missing, implement inline in `data/csv_manager.py` — `data/csv_manager.py`

**Frontend/UI Tasks:**
- [ ] No-due-date Extend: currently `ExtendDialog` sets `_base_date = date.today()` for no-due-date loans — confirm per R7 sample data: "new giving_date = today_date, due_date = new due date picked via date picker" — the current dialog uses spinbox period, not a date picker for due_date. [REVIEW REQUIRED] Should the no-due-date Extend show a QDateEdit for the new due date directly, rather than forcing the user to pick a period?

**Interface Contract:**
- `extend_loan(reference_id: str, new_giving_date: date, new_due_date: date) -> None`
- `delete_loan(reference_id: str) -> bool`
- `RefIdManager.next_ref_id(year: int, month: int) -> str`
- `RefIdManager.reset_counter(year: int, month: int) -> None`

**Dependency Order:** R4 is fully functional. Batch extend is used by R5 approval — validate that path end-to-end.

---

## Dev Lead Decomposition: R1 — Loan Entry

**Status:** Implemented

**What is implemented:**
- `EntryTab` with all required fields: Borrower Name, Borrower Group, Amount, Giving Date, Due Date (optional), Depositor Name, Depositor Group (optional)
- `QDateEdit` with `setCalendarPopup(True)` for Giving Date and Due Date
- "No Due Date" checkbox (default unchecked — note: R1 says "By default, No Due Date is checked"; this is a deviation)
- Amount as QSpinBox, INR suffix
- Autocomplete via QCompleter from existing CSV values
- Status bar message after save: "Loan saved successfully. Reference ID: {ref_id}"
- `write_loan()` persists to `./data/loans.csv`
- Status computed on entry via `compute_status()`

**What is NOT implemented / deviates:**
- R1 says "By default, No Due Date is checked" — current implementation line 89: `self._no_due_date_cb.setChecked(False)` (not checked by default). This is a bug.
- Bug 4 (date picker click-to-open on Windows) — see above

**Backend Tasks:**
- [ ] No backend changes needed for R1

**Frontend/UI Tasks:**
- [ ] Fix default checkbox state: `self._no_due_date_cb.setChecked(True)` and call `_on_no_due_date_toggled(True)` on init — `ui/entry_tab.py` line 89
- [ ] Fix Bug 4 (date picker) — see Bug 4 section above
- [ ] Trigger `_on_no_due_date_toggled` on construction to disable `_due_date` widget if default is checked — `ui/entry_tab.py` `_build_ui()`

**Interface Contract:**
- `write_loan(loan: Loan) -> None` — `data/csv_manager.py`
- `generate_ref_id(year: int, month: int) -> str` — `data/ref_id_manager.py`
- `compute_status(loan: Loan, today: date) -> str` — `data/status_engine.py`

**Dependency Order:** Bug 4 (widget) is prerequisite for good UX. Default checkbox fix is independent.

---

## Dev Lead Decomposition: R2 — View Tab

**Status:** Partially implemented

**What is implemented:**
- `ViewTab` with sortable QTableView using QSortFilterProxyModel
- All columns per spec: SNo, Ref ID, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status
- Sorting enabled on all columns
- "Unknown" for missing depositor_name and depositor_group
- Alternating row colors

**What is NOT implemented:**
- Bug 2 (color palette visibility) — see above
- Excel-like column filtering (year -> month -> date hierarchy per R6 — deferred but worth noting here)
- Status column is not a QComboBox (R3 overlap)
- In-line edit for depositor_group when depositor_name is blank — technically the cell is editable but there's no special UX affordance

**Backend Tasks:**
- [ ] No pure backend tasks for R2

**Frontend/UI Tasks:**
- [ ] Fix Bug 2 (color visibility) — `ui/view_tab.py`
- [ ] [R3 overlap] Status QComboBox delegate — `ui/view_tab.py` + potentially `ui/delegates/status_delegate.py`

**Interface Contract:**
- `read_loans() -> List[Loan]` — `data/csv_manager.py`
- `recompute_all(loans: List[Loan], today: date) -> List[Loan]` — `data/status_engine.py`
- `update_loan(loan: Loan) -> None` — `data/csv_manager.py`

**Dependency Order:** Bug 2 fix is self-contained. Status delegate is R3 work.

---

## Dev Lead Decomposition: R3 — Record Modification / Status Transitions

**Status:** Partially implemented

**What is implemented:**
- Inline editing for all non-protected columns via `_on_item_changed()`
- Status auto-recomputed after giving_date or due_date edits
- Delete action in context menu
- Extend action in context menu
- Mark Paidoff in context menu

**What is NOT implemented:**
- Bug 3 (Paidoff not reachable) — see above
- QComboBox for Status column — only context menu available
- Manual Active override (R3): "User can manually mark a loan as Active even if technically Overdue → asks for new expiration date (same as Extend)". Currently, setting status=Active via inline edit is not wired to prompt for a new due date.
- Transition matrix enforcement (e.g., preventing direct Paidoff toggle from Status combo without date dialog)

**Backend Tasks:**
- [ ] No new backend tasks for R3

**Frontend/UI Tasks:**
- [ ] Fix Bug 3 (Paidoff discoverability) — add toolbar Paidoff button — `ui/view_tab.py`
- [ ] Implement Status column QStyledItemDelegate — `ui/view_tab.py` or `ui/delegates/status_delegate.py`
  - On selection of "Paidoff": open PaidoffDialog
  - On selection of "Active" from Overdue: open ExtendDialog (or prompt for new due date)
  - Other transitions: update directly without dialog

**Interface Contract:**
- `mark_paidoff(reference_id: str, paidoff_date: date) -> None` — `data/csv_manager.py`
- `compute_status(loan: Loan, today: date) -> str` — `data/status_engine.py`

**Dependency Order:** Bug 3 fix (toolbar button) is prerequisite to QA testing Paidoff. Status delegate is next.

---

## Dev Lead Decomposition: R6 — Excel-like Filtering, Export/Import

**Status:** Minimally implemented

**What is implemented:**
- `data/export_service.py` — file exists (not read in detail; assumed CSV export)
- `data/import_service.py` — file exists (not read in detail; assumed CSV import)
- Basic sortable View Tab (not excel-like column header filtering)

**What is NOT implemented:**
- Excel-like column header filter (year -> month -> date hierarchy for date columns)
- Export to .xlsx
- Import preview dialog
- Import upsert / collision handling
- "Unknown" blank option in depositor group filter for no-depositor records
- Full import flow with recovery (import_recovery.tmp already referenced in MainWindow)

**Backend Tasks:**
- [ ] Implement `export_to_xlsx(loans: List[Loan], output_path: Path) -> None` — `data/export_service.py` (requires openpyxl or xlsxwriter)
- [ ] Implement `import_from_csv(source_path: Path) -> ImportResult` with upsert logic — `data/import_service.py`
- [ ] Implement `import_from_xlsx(source_path: Path) -> ImportResult` — `data/import_service.py`
- [ ] Auto-assign ref_ids for imported records without ref_ids
- [ ] Collision handling: imported data overrides existing record completely

**Frontend/UI Tasks:**
- [ ] Add Export button to View Tab toolbar — `ui/view_tab.py`
- [ ] Add Import button to View Tab toolbar — `ui/view_tab.py`
- [ ] Import preview dialog showing: total new rows, total overwritten rows, sample overwritten ref_ids — new `ui/dialogs/import_preview_dialog.py`
- [ ] Excel-like column header filter — [REVIEW REQUIRED] QHeaderView-based filter or custom filter row panel? This is a significant UI effort; consider a simpler filter row below the header as the prototype approach.

**Interface Contract:**
- `export_loans(loans: List[Loan], output_path: Path, format: str) -> None`
- `import_loans(source_path: Path) -> ImportResult` where `ImportResult` carries new_count, overwritten_count, sample_overwritten_ids

**Dependency Order:** Export is standalone. Import requires preview dialog. Column header filter is the most complex piece — defer for post-prototype or implement as simple dropdown panel filter.

---

## Dev Lead Decomposition: R8 — Prototype Executability / Windows .bat

**Status:** Partially implemented

**What is implemented:**
- PySide6 stack chosen
- `main.py` is the entry point
- Logging to `./data/logs/app.log`

**What is NOT implemented:**
- `run_windows.bat` — not found in codebase scan
- `run_mac.sh` — not found in codebase scan
- `requirements.txt` — not found in codebase scan

**Backend Tasks:**
- [ ] Create `requirements.txt` with pinned versions: PySide6, python-dateutil, openpyxl — project root (`/src/Loan Manager/requirements.txt`)
- [ ] Create `run_windows.bat`:
  - Python version check (>= 3.10); if not met, print upgrade message and exit
  - Create venv if not exists
  - Install requirements
  - Launch `python main.py`
  - `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/run_windows.bat`
- [ ] Create `run_mac.sh`:
  - Python version check (>= 3.10 via python3)
  - Create venv if not exists
  - Install requirements
  - Launch `python3 main.py`
  - `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/run_mac.sh`
- [ ] Empty data files for user distribution (not sample data): `loans.csv`, `loans_meta.csv`, `pending_reports.csv`, `pending_report_records.csv` with headers only — in `data/`

**Frontend/UI Tasks:**
- [ ] No additional UI tasks for R8

**Interface Contract:** N/A (infrastructure only)

**Dependency Order:** requirements.txt first, then .bat/.sh scripts that reference it.

---

## Dev Lead Decomposition: R7 — Sample Data / Edge Cases

**Status:** Partially implemented

**What is implemented:**
- Status engine handles no-due-date as Overdue correctly (BC-01)
- Extend dialog handles no-due-date case (base_date = today)

**What is NOT implemented:**
- Prototype ships with empty data files (R7: "sample data is for developer-only testing") — need to verify current `data/loans.csv` will not ship with test data
- No-due-date + Extend: current implementation uses period spinbox, not a direct date picker for due_date — [REVIEW REQUIRED] as noted in R4 decomposition

**Backend Tasks:**
- [ ] Create empty header-only data files for distribution — `data/loans.csv`, `data/loans_meta.csv`, `data/pending_reports.csv`, `data/pending_report_records.csv`
- [ ] Verify/add `.gitignore` entry to exclude `data/*.csv` content (keep only headers) for the end-user distribution

**Frontend/UI Tasks:**
- [ ] No new UI tasks specific to R7

**Dependency Order:** Empty data files are low risk; do after confirming current test data is excluded from user distribution.

---

## Dev Lead Decomposition: R10 — User Guide

**Status:** Not implemented

**Backend Tasks:**
- [ ] No backend tasks

**Frontend/UI Tasks:**
- [ ] No UI tasks

**Documentation Tasks:**
- [ ] Create `user_guides/windows_guide.md` — step-by-step for Windows users
- [ ] Create `user_guides/mac_guide.md` — step-by-step for Mac users
- [ ] Both guides cover: prerequisites (Python 3.10+), running `run_windows.bat` / `run_mac.sh`, first-time data setup, tab-by-tab usage instructions
- [ ] `/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager/user_guides/`

**Dependency Order:** Depends on R8 (.bat and .sh scripts being finalized) before writing guides.

---

## Dev Lead Decomposition: R9 — Modern UI / Theme

**Status:** Not implemented beyond default PySide6 styling

**Frontend/UI Tasks:**
- [ ] Define a `QStyleSheet` or `QPalette` for at minimum 2 theme options to present to user — new `ui/theme.py`
- [ ] Apply theme on `QApplication` in `main.py`
- [ ] [REVIEW REQUIRED] Theme preferences: user to evaluate and pick. Options: (a) system default + subtle color accents, (b) dark mode, (c) light professional. No purple hues per coding style rules.

**Dependency Order:** R9 is cosmetic and lowest risk; do last after all functional fixes.

---

## Part 3: QA Lead KT Package

```
## Dev Lead -> QA Lead KT: Loan Manager Prototype

**What was built:**

The Loan Manager is a PySide6 desktop application for managing loan records via CSV storage.
It consists of four tabs: Entry, View, Interest Calculator, and Pending Approval.

Core backend is split into two layers:
  - loan_manager/* (canonical, class-based, injectable-path, used by tests)
  - data/* (application-layer shims/adapters, used by UI)

The key components implemented:
  - Loan entry with autocomplete, ref_id generation, status computation
  - View Tab with sortable, inline-editable table; context menu for Delete/Extend/Paidoff
  - Interest Calculator with Monthly/Daily/Both modes; filtering; report generation
  - Pending Approval Tab with approve/decline; inline recalc; crash-safety recovery files
  - CSV-based persistence: loans.csv, history.csv, pending_reports.csv,
    pending_report_records.csv, loans_meta.csv, recovery.tmp, approval_recovery.tmp

**Backend changes needed (pre-QA):**
  - BUG 1: Fix interest_calculator_tab.py _on_apply_filters() so filter selections
    are not reset when _load_loans() repopulates the combos
  - BUG 3 supplement: Verify mark_paidoff() atomic two-write works end-to-end;
    check that history.csv is created if absent
  - Verify loan_manager/csv_manager.py CSVManager.batch_extend_loans() exists
    (referenced by data/csv_manager.py batch_extend_loans())
  - R1 fix: default No Due Date checkbox should be checked (not unchecked) per spec

**Frontend/UI changes needed (pre-QA):**
  - BUG 1: Filter combo revert fix in interest_calculator_tab.py
  - BUG 2: Status color palette — force dark foreground on all status-colored rows
    in view_tab.py
  - BUG 3: Add "Mark Paidoff" toolbar button to View Tab for discoverability
  - BUG 4: Create ClickableDateEdit widget; replace QDateEdit in entry_tab.py
    and paidoff_dialog.py
  - R1: Fix default No Due Date checkbox state

**Happy paths to test:**

  1. Entry Tab:
     - Enter a new loan (Borrower Name, Borrower Group, Amount, Giving Date, No Due Date checked)
     - Verify status bar shows "Loan saved successfully. Reference ID: YYYY_MM_001"
     - Enter a second loan with a due date in the future -> status = Active
     - Enter a loan with a past due date -> status = Overdue
     - Enter a loan with a future giving_date -> status = Pending
     - Verify autocomplete suggestions appear on second entry for same borrower

  2. View Tab:
     - Confirm all entered loans appear in correct order
     - Sort by Amount (ascending, descending)
     - Sort by Due Date
     - Inline-edit Borrower Name -> verify change persists after refresh
     - Inline-edit Giving Date to a future date -> verify status changes to Pending
     - Right-click a loan -> Extend -> select 1 month -> verify new dates in preview and saved
     - Right-click a loan -> Delete -> confirm dialog -> verify row removed
     - Select a loan -> click "Mark Paidoff" (toolbar button, post-fix) -> enter paidoff_date
       -> verify row removed from View Tab and present in history.csv

  3. Interest Calculator:
     - Select Borrower Group = "bg1" -> Apply Filters -> verify filter STAYS on bg1
       and table shows only bg1 loans
     - Select Monthly mode, interest_rate=12, commission_rate=2, extension_period=1
     - Click Calculate -> verify interest = (amount * 12 * 1) / (12 * 100) per row
     - Click Generate Report -> verify report appears in Pending Approval Tab
     - Select Daily mode, verify extension_unit locked to "days"
     - Select Both mode, verify per-record extension_unit is editable

  4. Pending Approval:
     - Select the generated report -> verify record table populates
     - Inline-edit interest_rate in a row -> verify Interest column auto-updates
     - Click Approve -> verify loans.csv updated with new giving_date/due_date
     - Generate a second report with overlapping ref_ids -> approve first -> approve second
       -> verify shared ref_id warning dialog appears
     - Click Decline on a report -> verify report removed from queue (status=Declined)

  5. App restart:
     - Close and reopen app
     - Verify status recompute runs (Overdue records updated if due_date has passed)
     - Verify Pending Approval queue still shows pending reports

**Edge cases / known risks:**

  R1:
    - Amount = 0 is valid (non-negative integer per spec); verify no validation rejection
    - Duplicate borrower entries (same name, different amounts) must both appear; no dedup
    - No Due Date + giving_date = today -> status should be Overdue (not Active)

  R3/R4:
    - Extend a loan with no due_date: new giving_date = today, new due_date = picked by user
      [REVIEW REQUIRED] current dialog uses period spinbox, may be confusing
    - Delete last loan for a YYYY_MM bucket -> counter resets -> next loan in same month gets _001
    - Extend a loan whose reference_id is in an active Pending Approval report:
      the report will then have stale pre-extension dates. This is an accepted data-loss risk
      (history loss accepted per R5 spec).

  R5:
    - ByMonth filter for "April" should include Overdue loans whose due_date was in April
      of the current calendar year (2026). Verify no off-by-one on month numbers.
    - TDS=true: interest_amount * 0.1 = tds_amount, not total * 0.1
    - Mode=Both with mixed units in a single report: some rows months, some days.
      Verify calculate_both() routes correctly per row.
    - If all filtered records have no due_date, "Apply Filters" with a filter selected
      should return empty table (per R5 "any filter applied: exclude no-due-date loans")
    - Generate Report with 0 rows (empty filter) -> should show warning, not create empty report

  R6:
    - Import with no reference_ids: all should be auto-assigned in YYYY_MM_<order> format
    - Import with some existing ref_ids: those rows should overwrite existing records
    - Import preview dialog must appear before destructive overwrite; "Cancel" must abort

  Recovery files:
    - Simulate crash between history.csv write and loans.csv removal for Paidoff:
      On next startup, recovery.tmp exists -> warning dialog should appear
    - import_recovery.tmp and approval_recovery.tmp similarly tested

**Out of scope for prototype:**

  - Backup copy of loans.csv before Paidoff / bulk Approve (explicitly deferred in R3)
  - Excel-like column header filter (year -> month -> date hierarchy in View Tab) — partial
  - "Fill all rows" / "Copy down" shortcut in Interest Calculator (explicitly deferred in R5)
  - Concurrent session file locking (single user; R8)
  - Paidoff history in-app view (no in-app view required per R3)
  - Batch write on startup to avoid O(N^2) writes (R10 note; currently each loan is
    written individually in startup recompute via update_loan() loop)
  - Full xlsx export (pending openpyxl integration)
  - Legacy ref_id format collision handling during import (low priority per R6 user note)
```

---

## Part 4: Test Coverage Targets

| Module | Current Coverage (estimate) | Target | Notes |
|---|---|---|---|
| `loan_manager/status_engine.py` | ~80% (test file exists) | 100% | All boundary conditions: Paidoff lock, no-due-date, same-day due |
| `loan_manager/interest_calculator.py` | ~70% (core formulas likely tested) | 100% | Monthly/Daily/Both; TDS on/off; zero amounts; unknown unit ValueError |
| `loan_manager/ref_id_manager.py` | ~70% (test file exists) | 100% | 999->1000 overflow; reset counter; empty CSV; collision increment |
| `data/csv_manager.py` | ~50% (test file exists) | 90% | mark_paidoff atomic steps; batch_extend; delete with counter reset |
| `loan_manager/report_manager.py` | ~30% (estimated) | 80% | generate_report_id; write/read/update/delete report records; approval flow |
| `models/loan.py` | ~60% | 80% | from_csv_row with missing fields; to_csv_row round-trip |
| `models/report.py` | ~20% (estimated) | 80% | PendingReport/ReportRecord round-trip serialization |
| `data/export_service.py` | ~0% | 70% | CSV and xlsx export; empty loans list |
| `data/import_service.py` | ~0% | 70% | New-only import; upsert; collision priority; no-ref_id auto-assign |
| `ui/interest_calculator_tab.py` | ~0% (UI; hard to unit test) | 30% | Filter logic via `_get_filtered_loans()` can be extracted and unit-tested |
| `ui/view_tab.py` | ~0% (UI) | 10% | Status color lookup; row construction helpers |
| `ui/dialogs/*.py` | ~0% (UI) | 20% | Dialog accepts/rejects; date parsing |

**Priority for new tests:**
1. `loan_manager/status_engine.py` — all edge cases confirmed (existing test file; verify completeness)
2. `loan_manager/interest_calculator.py` — all three modes, TDS, calculate_both routing
3. `loan_manager/ref_id_manager.py` — counter overflow, reset, collision
4. `data/csv_manager.py` — mark_paidoff atomic protocol, batch_extend
5. `data/import_service.py` — new module, zero coverage, high risk
6. Filter logic in `interest_calculator_tab.py` (`_get_filtered_loans`) — extract to pure function for testability

---

## Part 5: Technical Clarifications

### [REVIEW REQUIRED] RC-01: No Due Date Checkbox Default
R1 specifies "By default, No Due Date is checked". Current code has `setChecked(False)`.
Decision needed: Confirm requirement. If No Due Date IS the default, the due_date QDateEdit should be disabled on Entry Tab load. This affects data integrity (many loans may be entered without due dates inadvertently if users don't notice the checkbox).

### [REVIEW REQUIRED] RC-02: No-Due-Date Extend — Period vs Direct Date Picker
R7 says "new giving_date = today_date and the due_date = new due date picked by the user via date picker". The current `ExtendDialog` uses a period spinbox (e.g., "3 months"). For no-due-date loans, showing a direct `QDateEdit` for the new due date is likely more intuitive. Decision needed: Keep period-based or switch to date-picker for no-due-date case only?

### [REVIEW REQUIRED] RC-03: View Tab Color Direction
Two options for Bug 2 fix. Option A: keep light pastel backgrounds, force dark text. Option B: switch to dark/saturated backgrounds with white text. User preference required before implementing.

### [REVIEW REQUIRED] RC-04: ClickableDateEdit Implementation Strategy
If QDateEdit `showPopup()` override does not work on the target Windows 11 environment (Python 3.10 + PySide6), the fallback is a `QPushButton` + `QCalendarWidget` in a custom widget. This requires more UI work but is reliable. Decision needed: Test the subclass approach first, fallback only if it fails?

### [REVIEW REQUIRED] RC-05: batch_extend_loans Dependency
`data/csv_manager.py` line 302 calls `from loan_manager.csv_manager import CSVManager`. A file `loan_manager/csv_manager.py` was not confirmed to exist in the file scan. If it is missing, the batch approval flow will crash with an ImportError at approval time. This must be verified immediately and the function implemented inline in `data/csv_manager.py` if the module is absent.

### [REVIEW REQUIRED] RC-06: Excel-like Column Filter Scope for Prototype
R6 requires "year -> month -> date hierarchy" filtering in the View Tab. This is a significant UI engineering effort (custom QHeaderView or filter row). For the prototype, scope decision needed: (a) defer entirely, (b) implement a simple filter-row panel below the table header (QLineEdit + QComboBox per column), (c) implement the full year/month/date hierarchical filter. Option (b) is recommended for prototype.

### [REVIEW REQUIRED] RC-07: Paidoff Report Generation
R3 states: "When paidoff_date is entered, a report is generated for the interest calculations which is then sent over for approval." Currently `_action_paidoff()` in `view_tab.py` calls `mark_paidoff()` directly — it does NOT generate or route a report to Pending Approval. R5 defines the Paidoff Daily mode calculation as `extension_period(days) = paidoff_date - due_date`. Is the Paidoff-triggered report generation required for the prototype, or is direct archiving to history.csv sufficient? Decision needed to avoid mid-sprint scope change.

---

## Appendix: File Change Summary by Bug

| Bug | Files to Modify | New Files |
|---|---|---|
| Bug 1 (filter) | `ui/interest_calculator_tab.py` | None |
| Bug 2 (colors) | `ui/view_tab.py` | None |
| Bug 3 (paidoff) | `ui/view_tab.py` | Optionally `ui/delegates/status_delegate.py` |
| Bug 4 (date picker) | `ui/entry_tab.py`, `ui/dialogs/paidoff_dialog.py` | `ui/widgets/clickable_date_edit.py` |

## Appendix: Architecture Notes

- `data/*.py` = UI-facing adapter layer. Never import `loan_manager.*` directly in UI code.
- `loan_manager/*.py` = Canonical business logic. Used by tests with injectable paths.
- `models/*.py` = Pure dataclasses. No I/O.
- `data/status_engine.py` is a re-export shim only. All logic is in `loan_manager/status_engine.py`.
- The two-layer pattern (data/ + loan_manager/) allows unit testing without a QApplication.
- Do NOT bypass the data/ adapter layer in UI code.
