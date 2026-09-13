# Migration Strategy — Loan Manager MVP1

## Overview

MVP1 introduces SQLite as the primary data store. The old prototype used flat CSV files. This document covers:
1. Alembic schema migration setup
2. CSV-to-SQLite one-time data migration (BL-24)
3. Ongoing CSV export for compatibility

---

## 1. Alembic Setup

### Folder Layout
```
src/loan_manager/infrastructure/migrations/
  alembic.ini
  env.py
  script.py.mako
  versions/
    001_initial_schema.py
```

### alembic.ini (key setting)
```ini
[alembic]
script_location = src/loan_manager/infrastructure/migrations
sqlalchemy.url = sqlite:///./data/loans.db
```

### env.py
- Import all SQLAlchemy models so Alembic can detect schema changes
- Use `target_metadata = Base.metadata` for autogenerate support

### Initial Migration (001_initial_schema.py)
Creates all 6 tables:
- `loans`
- `loan_meta`
- `loan_history`
- `reports`
- `report_records`
- `report_meta`

### Running Migrations
```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply all pending migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

Migrations are run automatically on app startup via `DatabaseSession.initialize()`.

---

## 2. CSV-to-SQLite Data Migration (BL-24)

### When
- On first launch of MVP1 if `./data/loans.db` does not exist but `./data/loans.csv` exists
- User can also trigger manually from Settings Tab → "Import Legacy Data"

### Migration Script
`src/loan_manager/infrastructure/migrations/csv_to_sqlite.py`

```
Steps:
1. Detect ./data/loans.csv existence
2. Run Alembic migrations to create schema
3. Parse loans.csv using CsvImportService
4. Assign reference_ids (auto-assign if missing; collision detection)
5. Compute status for each record using StatusEngine
6. Bulk insert into loans table via UoW
7. Populate loan_meta counters from imported reference_ids
8. If pending_reports.csv + pending_report_records.csv exist:
   a. Parse and insert into reports + report_records tables
9. If history.csv exists:
   a. Parse and insert into loan_history table
10. Write migration completion log entry
11. Rename original CSVs to *.bak (do not delete)
```

### Collision Handling
- If imported ref_id already exists in DB → imported data wins (overwrite)
- Show preview dialog before commit (ImportPreviewDialog)

### Rollback
- If migration fails midway: rollback SQLAlchemy transaction
- Original CSV files are not modified until migration succeeds

---

## 3. Ongoing CSV Compatibility

Even after SQLite migration, CSV remains available:

### Export (always available)
- **Export All Loans**: writes `./data/exports/loans_export_YYYYMMDD.csv`
- **Export Report**: writes `./data/exports/RPT_<report_id>.csv`
- Cross-platform data sharing via git uses these exports

### Import (for new data or re-import)
- User imports CSV/XLSX via Settings Tab → Import
- Goes through `CsvImportService` → `ImportPreviewDTO` → `ImportLoans` use case
- Same collision detection as BL-24

---

## 4. Startup Sequence

```
main.py
  1. Initialize logging (./data/logs/app.log)
  2. Check for approval_recovery.tmp → warn if exists
  3. DatabaseSession.initialize()
     a. Create ./data/ directory if missing
     b. Run alembic upgrade head (idempotent)
     c. Check for legacy CSV → offer migration if found
  4. RecomputeAllStatuses use case (updates all loan statuses)
  5. Launch MainWindow
```

---

## 5. Schema Version Compatibility

- Alembic `alembic_version` table tracks applied migrations
- Future schema changes: add new Alembic revision; apply on next startup
- No manual SQL required from users
