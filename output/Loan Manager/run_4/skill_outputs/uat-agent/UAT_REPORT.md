# UAT Agent: User Acceptance Test Report — Loan Manager run_4
**Date:** 2026-04-04
**Run:** run_4 (Phase 3 Closure)
**Agent:** uat-agent (Wave 3, conditional — implementation complete)
**Source:** Backend Dev BACKEND_IMPLEMENTATION.md, QA Lead TEST_SCOPE.md, Backend QA BACKEND_QA_SPEC.md
**Implementation status at UAT entry:** All 6 items implemented. 197 baseline tests passing.

---

## UAT Entry Criteria Check

| Criterion | Status |
|---|---|
| All 6 source changes implemented | PASS — confirmed by Backend Dev |
| 197 existing tests passing before UAT | PASS — confirmed by Backend Dev |
| New test stubs written | PASS — Backend QA spec issued |
| QA Lead formal signoff | PASS — TEST_SCOPE.md written |

**UAT may proceed.**

---

## UAT Scope: 6 Acceptance Scenarios

UAT verifies end-to-end user-observable behaviour. These are manual acceptance tests performed on the running application, not pytest unit tests. Windows is the primary test environment (user's machine); Mac is secondary.

---

## UAT-01: BUG-UTR-1 — Interest Calculator Filter Dropdown Retains Selection

**Priority:** P1
**Pre-condition:** At least 2 loans with different Borrower Groups exist in the application.

**Steps:**
1. Open Interest Calculator Tab.
2. Observe that all filter combos show "All".
3. Select a Borrower Group from the Borrower Group combo (e.g., "Group A").
4. Click "Apply Filters".

**Expected Result:**
- The table shows only loans belonging to "Group A".
- The Borrower Group combo still shows "Group A" (not reverted to "All").
- Other filter combos still show "All".

**Pass Criteria:**
- Table row count matches only loans in the selected Borrower Group.
- Combo text == the selected value after the table updates.
- Repeated clicks of "Apply Filters" keep the filter in place.

**Fail Criteria:**
- Combo reverts to "All" immediately after clicking Apply.
- Table shows all loans regardless of filter.

**Cross-platform note:** Verify on both Windows and Mac.

**[REVIEW REQUIRED — UAT-01-EDGE]:** If a loan is deleted while a filter is active and that loan's group was the only representative of the selected filter value, the combo must fall back to "All" on next Apply. Confirm this edge case is acceptable — QA Lead documents it as expected fallback.

---

## UAT-02: BUG-UTR-2 — No Duplicate Reference IDs on Rapid Entry

**Priority:** P1
**Pre-condition:** Empty or existing loan data. Application running on Windows (primary test machine).

**Steps:**
1. Open the Entry Tab.
2. Enter 5 loans in rapid succession (borrower name "Test1" through "Test5", same month, any amount).
3. Click Submit for each without waiting.
4. Open View Tab. Click Refresh.
5. Check the Ref ID column.

**Expected Result:**
- Each loan has a unique, sequentially incremented reference_id in the current YYYY_MM bucket.
- Example: 2026_04_001, 2026_04_002, 2026_04_003, 2026_04_004, 2026_04_005.
- No two loans share the same reference_id.

**Pass Criteria:**
- All 5 Ref IDs are unique.
- Ref IDs are consecutive (no gaps unless existing loans already occupy lower order values).

**Fail Criteria:**
- Any two loans share the same Ref ID.
- Any Ref ID resets to _001 mid-sequence without all records for that month having been deleted.

**Additional check:** Force-close the application mid-entry (after submitting loan 3 but before loan 4). Restart. Verify the counter has not reset — loans_meta.csv is intact (atomic write fix verification).

---

## UAT-03: BUG-UTR-3 — View Tab Refresh Does Not Overwrite Unchanged Records

**Priority:** P1
**Pre-condition:** At least 3 loans exist. Application log (`data/logs/app.log`) is accessible.

**Steps:**
1. Open View Tab.
2. Note that all loan statuses are correct (Active/Overdue based on dates).
3. Click Refresh.
4. Open `data/logs/app.log`.

**Expected Result:**
- If no loans changed status since last load: log contains the line "Refresh: no status changes — skipping all writes".
- If any loans changed status: log contains "Refresh: N loan(s) status changed — persisted" and only those loans are rewritten.

**Pass Criteria:**
- "Loan updated" log entries are absent when no status change occurred.
- The debug log line is present after a no-change Refresh.
- View Tab display is correct after Refresh (no visual regressions).

**Fail Criteria:**
- Log shows "Loan updated" for every loan on every Refresh even when nothing changed.

---

## UAT-04: BUG-UTR-4 — Date Picker Opens on Single Click

**Priority:** P2
**Pre-condition:** Application running. Entry Tab open.

**Steps:**
1. Click anywhere on the Giving Date text area (not the dropdown arrow on the right edge).
2. Observe the calendar popup.
3. Repeat for Due Date field.
4. Repeat for the Paidoff Date field in the Mark Paidoff dialog (right-click a loan, select Mark Paidoff).

**Expected Result:**
- Calendar popup opens immediately on any click within the date field area.
- Behaviour is the same when clicking on the text portion vs the arrow portion.
- Calendar allows date selection normally.

**Pass Criteria:**
- Calendar opens on single click for all three date fields.
- Date selection from the calendar works correctly and updates the field.

**Fail Criteria:**
- Calendar only opens when the dropdown arrow is clicked (old behaviour).
- Calendar opens but closes immediately or has visual glitches.

**Cross-platform note:** Must be verified on both Windows and Mac — Qt calendar popup behaviour can differ.

---

## UAT-05: BC-301 — Paidoff Warning Label in Pending Approval Tab

**Priority:** LOW
**Pre-condition:** At least one Paidoff report exists in the Pending Approval queue (from a prior UAT-06 run, or created via the Interest Calculator tab using mode="Paidoff" if available).

**Steps:**
1. Open Pending Approval Tab.
2. Select a Monthly or Daily-mode report from the top table.
3. Observe the area between the report header and records table.
4. Select a Paidoff-mode report from the top table.
5. Observe the same area.

**Expected Result:**
- For Monthly/Daily reports: no warning label is visible between the header and records table.
- For Paidoff-mode reports: a styled warning label is visible with text "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied."
- Warning is displayed in a coloured banner (orange background, white text).
- When no report is selected (deselect or initial state): warning label is hidden.

**Pass Criteria:**
- Warning visible for mode="Paidoff" reports only.
- Warning hidden for all other report modes.
- Warning hidden when no report is selected.

---

## UAT-06: CHG-02-EXT — PaidoffDialog Collects Rate Fields and Generates Report

**Priority:** P2
**Pre-condition:** At least 1 Active or Overdue loan exists. Application running.

**Steps:**
1. Open View Tab. Right-click on an Active loan. Select "Mark Paidoff".
2. Observe the dialog.
3. Confirm the dialog shows: Paidoff Date field, Interest Rate spinner (default 12.0%), Commission Rate spinner (default 2.0%), TDS checkbox (default unchecked).
4. Change Interest Rate to 15.0%, Commission Rate to 3.0%, check TDS.
5. Set Paidoff Date to today.
6. Click OK.
7. Open Pending Approval Tab.
8. Select the new Paidoff-mode report.
9. Inspect the records table row for the loan.

**Expected Result:**
- Dialog collects all 4 values correctly.
- The loan disappears from View Tab (archived to history).
- A new Paidoff-mode report appears in Pending Approval Tab.
- The report record row shows: interest_rate=15.0, commission_rate=3.0, tds_flag=true, interest_amount and tds_amount calculated correctly.
- The Paidoff warning label (UAT-05) is visible for this report.

**Pass Criteria:**
- All 4 dialog fields present with correct defaults.
- Report appears in Pending queue with mode="Paidoff".
- Interest calculation values match the Daily formula: (amount * rate * extension_period) / (365 * 100).
- TDS amount = 10% of interest amount when TDS is checked.

**[REVIEW REQUIRED — TC-401]:** For a loan with no due_date: the dialog should still complete without error. extension_period = 0, interest_amount = 0. UAT must verify this edge case does not crash the application and that the resulting report record shows zero amounts.

**Fail Criteria:**
- Dialog shows only a date field (old behaviour — CHG-02-EXT not implemented).
- No report appears in Pending Approval after Paidoff.
- Application crashes or shows unhandled exception during Paidoff.
- Values in report record do not match entered values.

---

## UAT Sign-off Matrix

| UAT ID | Scenario | Priority | Windows | Mac | Status |
|---|---|---|---|---|---|
| UAT-01 | Filter dropdown retains selection | P1 | Pending | Pending | Not yet run |
| UAT-02 | No duplicate Ref IDs on rapid entry | P1 | Pending | N/A | Not yet run |
| UAT-03 | Refresh does not overwrite unchanged | P1 | Pending | Pending | Not yet run |
| UAT-04 | Date picker opens on single click | P2 | Pending | Pending | Not yet run |
| UAT-05 | Paidoff warning label visible | LOW | Pending | Pending | Not yet run |
| UAT-06 | PaidoffDialog collects rate fields | P2 | Pending | Pending | Not yet run |

**UAT Status:** Scenarios written. Pending user execution on target hardware.

**UAT Blocker:** TC-401 edge case (no-due-date Paidoff) — PO has defaulted to extension_period=0, interest=0, but user confirmation is requested to formally close this as a known documented behaviour rather than a defect.

---

## UAT Observations and Defect Log

No UAT runs have been executed yet (implementation just completed at run_4). This section will be populated when the user runs the above scenarios on the Windows machine.

**Instructions for user:**
1. Run the application: `cd "/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager" && python3 main.py` (or the Windows equivalent).
2. Execute UAT-01 through UAT-06 in order.
3. For each scenario: record Pass/Fail and any observations.
4. Report any Fail results as defects for run_5 scope.

---

## Phase 4 Readiness Check (UAT Perspective)

UAT confirms the following Phase 3 items are implementation-complete and ready for user acceptance:
- BUG-UTR-1, BUG-UTR-2, BUG-UTR-3, BUG-UTR-4: implemented
- BC-301: implemented
- CHG-02-EXT: implemented

**Phase 4 entry gate (UAT perspective):**
- All 6 UAT scenarios must pass on Windows before Phase 4 begins
- BC-03 user decision (Phase 4 scope selection) is the only remaining external dependency
- SA-401 (history.csv gap in `_active_year_months()`) should be reviewed and decided before Phase 4 reference ID work

**[REVIEW REQUIRED — BC-03]:** Phase 4 scope has not been decided. User must select one of options A, B, C, D, or E from the PO decisions document. UAT cannot plan Phase 4 acceptance scenarios until this is resolved.
