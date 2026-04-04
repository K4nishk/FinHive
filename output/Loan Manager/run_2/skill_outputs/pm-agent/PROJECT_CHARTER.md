# PM: Project Charter — Loan Manager

**Document Version:** 2.0
**Date:** 2026-04-03
**Run:** run_2 / Wave 0
**Author:** PM Agent
**Supersedes:** run_1/skill_outputs/pm-agent/PROJECT_CHARTER.md

---

## 1. Run_2 Delta Summary

This charter is a targeted update for run_2. The overall project charter from run_1 remains valid. This document records only what changed, the sprint plan for Phase 3 closure, updated risks, and the Phase 4 readiness gate.

### 1.1 Requirement Changes vs. run_1

| Change ID | Requirement | Description | Scope Classification |
|---|---|---|---|
| CHG-01 | R1 | `No Due Date` checkbox must default to checked state | Bug/Behaviour fix — Entry Tab |
| CHG-02 | R3 | Paidoff flow now generates an interest report (Daily Calculator, `extension_period = paidoff_date - due_date`) sent to Pending Approval | New capability — adds R3 → R5 integration |
| CHG-03 | R10 | Python version check elevated from [Low priority] to mandatory | Priority re-classification — launchers |
| BUG-01 | UT-R1 | Interest Calculator filters (BorrowerGroup, BorrowerName, DepositorName, DepositorGroup) reset to "All" on apply | P1 defect |
| BUG-02 | UT-R1 | View Tab color palette — light backgrounds with white text makes data unreadable | P1 UI defect |
| BUG-03 | UT-R1 | Paidoff marking flow broken/untestable from View Tab | P1 defect |
| BUG-04 | UT-R1 | Windows date picker must open on field click, not dropdown toggle only | P2 UX defect |
| DOC-01 | Sample Input | Date format in sample data documentation changed from YYYY-MM-DD to DD-MM-YYYY | Documentation-only; verify import parser handles DD-MM-YYYY input |

---

## 2. Run_2 Scope Baseline

### 2.1 In-Scope for run_2 (Phase 3 Closure)

| Item ID | Description | Priority |
|---|---|---|
| BUG-01 | Fix Interest Calculator filter reset for BorrowerGroup / BorrowerName / DepositorName / DepositorGroup combo boxes | P1 — must fix |
| BUG-02 | Fix View Tab color palette: replace light-background + white-text with legible high-contrast scheme | P1 — must fix |
| BUG-03 | Fix Paidoff marking flow: ensure context-menu Mark Paidoff and QComboBox Paidoff selection both reliably trigger PaidoffDialog | P1 — must fix |
| BUG-04 | Fix Windows date picker: QDateEdit fields open calendar popup on any click, not only on dropdown arrow | P2 — must fix |
| CHG-01 | Default `No Due Date` checkbox to checked state in Entry Tab | Behaviour change — R1 |
| CHG-02 | Paidoff flow generates Daily interest report: compute `extension_period_days = paidoff_date - due_date`, create ReportRecord using calculate_daily(), send to Pending Approval queue | New capability — R3 + R5 |
| CHG-03 | Verify Python version check is present and non-optional in both `run_windows.bat` and `run_mac.sh` | Already implemented per run_1 code review — confirm in validation |
| DOC-01 | Confirm import parser correctly handles DD-MM-YYYY format for `giving_date` / `due_date` and documents this in user guide | Verification + documentation |

### 2.2 Out-of-Scope for run_2

- Re-implementation of any already-passing Phase 1 or Phase 2 features
- Import/export (R6) — deferred to Phase 4 unless unblocked by CHG-02 colour changes
- Production packaging / installer
- Timestamped backup before destructive operations (prototype deferral confirmed)
- "Fill all rows / copy down" shortcut
- Report ID daily >999 fallback (very low likelihood)

### 2.3 Deferred to Phase 4

| Item | Reason |
|---|---|
| R6 — Excel-like column filtering with full date hierarchy | Phase 3 scope is closure only; R6 complexity warrants dedicated sprint |
| R9 — Alternate theme choices beyond the BUG-02 color fix | User preference selection deferred; fix readability now, theme chooser later |
| In-app Paidoff history view | Explicitly excluded by R3 |
| Timestamped backup before bulk approve / Paidoff | Deferred in run_1; remains deferred |

---

## 3. Phase 3 Closure Sprint Plan

### Sprint Goal
Resolve all four P1/P2 user-reported defects, implement the two accepted requirement changes (R1 default checkbox, R3 Paidoff interest report), verify launchers meet R10, and validate the import parser handles DD-MM-YYYY — producing a prototype that passes UAT hand-off criteria.

### Team Capacity
Single developer. Estimated available capacity: 5–7 dev-days for Phase 3 closure work items.

### Committed Items

| # | Item ID | Description | Owner | Estimate | Dependency |
|---|---|---|---|---|---|
| 1 | BUG-01 | Fix Interest Calculator filter reset — investigate QComboBox signal / slot wiring in `interest_calculator_tab.py`; ensure `_on_apply_filters` reads combo text after population | Backend Dev | 1 day | None |
| 2 | BUG-02 | Fix View Tab color palette — replace STATUS_COLORS light pastels in `view_tab.py` with high-contrast scheme (dark backgrounds, visible text); validate on Windows | Backend Dev | 0.5 day | None |
| 3 | BUG-03 | Fix Paidoff flow — trace QComboBox status change path vs context-menu path; ensure both reliably trigger PaidoffDialog and call `mark_paidoff()` | Backend Dev | 1 day | None |
| 4 | BUG-04 | Fix Windows date picker — set `QDateEdit` click events to open calendar popup on field click in all date entry locations (`entry_tab.py`, `paidoff_dialog.py`, `extend_dialog.py`) | Backend Dev | 0.5 day | None |
| 5 | CHG-01 | Default `No Due Date` checkbox to checked in `entry_tab.py` and ensure `_reset_form()` also resets to checked; update tests | Backend Dev | 0.25 day | None |
| 6 | CHG-02 | Paidoff generates interest report — extend `_action_paidoff()` in `view_tab.py` to: (a) compute `extension_period_days`, (b) call `calculate_daily()`, (c) create ReportRecord, (d) call `write_report()` + `write_report_records()`, (e) emit `report_generated` signal | Backend Dev | 2 days | BUG-03 must be fixed first |
| 7 | CHG-03 | Verify Python version check in both launchers — already implemented in run_1; confirm both `run_windows.bat` and `run_mac.sh` block on < 3.10 | Backend Dev | 0.25 day | None |
| 8 | DOC-01 | Verify CSV import parser handles DD-MM-YYYY format; update user guide sample data documentation | Backend Dev | 0.5 day | None |
| 9 | QA | Write/update unit tests for BUG-01 filter logic, CHG-01 default state, CHG-02 Paidoff report generation | Backend QA | 1 day | Items 1, 5, 6 |

**Total estimate: 7 dev-days** (within capacity window)

### Capacity Utilisation
7 of 5–7 estimated days available. At the upper bound of capacity — risk flag raised. Item 8 (DOC-01) can be parallelised or done last to reduce critical path.

### Explicitly NOT in this sprint
- R6 import/export enhancements
- R9 theme chooser
- Any Phase 1/2 re-architecture

---

## 4. Updated Risk Register (run_2 additions)

| ID | Risk | Likelihood | Impact | Status | Mitigation | Owner |
|---|---|---|---|---|---|---|
| RSK-12 | CHG-02 Paidoff interest report: `paidoff_date - due_date` produces negative extension_period if paidoff_date < due_date (early payoff) | Medium | Medium | Open | [REVIEW REQUIRED] — requirements do not define behaviour for early paidoff where paidoff_date < due_date. Zero or negative extension_period should be validated — see BC-01 below | Dev Lead |
| RSK-13 | BUG-03 root cause may be deeper than dialog wiring — status column in View Tab may not use QComboBox at all (uses inline text edit instead) | Medium | High | Open | Dev Lead to confirm whether QComboBox is wired for Status column; if not, this is a larger implementation gap | Backend Dev |
| RSK-14 | CHG-02 report generation adds a blocking dialog sequence during Paidoff — may confuse user if report generation fails after history.csv write completes | Medium | Medium | Open | Error handling must be explicit: Paidoff write completes atomically first, then report generation is best-effort with clear error message | Backend Dev |
| RSK-15 | DOC-01 — import parser may not support DD-MM-YYYY input if it only calls `date.fromisoformat()` which expects YYYY-MM-DD | Medium | Medium | Open | Must verify import path uses `datetime.strptime()` or equivalent for DD-MM-YYYY; storage always ISO 8601 (R8) | Backend Dev |
| RSK-16 | BUG-01 filter reset may be caused by `_populate_filters()` being called inside `_on_apply_filters()`, which clears and resets all combos to "All" before reading filter values — race condition or signal re-entrant call | High | High | Open | Dev Lead to confirm execution order in `_on_apply_filters()` — if `_load_loans()` calls `_populate_filters()` which resets combos, filters are read post-reset; fix by reading filter values before calling `_load_loans()` | Backend Dev |

---

## 5. Phase 4 Readiness Checklist

Before Phase 4 kick-off, the following must be complete or explicitly accepted:

| Gate | Description | Status |
|---|---|---|
| G-01 | All P1 defects (BUG-01, BUG-02, BUG-03) resolved and verified by QA | Pending |
| G-02 | P2 defect BUG-04 (Windows date picker) resolved | Pending |
| G-03 | CHG-01 (No Due Date default) implemented and unit-tested | Pending |
| G-04 | CHG-02 (Paidoff interest report) implemented, unit-tested, and early-paidoff edge case clarified — see BC-01 | Pending |
| G-05 | CHG-03 (Python version check) verified mandatory in both launchers | Pending — likely already done |
| G-06 | DOC-01 (DD-MM-YYYY import parser) verified or fixed, user guide updated | Pending |
| G-07 | All run_2 unit tests passing (`pytest` clean run) | Pending |
| G-08 | User (Windows end-user) has run the app and confirmed UT-R1 bugs are resolved | [REVIEW REQUIRED] — requires end-user confirmation |
| G-09 | Phase 4 scope agreed (R6 import/export, R9 themes, UAT) | [REVIEW REQUIRED] — PO to confirm Phase 4 scope |

---

## 6. Business Clarifications Required (BC)

| ID | Clarification | Impact of Deferring |
|---|---|---|
| BC-01 | When `paidoff_date < due_date` (early payoff), what should `extension_period_days` be? Options: (a) treat as 0 days — zero interest; (b) treat as absolute value — charge partial days; (c) block early paidoff and require paidoff_date >= due_date | CHG-02 Paidoff interest report will produce incorrect results or raise a ValueError without this decision |
| BC-02 | Should the Paidoff interest report generation be mandatory or optional? If report generation fails (e.g., data error), should the Paidoff write still complete? | Risk of broken Paidoff flow if report generation is blocking |
| BC-03 | Phase 4 scope confirmation: is R6 (import/export with full date-hierarchy filter) the sole focus, or does the user want R9 theme chooser bundled into Phase 4? | Phase 4 sprint plan cannot be committed without this decision |

---

## 7. Stakeholder Map (Unchanged from run_1)

| Name / Role | Interest | Engagement Level |
|---|---|---|
| End User (Windows) | Primary consumer — loan entry, status management, report approval, Phase 3 UAT validation | High — UAT sign-off required |
| Mac OS Tester / Bridge User | Cross-platform validation, git-based CSV sharing | Medium — periodic testing |
| Developer (Solo) | Implementation, testing, delivery | High — owns all phases |
| PM Agent | Phase governance, traceability, risk tracking | Wave 0 per run |

---

## 8. Success Metrics for run_2 Closure

| Metric | Target |
|---|---|
| All 4 UT-R1 defects resolved | BUG-01 through BUG-04 closed and confirmed by end-user |
| CHG-01 No Due Date defaults checked | Entry Tab form opens with No Due Date pre-checked; reset_form() preserves this default |
| CHG-02 Paidoff interest report generated | Marking a loan Paidoff creates a Daily-mode report in Pending Approval queue with correct extension_period_days |
| CHG-03 Python version check mandatory | Both launchers block on Python < 3.10 and print upgrade instruction |
| All unit tests passing | `pytest` exits with 0 failures on full test suite |
| Phase 4 kick-off gate met | All G-01 through G-07 gates pass; BC-01 through BC-03 resolved or accepted |

---

*End of Project Charter — Loan Manager — run_2 / Wave 0 — 2026-04-03*
