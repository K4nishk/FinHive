# Loan Manager — Windows User Guide

## Prerequisites

- Windows 10 or later
- Python 3.10 or higher

### Check your Python version
Open Command Prompt and run:
```
python --version
```

If the output shows Python 3.9 or lower (or Python is not found), download a newer version from [python.org](https://www.python.org/downloads/).

**Important during Python installation**: check the box **"Add Python to PATH"** before clicking Install.

---

## First Run

1. Open File Explorer and navigate to the application folder
2. Double-click **`run_windows.bat`**

Or from Command Prompt:
```
cd C:\path\to\LoanManager
run_windows.bat
```

The script will:
- Verify Python 3.10+
- Create a virtual environment (`.venv\`)
- Install all required packages
- Launch the application

A window will appear asking "Press any key to continue" when the app closes — this is normal.

Subsequent runs: double-click `run_windows.bat` again — the virtual environment is reused.

---

## Application Overview

The application has 5 tabs:

| Tab | Purpose |
|---|---|
| Entry | Add new loan records |
| View | Browse, sort, filter, and edit all loans |
| Calculator | Calculate interest and generate reports |
| Pending Approval | Review and approve/decline interest reports |
| Settings | Theme, colours, import/export |

---

## Entry Tab

1. Fill in borrower and depositor details (names autocomplete from existing records)
2. Enter the loan amount (INR, whole numbers only)
3. Select the Giving Date — press Tab into the date field or double-click to open the calendar
4. Optionally enter Due Period (months) — Due Date is calculated automatically
5. Or enter Due Date directly using the calendar
6. Click **Save Loan**
7. The status bar at the bottom shows: `Loan saved successfully. Reference ID: YYYY_MM_NNN`

---

## View Tab

- Click any column header to sort ascending/descending
- Click the filter arrow (▼) next to a column name to filter records
  - Date columns: expand Year → Month hierarchy
  - Text columns: check/uncheck specific values
- Double-click a cell to edit inline
  - Date cells: calendar picker opens automatically
  - Status cells: a dropdown appears with colour-coded options
- **Right-click** a row for additional options:
  - **Extend** — set a new due date for the loan
  - **Mark Paidoff** — generate a paidoff report (sent to Pending Approval)
  - **Delete** — permanently remove the record

### Status Colours (default dark theme)
- Active — dark green
- Overdue — dark red
- Pending — dark amber
- Paidoff — dark blue-grey

---

## Calculator Tab

1. Select **Mode**: Monthly, Daily, or Both
2. Apply optional filters (Borrower Group, Borrower Name, Depositor Name, Depositor Group, By Month)
3. Enter global parameters:
   - Interest Rate (%)
   - Commission Rate (%)
   - Extension Period and Unit (months or days)
   - TDS checkbox (applies 10% TDS deduction on interest)
4. Click **Calculate** — a results window opens showing all matching loans with calculated amounts
5. Edit any per-record values in the results table if needed — totals update automatically
6. Click **Generate Report** — the report is sent to the Pending Approval tab

---

## Pending Approval Tab

Each generated report appears here for review before any loan records are changed.

1. Select a report from the list at the top
2. Review the record details in the bottom panel
3. Edit parameters inline if needed — amounts recalculate on the fly
4. Click **Approve** to commit changes to loan records
   - If the report shares loans with another pending report: a warning appears — choose Proceed or Cancel
   - If loans in the report were deleted before approval: choose Ignore (skip those) or Decline
5. Click **Decline** to discard the report — loan records are unchanged
6. Click **Print/PDF** to print via the Windows print dialog (use "Microsoft Print to PDF" printer to save as PDF)

---

## Settings Tab

- **Theme**: switch between Dark and Light and click Apply
- **Status Colours**: click Pick next to any status to choose a custom colour
- **Import Legacy Data**: load a CSV or XLSX file from a previous version or another machine
  - A preview shows new records and records that will be overwritten
- **Export All Loans**: save to CSV or XLSX in `data\exports\`

---

## Data Files

All data is stored in the `data\` folder:

```
data\
  loans.db          ← All loan data (SQLite database)
  logs\app.log      ← Application log
  backups\          ← Automatic backups before bulk operations
  exports\          ← Your exported files
  settings.json     ← Theme and colour preferences
```

Do not delete `loans.db` — it contains all your loan records.

---

## Sharing Data with Mac Tester

1. In Settings → Export All Loans → CSV
2. Commit the CSV to the shared git repository
3. The Mac user pulls and imports via Settings → Import Legacy Data

---

## Troubleshooting

### "Python is not recognised as an internal or external command"
Python is not on the system PATH. Re-install Python from python.org and check **"Add Python to PATH"** during installation, or add it manually in System Settings → Environment Variables.

### "Python 3.10 or higher is required" message
Your installed Python is too old. Download Python 3.10+ from python.org.

### App window opens then closes immediately
Run `run_windows.bat` from Command Prompt so you can see the error message:
```
cd C:\path\to\LoanManager
run_windows.bat
```

### "approval_recovery.tmp" warning on startup
A report approval was interrupted (e.g. power cut). Check Pending Approval — verify or re-process any pending reports, and confirm that the relevant loan records are correct in the View tab.

### Calendar picker does not open
Click directly on the date field and press Tab, or double-click the date value in the cell.

### Data appears wrong after import
Imported records overwrite existing records with the same reference ID. A timestamped backup is saved in `data\backups\` before any bulk operation — restore from there if needed.
