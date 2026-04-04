# Loan Manager — PO Decisions
**Agent:** po-agent (Wave 0 Initial Triage + Wave 3 Synthesis)
**Run:** run_6
**Date:** 2026-04-04
**Phase:** Phase 3 Closure / Phase 4 MVP Kickoff

---

## Wave 0: PO Initial Triage

### Run_5 Carry-Forward Decisions (Binding — Already Issued)

The following decisions from run_5 are confirmed and carried forward. No re-escalation needed:

| PO Decision | Status | Decision |
|---|---|---|
| PD-01: Seed when absent/header-only | CONFIRMED | Implemented in data/seed.py |
| PD-02: No transient Paidoff status | CONFIRMED | mark_paidoff() only at approval |
| PD-03: DatePickerDelegate ISO format | CONFIRMED | YYYY-MM-DD in setModelData() |
| PD-04: CHQ_Amt derived on display only | CONFIRMED | Not stored in CSV |
| PD-05: due_period not stored | CONFIRMED | UI-only field |
| PD-06: Modal CalculationDialog | CONFIRMED | setModal(True), dialog.exec() |

### New PO Scope Decisions (Wave 0)

**PD-07:** The Generate Report button in the InterestCalculatorTab remains present in the UI but is gated by `_calculated = False` by default. Since the CalculationDialog is now the primary path for report generation, the tab-level button is effectively a no-op until Calculate is clicked. This is acceptable for prototype scope. No UI removal needed.

**PD-08:** The View Tab does NOT need to refresh after a Paidoff report is generated (report is created, not applied). Loan stays visible at its current status until approval. This confirms the current implementation: no `load_data()` call after `_action_paidoff()`.

**PD-09:** Deferred items for post-MVP are confirmed as explicitly out of scope for Phase 4:
- R9 alternate themes
- R6 hierarchical date filter (full year→month→date hierarchy)
- R6 Import/Export CSV/XLSX
- R10 batch write optimization
- R3 full atomic write / timestamped backup

---

## Wave 3: PO Synthesis — [REVIEW REQUIRED] Item Resolution

### Items Collected from Wave 1 + Wave 2 Outputs

| ID | Source Agent | Item | Resolvable from REQUIREMENTS.md? |
|---|---|---|---|
| TC-03 | BSA, Dev Lead | due_period + due_date conflict | NO — user preference |
| TC-05 | BSA, SA, Dev Lead, Backend QA | Double Paidoff report guard | YES — R3 partially; Option A preferred |
| TC-08 | BSA, SA, DM, Dev Lead, Backend QA | paidoff_date field storage | NO — schema preference |
| BC-02 | BSA, DM | Case normalization | NO — cosmetic preference |
| SRE-01 | SRE | Startup recovery.tmp warning | NO — user preference on feature |
| BACKEND-QA-01 | Backend QA | STATUS_COLORS import test | YES — implementable as pure import test |
| BACKEND-QA-02 | Backend QA | has_pending_paidoff_report() import location | YES — belongs in report_manager.py |

### PO Resolutions

**PD-10: TC-05 Resolution**
REQUIREMENTS.md R3 states: "Disable 'Mark Paidoff' if a Paidoff report for that loan is already pending." This is an explicit statement. PO rules Option A (disable) as the required behavior based on R3 text.

Decision: IMPLEMENT TC-05 Option A. Guard belongs in report_manager.py as `has_pending_paidoff_report()`. View Tab calls it at context menu build time.

**PD-11: BACKEND-QA-01 Resolution**
STATUS_COLORS is a module-level dict assigned before any QApplication is required. PySide6 widget class definitions do not instantiate QApplication. Importing `from ui.view_tab import STATUS_COLORS` will succeed in pytest without a QApplication instance as long as the import doesn't trigger `QApplication()`. Confirmed safe.

Decision: test_view_tab_colors.py can import from ui.view_tab directly. No QApplication needed for dict-only test.

**PD-12: BACKEND-QA-02 Resolution**
`has_pending_paidoff_report()` belongs in `data/report_manager.py` — the module already owns all report and record persistence logic. Confirmed by SA ADR-TC05-01.

Decision: Import path is `from data.report_manager import has_pending_paidoff_report`.

### [REVIEW REQUIRED] Items Remaining for User

After PO resolution, the following items require genuine user input:

1. **TC-05**: Already resolved by PD-10 (Option A — disable). No user input needed. PO decision is binding.

2. **TC-08**: Requires user input — Option A (field reuse) vs Option B (dedicated column). PO leans Option B but this is a user schema preference.

3. **TC-03**: Requires user input — Option A (clear period) vs Option B (keep period). Pure UX preference.

4. **BC-02**: Requires user input — Option A/B/C. Cosmetic preference.

5. **SRE-01**: Startup recovery warning — recommend including but not blocking. User to confirm whether to include in Phase 4 or defer.

---

## PO Integrated Action Plan

| Owner | Action | By When |
|---|---|---|
| PO | Issue user clarifications for TC-08, TC-03, BC-02, SRE-01 | Phase 4 kickoff |
| Dev Lead | Implement TC-05 Option A (PD-10 binding decision) | After Phase 4 kickoff |
| Backend QA | Create test_view_tab_colors.py immediately (no blockers) | Immediately |
| Backend QA | Create test_entry_tab_logic.py due_period calc tests | Immediately |
| Dev Lead | Implement TC-08 per user decision | After TC-08 answer |
| Dev Lead | Implement TC-03 per user decision | After TC-03 answer |
| Dev Lead | Implement BC-02 per user decision | After BC-02 answer |
| Dev Lead | Implement SRE-01 startup check (low effort) | Phase 4 sprint |
| QA Lead | Run pytest suite after all Phase 4 items implemented | Phase 4 exit |
| Mac Tester | Manual smoke tests M-R1-01 through M-TC05 | After pytest gate |
| End User | Windows run_windows.bat end-to-end test | Phase 5 UAT |
