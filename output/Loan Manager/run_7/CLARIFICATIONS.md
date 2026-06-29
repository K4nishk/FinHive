# Loan Manager — Phase 3 Closure: CLARIFICATIONS
**Run:** run_7
**Date:** 2026-04-05
**Phase:** Phase 3 Closure / Phase 4 MVP Kickoff

---

## PO Decisions (Binding — Resolved This Run)

| ID | Item | Decision | Requirements Reference |
|---|---|---|---|
| PD-13 | SRE-01: Startup approval_recovery.tmp warning | DONE — already implemented in main_window._check_recovery_file() | R10: "Add a non-blocking informational warning on startup if approval_recovery.tmp exists" — confirmed present in code |

### All Prior Binding Decisions (run_5 + run_6) — Still Active

| ID | Item | Decision |
|---|---|---|
| PD-01 | Seed guard | Seed when absent or header-only |
| PD-02 | Paidoff state machine | Archive at approval only |
| PD-03 | DatePickerDelegate ISO format | YYYY-MM-DD confirmed |
| PD-04 | CHQ_Amt persistence | Derive on display only |
| PD-05 | due_period storage | Not stored; UI-only |
| PD-06 | Calculation dialog | Modal; primary Generate Report path |
| PD-07 | Tab-level Generate Report | No change; gated by _calculated flag |
| PD-08 | View Tab after Paidoff report | No refresh until approval |
| PD-09 | Post-MVP deferred items | R9 themes, R6 import/export, R6 hierarchical filter, R10 batch write, R3 atomic backup — all deferred |
| PD-10 | TC-05 Double Paidoff Guard | Option A BINDING — disable Mark Paidoff when Paidoff report pending |
| PD-11 | STATUS_COLORS test import | Safe from ui.view_tab in pytest |
| PD-12 | has_pending_paidoff_report() location | data/report_manager.py |

---

## Technical Clarifications (Require User Input)

### TC-08: paidoff_date Field in ReportRecord

**Context:** When a Paidoff report is generated in `_action_paidoff()`, `paidoff_date` is currently stored in `ReportRecord.new_due_date`. For extension reports, `new_due_date` is the post-extension due date. For Paidoff-mode reports, it is the paidoff date. This dual semantic works correctly today but creates potential confusion.

**Options:**
- **Option A (zero code change):** Accept field reuse. Document in code comments. `new_due_date` = `paidoff_date` for mode="Paidoff". No schema or code change needed.
- **Option B (DM/SA/Dev Lead recommended):** Add dedicated `paidoff_date: Optional[date] = None` column to ReportRecord dataclass and `pending_report_records.csv`. Additive change — no migration, no data loss. Old records parse with `paidoff_date=""` → `None`. Backward-compatible approval logic reads `rec.paidoff_date or rec.new_due_date`.

**Affected files (Option B only):** `models/report.py`, `loan_manager/report_manager.py`, `ui/view_tab.py` (_action_paidoff), `ui/pending_approval_tab.py` (_on_approve)

**Effort:** Option A = 0 hours. Option B = ~2 hours.

**All agents recommend Option B** for semantic clarity. Option A also works correctly for prototype.

**User question:** Do you prefer clean dedicated schema (Option B) or accept field reuse (Option A)?

---

### TC-03: due_period Display After Manual due_date Edit

**Context:** In the Entry Tab, entering Due Period (e.g., 3) auto-calculates Due Date. If user then manually changes Due Date via the calendar picker, Due Period spinbox still shows "3" even though due_date is now different. `due_period` is not persisted — only `due_date` is saved.

**Options:**
- **Option A:** Clear Due Period to 0 / "Not set" when user manually edits Due Date. Prevents misleading display.
- **Option B (current, recommended by all agents):** Leave Due Period as-is. User knowingly overrode due_date. The due_period field is a UI helper only — stored value is always `due_date`, which is correct.

**Effort:** Option A = ~30 minutes. Option B = 0 (no change).

**User question:** Does seeing "3 months" in Due Period after you manually changed Due Date cause confusion? If yes → Option A. If you understand it's just a UI helper → Option B (no change needed).

---

## Business Clarifications (Require User Input)

### BC-02: Case Normalization for Stored Loan Names

**Context:** Filter matching uses case-insensitive `.lower()` comparisons (UTR1 fix — works correctly). However, filter dropdowns display values exactly as stored. If user enters "BG1" in one record and "bg1" in another, both appear as separate dropdown entries (though both match when selected).

**Options:**
- **Option A (no change):** Filter works correctly via `.lower()`. Dropdowns show values as typed. May show cosmetic duplicates if user is inconsistent.
- **Option B (recommended):** Normalize `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group` to lowercase at write time in `write_loan()`. Consistent with sample data convention (all lowercase: b1, bg1, d1, dg1).
- **Option C:** Normalize to title case at write time.

**Effort:** Option A = 0. Option B/C = ~30 minutes.

**User question:** Option A (no change), Option B (lowercase), or Option C (title case)?

---

## Phase 3 Closure: Implementation Completeness

### All Requirements — Final Status

| Requirement | Feature | Status |
|---|---|---|
| R1 | Loan entry form with all 8 fields | DONE |
| R1 | due_period shown before due_date in form | DONE |
| R1 | Calendar popup on Tab/click (ClickableDateEdit) | DONE |
| R1 | UTR1: showCalendarWidget AttributeError fixed | DONE |
| R1 | Due Period auto-calc: due_date = giving + period months | DONE |
| R1 | No Due Date checkbox | DONE |
| R1 | Autocomplete for name/group fields | DONE |
| R1 | Group auto-fill from history | DONE |
| R1 | Status bar on save: "Loan saved successfully. Reference ID: {ref_id}." | DONE |
| R1 | Amount: non-negative integer, INR | DONE |
| R2 | View Tab [SNo, Ref ID, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status] | DONE |
| R2 | Column sorting: alpha, date, numeric | DONE |
| R2 | Inline editing for all editable columns | DONE |
| R2 | DatePickerDelegate for date column inline edits | DONE |
| R2 | Unknown for missing fields (depositor_name, depositor_group, due_date) | DONE |
| R3 | Status engine: Active/Overdue/Pending/Paidoff | DONE |
| R3 | Status boundaries: giving>today→Pending; no due_date→Overdue; today<due→Active; today>=due→Overdue | DONE |
| R3 | Status auto-recomputed on every launch | DONE |
| R3 | Status color palette (dark palette, bold white text) | DONE |
| R3 | Mark Paidoff: right-click → PaidoffDialog → report → Pending Approval | DONE |
| R3 | Mark Paidoff disabled when no due_date | DONE |
| R3 | Mark Paidoff disabled when Paidoff report pending | PENDING — TC-05 (PD-10 BINDING — implement immediately) |
| R3 | Paidoff warning in Pending Approval Tab | DONE |
| R3 | Paidoff archived only at approval time | DONE |
| R3 | Paidoff loans removed from View Tab after approval | DONE |
| R3 | history.csv maintained with paidoff_date | DONE |
| R3 | recovery.tmp crash safety for paidoff | DONE |
| R3 | Active manual override prompts new due date | DONE |
| R4 | Reference ID YYYY_MM_NNN format | DONE |
| R4 | Ref ID increment with overflow >999 | DONE |
| R4 | Counter reset when all records for YM deleted | DONE |
| R4 | Counter from loans_meta.csv (high-water mark) | DONE |
| R4 | Delete loan | DONE |
| R4 | Extend loan (reuse ref_id, new giving=old due, new due=old due+period) | DONE |
| R5 | Interest Calculator: Monthly/Daily/Both modes | DONE |
| R5 | 5 filter options (Borrower Group, Borrower Name, Depositor Name, Depositor Group, ByMonth) | DONE |
| R5 | Case-insensitive filter matching (UTR1) | DONE |
| R5 | Unknown option in Depositor Group filter | DONE |
| R5 | No filter: show only no-due-date loans | DONE |
| R5 | Any filter: exclude no-due-date loans | DONE |
| R5 | ByMonth: due_date in selected month, current year, including Overdue | DONE |
| R5 | Global parameters applied to all filtered records | DONE |
| R5 | Global param change overwrites all rows | DONE |
| R5 | CalculationDialog: modal, inline editable, on-the-fly recalc | DONE |
| R5 | CHQ_Amt = interest - TDS (tds_flag=True) or 0.9*interest (tds_flag=False) | DONE |
| R5 | Generate Report disabled until Calculate clicked | DONE |
| R5 | Generate Report from dialog → Pending Approval | DONE |
| R5 | Pending Approval Tab: report list + record detail | DONE |
| R5 | Post-extension preview: Post Giving Date, Post Due Date | DONE |
| R5 | Inline editable records in Pending Approval with auto-recalc | DONE |
| R5 | Shared ref-id warning on approval | DONE |
| R5 | Deleted loan warning on approval | DONE |
| R5 | Approve: batch-extends loans (regular) or marks paidoff (Paidoff mode) | DONE |
| R5 | Decline: deletes records, marks report Declined | DONE |
| R5 | Reports persist across restarts (CSV) | DONE |
| R5 | two-file approach: pending_reports.csv + pending_report_records.csv | DONE |
| R5 | approval_recovery.tmp crash safety | DONE |
| R6 | Single loans.csv for all records | DONE |
| R6 | CSV in ./data/ subfolder | DONE |
| R6 | Full year→month→date column filter | DEFERRED (PD-09) |
| R6 | Export CSV/XLSX | DEFERRED (PD-09) |
| R6 | Import CSV/XLSX with preview | DEFERRED (PD-09) |
| R7 | Sample data (15 records) seeded on first launch | DONE |
| R7 | Logs to ./data/logs/app.log | DONE |
| R7 | Can loan without due_date become Overdue? YES | DONE |
| R7 | Extend for no-due-date loans: giving=today, due=user-picked | DONE |
| R8 | PySide6 desktop app | DONE |
| R8 | run_windows.bat with Python version check | DONE |
| R8 | run_mac.sh with Python version check | DONE |
| R8 | ISO 8601 date storage | DONE |
| R8 | No CSV file locking | DONE |
| R9 | Modern professional UI (baseline) | DONE |
| R9 | Alternate theme choices | DEFERRED (PD-09) |
| R10 | User guide for Mac and Windows in /user_guides/ | DONE |
| R10 | Python version check in both scripts | DONE |
| R10 | Startup warning if approval_recovery.tmp exists | DONE (PD-13 — confirmed in code) |
| R10 | Batch write optimization | DEFERRED (PD-09) |
| UTR1 | Date picker opens on Tab into date fields | DONE |
| UTR1 | showCalendarWidget AttributeError resolved | DONE |
| UTR1 | Filter case-insensitive matching | DONE |

---

## Remaining Test Coverage Gaps

| Test File | Covers | Can Create Now? |
|---|---|---|
| tests/test_view_tab_colors.py | R3 STATUS_COLORS values | YES — no blockers |
| tests/test_entry_tab_logic.py | R1 due_period calculation | YES — no blockers |
| tests/test_view_tab_paidoff.py | R3 TC-05 has_pending_paidoff_report() | After TC-05 implementation |
| tests/test_pending_approval.py (batch_extend) | R5 batch approval | YES — no blockers |
| tests/test_pending_approval.py (paidoff_date) | TC-08 | After TC-08 user decision (Option B) |
| tests/test_csv_manager.py (BC-02) | BC-02 | After BC-02 user decision |

---

## PO TLDR

### Product Summary

The Loan Manager is a single-user PySide6 desktop application for Windows (with Mac cross-platform support) that manages personal and business loans. It provides loan entry with auto-generated reference IDs, a sortable and inline-editable view with status tracking, an interest calculator in Monthly/Daily/Both modes with a Pending Approval workflow, and CSV-backed persistence. After three implementation phases spanning runs 1–6, all core features are complete and the application is functionally ready for MVP user acceptance testing. This run (run_7) provides Phase 3 closure confirmation with the important finding that SRE-01 (startup recovery warning) is already implemented, reducing open user decisions from 4 to 3.

### Phase Recommendation

| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Core: Entry Tab, View Tab, Status Engine, Ref ID | COMPLETE |
| Phase 2 | Interest Calculator, Pending Approval, Report Gen, Paidoff v1 | COMPLETE |
| Phase 3 | R5 Dialog, R3 Paidoff Redesign, R1 Due Period, R2 Date Picker, UTR1 Fix, R7 Seed, Color Palette, SRE-01 | COMPLETE |
| Phase 4 (current) | TC-05 guard (PD-10 binding), TC-08/TC-03/BC-02 per user decisions, 4 test files, pytest gate | Ready to start — TC-05 unblocked |
| Phase 5 (MVP UAT) | Mac smoke tests, Windows E2E, Go/No-Go | After Phase 4 |

### PO Decisions Issued This Run

| ID | Item | Decision | Rationale |
|---|---|---|---|
| PD-13 | SRE-01: startup approval_recovery.tmp warning | DONE — already in code | Code review of main_window.py confirms _check_recovery_file() handles all 3 recovery file types including approval_recovery.tmp |

### Where User Clarity is Required (Priority Order — Reduced to 3 Items)

**1. TC-08 — paidoff_date Field in ReportRecord** (MEDIUM — schema preference)

All agents recommend Option B (dedicated `paidoff_date` column). Additive schema change. ~2 hours. No migration needed. Option A (field reuse) also works correctly — zero code change.

**User question:** Option A (field reuse, zero work) or Option B (dedicated column, ~2 hours, cleaner schema)?

---

**2. TC-03 — due_period Display After Manual due_date Edit** (LOW — UX preference)

Current behavior: Due Period retains its value after user manually picks a different Due Date. Since `due_period` is UI-only (not stored), the stored `due_date` is always correct. Option A clears the period (30 min). Option B keeps current behavior (zero effort).

**User question:** Does seeing "3 months" in Due Period after manually changing Due Date cause confusion? If yes → Option A. Otherwise → Option B (no change).

---

**3. BC-02 — Case Normalization for Names** (COSMETIC — lowest priority)

Filter comparison already works case-insensitively. This is purely about dropdown display consistency.

**User question:** Option A (no change), Option B (lowercase at write time — consistent with sample data), or Option C (title case)?

---

### Phase 4 Immediate Actions (No User Decision Needed)

The following can start today without waiting for the 3 user decisions above:

1. **Implement TC-05** (PD-10 binding): Add `has_pending_paidoff_report()` to `loan_manager/report_manager.py` and `data/report_manager.py`, update `ui/view_tab.py` `_show_context_menu()`. ~1 hour.

2. **Create test_view_tab_colors.py**: 6 assertions on STATUS_COLORS. ~20 minutes.

3. **Create test_entry_tab_logic.py**: 7 assertions on due_period calculation. ~30 minutes.

4. **Create test_pending_approval.py** (batch_extend portion): 2 tests. ~30 minutes.

Once user provides the 3 answers above:
5. Implement TC-08 per decision
6. Implement TC-03 per decision (or confirm Option B = no change)
7. Implement BC-02 per decision
8. Complete remaining test files
9. Run `pytest --tb=short` from `src/Loan Manager/` — 0 failures
10. Mac tester smoke tests → Windows UAT → Go/No-Go
