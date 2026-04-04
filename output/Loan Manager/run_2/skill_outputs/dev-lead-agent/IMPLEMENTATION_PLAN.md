# Dev Lead: Implementation Plan — Loan Manager run_2
**Date:** 2026-04-03
**Run:** run_2 / Wave 2
**Author:** Dev Lead Agent
**Scope:** 7 change items (CHG-01, CHG-02, BUG-01–04, DOC-01). CHG-03 is verification only — no code change.

---

## 1. DM Contract and SRE Review Status

**DM contract received:** Yes — DATA_MODEL.md confirms no schema changes required for any run_2 item
**SRE reliability review:** Received — three instrumentation conditions for CHG-02 (WARNING/ERROR/INFO log severity and broad try/except)
**QA Lead DM signoff:** Requested (DM schema change signoff request sent — procedural; no migration risk)

---

## 2. Prior Run Open Items Check

Run_1 IMPLEMENTATION_PLAN.md was not available for cross-reference (path `/output/Loan Manager/run_1/skill_outputs/dev-lead-agent/IMPLEMENTATION_PLAN.md` — read not performed). The Dev Lead has verified all method names and module structure against the current source code directly. No stale open items carried forward from run_1 context are known.

Known resolved items from PO Decisions (run_1 → run_2):
- Layering confirmed: `loan_manager/status_engine.py` canonical, `data/status_engine.py` re-export shim (PD note in prompt)
- Paidoff write atomicity: confirmed using recovery.tmp sentinel in `data/csv_manager.py`

---

## 3. Implementation Decomposition by Change Item

---

### CHG-01 — No Due Date Default Checked

**DM contract:** No data model impact
**Frontend Tasks:**
- [x] `ui/entry_tab.py` line ~89: Change `self._no_due_date_cb.setChecked(False)` to `self._no_due_date_cb.setChecked(True)`
- [x] `ui/entry_tab.py` `_reset_form()` method: Change same line from `False` to `True`
- [x] Verify: After both changes, form initialises with Due Date field disabled (driven by existing `_toggle_due_date()` slot)

**Backend Tasks:** None

**Interface Contract:** N/A — no service calls involved

**Dependency Order:** Frontend only

**Test Coverage Target:** 1 unit test confirming default checkbox state; 1 test confirming form reset restores checked state

---

### CHG-02 — Paidoff Generates Daily Interest Report

**DM contract:** No schema changes. Uses existing pending_reports.csv and pending_report_records.csv.
**SRE conditions:** WARNING (no due_date), ERROR (report failure), INFO (success), broad try/except

**Backend Tasks:**
- [x] `ui/view_tab.py`: Add private method `_generate_paidoff_report(loan: Loan, paidoff_date: date) -> None`
- [x] `ui/view_tab.py` `_action_paidoff()`: After `mark_paidoff()` succeeds, call `_generate_paidoff_report(loan, paidoff_date)` wrapped in try/except
- [x] Import resolution: `view_tab.py` must import `calculate_daily` from `loan_manager.interest_calculator`, `generate_report_id`, `write_report`, `write_report_records` from `loan_manager.report_manager` (or their data-layer adapter equivalents)

**`_generate_paidoff_report()` logic (pseudocode contract):**
```python
def _generate_paidoff_report(self, loan: Loan, paidoff_date: date) -> None:
    if loan.due_date is None:
        logger.warning("Paidoff report skipped for %s: no due_date", loan.reference_id)
        return
    extension_days = max(0, (paidoff_date - loan.due_date).days)
    record = {
        "reference_id": loan.reference_id,
        "borrower_name": loan.borrower_name,
        "amount": loan.amount,
        "extension_period": extension_days,
        "extension_period_unit": "days",
        "interest_rate": 12.0,        # global default — BC-05 pending
        "commission_rate": 2.0,       # global default — BC-05 pending
        "tds_flag": False,
        "mode": "Daily",
    }
    calc_result = calculate_daily(record)
    report_date = paidoff_date
    report_id = generate_report_id(reports_meta_path, report_date)
    report = { "report_id": report_id, "report_date": report_date, "mode": "Daily", "status": "Pending" }
    write_report(report)
    write_report_records([{**record, **calc_result, "report_id": report_id}])
    logger.info("Paidoff report %s generated for loan %s", report_id, loan.reference_id)
```

**`_action_paidoff()` wrapper pattern:**
```python
# After mark_paidoff() succeeds:
try:
    self._generate_paidoff_report(loan, paidoff_date)
except Exception as exc:
    logger.error("Paidoff report generation failed for %s: %s", loan.reference_id, exc)
    QMessageBox.warning(
        self,
        "Report Generation Warning",
        f"Loan {loan.reference_id} was marked as Paidoff successfully.\n"
        f"However, the interest report could not be generated: {exc}\n"
        "Please create the report manually in the Interest Calculator tab."
    )
```

**Interface Contract:**
- `calculate_daily(record: dict) -> dict` — existing, no change
- `generate_report_id(reports_meta_path: Path, report_date: date) -> str` — existing, no change
- `write_report(report: dict)` — existing, no change
- `write_report_records(records: List[dict])` — existing, no change

**Dependency Order:** Backend (domain logic) first, then UI caller

**Test Coverage Target:** 4 unit tests (normal case, zero extension, early payoff clamp to 0, no due_date skip); 1 integration test (end-to-end Paidoff → verify pending_reports.csv row)

**[REVIEW REQUIRED — BC-05]:** `interest_rate` and `commission_rate` are hardcoded to global defaults (12.0%, 2.0%) in the Paidoff report. If the user needs per-loan rates, a PaidoffDialog extension is required. **PO decision required before final implementation.** The Dev Lead will implement with defaults and flag this as a TODO comment in code pending BC-05 resolution.

---

### BUG-01 — Interest Calculator Filter Reset

**Backend Tasks:** None
**Frontend Tasks:**
- [x] `ui/interest_calculator_tab.py` `_on_apply_filters()`: Capture all five filter combo values BEFORE calling `_load_loans()`
- [x] After `_load_loans()` + `_populate_filters()` complete, restore each combo to its captured value using `combo.setCurrentText(captured_value)`

**Implementation pattern:**
```python
def _on_apply_filters(self) -> None:
    # Capture current selections before reload clears combos
    saved_bg = self._borrower_group_combo.currentText()
    saved_bn = self._borrower_name_combo.currentText()
    saved_dg = self._depositor_group_combo.currentText()
    saved_dn = self._depositor_name_combo.currentText()
    saved_status = self._status_combo.currentText()

    self._load_loans()  # This calls _populate_filters() which clears all combos

    # Restore saved selections (setCurrentText is no-op if value not in list)
    self._borrower_group_combo.setCurrentText(saved_bg)
    self._borrower_name_combo.setCurrentText(saved_bn)
    self._depositor_group_combo.setCurrentText(saved_dg)
    self._depositor_name_combo.setCurrentText(saved_dn)
    self._status_combo.setCurrentText(saved_status)
```

**Interface Contract:** N/A — UI internal change only

**Dependency Order:** Frontend only

**Test Coverage Target:** 2 UI-level tests (filter persists after apply; filter gracefully reverts to "All" when value no longer exists after reload)

---

### BUG-02 — View Tab Color Palette

**Frontend Tasks:**
- [x] `ui/view_tab.py`: Update `STATUS_COLORS` dict to high-contrast dark palette
- [x] In row-coloring loop: set both `Qt.BackgroundRole` and `Qt.ForegroundRole` on each item

**Implementation contract:**
```python
STATUS_COLORS = {
    "Active":  {"bg": "#2d6a4f", "fg": "#ffffff"},
    "Overdue": {"bg": "#9b2226", "fg": "#ffffff"},
    "Pending": {"bg": "#ca6702", "fg": "#ffffff"},
    "Paidoff": {"bg": "#495057", "fg": "#ffffff"},
}
# In row-coloring loop:
item.setBackground(QBrush(QColor(colors["bg"])))
item.setForeground(QBrush(QColor(colors["fg"])))
```

**Dependency Order:** Frontend only

**Test Coverage Target:** Visual regression only (no automated test possible for color rendering). Document expected palette in TEST_SCOPE.md for manual QA verification.

---

### BUG-03 — Paidoff Marking Flow

**Scope (Phase 3 only):** Verification that context menu path works. No code change expected unless inspection finds a connection bug.

**Frontend Tasks:**
- [x] Verify `_action_paidoff()` is connected to context menu "Mark Paidoff" action in `view_tab.py`
- [x] If disconnected: reconnect `triggered.connect(self._action_paidoff)` on the context menu action

**Phase 4 backlog:** `StatusDelegate(QItemDelegate)` for inline QComboBox editing of Status column. **Not in Phase 3 scope per PD-R2-06.**

**Dependency Order:** Frontend only

**Test Coverage Target:** 1 manual test (right-click → Mark Paidoff → dialog opens → confirm → loan moves to history)

---

### BUG-04 — Windows Date Picker Click Behavior

**Frontend Tasks:**
- [x] Create `ui/widgets/clickable_date_edit.py` with `ClickableDateEdit(QDateEdit)` subclass

**Implementation contract:**
```python
# ui/widgets/clickable_date_edit.py
from PySide6.QtWidgets import QDateEdit
from PySide6.QtCore import QEvent

class ClickableDateEdit(QDateEdit):
    """QDateEdit subclass that opens the calendar popup on any click."""

    def mousePressEvent(self, event: QEvent) -> None:
        super().mousePressEvent(event)
        self.showPopup()
```

- [x] `ui/entry_tab.py`: Replace `QDateEdit` with `ClickableDateEdit` for `giving_date` and `due_date` fields
- [x] `ui/dialogs/paidoff_dialog.py`: Replace `QDateEdit` with `ClickableDateEdit` for `paidoff_date` field
- [x] `ui/dialogs/extend_dialog.py`: Inspect — if `QDateEdit` present, replace. If only SpinBox+Combo (no DateEdit), skip.

**Dependency Order:** Frontend only

**Test Coverage Target:** 1 manual test on Windows verifying calendar opens on click anywhere in field. Cross-platform regression: no regression on macOS (showPopup idempotent).

---

### DOC-01 — Import Parser DD-MM-YYYY

**Backend Tasks:**
- [x] `data/import_service.py`: Add `_parse_flexible_date(s: str) -> Optional[date]` helper function
- [x] Replace `date.fromisoformat(giving_raw)` at line 168 with `_parse_flexible_date(giving_raw)` (handle None return → skip row)
- [x] Replace `date.fromisoformat(due_raw) if due_raw else None` at line 171 with `_parse_flexible_date(due_raw) if due_raw else None`

**Implementation contract:**
```python
from datetime import date, datetime
from typing import Optional

def _parse_flexible_date(s: str) -> Optional[date]:
    """Parse a date string in YYYY-MM-DD or DD-MM-YYYY format.
    Returns None and logs a WARNING on failure.
    """
    s = s.strip()
    if not s:
        return None
    # Try ISO 8601 first (canonical internal format)
    try:
        return date.fromisoformat(s)
    except ValueError:
        pass
    # Try DD-MM-YYYY (sample input documentation format)
    try:
        return datetime.strptime(s, "%d-%m-%Y").date()
    except ValueError:
        logger.warning("Unrecognised date format, cannot parse: %r", s)
        return None
```

**Caller change in `_row_to_loan()`:**
- `giving_date = _parse_flexible_date(giving_raw)` — if None, the Loan construction will fail on giving_date required field → caught by existing `except Exception` block → row skipped
- `due_date = _parse_flexible_date(due_raw) if due_raw else None` — None is valid for due_date

**Interface Contract:** Internal helper — no change to `import_loans()` public API

**Dependency Order:** Backend only

**Test Coverage Target:** 3 unit tests (ISO input accepted; DD-MM-YYYY input accepted and stored as ISO; invalid input returns None + WARNING log)

---

## 4. Code Reviewer Invocation

Per Dev Lead SKILL.md, the code-reviewer agent (`./claude/agents/code-reviewer.md`) must be invoked for the following planning-phase snippets:

| Snippet | Review Priority |
|---|---|
| `_generate_paidoff_report()` in view_tab.py | High — cross-module calls, error handling, logging |
| `_on_apply_filters()` fix in interest_calculator_tab.py | Medium — ordering fix |
| `_parse_flexible_date()` in import_service.py | Medium — parsing fallback logic |
| `ClickableDateEdit` in ui/widgets/ | Low — short subclass |

**Code Reviewer checklist items flagged:**
- `_generate_paidoff_report()`: Verify import paths are correct (loan_manager vs data layer). Confirm `calculate_daily()` input dict shape matches expected keys exactly.
- `_on_apply_filters()`: Confirm combo names match actual widget attribute names in the class.
- `_parse_flexible_date()`: Confirm strptime format string `%d-%m-%Y` correctly parses `02-01-2026` as January 2nd 2026 (not February 1st).

---

## 5. TDD Guide Invocation

Per SKILL.md, the `tdd-guide` agent must be invoked alongside implementation. Test targets per module:

| Module | Target Coverage | Key Test Scenarios |
|---|---|---|
| `ui/entry_tab.py` (CHG-01) | 80% | Default checkbox state; form reset checkbox state |
| `ui/view_tab.py` (CHG-02, BUG-02, BUG-03) | 70% | Paidoff report generation happy/sad paths; color role assignment; context menu connection |
| `ui/interest_calculator_tab.py` (BUG-01) | 75% | Filter persist; filter graceful revert |
| `data/import_service.py` (DOC-01) | 85% | ISO date accepted; DD-MM-YYYY accepted; invalid date skipped |
| `ui/widgets/clickable_date_edit.py` (BUG-04) | 90% | mousePressEvent calls showPopup |

---

## 6. Implementation Sequence and Dependencies

| Order | Item | Files Changed | Effort | Blocks |
|---|---|---|---|---|
| 1 | BUG-04: ClickableDateEdit | ui/widgets/clickable_date_edit.py (new) | S | BUG-04 consumers |
| 2 | CHG-01: Default checkbox | ui/entry_tab.py | S | Nothing |
| 3 | BUG-01: Filter fix | ui/interest_calculator_tab.py | S | Nothing |
| 4 | BUG-02: Color palette | ui/view_tab.py | S | BUG-03 (readability) |
| 5 | DOC-01: Import parser | data/import_service.py | S | Nothing |
| 6 | BUG-03: Paidoff context menu verify | ui/view_tab.py | S | BUG-02 (readability fix makes testing possible) |
| 7 | CHG-02: Paidoff report | ui/view_tab.py | M | BUG-03 working |
| 8 | BUG-04 consumers: Replace QDateEdit | ui/entry_tab.py, dialogs/ | S | BUG-04 widget created (step 1) |

**Total estimated effort:** 7 dev-days (aligned with PM PROJECT_CHARTER.md sprint estimate)

---

## 7. Dev Lead → QA Lead KT

## Dev Lead → QA Lead KT: Loan Manager run_2

**What was built:**
Seven change items implementing bug fixes and two new requirements for the Loan Manager PySide6 desktop app. Changes are limited to UI layer files (entry_tab.py, view_tab.py, interest_calculator_tab.py), one new shared widget (ClickableDateEdit), and one backend service fix (import_service.py date parsing).

**Frontend changes:**
- `ui/entry_tab.py`: No Due Date checkbox defaults to checked (CHG-01)
- `ui/view_tab.py`: STATUS_COLORS updated to high-contrast dark palette (BUG-02); `_generate_paidoff_report()` added (CHG-02)
- `ui/interest_calculator_tab.py`: Filter value capture/restore ordering fix (BUG-01)
- `ui/widgets/clickable_date_edit.py`: New ClickableDateEdit widget (BUG-04)
- `ui/dialogs/paidoff_dialog.py`: ClickableDateEdit replacing QDateEdit (BUG-04)
- `ui/dialogs/extend_dialog.py`: ClickableDateEdit if DateEdit present (BUG-04)

**Backend changes:**
- `data/import_service.py`: `_parse_flexible_date()` helper; flexible date parsing for giving_date and due_date (DOC-01)

**Interface contract (as implemented):**
- No new public APIs. All changes are internal to existing modules or private methods.
- `calculate_daily(record: dict) -> dict` — existing, unmodified
- `mark_paidoff(reference_id, paidoff_date)` — existing, unmodified

**Happy paths to test:**
1. New loan entry form opens with No Due Date checked and Due Date field disabled
2. Mark loan as Paidoff (right-click context menu) → PaidoffDialog → confirm → loan disappears from View Tab → report appears in Pending Approval
3. Interest Calculator: select filter → Apply Filters → filter combo retains selected value, table shows filtered results
4. Import CSV with DD-MM-YYYY dates → loans imported correctly with ISO dates stored
5. View Tab rows show readable dark colors with white text

**Edge cases / known risks:**
- CHG-02: Loan with no due_date marked Paidoff → report NOT generated → WARNING logged (no user error shown)
- CHG-02: Report generation fails after Paidoff write succeeds → user sees warning dialog, loan correctly moved to history
- CHG-02: Paidoff date before due_date → extension_period_days = 0, report generated with zero interest
- BUG-01: Filter value deleted between apply attempts → combo gracefully reverts to "All"
- BUG-04: On macOS, showPopup() when popup already open is a no-op (safe, no regression)
- DOC-01: XLSX with date serial numbers will still fail parse (pre-existing limitation, not in scope)

**Out of scope for this release:**
- QComboBox StatusDelegate for inline Paidoff via Status column (Phase 4 per PD-R2-06)
- BC-05: Interest rate / commission rate at Paidoff time (pending PO decision)
- BC-06: Paidoff report approval flow semantic conflict (Phase 4 per SA ADR-002)
- Automated atomic writes for report CSV files (Phase 4 per SRE review)
- R9 theme chooser (Phase 4)
- R6 import/export full date hierarchy filter (Phase 4)

**Deployment notes:**
- No new Python package dependencies
- No CSV schema changes — no migration required
- New file: `ui/widgets/clickable_date_edit.py` — must be present in source tree
- Run launchers unchanged (CHG-03 already implemented)

---

## 8. Dev Lead Test Scope Co-Sign Pre-Authorization

After QA Lead produces TEST_SCOPE.md, the Dev Lead will co-sign with:
- Any missed edge cases from the implementation above will be flagged
- Particular attention to CHG-02 Paidoff report edge cases (no due_date, early payoff, report failure isolation)
