# Loan Manager

## Overview
- Plan, Design, Build and Implement a Loan Management Application.
- The app should focus on loan entries, record modification, Report generation and extract import/exports.
- Tech Stack and costs to be advised

## Requirements 

- **Requirement 1**: 
  - User should be able to record an entry for a Loan.
  - The UI should ask for `[Borrower Name, Depositor Name, Amount, Giving Date, Due Date [OPTIONAL], Borrower Group, Depositor Group[OPTIONAL]`.
    - Giving Date is just for the reference. This value does **not** account towards any calculations revolving around loan tenure.
  - For Dates, instead of manual entry a calendar widget for date-picker is needed.
  - Amount defaults to INR as currency and is a non-negative integer.
  - There be an autocomplete from existing values for future entries for fields like: `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group`
  - Entries are stored in a data folder (`./app/output/data/YYYY/`) for as `loans.csv`
  - After a user saves a new loan entry, Show a status-bar message: `Loan saved successfully. Reference ID: {ref_id}.` No need for auto-switch to View Tab.
- **Requirement 2**:
  - There should be a page where all the entries can be viewed. The Data Entries can be sorted in the View Tab based on the column values. `example`: Alphabetical sorting on `borrower_name or depositor_name or borrower_group or depositor_group`, Date sorting for `giving_date or due_date` and numerical sorting for `amount`.
    - When a loan has no Depositor Name (e.g., sample records b14, b15), there should be an "Unknown" Depositor Group value which can be in-line edited by the user
  - **View Template**: `[SNo, ref_id, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status]` 
    - `SNo` = Serial Number for the record. Not needed for persistence and will be more like a view-order counter.
    - `ref_id` = `reference_id` for the record
    - `B Name` = `borrower_name` for the record
    - `B Grp` = `borrower_group` for the record
    - `D Name` = `depositor_name` for the record
    - `D Grp` = `depositor_group` for the record
    - `G Dt` = `giving_date` for the record
    - `D Dt` = `due_date` for the record.
  - Any missing fields should show as "Unknown" value in the View tab.
- **Requirement 3**:
  - User should be able to modify any value for each entry in the View Tab by selecting the record and these values should update in storage too.
  - A Loan record's `Status` can be `[Active, Overdue, Paidoff, Pending]`, User can toggle in between these states for any record in the tab. Leverage `QComboBox` for simplicity.
    - A loan record is `Active` when `giving_date <= today < due_date`
    - A loan record is `Overdue` when `due_date <= today` 
    - When a loan record is marked `Paidoff` , ask for `paidoff_date` and make the original record as inactive record i.e. not visible in View Tab anymore. Internally, keep the record in the history with `paidoff_date` recorded. No in-app view for Paidoff history required. A separate `history.csv` file is maintained in the data directory and the `Paidoff` entries are removed from `loans.csv`. The app should create a timestamped backup copy of loans.csv before any destructive operation (Paidoff/**bulk Approve**) to reduce the risk of irrecoverable data loss. For prototype scope, this is not required but is a meaningful risk which has to be deferred for future. **Atomic Paidoff write**: i.e. recovery on partial failure. If the app crashes between two writes operation i.e. `loans.csv` and `history.csv` update, a record may be permanently lost. Crash-safety by logging the target row to a temporary recovery file before the first write is expected along with other potential risks documented.
    - A loan record is `Pending` when `giving_date > today`. All Pre-dated loan entries are marked as Pending. User can manually toggle Active → Pending, if user were to do an in-line edit of `giving_date`. User can manually toggle Overdue → Pending indirectly and the flow will be Overdue → Active (via **R4 Extend**) → Pending (via in-line `giving_date` edit). User csn manually toggle Pending → Overdue indirectly and the flow will be Pending → Active (via in-line `giving_date` edit) → Overdue (via in-line `due_date` edit). When no `due_date` given, loan with future i.e. `giving_date` > `today`, status = `Pending`.
  - The app auto-recomputes status on every app launch (overriding any manual toggle) and all manual toggles should be updating the app's state's storage.
  - A user can manually mark a loan as Active even if it is technically Overdue by date but then user is asked for the new expiration date and is similar to **R4: Extend**. Manual Active override always prompts for a new due date (same as Extend) and recompute evaluates against that new due date — never silently reverting to Overdue.
  - The allowed transition matrix (e.g., can Paidoff be toggled back to Active?) is: Paidoff loans are not visible on the View tab, user will have to manually update the .csv and import to make the record active again, otherwise no need.
- **Requirement 4**:
  - Each entry should have a `reference_id` in the following format: `YYYY_MM_<order>` where YYYY and MM are current year and month for the data entry. For example, `2026_03_001, .. 2026_12_999`. This `reference_id` is not editable by the user on View Tab but it should be visible.
    - 999 loans/month is a safe upper bound. Fallback/break avoidance logic to incorporate 1000th loan for the month should be there too i.e. after `2026_12_999` upon new entry, `2026_12_1000` should be possible.
    - Approx max loan records is 1500.
    - If all records for a given YYYY_MM are deleted, the counter resets to 001 for the next entry in that month. If the entire CSV is empty (all records deleted across all months/header row present and no data rows/file itself does not exist), each YYYY_MM counter independently resets to 001 and the next entry will have YYYY and MM values of `today`.
    - When a legacy-format imported record is auto-assigned a standard ref_id that collides with an existing record, the service should increment until a non-colliding ID is found.
    - The reference_id high-water mark counter can be embedded within loans storage directory as a separate `loans_meta.csv`.
    - For a sortable, filterable, inline-editable table of up to 1500 rows, the correct front-end choice has to be documented clearly as an architectural requirement.
  - User can also `Delete` a loan record.
    - If a loan with reference_id `2026_03_005` is deleted and a new loan is entered in March 2026, it gets  `2026_03_006` (next in sequence).
  - User can also `Extend` a loan record (re-using the `reference_id`).
    - User to provide 2 values for extension: `extension_period_unit, extension_period`
      - `extension_period_unit` options are `[months, days]`, by default `months` should be the unit.
      - Based on `extension_period` value, Update the record such that new `giving_date` = old `due_date` of the record and new `due_date` = old `due_date` + `extension_period(in extension_period_unit)`. 
- **Requirement 5**:
  - There has to be an Interest Calculator Tab which has 3 modes (a hover-dropdown-select UI to switch between the 3):
    - **Monthly** = Default Mode
    - **Daily**
    - **Both**
  - All modes need values `interest_rate` , `commission_rate`, `extension_period`, `extension_period_unit` and `TDS_flag` which will apply on all the filtered records for the Interest calculation. Only difference being in Mode = `Monthly` and `Daily`, `extension_period_unit` can be assumed accordingly but in Mode = `Both`, `extension_period_unit` and `extension_period` have to be entered on a per-record basis. 
    - `interest_rate` = Percentage Rate of Interest assigned by Depositor.
    - `commission_rate` = Percentage Commission Rate of Interest owed by Borrower on top of the rate of interest. Calculated separately.
    - `extension_period` = Time how long the entry has to be extended for. Based on `extension_period` value, Update the record such that new `giving_date` = old `due_date` of the record and new `due_date` = old `due_date` + `extension_period(in extension_period_unit)`. 
    - `TDS_flag` = Boolean value, Default = `false`. If `true`, Calculator output shall calculate TDS as well for the particular filtered records. `TDS = 0.1*Interest`
  - Each mode does Filtering of records, takes input values and apply on all filtered records, user validates and modifies record entry, if need be, for any of the inputs before calculations/report generations and generate calculations on filtered records and finally produce summary/report on the calculations. These modifications are for report generation purpose only. This report is sent to another **Pending Approval** Tab into approval queue. Each report essentially should have `[report_id, report_latest_update_dt(default=report_creation_date), status]` .
    - `report_id` has to be of the format: `RPT_YYYYMMDD_<order>` eg, RPT_20260320_001
    - `Pending Approval` Tab is where all the reports are sent. User approves the report and only then `reference_id`s are updated with the new dates and statuses on storage/View Tab i.e. Loan records are updated with new giving_date and due_date (same as R4 Extend, but batch).
    - When a loan is Extended (R4) or batch-extended via Pending Approval (R5), the `reference_id`s are reused. The .csv **Overwrites** the existing record (new giving_date replaces old due_date, new due_date replaces old due_date + extension_period(in extension_period_units)). Loss of history is okay. This is explicitly accepted for both single Extend (R4) and batch Pending Approval (R5) scenarios 
    - Use two-file normalised approach: `pending_reports.csv` (header metadata) and `pending_report_records.csv` (line items).
    - Any declined reports, are then deleted and removed from the queue. 
    - Each report will have: 
    ```
    [Report Identifier]
    [Report Latest Update Date]

    [list of records with all data columns and the calculated parameters for interest_rate, commission_rate, extension_period, extension_period_unit, TDS_flag, TDS]

    [Report Status]
    ```
    - The contents of the report are modifiable. Each parameter within the generated report should be in-line editable. Once the edit happens, Report Creation date is replaced with Report Modification date. These edits should also be saved a schema design is in works but essentially the storage can be like Matrix of data records be attached to the the matrix of calculator parameters. When a user edits a parameter (interest_rate, extension_period, etc.) in the Pending Approval Tab's record detail table, interest_amount/commission_amount/tds_amount should auto-update 
    - The Pending Approval queue should persist to .csv across restarts.
    - If two reports in the Pending Approval queue contain the same `reference_id` (e.g., a borrower appears in both a "March group" report and a borrower specific report). Warn the user when approving a report whose `reference_id`s appear in another currently-Pending report. Display: `This report shares loan records with another pending report. Approving may overwrite previous updates.` with `Proceed` and `Cancel` options. If one of them is approved, automatically silent overwrite the previous updates in both storage for loans and the other reports and their report records.
    - If a loan record is in the Pending Approval queue (as part of a report) and the user deletes that loan record from the View Tab before approving the report, when the report is approved, The user is warned: "Records in this report have been deleted.", if user wishes to ignore the warning, The approval updates only the records that still exist (skip deleted ones) otherwise user may decline the report.
    - If Report is `Declined`, the `report_id` is marked as Declined and the calculated values are deleted without any storage updates.
    - If Report is `Approved`, the `report_id` is updated and the original records(in `loans.csv`) as well is the in-line updated records on the `pending_report_records.csv` also updated with the post-extension values.
    - The Pending Approval report display the pre-extension value, only after approval are the values updated in both UI and the storage.
    - There will be preview columns for `post_extension_giving_date`, `post_extension_due_date` along with pre-extension values.
    - "Generate Report" button in the Interest Calculator Tab should be disabled until the user has clicked "Calculate".
    - When a loan has no Depositor Group (e.g., sample records b14, b15), there should be an "Unknown"/blank option appear in the dropdown so the user can explicitly filter for loans with no depositor.
  - This tab ask for 5 filter options:
    - `Borrower Group = Out of existing list of entries and exclude inactive entries i.e. PaidOff records`
    - `Borrower Name = Out of existing list of entries and exclude inactive entries i.e. PaidOff records`
    - `Depositor Name = Out of existing list of entries and exclude inactive entries i.e. PaidOff records`
    - `Depositor Group = Out of existing list of entries and exclude inactive entries i.e. PaidOff records`
    - `ByMonth = Out of 12 months for the year, show records whose due_date is in the selected month for the current calendar year only including the Overdue records`.
  - Multiple or all 5 filters can be applied at once and the inputs are set by default on all filtered records.
  - If no filter applied, then by default present all records that have no `due_date` values but when a filter is applied, the calculator totally excludes the ones without due date and only show the records which match the filter criteria.
  - Displayed record should show [`reference_id`, `borrower_name`, `amount`, `depositor_name`, `giving_date`, `due_date`]
  - **Calculations**:
    - For each Mode, different calculators apply. `giving_date` is only a reference column and is not included in any kind of time-period calculations. i.e. For a Rs 10,000 loan at 12% interest with 3-month original term + 1-month extension: Charge extension window only = Rs 100. This is a core calculation change and an **authoritative** decision, if the previous implementation defers from this. Re-write the logic and tests to adapt.
    - For Mode = `Monthly`, `extension_period_unit = months`, `Time = extension_period`,`Interest = (Amount*(interest_rate)*Time)/(12*100)`, `Commission = (Amount*(commission_rate)*Time)/(12*100)`
    - For Mode = `Daily`, `extension_period_unit = days` ,`Time = extension_period`, `Interest = (Amount*(interest_rate)*Time)/(365*100)` ,`Commission = (Amount*(commission_rate)*Time)/(365*100)`
    - For Mode = `Both`, User enters global `interest_rate`, `commission_rate`, `extension_period_unit` and `extension_period` values to be applied by default on all filtered records. There should be an orchestrator function for mode = `both` added to core calculator code file for testability.
  - Inline editable cells in the filtered table for all 4 parameters across all records.
  - For 20–50+ records, this is high data-entry burden. A "fill all rows" or "copy down" shortcut is not needed for prototype but a good feature. For now, the request for always filling default values is enough as the initial count post filtering is not supposed to cross 10 records.
  - The calculator accepts global `interest_rate` and `commission_rate` inputs applied to all filtered records. In all Modes, These values are still global and they can be overridden per-record via inline editing alongside `extension_period` and `extension_period_unit`. When the global header values change, the system overwrites all rows (including manually-edited rows).
  - Once Interest is calculated for all filtered records, summary report is created capturing `total_loan_amount, total_interest, total_commission` 

### Report Format per Borrower
```
[Borrower Name]
[Amount, Giving Date, Depositor, Extension Period, Extension Period Unit, Due Date, Interest Amount, Commission Amount, TDS]
record1
...
...
...
recordN

[Total Amount]
[Total Interest]
[Total Commission]
[Total TDS]
```

- **Requirement6**;
  - User prefers a simple UI but with accessibility features coherent to a normal spreadsheet/excel.
  - User wants excel like filtering for all columns in View Tab. Especially for date columns: Filter should present out of existing records only the available YYYY options, upon selecting a year, it should show MM options, upon selecting month. It shows filtered outputs. 
  - User wants System generated reports and outputs to be exported into .csv / .xlsx for user reference
    - All records(all years) can be stored in a single `.csv` as starting point as expected data volume is not huge i.e. all values within `loans.csv` are enough exclusive of `PaidOff` records.
  - User can Import .csv / .xlsx for historical data.
    - If imported data has no reference_id, the app auto-assigns new ones in respective format.
    - If imported data already has reference_ids (re-import scenario), the app appends/upserts the records for View Tab/Interest Calculator
    - If an imported record conflicts with an existing reference_id, then Imported data is given priority i.e. all fields of the imported record overwrite the existing record completely. There should be a preview dialog before committing destructive overwrites.
    - The preview UI should show: total rows to be inserted (new), total rows to be overwritten (existing), and the first few overwritten `reference_id`s as a sample. "Proceed" and "Cancel" options. Proposed: "N records will be overwritten: [sample ref_ids]. Proceed / Cancel."
    - If imported data has reference_ids in a format different from YYYY_MM_<order> (e.g., free-text IDs from a legacy system), The import service should check for collisions after auto-assignment. [Low relevance, user guarantees at least 80% data will follow the reference_id format]
    - The import should show a preview dialog for all the imported records. Skip preview dialog for new-only imports.
  - The full year->month->date hierarchy is required for the column filter.
  - CSV data files should reside in a fixed `./data/` subfolder.

- **Requirement7**:
  - The application should be ready to be executed and tested by User's personal windows machine without having to resolve too many dependencies. List out must have packages and their installation steps guide. User will have to validate after a prototype and prefers clean UI with minimum side-scrolling.
  - application logs can go under `./data/logs/app.log`
  - Leverage sample data:
    - Can a loan without a due_date ever become Overdue? Assume that it is overdue
    - Should Extend be disabled for loans without a due_date (since new giving_date = old due_date)? No because, for this particular scenario new `giving_date` = `today_date` and the `due_date` = new due date picked by the user via date picker.
    - Sample data is for developer-only testing, the prototype ships with an empty data file for user to provide in `.csv`

- **Requirement8**:
  - User wants a prototype. `PySide6` is good for GUI framework choice.
  - The prototype should be executable by just a simple `.bat` file for windows user which prepares the virtual env, installs requirements and starts up the app and a similar simple executable for Mac.
  - Database is not needed in the prototype. Since there is only a single user, `.csv` for history maintenance is good enough.
  - Prototype to be a good representation of all the features which are implemented.
  - Store dates as ISO 8601
  - No need for CSV file locking for concurrent sessions

- **Requirement 9**:
  - The User Interface should be modern, presentable and professional
  - Possible alternate theme choices for the user to try out amd provide preference.

- **Requirement 10**:
  - A user guide for the application run steps on both Mac OS and Windows should prepared under `/src/Loan Manager/user_guides/*`
  - Assume user has atleast python v3.10 installed, the Bash script should have a fallback message to request for upgrade. Python version check should not be absent from `run_windows.bat` and `run_mac.sh`. [Low priority]
  - Adding batch write option to avoid O(N^2) write operations on startup.

- **User-Testing Requirement 1**:
  - User was unable to see the Interest Calculator Tab/Pending Approval Tab on the App's UI
  - User demands testing of filtering logic in interest calculator tab along with calculation and the report generation.
  - User wasn't able to test out in-line edits in neither Filtered records of Calculator Tab nor for the reports generated under Pending Approval Tab 


---

## Prototype - Phase estimates
User wants to know what prototype can be built and for what features in what/how many phases to combine into a MVP


## Sample Input
```
borrower_name, borrower_group, amount, giving_date(YYYY-MM-DD), Depositor_name, depositor_group, due_date(YYYY-MM-DD)
b1, bg1, 10000, 2026-01-02, d1, dg1, 2026-04-02
b2, bg2, 10000, 2026-01-04, d2, dg1, 2026-05-04
b3, bg3, 15000, 2026-02-06, d3, dg1, 2026-05-06
b4, bg3, 20000, 2026-02-07, d4, dg2, 2026-06-07
b5, bg4, 20000, 2026-02-08, d5, dg2, 2026-06-08
b6, bg4, 15000, 2026-02-08, d6, dg3, 2026-07-08
b7, bg5, 15000, 2026-02-15, d7, dg3, 2026-07-15
b8, bg5, 20000, 2026-02-18, d8, dg3, 2026-06-18
b9, bg1, 20000, 2026-02-20, d9, dg3, 2026-06-20
b10, bg6, 10000, 2026-02-25, d10, dg1, 2026-05-25
b11, bg6, 15000, 2026-02-28, d11, dg2, 2026-05-28
b12, bg7, 15000, 2026-03-02, d12, dg4, 2026-07-02
b13, bg7, 10000, 2026-03-05, d13, dg4, 2026-07-05
b14, bg8, 15000, 2026-03-10, d14, , 2026-07-10
b15, bg8, 20000, 2026-03-14, d15, , 2026-07-14
```

## Priority
R5 > R4 > R1 > R2 > R3 > R6 > R8 > R7 > R10 > R9

## Usage Scope
- Single-System End-user (Windows)
- Single-System Human-in-the-loop Product i.e. Loan Manager Tester (Mac OS)
  - Does the Mac user need to run the full application (requires cross-platform packaging + shared CSV via network/cloud)? .csv can be shared via git and application should run on both Windows and Mac OS
  - Mac user bridges the gap for the end-user's git management.
