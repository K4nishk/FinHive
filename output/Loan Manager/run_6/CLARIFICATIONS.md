# Loan Manager — Phase 3 Closure: CLARIFICATIONS
**Run:** run_6
**Date:** 2026-04-04
**Phase:** Phase 3 Closure / Phase 4 MVP Kickoff Readiness

---

## PO Decisions (Binding — Resolved This Run)

The following items were raised as [REVIEW REQUIRED] by downstream agents and have been resolved by the PO from REQUIREMENTS.md. No user input needed.

| ID | Item | Decision | Requirements Reference |
|---|---|---|---|
| PD-07 | Tab-level Generate Report button | Remains present, gated by _calculated flag. Dialog is primary path. No UI removal needed. | R5: sequential Calculate → review dialog → Generate Report workflow |
| PD-08 | View Tab refresh after Paidoff report generated | No refresh. Loan stays visible until Paidoff report approved. | R3: "loan will be moved to history when the report is approved" |
| PD-09 | Deferred post-MVP items confirmed out of scope | R9 themes, R6 hierarchical filter, R6 Import/Export, R10 batch write, R3 atomic write deferred | R8: "Prototype to be good representation of all features" — not perfection |
| PD-10 | TC-05: Double Paidoff Guard | Option A — BINDING. Disable "Mark Paidoff" when Paidoff report already pending. R3 text is explicit. | R3: "Disable Mark Paidoff if a Paidoff report for that loan is already pending." |
| PD-11 | STATUS_COLORS import in test | Safe to import from ui.view_tab in pytest without QApplication | Implementation detail — no QApplication needed for dict import |
| PD-12 | has_pending_paidoff_report() location | Belongs in data/report_manager.py | Architecture: report_manager owns all report/record persistence |

### Carry-Forward Decisions (run_5 — Still Binding)

| ID | Item | Decision |
|---|---|---|
| PD-01 | Seed guard | Seed when absent or header-only only |
| PD-02 | Paidoff state machine | No transient status; archive at approval |
| PD-03 | DatePickerDelegate ISO format | ISO 8601 YYYY-MM-DD confirmed |
| PD-04 | CHQ_Amt persistence | Derive on display only |
| PD-05 | due_period storage | Not stored; UI-only field |
| PD-06 | Calculation dialog behavior | Modal; primary Generate Report path |

---

## Technical Clarifications (Require User Input)

### TC-08: paidoff_date Field in ReportRecord

**Context:** When a Paidoff report is generated, the user's entered `paidoff_date` is currently stored in `ReportRecord.new_due_date` (field reuse). For regular extension reports, `new_due_date` means post-extension due date. For Paidoff-mode reports, it means paidoff_date. This dual semantic works correctly today but creates ambiguity.

**Options:**
- **Option A:** Accept field reuse. Document that for mode="Paidoff", `new_due_date` = `paidoff_date`. No schema change. No code change.
- **Option B:** Add dedicated `paidoff_date: Optional[date]` column to `ReportRecord` dataclass and `pending_report_records.csv`. Additive change — no migration needed. Paidoff-mode writes `paidoff_date=<date>`, `new_due_date=None`. Approval reads `rec.paidoff_date`.

**Agents' Recommendation:** Option B (DM, SA, Dev Lead, Backend QA all recommend Option B for cleaner schema).

**Why this matters:** Option B requires updates to models/report.py, data/report_manager.py, ui/view_tab.py (`_action_paidoff()`), and ui/pending_approval_tab.py (`_on_approve()`). Option A requires only documentation (zero code change). Existing pending_report_records.csv files are unaffected either way.

**Impact on Phase 4 timeline:** Option B adds ~2 hours of implementation. Option A is zero effort.

---

### TC-03: due_period + due_date Edit Conflict

**Context:** In the Entry Tab, entering a Due Period (e.g., 3 months) auto-calculates the Due Date. If the user then manually edits the Due Date via the calendar picker, the Due Period field still shows "3" even though the due_date may no longer be 3 months from the giving_date.

**Options:**
- **Option A:** Clear Due Period (set to 0) when user manually edits Due Date. Prevents misleading display.
- **Option B (Current):** Leave Due Period as-is. User knowingly overrode due_date. due_period is UI-only (not persisted) and has no effect after the initial auto-calc.

**All agents' recommendation:** Option B unless the user finds the retained value confusing.

**Why this matters:** Option A adds a guard flag (`_suppressing_date_signal`) and an additional signal connection in entry_tab.py. Option B is zero code change. The stored data (due_date) is correct under both options.

---

## Business Clarifications (Require User Input)

### BC-02: Case Normalization for Stored Loan Names

**Context:** The Interest Calculator filter bug (UTR1) is resolved using case-insensitive comparison (`.lower()` on both sides). Filter matching works correctly regardless of stored case. However, filter dropdowns display values as stored. If different records store "BG1" and "bg1", both appear as separate dropdown entries (but both match correctly when selected).

**Options:**
- **Option A (No change):** Filter comparison uses `.lower()`, dropdowns show values as typed. May show duplicates if user enters names inconsistently.
- **Option B:** Normalize to lowercase at write time (`write_loan()` normalizes `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group`).
- **Option C:** Normalize to title case at write time. "bg1" → "Bg1".

**Agents' Recommendation:** Option B. Consistent with existing sample data (b1, bg1, d1, dg1 are all lowercase). Simple and clean.

**Why this matters:** Pure cosmetic preference. No functional impact on filtering. Option B or C are equally trivial to implement (one function + 4 field applications in csv_manager.py).

---

### SRE-01: Startup Recovery Warning

**Context:** When the application crashes during a Paidoff or batch-extend approval (between the first and second CSV write), `approval_recovery.tmp` is left on disk. Currently the application does not check for this file on startup — the user has no indication that a recovery scenario may have occurred.

**Proposal:** Add a non-blocking informational warning on startup if `approval_recovery.tmp` exists: "An approval was in progress when the application last closed. Please check the Pending Approval queue and verify loan records."

**Why this matters:** Low effort (15 lines in main.py). Provides operational visibility into a partial-write scenario. Does not block app startup or require user action.

**Question:** Should this be included in Phase 4 or deferred to post-MVP?

---

## Phase 3 Closure: Implementation Completeness Summary

### All Requirements — Phase 3 Status

| Requirement | Feature | Status |
|---|---|---|
| R1 | Loan entry form with all fields | DONE |
| R1 | Calendar popup on Tab/click | DONE (ClickableDateEdit) |
| R1 | Due Period auto-calc (due_date = giving + period months) | DONE |
| R1 | Autocomplete for name/group fields | DONE |
| R1 | Status bar on save: "Loan saved successfully. Reference ID: {ref_id}." | DONE |
| R2 | View Tab with all columns [SNo, Ref ID, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status] | DONE |
| R2 | Column sorting (alpha, date, numeric) | DONE |
| R2 | Inline editing for all editable columns | DONE |
| R2 | DatePickerDelegate for date column inline edits | DONE |
| R3 | Status engine: Active/Overdue/Pending/Paidoff | DONE |
| R3 | Status auto-recomputed on every launch | DONE |
| R3 | Status color palette with bold white text | DONE |
| R3 | Mark Paidoff: right-click → dialog → report → Pending Approval | DONE |
| R3 | Mark Paidoff disabled when no due_date | DONE |
| R3 | Mark Paidoff disabled when Paidoff report already pending | PENDING (TC-05 — PD-10 binding: implement Option A) |
| R3 | Paidoff archived at approval time only | DONE |
| R4 | Reference ID YYYY_MM_NNN format | DONE |
| R4 | Ref ID increment, overflow to 1000+ | DONE |
| R4 | Delete loan | DONE |
| R4 | Extend loan (reuse ref_id) | DONE |
| R5 | Interest Calculator Tab (Monthly/Daily/Both modes) | DONE |
| R5 | 5 filter options with case-insensitive matching | DONE (UTR1) |
| R5 | CalculationDialog (modal, on-the-fly recalc) | DONE |
| R5 | Generate Report from dialog → Pending Approval | DONE |
| R5 | Pending Approval Tab with approve/decline | DONE |
| R5 | Inline editable records in Pending Approval with auto-recalc | DONE |
| R5 | Post-extension preview columns | DONE |
| R5 | Shared ref-id warning | DONE |
| R5 | Deleted loan warning on approval | DONE |
| R5 | CHQ_Amt formula | DONE |
| R6 | Single loans.csv for all records | DONE |
| R6 | CSV in ./data/ subfolder | DONE |
| R6 | Full hierarchical date filter (year→month) | DEFERRED post-MVP |
| R6 | Export CSV/XLSX | DEFERRED post-MVP |
| R6 | Import CSV/XLSX with preview | DEFERRED post-MVP |
| R7 | Sample data seeding (15 records) on first launch | DONE |
| R7 | Logs to ./data/logs/app.log | DONE |
| R8 | PySide6 app | DONE |
| R8 | run_windows.bat with Python version check | DONE |
| R8 | run_mac.sh with Python version check | DONE |
| R8 | ISO 8601 date storage | DONE |
| R9 | Modern professional UI | DONE (baseline) |
| R9 | Alternate theme choices | DEFERRED post-MVP |
| R10 | User guides for Mac and Windows | DONE |
| R10 | Batch write optimization | DEFERRED post-MVP |
| UTR1 | Case-insensitive filter fix | DONE |
| UTR1 | Readable color palette | DONE |
| UTR1 | ClickableDateEdit.showCalendarWidget() bug fix | DONE |

---

## Remaining Test Coverage Gaps

| Test File | Requirement | Can Create Now? |
|---|---|---|
| tests/test_view_tab_colors.py | R3 STATUS_COLORS | YES — no blockers |
| tests/test_entry_tab_logic.py (due_period calc) | R1 | YES — pure calculation |
| tests/test_view_tab_paidoff.py | R3, TC-05 | YES for mark_paidoff() tests; has_pending_paidoff_report() after PD-10 implementation |
| tests/test_pending_approval.py (batch_extend) | R5 | YES for batch_extend() tests |
| tests/test_pending_approval.py (paidoff_date) | TC-08 | After TC-08 user decision |

---

## PO TLDR

### Product Summary

The Loan Manager is a single-user PySide6 desktop application for Windows (with Mac cross-platform support) that manages personal and business loans. It tracks loan entries with auto-generated reference IDs, computes interest in three modes (Monthly/Daily/Both), manages a Pending Approval workflow for batch extensions and Paidoff archival, and persists all data in CSV files. After three implementation phases (run_1 through run_5), all core features are complete and the application is functionally ready for MVP user acceptance testing. One binding PO decision (PD-10: TC-05 Option A) was issued this run, reducing the user decision burden from 4 items (run_5) to 3 items.

### Phase Recommendation

| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Core: Entry Tab, View Tab, Status Engine, Ref ID | COMPLETE |
| Phase 2 | Interest Calculator, Pending Approval, Report Gen, Paidoff v1 | COMPLETE |
| Phase 3 | R5 Dialog, R3 Paidoff Redesign, R1 Due Period, R2 Date Picker, UTR1 Fix, R7 Seed, Color Palette | COMPLETE |
| Phase 4 (Current) | TC-05 guard (PD-10 binding), TC-08/TC-03/BC-02 per user decisions, remaining test files, pytest gate | Ready after 3 user decisions |
| Phase 5 (MVP UAT) | Mac tester smoke tests, Windows end-to-end, Go/No-Go | After Phase 4 completion |

### PO Decisions Issued This Run

| ID | Item | Decision | Rationale |
|---|---|---|---|
| PD-07 | Tab-level Generate Report button | No change needed | Dialog is primary path; button gated by _calculated flag |
| PD-08 | View Tab refresh after Paidoff report | No refresh until approval | R3: loan archived at approval, not generation |
| PD-09 | Post-MVP deferred items | Confirmed out of Phase 4 scope | R8: prototype represents features, not perfection |
| PD-10 | TC-05 Double Paidoff Guard | Option A BINDING — disable Mark Paidoff when Paidoff report pending | R3 explicitly states "Disable Mark Paidoff if a Paidoff report for that loan is already pending" |
| PD-11 | STATUS_COLORS test import | Safe to import from ui.view_tab in pytest | No QApplication needed for module-level dict |
| PD-12 | has_pending_paidoff_report() location | data/report_manager.py | Architectural consistency with existing report logic |

### Where User Clarity is Required (Priority Order)

1. **TC-08 — paidoff_date Field in ReportRecord** (MEDIUM PRIORITY)
   All agents recommend Option B (dedicated column). Zero migration risk. Additive change. If user prefers zero code change, Option A also works — just document the dual semantic in code comments.
   **User question:** Prefer clean schema (Option B, ~2 hours work) or accept field reuse (Option A, zero work)?

2. **TC-03 — due_period Display After Manual due_date Edit** (LOW PRIORITY — UX preference)
   Current behavior (Option B): Due Period field retains its value after user manually edits Due Date. This is technically correct (due_date is what's stored, due_period is just a UI helper). Option A would clear the period, which is cleaner visually.
   **User question:** Does seeing "3 months" in Due Period after manually changing Due Date to a different date cause confusion? If yes, implement Option A.

3. **SRE-01 — Startup Recovery Warning** (LOW PRIORITY — operational feature)
   Adds a non-blocking warning if application crashed mid-approval. Low effort. Improves operational awareness.
   **User question:** Include startup recovery warning in Phase 4, or defer to post-MVP?

4. **BC-02 — Case Normalization for Names** (COSMETIC — lowest priority)
   Purely cosmetic. Filter works correctly under all options. Recommend Option B (lowercase) for consistency with sample data.
   **User question:** Option A (no change), Option B (lowercase), or Option C (title case)?

### Phase 4 Implementation Path

Once user provides the 3 answers above:

1. Implement TC-05 Option A (PD-10 binding — can start immediately)
   - Add `has_pending_paidoff_report()` to data/report_manager.py
   - Update `_show_context_menu()` in ui/view_tab.py

2. Implement TC-08 per user decision

3. Implement TC-03 per user decision (or no change if Option B confirmed)

4. Implement BC-02 per user decision (or no change if Option A confirmed)

5. Optionally implement SRE-01 startup warning

6. Create remaining test files (test_view_tab_colors.py can be created immediately)

7. Run `pytest --tb=short` from `src/Loan Manager/` — must pass 0 failures

8. Mac tester runs manual smoke tests M-R1-01 through M-TC05

9. End user runs run_windows.bat on Windows

10. Go/No-Go: Phase 5 UAT
