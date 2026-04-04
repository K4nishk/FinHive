# BSA Agent: Business Requirements — Loan Manager run_4
**Date:** 2026-04-04
**Run:** run_4 (Phase 3 Closure)
**Agent:** bsa-agent (Wave 1)
**Source authority:** /Users/ishq_kan/Documents/Github/FinHive/input/REQUIREMENTS.md
**PO Decisions authority:** /Users/ishq_kan/Documents/Github/FinHive/output/Loan Manager/run_4/skill_outputs/po-agent/PO_Decisions.md

---

## Scope Summary — run_4

Six items are in scope for Phase 3 closure. All are confirmed against source code.

| ID | Item | Priority | Source |
|---|---|---|---|
| BUG-UTR-1 | Interest Calculator filter dropdown resets on Apply | P1 | User-Testing Req 1 |
| BUG-UTR-2 | Duplicate reference_ids on Windows rapid entry | P1 | User-Testing Req 1 + R4 |
| BUG-UTR-3 | View Tab Refresh overwrites all records unconditionally | P1 | User-Testing Req 1 |
| BUG-UTR-4 | Date picker opens only on arrow click, not field click | P2 | User-Testing Req 1 + R1 |
| BC-301 | Paidoff warning label in Pending Approval Tab | LOW | R3 |
| CHG-02-EXT | PaidoffDialog missing interest_rate, commission_rate, tds_flag | P2 | R3 + PD-R4-07 |

---

## BSA Requirements Breakdown: BUG-UTR-1 — Interest Calculator Filter Dropdown Reset

**Functional Requirements:**
- FR-UTR1-01: When the user selects a filter value from any of the four named filter combos (Borrower Group, Borrower Name, Depositor Name, Depositor Group) and clicks "Apply Filters", the system shall display only the loan records that match the selected filter(s).
- FR-UTR1-02: After "Apply Filters" is clicked, each named filter combo shall retain the value the user selected — it shall not revert to "All".
- FR-UTR1-03: The system shall still reset all filter combos to "All" when the Interest Calculator Tab is first opened or when new loan data is loaded on initial tab activation.
- FR-UTR1-04: Combining multiple filters (e.g., Borrower Group + By Month) shall work correctly — only records matching all active filters are shown.
- FR-UTR1-05: The "By Month" filter shall retain its selection independently of the named filters.

**Non-Functional Requirements:**
- NFR-UTR1-01: Fix must apply identically on Windows and Mac (no OS-specific code paths).
- NFR-UTR1-02: The fix must not introduce a regression where filter combos fail to refresh when new loans are added.

**Root Cause (confirmed from source):**
`_on_apply_filters()` in `ui/interest_calculator_tab.py` calls `self._load_loans()` which calls `self._populate_filters()` which calls `combo.clear()` on all filter combos. Filter values are then read by `_get_filtered_loans()` AFTER the clear — so every apply reads "All" from all combos.

**Fix pattern:** Capture `bg_filter`, `bn_filter`, `dn_filter`, `dg_filter`, `month_filter` values from the combo widgets BEFORE calling `_load_loans()`. After load, re-apply captured values to the combos.

**User Stories:**

### Story UTR1-1: Filter Retains Selection After Apply
As a loan manager user,
I want my filter dropdown selection to be retained after I click Apply Filters,
So that I can see the filtered results without the filter resetting to "All".

**Acceptance Criteria:**
- Given I open the Interest Calculator Tab, When I select "bg1" from Borrower Group and click Apply Filters, Then the Borrower Group combo still shows "bg1" and the table shows only loans in group "bg1".
- Given I select "d1" from Depositor Name and click Apply Filters, Then the Depositor Name combo still shows "d1" after the table updates.
- Given I select multiple filters (Borrower Group + By Month) and click Apply Filters, Then all selected filter values are retained and the table shows only records matching all active filters.
- Given no filter is selected, When I click Apply Filters, Then all combos show "All" and the table shows records with no due_date per R5.

**Dependencies:**
- Dev Lead: Fix `_on_apply_filters()` in `ui/interest_calculator_tab.py`

---

## BSA Requirements Breakdown: BUG-UTR-2 — Duplicate Reference IDs on Windows (DEEP DIVE)

**Functional Requirements:**
- FR-UTR2-01: Each new loan entry in the same YYYY_MM bucket shall receive a unique, sequentially incremented reference_id (e.g., 2026_04_001, 2026_04_002 — no duplicates).
- FR-UTR2-02: The counter used to determine the next order value shall be derived from the existing reference_id values in storage, not from the giving_date of existing loans.
- FR-UTR2-03: The counter file (loans_meta.csv) shall be written atomically: written to a temporary file and then renamed to replace the original. A partial write followed by a crash shall not corrupt loans_meta.csv.
- FR-UTR2-04: If all records for a given YYYY_MM are deleted, the counter shall reset to 000 so the next entry gets _001.
- FR-UTR2-05: After 999 entries in a month the system shall continue generating IDs (e.g., 2026_04_1000) without failure.
- FR-UTR2-06: When a back-dated loan is entered (giving_date in a prior month), the reference_id shall use the current entry month (today's YYYY_MM), not the giving_date month.

**Non-Functional Requirements:**
- NFR-UTR2-01: Atomic write must use `pathlib.Path.replace()` which is atomic on both Windows (NTFS rename) and POSIX.
- NFR-UTR2-02: Fix must be validated by running 10+ consecutive rapid entries in the same month and confirming each receives a unique, sequential reference_id.

**Root Cause Analysis (confirmed from source):**

Two distinct defects combine to produce duplicate IDs on Windows:

**Defect A — Wrong year_month derivation in `_active_year_months()`:**
`data/ref_id_manager.py` line 28:
```python
ym = f"{loan.giving_date.year:04d}_{loan.giving_date.month:02d}"
```
This derives the year_month bucket from `giving_date`, not from the `reference_id`. If a loan was given on 2026-03-15 but entered in April 2026, its reference_id is `2026_04_001` but `_active_year_months()` records it as `2026_03`. When the next April loan is entered, `_active_year_months()` returns a set that does not include `2026_04` (since all April loans have March giving_dates), so the counter for April is incorrectly reset to 000 before generating the next ID — causing duplicate `2026_04_001` entries.

**Defect B — Non-atomic write in `_write_meta()`:**
`loan_manager/ref_id_manager.py` line 112:
```python
with self._meta_path.open("w", ...) as fh:
    writer.writeheader()
    writer.writerows(rows)
```
On Windows, if the process crashes or is forcibly terminated between `open("w")` (which truncates the file immediately) and the completion of `writerows`, loans_meta.csv is left partially written or empty. On the next startup, the empty meta file means all counters read as 0, and the next entry for any month gets `_001` regardless of how many records already exist.

**Fix specifications:**

Fix A — `data/ref_id_manager.py` `_active_year_months()`:
Extract YYYY_MM from the `reference_id` field directly:
```
ym = loan.reference_id.rsplit('_', 1)[0]   # e.g. "2026_04" from "2026_04_001"
```
This correctly anchors the counter bucket to the entry month, not the giving month.

Fix B — `loan_manager/ref_id_manager.py` `_write_meta()`:
Write to a temp file in the same directory, then atomically rename:
```
tmp = self._meta_path.with_suffix(".tmp")
# write to tmp
tmp.replace(self._meta_path)
```

**Edge cases for deep-dive:**

| Edge Case | Scenario | Expected Behaviour | Risk |
|---|---|---|---|
| Back-dated entry | giving_date = 2026-03-01, entry date = 2026-04-04 | reference_id = 2026_04_002 (using today's month) | Low — fixed by Fix A |
| All April records deleted | loans.csv has no 2026_04_* rows | Next April entry gets 2026_04_001 | Low — reset_counter() handles this |
| Counter at 999 | 999 loans exist in April | Next ID = 2026_04_1000 (no zero-padding) | Low — existing code handles >999 |
| Meta file missing | loans_meta.csv deleted | Counter reads as 0; next entry = _001 | Low — _read_meta() returns {} |
| Crash during write | Process killed mid-write | Temp file is incomplete; original intact | Fixed by Fix B |
| Collision on import | Imported record has same ref_id | R4: increment until non-colliding | Existing collision logic unchanged |

**Process Analysis: Reference ID Generation — As-Is vs To-Be**

**Current State (As-Is):**
1. User submits new loan entry
2. `generate_ref_id(year, month)` called with today's year and month
3. `_active_year_months()` reads all loans and builds ym_set from `giving_date` (WRONG)
4. If today's YYYY_MM not in ym_set, `reset_counter()` is called — incorrectly resetting a valid counter
5. `next_ref_id()` reads meta, increments, writes meta non-atomically
6. On Windows crash mid-write, meta is corrupted — next startup starts from 0

**Future State (To-Be):**
1. User submits new loan entry
2. `generate_ref_id(year, month)` called with today's year and month
3. `_active_year_months()` reads all loans and builds ym_set from `reference_id` field (CORRECT)
4. If today's YYYY_MM not in ym_set, `reset_counter()` called only when truly no records exist for that month
5. `next_ref_id()` reads meta, increments, writes to temp file, atomically renames
6. On Windows crash mid-write, original meta file is intact; retry gets correct counter

**User Stories:**

### Story UTR2-1: Unique Reference IDs on Rapid Entry
As a user entering multiple loans in rapid succession in April 2026,
I want each loan to receive a unique reference_id,
So that I can identify, edit, and track each loan individually.

**Acceptance Criteria:**
- Given I enter 10 loans back-to-back on 2026-04-04, Then each receives a unique ID: 2026_04_001 through 2026_04_010 with no duplicates.
- Given all April 2026 records are deleted and I enter a new April loan, Then the new loan gets 2026_04_001.
- Given a loan with giving_date 2026-03-01 is entered on 2026-04-04, Then its reference_id is 2026_04_NNN (current month, not March).
- Given loans_meta.csv is corrupted or missing, When I restart the app and enter a loan, Then the app does not crash and generates a reference_id based on existing loans.csv records.

### Story UTR2-2: Atomic Meta Write Survives Windows Crash
As a Windows user,
I want the reference ID counter to be safe even if the app crashes during a write,
So that the next session does not generate duplicate IDs.

**Acceptance Criteria:**
- Given the app is writing loans_meta.csv and is terminated mid-write, Then on next startup loans_meta.csv is not corrupted (original content retained).
- Given a normal successful write, Then loans_meta.csv contains all correct counters for all months.

**Dependencies:**
- Dev Lead: Fix `data/ref_id_manager.py` `_active_year_months()` (Fix A)
- Dev Lead: Fix `loan_manager/ref_id_manager.py` `_write_meta()` (Fix B)
- QA: Add unit tests for rapid consecutive ID generation (10 entries, same month)
- QA: Add unit test simulating crash recovery (meta written from temp)

---

## BSA Requirements Breakdown: BUG-UTR-3 — View Tab Refresh Overwrites All Records

**Functional Requirements:**
- FR-UTR3-01: When the user clicks Refresh in the View Tab, the system shall recompute loan statuses and write only the loans whose status has changed to storage.
- FR-UTR3-02: If no loan status has changed since last load, clicking Refresh shall not trigger any CSV write operations.
- FR-UTR3-03: Loans whose status has genuinely changed (e.g., Active → Overdue because today passed due_date) shall be persisted to loans.csv.
- FR-UTR3-04: The application log shall not emit "Loan updated" entries for loans whose status has not changed during a Refresh.

**Non-Functional Requirements:**
- NFR-UTR3-01: Performance — for 1500 loans, a Refresh with zero status changes shall complete without triggering 1500 write operations (each of which is a full CSV rewrite).
- NFR-UTR3-02: Correctness — the snapshot must be taken before `recompute_all()` mutates the Loan objects in place.

**Root Cause (confirmed from source):**
`view_tab.py` `load_data()` lines 139–142:
```python
loans = recompute_all(loans, date.today())
for loan in loans:
    update_loan(loan)   # called for ALL loans — O(N) full rewrites
```
`recompute_all()` mutates Loan objects in place (sets `loan.status`). The snapshot must therefore be taken BEFORE calling `recompute_all()` using the pre-mutation status values.

**Fix pattern:**
```
snapshot = {loan.reference_id: loan.status for loan in loans}
loans = recompute_all(loans, date.today())
for loan in loans:
    if loan.status != snapshot.get(loan.reference_id):
        update_loan(loan)
```

**User Stories:**

### Story UTR3-1: Safe Refresh Without Spurious Writes
As a user clicking Refresh in the View Tab,
I want the application to only write loans that have actually changed status,
So that I can refresh the view safely without risking data corruption.

**Acceptance Criteria:**
- Given all loans have statuses consistent with today's date, When I click Refresh, Then no "Loan updated" log entries appear and loans.csv is not rewritten.
- Given one loan has just become Overdue (today == due_date), When I click Refresh, Then exactly that one loan is updated in storage and the View Tab shows it as Overdue.
- Given I click Refresh 5 times in a row with no date changes, Then no CSV writes occur on any of the 5 refreshes.

**Dependencies:**
- Dev Lead: Fix `ui/view_tab.py` `load_data()` — add snapshot pattern
- QA: Verify via application log that zero writes occur when status unchanged

---

## BSA Requirements Breakdown: BUG-UTR-4 — Date Picker Opens on Field Click

**Functional Requirements:**
- FR-UTR4-01: Clicking anywhere on a date input field (text area, not just the dropdown arrow) shall open the calendar popup.
- FR-UTR4-02: The date picker behaviour shall be identical on Windows and Mac — no OS-specific code paths.
- FR-UTR4-03: The fix shall apply to all QDateEdit instances in the application: giving_date field in Entry Tab, due_date field in Entry Tab, paidoff_date field in PaidoffDialog.
- FR-UTR4-04: The calendar popup shall close normally when a date is selected or when the user clicks outside the popup.

**Non-Functional Requirements:**
- NFR-UTR4-01: The `ClickableDateEdit` widget shall be defined once in `ui/widgets.py` and imported wherever a date field is used — no duplication.
- NFR-UTR4-02: No new third-party dependencies introduced — PySide6 built-in calendar widget only.

**Design specification:**
Create `ui/widgets.py` with:
```python
class ClickableDateEdit(QDateEdit):
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.showCalendarWidget()
```
Apply in: `ui/entry_tab.py` (giving_date, due_date), `ui/dialogs/paidoff_dialog.py` (date_edit).

**User Stories:**

### Story UTR4-1: Calendar Popup on Single Click
As a user entering a loan giving_date or due_date,
I want the calendar to open when I click anywhere on the date field,
So that I can select a date without hunting for the small dropdown arrow.

**Acceptance Criteria:**
- Given the Entry Tab is open, When I single-click anywhere on the giving_date field, Then the calendar popup opens.
- Given the Entry Tab is open, When I single-click anywhere on the due_date field, Then the calendar popup opens.
- Given the PaidoffDialog is open, When I single-click anywhere on the paidoff date field, Then the calendar popup opens.
- Given I am on Windows and on Mac, Then the single-click behaviour is identical on both platforms.

**Dependencies:**
- Dev Lead: Create `ui/widgets.py` with `ClickableDateEdit`
- Dev Lead: Replace `QDateEdit` with `ClickableDateEdit` in `entry_tab.py` and `paidoff_dialog.py`

---

## BSA Requirements Breakdown: BC-301 — Paidoff Warning Label in Pending Approval Tab

**Functional Requirements:**
- FR-BC301-01: When a user selects a Paidoff-mode report in the Pending Approval Tab, the system shall display the warning message: "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied."
- FR-BC301-02: The warning label shall be placed below the report header area and above the records detail table (option a — accepted by PO per PD-R4-05).
- FR-BC301-03: The warning label shall be hidden (not visible) when the selected report is not a Paidoff-mode report.
- FR-BC301-04: The warning text shall be styled to draw attention (e.g., amber/orange background or bold text) so it is not overlooked.

**Non-Functional Requirements:**
- NFR-BC301-01: The label must not occupy space when hidden — use `setVisible(False)` not just colour change.
- NFR-BC301-02: Developer must read `pending_approval_tab.py` `_build_ui()` to identify the correct insertion point in the QSplitter bottom panel before implementing.

**User Stories:**

### Story BC301-1: Warning Message Visible for Paidoff Reports
As a user reviewing reports in the Pending Approval Tab,
I want to see a clear warning when a report was generated for a Paidoff loan,
So that I understand the loan has been archived and no extension was applied.

**Acceptance Criteria:**
- Given I select a report with mode="Paidoff" in the Pending Approval Tab, Then the warning message appears above the records table.
- Given I select a report with mode="Monthly" or mode="Daily", Then the warning message is not visible.
- Given the Pending Approval Tab opens with no report selected, Then the warning label is hidden.

**Dependencies:**
- Dev Lead: Read `pending_approval_tab.py` `_build_ui()` before implementing
- Dev Lead: Insert QLabel in bottom panel of QSplitter above QTableWidget for records

---

## BSA Requirements Breakdown: CHG-02-EXT — PaidoffDialog Rate Fields

**Functional Requirements:**
- FR-CHG02-01: The Mark Paidoff dialog shall collect the following inputs in addition to paidoff_date: interest_rate (decimal percentage, default 12.0%), commission_rate (decimal percentage, default 2.0%), tds_flag (boolean checkbox, default unchecked/False).
- FR-CHG02-02: On user confirmation, the system shall compute extension_period in days as: `extension_period = paidoff_date - due_date`.
- FR-CHG02-03: The system shall generate a Daily-mode interest report (mode="Paidoff") using the formula: `Interest = (Amount * interest_rate * extension_period) / (365 * 100)`, `Commission = (Amount * commission_rate * extension_period) / (365 * 100)`.
- FR-CHG02-04: If TDS flag is checked, TDS = 0.1 * Interest shall be included in the report.
- FR-CHG02-05: The generated report shall be sent to the Pending Approval queue with mode="Paidoff".
- FR-CHG02-06: The dialog shall use `ClickableDateEdit` for the paidoff_date field (consistent with BUG-UTR-4 fix).
- FR-CHG02-07: If the loan has no due_date, extension_period shall default to 0 days and interest/commission shall be 0 (PO default: TC-401 option a). [REVIEW REQUIRED — TC-401: User may prefer option (b) — manual extension_period entry for no-due-date loans. PO default is option (a) = 0 days.]

**Non-Functional Requirements:**
- NFR-CHG02-01: The `PaidoffDialog` shall return all 4 values (paidoff_date, interest_rate, commission_rate, tds_flag) to the caller via getter methods, not via global state.
- NFR-CHG02-02: Report generation shall reuse the existing report pipeline (report_manager write functions) — no new report schema.

**User Stories:**

### Story CHG02-1: Paidoff Dialog Collects Rate Information
As a user right-clicking a loan and selecting Mark Paidoff,
I want the dialog to ask for the interest rate, commission rate, and TDS flag as well as the paidoff date,
So that a correct interest report can be generated and sent for approval.

**Acceptance Criteria:**
- Given I right-click a loan and select Mark Paidoff, Then the dialog shows fields for: paidoff_date, interest_rate (default 12.0), commission_rate (default 2.0), and TDS checkbox (unchecked by default).
- Given I confirm with paidoff_date, interest_rate, commission_rate, and TDS flag set, Then a report with mode="Paidoff" appears in the Pending Approval Tab.
- Given the loan's due_date is 2026-01-01 and paidoff_date is 2026-04-01, Then extension_period = 90 days and Interest = (Amount * interest_rate * 90) / (365 * 100).
- Given TDS flag is checked, Then the report includes TDS = 0.1 * Interest.
- Given the loan has no due_date, Then extension_period = 0, interest = 0, commission = 0 in the report.

### Story CHG02-2: Paidoff Report in Pending Approval Queue
As a user reviewing the Pending Approval Tab,
I want to see Paidoff loan reports in the queue,
So that I can review and approve or decline the interest calculation before it is finalised.

**Acceptance Criteria:**
- Given a Paidoff report is generated, Then it appears in the Pending Approval reports list with mode="Paidoff".
- Given I select the Paidoff report, Then the warning "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied." is visible above the records table (BC-301).
- Given I approve the Paidoff report, Then no loan records are updated in loans.csv (loan is already in history.csv).

**Dependencies:**
- Dev Lead: Extend `PaidoffDialog` with rate fields
- Dev Lead: Wire PaidoffDialog output to report generation pipeline
- Dev Lead: Coordinate with BC-301 implementation (warning label must be present before Paidoff reports are generated)
- DM: Confirm mode="Paidoff" in pending_reports.csv schema (no schema change per TC-301)

---

## BSA → DM Agent: Data Requirements Brief

**Feature:** BUG-UTR-2 Reference ID Counter Fix

**Business entities identified:**
- RefIdMeta: tracks the high-water mark counter per YYYY_MM bucket

**Key attributes per entity:**
- RefIdMeta.year_month: YYYY_MM string, required, example "2026_04"
- RefIdMeta.counter: integer, required, high-water mark (last issued order number), example 3

**Relationships:**
- RefIdMeta.year_month is derived from Loan.reference_id (first two underscore segments), not from Loan.giving_date

**Business rules governing data:**
- Rule 1: The year_month bucket in loans_meta.csv must correspond to the first two underscore-separated segments of the reference_id, not the giving_date month
- Rule 2: A year_month entry is removed from loans_meta.csv only when reset_counter() is explicitly called (i.e., when no loans remain with that reference_id prefix)
- Rule 3: The file must be written atomically — no partial state must ever be visible to readers

**Data access patterns:**
- Read on every new loan entry: _read_meta() → full file scan (small file, <1KB typical)
- Write on every new loan entry: _write_meta() → atomic write via temp+rename

**Volume expectations:**
- Typically 1–12 rows (one per active YYYY_MM bucket), never exceeds 12 rows in normal operation

**Compliance / sensitivity:**
- Not PII. File corruption produces duplicate IDs — a data integrity issue, not a privacy issue.

---

**Feature:** CHG-02-EXT PaidoffDialog Rate Fields

**Business entities identified:**
- PendingReport (header record in pending_reports.csv)
- PendingReportRecord (line item in pending_report_records.csv)

**Key attributes per entity:**
- PendingReport.mode: string, "Paidoff" reserved value (confirmed TC-301 — no schema change)
- PendingReportRecord.interest_rate: decimal, as entered in PaidoffDialog
- PendingReportRecord.commission_rate: decimal, as entered in PaidoffDialog
- PendingReportRecord.tds_flag: boolean ("True"/"False" string in CSV)
- PendingReportRecord.extension_period: integer days (paidoff_date - due_date)
- PendingReportRecord.extension_period_unit: "days" (always for Paidoff mode)

**Relationships:**
- PendingReport 1:N PendingReportRecord (one report per Paidoff event, one record row per paidoff loan)

**Business rules governing data:**
- Rule 1: mode="Paidoff" is reserved and must not conflict with "Monthly", "Daily", "Both" modes
- Rule 2: For no-due-date loans, extension_period = 0 (PO default TC-401)
- Rule 3: Approving a Paidoff report does NOT update loans.csv (loan is already in history.csv)

**Volume expectations:**
- One row per paidoff event; low frequency (single-user usage)

**Compliance / sensitivity:**
- Financial data — interest calculations must be exact per the Daily formula in R3/R5

---

## UAT Plan: Phase 3 Closure

**Objective:** Validate that all 6 run_4 scope items are implemented correctly from an end-user perspective on Windows primary, Mac secondary.

**Scope:** BUG-UTR-1 through BUG-UTR-4, BC-301, CHG-02-EXT on actual user workflows.

**Test Scenarios:**

| ID | Scenario Description | Steps | Expected Result |
|---|---|---|---|
| UAT-UTR1-01 | Filter Borrower Group and click Apply Filters | 1. Open Interest Calculator Tab. 2. Select "bg1" from Borrower Group. 3. Click Apply Filters. | Table shows only bg1 loans; Borrower Group combo still shows "bg1". |
| UAT-UTR1-02 | Combine Borrower Group + By Month filters | 1. Select "bg1" + month "April". 2. Click Apply Filters. | Table shows only bg1 loans with April due dates; both combos retain selections. |
| UAT-UTR2-01 | Enter 5 loans rapidly | 1. Enter 5 loans back-to-back on same day. | Each loan gets a unique reference_id with sequential order (001, 002, 003, 004, 005). |
| UAT-UTR2-02 | Back-dated giving_date entry | 1. Enter loan with giving_date = last month. | reference_id uses current month (today's YYYY_MM), not last month. |
| UAT-UTR3-01 | Refresh with no status changes | 1. Open View Tab. 2. Click Refresh. 3. Check app.log. | Zero "Loan updated" entries in log. No CSV rewrite observed. |
| UAT-UTR4-01 | Click date field text area | 1. Open Entry Tab. 2. Click on the text area of the giving_date field (not the arrow). | Calendar popup opens. |
| UAT-UTR4-02 | Date picker on PaidoffDialog | 1. Right-click loan, select Mark Paidoff. 2. Click text area of paidoff date field. | Calendar popup opens. |
| UAT-BC301-01 | Select Paidoff report in Pending Approval | 1. Generate a Paidoff report. 2. Open Pending Approval Tab. 3. Select the Paidoff report. | Warning label visible above records table: "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied." |
| UAT-BC301-02 | Select non-Paidoff report | 1. Select a Monthly or Daily report. | Warning label not visible. |
| UAT-CHG02-01 | Mark Paidoff with rates | 1. Right-click loan, select Mark Paidoff. 2. Enter paidoff_date, interest_rate=12, commission_rate=2, TDS=checked. 3. Confirm. | Report appears in Pending Approval with mode="Paidoff" and correct interest calculation. TDS = 0.1 * Interest. |
| UAT-CHG02-02 | Paidoff loan with no due_date | 1. Right-click loan with no due_date. 2. Select Mark Paidoff. 3. Confirm. | extension_period = 0, interest = 0, commission = 0 in report. |

**Entry Criteria:**
- All 6 scope items implemented by backend dev
- Existing 197 tests pass + new unit tests for BUG-UTR-2 and BUG-UTR-3 pass
- QA Lead signoff received
- Application running on Windows test environment

**Exit Criteria:**
- All 11 UAT scenarios pass
- No P1 defects open
- User provides sign-off

**Sign-off Owner:** End User (Windows)

---

## Open Items and Handoff Notes

### For Dev Lead
- BUG-UTR-2 Fix A: `data/ref_id_manager.py` `_active_year_months()` — replace `loan.giving_date` with `loan.reference_id` as year_month source
- BUG-UTR-2 Fix B: `loan_manager/ref_id_manager.py` `_write_meta()` — implement atomic write via temp+rename
- BUG-UTR-1: `ui/interest_calculator_tab.py` `_on_apply_filters()` — capture filter values before `_load_loans()`
- BUG-UTR-3: `ui/view_tab.py` `load_data()` — add status snapshot before `recompute_all()`
- BUG-UTR-4: Create `ui/widgets.py` with `ClickableDateEdit`, apply everywhere QDateEdit is used
- BC-301: Read `pending_approval_tab.py` `_build_ui()` before implementing; insert QLabel in bottom panel above records QTableWidget
- CHG-02-EXT: Extend `PaidoffDialog` with rate fields; wire to report pipeline

### For DM
- Confirm no schema change needed for CHG-02-EXT (mode="Paidoff" already supported per TC-301)
- Confirm loans_meta.csv schema unchanged (Fix B is a write-process change only)

### [REVIEW REQUIRED — TC-401]
**Priority:** Low
**Item:** When a loan has no due_date and is marked Paidoff, what should extension_period be?
- Option (a): extension_period = 0, interest = 0 [PO default — proceed unless user specifies otherwise]
- Option (b): user manually enters extension_period in the PaidoffDialog
**Current default:** Proceeding with option (a) per PD-R4-07.
**Impact:** If option (b) is preferred, the PaidoffDialog must include a conditional input field for extension_period (shown only when due_date is None).
