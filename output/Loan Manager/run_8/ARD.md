# Architecture Reference Document — Loan Manager MVP1

**Version**: 1.0
**Date**: 2026-09-06
**Author**: Principal Engineer / Solution Architect
**Run**: run_8 (all 6 stages complete)
**Audience**: Junior Engineers (technical) and Junior Business Analysts (business)

---

## Table of Contents

1. [What This Application Does (Business Context)](#1-what-this-application-does)
2. [Who Uses It and How](#2-who-uses-it-and-how)
3. [The Core Problem It Solves](#3-the-core-problem-it-solves)
4. [Architecture Overview](#4-architecture-overview)
5. [Layer-by-Layer Walkthrough](#5-layer-by-layer-walkthrough)
6. [Data Model](#6-data-model)
7. [Key Business Rules](#7-key-business-rules)
8. [Interest Calculation Engine](#8-interest-calculation-engine)
9. [Approval Workflow](#9-approval-workflow)
10. [How Requirements Evolved](#10-how-requirements-evolved)
11. [Architecture Decision Records (Summary)](#11-architecture-decision-records)
12. [Risks and Accepted Tradeoffs](#12-risks-and-accepted-tradeoffs)
13. [Tech Stack](#13-tech-stack)
14. [Test Coverage](#14-test-coverage)
15. [Known Limitations](#15-known-limitations)
16. [Glossary](#16-glossary)

---

## 1. What This Application Does

Loan Manager is a **single-user desktop application** for tracking informal personal loans between borrowers and depositors. Think of it as a specialised digital ledger that replaces manual spreadsheets.

**In plain terms**: A person (the depositor) lends money to another person (the borrower). This app tracks every such loan — when it was given, when it's due, whether it's overdue, how much interest has accrued, and whether the borrower has paid it off. It also generates financial reports for calculating interest, commissions, and TDS (tax deducted at source).

---

## 2. Who Uses It and How

| User | Platform | Role |
|---|---|---|
| End-user | Windows 10/11 | Creates loans, views records, generates reports, approves/declines interest calculations |
| Tester/Developer | macOS 12+ | Validates the application, manages git-based data sharing |

- **No network required** — data lives locally as a SQLite database
- **Data shared via git** — the macOS user bridges git management for the Windows end-user
- **Single user at a time** — no concurrent session handling

---

## 3. The Core Problem It Solves

### Business Problem

Managing informal loans on paper or in spreadsheets is error-prone:
- No automatic status tracking (which loans are overdue?)
- Manual interest calculations are tedious and mistake-prone
- No audit trail when loans are extended or paid off
- Generating reports for multiple borrowers requires manual aggregation

### What the App Provides

| Capability | Business Value |
|---|---|
| **Loan Entry** (R1) | Structured data capture with autocomplete and validation |
| **Loan View** (R2) | Sortable, filterable, inline-editable table — like a spreadsheet |
| **Status Engine** (R3) | Automatic Active/Overdue/Pending computation on every app launch |
| **Extend & Delete** (R4) | Modify loan terms with automatic date recalculation |
| **Interest Calculator** (R5) | Monthly/Daily/Both calculation modes with report generation |
| **Approval Workflow** (R5/R6) | Pending approval queue with preview-before-commit |
| **Import/Export** (R6) | CSV/XLSX import with conflict resolution; export for portability |
| **Modern UI** (R9) | PySide6 desktop app with themes, keyboard navigation, date pickers |

---

## 4. Architecture Overview

### For Business Analysts

The application is built in **four layers**, each with a clear responsibility. Think of it like a building:

```
┌─────────────────────────────────────────────┐
│  PRESENTATION (what the user sees & clicks) │  ← PySide6 UI: tabs, dialogs, widgets
├─────────────────────────────────────────────┤
│  APPLICATION (what happens when they click)  │  ← Use cases: "Create Loan", "Approve Report"
├─────────────────────────────────────────────┤
│  DOMAIN (the business rules)                 │  ← Status engine, interest calculator, entities
├─────────────────────────────────────────────┤
│  INFRASTRUCTURE (where data is stored)       │  ← SQLite database, CSV import/export, logging
└─────────────────────────────────────────────┘
```

**Why this matters**: If the business rules change (e.g., a new status type), we change the Domain layer. If we switch databases, we change Infrastructure. The layers don't leak into each other.

### For Engineers

This is **Clean Architecture with Lightweight DDD**:

- **Dependency Rule**: Inner layers never depend on outer layers. Domain knows nothing about SQLAlchemy or PySide6.
- **Aggregate Roots**: `Loan` and `Report` are the two aggregates.
- **Value Objects**: `ReferenceId`, `ReportId`, `Money`, `LoanStatus` — immutable, validated on construction.
- **Domain Services**: `StatusEngine`, `InterestCalculator`, `ReferenceIdService` — stateless business logic.
- **Repository Pattern**: Domain defines interfaces (`ILoanRepository`); Infrastructure provides SQLAlchemy implementations.
- **Unit of Work**: Transaction boundary managed by `SqlAlchemyUnitOfWork`.
- **DTOs**: Pydantic v2 models with field validators for data transfer between layers.
- **Event Bus**: Simple in-memory pub/sub for cross-cutting concerns (logging, recovery writes).

---

## 5. Layer-by-Layer Walkthrough

### 5.1 Domain Layer (`loan_manager/domain/`)

**Purpose**: Pure business logic. No imports from infrastructure or presentation. 100% unit-testable.

| Component | File(s) | What It Does |
|---|---|---|
| **Loan entity** | `entities/loan.py` | Aggregate root. Holds all loan fields, status, ref_id. |
| **Report entity** | `entities/report.py` | Aggregate root. Holds report_id, mode, status, list of ReportRecords. |
| **StatusEngine** | `services/status_engine.py` | Computes `Active`/`Overdue`/`Pending` from `giving_date`, `due_date`, and today. |
| **InterestCalculator** | `services/interest_calculator.py` | Monthly, Daily, Both formulas. Orchestrator function for Both mode. |
| **ReferenceIdService** | `services/reference_id_service.py` | Generates `YYYY_MM_<order>` IDs with high-water mark tracking. |
| **Value Objects** | `value_objects/*.py` | `ReferenceId` (validated format), `Money` (non-negative int), `LoanStatus`/`ReportStatus`/`CalculationMode`/`ExtensionPeriodUnit` (enums). |
| **Repository Interfaces** | `repositories/*.py` | Abstract contracts: `ILoanRepository`, `IReportRepository`, `ILoanMetaRepository`, `ILoanHistoryRepository`. |
| **Domain Events** | `events/*.py` | `LoanCreated`, `LoanExtended`, `LoanPaidOffApproved`, `ReportApproved`, `ReportDeclined`, etc. |

### 5.2 Application Layer (`loan_manager/application/`)

**Purpose**: Orchestrates use cases. Delegates to domain services. Defines DTOs.

**15 Use Cases**:

| Category | Use Cases |
|---|---|
| **Loans** | `CreateLoan`, `UpdateLoan`, `DeleteLoan`, `ExtendLoan`, `MarkPaidOff`, `RecomputeAllStatuses`, `GetLoans`, `GetAutocomplete` |
| **Reports** | `CalculateInterest`, `GenerateReport`, `ApproveReport`, `DeclineReport`, `GetReports` |
| **Data** | `ImportLoans`, `ExportLoans` |

**Key DTOs** (Pydantic v2):
- `LoanCreateDTO` — validates borrower/depositor names (lowercase normalisation), computes `due_date` from `due_period`
- `CalculationResultDTO` — carries per-record interest/commission/TDS/CHQ calculations
- `ImportPreviewDTO` — shows new vs. overwrite counts before committing imports

**Event Bus**: In-memory publish/subscribe. Used by recovery service (writes `approval_recovery.tmp` before destructive operations).

### 5.3 Infrastructure Layer (`loan_manager/infrastructure/`)

**Purpose**: External concerns — database, file I/O, logging.

| Component | What It Does |
|---|---|
| **SQLAlchemy ORM** (`database/models.py`) | 6 tables: `loans`, `loan_meta`, `loan_history`, `reports`, `report_records`, `report_meta` |
| **DatabaseSession** (`database/session.py`) | Singleton session factory for SQLite |
| **SqlAlchemyUnitOfWork** (`database/unit_of_work.py`) | Transaction boundary: `commit()` / `rollback()` |
| **4 Repository Implementations** (`repositories/`) | Implement domain interfaces using SQLAlchemy queries |
| **CsvImportService** (`csv/import_service.py`) | Parses CSV/XLSX, detects conflicts, returns preview DTO |
| **CsvExportService** (`csv/export_service.py`) | Writes active loans or reports to CSV/XLSX |
| **RecoveryService** (`recovery/recovery_service.py`) | Writes/checks `approval_recovery.tmp` for crash safety |
| **BackupService** (`recovery/backup_service.py`) | Creates timestamped data backups before destructive ops |
| **Logger** (`logging/logger.py`) | Rotating file handler → `./data/logs/app.log` (5MB max, 3 backups) |
| **CSV-to-SQLite Migration** (`migrations/csv_to_sqlite.py`) | One-time migration from legacy CSV to SQLite on first MVP1 launch |

### 5.4 Presentation Layer (`loan_manager/presentation/`)

**Purpose**: PySide6 UI. Calls application use cases. No business logic.

| Component | What It Does |
|---|---|
| **MainWindow** | Tab container + status bar |
| **EntryTab** | Loan creation form with autocomplete, date pickers, due_period→due_date auto-fill |
| **ViewTab** | QAbstractTableModel + QSortFilterProxyModel; inline editing; column filters with date hierarchy |
| **CalculatorTab** | Mode selector (Monthly/Daily/Both); 5 filter dropdowns; global inputs; Calculate → dialog |
| **PendingApprovalTab** | Report queue; inline editing of rates/periods; approve/decline; PDF print |
| **SettingsTab** | Theme selection; custom status colours |
| **DateEditFixed** | QDateEdit with `calendarPopup(True)` + `QTimer.singleShot(0, showPopup)` — fixes the `showCalendarWidget` bug |
| **LoanTableModel** | QAbstractTableModel (not QTableWidget) — handles 1500 rows efficiently |
| **ColumnFilterWidget** | Per-column filter with single-source-of-truth state management |
| **StatusComboBox** | QComboBox with theme-configurable colour coding |
| **ThemeManager** | Loads QSS stylesheets + JSON colour configs; supports dark and light themes |

---

## 6. Data Model

### For Business Analysts

The application stores data in 6 tables inside a local SQLite database (`./data/loans.db`):

| Table | Purpose | Analogy |
|---|---|---|
| `loans` | All active loan records | The main ledger |
| `loan_meta` | Counter for generating reference IDs | Page numbers for the ledger |
| `loan_history` | Archive of paid-off loans | The "completed" filing cabinet |
| `reports` | Generated interest calculation reports | Report cover pages |
| `report_records` | Line items within each report | Report detail pages |
| `report_meta` | Counter for generating report IDs | Report numbering system |

### For Engineers

**Entity-Relationship Diagram**:

```
loans (1) ─── soft ref ───── report_records (N)
  │ reference_id                  │ reference_id (snapshot)
  │                               │ report_id ──► reports (N:1)
  │                               │                  │
  │                               │            report_meta
  │                               │            (counter per YYYYMMDD)
  │
  ├──► loan_history (N)    [on paidoff approval, loan archived here]
  │      reference_id
  │
  └──► loan_meta (N)       [counter per YYYY_MM for ref_id generation]
         year_month
```

**Key Design Notes**:
- `report_records` stores **snapshots** of loan data at report-generation time (not FK references). This ensures reports remain consistent even if the loan is later deleted or modified.
- `is_active = FALSE` records stay in `loans` table for audit; the UI hides them via filter.
- All dates are ISO 8601 strings in SQLite.
- Monetary amounts are integers (whole INR rupees, no paise).

### Loans Table Schema

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Internal row ID |
| `reference_id` | VARCHAR(20) UNIQUE | `YYYY_MM_<order>` e.g. `2026_03_001` |
| `borrower_name` | VARCHAR(255) | Stored lowercase |
| `borrower_group` | VARCHAR(255) | Stored lowercase |
| `depositor_name` | VARCHAR(255) | Stored lowercase |
| `depositor_group` | VARCHAR(255) NULLABLE | NULL → "Unknown" in UI |
| `amount` | INTEGER | INR, non-negative |
| `giving_date` | DATE | Reference only — never used in calculations |
| `due_period` | INTEGER NULLABLE | Months; derives due_date |
| `due_date` | DATE NULLABLE | NULL → "Unknown" in UI |
| `status` | VARCHAR(10) | `Active` / `Overdue` / `Pending` / `Paidoff` |
| `is_active` | BOOLEAN | FALSE = hidden (paidoff) |
| `created_at` | DATETIME | UTC |
| `updated_at` | DATETIME | UTC |

---

## 7. Key Business Rules

### 7.1 Status Engine

The application automatically determines loan status on every launch:

```
                  ┌─────────────────────┐
                  │ giving_date > today? │
                  └─────────┬───────────┘
                     YES    │    NO
                      ▼     │     ▼
                  ┌────────┐│ ┌──────────────┐
                  │PENDING ││ │due_date NULL? │
                  └────────┘│ └──────┬───────┘
                            │   YES  │   NO
                            │    ▼   │    ▼
                            │┌───────┐│┌────────────────┐
                            ││OVERDUE│││today < due_date?│
                            │└───────┘│└────────┬───────┘
                            │         │  YES    │   NO
                            │         │   ▼     │    ▼
                            │         │┌──────┐ │┌───────┐
                            │         ││ACTIVE│ ││OVERDUE│
                            │         │└──────┘ │└───────┘
```

**Critical rule**: `giving_date` is **never** used in interest calculations. It is purely a reference date for when the loan was disbursed.

### 7.2 Status Colours (Configurable via Theme)

| Status | Default Colour | Text |
|---|---|---|
| Active | `#025c33` (dark green) | Bold white |
| Overdue | `#6b0307` (dark red) | Bold white |
| Pending | `#804001` (dark amber) | Bold white |
| Paidoff | `#022a52` (dark grey-blue) | Bold white |

These are stored in theme JSON config files, not hardcoded.

### 7.3 Reference ID Format

Format: `YYYY_MM_<order>` — e.g., `2026_03_001`, `2026_03_002`, ..., `2026_12_999`, `2026_12_1000`

- Counter is **per YYYY_MM period**, tracked in `loan_meta` table
- Deletion does **not** reuse vacated numbers (high-water mark only increments)
- If all records for a YYYY_MM are deleted, counter resets to 001 for next entry in that month
- On import collision: auto-increment until non-colliding ID found

### 7.4 Paidoff Flow

```
User right-clicks loan → "Mark Paidoff"
  ├── Blocked if no due_date
  ├── Blocked if pending Paidoff report already exists
  │
  ▼
PaidOff Dialog: paidoff_date, interest_rate, commission_rate, tds_flag
  │
  ▼
Daily calculation: extension_period(days) = paidoff_date − due_date
  │
  ▼
Report sent to Pending Approval queue
  │
  ├── Approved → loan archived to loan_history, marked is_active=FALSE
  │               Warning: "This report was generated for a Paidoff loan."
  │
  └── Declined → no changes, loan remains in View Tab
```

### 7.5 Extend Flow

```
User selects loan → "Extend"
  │
  ▼
ExtendDialog: extension_period_unit (months/days), extension_period
  │
  ▼
new giving_date = old due_date
new due_date = old due_date + extension_period
  │
  ▼
Record overwritten (ref_id reused, history loss accepted)

Special case: loan with no due_date
  → new giving_date = today
  → new due_date = user picks via date picker
```

---

## 8. Interest Calculation Engine

### Formulas

| Mode | Formula | Divisor |
|---|---|---|
| **Monthly** | `(Amount × Rate × Period) / 1200` | 12 × 100 |
| **Daily** | `(Amount × Rate × Period) / 36500` | 365 × 100 |
| **Both** | Per-record; uses the record's own unit | Dispatches to Monthly or Daily |

Where:
- `Rate` = `interest_rate` or `commission_rate` (percentage)
- `Period` = `extension_period` (months or days)
- `TDS = 0.1 × Interest` (when `tds_flag` is true)
- `CHQ_Amt = Interest − TDS`

**Critical**: `giving_date` is **excluded** from all time-period calculations. Only `extension_period` counts. This was an authoritative design decision that overrode the previous prototype's behaviour.

### Example

A Rs 10,000 loan at 12% interest with 3-month original term + 1-month extension:
- Monthly interest = `(10000 × 12 × 1) / 1200 = Rs 100`
- Only the extension window is charged, not the original term.

### Calculator Filters

Users can combine up to 5 filters before calculating:

| Filter | Source |
|---|---|
| Borrower Group | Distinct values from active loans |
| Borrower Name | Distinct values from active loans |
| Depositor Name | Distinct values from active loans |
| Depositor Group | Distinct values from active loans (includes "Unknown") |
| ByMonth | Months with due_dates in current calendar year + overdue records |

**Filter rule**: No filter applied → show all records with no `due_date`. Any filter applied → exclude records without `due_date`, show only matching.

---

## 9. Approval Workflow

### Report Lifecycle

```
Calculator Tab                 Pending Approval Tab
┌──────────────┐              ┌───────────────────────────┐
│ Select Mode  │              │  Report Queue             │
│ Apply Filters│              │  ┌───────────────────┐    │
│ Enter Rates  │──Generate──►│  │ RPT_20260320_001  │    │
│ Calculate    │   Report     │  │ Status: Pending    │    │
│ Review Dialog│              │  │ [Approve] [Decline]│    │
└──────────────┘              │  └───────────────────┘    │
                               │                           │
                               │  On Approve:              │
                               │  ├─ Check duplicate refs  │
                               │  ├─ Check deleted loans   │
                               │  ├─ Write recovery file   │
                               │  ├─ Update loans table    │
                               │  ├─ Mark report approved  │
                               │  └─ Clear recovery file   │
                               │                           │
                               │  On Decline:              │
                               │  └─ Delete report+records │
                               └───────────────────────────┘
```

### Report Display Fields

The Pending Approval tab shows **both** pre-extension and post-extension values:

| Column | Meaning | Editable? |
|---|---|---|
| `giving_date` | Original giving date (pre-extension) | No |
| `due_date` | Original due date (pre-extension) | No |
| `post_extension_giving_date` | New giving date after approval | Computed |
| `post_extension_due_date` | New due date after approval | Computed |
| `interest_rate`, `commission_rate`, `extension_period`, `tds_flag` | Calculator parameters | Yes (inline) |
| `interest_amount`, `commission_amount`, `tds_amount`, `chq_amount` | Calculated results | Auto-recalculated on edit |

### Conflict Handling

1. **Duplicate ref_ids across pending reports**: Warning → "This report shares loan records with another pending report. Approving may overwrite previous updates." → Proceed / Cancel
2. **Deleted loans in report**: Warning → "Records in this report have been deleted." → Ignore (skip deleted) / Decline
3. **Crash safety**: `approval_recovery.tmp` written before first write; cleared after commit; checked on next startup

---

## 10. How Requirements Evolved

The application was built through **iterative prompt refinements**, not a single specification. Understanding this history explains why certain components exist.

| Input File | Role | Key Changes |
|---|---|---|
| `REQUIREMENTS.md` | Original specification | 10 core requirements + sample data + priority order |
| `prompt.md` | Stage-gated build prompt | 6-stage delivery model with explicit approval gates |
| `prompt_fix_20260705.md` | Bug fix iteration 1 | View Tab filtering broken, date filtering incorrect, print support, report formatting |
| `prompt_fix_20240705_ui.md` | Bug fix iteration 2 | Print margins, report layout tables, checkbox state sync, numeric SNo sorting |
| `prompt_fix_20260705_ui.md` | Architecture correction | Filter state management redesigned — single source of truth for checkbox state |
| `prompt_fix_20260708.md` | Cross-platform & compatibility | macOS filter sync, Python 3.13 compat, report shows post-approval preview values |

### Evolution Timeline

```
REQUIREMENTS.md ──► prompt.md (6-stage build)
                         │
                    run_8 Stages 1-6
                         │
                    prompt_fix_20260705.md (filter + print bugs)
                         │
                    prompt_fix_20240705_ui.md (layout + state sync)
                         │
                    prompt_fix_20260705_ui.md (filter architecture rewrite)
                         │
                    prompt_fix_20260708.md (cross-platform + Python 3.13 + report preview)
```

### Key Architectural Pivots

1. **CSV → SQLite** (CHG-001): Original spec assumed CSV-only; user required SQLite for MVP1. CSV import/export retained for portability.
2. **Hardcoded colours → ThemeManager** (CHG-002): Status colours moved from hardcoded hex to JSON config files.
3. **Filter state rewrite** (prompt_fix_20260705_ui.md): The most significant post-build change. Filter popup was redesigned from scratch with a single-source-of-truth `FilterState` model — popup became a pure view.
4. **Date picker fix** (UTR-1): `showCalendarWidget()` doesn't exist in PySide6. Fixed with `setCalendarPopup(True)` + `QTimer.singleShot(0, ...)`.
5. **giving_date exclusion** (A-05): Authoritative decision that `giving_date` is never used in interest calculations. Previous prototype behaviour was overridden.

---

## 11. Architecture Decision Records

| ADR | Decision | Why |
|---|---|---|
| ADR-001 | Clean Architecture + Lightweight DDD | Domain layer is pure Python, testable without DB/UI. Prevents business logic leaking into UI (a problem in the previous prototype). |
| ADR-002 | SQLite + SQLAlchemy 2.x + Alembic | SQLite bundled with Python (zero install); SQLAlchemy provides type-safe ORM + transactions; Alembic for schema versioning. CSV retained for import/export. |
| ADR-003 | QAbstractTableModel (not QTableWidget) | For 1500 rows with inline editing + sort + filter, QTableWidget creates one widget per cell and becomes sluggish. QAbstractTableModel + QSortFilterProxyModel is performant. |
| ADR-004 | Date picker via calendarPopup + QTimer | `QDateEdit.showCalendarWidget()` doesn't exist. `setCalendarPopup(True)` + `QTimer.singleShot(0, showPopup)` avoids focus recursion on Tab. |
| ADR-005 | Configurable theme + status colours in JSON | No hardcoded hex in UI code. Theme files (`dark_config.json`, `light_config.json`) define all colours. |
| ADR-006 | Pydantic v2 DTOs with field validators | Validates data at layer boundaries. Lowercase normalisation for names, non-negative amounts, due_date auto-computation. |

---

## 12. Risks and Accepted Tradeoffs

| Risk | Severity | Decision |
|---|---|---|
| **Data loss on Extend** — overwrites giving_date/due_date with no history | Medium | Accepted. Simplicity over auditability. Post-MVP: append-only audit log. |
| **Crash between dual writes** — paidoff approval writes to both loans and history | Medium | Mitigated: `approval_recovery.tmp` written before first write. Full atomic rollback deferred. |
| **No file locking** — two instances could corrupt data | Low | Accepted. Single-user app; not worth the complexity. |
| **Duplicate ref_ids in pending reports** — approving one silently overwrites the other | Medium | Mitigated: User warned on approval. Silent overwrite is the defined behaviour if user proceeds. |
| **Status recompute overrides manual toggles** — user sets Active, next launch reverts to Overdue | Low | By design. Exception: Manual Active override prompts for new due_date (Extend flow). |
| **macOS popup rendering** — Qt platform differences | Low | Mitigated: Deferred render via `QTimer.singleShot(0, ...)` for macOS compositor compatibility. |

---

## 13. Tech Stack

| Component | Choice | Version | Why |
|---|---|---|---|
| Language | Python | >= 3.10 | User requirement; wide ecosystem |
| GUI Framework | PySide6 | >= 6.8.0 | Cross-platform Qt; Python 3.13 support from 6.8.0 |
| ORM | SQLAlchemy | >= 2.0.0 | Type-safe, modern ORM API |
| Migrations | Alembic | >= 1.13.0 | Schema versioning |
| Validation/DTOs | Pydantic | >= 2.5.0 | Field validators, model validators |
| Database | SQLite | bundled | Zero-install; sufficient for ~1500 records |
| Excel I/O | openpyxl | >= 3.1.2 | XLSX read/write |
| Date Arithmetic | python-dateutil | >= 2.8.2 | `relativedelta` for month addition |
| Testing | pytest + pytest-cov | >= 8.0 / >= 5.0 | Modern test discovery; coverage reporting |

### Platform Compatibility

| Platform | Status |
|---|---|
| Windows 10/11 | Supported (primary) |
| macOS 12+ (Intel & Apple Silicon) | Supported (deferred render for popups) |
| Python 3.10–3.12 | Fully supported |
| Python 3.13 | Supported (requires PySide6 >= 6.8.0) |
| Python 3.14 | Untested (monitor PySide6 releases) |

---

## 14. Test Coverage

| Category | Count | Coverage |
|---|---|---|
| Unit tests (domain services + entities) | ~100 | 100% (domain services) |
| Integration tests (repositories, flows) | ~28 | — |
| Smoke tests (end-to-end domain verification) | 22 | — |
| **Total** | **150 passed, 0 failed** | **89%** (target: 85%) |

### What's Tested

- StatusEngine: all status transitions, edge cases (no due_date, future giving_date)
- InterestCalculator: monthly, daily, both, TDS, CHQ, orchestrator
- ReferenceIdService: generation, overflow, counter reset, collision resolution
- Loan/Report entities: construction, validation
- Repositories: CRUD against in-memory SQLite
- Filter logic: `bg3` → 2 records, `dg3` → 4 records (from sample data)
- Approval flow: approve, decline, duplicate ref_id warning, deleted-loan handling
- Import/export: CSV parsing, XLSX, conflict detection, preview DTO

### What's Not Tested

- PySide6 UI (no UI automation in prototype scope)
- Theme rendering (verified by import and code review only)
- Cross-platform visual parity (tested manually)

---

## 15. Known Limitations

| Limitation | Impact | Planned |
|---|---|---|
| PDF via system print dialog only | No styled PDF; relies on OS print-to-PDF | Post-MVP: reportlab/weasyprint |
| No "fill all rows" shortcut in Calculator | Higher data-entry burden for >10 records | Post-MVP feature |
| Timestamped backup partial | Wired for ApproveReport; deferred for Paidoff | Post-MVP |
| No UI tests | Feature correctness validated manually | Post-MVP |
| No batch write optimisation | O(N) per recompute on startup | Post-MVP (BL-22) |

---

## 16. Glossary

| Term | Definition |
|---|---|
| **Borrower** | The person who receives the loan |
| **Depositor** | The person who lends the money |
| **Giving Date** | Date the loan was disbursed (reference only — never used in calculations) |
| **Due Date** | Date the loan is expected to be repaid |
| **Extension Period** | Additional time granted beyond the original due date |
| **Reference ID** | Unique loan identifier in `YYYY_MM_<order>` format |
| **Report ID** | Unique report identifier in `RPT_YYYYMMDD_<order>` format |
| **TDS** | Tax Deducted at Source; `0.1 × Interest Amount` |
| **CHQ Amount** | Cheque amount; `Interest Amount − TDS` |
| **Paidoff** | Loan fully repaid; archived to history and hidden from active view |
| **Pending** | Loan with a future giving_date; not yet active |
| **Overdue** | Loan past its due_date (or no due_date with past giving_date) |
| **Active** | Loan currently within its term (giving_date ≤ today < due_date) |
| **Aggregate Root** | DDD concept: the top-level entity that controls access to its child objects |
| **Value Object** | DDD concept: an immutable object defined by its attributes, not an ID |
| **Use Case** | A single unit of application behaviour (e.g., "Create Loan") |
| **DTO** | Data Transfer Object; carries data between layers without business logic |
| **UoW** | Unit of Work; transaction boundary that commits or rolls back all changes together |
| **QAbstractTableModel** | Qt model class for efficient table data — better than QTableWidget for large datasets |
| **QSortFilterProxyModel** | Qt proxy that adds sorting and filtering on top of a table model |
