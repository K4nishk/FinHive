# DM: Data Model — Loan Manager run_3
**Date:** 2026-04-03
**Run:** run_3 / Wave 1
**Author:** Data Modeller Agent
**Scope:** Delta data model review for run_3 change items (CHG-02-EXT, BUG-02-REF)

---

## 1. Schema Evolution Diff (v2 → v3)

**Summary:** No structural schema changes are required for the run_3 implementable items (CHG-02-EXT dialog fields, BUG-02-REF color constants). However, the SA has raised TC-301 (paidoff report identification) which requires a DM ruling.

| Schema Version | Change Summary |
|---|---|
| v2 (run_2) | No column additions from run_1. All schemas confirmed stable. |
| v3 (run_3) | No column additions. SA TC-301 resolved: use mode="Paidoff" as reserved string value — zero schema change. |

---

## 2. TC-301 Resolution — Paidoff Report Identification

### SA Question
How does the Pending Approval Tab distinguish paidoff-generated reports from regular Daily Calculator reports? Options:
1. Add `paidoff_flag` boolean column to `pending_reports.csv`
2. Use reserved `mode="Paidoff"` string value in existing `mode` column

### DM Ruling: Use mode="Paidoff" (no schema change)

**Rationale:**
- The `mode` column in `pending_reports.csv` is a STRING type with no enforced enum at the storage layer. Values `"Monthly"`, `"Daily"`, `"Both"` are in use. Adding `"Paidoff"` as a fourth reserved value requires zero schema migration.
- Adding a `paidoff_flag` column would require: (a) a migration of existing rows to set `paidoff_flag=false`, (b) updating `PENDING_REPORT_FIELDNAMES` in `models/report.py`, (c) updating `PendingReport.to_csv_row()` and `PendingReport.from_csv_row()`. This is a breaking schema change with no benefit over option 1 given the small domain.
- The `PendingReport` dataclass `mode` field is already `str` — no type change required.
- Backward compatibility: existing `pending_reports.csv` rows with `mode=Daily/Monthly/Both` are unaffected. New paidoff reports use `mode="Paidoff"`. `read_pending_reports()` filters by `status=Pending` — no mode-based filtering exists in current code, so no existing query breaks.

**DM Decision:** Write paidoff-generated reports with `mode="Paidoff"`. No schema migration required. No `PENDING_REPORT_FIELDNAMES` update needed.

### Confirmation of No Schema Change for CHG-02-EXT Dialog Fields

The three new dialog fields (`interest_rate`, `commission_rate`, `tds_flag`) collected in `PaidoffDialog` are written into `pending_report_records.csv` via the existing `ReportRecord` model. These fields are already present in `REPORT_RECORD_FIELDNAMES`:

```python
REPORT_RECORD_FIELDNAMES = [
    ...
    "interest_rate",       # already present
    "commission_rate",     # already present
    ...
    "tds_flag",            # already present
    ...
]
```

**No schema change required.** The dialog values flow through unchanged into the existing record structure.

---

## 3. Existing Physical Data Model (Confirmed Reference — Unchanged from v2)

### Table: pending_reports.csv

| Column | Type | Nullable | Notes |
|---|---|---|---|
| report_id | STRING | No | PK — format RPT_YYYYMMDD_NNN |
| report_creation_date | DATE (ISO 8601) | No | |
| report_latest_update_dt | DATETIME (ISO 8601) | No | |
| mode | STRING | No | Monthly, Daily, Both — now also "Paidoff" (run_3 addition, no schema change) |
| status | ENUM-like STRING | No | Pending, Approved, Declined |

### Table: pending_report_records.csv (Unchanged)

All fields already present. The dialog-collected `interest_rate`, `commission_rate`, `tds_flag` values map directly to existing columns.

### Tables: loans.csv, history.csv, loans_meta.csv, reports_meta.csv

Unchanged. BUG-02-REF is a UI-only change with no data model impact.

---

## 4. Data Flow for CHG-02-EXT (Confirmed)

```
PaidoffDialog.interest_rate() -> float
PaidoffDialog.commission_rate() -> float
PaidoffDialog.tds_flag() -> bool
        |
        v
_generate_paidoff_report(loan, paidoff_date, interest_rate, commission_rate, tds_flag)
        |
        v
calculate_daily({
    "amount": loan.amount,
    "interest_rate": interest_rate,    # from dialog
    "commission_rate": commission_rate, # from dialog
    "extension_period": max(0, (paidoff_date - loan.due_date).days),
    "tds_flag": tds_flag,              # from dialog
})
        |
        v
ReportRecord(
    report_id=...,
    ...
    interest_rate=interest_rate,
    commission_rate=commission_rate,
    tds_flag=tds_flag,
    interest_amount=result["interest_amount"],
    commission_amount=result["commission_amount"],
    tds_amount=result["tds_amount"],
)
        |
        v
write_report_records() -> pending_report_records.csv
```

**Data integrity:** All fields are sourced from dialog input (user-provided) or derived by `calculate_daily()`. No ambiguity in data provenance.

---

## 5. DM [REVIEW REQUIRED] Summary

No [REVIEW REQUIRED] items from DM. TC-301 is resolved by DM ruling (mode="Paidoff" accepted). No schema changes required for any run_3 item.

---

## 6. Schema Version Catalogue

| Version | Run | Summary |
|---|---|---|
| v1 | run_1 | Initial: loans.csv, history.csv, loans_meta.csv, pending_reports.csv, pending_report_records.csv, reports_meta.csv |
| v2 | run_2 | No changes |
| v3 | run_3 | No structural changes; mode="Paidoff" is a reserved value addition (non-breaking) |

