# Loan Manager — macOS User Guide

## Prerequisites

- macOS 10.15 (Catalina) or later
- Python 3.10 or higher

### Check your Python version
```bash
python3 --version
```

If the output shows Python 3.9 or lower, download a newer version from [python.org](https://www.python.org/downloads/).

---

## First Run

1. Open Terminal
2. Navigate to the application folder:
   ```bash
   cd /path/to/LoanManager
   ```
3. Run the launcher:
   ```bash
   bash run_mac.sh
   ```

The script will:
- Verify Python 3.10+
- Create a virtual environment (`.venv/`)
- Install all required packages
- Launch the application

Subsequent runs: just `bash run_mac.sh` again — the virtual environment is reused.

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
3. Select the Giving Date using the calendar picker (press Tab into the field or double-click)
4. Optionally enter Due Period (months) — Due Date is calculated automatically
5. Or enter Due Date directly
6. Click **Save Loan**
7. The status bar shows: `Loan saved successfully. Reference ID: YYYY_MM_NNN`

---

## View Tab

- Click any column header to sort
- Click the filter arrow (▼) next to a column name to filter
  - Date columns: expand Year → Month to filter by period
  - Text columns: check/uncheck values to filter
- Double-click a cell to edit inline
  - Date cells: calendar picker opens automatically
  - Status cells: dropdown with colour-coded options
- **Right-click** a row for options:
  - **Extend** — extend the loan's due date
  - **Mark Paidoff** — generate a paidoff report (sends to Pending Approval)
  - **Delete** — remove the record permanently

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
   - Extension Period + Unit (months or days)
   - TDS checkbox (applies 10% TDS deduction)
4. Click **Calculate** — a results dialog opens
5. In the results dialog, edit any per-record parameters if needed (calculations update automatically)
6. Click **Generate Report** — the report is sent to Pending Approval

---

## Pending Approval Tab

Each generated report appears here.

1. Select a report from the list
2. Review the record details in the bottom panel
3. Edit any parameters inline — amounts recalculate automatically
4. Click **Approve** to apply the changes to loan records
   - If the report shares loans with another pending report: a warning is shown — choose Proceed or Cancel
   - If loans in the report were deleted: choose Ignore (skip deleted) or Decline
5. Click **Decline** to discard the report without any changes
6. Click **Print/PDF** to print the report via the system print dialog

---

## Settings Tab

- **Theme**: switch between Dark and Light
- **Status Colours**: click Pick to customise each status colour
- **Import Legacy Data**: import a CSV or XLSX file
  - A preview shows how many records are new and how many will be overwritten
  - Imported data takes priority over existing records with the same reference ID
- **Export All Loans**: save all active loans to CSV or XLSX

---

## Data Files

All data is stored in the `data/` folder next to the application:

```
data/
  loans.db              ← All loan data (SQLite)
  logs/app.log          ← Application log
  backups/              ← Auto-backups before destructive operations
  exports/              ← Exported CSV/XLSX files
  settings.json         ← Your preferences
```

Do not delete `loans.db` unless you want to start fresh.

---

## Sharing Data with Windows User

1. In Settings → Export All Loans → CSV
2. Commit the exported CSV to git
3. The Windows user imports it via Settings → Import Legacy Data

---

## Troubleshooting

### App doesn't start
```bash
python3 --version  # Must be 3.10+
bash run_mac.sh    # Re-run to reinstall packages
```

### "approval_recovery.tmp" warning on startup
A previous approval was interrupted. Check the Pending Approval queue — approve or decline any pending reports, then verify that the affected loan records are correct.

### Calendar picker doesn't open
Click directly on the date field and press Tab, or double-click the date value.

### Data looks incorrect after import
Imported records with the same reference ID overwrite existing records. To restore, use the backup in `data/backups/`.
