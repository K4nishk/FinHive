# Solution Architecture: Loan Manager Desktop Application

**Date:** 2026-04-03
**Run:** run_1 / Wave 1
**Agent:** Solution Architect (SA)
**Status:** Draft

---

## 1. Architecture Design

### Architecture Pattern

**Layered — UI / Service / Data**

Three discrete horizontal layers with strict dependency direction: UI depends on Service (loan_manager), Service depends on Data (models + csv). No upward dependencies are permitted.

```
+--------------------------------------------------------------+
|  UI Layer (ui/)                                              |
|  main_window, entry_tab, view_tab, interest_calculator_tab,  |
|  pending_approval_tab, dialogs/                              |
+--------------------------------------------------------------+
          |  signals/method calls only (no CSV access)
          v
+--------------------------------------------------------------+
|  Service Layer (loan_manager/)                               |
|  status_engine, interest_calculator, csv_manager,            |
|  ref_id_manager, report_manager                             |
+--------------------------------------------------------------+
          |  domain model access only
          v
+--------------------------------------------------------------+
|  Data Layer (models/ + data/ adapters + ./data/*.csv)        |
|  Loan dataclass, Report dataclass, CSV files                 |
+--------------------------------------------------------------+
```

### Components

| Component | Responsibility | Technology |
|---|---|---|
| `main.py` | Entry point. Bootstraps logging, creates QApplication, shows MainWindow. | Python 3.10+, PySide6 |
| `ui/main_window.py` | Root QMainWindow. Owns QTabWidget, wires cross-tab signals, runs startup status recompute. | PySide6 QMainWindow |
| `ui/entry_tab.py` | New loan entry form. Autocomplete, date pickers, amount spinner, status-bar confirmation. | PySide6 QWidget, QFormLayout, QDateEdit |
| `ui/view_tab.py` | Sortable, filterable, inline-editable loan table. Context menu for Delete / Extend / Paidoff. | PySide6 QTableView + QStandardItemModel + QSortFilterProxyModel |
| `ui/interest_calculator_tab.py` | Three-mode interest calculator (Monthly / Daily / Both). Filter panel, global params, per-record overrides, Calculate + Generate Report flow. | PySide6 QWidget, QTableWidget |
| `ui/pending_approval_tab.py` | Report approval queue. Inline-editable report records, Approve / Decline actions, conflict/stale-record warnings. | PySide6 QWidget, QTableWidget |
| `ui/dialogs/extend_dialog.py` | Extend loan dialog: collects extension_period_unit + extension_period. | PySide6 QDialog |
| `ui/dialogs/paidoff_dialog.py` | Paidoff dialog: collects paidoff_date, warns about archival. | PySide6 QDialog, QDateEdit |
| `loan_manager/status_engine.py` | **AUTHORITATIVE** status computation (`compute_status`, `recompute_all`). Pure functions, no I/O. | Python dataclasses |
| `loan_manager/interest_calculator.py` | Pure calculation functions: `calculate_monthly`, `calculate_daily`, `calculate_both`. No I/O. | Python |
| `loan_manager/csv_manager.py` | Core CSV I/O: read/write/update/delete loans, mark_paidoff, extend_loan, batch_extend_loans, recovery protocol. | Python csv module |
| `loan_manager/ref_id_manager.py` | Reference ID generation, counter persistence in loans_meta.csv, collision resolution. | Python csv module |
| `loan_manager/report_manager.py` | Pending report CRUD: read/write pending_reports.csv + pending_report_records.csv. | Python csv module |
| `data/status_engine.py` | Re-export shim only. All logic lives in `loan_manager/status_engine.py`. | Python import |
| `data/csv_manager.py` | App-layer adapter. Delegates to `loan_manager/csv_manager.py`. Provides import/export surface. | Python |
| `data/ref_id_manager.py` | App-layer adapter for ref_id_manager. | Python |
| `data/report_manager.py` | App-layer adapter for report_manager. | Python |
| `data/export_service.py` | Export to .csv / .xlsx. | Python, openpyxl |
| `data/import_service.py` | Import .csv / .xlsx. Preview dialog support, upsert, collision resolution, auto-assign ref_id. | Python, openpyxl |
| `models/loan.py` | `Loan` dataclass + `CSV_FIELDNAMES`. Serialisation/deserialisation helpers. | Python dataclasses |
| `models/report.py` | Report and ReportRecord dataclasses. | Python dataclasses |
| `data/loans.csv` | Single flat-file store for all active loan records (non-Paidoff). | CSV, UTF-8 |
| `data/history.csv` | Archive of Paidoff loan records with paidoff_date column. | CSV, UTF-8 |
| `data/loans_meta.csv` | High-water-mark counters per YYYY_MM for ref_id generation. | CSV, UTF-8 |
| `data/pending_reports.csv` | Report header metadata: report_id, status, timestamps. | CSV, UTF-8 |
| `data/pending_report_records.csv` | Report line items keyed by report_id + reference_id. | CSV, UTF-8 |
| `data/recovery.tmp` | Transient crash-safety token for paidoff operations. | Plain text |
| `data/import_recovery.tmp` | Transient crash-safety token for import operations. | Plain text |
| `data/approval_recovery.tmp` | Transient crash-safety token for batch approval operations. | Plain text |
| `data/logs/app.log` | Application log. Rotates on restart. | Python logging |

### Data Flow

#### New Loan Entry (R1)
```
EntryTab (form submit)
  -> generate_ref_id(today) [loan_manager/ref_id_manager]
  -> Loan(dataclass) created with compute_status(loan, today) [loan_manager/status_engine]
  -> write_loan(loan) [loan_manager/csv_manager -> loans.csv]
  -> StatusBar: "Loan saved successfully. Reference ID: {ref_id}."
  -> loan_added signal -> ViewTab.load_data() + EntryTab.refresh_completers()
```

#### View / Inline Edit (R2, R3)
```
ViewTab.load_data()
  -> read_loans() [loan_manager/csv_manager <- loans.csv]
  -> recompute_all(loans, today) [loan_manager/status_engine]
  -> update_loan(each) [loan_manager/csv_manager -> loans.csv]  (batch write, PD-30 pattern)
  -> QStandardItemModel populated, QSortFilterProxyModel sorts/filters

User edits cell
  -> _on_item_changed -> update_loan(loan) [loan_manager/csv_manager -> loans.csv]
  -> status recomputed inline for date column changes
  -> data_changed signal -> EntryTab.refresh_completers()
```

#### Mark Paidoff (R3)
```
ViewTab context menu -> "Mark Paidoff"
  -> PaidoffDialog (collects paidoff_date)
  -> mark_paidoff(ref_id, paidoff_date) [loan_manager/csv_manager]
     1. Write recovery.tmp (ref_id token)
     2. Append to history.csv (with paidoff_date, status=Paidoff)
     3. Remove from loans.csv
     4. Delete recovery.tmp
  -> ViewTab.load_data() + data_changed signal
```

#### Interest Calculator (R5)
```
InterestCalculatorTab
  -> _load_loans() -> read_loans() [loan_manager/csv_manager]
  -> User selects filters -> _on_apply_filters() -> _get_filtered_loans()
  -> User sets global params -> _on_global_param_changed() overwrites all rows
  -> "Calculate" -> calculate_monthly/daily/both() [loan_manager/interest_calculator]
     results written back to table cells; _btn_generate enabled
  -> "Generate Report"
     -> ReportManager.create_report() [loan_manager/report_manager]
        -> pending_reports.csv (header)
        -> pending_report_records.csv (line items)
     -> report_generated signal -> PendingApprovalTab.load_reports()
```

#### Pending Approval — Approve (R5)
```
PendingApprovalTab
  -> load_reports() -> ReportManager.read_pending_reports()
  -> User edits inline -> auto-recalculate interest_amount / commission_amount / tds_amount
  -> "Approve"
     -> Conflict check: any reference_id in another Pending report? Warn if yes.
     -> Write approval_recovery.tmp (report_id token)
     -> batch_extend_loans(extensions) [loan_manager/csv_manager] single-pass rewrite
     -> ReportManager.mark_approved(report_id) -> pending_reports.csv updated
     -> Delete approval_recovery.tmp
  -> data_changed signal -> ViewTab.load_data() + EntryTab.refresh_completers()
```

#### Import / Export (R6)
```
Import:
  User selects .csv or .xlsx
  -> ImportService.parse(file)
  -> Preview dialog: N new, M overwrite, sample ref_ids of overwrites
  -> User confirms
  -> write import_recovery.tmp
  -> upsert rows to loans.csv (imported record wins on collision)
  -> delete import_recovery.tmp
  -> ViewTab.load_data()

Export:
  User triggers export
  -> ExportService.export(loans, format)
  -> Writes to user-selected path as .csv or .xlsx
```

---

## 2. Technology Recommendation

### PySide6 — Confirmed Choice

**Rationale:** R8 explicitly selects PySide6. It is the official Qt for Python binding (LGPL), ships cross-platform (Windows + macOS), and supports the full Qt widget set required by this application.

| Aspect | Assessment |
|---|---|
| Cross-platform | Windows 10+, macOS 12+. Single codebase, no platform-specific branches needed for core features. |
| Widget richness | QTableView, QDateEdit, QCalendarWidget, QComboBox, QSortFilterProxyModel — all required widgets are available natively. |
| Packaging | Bundles via PyInstaller or briefcase; run_windows.bat / run_mac.sh scripts are viable. |
| Licensing | LGPL 3.0. Free for internal/single-user use. No commercial licensing cost. |
| Python compatibility | PySide6 requires Python 3.8+. R10 mandates 3.10+ which is compatible. |
| Cons | Larger install footprint (~50 MB) than tkinter. First-time pip install on Windows requires network. Mitigated by run_windows.bat creating a venv and installing requirements. |

### Table Widget Choice for View Tab (R4 Architectural Requirement)

**Decision: QTableView + QStandardItemModel + QSortFilterProxyModel**

This is implemented in the current codebase (`view_tab.py`). The rationale is documented as an architectural requirement per R4.

| Criterion | QTableWidget | QTableView + QStandardItemModel + QSortFilterProxyModel |
|---|---|---|
| Sorting | Manual sort required; no built-in multi-column model sort. | `setSortingEnabled(True)` on QTableView + QSortFilterProxyModel: built-in, stable sort per column. |
| Filtering | No built-in support; requires hiding rows manually. | QSortFilterProxyModel provides row-level filtering via `setFilterKeyColumn` and custom `filterAcceptsRow`. |
| Performance at 1500 rows | QTableWidget stores one QTableWidgetItem per cell. For 1500 rows x 10 cols = 15,000 items in memory. Acceptable but higher overhead. | QStandardItemModel stores items with same overhead but QSortFilterProxyModel operates on indices without copying data. More efficient for sort/filter operations. |
| Inline editing | Possible but requires subclassing or delegates for custom editors. | Delegates (QItemDelegate / QStyledItemDelegate) cleanly separate editor logic from model. Custom date editing and status combo can be implemented as delegates. |
| Custom column locking | Requires per-cell flag manipulation. | Per-item `setEditable(False)` or delegate-level lock. Cleaner. |
| Numerical sorting | String-based by default; requires custom sort role. | `Qt.ItemDataRole.DisplayRole` set to `int` for Amount/SNo gives correct numeric sort without subclassing. |
| **Verdict** | Suitable for small tables. Becomes unwieldy at 1500 rows with filtering requirements. | **Selected.** Model-View separation cleanly supports sort, filter, and inline edit at 1500 rows within requirements. |

**Note on Interest Calculator Tab:** `QTableWidget` is used in `interest_calculator_tab.py` and `pending_approval_tab.py`. These tables are not expected to exceed 10-50 rows post-filtering (per R5: "initial count post filtering is not supposed to cross 10 records"). `QTableWidget` is acceptable for these tabs since sorting and persistent filtering are not architectural requirements for these views. [REVIEW REQUIRED: confirm QTableWidget is sufficient for Pending Approval tab if report queue grows.]

### CSV Storage Trade-offs at 1500 Rows

| Aspect | Position |
|---|---|
| Read performance | Full-file read at startup for 1500 rows is fast (<50 ms on spinning disk, <10 ms on SSD). Acceptable for single-user desktop. |
| Write performance | `update_loan` and `delete_loan` perform a full-file rewrite (read-all, filter, write-all). At 1500 rows, this is O(N) per operation, roughly 1-5 ms. Acceptable. Batch operations use single-pass rewrite (PD-30). |
| Concurrency | R8 explicitly states no concurrent sessions and no CSV locking is needed. Single-user scope. |
| Integrity | No ACID guarantees. Mitigated by recovery.tmp protocol for destructive operations. |
| Backup | R3 mentions timestamped backup before destructive operations. Deferred to future (per R3 prototype scope note). [REVIEW REQUIRED: confirm deferral is still acceptable.] |
| Import/Export | openpyxl required for .xlsx support. No database dependency. |
| Upper bound | 1500 rows x ~200 bytes/row ~= 300 KB. Trivially small. CSV is appropriate for prototype scope. |
| Limitations | No indexing, no query language, no concurrent access protection, no rollback beyond recovery.tmp. Acceptable for prototype. Future scale-up path: SQLite (drop-in via Python stdlib, minimal migration). |

---

## 3. Architecture Decision Records (ADRs)

### ADR-001: loan_manager/ as Canonical Service Layer; data/ as App-Layer Adapter/Re-export Shim

**Status:** Accepted

**Context:** The codebase has two directories that superficially overlap: `loan_manager/` and `data/`. Early prototypes mixed CSV I/O directly in the data directory. Tests needed to import service logic without UI dependencies.

**Decision:** `loan_manager/` contains all authoritative business logic (status engine, interest calculator, CSV manager, ref_id manager, report manager). `data/` contains thin re-export shims or adapter wrappers that the UI layer imports. This preserves a clean import surface for UI code while allowing tests to import directly from `loan_manager/` without pulling in any UI or app-layer code.

**Consequence — Positive:**
- Service layer is independently testable with no UI dependencies.
- `data/status_engine.py` being a pure re-export means UI code importing from `data.*` continues to work after future refactors to `loan_manager.*`.
- Clear canonical answer to "where does this logic live?"

**Consequence — Negative:**
- Two-level import path adds a layer of indirection. New developers may be confused by `data/` containing shims rather than raw data files.
- Must enforce the rule that `loan_manager/` never imports from `data/` or `ui/`.

**Compliance Note:** `data/csv_manager.py` currently contains `batch_extend_loans` which delegates back to `loan_manager.csv_manager.CSVManager`. This delegation pattern is correct but the function `batch_extend_loans` in `data/csv_manager.py` must not contain logic of its own.

---

### ADR-002: QTableView + QStandardItemModel + QSortFilterProxyModel for View Tab

**Status:** Accepted

**Context:** R4 mandates a sortable, filterable, inline-editable table supporting up to 1500 rows. The current `view_tab.py` implements this pattern.

**Decision:** Use `QTableView` with `QStandardItemModel` as the data model and `QSortFilterProxyModel` as the sort/filter proxy. See Section 2 for full comparison.

**Key implementation constraints arising from this decision:**
1. Row access during inline edit requires mapping proxy index to source index via `self._proxy.mapToSource(index)`. This must be respected in all context menu and double-click handlers.
2. `itemChanged` signal must be disconnected (not blocked) during programmatic model population to keep the proxy mapping current (`_populate_model` uses disconnect/reconnect pattern).
3. Reference ID is stored in `Qt.ItemDataRole.UserRole` on the SNo item of each row to survive sort-order changes. All row lookup must go through this user role, never through row index alone.
4. Numeric columns (Amount, SNo) must set `DisplayRole` to `int` not `str` for correct numeric sort behavior.

**Consequence — Negative:**
- Excel-style per-column header filter dropdowns (R6: year->month->date hierarchy) require a custom `QHeaderView` or an overlay widget. The built-in `QSortFilterProxyModel` supports only single-column text filtering. This is a known gap — [REVIEW REQUIRED: Excel-style hierarchical column filter is not yet implemented. Assess whether a simpler text-filter bar above the table is acceptable for the prototype.]

---

### ADR-003: Single loans.csv for All Active Records

**Status:** Accepted

**Context:** R6 states "All records (all years) can be stored in a single .csv as starting point as expected data volume is not huge." R8 confirms no database is needed for prototype.

**Decision:** A single `./data/loans.csv` file stores all non-Paidoff loan records regardless of year. `history.csv` stores Paidoff records. `loans_meta.csv` stores ref_id counters.

**File Layout:**
```
data/
  loans.csv           - active loans (all statuses except Paidoff)
  history.csv         - paidoff loans (with paidoff_date column)
  loans_meta.csv      - ref_id high-water-mark counters per YYYY_MM
  pending_reports.csv - report headers (report_id, status, timestamps)
  pending_report_records.csv - report line items
  recovery.tmp        - transient crash token (paidoff)
  import_recovery.tmp - transient crash token (import)
  approval_recovery.tmp - transient crash token (batch approval)
  logs/app.log        - application log
```

**Consequence — Positive:** Simple, no partitioning logic. Easy manual inspection and git-sharing between Windows end-user and Mac tester.

**Consequence — Negative:** Full rewrite on every update/delete. Acceptable at 1500 rows. No enforced schema validation beyond `Loan.from_csv_row()` error handling.

---

### ADR-004: Pending Approval Normalised Two-File Approach

**Status:** Accepted

**Context:** R5 specifies reports have a header (report_id, status, timestamp) and line items (per-borrower calculation rows). A single-file approach would either denormalise repeated header columns into every row or require complex parsing to separate header from records.

**Decision:** Use two separate CSV files:
- `pending_reports.csv`: one row per report. Columns: `report_id, created_date, updated_date, status`.
- `pending_report_records.csv`: one row per report line item. Columns: `report_id, reference_id, borrower_name, amount, depositor_name, giving_date, due_date, interest_rate, commission_rate, extension_period, extension_period_unit, tds_flag, interest_amount, commission_amount, tds_amount, post_extension_giving_date, post_extension_due_date`.

**Consequence — Positive:**
- Clean separation between report metadata and record-level data.
- Adding/removing records from a report requires only a rewrite of `pending_report_records.csv` filtered by `report_id`.
- Report list loads cheaply from `pending_reports.csv` without parsing all record rows.

**Consequence — Negative:**
- Approval requires two coordinated writes (update loans.csv + update pending_reports.csv + delete from pending_report_records.csv). This is why `approval_recovery.tmp` exists.
- Conflict detection (two reports sharing a reference_id) requires a cross-join scan of `pending_report_records.csv` at approval time.

---

### ADR-005: Atomic Paidoff Write — recovery.tmp Protocol

**Status:** Accepted

**Context:** Marking a loan as Paidoff requires two destructive writes: appending to `history.csv` and removing from `loans.csv`. A crash between these two writes would result in a record that is neither in active loans nor in history — permanently lost.

**Decision:** Implement a four-step crash-safety protocol (implemented in `loan_manager/csv_manager.py::mark_paidoff`):

```
Step 1: Write reference_id to recovery.tmp
Step 2: Append record to history.csv
Step 3: Remove record from loans.csv (rewrite without the row)
Step 4: Delete recovery.tmp
```

On application startup, `MainWindow._check_recovery_file()` detects any stale `recovery.tmp`, `import_recovery.tmp`, or `approval_recovery.tmp` and alerts the user. Recovery is manual (user inspects history.csv and loans.csv) because automatic recovery would require knowing which step was interrupted, which requires the recovery file to encode step state — deferred as out of scope for prototype.

**Known Residual Risks (documented for future):**
1. Crash after Step 2 but before Step 3: record exists in both history.csv and loans.csv. Recovery: user manually removes from loans.csv.
2. Crash after Step 3 but before Step 4: stale recovery.tmp remains but data is consistent. Recovery: user dismisses warning, deletes recovery.tmp.
3. Crash before Step 1: no data loss, operation never started.
4. Timestamped backup of loans.csv before destructive operations (Paidoff, bulk Approve): deferred per R3 prototype scope note. [REVIEW REQUIRED: confirm deferral is still acceptable for prototype delivery.]

---

## 4. User-Testing Requirement 1 — Architectural Analysis

### Issue 1: Interest Calculator Filter Not Sticking (Dropdown Resets to "All")

**Observed Behaviour:** When the user selects a value in BorrowerGroup, BorrowerName, DepositorName, or DepositorGroup filter dropdowns and clicks "Apply Filters", the selected values appear to reset to "All".

**Root Cause Analysis:**

The `_on_apply_filters` method calls `_load_loans()` at the top of its execution:

```python
def _on_apply_filters(self) -> None:
    self._load_loans()           # <-- this calls _populate_filters()
    self._filtered_loans = self._get_filtered_loans()
    ...
```

`_load_loans()` calls `_populate_filters()`, which calls `_reset_combo()` on all four filter dropdowns. `_reset_combo` calls `combo.clear()` and then `combo.addItem("All")` followed by the data items. After `clear()`, the current index is reset to 0 ("All").

The issue is ordering: `_get_filtered_loans()` reads `currentText()` from the combos **after** `_populate_filters()` has already reset them to "All". The user's selection is overwritten before it can be read.

**Architectural Fix:**

Capture filter selections before reloading loans data. The corrected ordering:

```
1. Read current filter values from combos (before any reload)
2. Reload loans data from CSV
3. Repopulate filter dropdowns (this resets combo indices to 0)
4. Re-apply saved filter values to combos (restore user selection)
5. Apply filter logic using the restored combo values
```

This requires either:
- (a) Capturing `currentText()` of all combos at the start of `_on_apply_filters`, passing them directly to `_get_filtered_loans()` without re-reading from combos, OR
- (b) After `_populate_filters()`, programmatically set each combo's current index back to the captured value using `setCurrentText(saved_value)`.

Option (a) is cleaner: pass filter values as parameters to `_get_filtered_loans()` rather than reading them from widget state inside the function.

**Secondary issue:** `_load_loans()` is called on every filter application, which discards any manual edits the user may have made to the table before clicking Apply. This is by design per R5 (filters reload from CSV), but the combo-reset side effect is the bug.

---

### Issue 2: View Tab Color Palette — Poor Contrast (Light Background + White Text)

**Observed Behaviour:** The View Tab uses light pastel background colors for status rows (green, red, yellow, grey) with white text, making data unreadable.

**Root Cause Analysis:**

In `view_tab.py`, `STATUS_COLORS` defines background colors as:

```python
STATUS_COLORS = {
    "Active":  QColor("#d4edda"),  # light green
    "Overdue": QColor("#f8d7da"),  # light red/pink
    "Pending": QColor("#fff3cd"),  # light yellow
    "Paidoff": QColor("#e2e3e5"),  # light grey
}
```

These are Bootstrap-style alert background colors intended to be used with **dark text**. However, `QStandardItemModel` uses the system default text color (which on Windows 11 dark mode is white, and on certain Qt styles may also be white or light grey), creating near-zero contrast against these light backgrounds.

**Architectural Fix:**

The fix has two components:

1. **Set explicit foreground (text) color per status row.** Modify `_make_row` and the `item()` / `numeric_item()` helpers to call `it.setForeground(QColor("#212529"))` (near-black) for all items. This ensures dark text regardless of system theme.

2. **Strengthen background contrast.** The current pastel colors can be kept if dark foreground is applied. Alternatively, use higher-contrast backgrounds with proper text:

   | Status | Suggested Background | Suggested Foreground |
   |---|---|---|
   | Active | #198754 (Bootstrap success) or #d4edda (current) | #000000 |
   | Overdue | #dc3545 (Bootstrap danger) or #f8d7da (current) | #000000 |
   | Pending | #ffc107 (Bootstrap warning) or #fff3cd (current) | #000000 |
   | Paidoff | #6c757d (Bootstrap secondary) or #e2e3e5 (current) | #000000 |

   Note: The rules file (`coding-style.md`) prohibits purple hues in frontend. No purple is present in the current palette. Maintain this constraint.

3. **Defer dark-mode support.** Full Qt dark mode support (QPalette override) is not required for the prototype but is a future-facing risk on Windows 11 with dark system theme. [REVIEW REQUIRED: Confirm whether Windows end-user uses dark mode system theme.]

---

### Issue 3: Paidoff Flow Not Testable

**Observed Behaviour:** The user could not execute the "Mark Paidoff" flow during testing.

**Root Cause Analysis:**

The Paidoff action is accessible **only** via the right-click context menu in the View Tab (`_show_context_menu`). There is no toolbar button, keyboard shortcut, or Status column dropdown for triggering the paidoff flow.

Context menus are:
- Non-discoverable (users must know to right-click)
- On Windows, the right-click target area is the table row — if no row is selected or the click lands on empty space, `index.isValid()` returns False and the menu is silently suppressed.

Additionally, the Status column in `_make_row` sets `editable=False` for the status item:
```python
item(loan.status, editable=False),  # Status
```
A user expecting to change status via inline edit (as implied by R3: "User can toggle in between these states") would find the status column uneditable and have no indication that right-click is required.

**Architectural Fix:**

Two complementary fixes:

1. **Make Paidoff accessible without right-click.** Add a "Mark Paidoff" toolbar button that operates on the currently selected row, OR make the Status column editable via a `QComboBox` delegate that presents `[Active, Overdue, Pending, Paidoff]` options. When the user selects "Paidoff" from the combo, trigger the `PaidoffDialog` programmatically. This matches R3 requirement: "Leverage QComboBox for simplicity."

2. **Add a QItemDelegate for the Status column.** A `StatusDelegate(QStyledItemDelegate)` that returns a `QComboBox` as the editor widget. When the editor closes with "Paidoff" selected, the `_on_item_changed` handler intercepts this and opens `PaidoffDialog`. For Active override (R3: prompts for new due date), the handler opens `ExtendDialog`.

The `PaidoffDialog` itself is correctly implemented and takes `calendarPopup=True` on the `QDateEdit`, so the dialog UX is not the blocking issue.

**Note on R3 Status Transition Matrix:** The allowed transitions requiring dialog prompts:
- Any -> Paidoff: triggers PaidoffDialog
- Overdue -> Active (manual override): triggers ExtendDialog (new due date required)
- Any -> Active (not from Overdue): direct, no dialog needed

---

### Issue 4: Date Picker UX on Windows — Should Open on Field Click

**Observed Behaviour:** On the Windows machine, the date picker (`QDateEdit` with `setCalendarPopup(True)`) requires the user to click the small dropdown arrow button on the right side of the field. Clicking the text area of the field does not open the calendar.

**Root Cause Analysis:**

`QDateEdit.setCalendarPopup(True)` adds a small arrow button (QToolButton) to the right of the date field. By default in Qt, only clicking this specific arrow button opens the calendar popup. Clicking the text area focuses the field for keyboard editing but does not open the popup. On Windows with default Qt style (Fusion or Windows), this arrow button is small (~16px) and users expect clicking anywhere in the field to open the calendar.

This affects `entry_tab.py` (giving_date, due_date), `paidoff_dialog.py` (paidoff_date), and `dialogs/extend_dialog.py` if it contains a date field.

**Architectural Fix:**

Subclass `QDateEdit` with a custom `mousePressEvent` override that calls `self.calendarWidget().show()` or triggers the popup on any left-click within the widget bounds:

```python
class ClickableDateEdit(QDateEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            # Force open calendar popup on any click within the widget
            self.calendarWidget()  # ensures popup is initialised
            # Access the internal QToolButton and trigger it
            for child in self.children():
                from PySide6.QtWidgets import QToolButton
                if isinstance(child, QToolButton):
                    child.click()
                    break
```

Alternatively, install an event filter on the `QLineEdit` sub-widget of `QDateEdit`:

```python
date_edit.lineEdit().installEventFilter(self)
# In eventFilter:
# if obj == date_edit.lineEdit() and event.type() == QEvent.MouseButtonPress:
#     date_edit.calendarWidget().show() / trigger popup
```

A single `ClickableDateEdit` class should be created in `ui/widgets/clickable_date_edit.py` and used as a drop-in replacement for `QDateEdit` across all tabs and dialogs. This is the recommended approach to avoid repeating the fix in four locations.

---

## 5. Non-Functional Requirements

### Cross-Platform: Windows + macOS

| Requirement | Implementation |
|---|---|
| Path separators | `pathlib.Path` used throughout. No hardcoded `/` or `\` separators. |
| Virtual environment bootstrap | `run_windows.bat` (creates venv, installs requirements, launches main.py). `run_mac.sh` (equivalent for zsh/bash). Both check for Python 3.10+ and display upgrade message if lower version detected (R10). |
| CSV line endings | `newline=""` passed to all `open()` calls per Python csv module documentation. Produces `\r\n` on all platforms consistently. |
| File locking | Not required (R8: single user, no concurrent sessions). |
| Date picker behaviour | Windows-specific UX issue documented in Issue 4 above. Fix via `ClickableDateEdit` is cross-platform safe. |
| Font/DPI scaling | `QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)` should be set in `main.py` for Windows HiDPI displays. [REVIEW REQUIRED: confirm HiDPI is needed.] |
| Packaging | `requirements.txt` must pin PySide6 version to ensure consistent rendering on both platforms. openpyxl required for .xlsx import/export. python-dateutil required for `relativedelta` in interest_calculator. |

### Performance: max 1500 rows

| Operation | Expected Cost | Acceptable |
|---|---|---|
| Startup status recompute | O(N) reads + O(N) individual update_loan writes. At 1500 rows this is 1500 full-file rewrites. **This is O(N^2) and a known issue per R10.** | No — see below |
| Batch write fix (R10) | Replace per-loan `update_loan` loop with a single `batch_write_loans(loans)` call that rewrites the file once. | Required |
| View Tab load_data | Same O(N^2) issue in `view_tab.py::load_data` which also calls `update_loan` per loan. | Required fix |
| Single loan update | O(N) rewrite — acceptable. |  |
| Interest calculator filter | O(N) scan — acceptable for 1500 rows. |  |

**Batch Write Recommendation (R10):** Add `batch_update_loans(loans: List[Loan]) -> None` to `loan_manager/csv_manager.py`. This function reads all rows, builds an index by reference_id, applies updates in memory, then writes the entire file once. Replace the `for loan in updated: update_loan(loan)` patterns in `main_window._startup_recompute()` and `view_tab.load_data()` with single `batch_update_loans(updated)` calls.

### Single User, No Concurrency

No file locking, no session management, no conflict detection between sessions is required (R8). The recovery.tmp protocol handles intra-session crash safety only.

---

## 6. Component Dependency Map

```
main.py
  -> ui/main_window.py
       -> ui/entry_tab.py
            -> data/csv_manager.py (write_loan, read_autocomplete_values)
            -> data/ref_id_manager.py (generate_ref_id)
            -> data/status_engine.py (compute_status)
            -> models/loan.py
       -> ui/view_tab.py
            -> data/csv_manager.py (read_loans, update_loan, delete_loan, mark_paidoff, extend_loan)
            -> data/status_engine.py (compute_status, recompute_all)
            -> models/loan.py
            -> ui/dialogs/extend_dialog.py
            -> ui/dialogs/paidoff_dialog.py
       -> ui/interest_calculator_tab.py
            -> data/csv_manager.py (read_loans)
            -> loan_manager/interest_calculator.py (calculate_monthly, calculate_daily, calculate_both)
            -> models/loan.py
       -> ui/pending_approval_tab.py
            -> data/report_manager.py (read_pending_reports, mark_approved, mark_declined)
            -> data/csv_manager.py (batch_extend_loans)
            -> loan_manager/interest_calculator.py (recalculate on inline edit)
            -> models/loan.py

loan_manager/ (no imports from ui/ or data/)
  status_engine.py -> models/loan.py
  interest_calculator.py -> dateutil.relativedelta
  csv_manager.py -> models/loan.py, loan_manager/ref_id_manager.py
  ref_id_manager.py -> (stdlib only)
  report_manager.py -> models/report.py

data/ (re-exports or thin adapters of loan_manager/)
  status_engine.py -> loan_manager/status_engine.py
  csv_manager.py -> loan_manager/csv_manager.py
  ref_id_manager.py -> loan_manager/ref_id_manager.py
  report_manager.py -> loan_manager/report_manager.py
  export_service.py -> openpyxl, models/loan.py
  import_service.py -> openpyxl, loan_manager/csv_manager.py, loan_manager/ref_id_manager.py
```

---

## 7. Open Items and Deferred Decisions

| ID | Item | Status |
|---|---|---|
| OI-001 | Timestamped backup of loans.csv before destructive operations | Deferred per R3 prototype scope. [REVIEW REQUIRED] |
| OI-002 | Excel-style hierarchical column filter (year->month->date) in View Tab | Not yet implemented. [REVIEW REQUIRED: confirm acceptable for prototype.] |
| OI-003 | HiDPI scaling attribute in main.py for Windows | [REVIEW REQUIRED: confirm needed.] |
| OI-004 | QTableWidget vs QTableView for Pending Approval tab growth | [REVIEW REQUIRED: acceptable if queue < 50 reports.] |
| OI-005 | batch_update_loans implementation (O(N^2) write fix, R10) | Required before delivery. Not yet implemented. |
| OI-006 | ClickableDateEdit widget to fix Windows date picker UX | Required fix. Not yet implemented. |
| OI-007 | Status column QComboBox delegate in View Tab for discoverability of Paidoff flow | Required fix per Issue 3 analysis. |
| OI-008 | Explicit foreground color (#000000) on all status-colored rows in View Tab | Required fix per Issue 2 analysis. |
| OI-009 | Interest calculator filter capture-before-reload fix | Required fix per Issue 1 analysis. |
| OI-010 | Windows end-user dark mode system theme compatibility | [REVIEW REQUIRED: confirm user's system theme.] |
