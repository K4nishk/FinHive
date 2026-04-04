# Loan Manager — Test Scope
**Agent:** qa-lead-agent (Wave 2)
**Run:** run_6
**Date:** 2026-04-04
**Phase:** Phase 4 QA Planning

---

## Test Coverage Status

### Automated Tests — Currently Passing

| Test File | Tests | Requirement | Status |
|---|---|---|---|
| tests/test_csv_manager.py | CSV read/write operations | R1, R2, R3, R4 | PASSING |
| tests/test_interest_calculator.py | Monthly/Daily/Both calculations | R5 | PASSING |
| tests/test_ref_id_manager.py | Ref ID generation, increment, overflow | R4 | PASSING |
| tests/test_report_manager.py | Report generation and persistence | R5 | PASSING |
| tests/test_status_engine.py | Status computation for all states | R3 | PASSING |
| tests/test_filter_logic.py | Case-insensitive filter (UTR1) | UTR1 | PASSING |
| tests/test_seed.py | Sample data seeding guard | R7 | PASSING |
| tests/test_calculation_dialog_logic.py | CHQ_Amt formula, calculator | R5 | PASSING |

### Automated Tests — To Be Created (Phase 4)

| Test File | Coverage | Requirement | Blocked By |
|---|---|---|---|
| tests/test_view_tab_paidoff.py | has_pending_paidoff_report(), mark_paidoff() | R3, TC-05 | TC-05 user decision |
| tests/test_pending_approval.py | Paidoff date round-trip, batch_extend | R5, TC-08 | TC-08 user decision |
| tests/test_entry_tab_logic.py | due_period auto-calc, TC-03 Option A | R1, TC-03 | TC-03 user decision (partial) |
| tests/test_view_tab_colors.py | STATUS_COLORS constants | R3 | None — can create now |

### Manual Smoke Tests (Phase 4 / Phase 5)

All PySide6 UI interaction tests are manual. Tests requiring QApplication are excluded from the automated suite per QA policy (no headless PySide6 testing without significant test infrastructure overhead).

---

## Quality Gate — Phase 4 Exit Criteria

All of the following must be true before Phase 5 (UAT) begins:

| Gate | Criterion | Status |
|---|---|---|
| QG-01 | `pytest --tb=short` from `src/Loan Manager/` returns 0 failures | Open |
| QG-02 | 4 new test files created (test_view_tab_paidoff, test_pending_approval, test_entry_tab_logic, test_view_tab_colors) | Open |
| QG-03 | TC-05 user decision received and implemented | Open |
| QG-04 | TC-08 user decision received and implemented | Open |
| QG-05 | M-R1-01 through M-R8-01 manual smoke tests passed on Mac | Open |
| QG-06 | run_windows.bat end-to-end test passed on Windows | Open |
| QG-07 | 15 sample records load correctly on first launch (Windows) | Open |
| QG-08 | No regressions: existing 8 test files still passing after Phase 4 changes | Open |

---

## Test IDs — Phase 4 New Tests

### tests/test_view_tab_paidoff.py

| ID | Test | Requirement | Blocked |
|---|---|---|---|
| T-TC05-01 | has_pending_paidoff_report() returns True when Paidoff Pending report exists | TC-05 | No |
| T-TC05-02 | has_pending_paidoff_report() returns False when no Paidoff report | TC-05 | No |
| T-TC05-03 | has_pending_paidoff_report() returns False when Paidoff report is Approved | TC-05 | No |
| T-TC05-04 | has_pending_paidoff_report() returns False when Paidoff report is Declined | TC-05 | No |
| T-R3-01 | mark_paidoff() removes loan from loans.csv | R3 | No |
| T-R3-02 | mark_paidoff() adds loan to history.csv with paidoff_date | R3 | No |
| T-R3-03 | mark_paidoff() raises ValueError for unknown ref_id | R3 | No |
| T-R3-04 | Loan not in View Tab after Paidoff approval (integration check via CSV) | R3 | No |

### tests/test_pending_approval.py

| ID | Test | Requirement | Blocked |
|---|---|---|---|
| T-TC08-01 | ReportRecord(paidoff_date=date) survives CSV write+read | TC-08 | Option B only |
| T-TC08-02 | ReportRecord with paidoff_date=None survives CSV round-trip | TC-08 | Option B only |
| T-R5-01 | batch_extend_loans() updates giving_date and due_date in loans.csv | R5 | No |
| T-R5-02 | batch_extend_loans() skips non-existent ref_id gracefully | R5 | No |
| T-R5-03 | get_active_reference_ids_in_queue() returns only Pending report ref_ids | R5 | No |
| T-R5-04 | update_report_status() changes status and updates timestamp | R5 | No |

### tests/test_entry_tab_logic.py

| ID | Test | Requirement | Blocked |
|---|---|---|---|
| T-R1-01 | due_date = giving_date + 3 months (3-month period) | R1 | No (pure calculation) |
| T-R1-02 | due_date = giving_date + 0 months = giving_date when period=0 | R1 | No |
| T-R1-03 | due_date recalculates when giving_date changes and period > 0 | R1 | No |
| T-TC03-01 | due_period cleared to 0 when due_date manually edited (Option A only) | TC-03 | TC-03 Option A |

### tests/test_view_tab_colors.py

| ID | Test | Requirement | Blocked |
|---|---|---|---|
| T-R3-COLOR-01 | STATUS_COLORS['Active'] == ('#025c33', '#ffffff') | R3 | None |
| T-R3-COLOR-02 | STATUS_COLORS['Overdue'] == ('#6b0307', '#ffffff') | R3 | None |
| T-R3-COLOR-03 | STATUS_COLORS['Pending'] == ('#804001', '#ffffff') | R3 | None |
| T-R3-COLOR-04 | STATUS_COLORS['Paidoff'] == ('#022a52', '#ffffff') | R3 | None |
| T-R3-COLOR-05 | Unknown status falls back to ('#ffffff', '#000000') | R3 | None |

---

## Manual Smoke Tests — Full List

| ID | Scenario | Requirement | Priority |
|---|---|---|---|
| M-R1-01 | New loan with due_period=3 → due_date = giving_date + 3 months | R1 | P1 |
| M-R1-02 | Tab into Giving Date → calendar opens | R1 | P1 |
| M-R1-03 | Click Giving Date → calendar opens | R1 | P1 |
| M-R1-04 | No Due Date checkbox → due_date field disabled | R1 | P1 |
| M-R1-05 | Submit valid loan → status bar shows ref_id | R1 | P1 |
| M-R1-06 | Submit without Borrower Name → validation error | R1 | P2 |
| M-R2-01 | View Tab loads all loans on refresh | R2 | P1 |
| M-R2-02 | Click column header → sorts ascending, click again → descending | R2 | P1 |
| M-R2-03 | Inline edit Borrower Name → persisted in loans.csv | R2 | P1 |
| M-R2-04 | Inline edit Due Date → calendar opens, ISO date saved | R2 | P1 |
| M-R2-05 | Unknown shown for missing depositor name/group | R2 | P2 |
| M-R3-01 | Right-click Active loan → Mark Paidoff → dialog → report in Pending Approval | R3 | P1 |
| M-R3-02 | Right-click Overdue loan → Mark Paidoff → report generated | R3 | P1 |
| M-R3-03 | Right-click loan with no due_date → Mark Paidoff disabled | R3 | P1 |
| M-R3-04 | Approve Paidoff report → loan disappears from View Tab | R3 | P1 |
| M-R3-05 | history.csv contains paidoff loan after approval | R3 | P1 |
| M-R3-06 | Active loan color = dark green #025c33 with bold white text | R3 | P2 |
| M-R3-07 | Overdue loan color = dark red #6b0307 with bold white text | R3 | P2 |
| M-R3-08 | Pending loan color = dark amber #804001 with bold white text | R3 | P2 |
| M-R4-01 | New entry in March 2026 → ref_id = 2026_03_NNN (correct order) | R4 | P1 |
| M-R4-02 | Delete loan → next entry gets next sequential number | R4 | P2 |
| M-R4-03 | Extend loan with months → giving_date = old due_date, new due_date correct | R4 | P1 |
| M-R4-04 | Extend loan with days → new due_date = old due_date + N days | R4 | P2 |
| M-R5-01 | Borrower Group filter "bg1" → only bg1 loans shown | R5/UTR1 | P1 |
| M-R5-02 | BG1 (uppercase) filter → same result as bg1 | R5/UTR1 | P1 |
| M-R5-03 | ByMonth = April → only April due_date loans shown | R5 | P1 |
| M-R5-04 | Monthly mode Calculate → CalculationDialog opens with all filtered rows | R5 | P1 |
| M-R5-05 | Edit interest_rate in dialog cell → Interest/TDS/CHQ_Amt update on-the-fly | R5 | P1 |
| M-R5-06 | Generate Report from dialog → appears in Pending Approval with Pending status | R5 | P1 |
| M-R5-07 | Approve report → loan due_date updated in View Tab | R5 | P1 |
| M-R5-08 | Decline report → loans unchanged, report marked Declined | R5 | P1 |
| M-R5-09 | CHQ_Amt = Interest - TDS when TDS flag on | R5 | P1 |
| M-R5-10 | CHQ_Amt = 0.9 * Interest when TDS flag off | R5 | P1 |
| M-R7-01 | Fresh install: first launch → 15 sample records | R7 | P1 |
| M-R7-02 | Second launch → no re-seeding | R7 | P1 |
| M-R8-01 | run_mac.sh: executes, venv created, deps installed, app launches | R8 | P1 |
| M-TC05 | Mark Paidoff on loan already in Paidoff queue → disabled or warning | TC-05 | P1 |

---

## QA Recommendations

1. **test_view_tab_colors.py can be created immediately** — it has no blocked dependencies. Recommend creating it now for immediate confidence.
2. **test_pending_approval.py T-R5-01 through T-R5-04** can be created now regardless of TC-08 decision — batch_extend_loans() and status update tests don't require the paidoff_date field.
3. **BC-02 regression check**: If BC-02 Option B is chosen, `test_csv_manager.py` may need updates if it asserts exact-case borrower_name values. Review test assertions before implementing BC-02.
4. The existing 8 passing test files form a solid regression baseline. They must all continue passing after Phase 4 changes.
