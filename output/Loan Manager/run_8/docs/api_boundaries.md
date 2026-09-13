# API Boundaries — Loan Manager MVP1

Internal API boundaries between layers. No HTTP API — all in-process.

---

## 1. Presentation → Application

Presentation layer calls Application use cases only. Never accesses repositories or domain entities directly.

### Loan Use Cases

```python
# Input/Output types are DTOs (Pydantic models)

class CreateLoan:
    def execute(self, dto: LoanCreateDTO) -> LoanDTO: ...

class UpdateLoan:
    def execute(self, reference_id: str, dto: LoanUpdateDTO) -> LoanDTO: ...

class DeleteLoan:
    def execute(self, reference_id: str) -> None: ...

class ExtendLoan:
    def execute(self, reference_id: str, dto: ExtendLoanDTO) -> LoanDTO: ...

class MarkPaidOff:
    # Creates a Paidoff report and sends to Pending Approval queue
    def execute(self, reference_id: str, dto: PaidOffRequestDTO) -> ReportDTO: ...

class RecomputeAllStatuses:
    # Called on app launch; updates all active loan statuses in bulk
    def execute(self) -> int: ...  # returns count of updated records

class GetAllLoans:
    # Returns only is_active=True loans
    def execute(self, filters: LoanFilterDTO | None = None) -> list[LoanDTO]: ...

class GetLoanById:
    def execute(self, reference_id: str) -> LoanDTO | None: ...

class GetAutocompleteValues:
    # Returns unique values for autocomplete fields
    def execute(self, field: str) -> list[str]: ...
```

### Report Use Cases

```python
class CalculateInterest:
    # Returns calculation results without persisting
    def execute(self, dto: CalculationRequestDTO) -> CalculationResultDTO: ...

class GenerateReport:
    # Persists report to Pending Approval queue
    def execute(self, dto: GenerateReportDTO) -> ReportDTO: ...

class ApproveReport:
    # Returns warnings if conflicts detected; caller must re-invoke with force=True to proceed
    def execute(self, report_id: str, force: bool = False) -> ApprovalResultDTO: ...

class DeclineReport:
    def execute(self, report_id: str) -> None: ...

class GetPendingReports:
    def execute(self) -> list[ReportDTO]: ...

class UpdateReportRecord:
    # Inline edit of a report record; recalculates amounts
    def execute(self, report_id: str, record_id: int, dto: ReportRecordUpdateDTO) -> ReportRecordDTO: ...
```

### Data Use Cases

```python
class ImportLoans:
    # Step 1: preview
    def preview(self, file_path: str) -> ImportPreviewDTO: ...
    # Step 2: commit
    def commit(self, file_path: str, overwrite_existing: bool = True) -> ImportResultDTO: ...

class ExportLoans:
    def execute(self, format: str = 'csv', output_path: str | None = None) -> str: ...
    # Returns path of written file
```

---

## 2. Application → Domain

Application use cases call Domain entities and services directly (not via interfaces for pure domain logic).

```python
# Domain service interfaces
class StatusEngine:
    @staticmethod
    def compute(giving_date: date, due_date: date | None, today: date) -> LoanStatus: ...

class InterestCalculator:
    @staticmethod
    def calculate_monthly(amount: int, interest_rate: float, extension_period: int) -> Decimal: ...
    @staticmethod
    def calculate_daily(amount: int, interest_rate: float, extension_period: int) -> Decimal: ...
    @staticmethod
    def calculate_both(records: list[CalculationInputDTO]) -> list[CalculationOutputDTO]: ...
    # Orchestrator for Both mode (testable independently)

class ReferenceIdService:
    def next_id(self, year_month: str, current_max: int | None) -> str: ...
    # Returns YYYY_MM_<next_order>
```

---

## 3. Application → Infrastructure (via Repository Interfaces)

Application knows only the interfaces defined in the domain layer.

```python
# Domain repository interfaces (loan_manager/domain/repositories/)

class ILoanRepository(ABC):
    def get_by_reference_id(self, ref_id: str) -> Loan | None: ...
    def get_all_active(self, filters: dict | None = None) -> list[Loan]: ...
    def save(self, loan: Loan) -> Loan: ...
    def delete(self, reference_id: str) -> None: ...
    def bulk_update_status(self, updates: list[tuple[str, LoanStatus]]) -> None: ...
    def bulk_update_dates(self, updates: list[LoanDateUpdateDTO]) -> None: ...
    def get_unique_values(self, field: str, active_only: bool = True) -> list[str]: ...

class IReportRepository(ABC):
    def get_by_report_id(self, report_id: str) -> Report | None: ...
    def get_all_pending(self) -> list[Report]: ...
    def save(self, report: Report) -> Report: ...
    def update_record(self, record_id: int, dto: ReportRecordUpdateDTO) -> ReportRecord: ...
    def mark_approved(self, report_id: str) -> None: ...
    def mark_declined(self, report_id: str) -> None: ...
    def get_pending_reference_ids(self) -> set[str]: ...
    # Used for duplicate-ref_id conflict detection

class ILoanMetaRepository(ABC):
    def get_last_order(self, year_month: str) -> int | None: ...
    def set_last_order(self, year_month: str, order: int) -> None: ...

class ILoanHistoryRepository(ABC):
    def archive(self, loan: Loan, paidoff_date: date) -> None: ...
```

---

## 4. Infrastructure → External

```python
# CSV/XLSX I/O (no interface needed; called only from infrastructure layer)
class CsvImportService:
    def parse(self, file_path: str) -> list[RawLoanRecord]: ...

class CsvExportService:
    def write_loans(self, loans: list[LoanDTO], path: str) -> None: ...
    def write_report(self, report: ReportDTO, path: str) -> None: ...

# Recovery
class RecoveryService:
    def write(self, operation: str, data: dict) -> None: ...
    def clear(self) -> None: ...
    def exists(self) -> bool: ...

# Backup
class BackupService:
    def create_backup(self, db_path: str) -> str: ...
    # Returns path of backup file
```

---

## 5. DTO Contracts

### LoanFilterDTO
```python
class LoanFilterDTO(BaseModel):
    borrower_group: str | None = None
    borrower_name: str | None = None
    depositor_name: str | None = None
    depositor_group: str | None = None
    by_month: int | None = None          # 1-12; filters on current year's due_date month
    # Note: by_month excludes no-due-date records; other filters include them
```

### CalculationRequestDTO
```python
class CalculationRequestDTO(BaseModel):
    mode: CalculationMode                 # Monthly | Daily | Both
    filters: LoanFilterDTO
    interest_rate: float
    commission_rate: float
    extension_period: int
    extension_period_unit: ExtensionPeriodUnit
    tds_flag: bool = False
```

### ApprovalResultDTO
```python
class ApprovalResultDTO(BaseModel):
    success: bool
    duplicate_ref_ids: list[str]          # ref_ids also in other pending reports
    deleted_ref_ids: list[str]            # ref_ids that no longer exist in loans
    requires_confirmation: bool           # True if user must re-invoke with force=True
```

### ExtendLoanDTO
```python
class ExtendLoanDTO(BaseModel):
    extension_period: int
    extension_period_unit: ExtensionPeriodUnit  # default: months
    # For no-due-date loans: new_giving_date=today, new_due_date from user
    new_due_date: date | None = None
```
