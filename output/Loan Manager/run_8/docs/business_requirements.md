# Business Requirements — Loan Manager

## Overview

A single-user desktop loan management application for tracking personal/informal loans between borrowers and depositors. Built for Windows (primary) and macOS (secondary/testing). Storage is file-based CSV. No concurrent sessions.

---

## BR-01 — Loan Entry

**Priority**: MUST

### Fields
| Field | Type | Required | Notes |
|---|---|---|---|
| borrower_name | string | MUST | Normalize to lowercase at write |
| borrower_group | string | MUST | Normalize to lowercase at write; autocomplete from history |
| depositor_name | string | MUST | Normalize to lowercase at write |
| depositor_group | string | OPTIONAL | Normalize to lowercase at write; autocomplete from history |
| amount | non-negative integer | MUST | Defaults to INR currency |
| giving_date | date (ISO 8601) | MUST | Reference only — not used in time calculations |
| due_period | integer (months) | OPTIONAL | Shown before due_date; auto-calculates due_date |
| due_date | date (ISO 8601) | OPTIONAL | Default = "Unknown"; auto-filled when due_period entered |

### Rules
- `due_date = giving_date + due_period (months)` when due_period is entered
- `due_period` field appears before `due_date` in the form
- Date fields use a calendar widget (date-picker) triggered on Tab into field or double-click on value
- Autocomplete on `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group` from existing records
- When `borrower_name` or `depositor_name` matches an existing record, auto-fill the corresponding group field
- After save: display status bar message `Loan saved successfully. Reference ID: {ref_id}.`
- No auto-switch to View Tab after save
- Storage: `./data/loans.csv`

---

## BR-02 — Loan View

**Priority**: MUST

### View Columns
`[SNo, ref_id, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status]`

- SNo = display-order serial number (not persisted)
- Missing values display as "Unknown"
- All columns are sortable: alphabetical (name/group), date (dates), numeric (amount)
- Excel-like column filtering for all columns
- Date column filter: hierarchical YYYY → MM → records
- Inline editing for all fields except `ref_id`
- Date field inline edits trigger date-picker dialog
- Status shown via QComboBox for manual override

### Filter Behaviour
- Date columns: show available YYYY values from existing records; on year select show MM options; on month select show filtered rows

---

## BR-03 — Status Engine

**Priority**: MUST

### States
| Status | Colour | Condition |
|---|---|---|
| Active | #025c33 (bold white) | `giving_date <= today < due_date` |
| Overdue | #6b0307 (bold white) | `due_date <= today` |
| Pending | #804001 (bold white) | `giving_date > today` OR no due_date with future giving_date |
| Paidoff | #022a52 (bold white) | Manually triggered via right-click → Mark Paidoff |

### Rules
- Status auto-recomputed on every app launch (overrides manual toggle in storage)
- All manual toggles persisted to storage
- Loan with no `due_date` and past giving_date → treated as Overdue
- Loan with no `due_date` and future giving_date → Pending
- The colors should be configurable, these are just recommendations. Have a separate color-palette also in place.

### Transition Rules
- Active → Overdue (auto, date-based)
- Overdue → Active (via Extend R4, prompts new due_date)
- Active → Pending (inline edit giving_date to future date)
- Overdue → Pending (via Extend then inline edit giving_date)
- Any → Paidoff (right-click Mark Paidoff, only if due_date exists, only if no pending report)
- Paidoff loans: removed from View Tab; moved to `history.csv`; not reversible in-app

### Paidoff Flow
1. Right-click → Mark Paidoff
2. Dialog: `paidoff_date`, `interest_rate`, `commission_rate`, `tds_flag`
3. Calculation report generated (Daily mode: `extension_period = paidoff_date - due_date`)
4. Report sent to Pending Approval queue
5. On Approve: loan moved to `history.csv`, removed from `loans.csv`, marked inactive
6. On Decline: no changes; loan remains active in view
7. Warning displayed: "This report was generated for a Paidoff loan. The loan will be moved to history. No extension will be applied."
8. Disable "Mark Paidoff" if a pending Paidoff report already exists for the loan

### Backup
- Create timestamped backup of `loans.csv` before any destructive operation (Paidoff / bulk Approve)
- Crash-safety: log target row to `approval_recovery.tmp` before first write
- On startup: if `approval_recovery.tmp` exists, display non-blocking warning: "An approval was in progress when the application last closed. Please check the Pending Approval queue and verify loan records."

---

## BR-04 — Reference IDs, Delete, Extend

**Priority**: MUST

### Reference ID Format
`YYYY_MM_<order>` e.g. `2026_03_001`

- YYYY, MM = date of entry creation (today)
- Order is sequential, zero-padded to 3 digits
- Supports >999: `2026_12_1000` etc.
- Counter is per YYYY_MM
- If all records for a YYYY_MM are deleted → counter resets to 001 for next entry in that month
- If entire CSV is empty → all counters reset; next entry uses today's YYYY_MM with 001
- On collision (legacy import): increment until non-colliding ID found
- Counter stored in `./data/loans_meta.csv`
- `ref_id` is read-only in View Tab

### Delete
- User can delete any loan record
- Deleted loan's order number is not reused (next is always high-water + 1)

### Extend (Single Record)
- Right-click or action → Extend
- User provides: `extension_period_unit` [months | days] (default: months), `extension_period`
- New `giving_date` = old `due_date`
- New `due_date` = old `due_date` + extension_period (in extension_period_unit)
- Special case: loan with no due_date → `giving_date` = today, `due_date` = user-picked via date picker
- `ref_id` is reused (record overwritten)
- History loss is explicitly accepted

---

## BR-05 — Interest Calculator

**Priority**: MUST

### Modes
| Mode | extension_period_unit | Formula |
|---|---|---|
| Monthly (default) | months | Interest = (Amount × interest_rate × Time) / (1200) |
| Daily | days | Interest = (Amount × interest_rate × Time) / (36500) |
| Both | per-record | Uses record-level unit |

Commission uses same formula as Interest but with `commission_rate`.

`giving_date` is NOT used in any time calculations. Only the extension_period counts.

### Inputs (global, overridable per-record)
- `interest_rate` — percentage
- `commission_rate` — percentage
- `extension_period` — number
- `extension_period_unit` — months | days (per-record in Both mode)
- `TDS_flag` — boolean, default false; `TDS = 0.1 × Interest`
- `CHQ_Amt = Interest - TDS` (or `0.9 × Interest`)

### Filters (up to 5, combinable)
- Borrower Group — from existing active records
- Borrower Name — from existing active records
- Depositor Name — from existing active records
- Depositor Group — from existing active records (includes "Unknown"/blank option)
- ByMonth — records whose due_date is in selected month of current calendar year + Overdue records

### Filter Logic
- No filter applied: show all records with no due_date
- Any filter applied: exclude records without due_date; show only matching records

### Workflow
1. Select mode
2. Apply filters
3. Enter global input values
4. Click Calculate → dialog box with filtered records + calculated values
5. Inline edit any per-record value; calculations auto-update
6. "Generate Report" button (disabled until Calculate clicked)
7. Generate Report → sent to Pending Approval Tab

### Report Format per Borrower
```
[Borrower Name]
[Amount, Giving Date, Depositor, Extension Period, Extension Period Unit, Due Date, Interest Amount, TDS, CHQ_Amt, Commission Amount]
record1...recordN

[Total Amount]
[Total Interest]
[Total Commission]
[Total TDS]
```

### Both Mode
- Orchestrator function in core calculator module (for testability)
- Global defaults; per-record override

### Summary
After calculation: `total_loan_amount`, `total_interest`, `total_commission`

---

## BR-06 — Pending Approval Tab

**Priority**: MUST

### Report Metadata
- `report_id`: `RPT_YYYYMMDD_<order>` e.g. `RPT_20260320_001`
- `report_latest_update_dt`: defaults to creation date; updated on edit
- `status`: Pending | Approved | Declined

### Storage
- `pending_reports.csv` — header metadata
- `pending_report_records.csv` — line items

### Report Contents
- Pre-extension values (giving_date, due_date)
- Preview columns: `post_extension_giving_date`, `post_extension_due_date`
- Inline editable: `interest_rate`, `commission_rate`, `extension_period`, `extension_period_unit`, `tds_flag`
- Auto-recalculate `interest_amount`, `commission_amount`, `tds_amount` on edit

### Approval Rules
- Approve: update `loans.csv` with new giving_date/due_date; update `pending_report_records.csv` with post-extension values
- Decline: delete report + records; no storage updates
- Duplicate ref_id across pending reports: warn "This report shares loan records with another pending report. Approving may overwrite previous updates." → Proceed / Cancel
- On Proceed: silently overwrite earlier updates in both loans.csv and other pending report records
- If a loan was deleted before report approval: warn "Records in this report have been deleted." → Ignore (skip deleted) / Decline
- Approved reports: downloadable as PDF / printable

### Persistence
- Pending Approval queue persists across restarts

---

## BR-07 — Import / Export

**Priority**: SHOULD

### Export
- All records exportable as `.csv` / `.xlsx`
- System-generated reports exportable

### Import
- Accept `.csv` / `.xlsx`
- No ref_id in imported data → auto-assign in YYYY_MM_<order> format
- Existing ref_ids in imported data → upsert (append or overwrite)
- Conflict (same ref_id): imported data wins; preview before commit
- Preview dialog shows: total new rows, total overwritten rows, sample overwritten ref_ids
- Skip preview for new-only imports
- Legacy format IDs (non-standard): assign new ref_id; check collisions

---

## BR-08 — Launcher + Environment

**Priority**: MUST

### Deliverables
- `run_windows.bat`: prepare venv, install requirements, start app
- `run_mac.sh`: prepare venv, install requirements, start app
- Python version check in both launchers; require >= 3.10; fallback message if not met

### Storage Layout
```
./data/
  loans.csv
  loans_meta.csv
  history.csv
  pending_reports.csv
  pending_report_records.csv
  logs/
    app.log
```

### Startup
- Sample data loaded for demo
- Production ships with empty data files

---

## BR-09 — UI / UX

**Priority**: SHOULD

### Requirements
- Modern, professional, clean UI
- Minimum side-scrolling
- Keyboard-first navigation
- Spreadsheet/Excel-like UX
- Accessibility features
- Multiple theme options (user to select preference)
- Date-picker triggered on Tab into date field or double-click

### Bug Fix (MUST)
- Fix `AttributeError: 'ClickableDateEdit' object has no attribute 'showCalendarWidget'`
- Date picker must open correctly on Tab or double-click in all date fields across Entry and View tabs

---

## BR-10 — User Guides

**Priority**: SHOULD

- Windows guide: `user_guides/windows_guide.md`
- macOS guide: `user_guides/mac_guide.md`
- Covers: installation, first run, feature walkthrough
