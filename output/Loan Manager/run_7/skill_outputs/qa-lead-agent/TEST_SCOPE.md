# Loan Manager — Test Scope
**Agent:** qa-lead-agent (Wave 2)
**Run:** run_7
**Date:** 2026-04-05
**Phase:** Phase 3 Closure / Phase 4 MVP

---

## Test State — Run 7

**Current test run result:** 237 tests passed, 0 failures (confirmed by pytest run at run_7 start)

**Test files present:**
- tests/test_calculation_dialog_logic.py
- tests/test_csv_manager.py
- tests/test_filter_logic.py
- tests/test_interest_calculator.py
- tests/test_ref_id_manager.py
- tests/test_report_manager.py
- tests/test_seed.py
- tests/test_status_engine.py

---

## QA Coverage Gaps — Phase 4

### GAP-01: test_view_tab_colors.py (R3 STATUS_COLORS)
**Status:** NOT YET CREATED
**Blocker:** None (PD-11 confirmed safe — no QApplication needed for dict import)
**Coverage target:** 5 assertions on STATUS_COLORS dict values
**Owner:** Backend QA

### GAP-02: test_entry_tab_logic.py (R1 due_period calculation)
**Status:** NOT YET CREATED
**Blocker:** None (pure calculation logic, no QApplication)
**Coverage target:** 5+ assertions on `giving_date + relativedelta(months=N)` calculation
**Owner:** Backend QA

### GAP-03: test_view_tab_paidoff.py (R3 TC-05 has_pending_paidoff_report)
**Status:** NOT YET CREATED
**Blocker:** TASK-1 implementation must complete first
**Coverage target:**
- Test has_pending_paidoff_report() returns False when no pending reports
- Test returns False when pending reports exist but none are Paidoff-mode
- Test returns True when Pending Paidoff report contains the reference_id
- Test returns False when Paidoff report is Approved/Declined (not Pending)
- Test returns False when Paidoff report references a different loan
**Owner:** Backend QA

### GAP-04: test_pending_approval.py — batch_extend portion
**Status:** NOT YET CREATED
**Blocker:** None
**Coverage target:**
- Test batch_extend_loans() updates multiple loans in single CSV pass
- Test partial extension (some ref_ids not found — no error, skip missing)
- Test new_giving_date and new_due_date updated correctly
**Owner:** Backend QA

### GAP-05: test_pending_approval.py — paidoff_date portion
**Status:** NOT YET CREATED
**Blocker:** TC-08 user decision (Option B only)
**Coverage target (Option B):**
- Test paidoff_date round-trips correctly through to_csv_row() / from_csv_row()
- Test new_due_date is empty when paidoff_date is set (Paidoff mode)
- Test backward compatibility: records without paidoff_date column parse as None
**Owner:** Backend QA

### GAP-06: BC-02 normalization test
**Status:** NOT YET CREATED
**Blocker:** BC-02 user decision
**Coverage target (Option B):**
- Test write_loan() normalizes "BG1" → "bg1" at write time
- Test depositor_name None stays None (no lowercase on None)
**Owner:** Backend QA

---

## QA Gate: Phase 4 Exit Criteria

| Gate | Condition | Status |
|---|---|---|
| Automated tests | pytest: 0 failures, 0 errors | PASS (237 tests, pre-Phase 4) |
| TC-05 guard test | test_view_tab_paidoff.py: 5 tests pass | PENDING |
| Color palette test | test_view_tab_colors.py: 5 tests pass | PENDING |
| Entry logic test | test_entry_tab_logic.py: 5+ tests pass | PENDING |
| batch_extend test | test_pending_approval.py: 3+ tests pass | PENDING |
| TC-08 test (if B) | paidoff_date round-trip: 3 tests pass | PENDING (user decision) |
| BC-02 test (if B) | normalization: 2 tests pass | PENDING (user decision) |
| Manual smoke M-01 | Entry Tab: all fields save correctly | PENDING (Mac tester) |
| Manual smoke M-02 | View Tab: sorting, inline edit, date picker | PENDING (Mac tester) |
| Manual smoke M-03 | Status engine: Active/Overdue/Pending/Paidoff correct | PENDING (Mac tester) |
| Manual smoke M-04 | Interest Calculator: Monthly/Daily/Both modes | PENDING (Mac tester) |
| Manual smoke M-05 | Pending Approval: approve/decline, inline edit | PENDING (Mac tester) |
| Manual smoke M-TC05 | Mark Paidoff disabled when report pending | PENDING (after TASK-1) |
| Windows UAT | run_windows.bat completes without errors | PENDING (Phase 5) |

---

## Manual Smoke Test Scenarios

### M-R1-01: New Loan Entry
1. Launch app → Entry Tab visible with empty form
2. Enter Borrower Name: "b1", Group: "bg1", Amount: 10000
3. Set Giving Date via calendar picker
4. Enter Due Period: 3 → verify Due Date auto-calculated = Giving Date + 3 months
5. Enter Depositor Name: "d1"
6. Click "Submit Loan Entry"
7. Verify status bar: "Loan saved successfully. Reference ID: 2026_04_001" (or next seq)
8. Switch to View Tab → verify new row appears

### M-R2-01: View Tab Sort + Inline Edit
1. Click "Borrower Name" column header → verify alphabetical sort
2. Click "Amount" column header → verify numerical sort
3. Click "Giving Date" column header → verify date sort
4. Double-click amount cell → edit to 12000 → press Enter → verify saved
5. Double-click Due Date cell → verify date picker opens → pick new date → verify saved

### M-R3-01: Status Color Palette
1. Load sample data → verify Active loans show dark green (#025c33) rows
2. Verify Overdue loans show dark red (#6b0307) rows
3. Verify Pending loans show dark amber (#804001) rows
4. All status rows should have bold white text

### M-R3-02: Mark Paidoff Workflow
1. Right-click Active loan with due_date → verify "Mark Paidoff" enabled
2. Right-click loan with no due_date → verify "Mark Paidoff" disabled
3. Click "Mark Paidoff" on valid loan → PaidoffDialog opens
4. Enter paidoff_date, interest_rate=12, commission_rate=2, TDS off
5. Click OK → verify success message with report_id
6. Switch to Pending Approval Tab → verify Paidoff report appears
7. Right-click same loan again → verify "Mark Paidoff" is now DISABLED (TC-05)
8. Approve the report → verify loan disappears from View Tab

### M-R5-01: Interest Calculator Workflow
1. Switch to Interest Calculator Tab
2. Select Mode: Monthly
3. Set Borrower Group filter: "bg3" → Apply Filters → verify 2 records shown
4. Set interest_rate=12, commission_rate=2, extension_period=1
5. Click Calculate → CalculationDialog opens
6. Verify Interest = (Amount * 12 * 1) / (12 * 100) for each record
7. Click Generate Report → verify success message
8. Switch to Pending Approval Tab → verify report appears
9. Inline edit an interest_rate in the detail table → verify amounts auto-recalculate
10. Approve → verify loans updated with new giving/due dates in View Tab

### M-R5-02: Filter Edge Cases
1. Set Depositor Group filter: "dg3" → Apply → verify 4 records (b6, b7, b8, b9)
2. Set Depositor Group filter: "Unknown" → Apply → verify loans b14, b15 appear
3. Set ByMonth filter: July → Apply → verify loans with due_date in July 2026

### M-R6-01: Date Column Filter (View Tab)
1. Click column header filter for "Giving Date"
2. Verify year options appear (2026)
3. Select 2026 → verify month options (January, February, March)
4. Select March → verify only March loans shown

**Note:** R6 full hierarchical date filter is deferred (PD-09). Current behavior is QSortFilterProxyModel sort. Date column click sorts, does not open hierarchical filter.

---

## QA Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| TC-05 guard adds CSV read per context menu open | LOW | Fast path: returns immediately if no Paidoff reports in queue |
| TC-08 Option B breaks backward compat with existing pending_report_records.csv | LOW | from_csv_row uses row.get() with default "" — safe for missing column |
| Windows line endings in CSV files | LOW | csv module handles CRLF/LF, encoding="utf-8" |
| Sample data dates now in past (2026 Q1) → all "Overdue" on load | EXPECTED | Status recompute on launch will mark most sample records as Overdue. This is correct behavior. |
