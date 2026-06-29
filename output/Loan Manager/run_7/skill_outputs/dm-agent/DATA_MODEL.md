# Loan Manager — Data Model
**Agent:** dm-agent (Wave 1)
**Run:** run_7
**Date:** 2026-04-05
**Phase:** Phase 3 Closure / Phase 4 MVP

---

## Data Model State — Run 7

### Current Schema (Confirmed Stable)

#### loans.csv
```
reference_id, borrower_name, borrower_group, amount, giving_date,
depositor_name, depositor_group, due_date, status
```
- `reference_id`: YYYY_MM_NNN format (e.g., 2026_03_001). PK. Not editable by user.
- `borrower_name`: string, lowercase (BC-02 Option B if chosen)
- `borrower_group`: string, lowercase
- `amount`: integer, INR, non-negative
- `giving_date`: ISO 8601 date (YYYY-MM-DD)
- `depositor_name`: string, optional, lowercase
- `depositor_group`: string, optional, lowercase
- `due_date`: ISO 8601 date, optional (empty string if None)
- `status`: enum [Active, Overdue, Pending, Paidoff]

**Max capacity:** 1500 rows (R4 confirmed). QStandardItemModel handles this without pagination.

#### history.csv
```
reference_id, borrower_name, borrower_group, amount, giving_date,
depositor_name, depositor_group, due_date, status, paidoff_date
```
- All fields from loans.csv plus `paidoff_date` (ISO 8601 date)
- status is always "Paidoff" for all history records
- Write: atomic two-phase (recovery.tmp → append history → remove from loans)

#### loans_meta.csv
```
year, month, last_seq
```
- Tracks the high-water mark counter per YYYY_MM period
- Managed by `loan_manager/ref_id_manager.py` (RefIdManager)
- Reset when all records for a period are deleted

#### pending_reports.csv
```
report_id, report_creation_date, report_latest_update_dt, mode, status
```
- `report_id`: RPT_YYYYMMDD_NNN format
- `mode`: enum [Monthly, Daily, Both, Paidoff]
- `status`: enum [Pending, Approved, Declined]

#### pending_report_records.csv (current schema)
```
report_id, reference_id, borrower_name, amount, depositor_name,
giving_date, due_date, interest_rate, commission_rate,
extension_period, extension_period_unit, tds_flag,
new_giving_date, new_due_date, interest_amount, commission_amount, tds_amount
```

#### reports_meta.csv
```
report_date, last_seq
```
- Tracks the high-water mark counter per YYYYMMDD for report IDs

---

## TC-08: paidoff_date Schema Decision

### Option A — Field Reuse (zero schema change)
- `new_due_date` field dual-purpose: extension due date for regular reports; paidoff_date for Paidoff-mode reports.
- No column added to pending_report_records.csv
- Code annotation documents the dual semantic
- DM assessment: Violates single-responsibility principle but acceptable for prototype. No migration risk.

### Option B — Dedicated Column (DM RECOMMENDED)

**Updated pending_report_records.csv schema:**
```
report_id, reference_id, borrower_name, amount, depositor_name,
giving_date, due_date, interest_rate, commission_rate,
extension_period, extension_period_unit, tds_flag,
new_giving_date, new_due_date, interest_amount, commission_amount, tds_amount,
paidoff_date
```

**Field definition:**
- `paidoff_date`: ISO 8601 date, optional. Populated only for mode="Paidoff" records. Empty string when None.

**Migration impact:**
- Additive column. Existing rows (produced under current schema) parse with `paidoff_date=""` → `None`. No data loss.
- No action needed on existing CSV files.

**Model change:**
```python
# models/report.py
@dataclass
class ReportRecord:
    # ... existing fields ...
    paidoff_date: Optional[date] = None  # NEW: only for mode="Paidoff"
```

**CSV_FIELDNAMES update (loan_manager/report_manager.py):**
```python
RECORD_FIELDNAMES = [
    "report_id", "reference_id", "borrower_name", "amount", "depositor_name",
    "giving_date", "due_date", "interest_rate", "commission_rate",
    "extension_period", "extension_period_unit", "tds_flag",
    "new_giving_date", "new_due_date",
    "interest_amount", "commission_amount", "tds_amount",
    "paidoff_date",  # NEW
]
```

**Serialization (to_csv_row):**
```python
"paidoff_date": rec.paidoff_date.isoformat() if rec.paidoff_date else "",
```

**Deserialization (from_csv_row):**
```python
paidoff_date_str = row.get("paidoff_date", "").strip()
paidoff_date = date.fromisoformat(paidoff_date_str) if paidoff_date_str else None
```

**DM Decision:** Option B RECOMMENDED. The semantic separation eliminates a latent bug risk where future code might misinterpret `new_due_date` for Paidoff-mode records. Additive change. Zero migration. ~2 hours.

**[REVIEW REQUIRED] TC-08:** User to confirm Option A or Option B.

---

## BC-02: Case Normalization Impact on Data Model

**Current state:** No normalization at write time. Filter comparison uses `.lower()` (UTR1 fix). Dropdown shows stored values.

**Option B impact on data model:**
- New entries always stored lowercase for: `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group`
- Existing records not affected (no retroactive normalization)
- If user has entered "BG1" in old records and "bg1" in new records, both appear in dropdowns — but both filter correctly

**Option B data consistency note:** DM recommends a one-time migration script could normalize existing records (not required for prototype scope). For new entries only, Option B is clean.

**[REVIEW REQUIRED] BC-02:** User to confirm Option A, B, or C.

---

## Data Integrity Summary

| File | Write Strategy | Risk | Mitigation |
|---|---|---|---|
| loans.csv | Append (write_loan), Overwrite (update_loan/delete_loan) | Corruption on crash during rewrite | recovery.tmp crash safety for paidoff |
| history.csv | Append only | Low risk | Two-phase write protocol |
| loans_meta.csv | Overwrite | Low risk — counter metadata only | RefIdManager atomic update |
| pending_reports.csv | Append + targeted update | Low risk | approval_recovery.tmp |
| pending_report_records.csv | Append + full report overwrite | Low risk | Additive schema change safe |
| reports_meta.csv | Overwrite | Low risk — counter metadata only | CSVReportManager |

**Data volume assessment:**
- Max 1500 active loan records (R4) — well within CSV performance bounds for PySide6 table
- 15 seeded sample records for demo
- Reports queue typically 0-10 pending at any time

---

## Schema PM Delivery Impact

**TC-08 Option B:**
- Schema change type: Additive
- Schedule impact: ~2 hours (add field, update serialization, update 2 UI files, add tests)
- Coordination needed: Backend Dev to implement, Backend QA to test
- Risk: Minimal — backward compatible

**BC-02 Option B:**
- Schema change type: Write-time normalization (no schema change)
- Schedule impact: ~30 minutes
- Risk: None — existing data unaffected
