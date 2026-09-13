# Backlog — Loan Manager

## Classification: MUST / SHOULD / NICE

---

### MUST — Core MVP

#### BL-01 Loan Entry Form
- [ ] Fields: borrower_name, borrower_group, depositor_name, depositor_group, amount, giving_date, due_period, due_date
- [ ] Normalize string fields to lowercase at write time
- [ ] due_period auto-calculates due_date
- [ ] Calendar widget on Tab or double-click for date fields
- [ ] Autocomplete for name/group fields from existing records
- [ ] Auto-fill group when name matches existing record
- [ ] Status bar message after save with ref_id

#### BL-02 Reference ID System
- [ ] Format: `YYYY_MM_<order>` (3-digit zero-padded, overflow to 4+ digits)
- [ ] High-water counter per YYYY_MM in `loans_meta.csv`
- [ ] Counter resets if all records for YYYY_MM deleted
- [ ] Counter resets if CSV empty
- [ ] Collision detection and increment for legacy imports
- [ ] ref_id read-only in View Tab

#### BL-03 Loan View Table
- [ ] Columns: SNo, ref_id, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status
- [ ] Missing values display as "Unknown"
- [ ] Sortable by all columns (alpha, date, numeric)
- [ ] Inline editing for all non-ref_id fields
- [ ] Date field inline edit triggers date-picker
- [ ] Status column via QComboBox

#### BL-04 Status Engine
- [ ] Auto-compute on every app launch
- [ ] Active / Overdue / Pending / Paidoff logic
- [ ] Status colour coding per spec
- [ ] Manual override persisted to storage
- [ ] Active override → prompt for new due_date (Extend flow)
- [ ] No-due-date loan: Overdue if past, Pending if future

#### BL-05 Delete Loan
- [ ] Delete record from View Tab
- [ ] Remove from loans.csv
- [ ] Counter does not reuse deleted order number

#### BL-06 Extend Loan
- [ ] Extend dialog: extension_period_unit, extension_period
- [ ] Default unit: months
- [ ] New giving_date = old due_date (or today if no due_date)
- [ ] New due_date = old due_date + extension (or user-picked if no due_date)
- [ ] Overwrite record; reuse ref_id
- [ ] History loss accepted

#### BL-07 Mark Paidoff
- [ ] Right-click context menu on loan record
- [ ] Dialog: paidoff_date, interest_rate, commission_rate, tds_flag
- [ ] Calculate using Daily mode (extension_period = paidoff_date - due_date)
- [ ] Send report to Pending Approval queue
- [ ] Disable if no due_date or pending Paidoff report exists
- [ ] Display warning message
- [ ] On Approve: move to history.csv, remove from loans.csv
- [ ] On Decline: no changes
- [ ] Write to approval_recovery.tmp before each CSV write

#### BL-08 Interest Calculator Tab
- [ ] Mode selector: Monthly | Daily | Both (hover-dropdown)
- [ ] Filters: Borrower Group, Borrower Name, Depositor Name, Depositor Group, ByMonth
- [ ] Multiple filters combinable
- [ ] Global inputs: interest_rate, commission_rate, extension_period, extension_period_unit, tds_flag
- [ ] Filter logic: no filter → records with no due_date; any filter → excludes no-due-date records
- [ ] Calculate button → dialog with records + calculations
- [ ] Inline editing per-record; auto-recalculate on edit
- [ ] Global input change → overwrites all rows (including manually edited)
- [ ] Generate Report button (disabled until Calculate clicked)
- [ ] Summary: total_loan_amount, total_interest, total_commission
- [ ] Monthly formula: (Amount × rate × Time) / 1200
- [ ] Daily formula: (Amount × rate × Time) / 36500
- [ ] TDS = 0.1 × Interest; CHQ_Amt = Interest - TDS
- [ ] Both mode orchestrator function in core calculator
- [ ] giving_date NOT used in calculations (breaking change from previous)

#### BL-09 Pending Approval Tab
- [ ] Report list view with report_id, report_latest_update_dt, status
- [ ] Pre-extension values shown; post-extension preview columns
- [ ] Inline edit: interest_rate, commission_rate, extension_period, extension_period_unit, tds_flag
- [ ] Auto-recalculate on inline edit
- [ ] Approve: update loans.csv and pending_report_records.csv
- [ ] Decline: delete report + records; no loan changes
- [ ] Duplicate ref_id warning on approve
- [ ] Deleted loan warning on approve
- [ ] Persist queue across restarts
- [ ] Timestamped backup of loans.csv before bulk Approve
- [ ] Approved report: printable via system print dialog

#### BL-10 Crash Safety
- [ ] Write to approval_recovery.tmp before first CSV write in Paidoff flow
- [ ] On startup: non-blocking warning if approval_recovery.tmp exists

#### BL-11 Date Picker Bug Fix
- [ ] Fix `showCalendarWidget` AttributeError in ClickableDateEdit
- [ ] Use calendarPopup or separate QCalendarWidget dialog
- [ ] Works on Tab and double-click in both Entry Tab and View Tab

#### BL-12 Launchers
- [ ] run_windows.bat: Python version check, venv setup, install requirements, launch
- [ ] run_mac.sh: Python version check, venv setup, install requirements, launch
- [ ] Fallback message if Python < 3.10

#### BL-13 Logging
- [ ] App logs to `./data/logs/app.log`
- [ ] Structured log entries for key operations

---

### SHOULD — High Value

#### BL-14 Excel-Like Column Filter
- [ ] Per-column filter dropdowns in View Tab
- [ ] Date columns: hierarchical YYYY → MM → records
- [ ] Text columns: checkbox-style value selection

#### BL-15 Import
- [ ] Accept CSV / XLSX
- [ ] Auto-assign ref_id if missing
- [ ] Upsert on existing ref_id
- [ ] Conflict: imported data wins; preview dialog
- [ ] Preview: new count, overwrite count, sample ref_ids
- [ ] Skip preview for new-only imports

#### BL-16 Export
- [ ] Export all loans.csv as CSV / XLSX
- [ ] Export approved reports as CSV / XLSX

#### BL-17 Modern UI / Themes
- [ ] Minimum side-scrolling layout
- [ ] At least 2 theme choices
- [ ] Professional, clean appearance

#### BL-18 Depositor Group Unknown Handling
- [ ] Records with no depositor_group display "Unknown" in View Tab
- [ ] "Unknown"/blank option in Depositor Group filter dropdown

---

### NICE — Future Enhancement

#### BL-19 Fill-All-Rows Shortcut in Calculator
- [ ] "Copy down" for calculator input values across all filtered records

#### BL-20 Styled PDF Export
- [ ] Generate formatted PDF reports (reportlab/weasyprint)

#### BL-21 Atomic CSV Writes / Full Crash Recovery
- [ ] Full transactional rollback on crash during dual-write operations

#### BL-22 Batch Write Optimization
- [ ] Avoid O(N²) write operations on startup

#### BL-23 User Guides
- [ ] `user_guides/windows_guide.md`
- [ ] `user_guides/mac_guide.md`

#### BL-24 Database Compatibility
- [ ] Introduce SQLite
- [ ] Migrate the .csv file data and system read/write operations to Database
---

## Stage Mapping

| Stage | Backlog Items |
|---|---|
| Stage 3 — Scaffold | BL-02, BL-12, BL-13, BL-10 (structure only) |
| Stage 4 — Domain | BL-01, BL-02, BL-04, BL-05, BL-06, BL-07, BL-08, BL-09, BL-10 |
| Stage 5 — UI | BL-01, BL-03, BL-08, BL-09, BL-11, BL-14, BL-17, BL-18 |
| Stage 6 — Finalize | BL-12, BL-13, BL-15, BL-16, BL-23, BL-24 |
