# Data Model: Loan Manager

**Produced by:** Data Modeller (DM) Agent
**Run:** run_1, Wave 1
**Date:** 2026-04-03
**Version:** v1.0
**Status:** Proposed

---

## Table of Contents

1. [Logical Data Model](#1-logical-data-model)
2. [Physical Data Model (CSV-adapted)](#2-physical-data-model-csv-adapted)
3. [Data Contract](#3-data-contract)
4. [Schema Evolution Notes](#4-schema-evolution-notes)
5. [Data Dictionary](#5-data-dictionary)

---

## 1. Logical Data Model

### 1.1 Entity: Loan

**Description:** Represents a single active loan record between a borrower and a depositor. Paidoff loans are removed from this entity and archived in History. This is the primary operational entity of the system.

**Attributes:**

| Attribute        | Type          | Required | Business Meaning                                                                                       |
|------------------|---------------|----------|--------------------------------------------------------------------------------------------------------|
| reference_id     | String        | Yes      | System-assigned unique identifier in format YYYY_MM_<order>. Not user-editable. Primary key.          |
| borrower_name    | String        | Yes      | Name of the person who borrowed the money.                                                             |
| borrower_group   | String        | Yes      | Group or category the borrower belongs to, used for filtering and reporting.                           |
| amount           | Integer (INR) | Yes      | Non-negative loan amount in Indian Rupees.                                                             |
| giving_date      | Date          | Yes      | The date the loan was given. Reference only; not used in interest time-period calculations.            |
| depositor_name   | String        | No       | Name of the person who deposited/funded the loan. May be absent for legacy records.                    |
| depositor_group  | String        | No       | Group the depositor belongs to. May be absent; displayed as "Unknown" in UI.                          |
| due_date         | Date          | No       | The date the loan is due for repayment. Optional; a loan without a due_date is treated as Overdue.    |
| status           | Enum          | Yes      | Current lifecycle state of the loan. One of: Active, Overdue, Paidoff, Pending.                       |

**Business Rules:**

- BR-L-01: `reference_id` is system-assigned and immutable once written. Format: `YYYY_MM_<order>` (order is zero-padded to 3 digits minimum; extends beyond 999 if needed, e.g. 1000, 1001).
- BR-L-02: `status` is auto-recomputed on every app launch based on dates relative to today. Manual overrides are persisted but may be overwritten on next launch.
- BR-L-03: Status transition rules:
  - `Pending` when `giving_date > today` (future-dated entry).
  - `Active` when `giving_date <= today < due_date`.
  - `Overdue` when `due_date <= today`, or when `due_date` is absent.
  - `Paidoff` is a terminal state for this entity; paidoff records are moved to History and are no longer visible in the View Tab.
- BR-L-04: Manual Active override by the user always prompts for a new due_date (equivalent to Extend, R4). The recompute on next launch evaluates against the new due_date.
- BR-L-05: `amount` must be a non-negative integer.
- BR-L-06: `giving_date` is used only as a reference column and does not enter any time-period or interest calculations.
- BR-L-07: If `depositor_name` or `depositor_group` is absent, the UI displays "Unknown" as the value, and the user may inline-edit it.
- BR-L-08: On Extend (R4 or batch via R5 approval), the existing record is overwritten in-place: `giving_date` becomes old `due_date` (or `today` if no `due_date` existed), and `due_date` becomes `old_due_date + extension_period`. Loss of pre-extension history is explicitly accepted.
- BR-L-09: If all records for a given YYYY_MM are deleted, the counter for that month resets to 001. The next entry gets the next sequential number after the current high-water mark.

---

### 1.2 Entity: LoansMeta

**Description:** Stores the high-water-mark counter per year-month to support sequential, non-colliding `reference_id` assignment. One row per active YYYY_MM period.

**Attributes:**

| Attribute  | Type    | Required | Business Meaning                                                                              |
|------------|---------|----------|-----------------------------------------------------------------------------------------------|
| year_month | String  | Yes      | The year-month key in format YYYY_MM. Primary key for this entity.                            |
| counter    | Integer | Yes      | The highest order number issued for the given year_month. Used to derive the next reference_id. |

**Business Rules:**

- BR-M-01: `counter` reflects the last issued order number, not the count of active records. Deleting a record does not decrement the counter except when the last record for that year_month is deleted (counter resets to 0 so next entry gets 001).
- BR-M-02: When a collision is detected during import of legacy-format records with auto-assigned IDs, the counter increments until a free slot is found.
- BR-M-03: The counter supports integers beyond 999, enabling the 1000th+ loan in a month.

---

### 1.3 Entity: History

**Description:** An append-only archive of loans that have been marked as Paidoff. Records here are never modified after insertion. No in-app view is required for this entity.

**Attributes:**

| Attribute      | Type          | Required | Business Meaning                                                                                     |
|----------------|---------------|----------|------------------------------------------------------------------------------------------------------|
| reference_id   | String        | Yes      | Original reference_id from the Loan entity at time of paidoff.                                       |
| borrower_name  | String        | Yes      | Name of the borrower at time of paidoff.                                                             |
| borrower_group | String        | Yes      | Borrower group at time of paidoff.                                                                   |
| amount         | Integer (INR) | Yes      | Loan amount at time of paidoff.                                                                      |
| giving_date    | Date          | Yes      | Giving date at time of paidoff.                                                                      |
| depositor_name | String        | No       | Depositor name at time of paidoff.                                                                   |
| depositor_group| String        | No       | Depositor group at time of paidoff.                                                                  |
| due_date       | Date          | No       | Due date at time of paidoff.                                                                         |
| status         | String        | Yes      | Always "Paidoff" for history records.                                                                |
| paidoff_date   | Date          | Yes      | The date the loan was confirmed paid off by the user.                                                |

**Business Rules:**

- BR-H-01: History records are written using an atomic two-step protocol: (1) write `reference_id` to `recovery.tmp`, (2) append to `history.csv`, (3) remove from `loans.csv`, (4) delete `recovery.tmp`. On crash recovery, `recovery.tmp` signals an incomplete operation.
- BR-H-02: History is append-only. No update or delete operations are performed by the application on this file.
- BR-H-03: `status` is always "Paidoff". Records with other statuses in this file are considered malformed.
- BR-H-04: To reactivate a paidoff loan, the user must manually edit `history.csv` and `loans.csv` outside the application; there is no in-app reactivation flow.

---

### 1.4 Entity: PendingReport

**Description:** Header metadata for a calculator report generated from the Interest Calculator Tab. Represents a report awaiting approval, modification, or declination. Normalized header table; line items are in PendingReportRecord.

**Attributes:**

| Attribute               | Type     | Required | Business Meaning                                                                                             |
|-------------------------|----------|----------|--------------------------------------------------------------------------------------------------------------|
| report_id               | String   | Yes      | System-assigned unique identifier. Format: RPT_YYYYMMDD_<order>. Primary key.                               |
| report_creation_date    | Date     | Yes      | The date the report was first generated (YYYY-MM-DD).                                                        |
| report_latest_update_dt | Datetime | Yes      | ISO 8601 datetime of the last modification to the report (creation or subsequent edit). Updates on any inline edit of report records. |
| mode                    | Enum     | Yes      | Calculator mode used when generating the report. One of: Monthly, Daily, Both.                               |
| status                  | Enum     | Yes      | Current report lifecycle state. One of: Pending, Approved, Declined.                                        |

**Business Rules:**

- BR-PR-01: `report_id` format is `RPT_YYYYMMDD_<order>` (e.g., `RPT_20260320_001`). Order is zero-padded to 3 digits minimum.
- BR-PR-02: A report starts in `Pending` status. It transitions to `Approved` or `Declined` by user action only.
- BR-PR-03: On `Declined`: the report record is marked Declined and associated `pending_report_records` rows are deleted. No updates are made to `loans.csv`.
- BR-PR-04: On `Approved`: associated loan records in `loans.csv` are updated with the post-extension dates from `pending_report_records`. Records that no longer exist in `loans.csv` are skipped after user confirmation.
- BR-PR-05: `report_latest_update_dt` is updated to the current datetime whenever any inline edit is made to any record within the report in the Pending Approval Tab.
- BR-PR-06: The `reports_meta.csv` file tracks the per-date counter for `report_id` generation (analogous to `loans_meta.csv` for `reference_id`).
- BR-PR-07: If two pending reports share a `reference_id`, the user is warned before approval: "This report shares loan records with another pending report. Approving may overwrite previous updates." The user may Proceed or Cancel. On Proceed, prior updates in both storage and the other report records are silently overwritten.

---

### 1.5 Entity: PendingReportRecord

**Description:** A line item within a PendingReport. Stores per-loan calculator parameters, calculated output values, and preview of post-extension dates. Records are inline-editable by the user prior to approval. Foreign key to PendingReport.

**Attributes:**

| Attribute                  | Type          | Required | Business Meaning                                                                                          |
|----------------------------|---------------|----------|-----------------------------------------------------------------------------------------------------------|
| report_id                  | String        | Yes      | Foreign key to PendingReport.report_id.                                                                   |
| reference_id               | String        | Yes      | Foreign key to Loan.reference_id (at time of report generation).                                         |
| borrower_name              | String        | Yes      | Borrower name captured at report generation time (pre-extension snapshot).                                |
| amount                     | Integer (INR) | Yes      | Loan amount at time of report generation.                                                                 |
| depositor_name             | String        | No       | Depositor name at time of report generation.                                                              |
| giving_date                | Date          | Yes      | Pre-extension giving_date (snapshot).                                                                     |
| due_date                   | Date          | No       | Pre-extension due_date (snapshot). May be absent for no-due-date loans.                                   |
| interest_rate              | Float         | Yes      | Annual percentage rate of interest assigned by depositor. Inline-editable.                                |
| commission_rate            | Float         | Yes      | Annual percentage commission rate owed by borrower. Inline-editable.                                      |
| extension_period           | Integer       | Yes      | Duration of extension. Inline-editable per record.                                                        |
| extension_period_unit      | Enum          | Yes      | Unit for extension_period. One of: months, days. Inline-editable per record.                              |
| tds_flag                   | Boolean       | Yes      | Whether TDS should be calculated. Default: false. Inline-editable.                                        |
| interest_amount            | Float         | Yes      | Calculated interest. Auto-updates when any calculator parameter is inline-edited.                         |
| commission_amount          | Float         | Yes      | Calculated commission. Auto-updates when any calculator parameter is inline-edited.                        |
| tds_amount                 | Float         | Yes      | Calculated TDS (= 0.1 * interest_amount if tds_flag is true, else 0). Auto-updates.                      |
| new_giving_date            | Date          | Yes      | Post-extension giving_date preview (= old due_date, or today if no due_date).                             |
| new_due_date               | Date          | Yes      | Post-extension due_date preview (= old due_date + extension_period in extension_period_unit).             |

**Business Rules:**

- BR-PRR-01: `giving_date`, `due_date`, `borrower_name`, `amount`, `depositor_name` are snapshots taken at report generation time. The Pending Approval Tab displays pre-extension values; post-extension values are only shown in `new_giving_date` / `new_due_date` columns.
- BR-PRR-02: `interest_amount`, `commission_amount`, and `tds_amount` are derived calculated values. They must be recomputed whenever `interest_rate`, `commission_rate`, `extension_period`, `extension_period_unit`, or `tds_flag` changes inline.
- BR-PRR-03: Calculation formulas (authoritative, per R5):
  - Monthly mode: `Interest = (amount * interest_rate * extension_period) / (12 * 100)`, `Commission = (amount * commission_rate * extension_period) / (12 * 100)`
  - Daily mode: `Interest = (amount * interest_rate * extension_period) / (365 * 100)`, `Commission = (amount * commission_rate * extension_period) / (365 * 100)`
  - TDS: `tds_amount = 0.1 * interest_amount` when `tds_flag = true`, else `0`.
  - Only the extension window is charged; `giving_date` does not enter the calculation.
- BR-PRR-04: On report Decline, all rows for that `report_id` are deleted from this file.
- BR-PRR-05: On report Approval, `loans.csv` records are updated using `new_giving_date` and `new_due_date`. Deleted loans (reference_id no longer in loans.csv) are skipped after user warning.
- BR-PRR-06: Records for an Approved report are retained in `pending_report_records.csv` for audit trail purposes. [REVIEW REQUIRED: The requirements state that Declined reports are deleted. It is not explicitly stated whether Approved report records should be retained or also purged. Current implementation retains them. Clarification needed.]

---

## 2. Physical Data Model (CSV-adapted)

### 2.1 loans.csv

**Location:** `./data/loans.csv`
**Purpose:** Active loan records (all statuses except Paidoff are stored here).
**Note:** The current implementation retains rows with `status = Paidoff` in loans.csv until they are explicitly removed by `mark_paidoff()`. The `read_loans()` function filters them out at read time. This is an implementation detail; logically, Paidoff records belong in history.csv only.

| Column          | Type    | Nullable | Constraints                                                      | Example Value   |
|-----------------|---------|----------|------------------------------------------------------------------|-----------------|
| reference_id    | String  | No       | Format: YYYY_MM_<order>. Unique within file.                     | 2026_03_001     |
| borrower_name   | String  | No       | Non-empty string.                                                | b1              |
| borrower_group  | String  | No       | Non-empty string.                                                | bg1             |
| amount          | Integer | No       | Non-negative integer.                                            | 10000           |
| giving_date     | Date    | No       | ISO 8601: YYYY-MM-DD.                                            | 2026-01-02      |
| depositor_name  | String  | Yes      | Empty string when absent.                                        | d1              |
| depositor_group | String  | Yes      | Empty string when absent.                                        | dg1             |
| due_date        | Date    | Yes      | ISO 8601: YYYY-MM-DD. Empty string when absent.                  | 2026-04-02      |
| status          | String  | No       | Enum: Active, Overdue, Paidoff, Pending.                         | Active          |

**File-level constraints:**
- Header row must always be present, even if the file has no data rows.
- Encoding: UTF-8 (BOM-tolerant on read via `utf-8-sig`).
- Line endings: OS default (Python csv writer default).

---

### 2.2 loans_meta.csv

**Location:** `./data/loans_meta.csv`
**Purpose:** High-water-mark counters for reference_id generation, keyed by year_month.

| Column     | Type    | Nullable | Constraints                                            | Example Value |
|------------|---------|----------|--------------------------------------------------------|---------------|
| year_month | String  | No       | Format: YYYY_MM. Unique within file. Primary key.      | 2026_03       |
| counter    | Integer | No       | Non-negative integer. Represents last issued order.    | 3             |

**File-level constraints:**
- One row per active year_month period.
- Counter is reset to 0 (not deleted) when the last loan for that year_month is deleted, so the next entry gets order 001.

---

### 2.3 history.csv

**Location:** `./data/history.csv`
**Purpose:** Append-only archive of loans marked as Paidoff. Never modified after row insertion.

| Column          | Type    | Nullable | Constraints                                                      | Example Value   |
|-----------------|---------|----------|------------------------------------------------------------------|-----------------|
| reference_id    | String  | No       | Format: YYYY_MM_<order>. Not required to be unique if a loan is re-paidoff after re-import edge case. | 2026_03_002 |
| borrower_name   | String  | No       | Non-empty string.                                                | b20             |
| borrower_group  | String  | No       | Non-empty string.                                                | bg10            |
| amount          | Integer | No       | Non-negative integer.                                            | 10000           |
| giving_date     | Date    | No       | ISO 8601: YYYY-MM-DD.                                            | 2026-03-22      |
| depositor_name  | String  | Yes      | Empty string when absent.                                        | d21             |
| depositor_group | String  | Yes      | Empty string when absent.                                        | dg10            |
| due_date        | Date    | Yes      | ISO 8601: YYYY-MM-DD. Empty string when absent.                  |                 |
| status          | String  | No       | Always "Paidoff".                                                | Paidoff         |
| paidoff_date    | Date    | No       | ISO 8601: YYYY-MM-DD. The date paidoff was confirmed.            | 2026-03-23      |

**File-level constraints:**
- Append-only. Application never rewrites or truncates this file.
- Recovery mechanism: `recovery.tmp` in `./data/` contains the `reference_id` of any in-progress paidoff operation. On startup, if this file exists, the app should reconcile (verify if history row was written; if not, retry).

---

### 2.4 pending_reports.csv

**Location:** `./data/pending_reports.csv`
**Purpose:** Report header metadata for the Pending Approval queue.

| Column                  | Type     | Nullable | Constraints                                                                | Example Value                    |
|-------------------------|----------|----------|----------------------------------------------------------------------------|----------------------------------|
| report_id               | String   | No       | Format: RPT_YYYYMMDD_<order>. Unique within file.                          | RPT_20260324_001                 |
| report_creation_date    | Date     | No       | ISO 8601: YYYY-MM-DD. Date report was first created.                       | 2026-03-24                       |
| report_latest_update_dt | Datetime | No       | ISO 8601 datetime (YYYY-MM-DDTHH:MM:SS.ffffff). Updates on any edit.       | 2026-04-03T11:48:07.070796       |
| mode                    | String   | No       | Enum: Monthly, Daily, Both.                                                | Monthly                          |
| status                  | String   | No       | Enum: Pending, Approved, Declined.                                         | Approved                         |

**File-level constraints:**
- Persists across app restarts (reports must survive session close/reopen).
- Declined report rows: per current implementation, the row is retained with `status = Declined` and associated `pending_report_records` rows are deleted. [REVIEW REQUIRED: Requirements state "declined reports are deleted and removed from the queue." It is ambiguous whether the header row in `pending_reports.csv` is also deleted or merely marked Declined. Current implementation retains with Declined status. Clarification needed for consistency with UI queue display.]

---

### 2.5 pending_report_records.csv

**Location:** `./data/pending_report_records.csv`
**Purpose:** Line items per report. Stores pre-extension snapshot, calculator parameters (inline-editable), calculated output values, and post-extension date preview.

| Column                | Type    | Nullable | Constraints                                                                          | Example Value    |
|-----------------------|---------|----------|--------------------------------------------------------------------------------------|------------------|
| report_id             | String  | No       | Foreign key to pending_reports.report_id.                                            | RPT_20260324_001 |
| reference_id          | String  | No       | Foreign key to loans.reference_id at time of report generation.                      | 2026_03_001      |
| borrower_name         | String  | No       | Snapshot of borrower_name at report generation.                                      | b21              |
| amount                | Integer | No       | Snapshot of loan amount at report generation. Non-negative integer.                  | 100000           |
| depositor_name        | String  | Yes      | Snapshot of depositor_name at report generation. Empty string when absent.           | d20              |
| giving_date           | Date    | No       | Pre-extension giving_date snapshot. ISO 8601: YYYY-MM-DD.                            | 2026-03-27       |
| due_date              | Date    | Yes      | Pre-extension due_date snapshot. Empty string when absent. ISO 8601: YYYY-MM-DD.     | 2026-06-27       |
| interest_rate         | Float   | No       | Annual interest rate percentage. Inline-editable. e.g. 12.0 means 12%.              | 12.0             |
| commission_rate       | Float   | No       | Annual commission rate percentage. Inline-editable.                                  | 1.0              |
| extension_period      | Integer | No       | Extension duration as a positive integer. Inline-editable.                           | 6                |
| extension_period_unit | String  | No       | Enum: months, days. Inline-editable.                                                 | months           |
| tds_flag              | Boolean | No       | Whether TDS is applicable. Stored as: true / false (lowercase string).               | true             |
| interest_amount       | Float   | No       | Calculated interest. Derived; auto-recomputed on parameter change.                   | 6000.0           |
| commission_amount     | Float   | No       | Calculated commission. Derived; auto-recomputed on parameter change.                 | 500.0            |
| tds_amount            | Float   | No       | Calculated TDS. Derived; 0 when tds_flag is false. Auto-recomputed.                 | 600.0            |
| new_giving_date       | Date    | No       | Post-extension giving_date preview. ISO 8601: YYYY-MM-DD.                            | 2026-06-27       |
| new_due_date          | Date    | No       | Post-extension due_date preview. ISO 8601: YYYY-MM-DD.                               | 2026-12-27       |

**File-level constraints:**
- `(report_id, reference_id)` should be unique within this file under normal operation. Duplicate pairs may arise only in edge cases (e.g., re-generation without cleanup).
- `tds_flag` is stored as the string literals `true` or `false` (case-insensitive on read).
- All calculated amounts (`interest_amount`, `commission_amount`, `tds_amount`) are stored as floats rounded to 2 decimal places.

---

### 2.6 reports_meta.csv

**Location:** `./data/reports_meta.csv`
**Purpose:** High-water-mark counters for `report_id` generation, keyed by report_date (YYYYMMDD string).

| Column      | Type    | Nullable | Constraints                                               | Example Value |
|-------------|---------|----------|-----------------------------------------------------------|---------------|
| report_date | String  | No       | Format: YYYYMMDD. Unique within file. Primary key.        | 20260324      |
| counter     | Integer | No       | Non-negative integer. Represents last issued order number.| 1             |

**File-level constraints:**
- Analogous to `loans_meta.csv`. One row per date on which reports have been generated.

---

## 3. Data Contract

### Data Contract: Loan Manager CSV Schema

**Version:** v1.0
**Status:** Proposed
**Date:** 2026-04-03

---

**Summary of entities:**

| CSV File                     | Entity               | Primary Key                       | Relationship                                        |
|------------------------------|----------------------|-----------------------------------|-----------------------------------------------------|
| loans.csv                    | Loan                 | reference_id                      | Root entity                                         |
| loans_meta.csv               | LoansMeta            | year_month                        | Supports reference_id generation for Loan           |
| history.csv                  | History              | (reference_id, paidoff_date)      | Archive; derived from Loan on Paidoff transition    |
| pending_reports.csv          | PendingReport        | report_id                         | Report header; 1-to-many with PendingReportRecord   |
| pending_report_records.csv   | PendingReportRecord  | (report_id, reference_id)         | Report line items; many-to-1 with PendingReport     |
| reports_meta.csv             | ReportsMeta          | report_date                       | Supports report_id generation for PendingReport     |

---

**Breaking changes:** N/A (new system)

---

**Data integrity rules:**

- `reference_id` format: `YYYY_MM_<order>` where order is at minimum 3 digits (zero-padded), extensible beyond 999 (e.g., `2026_03_1000`).
- `giving_date`, `due_date`, `paidoff_date`, `report_creation_date`, `new_giving_date`, `new_due_date`: ISO 8601 date format `YYYY-MM-DD`.
- `report_latest_update_dt`: ISO 8601 datetime format `YYYY-MM-DDTHH:MM:SS.ffffff`.
- `amount`: non-negative integer (INR). No decimals.
- `status` enum for Loan: `Active`, `Overdue`, `Paidoff`, `Pending` (case-sensitive).
- `status` enum for PendingReport: `Pending`, `Approved`, `Declined` (case-sensitive).
- `mode` enum for PendingReport: `Monthly`, `Daily`, `Both` (case-sensitive).
- `extension_period_unit` enum: `months`, `days` (lowercase).
- `tds_flag` stored as: `true` or `false` (lowercase string literals).
- `report_id` format: `RPT_YYYYMMDD_<order>` (e.g., `RPT_20260320_001`).
- `interest_rate`, `commission_rate`: non-negative floats representing percentage values (e.g., `12.0` = 12%).
- `interest_amount`, `commission_amount`, `tds_amount`: non-negative floats, 2 decimal places.
- All CSV files must include the header row even when empty of data.
- All CSV files use UTF-8 encoding (UTF-8-BOM-tolerant on read).

---

**Cross-file integrity rules:**

- Every `reference_id` in `pending_report_records.csv` should correspond to an existing record in `loans.csv` at time of approval (skipped with user warning if not found).
- Every `report_id` in `pending_report_records.csv` must exist in `pending_reports.csv`.
- `history.csv` should not contain `reference_id` values that are currently active in `loans.csv` (enforced by atomic Paidoff protocol).
- `loans_meta.csv` counter for a given `year_month` must be >= the count of records in `loans.csv` with that `year_month` prefix.

---

## 4. Schema Evolution Notes

### 4.1 [REVIEW REQUIRED] Fate of pending_report_records on Report Decline

**Issue:** When a report is Declined (R5), the requirements state "the report_id is marked as Declined and the calculated values are deleted without any storage updates." This implies that rows in `pending_report_records.csv` for that `report_id` should be deleted.

**Current implementation observation:** The current `pending_reports.csv` retains the header row with `status = Declined`. It is not confirmed from the source code whether the associated `pending_report_records.csv` rows are also purged on decline.

**Decision needed:** Should `pending_report_records.csv` rows be hard-deleted on decline (to avoid orphan records), or retained for a lightweight audit trail? Retaining them requires the UI to filter by `status != Declined` when rendering the queue.

**Recommendation:** Hard-delete the line items on Decline to keep the queue file clean. The header row in `pending_reports.csv` may be retained with `status = Declined` as a minimal audit trace, but this should be a conscious decision. Mark as [REVIEW REQUIRED].

---

### 4.2 [REVIEW REQUIRED] Should history.csv include report_id for Paidoff-via-Report records?

**Issue:** R3 states that when a loan is marked `Paidoff`, a report is generated and sent to the Pending Approval Tab (per the Daily Calculator flow). When that report is approved, the loan transitions to Paidoff. However, the current `history.csv` schema (and the `HISTORY_FIELDNAMES` constant in `csv_manager.py`) does not include a `report_id` column.

**Impact:** There is no traceable link from a history record to the approval report that triggered it. This makes reconciliation and auditing harder if the user ever needs to cross-reference a paidoff loan with its approval report.

**Recommendation:** Add an optional `report_id` column to `history.csv` (nullable/empty for loans paidoff directly without a report path). Mark as [REVIEW REQUIRED] — this is a schema addition and would require updates to `HISTORY_FIELDNAMES`, `mark_paidoff()`, and the Paidoff dialog.

---

### 4.3 [REVIEW REQUIRED] pending_reports.csv header row retention on Decline

**Issue:** Requirements state declined reports are "deleted and removed from the queue." The current implementation retains the header row with `status = Declined` in `pending_reports.csv`. If the intent is to remove the record entirely, the UI queue must also filter by `status = Pending` only.

**Decision needed:** Hard-delete both header and line items on Decline, or retain the header as a declined audit record?

---

### 4.4 [REVIEW REQUIRED] Approved report records retention in pending_report_records.csv

**Issue:** After a report is Approved, it is unclear if the `pending_report_records.csv` rows for that `report_id` should be retained or deleted. Current file data shows an approved report (`RPT_20260324_001`) with its row still present in `pending_report_records.csv`.

**Recommendation:** Retain Approved report records for audit purposes (to allow reconstruction of what values were used). The UI should filter the active queue to `status = Pending` in `pending_reports.csv`. Mark as [REVIEW REQUIRED] for explicit product confirmation.

---

### 4.5 Asymmetry: giving_date snapshot in pending_report_records.csv vs. loans.csv

**Observation:** In the current data, the `giving_date` in `pending_report_records.csv` (`2026-03-27`) differs from the `giving_date` in `loans.csv` for the same `reference_id` (`2026-03-27` in the report vs. the current `loans.csv` value of `2026-06-27` after approval updated it). This confirms that the report stores a pre-extension snapshot, and the loans.csv record has been updated post-approval. This is expected and correct per R5.

---

### 4.6 No-due-date Loan Extension Edge Case

**Observation:** R7 clarifies that for loans without a `due_date`, Extend sets `new_giving_date = today` and `new_due_date = user-selected date`. The `pending_report_records.csv` must handle an empty `due_date` cell for such loans (the `new_giving_date` will be computed as today's date at report generation time, not old `due_date`). This is correctly nullable in the physical schema.

---

## 5. Data Dictionary

Canonical definitions for all fields used across the Loan Manager CSV files.

| Field                   | Used In                                               | Type          | Description                                                                                                                                                                                            |
|-------------------------|-------------------------------------------------------|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| reference_id            | loans.csv, history.csv, pending_report_records.csv    | String        | System-assigned unique loan identifier. Format: `YYYY_MM_<order>`. YYYY = year of entry, MM = month of entry (zero-padded), order = sequential counter padded to minimum 3 digits. Never user-editable. |
| borrower_name           | loans.csv, history.csv, pending_report_records.csv    | String        | Full name of the borrower. Used for autocomplete, filtering, and report grouping.                                                                                                                       |
| borrower_group          | loans.csv, history.csv                                | String        | Categorical group the borrower belongs to. Used for filtering in Interest Calculator.                                                                                                                   |
| amount                  | loans.csv, history.csv, pending_report_records.csv    | Integer (INR) | Loan principal amount in Indian Rupees. Non-negative integer. No decimal representation.                                                                                                                |
| giving_date             | loans.csv, history.csv, pending_report_records.csv    | Date (ISO 8601) | Date the loan was originally given. Reference column only; not used in interest time-period calculations.                                                                                              |
| depositor_name          | loans.csv, history.csv, pending_report_records.csv    | String        | Name of the depositor/lender. Optional; absent for some legacy records.                                                                                                                                 |
| depositor_group         | loans.csv, history.csv                                | String        | Categorical group the depositor belongs to. Optional; absent for some records. Displayed as "Unknown" in UI.                                                                                            |
| due_date                | loans.csv, history.csv, pending_report_records.csv    | Date (ISO 8601) | Date the loan repayment is due. Optional. A loan without a due_date is treated as Overdue by the status engine.                                                                                        |
| status                  | loans.csv, history.csv, pending_reports.csv           | String (Enum) | Loan lifecycle state (loans.csv/history.csv): Active, Overdue, Paidoff, Pending. Report lifecycle state (pending_reports.csv): Pending, Approved, Declined.                                             |
| paidoff_date            | history.csv                                           | Date (ISO 8601) | The date the user confirmed the loan was paid off. Written during the atomic Paidoff protocol.                                                                                                         |
| year_month              | loans_meta.csv                                        | String        | Year-month key for the reference_id counter. Format: YYYY_MM (e.g., 2026_03).                                                                                                                          |
| counter                 | loans_meta.csv, reports_meta.csv                      | Integer       | High-water-mark counter for ID generation. Represents the last issued order number for the given key. Reset to 0 when the last record for that key is deleted.                                          |
| report_id               | pending_reports.csv, pending_report_records.csv       | String        | System-assigned unique report identifier. Format: RPT_YYYYMMDD_<order> (e.g., RPT_20260320_001). YYYYMMDD = date of report generation, order = sequential counter per date.                            |
| report_creation_date    | pending_reports.csv                                   | Date (ISO 8601) | The calendar date the report was first generated. Never updated after creation.                                                                                                                        |
| report_latest_update_dt | pending_reports.csv                                   | Datetime (ISO 8601) | Full datetime of the most recent modification to the report or its records. Updated on every inline edit in the Pending Approval Tab.                                                                |
| mode                    | pending_reports.csv                                   | String (Enum) | Calculator mode used when the report was generated. One of: Monthly, Daily, Both.                                                                                                                       |
| interest_rate           | pending_report_records.csv                            | Float         | Annual percentage rate of interest assigned by the depositor. Applied to calculate interest_amount. Example: 12.0 represents 12% per annum.                                                            |
| commission_rate         | pending_report_records.csv                            | Float         | Annual percentage commission rate owed by the borrower on top of interest. Applied to calculate commission_amount.                                                                                      |
| extension_period        | pending_report_records.csv                            | Integer       | Duration of the loan extension. Positive integer. Unit determined by extension_period_unit.                                                                                                             |
| extension_period_unit   | pending_report_records.csv                            | String (Enum) | Unit for extension_period. One of: months, days (lowercase).                                                                                                                                           |
| tds_flag                | pending_report_records.csv                            | Boolean       | Whether Tax Deducted at Source (TDS) is applicable. Stored as lowercase string: true or false. Default: false.                                                                                          |
| interest_amount         | pending_report_records.csv                            | Float         | Calculated interest for the extension period. Formula (Monthly): (amount * interest_rate * extension_period) / (12 * 100). Formula (Daily): (amount * interest_rate * extension_period) / (365 * 100). |
| commission_amount       | pending_report_records.csv                            | Float         | Calculated commission for the extension period. Formula mirrors interest_amount with commission_rate substituted for interest_rate.                                                                     |
| tds_amount              | pending_report_records.csv                            | Float         | Calculated TDS. Equal to 0.1 * interest_amount when tds_flag is true, otherwise 0.0.                                                                                                                   |
| new_giving_date         | pending_report_records.csv                            | Date (ISO 8601) | Post-extension giving_date preview. Equals old due_date (or today's date if loan has no due_date). Updated in loans.csv on report Approval.                                                           |
| new_due_date            | pending_report_records.csv                            | Date (ISO 8601) | Post-extension due_date preview. Equals old due_date + extension_period (in extension_period_unit). Updated in loans.csv on report Approval.                                                          |
| report_date             | reports_meta.csv                                      | String        | Date key for report_id counter generation. Format: YYYYMMDD (e.g., 20260324).                                                                                                                          |

---

*End of DATA_MODEL.md*
