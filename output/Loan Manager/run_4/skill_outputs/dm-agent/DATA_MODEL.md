# DM Agent: Data Model — Loan Manager run_4
**Date:** 2026-04-04
**Run:** run_4 (Phase 3 Closure)
**Agent:** dm-agent (Wave 1)
**Sources:** models/loan.py, models/report.py, data/csv_manager.py, data/ref_id_manager.py, loan_manager/ref_id_manager.py

---

## Schema Change Summary

**run_4 schema change count: ZERO.**

All six in-scope items (BUG-UTR-1 through BUG-UTR-4, BC-301, CHG-02-EXT) are logic fixes and UI extensions. No CSV column additions, removals, or renames are required. The existing `REPORT_RECORD_FIELDNAMES` already includes `interest_rate`, `commission_rate`, `tds_flag`, `extension_period`, `extension_period_unit` — the fields required by CHG-02-EXT. The `mode` field in `pending_reports.csv` already supports arbitrary string values — "Paidoff" is valid without a schema change.

**No migration plan is required. No QA Lead signoff on schema changes is needed for run_4.**

---

## Schema Evolution Diff: run_3 → run_4

| File | run_3 Schema | run_4 Schema | Delta |
|---|---|---|---|
| loans.csv | 9 columns | 9 columns | No change |
| history.csv | 10 columns (loans + paidoff_date) | 10 columns | No change |
| loans_meta.csv | 2 columns | 2 columns | No change |
| pending_reports.csv | 5 columns | 5 columns | No change |
| pending_report_records.csv | 17 columns | 17 columns | No change |
| reports_meta.csv | 2 columns | 2 columns | No change |
| recovery.tmp | plain text | plain text | No change |
| approval_recovery.tmp | plain text | plain text | No change |

---

## Logical Data Model

### Entity: Loan
**Description:** A single loan record between a borrower and a depositor. Active records are stored in loans.csv. Paid-off records are archived to history.csv.

**Attributes:**

| Attribute | Type | Required | Business Meaning |
|---|---|---|---|
| reference_id | String | Yes | Unique identifier in YYYY_MM_NNN format. Derived from entry date (today), not giving_date. |
| borrower_name | String | Yes | Name of the person borrowing the money. |
| borrower_group | String | Yes | Group/category the borrower belongs to. |
| amount | Integer | Yes | Loan amount in INR. Non-negative. |
| giving_date | Date (ISO 8601) | Yes | Date the loan was given. Reference only — not used in interest calculations. |
| depositor_name | String | No | Name of the depositor. Null if unknown. |
| depositor_group | String | No | Group the depositor belongs to. Null if unknown. |
| due_date | Date (ISO 8601) | No | Date by which the loan must be repaid. Optional — some loans have no due date. |
| status | Enum | Yes | Auto-computed lifecycle state. Values: Pending, Active, Overdue, Paidoff. |

**Business Rules:**
- reference_id format: YYYY_MM_NNN where YYYY_MM is the month of data entry (not giving_date month). Order NNN is zero-padded to 3 digits up to 999, then unbounded integer.
- status=Paidoff records are not stored in loans.csv — they are moved to history.csv.
- status is auto-recomputed on every app launch; manual overrides are persisted but may be overwritten.
- giving_date is reference-only and does not drive any calculations.
- amount is always INR, non-negative integer.

**Status transition rules:**
- Pending: giving_date > today
- Active: giving_date <= today AND due_date is set AND today < due_date
- Overdue: due_date <= today, OR (no due_date AND giving_date <= today)
- Paidoff: user-initiated; record moves to history.csv

---

### Entity: LoanHistory
**Description:** Archived record for a loan that has been marked Paidoff. Stored in history.csv. Identical schema to Loan plus paidoff_date. No in-app view — archival only.

**Attributes:**

| Attribute | Type | Required | Business Meaning |
|---|---|---|---|
| reference_id | String | Yes | Same as original Loan.reference_id |
| borrower_name | String | Yes | Copied from Loan at paidoff time |
| borrower_group | String | Yes | Copied from Loan |
| amount | Integer | Yes | Copied from Loan |
| giving_date | Date | Yes | Copied from Loan |
| depositor_name | String | No | Copied from Loan |
| depositor_group | String | No | Copied from Loan |
| due_date | Date | No | Copied from Loan |
| status | Enum | Yes | Always "Paidoff" in history.csv |
| paidoff_date | Date | Yes | Date the loan was marked as paid off |

**Business Rules:**
- history.csv is append-only. Records are never deleted from history.csv.
- paidoff_date is set to the value entered by the user in PaidoffDialog.

---

### Entity: RefIdMeta
**Description:** High-water mark counter per YYYY_MM bucket. Used to generate unique, sequentially incrementing reference_ids. Stored in loans_meta.csv.

**Attributes:**

| Attribute | Type | Required | Business Meaning |
|---|---|---|---|
| year_month | String | Yes | YYYY_MM bucket key. Derived from the reference_id of existing loans (first two underscore-separated segments), NOT from loan.giving_date. |
| counter | Integer | Yes | Highest order number issued for this YYYY_MM. Next ID = counter + 1. |

**Business Rules:**
- year_month bucket must be derived from reference_id, not giving_date. A back-dated loan (giving_date in March, entry date in April) has reference_id = 2026_04_NNN and its bucket is 2026_04.
- Counter is reset (removed from file) when all loans for a YYYY_MM are deleted.
- File is written atomically (write-to-temp + rename) to prevent corruption on crash (BUG-UTR-2 Fix B).
- Typical file size: 1–12 rows (one per active calendar month).

**[REVIEW REQUIRED — SA-401]: Counter scope — does _active_year_months() need to include history.csv?**
Current implementation: `read_all_loans_including_paidoff()` reads loans.csv only (including Paidoff-status rows that haven't been archived yet — but archived Paidoff records in history.csv are NOT included). If all loans for a YYYY_MM are paid off and moved to history.csv, the next entry for that month would reset the counter to 001, potentially generating a reference_id that collides with an archived record. Options: (a) include history.csv in _active_year_months() scan — prevents collisions with archived IDs; (b) accept collision with archived records as low-risk since history.csv records are not visible in the active app. DM recommendation: option (a) is safer. A colliding reference_id in history.csv would cause data integrity confusion if history is ever re-imported.

---

### Entity: PendingReport
**Description:** Header record for a batch interest calculation report submitted for approval. One row per report in pending_reports.csv.

**Attributes:**

| Attribute | Type | Required | Business Meaning |
|---|---|---|---|
| report_id | String | Yes | Unique report identifier. Format: RPT_YYYYMMDD_NNN. |
| report_creation_date | Date (ISO 8601) | Yes | Date the report was generated. |
| report_latest_update_dt | DateTime (ISO 8601) | Yes | Timestamp of last modification. Defaults to creation time. Updated on inline edit. |
| mode | String | Yes | Calculation mode. Values: Monthly, Daily, Both, Paidoff (reserved for CHG-02-EXT). |
| status | Enum | Yes | Report lifecycle state. Values: Pending, Approved, Declined. |

**Business Rules:**
- mode="Paidoff" is a reserved value used for reports generated by the PaidoffDialog (CHG-02-EXT). This is already supported by the schema — no change needed.
- Declined reports are retained with status=Declined (not deleted). Line items are deleted from pending_report_records.csv on decline.
- report_id is globally unique per day. Counter resets per calendar day (not per month).

---

### Entity: ReportRecord
**Description:** Individual loan line item within a pending report. One row per loan per report in pending_report_records.csv.

**Attributes:**

| Attribute | Type | Required | Business Meaning |
|---|---|---|---|
| report_id | String | Yes | Foreign key to PendingReport. |
| reference_id | String | Yes | Foreign key to Loan. |
| borrower_name | String | Yes | Snapshot of borrower name at report generation time. |
| amount | Integer | Yes | Loan amount in INR. |
| depositor_name | String | No | Snapshot of depositor name. |
| giving_date | Date | Yes | Pre-extension giving date (snapshot). |
| due_date | Date | No | Pre-extension due date (snapshot). Null for no-due-date loans. |
| interest_rate | Float | Yes | Interest rate percentage applied to this record. |
| commission_rate | Float | Yes | Commission rate percentage applied. |
| extension_period | Integer | Yes | Extension duration. In days (mode=Daily/Paidoff) or months (mode=Monthly). |
| extension_period_unit | String | Yes | "days" or "months". Always "days" for mode=Paidoff. |
| tds_flag | Boolean | Yes | Whether TDS (10% of interest) is applied. Stored as "true"/"false". |
| new_giving_date | Date | No | Post-extension giving date preview. Null for Paidoff mode. |
| new_due_date | Date | No | Post-extension due date preview. Null for Paidoff mode. |
| interest_amount | Float | Yes | Calculated interest = (amount * interest_rate * extension_period) / (denominator * 100). |
| commission_amount | Float | Yes | Calculated commission = (amount * commission_rate * extension_period) / (denominator * 100). |
| tds_amount | Float | Yes | TDS = 0.1 * interest_amount if tds_flag else 0.0. |

**Business Rules:**
- For mode=Paidoff: new_giving_date and new_due_date are null (no extension applied).
- For no-due-date loans marked Paidoff (TC-401 default): extension_period=0, interest_amount=0, commission_amount=0, tds_amount=0.
- Records are inline-editable in the Pending Approval Tab. Edits update pending_report_records.csv immediately.
- Approving a report batch-extends loans.csv using new_giving_date and new_due_date.
- For mode=Paidoff, approving does NOT update loans.csv (loan already in history.csv).

---

### Entity: ReportMeta
**Description:** High-water mark counter per YYYYMMDD date key for report_id generation. Stored in reports_meta.csv.

| Attribute | Type | Required | Business Meaning |
|---|---|---|---|
| report_date | String | Yes | YYYYMMDD date key. |
| counter | Integer | Yes | Highest order number issued for this date. |

**Business Rules:**
- Counter is per calendar day. First report of the day gets _001.
- reports_meta.csv has the same non-atomic write vulnerability as loans_meta.csv. However, report_id collisions are lower risk than reference_id collisions (reports can be distinguished by creation timestamp). No fix mandated in run_4 — log as future improvement.

---

## Physical Data Model

### File: loans.csv
**Location:** `./data/loans.csv`
**Encoding:** UTF-8
**Managed by:** data/csv_manager.py, loan_manager/csv_manager.py

| Column | Python Type | CSV Representation | Nullable | Constraints |
|---|---|---|---|---|
| reference_id | str | String | No | YYYY_MM_NNN format; unique in file |
| borrower_name | str | String | No | Non-empty |
| borrower_group | str | String | No | Non-empty |
| amount | int | Decimal integer string | No | Non-negative |
| giving_date | date | ISO 8601 (YYYY-MM-DD) | No | Valid date |
| depositor_name | str | String or empty | Yes | Empty string = null |
| depositor_group | str | String or empty | Yes | Empty string = null |
| due_date | date | ISO 8601 or empty | Yes | Empty string = no due date |
| status | str | Enum string | No | One of: Active, Overdue, Pending (Paidoff rows archived to history.csv) |

**Access patterns:**
- Full scan on every read_loans() call — acceptable for max 1500 rows
- Full rewrite on every update_loan() call — performance concern at scale (R10 batch write noted)
- Append on write_loan()

---

### File: history.csv
**Location:** `./data/history.csv`
**Encoding:** UTF-8
**Managed by:** data/csv_manager.py (mark_paidoff)

| Column | Python Type | CSV Representation | Nullable |
|---|---|---|---|
| reference_id | str | String | No |
| borrower_name | str | String | No |
| borrower_group | str | String | No |
| amount | int | Decimal integer string | No |
| giving_date | date | ISO 8601 | No |
| depositor_name | str | String or empty | Yes |
| depositor_group | str | String or empty | Yes |
| due_date | date | ISO 8601 or empty | Yes |
| status | str | Always "Paidoff" | No |
| paidoff_date | date | ISO 8601 | No |

**Access patterns:** Append-only. Read by read_all_loans_including_paidoff() indirectly (see SA-401 note — currently history.csv is NOT read by this function).

---

### File: loans_meta.csv
**Location:** `./data/loans_meta.csv`
**Encoding:** UTF-8
**Managed by:** loan_manager/ref_id_manager.py (RefIdManager)

| Column | Python Type | CSV Representation | Nullable | Constraints |
|---|---|---|---|---|
| year_month | str | YYYY_MM | No | Must match first two segments of reference_id, not giving_date |
| counter | int | Decimal integer string | No | High-water mark; 0 = month just reset |

**Write safety note (BUG-UTR-2 Fix B):** Current implementation writes directly via open("w"). Fix required: write to loans_meta.tmp, then Path.replace() to atomically rename. Without this fix, a Windows crash mid-write truncates the file, causing duplicate IDs on next launch.

**Access patterns:** Read + full rewrite on every new loan entry. Typically 1–12 rows.

---

### File: pending_reports.csv
**Location:** `./data/pending_reports.csv`
**Encoding:** UTF-8
**Managed by:** loan_manager/report_manager.py (CSVReportManager)

| Column | Python Type | CSV Representation | Nullable | Constraints |
|---|---|---|---|---|
| report_id | str | RPT_YYYYMMDD_NNN | No | Unique |
| report_creation_date | date | ISO 8601 | No | |
| report_latest_update_dt | datetime | ISO 8601 datetime | No | |
| mode | str | Monthly/Daily/Both/Paidoff | No | "Paidoff" supported — no schema change needed |
| status | str | Pending/Approved/Declined | No | |

---

### File: pending_report_records.csv
**Location:** `./data/pending_report_records.csv`
**Encoding:** UTF-8
**Managed by:** loan_manager/report_manager.py (CSVReportManager)

| Column | Python Type | CSV Representation | Nullable | Constraints |
|---|---|---|---|---|
| report_id | str | RPT_YYYYMMDD_NNN | No | FK to pending_reports.csv |
| reference_id | str | YYYY_MM_NNN | No | FK to loans.csv (may be deleted) |
| borrower_name | str | String | No | |
| amount | int | Decimal integer string | No | |
| depositor_name | str | String or empty | Yes | |
| giving_date | date | ISO 8601 | No | |
| due_date | date | ISO 8601 or empty | Yes | Empty for no-due-date loans |
| interest_rate | float | Decimal string | No | |
| commission_rate | float | Decimal string | No | |
| extension_period | int | Decimal integer string | No | 0 for Paidoff no-due-date loans (TC-401 default) |
| extension_period_unit | str | "days" or "months" | No | Always "days" for Paidoff mode |
| tds_flag | bool | "true" or "false" | No | |
| new_giving_date | date | ISO 8601 or empty | Yes | Empty for Paidoff mode |
| new_due_date | date | ISO 8601 or empty | Yes | Empty for Paidoff mode |
| interest_amount | float | Decimal string | No | |
| commission_amount | float | Decimal string | No | |
| tds_amount | float | Decimal string | No | |

**CHG-02-EXT confirmation:** All columns required for Paidoff-mode report records already exist in this schema. No column additions needed.

---

### File: reports_meta.csv
**Location:** `./data/reports_meta.csv`
**Encoding:** UTF-8
**Managed by:** loan_manager/report_manager.py (CSVReportManager._write_reports_meta)

| Column | Python Type | CSV Representation | Nullable |
|---|---|---|---|
| report_date | str | YYYYMMDD | No |
| counter | int | Decimal integer string | No |

---

### File: recovery.tmp
**Location:** `./data/recovery.tmp`
**Content:** Plain text — reference_id of the loan being paid off
**Purpose:** Crash-safety for the atomic two-write Paidoff protocol. Written before the first write (history.csv append), deleted after the second write (loans.csv removal) completes. If found on startup, indicates an incomplete Paidoff operation requiring manual review.

---

### File: approval_recovery.tmp
**Location:** `./data/approval_recovery.tmp`
**Content:** Plain text — report_id of the report being approved
**Purpose:** Crash-safety for batch approval. Same pattern as recovery.tmp.

---

## Entity Relationship Diagram (Text)

```
Loan (loans.csv)
  |-- 1:1 archived as --> LoanHistory (history.csv) [on Paidoff]
  |-- 1:N referenced in --> ReportRecord (pending_report_records.csv)

PendingReport (pending_reports.csv)
  |-- 1:N contains --> ReportRecord (pending_report_records.csv)

RefIdMeta (loans_meta.csv)
  |-- 1:1 per YYYY_MM --> [counter for Loan.reference_id generation]

ReportMeta (reports_meta.csv)
  |-- 1:1 per YYYYMMDD --> [counter for PendingReport.report_id generation]
```

---

## Data Contract: run_4

**Version:** v4.0
**Status:** Approved (no schema changes — no signoff gate required)

**Summary of changes:**
- No schema changes. All 6 run_4 items are logic/UI fixes.
- CHG-02-EXT: PaidoffDialog will populate existing ReportRecord columns (interest_rate, commission_rate, tds_flag, extension_period, extension_period_unit) with mode="Paidoff". Schema already supports this.
- BUG-UTR-2: loans_meta.csv year_month derivation logic changes in application code — schema unchanged.

**Breaking changes:** No
**Data migration required:** No
**QA Lead schema signoff required:** No (no schema changes)

**Recipients:**
- Dev Lead agent: implement all 6 fixes per SA architecture; no data model changes required
- QA Lead agent: no schema signoff needed; focus QA on logic correctness for counter derivation (BUG-UTR-2) and Paidoff report pipeline (CHG-02-EXT)

---

## Flagged Items

### [REVIEW REQUIRED — SA-401]: history.csv in _active_year_months() scope

**Priority:** Low
**Description:** `data/ref_id_manager.py` `_active_year_months()` calls `read_all_loans_including_paidoff()` which reads from loans.csv only (including status=Paidoff rows that are still in loans.csv, but NOT rows already archived to history.csv). If a month's last loan is paid off and moved to history.csv, that month has zero rows in loans.csv. The next entry for that month would reset the counter to 001, generating a reference_id that collides with the archived history.csv record.

**DM recommendation:** Extend `read_all_loans_including_paidoff()` to also read history.csv, or create a separate `read_history_loans()` function and include its results in `_active_year_months()`.

**Impact on schema:** None. history.csv schema already contains reference_id.

**[REVIEW REQUIRED — TC-401]: No-due-date Paidoff extension_period default**

**Priority:** Low
**Description:** When marking a Paidoff loan that has no due_date, `extension_period = paidoff_date - due_date` is undefined. PO default (PD-R4-07): extension_period = 0, interest = 0. This is reflected in the pending_report_records.csv as extension_period=0, interest_amount=0.0, commission_amount=0.0, tds_amount=0.0. No schema impact — the columns accept 0 values.

**User question:** Confirm whether option (a) extension_period=0 or option (b) user-entered extension_period is preferred for no-due-date Paidoff loans.
