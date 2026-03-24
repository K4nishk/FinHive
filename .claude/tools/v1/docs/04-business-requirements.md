# Business Requirements & Logic Documentation

## 📋 Document Overview

**Version**: 1.0.0
**Last Updated**: March 2026
**Status**: Active - Editable
**Owner**: Business Team

---

## 1. Core Data Model

### 1.1 Loan Record Structure

| Field | Type | Required | Default | Validation | Business Rule |
|-------|------|----------|---------|------------|---------------|
| `borrower_name` | String | Yes | - | 2-100 chars | Name of person/entity borrowing money |
| `amount` | Decimal | Yes | - | > 0, max 999,999,999.99 | Principal loan amount in INR (₹) |
| `currency` | String | Auto | "INR" | Fixed: INR only | **All amounts in INR only - no currency selection** |
| `depositor_name` | String | Yes | - | 2-100 chars | Name of lender/depositor |
| `giving_date` | Date | Yes | - | Cannot be future | Date loan was disbursed |
| `due_date` | Date | **No** | **1970-01-01** | Must be >= giving_date or 1970-01-01 | Repayment due date; defaults to 1970-01-01 if not provided |
| `borrower_group` | String | No | null | 0-50 chars | Category/group for borrower (e.g., "Family", "Business") |
| `depositor_group` | String | No | null | 0-50 chars | Category/group for depositor (e.g., "Bank", "Personal") |
| `status` | Enum | Auto | "active" | active/paid_off/overdue | Auto-calculated based on due_date |

### 1.2 Currency Policy

**Policy**: All loan amounts must be in **INR (Indian Rupees) only**.

**Business Rules**:
- No currency selection in Data Entry form
- All amounts automatically stored as INR
- All displays show ₹ symbol
- No support for CAD, USD, or other currencies

**Rationale**: Business operates exclusively in Indian market with INR transactions.

---

### 1.3 Serial Number (SNo) Format

**Format**: `YYYY/xxx` where:
- `YYYY` = Year from the loan's giving_date
- `xxx` = Zero-padded sequential number (001, 002, 003, ...)

**Examples**:
- `2026/001` - First loan in 2026
- `2026/002` - Second loan in 2026
- `2025/150` - 150th loan in 2025

**Display Rules**:
- Replace Loan ID in all reports and tables
- Used in View Loans table
- Used in Interest Calculator report
- Included in CSV exports

**Business Rule**: SNo is display-only, internal Loan ID (UUID) still used for database operations.

---

### 1.4 Loan Status Auto-Calculation

```python
# Business Logic for Status
if due_date == "1970-01-01":
    status = "active"  # No due date set, assume active
elif due_date < today and status != "paid_off":
    status = "overdue"
elif status != "paid_off":
    status = "active"
```

**Rationale**: Default due date of 1970-01-01 indicates "no specific due date" - treating as perpetual/on-demand loan.

---

## 2. Reporting Requirements

### 2.1 Filter by Borrower Name

**Requirement ID**: REQ-RPT-001
**Priority**: High
**User Story**: As a user, I want to filter loans by borrower name to see all loans for a specific borrower.

**Acceptance Criteria**:
- Partial match (case-insensitive)
- Returns all loans where borrower_name contains search term
- Example: "John" matches "John Doe", "Johnny Smith"

**Business Logic**:
```sql
SELECT * FROM loans
WHERE LOWER(borrower_name) LIKE '%{search_term}%'
AND deleted_at IS NULL
```

**Use Cases**:
1. View payment history for specific borrower
2. Calculate total debt for individual
3. Assess borrower reliability

---

### 2.2 Filter by Borrower Group

**Requirement ID**: REQ-RPT-002
**Priority**: Medium
**User Story**: As a user, I want to filter loans by borrower group to analyze lending patterns by category.

**Acceptance Criteria**:
- Exact match on borrower_group field
- Returns all loans in specified group
- Example: Group "Family" shows all family loans

**Business Logic**:
```sql
SELECT * FROM loans
WHERE borrower_group = '{group_name}'
AND deleted_at IS NULL
```

**Common Groups**:
- Family
- Friends
- Business Partners
- Employees
- Customers

**Use Cases**:
1. Track total lending to family vs business
2. Risk assessment by borrower category
3. Portfolio diversification analysis

---

### 2.3 Filter by Depositor Name

**Requirement ID**: REQ-RPT-003
**Priority**: High
**User Story**: As a user, I want to filter loans by depositor name to see all loans from a specific lender.

**Acceptance Criteria**:
- Partial match (case-insensitive)
- Returns all loans where depositor_name contains search term
- Example: "Bank" matches "City Bank", "Bank of America"

**Business Logic**:
```sql
SELECT * FROM loans
WHERE LOWER(depositor_name) LIKE '%{search_term}%'
AND deleted_at IS NULL
```

**Use Cases**:
1. Track borrowing from specific lender
2. Calculate total liability per lender
3. Manage multiple funding sources

---

### 2.4 Filter by Depositor Group

**Requirement ID**: REQ-RPT-004
**Priority**: Medium
**User Story**: As a user, I want to filter loans by depositor group to analyze funding sources by category.

**Acceptance Criteria**:
- Exact match on depositor_group field
- Returns all loans from specified group
- Example: Group "Bank" shows all bank loans

**Business Logic**:
```sql
SELECT * FROM loans
WHERE depositor_group = '{group_name}'
AND deleted_at IS NULL
```

**Common Groups**:
- Banks
- Personal Savings
- Family
- Investors
- Credit Unions

**Use Cases**:
1. Compare institutional vs personal lending
2. Interest rate analysis by source
3. Liability breakdown by lender type

---

### 2.5 Filter by Due Date Range

**Requirement ID**: REQ-RPT-005
**Priority**: High
**User Story**: As a user, I want to filter loans by due date range to identify upcoming or overdue payments.

**Acceptance Criteria**:
- Accepts date_from and/or date_to parameters
- Inclusive range (includes boundary dates)
- Handles null due_dates (1970-01-01) separately

**Business Logic**:
```sql
SELECT * FROM loans
WHERE due_date >= '{date_from}'
AND due_date <= '{date_to}'
AND due_date != '1970-01-01'  -- Exclude perpetual loans
AND deleted_at IS NULL
```

**Special Cases**:
- `due_date = 1970-01-01`: Excluded from date range filters by default
- Option to include perpetual loans: Add checkbox "Include loans without due date"

**Use Cases**:
1. Identify overdue loans: `date_to = yesterday`
2. Upcoming payments (next 30 days): `date_from = today, date_to = today + 30 days`
3. Quarterly reviews: Filter by fiscal quarter dates

---

## 3. Interest Calculator Feature

### 3.1 Business Context

**Feature ID**: FEAT-INT-001
**Priority**: High (MVP1)
**Name**: Interest Calculator (formerly "Commission Calculator")
**User Story**: As a broker/intermediary, I want to calculate interest and commissions based on loan amounts to track earnings.

**Business Model**:
- Commissions earned on interest generated from loans
- Different borrowers may have different interest rates
- Commission rate varies by agreement with borrower
- Commission calculated per month (MVP1) or per day (Future)

---

### 3.2 Commission Formula

**Base Formula**:
```
Commission = (Loan Amount × Interest Rate × Time Period) × Commission Rate
```

**For Monthly Period** (MVP1):
```
Monthly Interest = Loan Amount × (Interest Rate / 12)
Commission = Monthly Interest × Commission Rate
```

**For Daily Period** (MVP1):
```
Daily Interest = Loan Amount x (Interest Rate / 365)
Commission = Daily Interest * Commission Rate 
```

**Example Calculation**:
```
Loan Amount: ₹10,000
Interest Rate: 12% per annum (0.12)
Commission Rate: 10% (0.10)
Period: 1 month

Step 1: Calculate Monthly Interest
Monthly Interest = ₹10,000 × (0.12 / 12)
                 = ₹10,000 × 0.01
                 = ₹100

Step 2: Calculate Commission
Commission = ₹100 × 0.10
           = ₹10

Result: ₹10 commission per month for this loan
```

---

### 3.3 Commission Calculation Inputs

| Input | Type | Required | Default | Validation | Notes |
|-------|------|----------|---------|------------|-------|
| `borrower_name` | String | Yes | - | Must exist in loans | Select from existing borrowers |
| `interest_rate` | Decimal | Yes | - | 0.01 - 100.00 (%) | Annual interest rate |
| `commission_rate` | Decimal | Yes | - | 0.01 - 100.00 (%) | Must be < interest_rate |
| `period_type` | Enum | Yes | "monthly" | monthly/daily | MVP1: Only monthly |
| `period_count` | Integer | Yes | 1 | 1 - 360 | Number of periods |

---

### 3.4 Commission Business Rules

**Rule 1: Commission Rate Validation**
```python
if commission_rate >= interest_rate:
    raise ValidationError("Commission rate must be less than interest rate")
```

**Rationale**: Commission is always a fraction of interest, never equal or greater.

---

**Rule 2: Historical Data Aggregation**
```python
# For borrower with multiple loans
total_commission = sum(
    calculate_commission(loan, interest_rate, commission_rate, period)
    for loan in borrower_loans
    if loan.status in ['active', 'overdue']  # Exclude paid_off
)
```

**Rationale**: Calculate commission on all active loans for borrower.

---

**Rule 3: Borrower Group Commission**
```python
# For borrower group
group_loans = get_loans(borrower_group=group_name)
total_commission = sum(
    calculate_commission(loan, interest_rate, commission_rate, period)
    for loan in group_loans
    if loan.status in ['active', 'overdue']
)
```

**Rationale**: Support bulk commission calculation for entire groups.

---

### 3.5 Interest Calculator Report Requirements

**Requirement ID**: REQ-INT-001
**Priority**: High

**Report Format**: Enhanced detailed breakdown per borrower

**Report Contents**:
1. **Borrower Name Header**: Display borrower/group name prominently
2. **Individual Loan Breakdown Table**:
   - **SNo**: Serial number in YYYY/xxx format (not Loan ID)
   - **Amount**: Principal amount in INR (₹)
   - **Giving Date**: Date loan was disbursed
   - **Depositor**: Name of lender
   - **LoanPeriod(Days or months)**: Number of days or months between giving_date and due_date (displays the value of LoanPeriod when no due date, i.e., due_date = 1970-01-01 is given for the record)
   - **Due Date**: Repayment due date (or "No due date" for 1970-01-01). Also if there is no due_date given and a value for LoanPeriod is included in the Interest calculator, then the due_date value should automatically be picked up depending on the number of Days/Months as provided with respect to giving date. 
   - **Interest Amount**: Total interest for the period
   - **Commission**: Total commission for the period

3. **Summary Totals**:
   - Total Loans count
   - Total Amount (sum of all loan amounts)
   - Total Interest (sum of all interest)
   - **Total Commission** (sum of all commission)

**Sample Report Output**:
```
Interest Calculator Report

John Doe

SNo      | Amount     | Giving Date | Depositor    | LoanPeriod(Days) | Due Date   | Interest   | Commission
─────────┼────────────┼─────────────┼──────────────┼──────────────────┼────────────┼────────────┼───────────
2026/001 | ₹100,000   | 2025-01-15  | Bank         | 365 days         | 2026-01-15 | ₹12,000    | ₹1,200
2026/002 | ₹50,000    | 2025-02-01  | Lender       | 181 days         | 2025-08-01 | ₹3,000     | ₹300

Summary:
  Total Loans: 2
  Total Amount: ₹150,000
  Total Interest: ₹15,000
  Total Commission: ₹1,500
```

**Display Rules**:
- All amounts in Indian number format with ₹ symbol
- Borrower name as H4 header above table
- **LoanPeriod(Days)** calculated as: `(due_date - giving_date)` in days
  - Displays "N/A" for loans with `due_date = 1970-01-01` (no specific due date)
  - Formula: `Math.ceil((due_date - giving_date) / (1000 * 60 * 60 * 24))` in JavaScript
- Due date formatted as YYYY-MM-DD or "No due date"

---

## 4. CSV Import Feature

### 4.1 Historical Data Import

**Requirement ID**: REQ-IMP-001
**Priority**: Medium
**User Story**: As a user, I want to import historical loan data from CSV to migrate from existing systems.

**Acceptance Criteria**:
- Support standard CSV format (UTF-8, comma-delimited)
- Handle missing optional fields gracefully
- Validate required fields before import
- Report import success/failure with details

---

### 4.2 CSV Format Specification

**Required Columns**:
- `borrower_name`
- `amount`
- `depositor_name`
- `giving_date` (Format: YYYY-MM-DD)

**Optional Columns**:
- `due_date` (Format: YYYY-MM-DD, Default: 1970-01-01)
- `borrower_group`
- `depositor_group`
- `status` (Default: auto-calculated)

**Example CSV**:
```csv
borrower_name,amount,depositor_name,giving_date,due_date,borrower_group,depositor_group
John Doe,10000.00,Jane Smith,2025-01-01,2025-12-31,Family,Personal
ABC Corp,50000.00,City Bank,2025-02-15,,Business,Bank
Mary Johnson,2500.00,Credit Union,2024-06-10,2025-06-10,Friends,Credit Union
```

---

### 4.3 Missing Value Handling

**Field-by-Field Rules**:

| Field | Missing Value Handling | Business Logic |
|-------|----------------------|----------------|
| `borrower_name` | **Error** - Required | Reject row, log error |
| `amount` | **Error** - Required | Reject row, log error |
| `depositor_name` | **Error** - Required | Reject row, log error |
| `giving_date` | **Error** - Required | Reject row, log error |
| `due_date` | **Default**: 1970-01-01 | Set to default, import row |
| `borrower_group` | **Default**: null/empty | Import row with null value |
| `depositor_group` | **Default**: null/empty | Import row with null value |
| `status` | **Auto-calculate** | Based on due_date vs today |

**Validation Logic**:
```python
def validate_csv_row(row):
    errors = []

    # Required fields
    if not row.get('borrower_name'):
        errors.append("Missing borrower_name")
    if not row.get('amount'):
        errors.append("Missing amount")
    elif float(row['amount']) <= 0:
        errors.append("Amount must be > 0")
    if not row.get('depositor_name'):
        errors.append("Missing depositor_name")
    if not row.get('giving_date'):
        errors.append("Missing giving_date")

    # Optional fields - set defaults
    if not row.get('due_date'):
        row['due_date'] = '1970-01-01'
    if not row.get('borrower_group'):
        row['borrower_group'] = None
    if not row.get('depositor_group'):
        row['depositor_group'] = None

    # Date validation
    if row.get('due_date') and row.get('giving_date'):
        if row['due_date'] < row['giving_date'] and row['due_date'] != '1970-01-01':
            errors.append("due_date must be >= giving_date")

    return errors, row
```

---

### 4.4 Import Process

**Steps**:
1. **Upload**: User uploads CSV file
2. **Validation**: System validates all rows
3. **Preview**: Show first 10 valid rows + error summary
4. **Confirmation**: User confirms import
5. **Import**: Batch insert valid rows
6. **Report**: Show success count + error log

**Error Handling**:
- **Partial Import**: Import valid rows, skip invalid rows
- **Error Report**: CSV file with failed rows + error messages
- **Rollback**: Option to undo import (if within same session)

---

## 5. Data Integrity Rules

### 5.1 Soft Delete Policy

**Rule**: Never hard delete loan records
**Rationale**: Preserve historical data for reporting and auditing

**Implementation**:
```python
def delete_loan(loan_id):
    loan.deleted_at = datetime.utcnow()
    loan.save()
    # Loan still exists in DB but excluded from queries
```

### 5.2 Status Update Rules

**Manual Updates Allowed**:
- active → paid_off ✅
- overdue → paid_off ✅
- paid_off → active ⚠️ (with confirmation)

**Auto-Updates** (Daily Background Job):
- active → overdue (if due_date < today)
- overdue → active (if due_date updated to future)

### 5.3 Amount Modification

**Rule**: Amount can be updated only for active loans
**Rationale**: Paid-off loans are historical records and should not change

**Validation**:
```python
if loan.status == 'paid_off' and new_amount != loan.amount:
    raise ValidationError("Cannot modify amount of paid-off loan")
```

---

## 6. Calculation Examples

### Example 1: Simple Interest Calculation

**Scenario**: Single loan, 1-month interest

```
Loan: ₹10,000
Interest Rate: 12% per annum
Commission Rate: 10%
Period: 1 month

Monthly Interest = ₹10,000 × (12% / 12) = ₹100
Commission = ₹100 × 10% = ₹10
```

### Example 2: Multi-Loan Borrower

**Scenario**: Borrower with 3 loans

```
Loan 1: ₹10,000 @ 12%
Loan 2: ₹5,000 @ 15%
Loan 3: ₹8,000 @ 10%

Commission Rate: 10%
Period: 12 months

Loan 1: (₹10,000 × 12%) × 10% × 12 = ₹144
Loan 2: (₹5,000 × 15%) × 10% × 12 = ₹90
Loan 3: (₹8,000 × 10%) × 10% × 12 = ₹96

Total Annual Commission = ₹330
```

### Example 3: Borrower Group

**Scenario**: "Family" group with 5 borrowers, 8 total loans

```
Same calculation as multi-loan but aggregated across all borrowers in group.
```

---

## 7. Future Enhancements (Post-MVP1)

### 7.1 Daily Commission Period
- Formula: `Daily Interest = Amount × (Rate / 365)`
- Use Case: Short-term loans, bridge financing

### 7.2 Variable Commission Rates
- Different rates per loan (store in loan record)
- Historical rate tracking

### 7.3 Commission Payment Tracking
- Record when commission is paid
- Outstanding commission balance

### 7.4 Advanced Filters
- Combine multiple filters (AND/OR logic)
- Saved filter presets
- Export filtered results

---

## 8. Edit History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-03-07 | System | Initial creation |
| 1.1.0 | 2026-03-08 | System | Post-demo updates: Currency INR-only policy, SNo format, Interest Calculator rename, Enhanced report format |
| 1.2.0 | 2026-03-08 | System | Updated Interest Calculator report: Changed "Ext Month/Days" to "LoanPeriod(Days)" with calculation logic (days between due_date and giving_date) |

---

## 9. Approval

**Business Owner**: _______________ Date: ___________
**Technical Lead**: _______________ Date: ___________
**QA Lead**: _______________ Date: ___________

---

**This is a living document. Please update as business requirements evolve.**
