# Loan Manager — Repository WIKI

> **LLM-friendly knowledge base** for the Loan Manager codebase.
> Structured for maximum context retrieval by both humans and language models.
> Follows Andrej Karpathy's LLM Wiki approach: flat, self-contained sections with explicit cross-references; no implicit knowledge required.

---

## 0. How to Read This WIKI

This document is a **complete knowledge map** of the Loan Manager repository. It is designed so that:

1. A **new engineer** can locate any file, understand any component, and trace any workflow within minutes.
2. An **LLM agent** can retrieve precise, grounded context about the codebase without hallucinating file paths or business rules.
3. A **business stakeholder** can read Sections 1–3 and understand what the system does without reading code.

**Conventions used**:
- `[FILE: path/to/file.py]` = clickable pointer to an actual file in the repository
- `[DECISION: ADR-NNN]` = references an Architecture Decision Record
- `[RULE: BR-NN]` = references a Business Requirement
- `→` = "leads to" or "calls"
- Section headers are flat (no deep nesting) for maximum LLM retrieval accuracy

---

## 1. The Problem

An individual/small-to-medium businesses' manage dozens to hundreds (max thousands) of Business loans monthly — money lent to various borrowers through various trusted-partner lenders/investors for regular Business Operation purposes. Business owners have an overhead in updating and keeping track of them typically via spreadsheets.

**Pain points being solved**:
- If Human Business Owner forgets, then who reminds which loans are overdue and since when?
- Interest calculations across different rates, periods, and modes are error-prone
- No structured approval workflow for a loan: business owner has to rummage spreadsheet to generate report on a ad-hoc basis
- No import/export: data lives in fragile spreadsheets
- No auditability: extending a loan loses the original dates

**MVP1 Scale**: ~1500 loans maximum. Single user on Windows (production) and macOS (testing/dev). No network. No concurrent sessions.

---

## 2. The Solution

A **PySide6 desktop application** with five tabs:

| Tab | Purpose | Key Workflows |
|---|---|---|
| **Entry** | Create new loan records | Form → validate → save → status bar confirmation |
| **View** | Browse, sort, filter, edit, delete, extend, mark paidoff | QAbstractTableModel; column filters; context menu actions |
| **Calculator** | Calculate interest/commission across filtered loans | Mode select → filter → global inputs → calculate → preview → generate report |
| **Pending Approval** | Review and approve/decline generated reports | Inline editing → recalculate → approve (update loans) or decline (discard) |
| **Settings** | Theme selection, custom colours | Dark/Light themes; configurable status colours |

**Architecture**: Clean Architecture + Lightweight DDD, 4 layers (Domain → Application → Infrastructure → Presentation).

**Storage**: SQLite via SQLAlchemy. CSV/XLSX import/export for portability.

---

## 3. Key Business Rules (Authoritative)

These rules are the **single source of truth**. If code conflicts with these, the rules win.

### 3.1 giving_date Is Never Used in Calculations

`giving_date` is a reference column only. Interest is calculated using `extension_period` alone.

**Example**: Rs 10,000 at 12% with 1-month extension → `(10000 × 12 × 1) / 1200 = Rs 100`.

### 3.2 Status Computation

Evaluated on every app launch via `StatusEngine.compute()`:

```python
if giving_date > today:        → PENDING
if due_date is None:            → OVERDUE
if today < due_date:            → ACTIVE
else:                           → OVERDUE
```

`[FILE: src/Loan Manager/loan_manager/domain/services/status_engine.py]`

### 3.3 Interest Formulas

- **Monthly**: `(Amount × Rate × Months) / 1200`
- **Daily**: `(Amount × Rate × Days) / 36500`
- **TDS**: `0.1 × Interest` (when flag is true)
- **CHQ_Amt**: `Interest − TDS`

`[FILE: src/Loan Manager/loan_manager/domain/services/interest_calculator.py]`

### 3.4 ByMonth Filter Behaviour

- No filter applied → show all records with no due_date
- ByMonth filter applied → **exclude** records without due_date; show only records whose due_date falls in the selected month of the current calendar year, plus overdue records
- All other filters → include no-due-date records if they match other criteria

### 3.5 Extend Overwrites History

When a loan is extended (R4) or batch-extended via Pending Approval (R5), the record is **overwritten**: new `giving_date` replaces old `due_date`, new `due_date` replaces old `due_date + extension_period`. History loss is explicitly accepted.

### 3.6 Paidoff Is Irreversible In-App

Paidoff loans are archived to `loan_history`, marked `is_active=FALSE` in `loans`, and hidden from the View Tab. To reverse: manually edit the database or CSV and re-import.

---

## 4. Repository File Navigation Index

### 4.1 Root Structure

```
FinHive/
├── input/                          # Requirements and prompt specifications
│   ├── REQUIREMENTS.md             # Authoritative business requirements (R1–R10)
│   ├── prompt.md                   # 6-stage build prompt
│   ├── prompt_fix_20260705.md      # Bug fix iteration 1
│   ├── prompt_fix_20240705_ui.md   # Bug fix iteration 2
│   ├── prompt_fix_20260705_ui.md   # Filter architecture rewrite
│   └── prompt_fix_20260708.md      # Cross-platform + Python 3.13 + report preview
│
├── output/Loan Manager/run_8/      # Current run's design artifacts
│   ├── FINAL_REVIEW.md             # Signoff document
│   ├── ARD.md                      # Architecture Reference Document (this run)
│   ├── WIKI.md                     # This file
│   └── docs/                       # Design documents
│       ├── business_requirements.md
│       ├── technical_design_document.md
│       ├── data_model.md
│       ├── migration_strategy.md
│       ├── api_boundaries.md
│       ├── ui_wireframes.md
│       ├── assumptions.md
│       ├── risks_and_tradeoffs.md
│       ├── backlog.md
│       ├── open_questions.md
│       ├── stage_log.md
│       ├── stage_review.md
│       ├── stage2_review.md
│       └── architecture_decision_records/
│           ├── ADR-001-clean-architecture.md
│           ├── ADR-002-sqlite-sqlalchemy.md
│           ├── ADR-003-pyside6-tablemodel.md
│           ├── ADR-004-date-picker-fix.md
│           ├── ADR-005-configurable-theme.md
│           └── ADR-006-pydantic-dtos.md
│
├── src/Loan Manager/               # Application source code
│   ├── loan_manager/               # Python package root
│   │   ├── main.py                 # Entry point
│   │   ├── config.py               # Paths: DATA_DIR, DB_PATH, LOG_FILE, etc.
│   │   ├── container.py            # DI wiring (ApplicationServiceLocator)
│   │   ├── domain/                 # Layer 1: Business rules
│   │   ├── application/            # Layer 2: Use cases + DTOs
│   │   ├── infrastructure/         # Layer 3: Database + CSV + logging
│   │   └── presentation/           # Layer 4: PySide6 UI
│   ├── data/                       # Runtime data directory
│   │   ├── loans.db                # SQLite database
│   │   └── logs/app.log            # Application log
│   ├── tests/                      # Test suite
│   ├── user_guides/                # End-user documentation
│   ├── docs/                       # Source-level architecture docs
│   │   ├── filter_architecture.md
│   │   ├── compatibility.md
│   │   └── report_calculation_flow.md
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── run_windows.bat
│   ├── run_mac.sh
│   └── README.md
│
├── .claude/                        # FinHive agent/skill definitions
│   ├── agents/                     # Subagent definitions
│   └── skills/                     # Domain skill definitions
│
└── CLAUDE.md                       # Project-level instructions for Claude
```

### 4.2 Domain Layer — `loan_manager/domain/`

| File | Purpose | Key Exports |
|---|---|---|
| `entities/loan.py` | Loan aggregate root | `Loan` dataclass |
| `entities/report.py` | Report aggregate root + ReportRecord | `Report`, `ReportRecord` dataclasses |
| `value_objects/status.py` | All enums | `LoanStatus`, `ReportStatus`, `CalculationMode`, `ExtensionPeriodUnit` |
| `value_objects/reference_id.py` | Validated loan ref_id | `ReferenceId` (frozen dataclass, regex-validated) |
| `value_objects/report_id.py` | Validated report ref_id | `ReportId` |
| `value_objects/money.py` | Non-negative integer amount | `Money` |
| `services/status_engine.py` | Status computation | `StatusEngine.compute(giving_date, due_date, today) → LoanStatus` |
| `services/interest_calculator.py` | Interest/commission/TDS/CHQ | `InterestCalculator.calculate_monthly()`, `.calculate_daily()`, `.calculate_both_orchestrator()` |
| `services/reference_id_service.py` | ID generation | `ReferenceIdService.next_id(year_month, current_high_water) → ReferenceId` |
| `repositories/loan_repository.py` | Loan repo interface | `ILoanRepository` (abstract) |
| `repositories/report_repository.py` | Report repo interface | `IReportRepository` (abstract) |
| `repositories/loan_meta_repository.py` | Meta repo interface | `ILoanMetaRepository` (abstract) |
| `repositories/history_repository.py` | History repo interface | `ILoanHistoryRepository` (abstract) |
| `events/loan_events.py` | Loan domain events | `LoanCreated`, `LoanExtended`, `LoanPaidOffRequested`, `LoanPaidOffApproved` |
| `events/report_events.py` | Report domain events | `ReportGenerated`, `ReportApproved`, `ReportDeclined` |

### 4.3 Application Layer — `loan_manager/application/`

| File | Purpose |
|---|---|
| `use_cases/loans/create_loan.py` | Create a new loan record |
| `use_cases/loans/update_loan.py` | Update an existing loan inline |
| `use_cases/loans/delete_loan.py` | Delete a loan record |
| `use_cases/loans/extend_loan.py` | Extend a loan (new giving_date = old due_date) |
| `use_cases/loans/mark_paidoff.py` | Initiate paidoff flow (generates Daily report) |
| `use_cases/loans/recompute_statuses.py` | Batch recompute all loan statuses (called on startup) |
| `use_cases/loans/get_loans.py` | Query loans (all active, by filter, by ID) |
| `use_cases/loans/get_autocomplete.py` | Get distinct values for autocomplete dropdowns |
| `use_cases/reports/calculate_interest.py` | Run interest calculation on filtered loans |
| `use_cases/reports/generate_report.py` | Create Report + ReportRecords from calculation results |
| `use_cases/reports/approve_report.py` | Approve a pending report (update loans, handle conflicts) |
| `use_cases/reports/decline_report.py` | Decline a pending report (delete report + records) |
| `use_cases/reports/get_reports.py` | Query pending/approved/declined reports |
| `use_cases/data/import_loans.py` | Import CSV/XLSX with conflict detection |
| `use_cases/data/export_loans.py` | Export active loans to CSV/XLSX |
| `dtos/loan_dto.py` | `LoanCreateDTO`, `LoanUpdateDTO`, `LoanDTO` (Pydantic v2) |
| `dtos/report_dto.py` | `ReportDTO`, `ReportRecordDTO` |
| `dtos/calculation_dto.py` | `CalculationResultDTO`, `CalculationLineDTO` |
| `dtos/import_dto.py` | `ImportPreviewDTO` |
| `interfaces/unit_of_work.py` | `IUnitOfWork` abstract (context manager) |
| `event_bus.py` | In-memory publish/subscribe `EventBus` |

### 4.4 Infrastructure Layer — `loan_manager/infrastructure/`

| File | Purpose |
|---|---|
| `database/models.py` | SQLAlchemy ORM: `LoanModel`, `LoanMetaModel`, `LoanHistoryModel`, `ReportModel`, `ReportRecordModel`, `ReportMetaModel` |
| `database/session.py` | `DatabaseSession` singleton factory |
| `database/unit_of_work.py` | `SqlAlchemyUnitOfWork` (implements `IUnitOfWork`) |
| `repositories/sqlalchemy_loan_repo.py` | `SqlAlchemyLoanRepository` (implements `ILoanRepository`) |
| `repositories/sqlalchemy_report_repo.py` | `SqlAlchemyReportRepository` (implements `IReportRepository`) |
| `repositories/sqlalchemy_meta_repo.py` | `SqlAlchemyLoanMetaRepository` (implements `ILoanMetaRepository`) |
| `repositories/sqlalchemy_history_repo.py` | `SqlAlchemyLoanHistoryRepository` (implements `ILoanHistoryRepository`) |
| `csv/import_service.py` | `CsvImportService` — CSV/XLSX parser, conflict detector |
| `csv/export_service.py` | `CsvExportService` — CSV/XLSX writer |
| `migrations/csv_to_sqlite.py` | One-time migration tool from legacy CSV files to SQLite |
| `recovery/recovery_service.py` | `RecoveryService` — writes/checks `approval_recovery.tmp` |
| `recovery/backup_service.py` | `BackupService` — timestamped backups before destructive ops |
| `logging/logger.py` | `setup_logging()`, `get_logger()` — rotating file handler |

### 4.5 Presentation Layer — `loan_manager/presentation/`

| File | Purpose |
|---|---|
| `main_window.py` | `MainWindow` — QMainWindow with tab container + status bar |
| `tabs/entry_tab.py` | `EntryTab` — loan creation form |
| `tabs/view_tab.py` | `ViewTab` — sortable/filterable table with context menu |
| `tabs/calculator_tab.py` | `CalculatorTab` — mode selector, filters, global inputs, Calculate button |
| `tabs/pending_approval_tab.py` | `PendingApprovalTab` — report queue, inline editing, approve/decline |
| `tabs/settings_tab.py` | `SettingsTab` — theme picker, custom colour controls |
| `dialogs/date_picker_dialog.py` | `DatePickerDialog` — standalone calendar popup |
| `dialogs/extend_dialog.py` | `ExtendDialog` — extension_period_unit + extension_period inputs |
| `dialogs/paidoff_dialog.py` | `PaidOffDialog` — paidoff_date, rates, TDS flag |
| `dialogs/calculation_dialog.py` | `CalculationDialog` — inline-editable calculation results preview |
| `dialogs/import_preview_dialog.py` | `ImportPreviewDialog` — new/overwrite counts before import commit |
| `widgets/date_edit.py` | `DateEditFixed` — QDateEdit with calendarPopup(True) + QTimer fix |
| `widgets/loan_table_model.py` | `LoanTableModel` — QAbstractTableModel + QSortFilterProxyModel |
| `widgets/column_filter_widget.py` | `ColumnFilterWidget` — per-column filter with FilterState (single source of truth) |
| `widgets/status_combobox.py` | `StatusComboBox` — QComboBox with theme-configured colours |
| `widgets/report_printer.py` | `ReportPrinter` — print/PDF output formatting |
| `view_models/loan_view_model.py` | `LoanViewModel` — maps LoanDTO to display strings + colours |
| `view_models/report_view_model.py` | `ReportViewModel` — maps ReportDTO to display strings |
| `themes/theme_manager.py` | `ThemeManager` — loads QSS + JSON config; applies to QApplication |

---

## 5. Data Flow Diagrams

### 5.1 Startup Sequence

```
main.py
  │
  ├─ 1. setup_logging()           → ./data/logs/app.log
  ├─ 2. RecoveryService.exists()  → warn if approval_recovery.tmp found
  ├─ 3. DatabaseSession.initialize() → create tables in ./data/loans.db
  ├─ 4. Container()               → wire DI: recovery, backup, event_bus
  ├─ 5. RecomputeAllStatuses.execute()
  │        → for each active loan: StatusEngine.compute() → update status
  └─ 6. QApplication + MainWindow → launch PySide6 UI with saved theme
```

`[FILE: src/Loan Manager/loan_manager/main.py]`

### 5.2 Create Loan Flow

```
EntryTab (form submit)
  → LoanCreateDTO (Pydantic validation: lowercase names, compute due_date from due_period)
    → CreateLoan use case
      → ReferenceIdService.next_id() → generate YYYY_MM_<order>
      → StatusEngine.compute() → determine initial status
      → ILoanRepository.add(loan)
      → ILoanMetaRepository.update_counter()
      → UoW.commit()
      → EventBus.publish(LoanCreated)
  → status bar: "Loan saved successfully. Reference ID: {ref_id}."
```

### 5.3 Interest Calculation → Report → Approval Flow

```
CalculatorTab
  ├─ Select mode (Monthly / Daily / Both)
  ├─ Apply filters (up to 5)
  ├─ Enter global: interest_rate, commission_rate, extension_period, tds_flag
  ├─ Click "Calculate"
  │     → CalculateInterest use case
  │       → InterestCalculator.calculate() or .calculate_both_orchestrator()
  │       → returns CalculationResultDTO (per-record: interest, commission, TDS, CHQ)
  │       → also computes post_extension_giving_date, post_extension_due_date
  │
  ├─ CalculationDialog (preview: inline-editable, auto-recalculates)
  │
  └─ Click "Generate Report"
        → GenerateReport use case
          → create Report + ReportRecords in database
          → stores BOTH pre-extension and post-extension dates
          → report appears in PendingApprovalTab

PendingApprovalTab
  ├─ Shows pre-extension dates (read-only) + post-extension dates (computed preview)
  ├─ Inline edit: rates, period, unit, TDS flag → auto-recalculate amounts
  │
  ├─ Click "Approve"
  │     → ApproveReport use case
  │       → check duplicate ref_ids → warn if conflict
  │       → check deleted loans → warn if any missing
  │       → RecoveryService.write_recovery()
  │       → UoW: update loans (new dates), mark report approved
  │       → RecoveryService.clear_recovery()
  │       → EventBus.publish(ReportApproved)
  │       → For Paidoff: archive to loan_history, mark is_active=FALSE
  │
  └─ Click "Decline"
        → DeclineReport use case
          → delete report + records from database
          → no loan updates
```

`[FILE: src/Loan Manager/loan_manager/application/use_cases/reports/calculate_interest.py]`
`[FILE: src/Loan Manager/loan_manager/application/use_cases/reports/approve_report.py]`
`[FILE: src/Loan Manager/docs/report_calculation_flow.md]`

### 5.4 Filter State Architecture

```
ColumnFilterWidget (owns FilterState)
  │
  │  committed: set    ← what is applied to the table
  │  pending: set      ← what is shown in the open popup
  │
  ├── On popup open:
  │     pending = committed.copy()
  │     popup.render(all_values, pending)
  │
  ├── On item click:
  │     popup emits item_toggled → widget updates pending → widget updates popup visual
  │
  ├── On Apply:
  │     committed = pending.copy() → popup.hide() → filter_changed.emit()
  │
  ├── On Cancel:
  │     pending = committed.copy() → popup.hide()
  │
  └── On Clear:
        committed = set(); pending = set() → popup.hide() → filter_changed.emit()

INVARIANT: popup checkbox state == pending == committed (after Apply) == table filter
```

`[FILE: src/Loan Manager/docs/filter_architecture.md]`
`[FILE: src/Loan Manager/loan_manager/presentation/widgets/column_filter_widget.py]`

---

## 6. Database Schema

### Tables

| Table | Row Count (expected) | Purpose |
|---|---|---|
| `loans` | ~1500 max | Active loan records |
| `loan_meta` | ~12/year | High-water counter per YYYY_MM |
| `loan_history` | grows over time | Archived paidoff loans |
| `reports` | varies | Report header metadata |
| `report_records` | varies (N per report) | Report line items (loan snapshots) |
| `report_meta` | ~365/year | Daily counter for report IDs |

### Entity-Relationship

```
loans ──(soft ref by reference_id)── report_records ──(FK report_id)── reports
  │                                                                       │
  └──(on paidoff)── loan_history                                    report_meta

loans ──(derived YYYY_MM)── loan_meta
```

**Key**: `report_records` stores **snapshots** of loan data at report time, not live FK references. This means reports remain consistent even if the loan is later modified or deleted.

`[FILE: src/Loan Manager/loan_manager/infrastructure/database/models.py]`
`[FILE: output/Loan Manager/run_8/docs/data_model.md]`

---

## 7. Configuration & Paths

All paths are defined in `[FILE: src/Loan Manager/loan_manager/config.py]`:

| Constant | Value | Purpose |
|---|---|---|
| `BASE_DIR` | `loan_manager/` parent | Package root |
| `DATA_DIR` | `BASE_DIR / "data"` | All runtime data |
| `DB_PATH` | `DATA_DIR / "loans.db"` | SQLite database |
| `LOG_DIR` | `DATA_DIR / "logs"` | Log directory |
| `LOG_FILE` | `LOG_DIR / "app.log"` | Application log (5MB rotating, 3 backups) |
| `RECOVERY_FILE` | `DATA_DIR / "approval_recovery.tmp"` | Crash recovery marker |
| `BACKUP_DIR` | `DATA_DIR / "backups"` | Timestamped backups |
| `SETTINGS_FILE` | `DATA_DIR / "settings.json"` | User preferences (theme, custom colours) |
| `EXPORT_DIR` | `DATA_DIR / "exports"` | Export output directory |
| `DATABASE_URL` | `sqlite:///` + DB_PATH | SQLAlchemy connection string |

---

## 8. Dependency Injection

The app uses **constructor injection** wired through a simple `Container` class (not a full DI framework):

```
Container()
  ├── recovery_service = RecoveryService()
  ├── backup_service = BackupService()
  ├── event_bus = EventBus()
  └── get_uow() → SqlAlchemyUnitOfWork(session)
                    └── session = DatabaseSession.get_session()

MainWindow receives Container → creates tabs → tabs create use cases via container
```

`[FILE: src/Loan Manager/loan_manager/container.py]`

---

## 9. Build & Run

### Prerequisites

- Python >= 3.10 (check: `python --version`)
- pip (bundled with Python)

### Windows

```bat
run_windows.bat
```

Does: Python version check → create venv → install requirements → launch `python -m loan_manager.main`

### macOS

```bash
chmod +x run_mac.sh && ./run_mac.sh
```

Does: Python version check → create venv → install requirements → launch `python -m loan_manager.main`

### Manual

```bash
cd "src/Loan Manager"
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m loan_manager.main
```

### Tests

```bash
cd "src/Loan Manager"
python -m pytest tests/ -v --cov=loan_manager
```

Expected: 150 passed, 0 failed, 89% coverage.

`[FILE: src/Loan Manager/requirements.txt]`
`[FILE: src/Loan Manager/run_mac.sh]`
`[FILE: src/Loan Manager/run_windows.bat]`

---

## 10. Architecture Decision Records

| ID | Decision | Rationale | File |
|---|---|---|---|
| ADR-001 | Clean Architecture + Lightweight DDD | Pure-Python domain layer; testable without DB/UI; prevents logic leakage | `[FILE: output/Loan Manager/run_8/docs/architecture_decision_records/ADR-001-clean-architecture.md]` |
| ADR-002 | SQLite + SQLAlchemy 2.x + Alembic | Zero-install DB; type-safe ORM; versioned migrations; CSV retained for portability | `[FILE: output/Loan Manager/run_8/docs/architecture_decision_records/ADR-002-sqlite-sqlalchemy.md]` |
| ADR-003 | QAbstractTableModel (not QTableWidget) | QTableWidget creates one widget/cell — too slow for 1500 rows with sort/filter/edit | `[FILE: output/Loan Manager/run_8/docs/architecture_decision_records/ADR-003-pyside6-tablemodel.md]` |
| ADR-004 | Date picker via calendarPopup + QTimer | `showCalendarWidget()` doesn't exist; `QTimer.singleShot(0, ...)` avoids focus recursion | `[FILE: output/Loan Manager/run_8/docs/architecture_decision_records/ADR-004-date-picker-fix.md]` |
| ADR-005 | Configurable theme + status colours in JSON | No hardcoded hex in UI; colours in `dark_config.json` / `light_config.json` | `[FILE: output/Loan Manager/run_8/docs/architecture_decision_records/ADR-005-configurable-theme.md]` |
| ADR-006 | Pydantic v2 DTOs with field validators | Validates at layer boundaries; lowercase normalisation; due_date auto-compute | `[FILE: output/Loan Manager/run_8/docs/architecture_decision_records/ADR-006-pydantic-dtos.md]` |

---

## 11. Design Documents Index

| Document | Location | Contents |
|---|---|---|
| Business Requirements | `[FILE: output/Loan Manager/run_8/docs/business_requirements.md]` | BR-01 through BR-10; all MUST/SHOULD/NICE classified |
| Technical Design | `[FILE: output/Loan Manager/run_8/docs/technical_design_document.md]` | Full architecture, layer breakdown, event flows, tech stack, folder structure |
| Data Model | `[FILE: output/Loan Manager/run_8/docs/data_model.md]` | All 6 tables, columns, types, constraints, ER diagram |
| Migration Strategy | `[FILE: output/Loan Manager/run_8/docs/migration_strategy.md]` | Alembic setup + CSV-to-SQLite one-time migration |
| API Boundaries | `[FILE: output/Loan Manager/run_8/docs/api_boundaries.md]` | Interface contracts between layers |
| UI Wireframes | `[FILE: output/Loan Manager/run_8/docs/ui_wireframes.md]` | Tab layouts and interaction flows |
| Assumptions | `[FILE: output/Loan Manager/run_8/docs/assumptions.md]` | A-01 through A-12; all assumptions documented |
| Risks & Tradeoffs | `[FILE: output/Loan Manager/run_8/docs/risks_and_tradeoffs.md]` | R-01 through R-12; risk/severity/mitigation |
| Backlog | `[FILE: output/Loan Manager/run_8/docs/backlog.md]` | Feature backlog with priority classifications |
| Stage Log | `[FILE: output/Loan Manager/run_8/docs/stage_log.md]` | 6-stage delivery log with inputs/outputs/decisions |
| Final Review | `[FILE: output/Loan Manager/run_8/FINAL_REVIEW.md]` | Requirements traceability, test results, known limitations |
| Filter Architecture | `[FILE: src/Loan Manager/docs/filter_architecture.md]` | State flow, invariants, design decisions |
| Platform Compatibility | `[FILE: src/Loan Manager/docs/compatibility.md]` | Python versions, PySide6 versions, OS support |
| Report Calculation Flow | `[FILE: src/Loan Manager/docs/report_calculation_flow.md]` | End-to-end flow from source data → calculation → report → approval |

---

## 12. Sample Data Reference

The 15-record sample dataset (used in tests and demo):

| Record | Borrower | B.Group | Amount | Depositor | D.Group | Giving Date | Due Date |
|---|---|---|---|---|---|---|---|
| b1 | b1 | bg1 | 10,000 | d1 | dg1 | 02-01-2026 | 02-04-2026 |
| b2 | b2 | bg2 | 10,000 | d2 | dg1 | 04-01-2026 | 04-05-2026 |
| b3 | b3 | bg3 | 15,000 | d3 | dg1 | 06-02-2026 | 06-05-2026 |
| b4 | b4 | bg3 | 20,000 | d4 | dg2 | 07-02-2026 | 07-06-2026 |
| b5 | b5 | bg4 | 20,000 | d5 | dg2 | 08-02-2026 | 08-06-2026 |
| b6 | b6 | bg4 | 15,000 | d6 | dg3 | 08-02-2026 | 08-07-2026 |
| b7 | b7 | bg5 | 15,000 | d7 | dg3 | 15-02-2026 | 15-07-2026 |
| b8 | b8 | bg5 | 20,000 | d8 | dg3 | 18-02-2026 | 18-06-2026 |
| b9 | b9 | bg1 | 20,000 | d9 | dg3 | 20-02-2026 | 20-06-2026 |
| b10 | b10 | bg6 | 10,000 | d10 | dg1 | 25-02-2026 | 25-05-2026 |
| b11 | b11 | bg6 | 15,000 | d11 | dg2 | 28-02-2026 | 28-05-2026 |
| b12 | b12 | bg7 | 15,000 | d12 | dg4 | 02-03-2026 | 02-07-2026 |
| b13 | b13 | bg7 | 10,000 | d13 | dg4 | 05-03-2026 | 05-07-2026 |
| b14 | b14 | bg8 | 15,000 | d14 | *(none)* | 10-03-2026 | 10-07-2026 |
| b15 | b15 | bg8 | 20,000 | d15 | *(none)* | 14-03-2026 | 14-07-2026 |

**Validation checkpoints** (used in filter tests):
- Filter `bg3` (Borrower Group) → **2 records** (b3, b4)
- Filter `dg3` (Depositor Group) → **4 records** (b6, b7, b8, b9)
- b14, b15 have no depositor_group → shown as "Unknown" in UI

`[FILE: input/REQUIREMENTS.md]` (Sample Input section)

---

## 13. Requirement-to-Code Traceability

| Requirement | Primary Code | Tests |
|---|---|---|
| R1 — Loan Entry | `presentation/tabs/entry_tab.py`, `use_cases/loans/create_loan.py`, `dtos/loan_dto.py` | `test_create_loan.py` |
| R2 — Loan View | `presentation/tabs/view_tab.py`, `widgets/loan_table_model.py`, `widgets/column_filter_widget.py` | Filter integration tests |
| R3 — Status Engine | `domain/services/status_engine.py`, `use_cases/loans/recompute_statuses.py` | `test_status_engine.py` |
| R4 — Ref IDs + Extend | `domain/services/reference_id_service.py`, `domain/value_objects/reference_id.py`, `use_cases/loans/extend_loan.py` | `test_reference_id_service.py`, `test_extend_loan.py` |
| R5 — Interest Calculator | `domain/services/interest_calculator.py`, `use_cases/reports/calculate_interest.py`, `use_cases/reports/generate_report.py` | `test_interest_calculator.py`, `test_calculate_interest.py` |
| R5/R6 — Approval | `use_cases/reports/approve_report.py`, `use_cases/reports/decline_report.py`, `presentation/tabs/pending_approval_tab.py` | `test_approve_report.py`, `test_approval_flow.py` |
| R6 — Import/Export | `csv/import_service.py`, `csv/export_service.py`, `use_cases/data/import_loans.py` | `test_import_loans.py` |
| R7/R8 — Launchers | `run_windows.bat`, `run_mac.sh`, `requirements.txt` | — |
| R9 — Themes | `presentation/themes/theme_manager.py` | — (visual) |
| R10 — User Guides | `user_guides/windows_guide.md`, `user_guides/mac_guide.md` | — |
| UTR-1 — Date Picker | `presentation/widgets/date_edit.py` | — (visual) |

---

## 14. FinHive Meta-Architecture

Loan Manager is one project built within the **FinHive** framework — a multi-agent orchestration system that uses Claude skills to simulate coordinated software delivery.

### How FinHive Works

```
input/REQUIREMENTS.md  ──►  Stage-gated prompt (prompt.md)
                                    │
                              6 Stages, each:
                              ├── Produce artifacts
                              ├── STOP for review
                              └── Await PROCEED / PROCEED WITH MODIFICATIONS
                                    │
                              output/Loan Manager/run_8/
                              ├── docs/ (design artifacts)
                              └── FINAL_REVIEW.md
                                    │
                              src/Loan Manager/
                              └── (implementation)
```

### Agent Model Split (run_8)

| Stages | Model | Rationale |
|---|---|---|
| 1–2 (Discovery + Architecture) | claude-sonnet-4-6 | Planning benefits from breadth |
| 3–5 (Scaffold + Domain + UI) | claude-opus-4-6 | Implementation benefits from depth |
| 6 (Finalization) | claude-sonnet-4-6 | Docs and packaging |

### Post-Build Bug Fix Iterations

After the 6-stage build, 4 additional prompt iterations addressed QA findings:
1. **prompt_fix_20260705.md**: View Tab filtering + print support
2. **prompt_fix_20240705_ui.md**: Layout + checkbox state sync
3. **prompt_fix_20260705_ui.md**: Filter state architecture rewrite
4. **prompt_fix_20260708.md**: Cross-platform + Python 3.13 + report preview

Each iteration preserved existing business logic and made targeted corrections.

---

## 15. Quick Reference — Common Tasks

### "I need to change a business rule"

→ Edit the domain service (`domain/services/`) → update its unit test → run `pytest`.

### "I need to add a new column to the loans table"

→ Add field to `LoanModel` in `infrastructure/database/models.py` → add to `Loan` entity → add to DTOs → create Alembic migration → update UI display in `LoanTableModel`.

### "I need to understand why a filter isn't working"

→ Read `[FILE: src/Loan Manager/docs/filter_architecture.md]` → check `ColumnFilterWidget` → trace state flow: committed → pending → popup render.

### "I need to add a new calculation mode"

→ Add enum value to `CalculationMode` in `value_objects/status.py` → add formula to `InterestCalculator` → add use case handling in `calculate_interest.py` → add UI mode option in `CalculatorTab`.

### "I need to understand the approval flow"

→ Read `[FILE: src/Loan Manager/docs/report_calculation_flow.md]` → trace from `GenerateReport` → `PendingApprovalTab` → `ApproveReport` use case.

### "I need to debug a startup issue"

→ Check `main.py` startup sequence → check `./data/logs/app.log` → check for `approval_recovery.tmp`.

---

## 16. Changelog (Architectural)

| Change | When | Impact |
|---|---|---|
| CSV → SQLite + SQLAlchemy | Stage 2 (CHG-001) | Full persistence layer rewrite; CSV retained for import/export |
| Hardcoded colours → ThemeManager | Stage 2 (CHG-002) | All UI colours from JSON config |
| ByMonth filter excludes no-due-date | Stage 4 (CHG-003) | Other filters include no-due-date records if matching |
| Filter popup → single-source-of-truth FilterState | Post-build (prompt_fix_20260705_ui.md) | Popup became pure view; eliminated checkbox desync |
| macOS deferred render | Post-build (prompt_fix_20260708.md) | `QTimer.singleShot(0, ...)` for Qt compositor compatibility |
| Report shows post-extension preview | Post-build (prompt_fix_20260708.md) | Pending Approval now shows projected values, not just pre-extension |
| Python 3.13 compatibility | Post-build (prompt_fix_20260708.md) | PySide6 >= 6.8.0; `datetime.utcnow()` deprecation resolved |
