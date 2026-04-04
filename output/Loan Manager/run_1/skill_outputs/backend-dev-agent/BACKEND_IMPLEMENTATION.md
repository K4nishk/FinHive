# Backend Implementation Specification — Loan Manager
**Run:** run_1 | **Wave:** 2 | **Date:** 2026-04-03
**Role:** Backend Developer Agent

---

## Table of Contents

1. [User-Testing Requirement 1 — Code-Level Fix Specs](#1-user-testing-requirement-1--code-level-fix-specs)
2. [Backend Service Specs (loan_manager/)](#2-backend-service-specs)
3. [Data Layer Spec (data/)](#3-data-layer-spec)
4. [Backend QA Sync](#4-backend-qa-sync)
5. [Planning-Phase Code Snippet — Filter Fix](#5-planning-phase-code-snippet--filter-fix)

---

## 1. User-Testing Requirement 1 — Code-Level Fix Specs

### Bug 1: Interest Calculator Filter Not Sticking

**Root Cause Identified**

In `ui/interest_calculator_tab.py`, `_on_apply_filters()` (line 264) calls `_load_loans()` first, which calls `_populate_filters()`. Inside `_populate_filters()`, `_reset_combo()` calls `combo.clear()` then `combo.addItem("All")`. Critically, after `clear()` the combo's `currentText()` resets to `""` (empty) and then to `"All"` after `addItem("All")`. This `currentText` reset happens **before** `_get_filtered_loans()` is called on line 267.

The sequence inside `_on_apply_filters` is:
1. `_load_loans()` → `_populate_filters()` → all four filter combos are cleared and rebuilt with `blockSignals(True)` — so the combo's **stored selection** is lost and returns to `"All"`.
2. `_get_filtered_loans()` then reads `currentText()` on all four combos — which now all read `"All"`.

Result: every filter selection made by the user is destroyed by the reload step before the filter is evaluated.

**Exact Location**
- File: `ui/interest_calculator_tab.py`
- Method: `_on_apply_filters()` (lines 264–270) and `_populate_filters()` (lines 243–262)

**Fix Specification**

Snapshot the user's current filter selections BEFORE calling `_load_loans()`, then restore those selections after `_populate_filters()` has rebuilt the combo contents. The restored values need to be set with `blockSignals(True)` to avoid triggering the mode-changed or any incidental slot.

Step-by-step changes:

1. In `_on_apply_filters()`, capture the five current filter values before calling `_load_loans()`.
2. After `_load_loans()` (which calls `_populate_filters()` and resets everything), re-apply the saved selections to each combo using `setCurrentText()` inside a `blockSignals(True)` / `blockSignals(False)` guard.
3. Then call `_get_filtered_loans()` and `_populate_table()`.

Function signatures are unchanged; only the body of `_on_apply_filters` needs modification. See Section 5 for the representative code snippet.

**No change is needed** to the underlying filter logic in `_get_filtered_loans()` — that logic is correct. The problem is purely the ordering of operations in `_on_apply_filters`.

---

### Bug 2: View Tab Color Palette — Poor Contrast

**Root Cause Identified**

In `ui/view_tab.py`, `STATUS_COLORS` (lines 73–78) maps statuses to light pastel background colors:

```
STATUS_COLORS = {
    "Active":  QColor("#d4edda"),   # light green — background
    "Overdue": QColor("#f8d7da"),   # light red — background
    "Pending": QColor("#fff3cd"),   # light yellow — background
    "Paidoff": QColor("#e2e3e5"),   # light grey — background
}
```

No foreground (text) color is set in `_make_row`. The default Qt text color on many platforms is white or near-white when the application uses a dark system theme, making text on these pale pastel backgrounds nearly invisible.

**Fix Specification**

Two complementary changes:

**Change A — Set explicit foreground color on every cell item.**

In `_make_row()`, after setting the background on each `QStandardItem`, also call `it.setForeground(QColor("#1a1a1a"))` (near-black) unconditionally. This decouples text visibility from the platform theme.

Status-specific foreground pairings to use:

| Status  | Background | Foreground |
|---------|-----------|------------|
| Active  | `#1e4d2b` (dark green) | `#e8f5e9` (light green-white) |
| Overdue | `#7b1c24` (dark red)   | `#fde8ea` (light pink-white)  |
| Pending | `#6b5900` (dark amber) | `#fff8dc` (light cream)       |
| Paidoff | `#3a3a3a` (dark grey)  | `#e0e0e0` (light grey)        |

Rationale: dark backgrounds + light text gives high contrast (WCAG AA equivalent) on both Windows default and dark-mode themes, and avoids the light-on-light failure mode entirely.

**Change B — Status colors dict update.**

Replace `STATUS_COLORS` with a paired structure:

```python
STATUS_COLORS: dict[str, tuple[QColor, QColor]] = {
    "Active":  (QColor("#1e4d2b"), QColor("#e8f5e9")),
    "Overdue": (QColor("#7b1c24"), QColor("#fde8ea")),
    "Pending": (QColor("#6b5900"), QColor("#fff8dc")),
    "Paidoff": (QColor("#3a3a3a"), QColor("#e0e0e0")),
}
```

In `_make_row()`, unpack both colors:

```python
bg_color, fg_color = STATUS_COLORS.get(loan.status, (QColor("#2b2b2b"), QColor("#f0f0f0")))
```

Then apply both on each `QStandardItem` via `it.setBackground(bg_color)` and `it.setForeground(fg_color)`.

**Files to modify:**
- `ui/view_tab.py`: `STATUS_COLORS` constant + `_make_row()` method (the `item()` and `numeric_item()` inner functions)

---

### Bug 3: Paidoff Flow Not Testable

**Root Cause Identified**

After code review, the Paidoff dialog chain itself is correctly wired:

- `_action_paidoff(loan)` in `view_tab.py` (lines 345–357) correctly instantiates `PaidoffDialog`, calls `dialog.exec()`, reads `dialog.paidoff_date()`, and calls `mark_paidoff(loan.reference_id, ...)`.
- `PaidoffDialog` (in `ui/dialogs/paidoff_dialog.py`) has `setCalendarPopup(True)`, a functional `_on_accept()` that writes `self._paidoff_date`, and correct `accept()` call.
- `data.csv_manager.mark_paidoff()` implements the full four-step atomic protocol.

The most likely reason the user "was unable to test out marking a record as Paidoff" is **the context menu not appearing or being difficult to trigger**. The context menu is the ONLY path to `_action_paidoff` — there is no button. On Windows, right-click on `QTableView` rows is not always obvious, especially when the view has `SelectionBehavior.SelectRows` active.

**Secondary candidate bug:** The `PaidoffDialog` has no `setCalendarPopup(True)` note for the date picker on Windows — but it does have it (`self._date_edit.setCalendarPopup(True)` at line 50). That path is fine.

**Tertiary candidate bug — status field non-editable:** In `view_tab.py`, `COL_STATUS` is set with `editable=False` in `_make_row()` (line 199). There is no `QComboBox` for status toggling inline as R3 requires (`Leverage QComboBox for simplicity`). The `_on_item_changed` handler also has no branch for `COL_STATUS` (lines 225–245). So the user cannot toggle status to Paidoff via the table at all — the only path is right-click context menu.

**Fix Specification (two-part)**

**Part A — Add a "Mark Paidoff" toolbar/action button** to make discoverability obvious. This is a UI change but needed for testability. Add a `QPushButton("Mark Paidoff")` to the toolbar row in `_build_ui()` that is enabled only when a row is selected. Connect it to `_action_paidoff()` for the selected row.

**Part B — Add a status QComboBox delegate** (the full R3 requirement). This requires a `QStyledItemDelegate` subclass for `COL_STATUS` that renders a `QComboBox` with items `["Active", "Overdue", "Pending", "Paidoff"]`. When the user selects `"Paidoff"`, the delegate triggers `_action_paidoff`. When the user selects `"Active"` on an Overdue loan, trigger the Extend flow. This is the authoritative fix per R3.

For the immediate user-testing fix (unblocking), Part A alone is sufficient and lower risk. Part B is the full R3 implementation.

**Files to modify:**
- `ui/view_tab.py`: `_build_ui()` toolbar section, add selection-aware Paidoff button; connect to `_action_paidoff`.

---

### Bug 4: Date Picker Not Opening on Click (Entry Tab, Windows)

**Root Cause Identified**

In `ui/entry_tab.py`, both `self._giving_date` and `self._due_date` are `QDateEdit` instances with `setCalendarPopup(True)` (lines 72–73 and 82–83). This is correct for enabling the calendar dropdown button.

However, `setCalendarPopup(True)` only makes the **drop-down arrow button** functional — it does NOT make clicking anywhere on the `QDateEdit` field open the calendar. On Windows, the user must click the small arrow button at the right edge of the field. Users accustomed to spreadsheet date pickers (which open on any click of the cell) find this unintuitive.

The requirement states: "the date picker should show up whenever the field is clicked."

**Fix Specification**

Install a `mousePressEvent` override (via `eventFilter`) on both `QDateEdit` widgets so that a single click anywhere on the field calls `self.calendarWidget().show()` via `QDateEdit.calendarWidget()`, or equivalently calls `QDateEdit.showEvent` trigger.

The PySide6-specific and cross-platform reliable approach is to subclass `QDateEdit` or install an event filter:

```python
class ClickableDateEdit(QDateEdit):
    """QDateEdit that opens the calendar popup on any mouse press."""

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if self.calendarPopup():
            # Show the calendar immediately on any click within the widget
            popup = self.calendarWidget()
            if popup is not None and not popup.isVisible():
                # Trigger the drop-down the same way the arrow button does
                self.showPopup()
```

`QDateEdit` inherits `showPopup()` from `QAbstractSpinBox`. Calling `self.showPopup()` in `mousePressEvent` replicates exactly what the arrow button does.

**Alternative (no subclass) — event filter on existing widgets:**

```python
class _DateEditClickFilter(QObject):
    def eventFilter(self, obj, event) -> bool:
        if isinstance(obj, QDateEdit) and event.type() == QEvent.Type.MouseButtonPress:
            if obj.calendarPopup():
                obj.showPopup()
        return super().eventFilter(obj, event)
```

Then install: `self._giving_date.installEventFilter(self._date_click_filter)`.

**Recommended approach:** Create `ClickableDateEdit` as a small internal class inside `entry_tab.py` (and replicate for `paidoff_dialog.py`). Replace `QDateEdit()` instantiation with `ClickableDateEdit()` at lines 71 and 82 of `entry_tab.py` and line 49 of `paidoff_dialog.py`.

**Files to modify:**
- `ui/entry_tab.py`: Replace `QDateEdit` with `ClickableDateEdit` at lines 71 and 82.
- `ui/dialogs/paidoff_dialog.py`: Replace `QDateEdit` with `ClickableDateEdit` at line 49 (consistent UX).
- The `ClickableDateEdit` class can live in a new small `ui/widgets.py` shared utility file, or be defined locally in each module.

---

## 2. Backend Service Specs

### Backend Service: StatusEngine

**Current state:** Implemented — canonical, authoritative.

**File:** `loan_manager/status_engine.py`

**Assessment:** Implementation is correct and complete. Covers all boundary conditions (BC-01 confirmed):
- `Paidoff` is never auto-recomputed.
- `Pending` when `giving_date > today`.
- `Active` when `giving_date <= today < due_date`.
- `Overdue` when `due_date <= today` or no `due_date` with `giving_date <= today`.

**Required changes:**
- None to core logic.
- [REVIEW REQUIRED] The `recompute_all` function mutates the `Loan.status` field in-place for dataclass instances (line 102: `loan.status = new_status`). This is intentional per the docstring ("the original list items are NOT mutated" is contradicted by the actual code for `Loan` objects). The docstring claim is incorrect for the `Loan` branch. Clarify or fix the docstring to match actual behavior.

**Function signatures (current, confirmed correct):**

```python
def compute_status(
    loan: Optional[Loan] = None,
    today: Optional[date] = None,
    *,
    giving_date: Optional[date] = None,
    due_date: Optional[date] = None,
    current_status: Optional[str] = None,
) -> str:
    """Compute auto-derived status for a loan based on today's date."""

def recompute_all(
    loans: List[LoanLike],
    today: date,
) -> List[LoanLike]:
    """Recompute status for all non-Paidoff loans and return updated list."""
```

**Error conditions:**
- `giving_date is None`: raises `ValueError` — correct behavior.
- `today is None` in keyword-arg convention: raises `ValueError` — correct behavior.
- Unknown status value (not `"Paidoff"`): treated as non-Paidoff and recomputed — acceptable, no additional guard needed.

---

### Backend Service: InterestCalculator

**Current state:** Implemented — correct per BC-05 Interpretation B (Time = extension_period only).

**File:** `loan_manager/interest_calculator.py`

**Assessment:** All three calculator functions (`calculate_monthly`, `calculate_daily`, `calculate_both`) are correct. The BC-05 interpretation is confirmed: Time = extension_period, not derived from date arithmetic. `giving_date` and `due_date` are passed through for compatibility but do not affect calculations.

**Required changes:**
- None to calculation logic.
- Minor: `months_between()` docstring example states "2026-01-15 to 2026-02-16 = 2 months" but the comment says "1 month + 1 day, rounded up". The result is 2 (rounded up from 1m+1d), which is correct. The docstring phrasing is confusing — should say "rounds up to 2". Low priority.

**Function signatures (current, confirmed correct):**

```python
def months_between(giving_date: date, due_date: date) -> int:
    """Return number of complete months between dates, partial months rounded UP."""

def days_between(giving_date: date, due_date: date) -> int:
    """Return number of calendar days between giving_date and due_date."""

def calculate_monthly(record: dict) -> dict:
    """Compute interest/commission/TDS for Monthly mode. Returns enriched record dict."""

def calculate_daily(record: dict) -> dict:
    """Compute interest/commission/TDS for Daily mode. Returns enriched record dict."""

def calculate_both(record: dict) -> dict:
    """Orchestrator for Mode=Both. Routes by extension_period_unit."""
```

**Error conditions:**
- `calculate_both` with unknown `extension_period_unit`: raises `ValueError` — correct.
- `extension_period = 0`: produces `interest_amount = 0.0`, `commission_amount = 0.0` — mathematically correct, no guard needed.
- Missing `amount` key: raises `KeyError` — caller (`_on_calculate` in the UI) catches `KeyError` at line 442. Acceptable at current scope.

---

### Backend Service: RefIdManager

**Current state:** Implemented — complete.

**File:** `loan_manager/ref_id_manager.py`

**Assessment:** Implementation is correct. Handles the high-water mark counter, 3-digit zero-padding up to 999, un-padded beyond 999, and BOM-tolerant CSV reading (`utf-8-sig`). Reset-counter logic correctly deletes the key from the meta dict.

**Required changes:**
- None to core logic.
- [REVIEW REQUIRED] `_read_meta()` uses a bare `except Exception` at line 101 (`logger.warning("Could not read meta CSV...")`). Per project coding standards this should be narrowed to specific exceptions (`OSError`, `csv.Error`). Change to `except (OSError, csv.Error) as exc:`.

**Function signatures (current, confirmed correct):**

```python
class RefIdManager:
    def __init__(self, meta_path: Path) -> None: ...

    def next_ref_id(self, year: int, month: int) -> str:
        """Return the next reference_id for the given year and month."""

    def reset_counter(self, year: int, month: int) -> None:
        """Reset the counter for the given year/month bucket to zero."""
```

**Error conditions:**
- Meta CSV absent: returns empty dict (starts from 001) — correct per R4.
- Corrupted counter value: defaults to `0` (next will be `001`) — acceptable.
- File write failure: propagates `OSError` — acceptable, callers should log.

---

### Backend Service: CSVReportManager

**Current state:** Implemented — complete.

**File:** `loan_manager/report_manager.py`

**Assessment:** Two-file normalized storage (PD-06), report_id generation (PD-07/PD-15), Declined records retained with status (PD-16), batch approval model (PD-18), and duplicate ref_id detection (PD-19) are all implemented.

**Required changes:**

1. **Exception handling narrowing:** `read_pending_reports()` line 169 uses bare `except Exception`. Narrow to `(ValueError, KeyError)` — those are the expected parsing failures from `PendingReport.from_csv_row()`.

2. **`get_active_reference_ids_in_queue` scope issue:** The method returns ref_ids from ALL pending reports including the one being approved. The calling code in `pending_approval_tab.py` (lines 549–568) correctly compensates with set subtraction to isolate other-report IDs — but this logic is fragile (see comments in the UI code at lines 554–567 showing confusion). Consider adding a `exclude_report_id: Optional[str] = None` parameter to this method to make the exclusion explicit at the service layer.

**Function signatures (current, with proposed addition):**

```python
def get_active_reference_ids_in_queue(
    self,
    reports_path: Path,
    records_path: Path,
    exclude_report_id: Optional[str] = None,  # NEW: exclude this report from the result
) -> set[str]:
    """Return ref_ids in any Pending report, optionally excluding one report."""
```

**Error conditions:**
- `update_report_status` with unknown `report_id`: logs warning, writes file with no changes — no exception raised. Acceptable (no-op semantics documented).
- `delete_report_records` with unknown `report_id`: silently rewrites file unchanged — acceptable.
- `write_report_records` with empty list: logs `n/a` for report_id — low priority cosmetic issue.

---

### Backend Service: CSVManager (loan_manager layer)

**Current state:** Implemented — complete.

**File:** `loan_manager/csv_manager.py`

**Assessment:** Injectable-path class API. All CRUD operations, atomic `mark_paidoff` (four-step protocol), `extend_loan` (with no-due-date branch), and `batch_extend_loans` (single-pass rewrite) are implemented.

**Required changes:**

1. `_write_raw()` at line 40 opens the file using `open(str(path), ...)` instead of `path.open(...)`. Inconsistent with `_read_raw()` which uses `path.open()`. Normalize to `path.open()` for consistency.

2. `_append_raw()` at line 46 same issue — uses `open(str(path), ...)`.

3. `extend_loan()` at line 186 has an inline `from datetime import timedelta` inside the loop body. Move this import to the module level.

**Function signatures (confirmed correct, no signature changes):**

```python
def read_loans(self, loans_path: Path) -> list[dict]: ...
def write_loan(self, loans_path: Path, loan: dict) -> None: ...
def update_loan(self, loans_path: Path, reference_id: str, updated_fields: dict) -> None: ...
def delete_loan(self, loans_path: Path, reference_id: str) -> None: ...
def mark_paidoff(self, loans_path: Path, history_path: Path, reference_id: str, paidoff_date: date) -> None: ...
def extend_loan(self, loans_path: Path, reference_id: str, period: int, unit: str, today: Optional[date] = None, new_due_date: Optional[date] = None) -> None: ...
def batch_extend_loans(self, loans_path: Path, extensions: list[dict]) -> None: ...
```

**Error conditions:**
- `mark_paidoff` with unknown `reference_id`: returns early (no-op) — correct.
- `extend_loan` with no matching row: silently rewrites unchanged — acceptable, consistent with other methods.
- Recovery `.tmp` write failure in `mark_paidoff`: propagates exception — correct (operation aborted before any mutation).

---

## 3. Data Layer Spec

### data/csv_manager.py

**Current state:** Implemented — application-layer adapter with path resolution.

**Assessment:** This module correctly resolves the `./data/` path and delegates to `loan_manager.CSVManager` for batch operations. Direct CRUD functions (`read_loans`, `write_loan`, `update_loan`, `delete_loan`, `mark_paidoff`, `extend_loan`) are implemented here directly (not as pass-throughs), which creates slight duplication with `loan_manager/csv_manager.py`.

**Required changes:**

1. **`_read_all_rows()` bare except (line 74):** `except Exception as exc:` should be narrowed to `except (OSError, csv.Error) as exc:`.

2. **`delete_loan()` bare except at counter reset (line 183):** `except Exception as exc:` should be narrowed to `except (ValueError, OSError) as exc:`.

3. **`mark_paidoff()` — missing `_ensure_loans_csv()` guard:** The function calls `_read_all_rows(_loans_path())` without calling `_ensure_loans_csv()` first. If `loans.csv` does not exist, `_read_all_rows` returns `[]` and `target_row` is `None`, raising a `ValueError("reference_id not found")`. This is a correct error but confusing. Add `_ensure_loans_csv()` call at the top of `mark_paidoff()` for consistency with `read_loans()` and `write_loan()`.

4. **`batch_extend_loans()` (line 291):** Currently delegates to `loan_manager.CSVManager().batch_extend_loans()`. This creates an inconsistency: other functions in this module do their own I/O, but `batch_extend_loans` creates a fresh `CSVManager` instance. This is fine for correctness but inconsistent. [REVIEW REQUIRED] Consider whether all data-layer functions should be pure pass-throughs to a module-level `CSVManager` instance or all direct implementations.

**No function signature changes required.**

---

### data/report_manager.py

**Current state:** Implemented — thin adapter, correct.

**Assessment:** All functions correctly delegate to `_manager = CSVReportManager()` module-level singleton and resolve paths via `_data_dir()`. The adapter is clean.

**Required changes:**

1. If `CSVReportManager.get_active_reference_ids_in_queue()` gains the `exclude_report_id` parameter (proposed in Section 2), update the adapter function signature to match:

```python
def get_active_reference_ids_in_queue(
    exclude_report_id: Optional[str] = None,
) -> set[str]:
    """Return ref_ids in any Pending report, optionally excluding one report."""
    return _manager.get_active_reference_ids_in_queue(
        _reports_path(), _records_path(), exclude_report_id=exclude_report_id
    )
```

2. All adapter functions currently have no logging. Consider adding `logger.debug()` calls at entry points for traceability during testing. [REVIEW REQUIRED] Low priority.

---

### data/import_service.py

**Current state:** Implemented — complete per R6/PD-35/RR-001.

**Assessment:** Atomic recovery sentinel, malformed-row skip with WARNING log, upsert-with-priority, collision-increment loop, and `parse_rows()` public preview API are all implemented.

**Required changes:**

1. **`_assign_unique_ref_id()` potential infinite loop (line 142–146):** The while loop increments by calling `generate_ref_id()` which always advances the high-water counter. If the CSV is corrupt and `existing_ref_ids` contains every possible ID for a month (pathological), this loops indefinitely. Wrap with a bounded iteration guard:

```python
def _assign_unique_ref_id(today: date, existing_ref_ids: set[str]) -> str:
    """Generate a unique ref_id, incrementing until non-colliding (PD-26)."""
    max_attempts = 10000
    for _ in range(max_attempts):
        ref_id = generate_ref_id(today.year, today.month)
        if ref_id not in existing_ref_ids:
            return ref_id
    raise RuntimeError(
        f"Could not find a non-colliding ref_id after {max_attempts} attempts"
    )
```

2. **`_parse_xlsx()` bare except equivalent:** `openpyxl.load_workbook` can raise `InvalidFileException` or `zipfile.BadZipFile`. Currently no exception handling in `_parse_xlsx`. Wrap with `except Exception as exc: raise ValueError(f"Failed to parse XLSX: {exc}") from exc`.

3. **`_row_to_loan()` bare except (line 174):** `except Exception as exc:` — narrow to `(ValueError, KeyError, TypeError) as exc:`.

4. **`import_loans()` recovery file delete (lines 113–116):** Currently in `finally` block which is correct. The recovery file is always deleted even on exception. However, on exception the partial writes may have occurred. The startup recovery check (`main_window._check_recovery_file()`) is mentioned in the docstring but its implementation is external to this file. [REVIEW REQUIRED] Verify the startup check is implemented in `main_window.py`.

---

### data/export_service.py

**Current state:** Implemented — atomic write via `os.replace()`.

**Assessment:** Both `export_to_csv()` and `export_to_xlsx()` correctly use temp-file-then-replace for atomic writes. Caller is responsible for filtering out Paidoff records (documented in docstrings).

**Required changes:**

1. **`export_to_xlsx()` temp file extension `.tmp.xlsx` (line 60):** On Windows, `os.replace()` of a `.tmp.xlsx` to `.xlsx` works but leaves the temp file if the process is killed after `wb.save()` but before `os.replace()`. The temp file name is distinct (different extension), so it is detectable. Low priority but add a startup cleanup for orphaned `.tmp.xlsx` files. [REVIEW REQUIRED]

2. **`export_to_csv()` and `export_to_xlsx()` — no logging on `IOError`:** The `IOError` for missing parent directory is raised but not logged. Add `logger.error()` before the raise.

3. **Type annotation for `loans` parameter:** Both functions accept `List[Loan]`. Add return type `None` annotations (they are missing in the signatures).

```python
def export_to_csv(file_path: Path, loans: List[Loan]) -> None: ...
def export_to_xlsx(file_path: Path, loans: List[Loan]) -> None: ...
```

These are already effectively `None`-returning but explicit annotations are required per project convention.

---

## 4. Backend QA Sync

```
## Backend Dev -> Backend QA Sync: Loan Manager

**Status:** Planning

**What I'm building:**

Four user-testing bug fixes and hardening changes across the service and data layers.

Bug fixes (all in Wave 2):
1. Interest Calculator filter reset fix — _on_apply_filters() selection snapshot/restore pattern
2. View Tab contrast fix — STATUS_COLORS changed to dark-bg/light-fg paired tuples
3. Paidoff flow discoverability fix — toolbar button added to ViewTab + R3 status delegate (deferred)
4. Date picker click-to-open fix — ClickableDateEdit subclass for entry_tab.py and paidoff_dialog.py

Service-layer hardening:
- Narrow bare except clauses in: ref_id_manager._read_meta(), csv_manager.CSVManager._write_raw/_append_raw, data.csv_manager._read_all_rows(), data.csv_manager.delete_loan(), import_service._row_to_loan()
- Add exclude_report_id param to get_active_reference_ids_in_queue (fixes fragile set subtraction in PendingApprovalTab)
- Add iteration guard to import_service._assign_unique_ref_id()
- Fix recompute_all docstring (claims no mutation but Loan branch mutates in-place)
- Fix data.csv_manager.mark_paidoff() missing _ensure_loans_csv() guard

**Data model changes:**
- No schema changes to CSV files.
- STATUS_COLORS in view_tab.py changes from dict[str, QColor] to dict[str, tuple[QColor, QColor]] — UI-only change, no persistence impact.
- get_active_reference_ids_in_queue signature gains optional exclude_report_id: Optional[str] = None — backwards compatible.

**Error conditions to test:**

Service layer:
- RefIdManager: meta CSV absent -> first ID is YYYY_MM_001
- RefIdManager: meta CSV corrupt -> starts from 001 (no exception)
- CSVManager.mark_paidoff: unknown reference_id -> no-op return (not ValueError at data layer, ValueError at loan_manager layer — verify which layer is used by UI)
- CSVManager.batch_extend_loans: empty extensions list -> no-op rewrite
- import_service: all rows malformed -> returns ImportResult(inserted=0, updated=0, skipped=N)
- import_service: XLSX with openpyxl not installed -> ImportError propagates to UI
- export_service: parent directory missing -> IOError raised

Data layer:
- read_loans with Paidoff rows -> Paidoff rows excluded from result
- read_all_loans_including_paidoff -> all rows returned including Paidoff
- delete_loan with last record for YYYY_MM -> counter reset triggered

UI / integration:
- Filter fix: select borrower_group, click Apply -> filter persists through _load_loans()
- Filter fix: select all 5 filters simultaneously -> all persist
- Paidoff flow: right-click -> Mark Paidoff -> dialog opens -> date entered -> OK -> record removed from view
- Paidoff flow: toolbar Paidoff button (new) -> same flow
- Date picker: single click anywhere on QDateEdit -> calendar popup opens
- Status colors: all four status rows readable on Windows with default (light) theme and dark theme

**Proposed test scope:**
- [ ] test_filter_selection_preserved_after_load_loans: mock _load_loans, assert currentText() unchanged after _on_apply_filters
- [ ] test_filter_all_five_simultaneously: set all 5 filters, apply, assert filtered_loans matches expected subset
- [ ] test_paidoff_dialog_accept_date: QTest.mouseClick OK, assert paidoff_date() == selected date
- [ ] test_paidoff_action_removes_from_view: mock mark_paidoff, assert load_data called after
- [ ] test_clickable_date_edit_opens_popup: QTest.mouseClick widget body, assert calendarWidget().isVisible()
- [ ] test_status_colors_foreground_set: for each status, assert item.foreground().color() != QColor("white")
- [ ] test_get_active_ref_ids_excludes_report: pass exclude_report_id, assert that report's IDs not in result
- [ ] test_assign_unique_ref_id_max_attempts: patch generate_ref_id to always return same id, assert RuntimeError after 10000 attempts
- [ ] test_recompute_all_mutates_loan_status: confirm Loan.status is updated in-place (document actual behavior)
```

---

## 5. Planning-Phase Code Snippet — Filter Fix

The most complex change is Bug 1 (Interest Calculator filter reset). The fix requires careful ordering to preserve user selections through the `_load_loans()` / `_populate_filters()` cycle.

This snippet shows the approach for `_on_apply_filters()` in `ui/interest_calculator_tab.py`:

```python
def _on_apply_filters(self) -> None:
    """Apply current filter selections and populate the records table.

    Fix for User-Testing Requirement 1 (filter not sticking):
    Snapshot filter selections BEFORE _load_loans() destroys them via
    _populate_filters() clear+rebuild, then restore after rebuild.
    """
    # Step 1: Snapshot current selections before any reload
    saved_bg = self._filter_borrower_group.currentText()
    saved_bn = self._filter_borrower_name.currentText()
    saved_dn = self._filter_depositor_name.currentText()
    saved_dg = self._filter_depositor_group.currentText()
    saved_month = self._filter_by_month.currentText()

    # Step 2: Reload loans from CSV (calls _populate_filters internally,
    # which clears and rebuilds all combos -> resets selections to "All")
    self._load_loans()

    # Step 3: Restore saved selections now that combos are rebuilt.
    # Use blockSignals to avoid triggering _on_mode_changed or other slots.
    for combo, saved in (
        (self._filter_borrower_group, saved_bg),
        (self._filter_borrower_name, saved_bn),
        (self._filter_depositor_name, saved_dn),
        (self._filter_depositor_group, saved_dg),
        (self._filter_by_month, saved_month),
    ):
        combo.blockSignals(True)
        combo.setCurrentText(saved)
        # If saved value no longer exists in the repopulated combo
        # (e.g., all loans for that group were deleted), setCurrentText
        # will silently fall back to the first item ("All"), which is
        # the correct degraded behavior.
        combo.blockSignals(False)

    # Step 4: Now evaluate filters against the restored selections
    self._filtered_loans = self._get_filtered_loans()
    self._populate_table(self._filtered_loans)
    self._calculated = False
    self._btn_generate.setEnabled(False)
```

**Why `setCurrentText` is safe here:** If the saved value no longer exists in the combo (e.g., a borrower group was deleted from the data since the user last loaded the tab), `setCurrentText` performs a no-op and the combo remains at `"All"`. This is the correct graceful-degradation behavior — no crash, no stale filter applied.

**Why `blockSignals` is needed on the combos:** The filter combos do not have `currentTextChanged` connected to any slot in the current code, so `blockSignals` is technically redundant here. However, it is a defensive guard against future signal connections being added and should remain.

**The `_filter_by_month` combo does not go through `_populate_filters()`** (months are static) — but it is still snapshotted and restored for consistency and future-proofing.

---

*End of BACKEND_IMPLEMENTATION.md*
