# Technical Design Document — Loan Manager MVP1

## 1. Overview

Loan Manager MVP1 is a single-user desktop application for managing informal personal loans. Built with Python + PySide6 + SQLite. Replaces the previous CSV-only prototype with a proper persistence layer while maintaining CSV import/export for data portability.

---

## 2. Architecture Style

**Clean Architecture** with **Lightweight DDD**.

Four concentric layers — inner layers have no dependency on outer layers:

```
+-----------------------------------------------+
|              Presentation (PySide6)           |
|  +------------------------------------------+ |
|  |       Application (Use Cases / DTOs)     | |
|  |  +-------------------------------------+ | |
|  |  |    Domain (Entities / Rules)        | | |
|  |  +-------------------------------------+ | |
|  +------------------------------------------+ |
|  Infrastructure (SQLAlchemy / Alembic / CSV)  |
+-----------------------------------------------+
```

### Dependency Rule
- Domain knows nothing about Infrastructure or Presentation
- Application knows Domain only
- Infrastructure implements Domain interfaces
- Presentation calls Application use cases

---

## 3. Layer Breakdown

### 3.1 Domain Layer

**Responsibility**: Core business entities, rules, value objects, domain events, repository interfaces.

**Entities**:
- `Loan` — aggregate root; owns status, ref_id, all loan fields
- `Report` — aggregate root; owns report_id, status, list of ReportRecords
- `ReportRecord` — value object within Report aggregate

**Value Objects**:
- `ReferenceId` — encapsulates YYYY_MM_<order> format + validation
- `ReportId` — encapsulates RPT_YYYYMMDD_<order> format
- `Money` — non-negative integer amount in INR
- `LoanStatus` — enum: Active, Overdue, Pending, Paidoff
- `ReportStatus` — enum: Pending, Approved, Declined
- `CalculationMode` — enum: Monthly, Daily, Both
- `ExtensionPeriodUnit` — enum: months, days

**Domain Services**:
- `StatusEngine` — computes loan status from dates + today
- `InterestCalculator` — Monthly, Daily, Both formulas; orchestrator for Both mode
- `ReferenceIdService` — generates and increments YYYY_MM_<order>

**Repository Interfaces** (in domain layer):
- `ILoanRepository`
- `IReportRepository`
- `ILoanMetaRepository`
- `ILoanHistoryRepository`

**Domain Events**:
- `LoanCreated`
- `LoanExtended`
- `LoanPaidOffRequested`
- `LoanPaidOffApproved`
- `ReportGenerated`
- `ReportApproved`
- `ReportDeclined`

---

### 3.2 Application Layer

**Responsibility**: Orchestrates use cases. No business logic — delegates to domain. Defines DTOs and event bus.

**Use Cases**:
| Use Case | Command/Query |
|---|---|
| `CreateLoan` | Command |
| `UpdateLoan` | Command |
| `DeleteLoan` | Command |
| `ExtendLoan` | Command |
| `MarkPaidOff` | Command |
| `RecomputeAllStatuses` | Command (called on launch) |
| `GetAllLoans` | Query |
| `GetLoanById` | Query |
| `GetAutocompleteValues` | Query |
| `CalculateInterest` | Command (returns calculation DTO) |
| `GenerateReport` | Command |
| `ApproveReport` | Command |
| `DeclineReport` | Command |
| `GetPendingReports` | Query |
| `ImportLoans` | Command |
| `ExportLoans` | Command |

**DTOs**:
- `LoanDTO`, `LoanCreateDTO`, `LoanUpdateDTO`
- `ReportDTO`, `ReportRecordDTO`
- `CalculationResultDTO`
- `ImportPreviewDTO`

**Unit of Work Interface**:
- `IUnitOfWork` — context manager; `commit()`, `rollback()`

**Event Bus**:
- `EventBus` — simple in-memory publish/subscribe
- Used for cross-cutting concerns (logging, recovery file writes)

---

### 3.3 Infrastructure Layer

**Responsibility**: All external concerns — database, migrations, file I/O, logging.

**Database**:
- SQLAlchemy ORM with SQLite backend
- Session managed via `UnitOfWork` implementation
- `DatabaseSession` — singleton session factory

**Repositories** (implement domain interfaces):
- `SqlAlchemyLoanRepository`
- `SqlAlchemyReportRepository`
- `SqlAlchemyLoanMetaRepository`
- `SqlAlchemyLoanHistoryRepository`

**Migrations**:
- Alembic; `migrations/` folder
- Auto-generate from ORM models

**CSV Services**:
- `CsvImportService` — parses CSV/XLSX, returns `ImportPreviewDTO`
- `CsvExportService` — writes active loans / reports to CSV/XLSX

**Recovery Service**:
- `RecoveryService` — writes `approval_recovery.tmp`; checks on startup
- `BackupService` — creates timestamped copy of data before destructive ops

**Logging**:
- Python `logging` module to `./data/logs/app.log`
- Rotating file handler (max 5MB, 3 backups)

---

### 3.4 Presentation Layer

**Responsibility**: PySide6 UI. Calls Application use cases. No business logic.

**Main Window**: `MainWindow` — tab container + status bar

**Tabs**:
- `EntryTab` — loan creation form
- `ViewTab` — sortable/filterable table + context menu
- `CalculatorTab` — mode selector + filters + global inputs + Calculate
- `PendingApprovalTab` — report queue + inline editing
- `SettingsTab` — theme selection, data directory config

**Dialogs**:
- `DatePickerDialog` — standalone calendar (fixes date picker bug)
- `ExtendDialog` — extension_period_unit + extension_period
- `PaidOffDialog` — paidoff_date, interest_rate, commission_rate, tds_flag
- `CalculationDialog` — inline-editable results table
- `ImportPreviewDialog` — shows new/overwrite counts + sample ref_ids

**Widgets**:
- `DateEditFixed` — QDateEdit with calendarPopup(True); opens on Tab focus or double-click
- `StatusComboBox` — QComboBox with status colour coding
- `LoanTableModel` — QAbstractTableModel + QSortFilterProxyModel (not QTableWidget)
- `ColumnFilterWidget` — per-column filter with date hierarchy YYYY→MM→records

**View Models** (thin ViewModel layer):
- `LoanViewModel` — maps LoanDTO to display strings + colours
- `ReportViewModel` — maps ReportDTO to display strings

**Theme Manager**:
- `ThemeManager` — loads QSS stylesheets; supports at least 2 themes
- Theme includes: background, foreground, status colours (configurable)
- Status colours stored in theme config, not hardcoded

---

## 4. Dependency Injection

Simple constructor injection throughout. No DI container for prototype scope.

`ApplicationServiceLocator` — instantiated at startup:
```
db_session → repositories → unit_of_work → use_cases → tab/dialog constructors
```

---

## 5. Event Flow: Approve Report

```
User clicks Approve
  → PendingApprovalTab
    → ApproveReport use case
      → check duplicate ref_ids across pending reports
        → warn if conflict; user chooses Proceed/Cancel
      → check for deleted loans in report
        → warn if any deleted; user chooses Ignore/Decline
      → RecoveryService.write_recovery(report_id, affected_loan_ids)
      → UoW.begin()
        → SqlAlchemyLoanRepository.bulk_update(new dates)
        → SqlAlchemyReportRepository.mark_approved(report_id)
      → UoW.commit()
      → BackupService.create_timestamped_backup()  [before commit in production order]
      → RecoveryService.clear_recovery()
      → EventBus.publish(ReportApproved)
```

---

## 6. Tech Stack

| Component | Choice | Version |
|---|---|---|
| Language | Python | >= 3.10 |
| GUI | PySide6 | latest |
| ORM | SQLAlchemy | 2.x |
| Migrations | Alembic | latest |
| Validation/DTOs | Pydantic | v2 |
| Database | SQLite | bundled with Python |
| Excel I/O | openpyxl | latest |
| Logging | stdlib logging | — |
| Testing | pytest | latest |
| Coverage | pytest-cov | 85% target |

---

## 7. Folder Structure

```
src/
  loan_manager/
    domain/
      entities/
        loan.py
        report.py
      value_objects/
        reference_id.py
        report_id.py
        money.py
        status.py
      events/
        loan_events.py
        report_events.py
      repositories/
        loan_repository.py        (interface)
        report_repository.py      (interface)
        loan_meta_repository.py   (interface)
        history_repository.py     (interface)
      services/
        status_engine.py
        interest_calculator.py
        reference_id_service.py
    application/
      use_cases/
        loans/
          create_loan.py
          update_loan.py
          delete_loan.py
          extend_loan.py
          mark_paidoff.py
          recompute_statuses.py
          get_loans.py
          get_autocomplete.py
        reports/
          calculate_interest.py
          generate_report.py
          approve_report.py
          decline_report.py
          get_reports.py
        data/
          import_loans.py
          export_loans.py
      dtos/
        loan_dto.py
        report_dto.py
        calculation_dto.py
        import_dto.py
      interfaces/
        unit_of_work.py
      event_bus.py
    infrastructure/
      database/
        models.py                 (SQLAlchemy ORM)
        session.py
        unit_of_work.py
      repositories/
        sqlalchemy_loan_repo.py
        sqlalchemy_report_repo.py
        sqlalchemy_meta_repo.py
        sqlalchemy_history_repo.py
      migrations/                 (Alembic folder)
        alembic.ini
        env.py
        versions/
      csv/
        import_service.py
        export_service.py
      recovery/
        recovery_service.py
        backup_service.py
      logging/
        logger.py
    presentation/
      main_window.py
      tabs/
        entry_tab.py
        view_tab.py
        calculator_tab.py
        pending_approval_tab.py
        settings_tab.py
      dialogs/
        date_picker_dialog.py
        extend_dialog.py
        paidoff_dialog.py
        calculation_dialog.py
        import_preview_dialog.py
      widgets/
        date_edit.py              (fixed DateEditFixed)
        status_combobox.py
        loan_table_model.py       (QAbstractTableModel)
        column_filter_widget.py
      view_models/
        loan_view_model.py
        report_view_model.py
      themes/
        theme_manager.py
        themes/
          dark.qss
          light.qss
          dark_config.json
          light_config.json
    config.py
    container.py                  (ApplicationServiceLocator)
    main.py
data/
  loans.db
  logs/
    app.log
migrations/                       (Alembic root)
tests/
  unit/
    domain/
      test_status_engine.py
      test_interest_calculator.py
      test_reference_id_service.py
      test_loan_entity.py
      test_report_entity.py
    application/
      test_create_loan.py
      test_extend_loan.py
      test_approve_report.py
      test_calculate_interest.py
      test_import_loans.py
  integration/
    test_loan_repository.py
    test_report_repository.py
    test_approval_flow.py
  fixtures/
    sample_loans.py
    conftest.py
user_guides/
  windows_guide.md
  mac_guide.md
run_windows.bat
run_mac.sh
requirements.txt
```

---

## 8. Critical Design Decisions

### 8.1 QAbstractTableModel over QTableWidget
For 1500 rows with inline editing, sort, and filter: use `QAbstractTableModel` + `QSortFilterProxyModel`. QTableWidget creates one widget per cell and will be sluggish.

### 8.2 Date Picker Fix
`QDateEdit.showCalendarWidget()` does not exist. Fix: set `calendarPopup(True)` on the QDateEdit. For Tab-triggered open: install event filter on the widget and call `QDateEdit.calendarWidget().show()` after a `QTimer.singleShot(0, ...)` to avoid focus recursion.

### 8.3 Calculator: giving_date Excluded
Interest calculations use only `extension_period`. The extension window is the billable period. `giving_date` is never passed to calculator formulas.

### 8.4 Status Colour Configuration
Status colours defined in `theme_config.json` per theme. `ThemeManager` reads config at startup. UI components reference `theme.status_colours[status]` — never hardcoded hex values.

### 8.5 SQLite for MVP1 + CSV Compatibility
SQLite is the primary store. CSV import/export maintained for:
- Legacy data migration (BL-24)
- Cross-platform data sharing via git
- User familiarity / auditability

---

## 9. Testing Strategy

- **85% coverage target**
- Unit tests: domain services + entities (pure Python, no DB)
- Integration tests: repositories against in-memory SQLite (`sqlite:///:memory:`)
- No UI tests in prototype scope
- Calculator tests: use sample data from REQUIREMENTS.md (bg3 → 2 records, dg3 → 4 records)
- Filter logic tests: comprehensive coverage per business requirement
