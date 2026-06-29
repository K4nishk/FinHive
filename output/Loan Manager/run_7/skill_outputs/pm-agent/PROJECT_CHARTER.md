# Loan Manager — Project Charter
**Agent:** pm-agent (Wave 0)
**Run:** run_7
**Date:** 2026-04-05
**Phase:** Phase 3 Closure / Phase 4 MVP Implementation

---

## PM: Project Charter — Loan Manager

**Business Objective:** Deliver a single-user PySide6 desktop application that enables personal and business loan lifecycle management including entry, tracking, interest calculation, and paidoff archival, with all core features production-ready for the primary end-user's Windows machine.

**Problem Statement:** The end-user currently manages loans manually with no structured tracking for due dates, interest calculations, or status transitions. This creates reconciliation errors, missed due dates, and manual calculation burden.

**Success Metrics:**
- All 237 tests pass with 0 failures
- TC-05 Paidoff guard implemented and tested
- All 4 remaining user decisions resolved (TC-08, TC-03, BC-02, SRE-01)
- Application runs on Windows via run_windows.bat without dependency errors
- Application runs on macOS via run_mac.sh without dependency errors
- Mac tester validates all smoke test scenarios M-R1-01 through M-TC05

**Stakeholders:**
| Name / Role | Interest | Engagement Level |
|---|---|---|
| End User (Windows) | Loan tracking, reports, ease of use | Decide |
| Mac Tester | Cross-platform validation, git CSV management | Consult |
| Dev Lead + Agents | Implementation quality, test coverage | Execute |

**Constraints:**
- Budget: None (personal project)
- Timeline: MVP user acceptance pending 4 user decisions (TC-08, TC-03, BC-02, SRE-01)
- Scope boundary: No database, no multi-user, no mobile, no server — desktop CSV only
- Post-MVP deferred: R6 full import/export, R6 hierarchical date filter, R9 alternate themes, R10 batch write, R3 atomic backup

**Assumptions and Risks at Kick-off:**
- Assumption: User confirms answers to TC-08, TC-03, BC-02, SRE-01 at Phase 4 kickoff → Risk: Phase 4 blocked until decisions received
- Assumption: Python 3.10+ available on Windows end-user machine → Risk: run_windows.bat version check handles this
- Assumption: No data migration needed between runs → Risk: paidoff_date schema (TC-08) only affects new records

**Agreed Next Step:** User provides 4 decisions → Dev Lead implements TC-05 (PD-10, can start immediately) + TC-08/TC-03/BC-02/SRE-01 per user answers → pytest gate → Mac smoke tests → Windows UAT

---

## PM: Scope Baseline — Phase 4 / Phase 3 Closure

**In scope (agreed):**
- TC-05 Option A: `has_pending_paidoff_report()` in data/report_manager.py + disable "Mark Paidoff" in view_tab.py (PD-10 BINDING)
- TC-08: Implement per user decision (Option A field reuse or Option B dedicated `paidoff_date` column)
- TC-03: Implement per user decision (Option A clear period or Option B no change)
- BC-02: Implement per user decision (Option A no change, Option B lowercase, Option C title case)
- SRE-01: Startup recovery warning — implement per user decision
- Missing test files: test_view_tab_colors.py, test_entry_tab_logic.py, test_view_tab_paidoff.py, test_pending_approval.py
- pytest gate: all tests must pass before declaring Phase 4 complete

**Out of scope (explicit):**
- R6: Import/Export CSV/XLSX (deferred PD-09)
- R6: Year→month→date hierarchical column filter (deferred PD-09)
- R9: Alternate themes (deferred PD-09)
- R10: Batch write optimization (deferred PD-09)
- R3: Timestamped backup on destructive ops (deferred PD-09)
- Database, multi-user, API layer

**Deferred (post-MVP):**
- All PD-09 items above
- CHQ_Amt column in Pending Approval (currently in CalculationDialog only)
- "Fill all rows" shortcut in calculator (noted in R5 as low priority)

**Open scope questions (needs PO decision):**
- TC-08: Option A vs Option B for paidoff_date field → blocks 2 test files
- TC-03: Option A vs Option B for due_period clear behavior → zero blocking impact
- BC-02: Option A/B/C for case normalization → zero blocking impact
- SRE-01: Include in Phase 4 or defer → low effort, low blocking impact

**Traceability:**
| Req ID | BSA Story | SA Component | DM Entity | Dev Task | QA Scenario |
|---|---|---|---|---|---|
| R3/TC-05 | Mark Paidoff guard | view_tab.py context menu + report_manager.py | PendingReport query | has_pending_paidoff_report() + context menu disable | test_view_tab_paidoff.py |
| R5/TC-08 | paidoff_date field | models/report.py, data/report_manager.py | ReportRecord schema | dedicated column or field reuse | test_pending_approval.py |
| R1/TC-03 | due_period clear behavior | ui/entry_tab.py | Loan (no schema change) | _on_due_date_changed guard | test_entry_tab_logic.py |
| R1,R2/BC-02 | Lowercase normalization | data/csv_manager.py write_loan | Loan names | normalize at write_loan() | test_csv_manager.py |
| R10/SRE-01 | Startup recovery warning | ui/main_window.py | None | _check_recovery_file() extend | test_main_window_startup.py |

---

## PM: Phase Roadmap

| Phase | Scope | Est. Effort | Status |
|---|---|---|---|
| Phase 1 | Entry Tab, View Tab, Status Engine, Ref ID | ~3 days | COMPLETE |
| Phase 2 | Interest Calculator, Pending Approval, Report Gen | ~3 days | COMPLETE |
| Phase 3 | R5 Dialog, Paidoff Redesign, Due Period, Date Picker, UTR1 Fix | ~2 days | COMPLETE |
| Phase 4 (current) | TC-05 guard, user decisions, remaining tests, pytest gate | ~0.5 day core + user decisions | IN PROGRESS |
| Phase 5 (MVP UAT) | Mac smoke tests, Windows E2E, Go/No-Go | ~1 day | NOT STARTED |

**Phase 4 capacity estimate:**
- TC-05 Option A implementation: 1 hour (no user decision required)
- TC-08 Option B (if chosen): 2 hours
- TC-03 Option A (if chosen): 30 min
- BC-02 Option B (if chosen): 30 min
- SRE-01 (if in scope): 30 min
- Test files (4 new): 2 hours
- Pytest gate + review: 30 min
- **Total Phase 4: ~7 hours** (dependent on user decisions)

**Risk Register:**
| ID | Risk | Prob | Impact | Mitigation |
|---|---|---|---|---|
| R-001 | User delays decisions on TC-08/TC-03/BC-02 | M | L | TC-05 can proceed immediately; others are low-effort and not blocking |
| R-002 | Windows run_windows.bat fails on end-user machine | L | H | Python version check included; requirements.txt tested |
| R-003 | TC-05 has_pending_paidoff_report() introduces CSV read overhead at context menu open | L | L | Single lightweight CSV scan; acceptable for 1500 max records |

---

## PM: Architecture Delivery Review — Phase 4

**Timeline implications:**
- TC-05 (PD-10 binding): Unblocked — no user decision needed. Can be implemented and tested immediately.
- TC-08: 2-hour additive schema change. Blocks test_pending_approval.py paidoff_date tests.
- BC-02: 30-minute normalization. No blockers.
- SRE-01: 30-minute startup check extension. No blockers.

**Team capability gaps:** None — all implementation is in Python/PySide6, team has established patterns.

**Dependencies introduced:**
- TC-05 requires `has_pending_paidoff_report()` to be added to data/report_manager.py before view_tab.py can reference it. Sequential dependency within Phase 4.

**Risk introduced:** Minimal. All changes are additive (no destructive mutations to existing CSV schemas under Option A for TC-08).

**PM recommendation:** Proceed with Phase 4. TC-05 starts immediately. User decisions for TC-08/TC-03/BC-02/SRE-01 collected at Phase 4 kickoff.
