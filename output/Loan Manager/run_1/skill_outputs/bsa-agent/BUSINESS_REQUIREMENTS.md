# Business Requirements Document
## Loan Manager — BSA Agent Output
**Run**: run_1 | **Wave**: 1 | **Date**: 2026-04-03

---

## Table of Contents
1. [R1 — Loan Entry Recording](#r1)
2. [R2 — Loan View Tab](#r2)
3. [R3 — Record Modification and Status Management](#r3)
4. [R4 — Reference ID, Delete, and Extend](#r4)
5. [R5 — Interest Calculator (Deep-Dive)](#r5)
6. [R6 — UI Accessibility, Export, Import](#r6)
7. [R7 — Usability and Sample Data](#r7)
8. [R8 — Prototype Stack and Storage](#r8)
9. [R9 — UI Theme](#r9)
10. [R10 — User Guide and Startup Scripts](#r10)
11. [UT1 — User-Testing Defects](#ut1)
12. [BSA → DM Agent: Data Requirements Brief](#dm)
13. [UAT Plan for Prototype](#uat)

---

<a name="r1"></a>
## BSA Requirements Breakdown: R1 — Loan Entry Recording

**Functional Requirements:**
- FR-001: The system shall provide a form for recording a new loan entry with the following fields: Borrower Name, Depositor Name, Amount, Giving Date, Due Date (optional), Borrower Group, Depositor Group (optional).
- FR-002: The system shall present a calendar date-picker widget for Giving Date and Due Date fields; manual text entry for dates is not permitted.
- FR-003: The system shall default the Due Date field to "No Due Date" (unchecked/blank) on the form.
- FR-004: The Amount field shall accept only non-negative integers and default to INR currency denomination.
- FR-005: The system shall provide autocomplete suggestions drawn from existing stored values for: borrower_name, borrower_group, depositor_name, depositor_group.
- FR-006: On successful save, the system shall persist the new loan record to `./data/loans.csv`.
- FR-007: On successful save, the system shall display a status-bar message: `Loan saved successfully. Reference ID: {ref_id}.`
- FR-008: After saving, the system shall NOT automatically switch to the View Tab; the user remains on the entry form.
- FR-009: Giving Date is stored as a reference-only field and shall not contribute to tenure or interest calculations.

**Non-Functional Requirements:**
- NFR-001: Autocomplete lookups shall respond within 200ms for up to 1500 existing records.
- NFR-002: Date-picker widget must be cross-platform (Windows and macOS) using PySide6 native calendar component.

**User Stories:**

### Story: Record a New Loan
As a loan manager operator,
I want to fill in a loan entry form and save it,
So that the new loan is persisted with a unique reference ID and I am immediately notified of success.

**Acceptance Criteria:**
- Given the entry form is open, When the user fills all required fields and clicks Save, Then the record is written to `loans.csv` and the status bar shows `Loan saved successfully. Reference ID: {ref_id}.`
- Given the Due Date field, When the form opens, Then "No Due Date" is the default state (field is blank/unchecked).
- Given the Amount field, When the user enters a negative number or a decimal, Then the system rejects the input and shows a validation error.
- Given the Borrower Name field, When the user begins typing, Then autocomplete suggestions from existing borrower names appear within 200ms.
- Given the date fields, When the user clicks Giving Date or Due Date, Then a calendar date-picker widget appears for selection.
- Given a successful save, When the record is persisted, Then the active tab does not change.

**Assumptions / Open Questions:**
- Depositor Name is optional (evidenced by sample records b14, b15 which have depositor but no depositor_group). [REVIEW REQUIRED: Is Depositor Name itself optional, or only Depositor Group? b14/b15 have a depositor_name but no depositor_group. Clarify whether a loan entry with NO depositor_name at all is permitted.]
- Giving Date is mandatory (no "No Giving Date" checkbox exists by specification).

---

<a name="r2"></a>
## BSA Requirements Breakdown: R2 — Loan View Tab

**Functional Requirements:**
- FR-010: The system shall display all active loan records in a tabular View Tab with columns: SNo, ref_id, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status.
- FR-011: SNo shall be a view-order counter computed at render time and shall not be persisted to storage.
- FR-012: The table shall support column-level sorting: alphabetical for borrower_name, borrower_group, depositor_name, depositor_group; date-based for giving_date, due_date; numeric for amount.
- FR-013: Any missing/blank field value shall display as "Unknown" in the View Tab.
- FR-014: When a loan has no depositor_group (e.g., b14, b15), the depositor_group cell shall display "Unknown" and shall be inline-editable by the user.
- FR-015: Paidoff records shall not appear in the View Tab.
- FR-016: The View Tab shall support Excel-style column filtering including a year→month→date hierarchy for date columns, showing only values present in existing records.

**Non-Functional Requirements:**
- NFR-003: The View Tab table must remain responsive (render within 1 second) for up to 1500 records.
- NFR-004: The chosen front-end table component must support sortable, filterable, and inline-editable rows — this choice must be documented as an architectural requirement by the Solution Architect.
- NFR-005: Text color and background color choices for the View Tab must ensure sufficient contrast for readability; light background with white text is explicitly unacceptable (per UT1 feedback).

**User Stories:**

### Story: View All Active Loans
As a loan manager operator,
I want to see all active (non-Paidoff) loan entries in a sortable table,
So that I can quickly review and manage the loan portfolio.

**Acceptance Criteria:**
- Given loans exist in `loans.csv`, When the View Tab is opened, Then all non-Paidoff records are displayed in the column order: SNo, ref_id, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status.
- Given a loan with no depositor_group (like b14, b15), When displayed in View Tab, Then D Grp cell shows "Unknown" and is inline-editable.
- Given the ref_id column, When the user clicks the column header, Then records sort alphabetically by ref_id; similarly for other column types.
- Given a date column filter, When the user opens the filter dropdown, Then available years are shown first; on selecting a year, available months appear; on selecting a month, filtered records are shown.

**Assumptions / Open Questions:**
- "Unknown" as a display sentinel for missing values is also the editable placeholder; editing "Unknown" saves the real value back to CSV. [REVIEW REQUIRED: Should saving a blank/empty value in an inline edit revert to "Unknown" display or store a blank?]

---

<a name="r3"></a>
## BSA Requirements Breakdown: R3 — Record Modification and Status Management

**Functional Requirements:**
- FR-017: The user shall be able to inline-edit any field of a loan record in the View Tab; changes shall persist to `loans.csv`.
- FR-018: The system shall expose a Status dropdown (QComboBox) per record with options: Active, Overdue, Paidoff, Pending.
- FR-019: Status auto-computation rules on app launch:
  - Active: giving_date <= today < due_date
  - Overdue: due_date <= today (also applies when no due_date is present per R7 clarification)
  - Pending: giving_date > today (includes no-due-date loans where giving_date > today)
  - Paidoff: explicitly set by user with a paidoff_date
- FR-020: On app launch, the system shall recompute and overwrite stored status for all non-Paidoff records according to FR-019 rules.
- FR-021: When a user marks a record as Paidoff, the system shall prompt for a paidoff_date via a date-picker.
- FR-022: On Paidoff confirmation, the system shall:
  a. Log the target row to a temporary recovery file before any write.
  b. Append the record with paidoff_date to `history.csv`.
  c. Remove the record from `loans.csv`.
  d. Generate an interest calculation report (Daily mode, extension_period(days) = paidoff_date - due_date) and submit it to the Pending Approval queue.
- FR-023: The app shall create a timestamped backup of `loans.csv` before any destructive operation (Paidoff or bulk Approve). [NOTE: Deferred from prototype scope per R3, but must be architecturally documented as a future requirement.]
- FR-024: When the user manually sets a record to Active (override of Overdue status), the system shall prompt for a new due_date (same flow as R4 Extend).
- FR-025: Manual Active override shall persist the new due_date and status recomputation on next launch shall evaluate against this new due_date.
- FR-026: Paidoff records shall not be visible in the View Tab; re-activation requires manual CSV edit and re-import.
- FR-027: Allowed status transition matrix:
  - Active → Overdue, Paidoff, Pending (via giving_date inline edit)
  - Overdue → Active (via R4 Extend or manual Active override with new due_date), Paidoff
  - Pending → Active (via inline giving_date edit to past/today date)
  - Paidoff → (not reversible in-app; requires CSV manual edit + re-import)
- FR-028: All manual status toggles shall update both the in-memory state and `loans.csv` immediately.

**Non-Functional Requirements:**
- NFR-006: Crash-safety for Paidoff write: a recovery log file shall be written with the target row data before executing the dual-write to `loans.csv` and `history.csv`. Potential failure modes shall be documented.
- NFR-007: Status recomputation on launch shall complete within 2 seconds for 1500 records.

**User Stories:**

### Story: Mark a Loan as Paidoff
As a loan manager operator,
I want to mark a loan as Paidoff and record the payoff date,
So that the loan is archived in history and an interest report is queued for approval.

**Acceptance Criteria:**
- Given an Active or Overdue loan, When the user selects Paidoff from the Status dropdown, Then the system prompts for a paidoff_date via a date-picker.
- Given a valid paidoff_date is entered, When confirmed, Then the record is appended to `history.csv` with paidoff_date, removed from `loans.csv`, and an interest report (Daily mode) is created in the Pending Approval queue.
- Given a crash occurs between the two writes, When the app restarts, Then the recovery log file is present and the operator can manually resolve the partial write.
- Given app launch, When the app loads, Then status for all non-Paidoff records is recomputed per FR-019 rules, overriding any previously stored values.

### Story: Override Overdue to Active
As a loan manager operator,
I want to manually set an Overdue loan to Active with a new due date,
So that the loan tenure is effectively extended without losing the reference_id.

**Acceptance Criteria:**
- Given an Overdue record, When the user selects Active from the Status dropdown, Then the system prompts for a new due_date.
- Given a new due_date is provided, When saved, Then the record's due_date is updated and status is set to Active.
- Given the new due_date has already passed at next launch, When the app recomputes, Then status reverts to Overdue based on the new due_date.

**Assumptions / Open Questions:**
- A loan with no due_date and giving_date <= today is treated as Overdue (per R7 clarification).
- [REVIEW REQUIRED]: When Paidoff is triggered and the paidoff_date < due_date (loan paid back early), should extension_period(days) be negative or zero? Clarify the expected behavior for early payoff interest calculation.

---

<a name="r4"></a>
## BSA Requirements Breakdown: R4 — Reference ID, Delete, and Extend

**Functional Requirements:**
- FR-029: Each loan record shall be assigned a reference_id in format `YYYY_MM_<order>` where YYYY and MM are the calendar year and month of entry creation, and order is a zero-padded 3-digit integer (001–999), with overflow to 4+ digits beyond 999.
- FR-030: The reference_id counter per YYYY_MM shall be tracked in `loans_meta.csv` as a high-water mark.
- FR-031: If all records for a given YYYY_MM are deleted, the counter resets to 001 for the next entry in that month.
- FR-032: If `loans.csv` is entirely empty (header only or file absent), all YYYY_MM counters reset and the next entry uses today's YYYY_MM with order 001.
- FR-033: When a legacy-imported record is auto-assigned a ref_id that collides with an existing record, the system shall increment the order until a non-colliding ID is found.
- FR-034: The reference_id field shall be visible but not editable by the user in the View Tab.
- FR-035: The user shall be able to Delete a loan record from the View Tab; the record is removed from `loans.csv` and the ref_id is not reused.
- FR-036: After deletion of `2026_03_005`, the next new entry in March 2026 receives `2026_03_006` (next in high-water sequence, not gap-fill).
- FR-037: The user shall be able to Extend a loan record from the View Tab. Extension inputs: extension_period_unit (months [default] or days) and extension_period (integer).
- FR-038: Extend logic: new giving_date = old due_date; new due_date = old due_date + extension_period (in extension_period_unit). The reference_id is reused and the record is overwritten in-place in `loans.csv`. History of the pre-extension record is not retained (explicitly accepted per requirements).
- FR-039: For loans with no due_date, Extend shall set new giving_date = today and new due_date = date selected by user via date-picker.
- FR-040: The architectural choice for the front-end table (supporting sort, filter, inline-edit for up to 1500 rows) shall be documented as a formal architectural requirement.

**Non-Functional Requirements:**
- NFR-008: The `loans_meta.csv` counter update shall be atomic with the new record write to avoid counter drift.
- NFR-009: Reference ID generation shall handle the 1000th loan in a month without error (overflow from 3-digit to 4-digit order).

**User Stories:**

### Story: Auto-assign Reference ID on New Loan
As the system,
I want to assign the next sequential reference_id for the current month,
So that every loan record has a unique, traceable identifier.

**Acceptance Criteria:**
- Given no loans exist for 2026_03, When a new loan is entered in March 2026, Then it receives ref_id `2026_03_001`.
- Given the last loan for 2026_03 was `2026_03_999`, When a new loan is entered, Then it receives `2026_03_1000`.
- Given all March 2026 records are deleted, When a new loan is entered in March 2026, Then it receives `2026_03_001`.

### Story: Extend a Loan
As a loan manager operator,
I want to extend a loan's tenure by specifying an extension period,
So that the due date is updated and the reference_id is preserved.

**Acceptance Criteria:**
- Given loan `2026_03_001` with due_date 2026-04-02, When extended by 1 month, Then giving_date becomes 2026-04-02 and due_date becomes 2026-05-02.
- Given loan with no due_date, When Extend is triggered, Then system sets giving_date = today and prompts for new due_date via date-picker.
- Given an Extend operation, When saved, Then the record in `loans.csv` is overwritten in-place; no separate history entry is created.

**Assumptions / Open Questions:**
- [REVIEW REQUIRED]: When a user deletes a record that has pending reports referencing it, does the deletion require confirmation beyond the standard Pending Approval warning described in R5?

---

<a name="r5"></a>
## BSA Requirements Breakdown: R5 — Interest Calculator (Deep-Dive)

**Functional Requirements:**
- FR-041: The system shall provide an Interest Calculator Tab with three computation modes selectable via a hover-dropdown: Monthly (default), Daily, Both.
- FR-042: All modes shall accept the following global inputs: interest_rate (%), commission_rate (%), extension_period (integer), extension_period_unit (months for Monthly; days for Daily; per-record for Both), TDS_flag (boolean, default false).
- FR-043: In Both mode, extension_period_unit and extension_period shall be entered on a per-record basis (with global defaults pre-filled).
- FR-044: In Both mode, an orchestrator function shall exist in the core calculator code file to handle the dual-mode calculation for testability.
- FR-045: The Interest Calculator Tab shall expose 5 filter controls: Borrower Group, Borrower Name, Depositor Name, Depositor Group, ByMonth (due_date month within current calendar year, including Overdue records). All filter dropdowns shall exclude Paidoff records.
- FR-046: When no filter is applied, the calculator shall display only records with no due_date value.
- FR-047: When any filter is applied, the calculator shall exclude records with no due_date and display only records matching the filter criteria.
- FR-048: Depositor Group filter shall include an "Unknown"/blank option to allow filtering for loans with no depositor_group (e.g., b14, b15).
- FR-049: Multiple filters may be applied simultaneously (AND logic).
- FR-050: The displayed record columns in the calculator table shall be: reference_id, borrower_name, amount, depositor_name, giving_date, due_date.
- FR-051: All 4 per-record parameters (interest_rate, commission_rate, extension_period, extension_period_unit) shall be inline-editable within the filtered table.
- FR-052: Global header values for interest_rate and commission_rate, when changed, shall overwrite all rows (including manually-edited rows).
- FR-053: The "Generate Report" button shall be disabled until the user clicks "Calculate".
- FR-054: Calculation formulas (giving_date is excluded from all time-period calculations; only extension_period drives the computation window):
  - Monthly: Interest = (Amount * interest_rate * extension_period) / (12 * 100); Commission = (Amount * commission_rate * extension_period) / (12 * 100)
  - Daily: Interest = (Amount * interest_rate * extension_period) / (365 * 100); Commission = (Amount * commission_rate * extension_period) / (365 * 100)
  - TDS (when TDS_flag = true): TDS = 0.1 * Interest
- FR-055: After Calculate, a summary is produced: total_loan_amount, total_interest, total_commission (and total_TDS when TDS_flag = true).
- FR-056: "Generate Report" submits calculated records to the Pending Approval queue as a new report with report_id format: `RPT_YYYYMMDD_<order>` (e.g., RPT_20260320_001).
- FR-057: Each pending report record shall store pre-extension values and preview columns post_extension_giving_date and post_extension_due_date.
- FR-058: The Pending Approval Tab shall list all pending reports; user can Approve or Decline each.
- FR-059: On Approve, the system shall update `loans.csv` records (overwriting giving_date and due_date with post-extension values, same logic as R4 Extend, batch) and update `pending_report_records.csv` with final values.
- FR-060: On Approve where a report's reference_ids overlap with another pending report, the system shall warn: `This report shares loan records with another pending report. Approving may overwrite previous updates.` with Proceed and Cancel options. If Proceed is selected, the system shall silently overwrite storage and update the other report's records.
- FR-061: On Approve where a report contains reference_ids for loans deleted from the View Tab, the system shall warn: `Records in this report have been deleted.` User may Proceed (approve remaining valid records) or Decline.
- FR-062: On Decline, the report_id is marked Declined, pending_report_records are removed from queue, and no loan records are updated.
- FR-063: Report contents in the Pending Approval Tab shall be inline-editable per record for all calculator parameters (interest_rate, commission_rate, extension_period, extension_period_unit, TDS_flag). On edit, interest_amount, commission_amount, and tds_amount shall auto-recalculate.
- FR-064: When a report record is edited, the report's report_latest_update_dt is updated to the edit timestamp (replacing the creation date).
- FR-065: The Pending Approval queue shall persist to `pending_reports.csv` (report metadata) and `pending_report_records.csv` (line items) and survive application restarts.
- FR-066: Report format per borrower (as displayed and exportable):
  ```
  [Borrower Name]
  [Amount, Giving Date, Depositor, Extension Period, Extension Period Unit, Due Date, Interest Amount, Commission Amount, TDS]
  record1
  ...
  recordN
  [Total Amount]
  [Total Interest]
  [Total Commission]
  [Total TDS]
  ```

**Non-Functional Requirements:**
- NFR-010: Filter dropdowns in the Interest Calculator Tab shall not reset to "All" after selection; selected filter state must persist until explicitly cleared by the user. (Addresses UT1 bug.)
- NFR-011: Auto-recalculation on inline edit in the Pending Approval Tab shall complete within 100ms per cell edit.
- NFR-012: The Pending Approval queue must be fully restored from CSV on app restart with no data loss.

---

### R5 Deep-Dive: Detailed Acceptance Criteria

#### Mode: Monthly
- Given records filtered by Borrower Group = bg1, When mode = Monthly with interest_rate=12, commission_rate=2, extension_period=3 (months), TDS_flag=false, Then for a Rs 10,000 loan: Interest = (10000 * 12 * 3) / (12 * 100) = Rs 300; Commission = (10000 * 2 * 3) / (12 * 100) = Rs 50.
- Given global interest_rate is changed after per-record edits, When user updates the global field, Then all rows (including previously manually-edited rows) reflect the new global value.
- Given extension_period_unit in Monthly mode, Then it is fixed as "months" and the field is non-editable at the per-record level in this mode.

#### Mode: Daily
- Given records filtered by Depositor Name = d1, When mode = Daily with interest_rate=12, commission_rate=2, extension_period=30 (days), TDS_flag=false, Then for Rs 10,000: Interest = (10000 * 12 * 30) / (365 * 100) = Rs 98.63 (rounded per display precision); Commission = (10000 * 2 * 30) / (365 * 100) = Rs 16.44.
- Given a Paidoff flow (R3), When Daily mode is invoked, extension_period(days) = paidoff_date - due_date, If paidoff_date >= due_date, Then extension_period >= 0 and calculation proceeds normally.
- [REVIEW REQUIRED]: If paidoff_date < due_date (early payoff), is extension_period = 0 or should it be treated as 0 with a note? Clarify expected behavior.
- Given extension_period_unit in Daily mode, Then it is fixed as "days" and is non-editable at the per-record level in this mode.

#### Mode: Both
- Given mode = Both, When global defaults are set (e.g., interest_rate=12, commission_rate=2, extension_period=1, extension_period_unit=months), Then all rows are pre-filled with these defaults.
- Given a specific record in Both mode, When the user overrides extension_period_unit to "days" and extension_period to 30 for that record, Then that record's calculation uses Daily formula and other records retain Monthly formula.
- Given the orchestrator function for Both mode exists, When called in tests, Then it returns a list of per-record results where each record independently selects Monthly or Daily formula based on its extension_period_unit.
- Given global header change in Both mode, When interest_rate is updated globally, Then all rows receive the new interest_rate while their individual extension_period_unit selections are preserved.

#### Filter Behavior
- Given no filter is applied (all filter dropdowns = "All"), Then the calculator table shows ONLY records where due_date IS NULL/empty.
- Given any filter is applied (at least one dropdown != "All"), Then records with no due_date are excluded; only records matching all active filter criteria are shown.
- Given ByMonth filter = April (current year 2026), Then records where due_date falls in April 2026 are shown, including records already Overdue whose due_date was in April 2026.
- Given Depositor Group filter with "Unknown" selected, Then records b14 and b15 (no depositor_group) are included in the filtered set.
- Given a filter is selected from a dropdown, When the user navigates away and returns to the Interest Calculator Tab, Then the selected filter value remains set (not reset to "All"). [Addresses UT1.]

#### Pending Approval Flow
- Given a report is generated (Calculate → Generate Report), Then a new entry appears in the Pending Approval queue with status = Pending, report_id = RPT_YYYYMMDD_NNN, report_latest_update_dt = creation datetime.
- Given the Pending Approval Tab, When the report is displayed, Then pre-extension giving_date and due_date are shown alongside preview columns post_extension_giving_date and post_extension_due_date.
- Given inline edit of extension_period for a record in the Pending Approval Tab, When the value changes, Then interest_amount, commission_amount, and tds_amount auto-recalculate immediately and report_latest_update_dt is updated.
- Given Approve is clicked, When no conflicts exist, Then loans.csv records are overwritten with post-extension values and pending report status is updated to Approved.
- Given Decline is clicked, Then report status is set to Declined; pending_report_records line items are deleted from queue; loans.csv is unchanged.

#### Conflict Warning: Same reference_id in Multiple Pending Reports
- Given report RPT_20260401_001 and RPT_20260401_002 both contain reference_id `2026_03_001`, When the user attempts to approve RPT_20260401_001, Then the system displays: `This report shares loan records with another pending report. Approving may overwrite previous updates.` with Proceed and Cancel options.
- Given Proceed is selected, Then RPT_20260401_001 is approved, loans.csv is updated, and RPT_20260401_002's records for `2026_03_001` are silently updated in pending_report_records.csv to reflect the new post-extension values.
- Given Cancel is selected, Then no changes are made and the user returns to the Pending Approval Tab.

#### Deleted Record Warning
- Given reference_id `2026_03_001` is deleted from the View Tab while it exists in a pending report, When the pending report is approved, Then the system warns: `Records in this report have been deleted.`
- Given the user selects Proceed on the warning, Then approval updates only the records still existing in loans.csv; deleted records are skipped silently.
- Given the user selects Decline, Then no changes are made.

#### Inline Editing and Auto-Recalculation
- Given a record in the pending report detail table, When interest_rate is changed from 12 to 15, Then interest_amount recalculates as (Amount * 15 * extension_period) / (formula_denominator) immediately.
- Given any calculator parameter is edited, When the edit is committed (focus lost or Enter pressed), Then interest_amount, commission_amount, and tds_amount (if TDS_flag=true) all update without requiring a separate "Recalculate" button press.

---

**User Stories:**

### Story: Calculate Interest in Monthly Mode
As a loan manager operator,
I want to select filtered loan records and compute monthly interest and commission,
So that I can generate an approval report with the correct calculations.

**Acceptance Criteria:**
- Given filter Borrower Group = bg1 is applied, When monthly mode with rate inputs is set and Calculate is clicked, Then interest and commission are computed per record using the Monthly formula and a summary total is displayed.
- Given Calculate is clicked, When no errors exist, Then "Generate Report" button is enabled.
- Given "Generate Report" is clicked, Then a pending report is created and appears in the Pending Approval Tab.

### Story: Approve a Pending Report
As a loan manager operator,
I want to review and approve a pending interest report,
So that loan records are batch-updated with new extension dates.

**Acceptance Criteria:**
- Given a pending report is displayed, When Approve is clicked with no conflicts, Then all referenced loans in loans.csv are updated and the report status becomes Approved.
- Given a pending report contains a deleted loan, When Approve is clicked, Then the system warns and allows selective approval.
- Given two reports share a reference_id, When one is approved, Then the conflict warning is shown with Proceed/Cancel options.

### Story: Filter Interest Calculator Records
As a loan manager operator,
I want to filter records by borrower group, borrower name, depositor name, depositor group, or due-date month,
So that I only calculate interest for the relevant subset of loans.

**Acceptance Criteria:**
- Given no filter is set, Then only records with no due_date are displayed in the calculator table.
- Given Borrower Group filter = bg1 is selected, Then only loans belonging to bg1 with a due_date are shown; no-due-date records are excluded.
- Given a filter is selected, When the user switches tabs and returns, Then the filter value is preserved.

**Assumptions / Open Questions:**
- [REVIEW REQUIRED]: Currency display precision for interest amounts — should values be rounded to 2 decimal places, or displayed as exact floating-point?
- [REVIEW REQUIRED]: In Both mode, is the per-record extension_period_unit defaulted to the global value initially, or does the user always have to set it explicitly per record?
- The requirement states "giving_date is only a reference column and is not included in any kind of time-period calculations" — this is treated as authoritative. Any implementation computing tenure from giving_date to due_date must be corrected.

---

<a name="r6"></a>
## BSA Requirements Breakdown: R6 — UI Accessibility, Export, and Import

**Functional Requirements:**
- FR-067: The system shall provide Excel-like column filtering for all columns in the View Tab. Date column filters shall present a year→month→date hierarchy showing only values present in existing records.
- FR-068: The system shall allow export of the current View Tab data to both .csv and .xlsx formats.
- FR-069: The system shall allow export of generated reports (Interest Calculator output) to both .csv and .xlsx formats.
- FR-070: All loan records (all years, excluding Paidoff) shall be stored in a single `loans.csv` file.
- FR-071: The system shall support import of .csv and .xlsx files for historical loan data.
- FR-072: On import, if records have no reference_id, the system shall auto-assign new ref_ids in YYYY_MM_<order> format.
- FR-073: On import (re-import scenario), if records already have reference_ids, the system shall upsert records (append new, overwrite existing).
- FR-074: On import conflict (imported ref_id matches existing ref_id), imported data takes priority: all fields of the imported record overwrite the existing record completely.
- FR-075: Before committing any destructive import overwrite, the system shall show a preview dialog: total rows to be inserted (new), total rows to be overwritten (existing), sample overwritten reference_ids. Proceed and Cancel options. Message format: `N records will be overwritten: [sample ref_ids]. Proceed / Cancel.`
- FR-076: For new-only imports (no conflicts), the preview dialog shall be skipped.
- FR-077: If imported data has reference_ids in a non-standard format (legacy free-text IDs), the import service shall check for collisions after auto-assignment and increment until a non-colliding ID is found.
- FR-078: CSV data files shall reside in a fixed `./data/` subfolder.
- FR-079: The full year→month→date hierarchy shall be required for date column filters (not just year→month).

**Non-Functional Requirements:**
- NFR-013: Import processing for up to 1500 records shall complete within 5 seconds.
- NFR-014: Export file format (xlsx) shall use openpyxl or equivalent; no external paid libraries.

**User Stories:**

### Story: Import Historical Loan Data
As a loan manager operator,
I want to import a CSV file of historical loans,
So that legacy records are loaded into the application with correct reference IDs.

**Acceptance Criteria:**
- Given a CSV with no reference_ids, When imported, Then all records are auto-assigned ref_ids in YYYY_MM_<order> format based on their entry dates.
- Given a CSV with existing reference_ids that conflict with current records, When imported, Then a preview dialog shows the count and sample ref_ids of conflicts; on Proceed, imported records overwrite existing.
- Given a new-only import (no conflicts), When processed, Then no preview dialog appears and records are inserted directly.

### Story: Export Loan Data
As a loan manager operator,
I want to export all active loan records to CSV or XLSX,
So that I have a portable copy for offline reference.

**Acceptance Criteria:**
- Given the View Tab is displayed, When the user selects Export CSV or Export XLSX, Then a file is generated containing all visible (non-Paidoff) records.

**Assumptions / Open Questions:**
- [REVIEW REQUIRED]: Should exported files include history.csv (Paidoff records) as an optional separate export, or is it always excluded?

---

<a name="r7"></a>
## BSA Requirements Breakdown: R7 — Usability and Sample Data

**Functional Requirements:**
- FR-080: Application logs shall be written to `./data/logs/app.log`.
- FR-081: A loan with no due_date shall be treated as Overdue if giving_date <= today.
- FR-082: A loan with no due_date and giving_date > today shall be treated as Pending.
- FR-083: For Extend on a loan with no due_date, new giving_date = today and new due_date = user-selected date via date-picker.
- FR-084: The prototype shall ship with an empty `loans.csv` (header row only) for the end user to populate.
- FR-085: Sample data (b1–b15, bg1–bg8, dg1–dg4) is for developer testing only and shall not be included in the production prototype distribution.

**Non-Functional Requirements:**
- NFR-015: The application shall minimize side-scrolling; all primary views shall fit within a standard 1366x768 or higher resolution viewport without horizontal scroll.
- NFR-016: The UI must be intuitive for non-technical Windows users with minimal dependency resolution at startup.

**User Stories:**

### Story: View Overdue Status for No-Due-Date Loans
As a loan manager operator,
I want loans with no due date and a past giving date to automatically show as Overdue,
So that I can track all outstanding loans regardless of whether a due date was set.

**Acceptance Criteria:**
- Given a loan with no due_date and giving_date = 2026-01-01, When the app launches on 2026-04-03, Then the record's status is recomputed to Overdue.
- Given a loan with no due_date and giving_date = 2026-05-01, When the app launches on 2026-04-03, Then the record's status is Pending.

**Assumptions / Open Questions:**
- No additional assumptions. Behavior is explicitly defined in R7 clarification notes.

---

<a name="r8"></a>
## BSA Requirements Breakdown: R8 — Prototype Stack and Storage

**Functional Requirements:**
- FR-086: The application shall be built using PySide6 as the GUI framework.
- FR-087: The application shall be startable via a `.bat` file on Windows and a `.sh` file on macOS, which: check Python version (minimum 3.10 with upgrade prompt if below), create a virtual environment, install requirements, and launch the app.
- FR-088: Storage shall use CSV files only; no database is required for the prototype.
- FR-089: All dates shall be stored in ISO 8601 format (YYYY-MM-DD).
- FR-090: No CSV file locking is required (single-user, single-session assumption).
- FR-091: Batch write optimization shall be used to avoid O(N^2) write operations on startup (referenced in R10).

**Non-Functional Requirements:**
- NFR-017: Prototype must be executable on both Windows 10/11 and macOS (latest) without requiring system-level package installation beyond Python 3.10+.
- NFR-018: Startup time from `.bat`/`.sh` invocation to application window visible shall be under 30 seconds on first run (including venv creation and pip install).

**User Stories:**

### Story: Launch the App on Windows
As an end-user on Windows,
I want to run a `.bat` file to start the Loan Manager,
So that I do not need to manually configure a Python environment.

**Acceptance Criteria:**
- Given Python 3.10+ is installed, When the `.bat` file is run, Then the virtual environment is created (if absent), requirements are installed, and the app launches.
- Given Python version < 3.10, When the `.bat` file is run, Then a message is displayed requesting the user to upgrade Python before proceeding.

**Assumptions / Open Questions:**
- [REVIEW REQUIRED]: Should the `.bat` file handle the case where Python is not installed at all (not on PATH), or is that out of scope?

---

<a name="r9"></a>
## BSA Requirements Breakdown: R9 — UI Theme

**Functional Requirements:**
- FR-092: The application shall offer at least 2 alternate color theme choices for the user to evaluate.
- FR-093: Themes shall be selectable at runtime (or at minimum documented as switchable options in prototype).

**Non-Functional Requirements:**
- NFR-019: No purple hues shall be used in any theme (per project coding style rules).
- NFR-020: All themes must maintain sufficient contrast ratios for text readability (minimum WCAG AA contrast ratio of 4.5:1 for body text).
- NFR-021: Light background with white text combinations are explicitly prohibited (per UT1 feedback).

**User Stories:**

### Story: Select UI Theme
As a loan manager operator,
I want to choose from at least 2 UI color themes,
So that I can use the application in a visually comfortable setting.

**Acceptance Criteria:**
- Given the application is running, When the user selects a different theme, Then the application's color scheme updates without requiring a restart.
- Given any theme is applied, Then text and background contrast meets WCAG AA minimums.

**Assumptions / Open Questions:**
- [REVIEW REQUIRED]: Should the selected theme persist across sessions (stored in a config file)?

---

<a name="r10"></a>
## BSA Requirements Breakdown: R10 — User Guide and Startup Scripts

**Functional Requirements:**
- FR-094: User guides for Mac OS and Windows run steps shall be created and stored under `/src/Loan Manager/user_guides/`.
- FR-095: Both `run_windows.bat` and `run_mac.sh` shall include a Python version check with a fallback message requesting upgrade if version < 3.10.
- FR-096: Startup scripts shall not silently proceed if the Python version check fails.
- FR-097: Batch write optimization shall be documented and implemented to avoid O(N^2) write operations on app startup (e.g., loading all records into memory, modifying, and writing once rather than per-record).

**Non-Functional Requirements:**
- NFR-022: User guides shall be written in plain English, step-by-step, suitable for a non-technical Windows end-user.
- NFR-023: User guides shall cover: prerequisites, launching the app, basic operations (add, view, extend, paidoff, interest calculator, export/import).

**User Stories:**

### Story: Follow Startup Instructions on Windows
As a Windows end-user,
I want a user guide that tells me exactly how to run the Loan Manager,
So that I can set it up without technical assistance.

**Acceptance Criteria:**
- Given the user guide exists, When a non-technical user follows steps, Then the app launches successfully with no unresolved dependency errors.
- Given Python < 3.10, When the `.bat` file runs, Then a clear message directs the user to upgrade Python.

**Assumptions / Open Questions:**
- No additional assumptions.

---

<a name="ut1"></a>
## BSA Requirements Breakdown: UT1 — User-Testing Defects

**Functional Requirements:**
- FR-098: The Interest Calculator filter dropdowns (Borrower Group, Borrower Name, Depositor Name, Depositor Group) shall retain their selected values after a filter is applied and not reset to "All". [Bug: filter resets on application.]
- FR-099: The View Tab color palette shall be updated to use high-contrast colors: dark or mid-tone backgrounds with clearly readable (dark or white) text, ensuring data visibility. Light background + white text combinations are prohibited.
- FR-100: The Paidoff flow shall be fully functional: selecting Paidoff from the Status dropdown shall trigger the paidoff_date prompt, archive the record to history.csv, remove from loans.csv, and generate a report in the Pending Approval queue.
- FR-101: The date-picker for giving_date and due_date on Windows shall open the calendar widget immediately on field click (single click), not require navigating a dropdown; the interaction shall be intuitive for Windows users.

**Non-Functional Requirements:**
- NFR-024: UT1 bugs (FR-098 through FR-101) are P1 defects for the prototype and must be resolved before user acceptance testing resumes.

**User Stories:**

### Story: Retain Filter Selection in Interest Calculator
As a loan manager operator,
I want the filter dropdowns in the Interest Calculator to retain my selections,
So that I do not have to re-select filters every time I interact with the tab.

**Acceptance Criteria:**
- Given Borrower Group = bg1 is selected, When the user clicks Calculate or navigates within the tab, Then the dropdown still shows bg1 selected.
- Given all 5 filters are set, When the user clicks Calculate, Then all 5 filter values remain unchanged.

### Story: Readable View Tab Color Scheme
As a loan manager operator,
I want the View Tab to display data in clearly readable colors,
So that I can review loan records without straining to see the text.

**Acceptance Criteria:**
- Given any row in the View Tab, When displayed, Then the text color and background color contrast ratio meets WCAG AA (4.5:1 minimum).
- Given the current theme, Then no white-text-on-light-background combination is present in the View Tab.

### Story: Mark Loan as Paidoff (End-to-End)
As a loan manager operator,
I want to successfully mark a loan as Paidoff by selecting it from the Status dropdown,
So that the record is archived and an interest report is queued.

**Acceptance Criteria:**
- Given an Active loan in the View Tab, When the user selects Paidoff from the QComboBox, Then a paidoff_date date-picker dialog appears.
- Given a paidoff_date is entered and confirmed, Then the record disappears from the View Tab, appears in history.csv, and a report appears in the Pending Approval Tab.

### Story: Intuitive Date Picker on Windows
As a Windows end-user,
I want the date picker for giving_date and due_date to open immediately on field click,
So that I can enter dates quickly without navigating a dropdown first.

**Acceptance Criteria:**
- Given the loan entry form on Windows, When the user clicks the giving_date or due_date field, Then the calendar date-picker opens immediately.
- Given the date-picker is open, When a date is selected, Then the field is populated with the selected date in the correct format.

**Assumptions / Open Questions:**
- [REVIEW REQUIRED]: The filter reset bug (FR-098) — is the issue in the signal/slot connection resetting the QComboBox, or is the filter state not being stored in the view model? Root cause should be determined by the developer during implementation.

---

<a name="dm"></a>
## BSA → DM Agent: Data Requirements Brief

**Business entities identified:**
- **Loan**: Core loan record (active and non-Paidoff loans)
- **LoanHistory**: Archived Paidoff loan records
- **PendingReport**: Report metadata for the Pending Approval queue
- **PendingReportRecord**: Individual loan line items within a pending report
- **LoansMeta**: High-water mark counter for reference_id generation per YYYY_MM
- **RecoveryLog**: Temporary file for crash-safety during Paidoff dual-write

---

### Entity: Loan (`loans.csv`)

| Column Name | Business Meaning | Required | Example |
|---|---|---|---|
| reference_id | Unique identifier YYYY_MM_<order> | Required | 2026_03_001 |
| borrower_name | Name of the borrower | Required | b1 |
| borrower_group | Group the borrower belongs to | Optional | bg1 |
| amount | Loan amount in INR (non-negative integer) | Required | 10000 |
| giving_date | Date loan was given (reference only, no calculation use) | Required | 2026-01-02 |
| depositor_name | Name of the depositor/lender | Optional | d1 |
| depositor_group | Group the depositor belongs to | Optional | dg1 |
| due_date | Date the loan is due (NULL if no due date) | Optional | 2026-04-02 |
| status | Computed loan status: Active, Overdue, Pending, Paidoff | Required | Active |

**Business rules:**
- status is auto-recomputed on every app launch; stored value is a last-known-state cache.
- Paidoff records must NOT exist in loans.csv; they live in history.csv only.
- amount must be a non-negative integer.
- All dates stored as ISO 8601 (YYYY-MM-DD).
- reference_id is immutable once assigned (no user edit permitted).

---

### Entity: LoanHistory (`history.csv`)

| Column Name | Business Meaning | Required | Example |
|---|---|---|---|
| reference_id | Same ref_id as the original loan | Required | 2026_03_001 |
| borrower_name | Name of borrower | Required | b1 |
| borrower_group | Group of borrower | Optional | bg1 |
| amount | Original loan amount | Required | 10000 |
| giving_date | Original giving date | Required | 2026-01-02 |
| depositor_name | Name of depositor | Optional | d1 |
| depositor_group | Group of depositor | Optional | dg1 |
| due_date | Original due date | Optional | 2026-04-02 |
| status | Always "Paidoff" | Required | Paidoff |
| paidoff_date | Date the loan was marked as paid off | Required | 2026-04-03 |

---

### Entity: PendingReport (`pending_reports.csv`)

| Column Name | Business Meaning | Required | Example |
|---|---|---|---|
| report_id | Unique report identifier RPT_YYYYMMDD_NNN | Required | RPT_20260320_001 |
| report_latest_update_dt | ISO 8601 datetime of last creation or modification | Required | 2026-03-20T14:30:00 |
| status | Report lifecycle state: Pending, Approved, Declined | Required | Pending |
| calculator_mode | Mode used: Monthly, Daily, Both | Required | Monthly |
| interest_rate | Global interest rate applied | Required | 12.0 |
| commission_rate | Global commission rate applied | Required | 2.0 |
| tds_flag | Whether TDS was applied | Required | False |

---

### Entity: PendingReportRecord (`pending_report_records.csv`)

| Column Name | Business Meaning | Required | Example |
|---|---|---|---|
| report_id | FK to pending_reports.report_id | Required | RPT_20260320_001 |
| reference_id | FK to loans.reference_id (pre-extension) | Required | 2026_03_001 |
| borrower_name | Snapshot of borrower name at report creation | Required | b1 |
| amount | Snapshot of loan amount | Required | 10000 |
| depositor_name | Snapshot of depositor name | Optional | d1 |
| giving_date | Pre-extension giving date | Required | 2026-01-02 |
| due_date | Pre-extension due date | Optional | 2026-04-02 |
| extension_period | Extension duration for this record | Required | 3 |
| extension_period_unit | Unit for extension: months or days | Required | months |
| interest_rate | Per-record interest rate (may override global) | Required | 12.0 |
| commission_rate | Per-record commission rate (may override global) | Required | 2.0 |
| tds_flag | Per-record TDS flag | Required | False |
| interest_amount | Calculated interest amount | Required | 300.00 |
| commission_amount | Calculated commission amount | Required | 50.00 |
| tds_amount | Calculated TDS amount (0 if tds_flag=False) | Required | 0.00 |
| post_extension_giving_date | Projected new giving_date after approval | Required | 2026-04-02 |
| post_extension_due_date | Projected new due_date after approval | Required | 2026-07-02 |

---

### Entity: LoansMeta (`loans_meta.csv`)

| Column Name | Business Meaning | Required | Example |
|---|---|---|---|
| year_month | YYYY_MM key for the counter | Required | 2026_03 |
| high_water_mark | Highest order number assigned for this YYYY_MM | Required | 5 |

**Business rules:**
- If all records for a YYYY_MM are deleted, the high_water_mark resets to 0 (next assignment = 001).
- Counter increment and record insert must be atomic.

---

### Entity: RecoveryLog (temporary file, `./data/recovery.log`)

| Field | Business Meaning |
|---|---|
| timestamp | ISO 8601 datetime of the recovery log write |
| operation | Operation type (e.g., "PAIDOFF") |
| reference_id | The ref_id of the record being operated on |
| record_snapshot | Full JSON/CSV row snapshot of the record before write |

**Business rules:**
- Recovery log is written BEFORE the first write in any dual-write operation.
- On app launch, if recovery.log exists, warn the user of a potential partial write.
- Recovery log is deleted on successful completion of the dual-write.

---

### Relationships

```
Loan (1) ----< PendingReportRecord (N) via reference_id
PendingReport (1) ----< PendingReportRecord (N) via report_id
Loan (0..1) ----< LoanHistory (1) via reference_id [on Paidoff]
LoansMeta (1) per YYYY_MM ---- Loan (N) [counter association, not FK]
```

---

### Business Rules Governing Data

1. A reference_id, once assigned to a loan, is never reassigned to a different borrower. It may be reused (overwritten in-place) only for the same loan on Extend or batch Approve.
2. Paidoff records are removed from loans.csv and must not appear in the View Tab or Interest Calculator filters.
3. All date values are stored exclusively in ISO 8601 format (YYYY-MM-DD). Display formatting (DD-MM-YYYY) is view-layer only.
4. The due_date field is nullable; NULL due_date has specific business logic implications for status computation and filter behavior.
5. interest_rate, commission_rate, extension_period are stored as per-record values in pending_report_records to preserve audit trail of what was approved.
6. When a report is Declined, pending_report_records rows for that report_id are deleted; pending_reports row is marked Declined.
7. When a report is Approved, loans.csv records are overwritten and pending_report_records post-extension values become the canonical record.

---

### Volume Expectations
- Max ~1500 loan records in loans.csv at any time.
- Max ~50 reports in pending_reports.csv at a time.
- pending_report_records: up to ~500 line items (50 reports x ~10 records avg).
- history.csv: unbounded over time; no in-app view required.
- loans_meta.csv: one row per active YYYY_MM, expected < 24 rows at any time.

---

<a name="uat"></a>
## UAT Plan for Prototype

**Today's Date**: 2026-04-03
**Platform**: Windows (primary), macOS (secondary/tester)

---

### UAT-R1: Loan Entry Recording

| Scenario | Steps | Expected Result |
|---|---|---|
| UAT-R1-01: Basic loan entry | Open app, fill all fields for b1 (borrower=b1, group=bg1, amount=10000, giving_date=2026-01-02, depositor=d1, group=dg1, due_date=2026-04-02), click Save | Status bar: "Loan saved successfully. Reference ID: 2026_04_001" (or next available); tab remains on entry form |
| UAT-R1-02: Entry without due date | Fill form with No Due Date checked, save | Record saved with blank due_date; status computed as Overdue (giving_date <= today) |
| UAT-R1-03: Autocomplete on Borrower Name | Type "b" in Borrower Name after b1 exists | Autocomplete dropdown shows "b1" |
| UAT-R1-04: Invalid amount | Enter amount = -100, attempt to save | Validation error shown; record not saved |
| UAT-R1-05: Date picker on Windows | Click giving_date field | Calendar widget opens immediately on single click |

---

### UAT-R2: Loan View Tab

| Scenario | Steps | Expected Result |
|---|---|---|
| UAT-R2-01: View all active records | Navigate to View Tab | All non-Paidoff records displayed in correct column order |
| UAT-R2-02: Sort by Borrower Name | Click B Name column header | Records sort alphabetically |
| UAT-R2-03: Sort by Amount | Click Amt column header | Records sort numerically |
| UAT-R2-04: Unknown depositor_group | View records b14, b15 | D Grp shows "Unknown"; cell is inline-editable |
| UAT-R2-05: Date column filter | Click due_date filter dropdown | Year list appears; selecting 2026 shows month list; selecting April shows April records only |
| UAT-R2-06: Color contrast | Review View Tab visually | All text clearly readable; no white-on-light combination |

---

### UAT-R3: Status Management

| Scenario | Steps | Expected Result |
|---|---|---|
| UAT-R3-01: Auto-status on launch | Close and reopen app | Overdue/Active/Pending statuses recomputed correctly |
| UAT-R3-02: Mark as Paidoff | Select an Active record, set Status = Paidoff | paidoff_date picker appears |
| UAT-R3-03: Confirm Paidoff | Enter paidoff_date, confirm | Record removed from View Tab; appears in history.csv; pending report created |
| UAT-R3-04: Active override of Overdue | Select an Overdue record, set Status = Active | New due_date prompt appears |
| UAT-R3-05: No-due-date Overdue | Find record with no due_date and giving_date <= today | Status = Overdue on launch |

---

### UAT-R4: Reference ID, Delete, Extend

| Scenario | Steps | Expected Result |
|---|---|---|
| UAT-R4-01: Ref_id assignment | Add new loan in current month | ref_id = YYYY_MM_<next_order> |
| UAT-R4-02: Delete loan | Select a record, click Delete | Record removed from View Tab and loans.csv; ref_id not reused |
| UAT-R4-03: Extend by months | Select a loan with due_date, Extend by 1 month | giving_date = old due_date; due_date = old due_date + 1 month; ref_id preserved |
| UAT-R4-04: Extend no-due-date loan | Select a loan with no due_date, click Extend | giving_date = today; new due_date set via date picker |
| UAT-R4-05: ref_id non-editable | Try to click/edit ref_id in View Tab | Field is read-only; no edit allowed |

---

### UAT-R5: Interest Calculator

| Scenario | Steps | Expected Result |
|---|---|---|
| UAT-R5-01: No-filter default | Open Interest Calculator with no filters | Only records with no due_date displayed |
| UAT-R5-02: Filter by Borrower Group | Select bg1 in Borrower Group dropdown | Only bg1 records with due_date shown; no-due-date records excluded |
| UAT-R5-03: Filter retention | Select bg1 filter, click Calculate | Filter dropdown still shows bg1 after Calculate |
| UAT-R5-04: Monthly calculation | Set interest_rate=12, commission_rate=2, extension_period=3, mode=Monthly, click Calculate for b1 (10000) | Interest = 300.00; Commission = 50.00 |
| UAT-R5-05: Daily calculation | Set interest_rate=12, commission_rate=2, extension_period=30, mode=Daily, click Calculate for b1 (10000) | Interest = 98.63; Commission = 16.44 |
| UAT-R5-06: TDS flag | Set TDS_flag=true, click Calculate for b1 | TDS = 0.1 * Interest displayed |
| UAT-R5-07: Generate Report | After Calculate, click Generate Report | New report appears in Pending Approval Tab with status=Pending |
| UAT-R5-08: Generate Report disabled | Open calculator without clicking Calculate | Generate Report button is greyed out/disabled |
| UAT-R5-09: Inline edit in pending report | Open pending report, change extension_period for a record | interest_amount, commission_amount recalculate immediately |
| UAT-R5-10: Approve report | Click Approve on a pending report with no conflicts | loans.csv updated with post-extension dates; report status = Approved |
| UAT-R5-11: Decline report | Click Decline on a pending report | Report removed from queue; loans.csv unchanged |
| UAT-R5-12: Conflict warning | Approve a report sharing ref_id with another pending report | Warning message displayed with Proceed/Cancel |
| UAT-R5-13: Deleted record warning | Delete a loan referenced in a pending report, then approve | Warning: "Records in this report have been deleted." |
| UAT-R5-14: Both mode | Switch to Both mode, set per-record extension_period_unit = days for one record, months for another | Each record calculated with its own formula |
| UAT-R5-15: Unknown depositor filter | Select "Unknown" in Depositor Group filter | Records b14, b15 appear in results |
| UAT-R5-16: ByMonth filter | Select April in ByMonth filter | Records with due_date in April 2026 shown |

---

### UAT-R6: Import and Export

| Scenario | Steps | Expected Result |
|---|---|---|
| UAT-R6-01: Export to CSV | Click Export CSV | File downloaded with all active records |
| UAT-R6-02: Export to XLSX | Click Export XLSX | Excel file generated with all active records |
| UAT-R6-03: Import new records | Import CSV with no ref_ids | Records auto-assigned ref_ids; no preview dialog |
| UAT-R6-04: Import with conflicts | Import CSV containing ref_id that exists | Preview dialog shows count and sample ref_ids; Proceed overwrites |
| UAT-R6-05: Date column filter hierarchy | Filter by G Dt column | Year list → Month list → Date list; only existing values shown |

---

### UAT-R7: Sample Data / Edge Cases

| Scenario | Steps | Expected Result |
|---|---|---|
| UAT-R7-01: Empty loans.csv on launch | Launch app with empty loans.csv | View Tab shows empty table; no errors |
| UAT-R7-02: Log file created | Perform operations, check ./data/logs/app.log | Log file exists and contains operation entries |

---

### UAT-R8: Startup Scripts

| Scenario | Steps | Expected Result |
|---|---|---|
| UAT-R8-01: Windows bat file (Python 3.10+) | Run run_windows.bat with Python 3.10+ | venv created, requirements installed, app launches |
| UAT-R8-02: Windows bat file (Python < 3.10) | Run run_windows.bat with Python 3.9 | Error message: "Please upgrade to Python 3.10 or higher" |
| UAT-R8-03: Mac sh file (Python 3.10+) | Run run_mac.sh with Python 3.10+ | venv created, requirements installed, app launches |
| UAT-R8-04: Mac sh file (Python < 3.10) | Run run_mac.sh with Python 3.9 | Error message requesting upgrade |

---

### UAT-R9: UI Theme

| Scenario | Steps | Expected Result |
|---|---|---|
| UAT-R9-01: Theme switch | Select an alternate theme | App color scheme updates; no restart needed |
| UAT-R9-02: Contrast check | Review all tabs under each theme | All text readable; no purple hues; no white-on-light |

---

### UAT-R10: User Guide

| Scenario | Steps | Expected Result |
|---|---|---|
| UAT-R10-01: Follow Windows guide | Non-technical user follows /src/Loan Manager/user_guides/windows guide | App launches successfully |
| UAT-R10-02: Follow Mac guide | Mac OS tester follows mac guide | App launches successfully |

---

*End of BSA Business Requirements Document — Loan Manager run_1*
