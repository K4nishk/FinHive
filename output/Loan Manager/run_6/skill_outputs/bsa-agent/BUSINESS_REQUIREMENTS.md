# Loan Manager — Business Requirements
**Agent:** bsa-agent (Wave 1)
**Run:** run_6
**Date:** 2026-04-04
**Phase:** Phase 3 Closure / Phase 4 MVP Readiness

---

## Executive Summary

Phase 3 implementation is complete as of run_5. This document focuses on:
1. Acceptance criteria for the 4 open user decisions (TC-05, TC-08, TC-03, BC-02)
2. Completeness audit of all Phase 1+2+3 requirements
3. UAT scenario list for Phase 4 manual testing
4. Deep-dive on TC-05 (highest risk open item)

---

## Completeness Audit — All Requirements

### R1 — Loan Entry Tab

| Acceptance Criterion | Status |
|---|---|
| Borrower Name, Depositor Name, Amount, Giving Date, Due Date, Due Period, Borrower Group, Depositor Group fields present | DONE |
| Calendar widget opens on Tab/click for date fields | DONE — ClickableDateEdit with focusInEvent + mousePressEvent |
| Amount defaults to INR, non-negative integer | DONE — QSpinBox with min=0, suffix " INR" |
| due_date = giving_date + due_period(months) auto-calc | DONE — _on_due_period_changed() |
| due_date defaults to "No Due Date" when unchecked | DONE — QCheckBox "No Due Date" |
| Autocomplete for borrower_name, borrower_group, depositor_name, depositor_group | DONE — QCompleter |
| Status bar: "Loan saved successfully. Reference ID: {ref_id}." | DONE — _status_label |
| No auto-switch to View Tab after save | DONE — loan_added signal only, no tab switch |

**Open item:** TC-03 — When user manually edits due_date after auto-calc, should due_period field clear? [REVIEW REQUIRED — awaiting user decision]

### R2 — View Tab

| Acceptance Criterion | Status |
|---|---|
| View Template [SNo, ref_id, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status] | DONE |
| Column sorting: alphabetical, date, numeric | DONE — QSortFilterProxyModel with sort enabled |
| Unknown Depositor Name/Group displayed as "Unknown" | DONE — _make_row() with "Unknown" fallback |
| Inline editing for all editable columns | DONE — _on_item_changed() |
| Date columns open calendar picker for inline edit | DONE — DatePickerDelegate |
| ref_id visible but not editable | DONE — editable=False on ref_id item |

### R3 — Status and Paidoff

| Acceptance Criterion | Status |
|---|---|
| Status values: Active, Overdue, Pending | DONE — compute_status() |
| Status auto-recomputed on app launch | DONE — recompute_all() in load_data() |
| Color palette: Active #025c33, Overdue #6b0307, Pending #804001, Paidoff #022a52, all bold white | DONE — STATUS_COLORS dict |
| Mark Paidoff via right-click → PaidoffDialog → report → Pending Approval | DONE |
| Mark Paidoff disabled when no due_date | DONE — paidoff_action.setEnabled(loan.due_date is not None) |
| Warning label for Paidoff-mode reports in Pending Approval | DONE — _paidoff_warning QLabel |
| Paidoff loan archived at approval time only (not at report generation) | DONE — mark_paidoff() in _on_approve() |
| history.csv maintained for paidoff records | DONE — mark_paidoff() in csv_manager |
| Paidoff records removed from loans.csv | DONE |
| Manual Active override prompts for new due date | DONE — handled via inline due_date edit + status recompute |

**Open item TC-05:** Guard against double Paidoff report generation. [REVIEW REQUIRED — see deep-dive below]

### R4 — Reference ID and CRUD

| Acceptance Criterion | Status |
|---|---|
| ref_id format YYYY_MM_<order> (e.g. 2026_03_001) | DONE |
| Order increments within month; 999-overflow to 1000+ supported | DONE — ref_id_manager.py |
| Delete loan removes from loans.csv | DONE — delete_loan() |
| Extend loan reuses ref_id, updates giving_date/due_date | DONE — extend_loan() via ExtendDialog |
| Extension period unit: months (default) or days | DONE — ExtendDialog |
| Counter resets if all records for YYYY_MM deleted | DONE |
| loans_meta.csv stores high-water mark | DONE |

### R5 — Interest Calculator

| Acceptance Criterion | Status |
|---|---|
| Three modes: Monthly (default), Daily, Both | DONE |
| Mode selector (QComboBox) | DONE |
| 5 filter options: Borrower Group, Borrower Name, Depositor Name, Depositor Group, ByMonth | DONE |
| No filter = show loans with no due_date only | DONE |
| Filter applied = exclude no-due-date loans, show matching records | DONE |
| Filter comparisons case-insensitive (UTR1 fix) | DONE |
| Unknown option in Depositor Group filter | DONE |
| Global interest_rate, commission_rate, extension_period, tds_flag inputs | DONE |
| Monthly: Interest = (Amount * rate * period) / (12 * 100) | DONE |
| Daily: Interest = (Amount * rate * period) / (365 * 100) | DONE |
| Both: routes by extension_period_unit | DONE — calculate_both() |
| Time = extension_period only (not tenure) | DONE — authoritative per R5 |
| TDS = 0.1 * Interest when tds_flag=True | DONE |
| CHQ_Amt = Interest - TDS (or 0.9 * Interest when tds_flag=False) | DONE — _compute_chq_amt() |
| Calculate button opens CalculationDialog (modal) | DONE |
| Generate Report button inside dialog only | DONE — tab's Generate button hidden, dialog has it |
| Inline-editable cells in dialog with on-the-fly recalculation | DONE |
| Report sent to Pending Approval after Generate | DONE |
| Summary: total_loan_amount, total_interest, total_commission | DONE |
| two-file normalized: pending_reports.csv + pending_report_records.csv | DONE |
| Post-extension preview columns (post_giving_date, post_due_date) | DONE — REC_COL_POST_GIVING, REC_COL_POST_DUE |
| Shared ref-id warning between reports | DONE |
| Deleted loan warning on approval | DONE |
| Declined reports: delete records, mark Declined | DONE |
| Report inline edits auto-update interest/commission/tds | DONE — _recalc_row() |
| report_latest_update_dt refreshed on edit | DONE |

**Open item TC-08:** paidoff_date field storage. [REVIEW REQUIRED — see below]

### R6 — Import/Export and Filters

| Acceptance Criterion | Status |
|---|---|
| Excel-like column filtering in View Tab | PARTIAL — sorting works; full hierarchical date filter (year→month) deferred |
| Export to CSV/XLSX | DEFERRED — out of Phase 3 scope |
| Import CSV/XLSX with preview | DEFERRED — out of Phase 3 scope |
| All records in single loans.csv (no year-based partitioning) | DONE |
| CSV in ./data/ subfolder | DONE |

**Note:** Full hierarchical date filter (R6) and Import/Export (R6) remain deferred for post-MVP.

### R7 — Sample Data and Logging

| Acceptance Criterion | Status |
|---|---|
| Sample data (15 records) seeded on first launch | DONE — data/seed.py |
| Seeding skips if loans.csv has data rows | DONE — guard condition |
| loans_meta.csv updated after seeding | DONE |
| Logs to ./data/logs/app.log | DONE |
| No due_date loan can become Overdue | DONE — compute_status() handles None due_date |
| Extend for no-due-date loan: new giving_date = today | DONE — ExtendDialog special case |

### R8 — Tech Stack and Run Scripts

| Acceptance Criterion | Status |
|---|---|
| PySide6 desktop app | DONE |
| run_windows.bat — venv, install, launch | DONE |
| run_mac.sh — venv, install, launch | DONE |
| Python version check in both scripts | DONE |
| Dates stored as ISO 8601 | DONE |
| No CSV file locking | DONE |

### R9 — UI Theme

| Acceptance Criterion | Status |
|---|---|
| Modern, professional UI | DONE (baseline) |
| Alternate theme choices | DEFERRED — post-MVP |

### R10 — User Guide

| Acceptance Criterion | Status |
|---|---|
| User guide for Mac and Windows | CONFIRMED PRESENT — user_guides/* |
| Python version check in run scripts | DONE |
| Batch write optimization | DEFERRED — post-MVP |

### User-Testing Requirement 1

| Acceptance Criterion | Status |
|---|---|
| Filter works for BorrowerGroup, BorrowerName, DepositorName, DepositorGroup | DONE — .lower() comparison on both sides |
| No testing drifts between OS implementations | DONE — pure Python logic, no OS-specific code in filter |
| UI color palette more readable | DONE — dark palette with bold white text |
| ClickableDateEdit showCalendarWidget AttributeError fixed | DONE — widgets.py uses showCalendarWidget() which is valid in PySide6 |

---

## TC-05 Deep-Dive — Double Paidoff Report Guard

### Business Context

When a user right-clicks a loan and selects "Mark Paidoff", the system:
1. Opens PaidoffDialog for paidoff_date, interest_rate, commission_rate, tds_flag
2. Generates a PendingReport (mode="Paidoff") and writes to pending_reports.csv + pending_report_records.csv
3. Loan remains in View Tab at its current status (Active/Overdue)
4. User approves report in Pending Approval Tab → mark_paidoff() called → loan archived

The gap: Between steps 1 and 4, the loan is still visible in the View Tab. The user could right-click it again and generate a second Paidoff report. Two Paidoff reports for the same loan would result in:
- On first approval: loan moved to history.csv, removed from loans.csv
- On second approval: mark_paidoff() raises ValueError (loan not found in loans.csv) — silent failure

### Acceptance Criteria for TC-05

**Option A (Recommended — Disable guard):**
- The "Mark Paidoff" context menu item is disabled/greyed out when a Paidoff-mode report for that loan already exists with status="Pending" in pending_report_records.csv
- Enabling condition: no pending Paidoff report for that ref_id exists
- Implementation: `has_pending_paidoff_report(reference_id: str) -> bool` in report_manager.py
- Called at context menu construction time in view_tab._show_context_menu()

**Option B (Warn):**
- "Mark Paidoff" always enabled
- When user selects it and a Paidoff report already exists, show: "A Paidoff report for this loan is already pending approval. Generating another report may result in duplicate archives. Proceed?"
- Implementation: check in _action_paidoff() before opening PaidoffDialog

**BSA Recommendation:** Option A. Disabling is a cleaner UX and prevents the user from accidentally generating duplicates. Option B still allows the mistake if the user dismisses the warning.

### [REVIEW REQUIRED] TC-05
User must choose Option A or Option B for the Double Paidoff guard behavior.

---

## TC-08 Deep-Dive — paidoff_date Field

### Business Context

When a Paidoff report is generated, the `paidoff_date` entered by the user in PaidoffDialog is currently stored in `ReportRecord.new_due_date`. This is a field reuse: in regular extension reports, `new_due_date` means the post-extension due date. In Paidoff-mode reports, `new_due_date` means the paidoff_date.

This dual semantic exists because the `ReportRecord` dataclass has no dedicated `paidoff_date` field.

### Acceptance Criteria

**Option A (Field reuse):**
- Document that for mode="Paidoff" reports, `new_due_date` = `paidoff_date`
- No schema change. `pending_report_records.csv` columns unchanged.
- Approval code reads `rec.new_due_date` as paidoff_date — works correctly today

**Option B (Dedicated field):**
- Add `paidoff_date: Optional[date]` column to `ReportRecord` dataclass
- Add `paidoff_date` column to `pending_report_records.csv`
- Additive change — DictReader handles missing column gracefully for existing files
- Paidoff report writes `paidoff_date=paidoff_date`, `new_due_date=None`
- Regular extension reports write `paidoff_date=None`, `new_due_date=<new date>`

**BSA Recommendation:** Option B. The clean separation prevents future developer confusion. The schema change is additive (no migration needed for empty files).

### [REVIEW REQUIRED] TC-08
User must choose Option A or Option B for the paidoff_date field storage.

---

## TC-03 Deep-Dive — due_period + due_date Conflict

### Business Context

In the Entry Tab:
- User enters Due Period (e.g., 3 months) → due_date auto-calculates to giving_date + 3 months
- User then manually edits the due_date field (calendar picker) to a different date
- Due Period field still shows "3 months" — but the due_date no longer corresponds to 3 months from giving_date

### Acceptance Criteria

**Option A:** Clear due_period (set to 0) when user manually edits due_date.
- Implementation: Override `setModelData` on due_date ClickableDateEdit to reset `_due_period.setValue(0)` after manual edit
- More precisely: intercept `_due_date.dateChanged` signal only when NOT triggered by due_period auto-calc

**Option B (Current):** Leave due_period as-is. User knowingly overrode due_date. The stored value is always due_date — due_period is UI-only and not persisted.

**BSA Recommendation:** Option B unless user finds the retained period value confusing. The stored data (due_date) is always correct regardless. This is a pure UX preference.

### [REVIEW REQUIRED] TC-03
User must confirm Option A or Option B for due_period display after manual due_date edit.

---

## BC-02 Deep-Dive — Case Normalization

### Business Context

The filter fix (UTR1) uses case-insensitive comparison (`.lower()` on both sides). Filter works correctly regardless of stored case. However, filter dropdowns display values exactly as stored — if "BG1" and "bg1" both exist, they appear as two separate dropdown entries even though the filter treats them identically.

The sample data uses lowercase (b1, bg1, d1, dg1). New entries typed by the user follow whatever case they type.

### Options

**Option A (No change):** Leave values as typed. Case-insensitive matching works. Dropdown may show duplicates for inconsistently-entered data.

**Option B:** Normalize to lowercase at write time in `write_loan()`.

**Option C:** Normalize to title case at write time. "bg1" → "Bg1".

**BSA Recommendation:** Option B (lowercase). Consistent with existing sample data, minimal visual disruption, and prevents dropdown duplication in practice.

### [REVIEW REQUIRED] BC-02
User must choose Option A, B, or C for name storage normalization.

---

## UAT Scenario List (Phase 4 / Phase 5)

| ID | Scenario | Requirement | Priority |
|---|---|---|---|
| M-R1-01 | Enter new loan with due_period=3 months → verify due_date auto-calculates | R1 | P1 |
| M-R1-02 | Tab into date fields → calendar popup opens | R1 | P1 |
| M-R2-01 | Sort View Tab by amount ascending/descending | R2 | P1 |
| M-R2-02 | Inline edit borrower_name → verify persisted in loans.csv | R2 | P1 |
| M-R2-03 | Inline edit due_date → calendar opens, ISO date saved | R2 | P1 |
| M-R3-01 | Right-click loan → Mark Paidoff → PaidoffDialog → report generated | R3 | P1 |
| M-R3-02 | Approve Paidoff report → loan disappears from View Tab, appears in history.csv | R3 | P1 |
| M-R3-03 | Right-click loan with no due_date → Mark Paidoff disabled | R3 | P1 |
| M-R3-04 | Status colors correct for Active/Overdue/Pending | R3 | P1 |
| M-R4-01 | ref_id increments correctly for new entry in same month | R4 | P1 |
| M-R4-02 | Delete loan → ref_id counter continues (no reset) | R4 | P2 |
| M-R4-03 | Extend loan → giving_date = old due_date, due_date = old + extension | R4 | P1 |
| M-R5-01 | Apply Borrower Group filter → only matching loans shown | R5/UTR1 | P1 |
| M-R5-02 | Apply all 5 filters simultaneously | R5 | P2 |
| M-R5-03 | Monthly mode Calculate → CalculationDialog opens with correct values | R5 | P1 |
| M-R5-04 | Edit interest_rate in dialog → CHQ_Amt updates on-the-fly | R5 | P1 |
| M-R5-05 | Generate Report from dialog → appears in Pending Approval | R5 | P1 |
| M-R5-06 | Approve report in Pending Approval → loan dates updated in View Tab | R5 | P1 |
| M-R5-07 | Decline report → report removed, loans unchanged | R5 | P1 |
| M-R5-08 | Shared ref-id warning shown when two reports share a loan | R5 | P2 |
| M-R7-01 | First launch with no loans.csv → 15 sample records loaded | R7 | P1 |
| M-R7-02 | Second launch with data → no re-seeding occurs | R7 | P1 |
| M-R8-01 | run_mac.sh executes, creates venv, installs deps, launches app | R8 | P1 |
| M-TC05 | Mark Paidoff on loan already in Paidoff queue → guard triggers | TC-05 | P1 |
