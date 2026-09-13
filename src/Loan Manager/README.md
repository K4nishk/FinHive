# Loan Manager — MVP1

A single-user desktop application for managing informal personal loans. Built with Python + PySide6 + SQLite.

---

## Quick Start

### macOS
```bash
bash run_mac.sh
```

### Windows
```
run_windows.bat
```

Both scripts handle virtual environment creation, dependency installation, and app launch automatically. Python 3.10 or higher is required.

---

## Features

- **Loan Entry** — Record loans with borrower/depositor details, amounts, and dates. Autocomplete from history.
- **Loan View** — Sortable, filterable table with inline editing. Status colour coding.
- **Status Engine** — Auto-computed on every launch: Active, Overdue, Pending, Paidoff.
- **Interest Calculator** — Monthly, Daily, and Both modes. Global and per-record parameter overrides.
- **Pending Approval** — Batch interest reports reviewed and approved before loan records are updated.
- **Import / Export** — CSV and XLSX support. Legacy data migration from previous CSV files.
- **Themes** — Dark and light themes; configurable status colours.

---

## Requirements

- Python 3.10 or higher
- Internet connection (first run only, to install packages)

All Python dependencies are installed automatically by the launcher scripts.

---

## Data Storage

All data is stored locally in `./data/`:

```
data/
  loans.db              ← SQLite database (primary store)
  logs/app.log          ← Application log
  backups/              ← Timestamped backups before destructive operations
  exports/              ← CSV/XLSX exports
  settings.json         ← Theme and colour preferences
  approval_recovery.tmp ← Crash recovery marker (auto-deleted after clean approval)
```

---

## Reference ID Format

Each loan is assigned a unique reference ID: `YYYY_MM_<order>`

Example: `2026_03_001` — first loan entered in March 2026.

---

## Interest Calculation

Calculations use the **extension period only** — the original loan term is not included.

- **Monthly**: `Interest = (Amount × Rate × Months) / 1200`
- **Daily**: `Interest = (Amount × Rate × Days) / 36500`
- **TDS**: `0.1 × Interest` (when enabled)
- **CHQ Amount**: `Interest − TDS`

---

## Crash Recovery

If the application crashes during a report approval, an `approval_recovery.tmp` file is written. On next launch, a non-blocking warning is shown. Check the Pending Approval queue and verify loan records before proceeding.

---

## Cross-Platform Data Sharing

The Windows end-user and macOS tester share data via git. Export loans to CSV, commit, and import on the other machine using Settings → Import Legacy Data.

---

## User Guides

- [macOS Guide](user_guides/mac_guide.md)
- [Windows Guide](user_guides/windows_guide.md)

---

## Development

```bash
# Run tests
cd "src/Loan Manager"
python -m pytest tests/ -v --cov=loan_manager

# Run application
python -m loan_manager.main
```

Coverage target: 85% (current: 89%)
