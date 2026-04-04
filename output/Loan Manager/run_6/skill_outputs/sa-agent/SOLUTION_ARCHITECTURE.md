# Loan Manager — Solution Architecture
**Agent:** sa-agent (Wave 1)
**Run:** run_6
**Date:** 2026-04-04
**Phase:** Phase 3 Closure / Phase 4 Architecture Review

---

## Architecture Status: Stable

The layered architecture established in run_2 is confirmed correct and fully implemented. No architectural changes required for Phase 4 features. This document audits all ADRs from previous runs for compliance in the current codebase and issues new ADRs only for the 4 open user decisions.

---

## Confirmed Architecture (Unchanged)

```
src/Loan Manager/
    main.py                         Entry point, logging setup, seed on startup
    loan_manager/
        __init__.py
        interest_calculator.py      Pure calculation functions — no I/O
        status_engine.py            Canonical status engine
    data/
        __init__.py
        csv_manager.py              CSV read/write adapter (all persistence)
        ref_id_manager.py           Reference ID generation + high-water mark
        report_manager.py           Report + record persistence
        seed.py                     Sample data seeding (R7)
        status_engine.py            Re-export shim (points to loan_manager/status_engine.py)
        logs/app.log                Application log
        loans.csv                   Active loan records
        loans_meta.csv              High-water mark per YYYY_MM
        pending_reports.csv         Report header metadata
        pending_report_records.csv  Report line items
        history.csv                 Paidoff archive
    models/
        __init__.py
        loan.py                     Loan dataclass
        report.py                   PendingReport + ReportRecord dataclasses
    ui/
        __init__.py
        main_window.py              QTabWidget container
        entry_tab.py                R1 — loan entry form
        view_tab.py                 R2, R3, R4 — sortable inline-editable table
        interest_calculator_tab.py  R5 — filter + calculate
        pending_approval_tab.py     R5 — approve/decline workflow
        widgets.py                  ClickableDateEdit, DatePickerDelegate
        dialogs/
            __init__.py
            calculation_dialog.py   R5 modal calculation review
            extend_dialog.py        R4 extend loan
            paidoff_dialog.py       R3 paidoff date input
    tests/
        conftest.py
        test_csv_manager.py
        test_interest_calculator.py
        test_ref_id_manager.py
        test_report_manager.py
        test_status_engine.py
        test_filter_logic.py        run_5 — UTR1
        test_seed.py                run_5 — R7
        test_calculation_dialog_logic.py  run_5 — R5 dialog
    user_guides/                    R10 — Mac and Windows guides
    requirements.txt
    run_mac.sh
    run_windows.bat
    pytest.ini
```

---

## ADR Review — Previous Runs (Compliance Confirmed)

### ADR-R3-01: No Transient Paidoff Pending Status (run_3)
**Status: COMPLIANT**
Confirmed in pending_approval_tab.py: `mark_paidoff()` called only in `_on_approve()`, never in view_tab. Loan remains Active/Overdue until approval.

### ADR-R2-01: DatePickerDelegate with ClickableDateEdit (run_4)
**Status: COMPLIANT**
`widgets.py` implements both correctly. `setModelData()` writes ISO 8601. `showCalendarWidget()` is called correctly (bug from UTR1 was fixed).

### ADR-UTR1-01: Case-Insensitive Comparison (run_5)
**Status: COMPLIANT**
`_get_filtered_loans()` in interest_calculator_tab.py uses `.lower()` on both sides for all 4 text filter dimensions.

### ADR-R5-04: Modal CalculationDialog (run_5)
**Status: COMPLIANT**
`CalculationDialog` inherits from `QDialog`, `setModal(True)`, opened via `dialog.exec()`. Tab's Generate Report button remains present but only functional after Calculate (current behavior slightly differs from PD-06 which says "hidden" — see new ADR below).

---

## New ADRs — Phase 4 Decisions

### ADR-R6-01: Hierarchical Date Filter for View Tab
**Decision:** Defer full year→month→date hierarchy for the View Tab column filter to post-MVP.
**Rationale:** R6 specifies the hierarchy but Phase 3 is the final prototype phase. The sortable table with `QSortFilterProxyModel` handles column-level sorting. The full hierarchy requires a custom `QHeaderView` with a nested filter popup — significant complexity for a prototype.
**Impact:** None on current implementation. Document as post-MVP backlog item.
**Status:** DEFERRED

### ADR-TC05-01: Paidoff Report Guard Location
**Decision:** If user selects Option A (disable), the guard check belongs in the data layer, not the UI layer.
**Rationale:** A UI-only check in `_show_context_menu()` could be bypassed. The authoritative check must query `pending_report_records.csv` directly.
**Proposed function:** `has_pending_paidoff_report(reference_id: str) -> bool` in `report_manager.py`
**Implementation:** Query `pending_report_records.csv` for any record with `reference_id=ref_id` whose parent report has `mode=Paidoff` and `status=Pending` in `pending_reports.csv`.
**Caller:** `view_tab._show_context_menu()` — disable `paidoff_action` when `has_pending_paidoff_report(ref_id)` returns True.
**Status:** Pending user decision on TC-05

### ADR-TC08-01: ReportRecord paidoff_date Field
**Decision (Recommended Option B):** Add `paidoff_date: Optional[date] = None` to `ReportRecord` dataclass.
**Schema change:** Additive. One new column in `pending_report_records.csv`.
**Migration:** None required. `csv.DictReader` with `fieldnames` handles missing column as empty string → `None` after parse.
**Breaking change:** Zero. Existing files load correctly.
**Status:** Pending user decision on TC-08

### ADR-R1-02: due_period + due_date Conflict Resolution
**Decision (Pending TC-03):** If user chooses Option A (clear period), the implementation is:
1. Connect `_due_date.dateChanged` signal to a new slot `_on_due_date_manually_changed()`
2. In that slot, check if the change was NOT triggered by `_on_due_period_changed()` (use a `_suppressing_date_change: bool` guard flag)
3. If manual edit: call `self._due_period.blockSignals(True); self._due_period.setValue(0); self._due_period.blockSignals(False)`
**Architectural note:** The guard flag pattern is already used in `_on_due_period_changed()` (blockSignals). Consistent pattern.
**Status:** Pending user decision on TC-03

### ADR-BC02-01: Case Normalization at Write Time
**Decision (Pending BC-02):** If user chooses Option B or C, normalization belongs in `csv_manager.write_loan()` before the row is written to loans.csv. All fields subject to normalization: `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group`.
**Option B implementation:** `.lower()` on write
**Option C implementation:** `.title()` on write
**Non-impact:** Filter comparisons already use `.lower()` — normalization only affects display readability in dropdowns.
**Status:** Pending user decision on BC-02

---

## Architecture Risk Assessment — Phase 4

| Risk | Severity | Mitigation |
|---|---|---|
| TC-05 implemented as UI-only check (insufficient) | High | ADR-TC05-01 mandates data-layer check |
| TC-08 Option A: semantic confusion in future | Low-Medium | Document dual meaning clearly in code comment |
| TC-08 Option B: schema migration for existing pending records | None | DictReader handles missing column gracefully |
| View Tab Generate Report button behavior (tab vs dialog) | Low | Clarify: tab button remains but is only reachable if _calculated=True; dialog is the primary path |

---

## Frontend Architecture Note (R4)

For a sortable, filterable, inline-editable table of up to 1500 rows, the confirmed correct choice is:
- **QStandardItemModel + QSortFilterProxyModel** for sort and filter
- **QTableView** (model-based, not QTableWidget) for performance at 1500 rows
- **QStyledItemDelegate** subclass for custom cell editors (DatePickerDelegate)
- **QHeaderView** for column resize modes

This is already implemented correctly in `view_tab.py`. The BSA requirement to document this as an architectural requirement is hereby fulfilled.

---

## Integration Impact Summary

| Phase 4 Change | Files Affected | Type |
|---|---|---|
| TC-05 Option A | report_manager.py, view_tab.py | Additive |
| TC-08 Option B | models/report.py, data/report_manager.py | Additive schema change |
| TC-03 Option A | ui/entry_tab.py | Behavioral change (UX only) |
| BC-02 Option B | data/csv_manager.py write_loan() | Behavioral change (write normalization) |
| Remaining tests | tests/ — 4 new files | Test-only |
