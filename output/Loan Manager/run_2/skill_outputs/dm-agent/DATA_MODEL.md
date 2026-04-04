# DM: Data Model — Loan Manager run_2
**Date:** 2026-04-03
**Run:** run_2 / Wave 1
**Author:** Data Modeller Agent
**Scope:** Delta data model review for run_2 change items. BSA data requirements brief consumed.

---

## 1. Schema Evolution Diff (v1 → v2)

This section documents the schema state change from run_1 (v1) to run_2 (v2).

**Summary: No structural schema changes required for run_2.**

All run_2 change items (CHG-01, CHG-02, BUG-01–04, DOC-01) are implementable using the existing CSV schemas without adding, removing, or renaming any columns.

| Schema Version | Change Summary |
|---|---|
| v1 (run_1) | Initial schema: loans.csv, history.csv, loans_meta.csv, pending_reports.csv, pending_report_records.csv, reports_meta.csv |
| v2 (run_2) | No column additions, removals, or renames. CHG-02 Paidoff report uses existing pending_reports and pending_report_records schemas. |

---

## 2. Existing Physical Data Model (Confirmed Reference)

### Table: loans.csv

| Column | Type | Nullable | Notes |
|---|---|---|---|
| reference_id | STRING | No | PK — format YYYY_MM_NNN |
| borrower_name | STRING | No | |
| borrower_group | STRING | Yes | |
| amount | INTEGER | No | Positive integer, unit = currency |
| giving_date | DATE (ISO 8601) | No | YYYY-MM-DD stored |
| depositor_name | STRING | Yes | |
| depositor_group | STRING | Yes | |
| due_date | DATE (ISO 8601) | Yes | NULL when "No Due Date" checked |
| status | ENUM | No | Active, Pending, Overdue — Paidoff records excluded (in history.csv) |

### Table: history.csv

Same columns as loans.csv. Paidoff loans are moved here on `mark_paidoff()`. Additional column:

| Column | Type | Nullable | Notes |
|---|---|---|---|
| paidoff_date | DATE (ISO 8601) | Yes | Set when loan is marked Paidoff |

**Business Rule:** history.csv is append-only (move from loans.csv). No in-place updates after move.

### Table: loans_meta.csv

| Column | Type | Nullable | Notes |
|---|---|---|---|
| year | INTEGER | No | |
| month | INTEGER | No | |
| last_sequence | INTEGER | No | Counter for reference_id generation |

### Table: pending_reports.csv

| Column | Type | Nullable | Notes |
|---|---|---|---|
| report_id | STRING | No | PK — format RPT_YYYYMMDD_NNN |
| report_date | DATE (ISO 8601) | No | Date report was created |
| mode | ENUM | No | Monthly, Daily, Both |
| status | ENUM | No | Pending, Approved, Declined |
| created_by | STRING | Yes | |

### Table: pending_report_records.csv

| Column | Type | Nullable | Notes |
|---|---|---|---|
| report_id | STRING | No | FK → pending_reports.report_id |
| reference_id | STRING | No | FK → loans.reference_id (or history.reference_id for Paidoff) |
| borrower_name | STRING | No | Denormalised copy at time of report creation |
| amount | INTEGER | No | Denormalised copy |
| extension_period | INTEGER | No | For Paidoff reports: max(0, (paidoff_date - due_date).days) |
| extension_period_unit | ENUM | No | days, months |
| interest_rate | DECIMAL | No | Default 12.0 for Paidoff reports — see BC-05 |
| commission_rate | DECIMAL | No | Default 2.0 for Paidoff reports — see BC-05 |
| tds_flag | BOOLEAN | No | Default false for Paidoff reports — see BC-05 |
| interest_amount | DECIMAL | No | Calculated: (amount × interest_rate × extension_period) / (365 × 100) |
| commission_amount | DECIMAL | No | Calculated: (amount × commission_rate × extension_period) / (365 × 100) |
| mode | ENUM | No | Monthly, Daily, Both — always "Daily" for Paidoff reports |

### Table: reports_meta.csv

| Column | Type | Nullable | Notes |
|---|---|---|---|
| report_date | DATE (ISO 8601) | No | |
| last_sequence | INTEGER | No | Counter for report_id generation |

---

## 3. Logical Data Model: CHG-02 Paidoff Report

## Logical Data Model: Paidoff Interest Report

**Entities:**

### PaidoffInterestReport
- **Description:** An interest calculation report generated automatically when a loan is marked as Paidoff. Captures the interest owed for any extension period (days between due_date and paidoff_date).
- **Attributes:**

| Attribute | Type | Required | Description |
|---|---|---|---|
| report_id | String | Yes | System-generated identifier |
| report_date | Date | Yes | Date the Paidoff event occurred |
| mode | Enum ("Daily") | Yes | Fixed to "Daily" for all Paidoff reports |
| status | Enum | Yes | Always "Pending" at creation — awaits approval queue action |
| loan_reference_id | String | Yes | The paidoff loan's reference_id |
| extension_period_days | Integer | Yes | max(0, paidoff_date - due_date). Zero for early payoffs. |
| interest_rate | Decimal | Yes | Loan interest rate (default 12.0%) — [REVIEW REQUIRED BC-05] |
| commission_rate | Decimal | Yes | Loan commission rate (default 2.0%) — [REVIEW REQUIRED BC-05] |
| interest_amount | Decimal | Yes | Calculated interest owed |
| commission_amount | Decimal | Yes | Calculated commission owed |

**Business Rules:**
- A Paidoff report is only created if the paidoff loan has a `due_date`. Loans with no `due_date` do not generate a report.
- `extension_period_days` is always non-negative (negative values clamped to 0 per PD-R2-02).
- A Paidoff report with `extension_period_days = 0` results in `interest_amount = 0.00` and `commission_amount = 0.00`.
- One report per Paidoff event (one PendingReport + one PendingReportRecord).

**Relationships:**
| Entity A | Relationship | Entity B | Notes |
|---|---|---|---|
| Loan (paidoff) | triggers creation of | PaidoffInterestReport | After mark_paidoff() completes |
| PaidoffInterestReport | stored as | PendingReport + PendingReportRecord | Uses existing schema — no new tables |

---

## 4. Data Contract: CHG-02 Paidoff Report

## Data Contract: Paidoff Interest Report (CHG-02)

**Version:** v1.0
**Status:** Approved (no schema changes, uses existing model)

**Summary of changes:**
- No new tables or columns
- pending_reports.csv receives one new row per Paidoff event with `mode = "Daily"`
- pending_report_records.csv receives one new row with `extension_period_unit = "days"`, `extension_period = max(0, days)`, and calculated amounts

**Breaking changes:** No
**Non-breaking additions:** None (existing schema is used as-is)
**Data migration required:** No

**Key data values for Paidoff reports (fixed at creation time):**
| Field | Value | Source |
|---|---|---|
| mode | "Daily" | Fixed |
| extension_period_unit | "days" | Fixed |
| extension_period | max(0, (paidoff_date - due_date).days) | Computed |
| interest_rate | 12.0 (default) | Global default — see BC-05 |
| commission_rate | 2.0 (default) | Global default — see BC-05 |
| tds_flag | false | Global default — see BC-05 |
| status | "Pending" | Fixed at creation |

**[REVIEW REQUIRED — BC-05]:** The `interest_rate`, `commission_rate`, and `tds_flag` values in the Paidoff report are sourced from global defaults (12%, 2%, false). If the loan was originally entered with different rates, the Paidoff report will not reflect those per-loan rates because the Loan model does not store `interest_rate` or `commission_rate` at the individual loan level. The DM confirms there is no rate data available at the loan record level to use as an alternative source. Options:
1. Use global defaults (current approach) — simple but potentially inaccurate if rates vary
2. Prompt user for rate inputs at Paidoff time (requires PaidoffDialog extension)
3. Add `interest_rate` and `commission_rate` columns to loans.csv/history.csv (schema change required)

PO decision required before implementation proceeds on this point.

**Recipients:**
- Dev Lead agent — implement CHG-02 per this contract
- QA Lead agent — schema signoff: no migration risk, no breaking changes

**Signoff required from QA Lead before Dev Lead proceeds:** Yes (procedural — no schema risk but QA must agree on test data setup)

---

## 5. Data Contract: DOC-01 Import Parser

## Data Contract: DOC-01 Import Date Format

**Version:** v1.0
**Status:** Approved

**Summary of changes:**
- No schema changes
- `import_service.py` internal parsing logic is modified to accept DD-MM-YYYY in addition to YYYY-MM-DD
- All dates remain stored as ISO 8601 (YYYY-MM-DD) internally — this is a read/parse change only, not a storage change

**Breaking changes:** No
**Data migration required:** No

**DM note:** The `_parse_flexible_date()` helper is a pure parsing utility. It does not change what is stored. The data contract for loans.csv, history.csv, and all other tables is unchanged.

---

## 6. DM Business Risk Flags

**Risk DM-R01 — Denormalised rate fields in pending_report_records.csv**
The `interest_rate` and `commission_rate` columns in `pending_report_records.csv` hold snapshot values at report creation time. For Paidoff reports, these values default to global defaults (12.0%, 2.0%) because individual loan records do not store rate information. This is an asymmetry: manual reports created via the Interest Calculator tab may reflect user-specified rates, while Paidoff-auto-generated reports always use defaults.

**This asymmetry requires explicit user acknowledgement.** If in practice rates vary per loan or borrower group, the Paidoff reports will be systematically inaccurate. This is flagged as BC-05.

**Risk DM-R02 — history.csv loan reference in pending_report_records.csv**
After `mark_paidoff()`, the loan exists in `history.csv`, not `loans.csv`. The `pending_report_records.reference_id` foreign key conceptually points to a loan that has been moved out of the active table. The approval flow (`batch_extend_loans()`) will not find the loan in `loans.csv` and will trigger the "records deleted" warning path. This is the BC-06 semantic conflict raised by BSA. The DM confirms this is an existing architectural limitation — the `pending_report_records` schema does not distinguish between `loans.csv` references and `history.csv` references. A `source_table` or `record_type` column would be needed for a clean fix (Phase 4 scope).

---

## 7. DM → DEV and QA Lead: Schema Change Signoff Request

## DM → DEV and QA Lead: Schema Change Signoff Request

**Feature:** run_2 (CHG-01, CHG-02, BUG-01–04, DOC-01)
**Change summary:** No structural schema changes. Existing schemas are used as-is for all run_2 items. The only data layer change is import parsing logic (DOC-01) and a new Paidoff report write path (CHG-02).

**Test impact:**
- pending_reports.csv / pending_report_records.csv: QA must cover new Paidoff report row creation (CHG-02 test cases)
- loans.csv / history.csv: QA must verify loan moves correctly on `mark_paidoff()` (regression from BUG-03 context menu fix)
- Import test fixtures: QA needs both YYYY-MM-DD and DD-MM-YYYY format test CSVs (DOC-01)

**Migration test requirements:**
- No migration. No backfill. No rollback plan needed.
- Verify: Paidoff report creation does not corrupt existing pending_reports.csv entries

**Signoff requested from:** QA Lead agent and DEV Lead agent
