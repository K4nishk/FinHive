# Loan Manager — Project Charter
**Agent:** pm-agent (Wave 0)
**Run:** run_6
**Date:** 2026-04-04
**Phase:** Phase 3 Closure — Phase 4 MVP Readiness Assessment

---

## Business Objective

Deliver a single-user, desktop-based Loan Management application for Windows (with Mac tester support) that enables a private lending operator to record, track, extend, and settle personal and business loans. All data persists in CSV files. The product replaces manual spreadsheet management with a structured, auditable system featuring automated interest calculations, a Pending Approval workflow, and a reference ID system for record traceability.

**Problem Statement:** The user currently manages loan records in unstructured spreadsheets with no enforcement of calculation rules, no paidoff archival, and no interest calculation workflow. Manual errors and lack of audit trail are the primary pain points.

**Success Metrics:**
- All 15 sample records load and display correctly on first launch
- Interest calculations match the R5 authoritative formula for all 3 modes
- Paidoff workflow archives a record to history.csv correctly upon approval
- Filter logic returns correct records across all 5 filter dimensions
- Application runs on Windows and Mac without dependency errors

---

## Stakeholder Map

| Stakeholder | Role | Interest | Engagement |
|---|---|---|---|
| End User (Windows) | Primary consumer | Loan entry, View Tab, calculator, approvals | Daily user |
| Mac Tester | Bridge tester, git manager | Cross-platform validation, CSV sync | Periodic (per release) |
| Developer | Implementer | Code quality, architecture, test coverage | Sprint-level |

---

## Phase Scope Baseline

### Phase 1 — Complete
Core data model, Entry Tab (R1), View Tab (R2, R3), Status Engine, Reference ID Manager (R4).

### Phase 2 — Complete
Interest Calculator Tab (R5), Pending Approval Tab (R5), Report generation, Paidoff workflow v1, CSV export/import scaffold (R6).

### Phase 3 — Complete (run_5 implementation)
- R5 CalculationDialog (modal) — implemented
- R3 Paidoff workflow redesign (deferred archive, report-first) — implemented
- R1 Due Period field + auto-calc — implemented
- R2 DatePickerDelegate for View Tab date columns — implemented
- UTR1 case-insensitive filter fix — implemented
- R7 sample data seeding (15 records) — implemented
- R3 Status color palette (#025c33, #6b0307, #804001, #022a52) — implemented
- ClickableDateEdit.showCalendarWidget bug fix — implemented

### Phase 4 — MVP (Current Target)
**Prerequisite:** 4 user decisions from run_5 CLARIFICATIONS.md must be received:

| ID | Item | Blocking |
|---|---|---|
| TC-05 | Double Paidoff report guard | Data integrity — prevents duplicate archive |
| TC-08 | paidoff_date field placement | Integration test T-R3-03 blocked |
| TC-03 | due_period + due_date edit conflict | UX polish for R1 |
| BC-02 | Case normalization for stored names | Filter dropdown cosmetics |

**Phase 4 delivery items (after user decisions):**
- Implement TC-05 guard (disable/warn on duplicate Paidoff report)
- Implement TC-08 schema update if Option B chosen
- Implement TC-03 UX fix if Option A chosen
- Apply BC-02 normalization if Option B or C chosen
- Create remaining test files: test_entry_tab_logic.py, test_view_tab_paidoff.py, test_pending_approval.py, test_view_tab_colors.py
- Run full pytest suite: 0 failures required
- Manual smoke tests M-R1 through M-R7 by Mac tester
- Run run_mac.sh and run_windows.bat end-to-end on both OS

### Phase 5 — UAT
End-user acceptance on Windows machine. Mac tester validates cross-platform. Go/No-Go decision.

### Deferred to Post-MVP
- R9: Alternate theme choices
- R6: Full Excel-style hierarchical date filter (year → month → date)
- R5: "Copy down" shortcut for bulk parameter fill
- R3: Atomic Paidoff write with full crash safety (backup before destructive ops)
- R10: Batch write optimization (O(N^2) → O(N) startup writes)
- R6: Full Import/Export CSV/XLSX with preview dialog

---

## Risk Register

| ID | Risk | Prob | Impact | Status | Mitigation | Owner |
|---|---|---|---|---|---|---|
| R-001 | TC-05 not decided — duplicate Paidoff archive possible | H | H | Open | Disable Mark Paidoff guard (Option A recommended) | User decision |
| R-002 | TC-08 not decided — paidoff_date stored in wrong field | M | M | Open | Either option safe; Option B preferred for clean schema | User decision |
| R-003 | Windows-only PATH issues in run_windows.bat | L | M | Mitigated | Python version check + venv fallback logic present | Dev |
| R-004 | pytest failures from missing test files | M | H | Open | 4 test files need creation before UAT | Dev |
| R-005 | CSV corruption on partial Paidoff write | L | H | Partial | approval_recovery.tmp implemented; full atomic write deferred | SRE |
| R-006 | Cross-platform date format inconsistency | L | M | Mitigated | ISO 8601 enforced throughout; confirmed in run_5 | Dev |

---

## Traceability Matrix — Phase 4 Items

| Req ID | User Story | SA Component | DM Entity | Dev Task | QA Scenario |
|---|---|---|---|---|---|
| TC-05 | As a user, I cannot generate a second Paidoff report for a loan already pending approval | view_tab.py context menu | pending_report_records.csv | Add has_pending_paidoff_report() check | T-TC05-01: attempt second paidoff generates guard |
| TC-08 | paidoff_date stored in dedicated field or reused new_due_date | ReportRecord dataclass + CSV | pending_report_records.csv | Add paidoff_date column or document reuse | T-TC08-01: paidoff_date survives round-trip to CSV |
| TC-03 | due_period clears when user manually edits due_date | entry_tab.py | n/a (UI only) | Optionally clear _due_period on manual due_date edit | T-TC03-01: period cleared after manual due_date edit |
| BC-02 | Names stored consistently for clean dropdowns | csv_manager.py write_loan() | loans.csv | Optionally normalize case at write time | T-BC02-01: dropdown shows single entry per unique name |
| R4/R5 | Remaining test coverage | tests/ | n/a | test_entry_tab_logic, test_view_tab_paidoff, test_pending_approval, test_view_tab_colors | All new tests pass |

---

## Phase 4 Rough Sprint Plan

**Estimated duration:** 1-2 implementation sessions (3-5 working days)

| Sprint Item | Effort | Dependency | Owner |
|---|---|---|---|
| Receive 4 user decisions (TC-05, TC-08, TC-03, BC-02) | 0 dev | User | User |
| Implement TC-05 (Paidoff guard) | 0.5 day | TC-05 decision | Backend Dev |
| Implement TC-08 (paidoff_date field) | 0.5 day | TC-08 decision | Backend Dev |
| Implement TC-03 (due_period UX) | 0.25 day | TC-03 decision | Backend Dev |
| Implement BC-02 (normalization) | 0.25 day | BC-02 decision | Backend Dev |
| Write test_entry_tab_logic.py | 0.5 day | TC-03 decision | QA |
| Write test_view_tab_paidoff.py | 0.5 day | TC-05 decision | QA |
| Write test_pending_approval.py | 0.75 day | TC-08 decision | QA |
| pytest --tb=short passes 0 failures | Gate | All above | Dev/QA |
| Manual smoke tests M-R1..M-R7 (Mac) | 1 day | pytest gate | Mac Tester |
| Windows run_windows.bat end-to-end | 0.5 day | smoke tests | End User |
| Go/No-Go: Phase 5 UAT | Decision | All above | PO |

**Sprint Goal:** All MVP features implemented, all tests green, manual smoke tests passed, application runs end-to-end on both Windows and Mac.

---

## PM Recommendation for Phase 4 Kickoff

**Status:** READY to start Phase 4 — blocked only on 4 user decisions.

The codebase is in a strong state after run_5. Three new test files are passing. All Phase 3 features are implemented. The 4 open items are well-characterized with clear Option A/B choices. No architectural blockers remain.

**PM recommendation:** Provide the 4 user decisions (TC-05, TC-08, TC-03, BC-02) to unblock the Phase 4 implementation sprint. Estimated time from decisions to Phase 5 UAT readiness: 1-2 implementation sessions.
