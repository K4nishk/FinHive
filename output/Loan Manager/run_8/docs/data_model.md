# Data Model — Loan Manager MVP1

## Storage Engine: SQLite (via SQLAlchemy ORM)

All primary data stored in `./data/loans.db`. CSV import/export available for portability.

---

## Tables

### 1. loans

Primary table for all active loan records.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | Internal row ID |
| reference_id | VARCHAR(20) | UNIQUE, NOT NULL, INDEX | Format: YYYY_MM_<order> |
| borrower_name | VARCHAR(255) | NOT NULL | Stored lowercase |
| borrower_group | VARCHAR(255) | NOT NULL | Stored lowercase |
| depositor_name | VARCHAR(255) | NOT NULL | Stored lowercase |
| depositor_group | VARCHAR(255) | NULLABLE | Stored lowercase; NULL = "Unknown" in UI |
| amount | INTEGER | NOT NULL, >= 0 | INR, non-negative integer |
| giving_date | DATE | NOT NULL | ISO 8601; reference only |
| due_period | INTEGER | NULLABLE | Months; used to derive due_date |
| due_date | DATE | NULLABLE | ISO 8601; NULL = "Unknown" |
| status | VARCHAR(10) | NOT NULL | Enum: Active, Overdue, Pending, Paidoff |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | FALSE = hidden (paidoff); kept for audit |
| created_at | DATETIME | NOT NULL | UTC |
| updated_at | DATETIME | NOT NULL | UTC; updated on any change |

**Indexes**: `reference_id` (unique), `borrower_name`, `depositor_name`, `status`

---

### 2. loan_meta

Tracks the high-water counter per YYYY_MM period for reference ID generation.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| year_month | VARCHAR(7) | PK | Format: YYYY_MM |
| last_order | INTEGER | NOT NULL, >= 1 | Last used order number |

---

### 3. loan_history

Immutable archive of paidoff loans. Written on approval of a Paidoff report.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | |
| reference_id | VARCHAR(20) | NOT NULL, INDEX | Original ref_id |
| borrower_name | VARCHAR(255) | NOT NULL | |
| borrower_group | VARCHAR(255) | NOT NULL | |
| depositor_name | VARCHAR(255) | NOT NULL | |
| depositor_group | VARCHAR(255) | NULLABLE | |
| amount | INTEGER | NOT NULL | |
| giving_date | DATE | NOT NULL | |
| due_date | DATE | NULLABLE | |
| paidoff_date | DATE | NULLABLE | Populated from ReportRecord |
| archived_at | DATETIME | NOT NULL | When moved to history |

---

### 4. reports

Report header metadata. One row per generated report.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | |
| report_id | VARCHAR(20) | UNIQUE, NOT NULL | Format: RPT_YYYYMMDD_<order> |
| report_mode | VARCHAR(10) | NOT NULL | Enum: Monthly, Daily, Both, Paidoff |
| status | VARCHAR(10) | NOT NULL, DEFAULT 'Pending' | Enum: Pending, Approved, Declined |
| created_at | DATETIME | NOT NULL | |
| updated_at | DATETIME | NOT NULL | Updated on inline edit or status change |

---

### 5. report_records

Line items for each report. One row per loan in a report.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| id | INTEGER | PK, autoincrement | |
| report_id | VARCHAR(20) | FK → reports.report_id, NOT NULL | CASCADE DELETE |
| reference_id | VARCHAR(20) | NOT NULL | Loan ref_id at time of report generation |
| borrower_name | VARCHAR(255) | NOT NULL | Snapshot at report time |
| depositor_name | VARCHAR(255) | NOT NULL | Snapshot at report time |
| depositor_group | VARCHAR(255) | NULLABLE | |
| amount | INTEGER | NOT NULL | |
| giving_date | DATE | NOT NULL | Pre-extension value |
| due_date | DATE | NULLABLE | Pre-extension value |
| extension_period | INTEGER | NOT NULL | |
| extension_period_unit | VARCHAR(10) | NOT NULL | Enum: months, days |
| interest_rate | DECIMAL(5,2) | NOT NULL | Percentage |
| commission_rate | DECIMAL(5,2) | NOT NULL | Percentage |
| tds_flag | BOOLEAN | NOT NULL, DEFAULT FALSE | |
| interest_amount | DECIMAL(12,2) | NULLABLE | Computed |
| commission_amount | DECIMAL(12,2) | NULLABLE | Computed |
| tds_amount | DECIMAL(12,2) | NULLABLE | Computed; 0.1 × interest_amount |
| chq_amount | DECIMAL(12,2) | NULLABLE | Computed; interest_amount - tds_amount |
| post_extension_giving_date | DATE | NULLABLE | Preview; populated on generate |
| post_extension_due_date | DATE | NULLABLE | Preview; populated on generate |
| paidoff_date | DATE | NULLABLE | Paidoff mode only |

**Indexes**: `report_id`, `reference_id`

---

### 6. report_meta

Tracks daily counter for report ID generation.

| Column | Type | Constraints | Notes |
|---|---|---|---|
| report_date | VARCHAR(8) | PK | Format: YYYYMMDD |
| last_order | INTEGER | NOT NULL, >= 1 | |

---

## Entity Relationship Diagram (ASCII)

```
loans (1) ──────────────────── report_records (N)
  id                             id
  reference_id ◄── ref (soft) ── reference_id
  ...                            report_id ──► reports (N→1)
                                 ...            id
                                                report_id
                                                ...
                                                     │
                                              report_meta
                                              report_date
                                              last_order

loans (1) ──► loan_history (N) [on paidoff approval]
  reference_id      reference_id

loans (1) ──► loan_meta (N) [counter per YYYY_MM]
  YYYY_MM (derived)   year_month
```

---

## Domain Entity Mapping

```python
# Domain entity (loan_manager/domain/entities/loan.py)
class Loan:
    id: int
    reference_id: ReferenceId      # value object
    borrower_name: str
    borrower_group: str
    depositor_name: str
    depositor_group: str | None
    amount: Money                  # value object (non-negative int)
    giving_date: date
    due_period: int | None
    due_date: date | None
    status: LoanStatus             # value object (enum)
    is_active: bool
    created_at: datetime
    updated_at: datetime

    def compute_status(self, today: date) -> LoanStatus:
        # Status engine logic (delegated to StatusEngine domain service)
        ...
```

```python
# Domain entity (loan_manager/domain/entities/report.py)
class Report:
    id: int
    report_id: ReportId            # value object
    report_mode: CalculationMode
    status: ReportStatus
    records: list[ReportRecord]    # value objects
    created_at: datetime
    updated_at: datetime
```

---

## Pydantic DTO Examples

```python
# loan_manager/application/dtos/loan_dto.py
class LoanCreateDTO(BaseModel):
    borrower_name: str
    borrower_group: str
    depositor_name: str
    depositor_group: str | None = None
    amount: int = Field(ge=0)
    giving_date: date
    due_period: int | None = None
    due_date: date | None = None

    @model_validator(mode='after')
    def compute_due_date(self) -> 'LoanCreateDTO':
        if self.due_period is not None and self.due_date is None:
            self.due_date = self.giving_date + relativedelta(months=self.due_period)
        return self

    @field_validator('borrower_name', 'borrower_group', 'depositor_name', 'depositor_group', mode='before')
    @classmethod
    def normalize_lowercase(cls, v: str | None) -> str | None:
        return v.lower().strip() if v else v
```

---

## Migration Strategy

See `migration_strategy.md` for full Alembic setup and CSV-to-SQLite migration plan.

---

## Notes

- `is_active = FALSE` records remain in `loans` table for potential audit; UI hides them
- `report_records` stores snapshots (not FK to loans) to remain consistent if loan is later deleted
- All monetary amounts stored as integers (INR paise not needed; amounts are whole rupees)
- All dates stored as SQLite DATE type (ISO 8601 string internally)
