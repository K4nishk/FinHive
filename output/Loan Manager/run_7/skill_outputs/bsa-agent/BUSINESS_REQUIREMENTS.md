# Loan Manager — Business Requirements
**Agent:** bsa-agent (Wave 1)
**Run:** run_7
**Date:** 2026-04-05
**Phase:** Phase 3 Closure / Phase 4 MVP

---

## BSA Requirements Breakdown: Phase 3 Closure — Remaining Items

This document covers the five remaining open items from run_6 that require resolution before Phase 4 can be declared complete. All other requirements (R1–R10, UTR1) have been confirmed DONE per the run_6 completeness summary.

---

### Deep-Dive: TC-05 — Mark Paidoff Double-Report Guard (R3)

**Source requirement (REQUIREMENTS.md R3):**
> "Disable 'Mark Paidoff' if a Paidoff report for that loan is already pending."

**Current state:** The `_show_context_menu()` in `ui/view_tab.py` sets `paidoff_action.setEnabled(loan.due_date is not None)` — this only guards against missing due_date. The second guard (pending Paidoff report check) is NOT yet implemented.

**PO Decision:** PD-10 BINDING — Option A: disable "Mark Paidoff" when a Paidoff report for that loan is already in the Pending queue.

**Functional Requirements:**
- FR-TC05-01: The system shall query `pending_report_records.csv` and `pending_reports.csv` at context menu build time to determine if a Paidoff-mode report with status="Pending" already exists for the selected loan's `reference_id`.
- FR-TC05-02: `has_pending_paidoff_report(reference_id: str) -> bool` shall be implemented in `data/report_manager.py` (PD-12).
- FR-TC05-03: If `has_pending_paidoff_report()` returns True, the "Mark Paidoff" context menu action shall be disabled (grayed out).
- FR-TC05-04: The function shall read only active Pending reports (status="Pending"), not Approved or Declined.

**User Story:**

### Story TC-05: Prevent duplicate Paidoff reports
As a loan manager user,
I want the "Mark Paidoff" option to be grayed out when a Paidoff report for this loan is already awaiting approval,
So that I cannot accidentally create duplicate Paidoff reports for the same loan.

**Acceptance Criteria:**
- Given a loan with reference_id "2026_03_001" has a Pending Paidoff report in the queue, When the user right-clicks that loan in the View Tab, Then "Mark Paidoff" is disabled.
- Given no Pending Paidoff report exists for "2026_03_001", When the user right-clicks, Then "Mark Paidoff" is enabled (subject to due_date check).
- Given a Paidoff report for "2026_03_001" has status="Approved" or "Declined", When the user right-clicks, Then "Mark Paidoff" is enabled.

**Affected files:**
- `data/report_manager.py` → add `has_pending_paidoff_report(reference_id: str) -> bool`
- `ui/view_tab.py` → update `_show_context_menu()` to call `has_pending_paidoff_report()`

**Estimate:** 1 hour. No schema changes.

---

### TC-08 — paidoff_date Field in ReportRecord

**Current state:** In `ui/view_tab.py`, `_action_paidoff()` stores `paidoff_date` in `record.new_due_date`. For regular extension reports, `new_due_date` is the post-extension due date. For Paidoff-mode, it is the paidoff_date. This dual semantic is functionally correct but architecturally ambiguous.

**Functional Requirements:**
- Option A: Accept field reuse. Document in code comments. Zero code change.
- Option B: Add `paidoff_date: Optional[date] = None` to `ReportRecord`. Update `pending_report_records.csv` schema, write logic, read logic, and approval logic.

**User Story (Option B):**

### Story TC-08-B: Dedicated paidoff_date field
As a developer maintaining the Loan Manager,
I want a dedicated `paidoff_date` column in ReportRecord,
So that the semantic difference between Paidoff-mode and extension-mode reports is explicit in the schema.

**Acceptance Criteria (Option B):**
- Given a Paidoff report is generated, When it is written to `pending_report_records.csv`, Then the `paidoff_date` column contains the user-entered paidoff date and `new_due_date` is empty.
- Given a Paidoff report is approved, When `_on_approve()` runs, Then it reads `rec.paidoff_date` (not `rec.new_due_date`) to call `mark_paidoff()`.
- Given an extension report is generated, Then `paidoff_date` is empty and `new_due_date` contains the post-extension due date.

**Affected files (Option B):**
- `models/report.py` → add `paidoff_date: Optional[date] = None` to ReportRecord
- `loan_manager/report_manager.py` → update CSV_FIELDNAMES, read/write functions
- `ui/view_tab.py` → update `_action_paidoff()` to pass `paidoff_date=paidoff_date` and `new_due_date=None`
- `ui/pending_approval_tab.py` → update `_on_approve()` to read `rec.paidoff_date or rec.new_due_date` (backward-compat) for Paidoff mode

**Impact on existing data:** Additive column. Existing rows read with empty `paidoff_date` — no corruption. No migration needed.

**[REVIEW REQUIRED] TC-08 — User Decision Needed:**
User must choose:
- Option A: Accept field reuse of `new_due_date` for `paidoff_date`. Zero code change. Document in comments.
- Option B: Add dedicated `paidoff_date` column to ReportRecord. ~2 hours. Cleaner schema.

---

### TC-03 — due_period Display After Manual due_date Edit

**Current state:** In `ui/entry_tab.py`, entering Due Period auto-calculates Due Date. If user then manually edits Due Date via calendar picker, the Due Period spinbox still shows the old value. `due_period` is not persisted; it is UI-only.

**Functional Requirements:**
- Option A: When user manually changes Due Date, clear Due Period to 0 (or "Not set").
- Option B (current): Leave Due Period value unchanged. Since `due_period` is not persisted and has no further effect after initial calc, the display inconsistency is cosmetic only.

**User Story (Option A):**

### Story TC-03-A: Clear Due Period when user manually edits Due Date
As a loan entry user,
I want the Due Period to clear when I manually edit the Due Date,
So that the displayed due_period is always consistent with the actual due_date.

**Acceptance Criteria (Option A):**
- Given Due Period = 3 months and Due Date = 2026-04-05, When user changes Due Date to 2026-05-01 via calendar picker, Then Due Period resets to 0 / "Not set".

**Affected files (Option A):**
- `ui/entry_tab.py` → connect `_due_date.dateChanged` to clear `_due_period` (with a `_suppressing_due_period_signal` flag to avoid recursion)

**[REVIEW REQUIRED] TC-03 — User Decision Needed:**
- Option A: Clear Due Period when user manually edits Due Date (~30 min)
- Option B: No change — retain current behavior (zero effort)

---

### BC-02 — Case Normalization for Stored Loan Names

**Current state:** Filter matching in Interest Calculator uses case-insensitive `.lower()` comparison (UTR1 fixed). However, filter dropdowns display values as stored. Inconsistent casing (e.g., "BG1" vs "bg1") creates duplicate dropdown entries.

**Functional Requirements:**
- Option A: No change. Filter matching works correctly via `.lower()`.
- Option B: Normalize `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group` to lowercase at write time in `write_loan()` in `data/csv_manager.py`.
- Option C: Normalize to title case.

**Acceptance Criteria (Option B):**
- Given user enters "BG1" as Borrower Group, When loan is saved, Then `borrower_group` stored in CSV is "bg1".
- Filter dropdowns show only lowercase entries, matching the sample data convention (b1, bg1, d1, dg1).

**Affected files (Option B or C):**
- `data/csv_manager.py` → normalize 4 fields in `write_loan()`
- `tests/test_csv_manager.py` → add test for normalization

**[REVIEW REQUIRED] BC-02 — User Decision Needed:**
- Option A: No change (zero effort)
- Option B: Lowercase normalization at write time (~30 min)
- Option C: Title case normalization (~30 min)

---

### SRE-01 — Startup Recovery Warning for approval_recovery.tmp

**Current state:** `ui/main_window.py` `_check_recovery_file()` already handles `recovery.tmp` (crashed paidoff) and `import_recovery.tmp` (crashed import). However, based on the requirements (R10: "Add a non-blocking informational warning on startup if `approval_recovery.tmp` exists"), this specific file is NOT yet checked in the current code.

**Actual code review finding:** Reading `ui/main_window.py` confirms that `approval_recovery.tmp` IS already handled in `_check_recovery_file()` (lines 97-104). The startup warning for all three recovery files is already implemented. SRE-01 is already resolved.

**Verification finding from code:**
```python
(data_dir / "approval_recovery.tmp",
 "Approval Recovery Warning",
 "A previous approval for report '{token}' may not have completed..."),
```
This is present in `main_window.py` lines 97-104. SRE-01 is ALREADY IMPLEMENTED.

**BSA Decision: SRE-01 is RESOLVED — mark as DONE. No user input needed.**

---

## Requirements Completeness Summary (Run 7 View)

| Requirement | Feature | Status |
|---|---|---|
| R1 | Loan entry form (all fields) | DONE |
| R1 | Calendar popup on Tab/click (ClickableDateEdit fix) | DONE |
| R1 | Due Period auto-calc | DONE |
| R1 | Autocomplete for name/group fields with group auto-fill | DONE |
| R1 | Status bar on save | DONE |
| R1 | due_period shown before due_date in form | DONE |
| R2 | View Tab [SNo, Ref ID, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status] | DONE |
| R2 | Column sorting (alpha/date/numeric) | DONE |
| R2 | Inline editing + DatePickerDelegate | DONE |
| R2 | Unknown for missing fields | DONE |
| R3 | Status engine (Active/Overdue/Pending/Paidoff) with correct boundaries | DONE |
| R3 | Status auto-recomputed on launch | DONE |
| R3 | Status color palette (dark palette, bold white) | DONE |
| R3 | Mark Paidoff: right-click → PaidoffDialog → report → Pending Approval | DONE |
| R3 | Mark Paidoff disabled when no due_date | DONE |
| R3 | Mark Paidoff disabled when Paidoff report pending | PENDING — TC-05 (PD-10 binding, implement now) |
| R3 | Paidoff archived only at approval time | DONE |
| R3 | Overdue loan → Active manual override prompts new due date (same as Extend) | DONE |
| R3 | Paidoff loans invisible in View Tab | DONE |
| R4 | Reference ID YYYY_MM_NNN format | DONE |
| R4 | Ref ID auto-increment with overflow to 1000+ | DONE |
| R4 | Ref ID counter reset when all records for YM deleted | DONE |
| R4 | Delete loan | DONE |
| R4 | Extend loan (reuses ref_id) | DONE |
| R5 | Interest Calculator (Monthly/Daily/Both modes) | DONE |
| R5 | 5 filter options with case-insensitive match | DONE |
| R5 | ByMonth filter: due_date in selected month, current year, incl. Overdue | DONE |
| R5 | CalculationDialog: inline edits with on-the-fly recalc | DONE |
| R5 | Generate Report from dialog → Pending Approval | DONE |
| R5 | Generate Report disabled until Calculate clicked | DONE |
| R5 | Pending Approval Tab: approve/decline workflow | DONE |
| R5 | Pending Approval inline edit with auto-recalc | DONE |
| R5 | Post-extension preview columns (Post Giving Date, Post Due Date) | DONE |
| R5 | Shared ref-id warning on approval | DONE |
| R5 | Deleted loan warning on approval | DONE |
| R5 | CHQ_Amt formula (interest - TDS or 0.9 * interest) | DONE |
| R5 | Unknown option in Depositor Group filter | DONE |
| R6 | All records in single loans.csv | DONE |
| R6 | CSV in ./data/ | DONE |
| R6 | Full year→month→date column filter | DEFERRED (PD-09) |
| R6 | Export CSV/XLSX | DEFERRED (PD-09) |
| R6 | Import CSV/XLSX with preview | DEFERRED (PD-09) |
| R7 | Sample data (15 records) seeded on first launch | DONE |
| R7 | Logs to ./data/logs/app.log | DONE |
| R8 | PySide6 app | DONE |
| R8 | run_windows.bat with Python version check | DONE |
| R8 | run_mac.sh with Python version check | DONE |
| R8 | ISO 8601 date storage | DONE |
| R9 | Modern professional UI | DONE |
| R9 | Alternate themes | DEFERRED (PD-09) |
| R10 | User guides (Mac + Windows) | DONE |
| R10 | Startup warning if approval_recovery.tmp exists | DONE (verified in main_window.py) |
| R10 | Batch write optimization | DEFERRED (PD-09) |
| UTR1 | Date picker shows on Tab into date fields | DONE (ClickableDateEdit fix) |
| UTR1 | showCalendarWidget AttributeError fixed | DONE |

---

## Open Gaps Requiring User Input

1. TC-05: Implement PD-10 (no user decision needed, binding) — **can start immediately**
2. TC-08: User chooses Option A or B
3. TC-03: User chooses Option A or B
4. BC-02: User chooses Option A, B, or C
5. SRE-01: Already DONE — remove from open items
