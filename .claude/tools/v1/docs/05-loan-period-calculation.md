# LoanPeriod(Days) Calculation Feature

## 📋 Document Overview

**Version**: 1.0.0
**Last Updated**: March 8, 2026
**Status**: Active
**Feature ID**: FEAT-CALC-001

---

## 1. Feature Summary

### 1.1 Purpose
The **LoanPeriod** field displays the duration of a loan in days/months, calculated as the number of days between the `giving_date` (when the loan was disbursed) and the `due_date` (when repayment is expected).

This feature replaces the previous "Ext Month/Days" column which displayed an arbitrary extension period in months. Have a drop down option for allowing month/days as the unit for LoanPeriod.

### 1.2 Business Value
- **Accurate Duration Tracking**: Shows exact loan duration for reporting and analysis
- **Standardized Measurement**: All loans measured in consistent unit (days/month) depending on the unit selected by user.
- **Better Decision Making**: Enables comparison of short-term vs long-term loans
- **Audit Trail**: Clear calculation logic based on actual loan dates

---

## 2. Calculation Logic

### 2.1 Formula

```javascript
// For loans with a specific due date
loanPeriodDays = Math.ceil((dueDate - givingDate) / (1000 * 60 * 60 * 24))

// For loans without a due date (due_date = 1970-01-01)
loanPeriodDays = 'N/A'
```

**Breakdown**:
1. Subtract `givingDate` from `dueDate` to get difference in milliseconds
2. Divide by milliseconds in a day: `(1000 ms/s × 60 s/min × 60 min/hr × 24 hr/day)`
3. Round up using `Math.ceil()` to ensure partial days count as full days

### 2.2 Special Cases

#### Case 1: No Due Date (1970-01-01)
```javascript
givingDate = "2026-01-15"
dueDate = "1970-01-01"

Result: "N/A"
```
**Rationale**: `1970-01-01` is a special marker indicating "no specific due date" (perpetual/on-demand loan). Cannot calculate a meaningful period.

#### Case 2: Same Day Loan
```javascript
givingDate = "2026-03-08"
dueDate = "2026-03-08"

Result: 0 days
```
**Rationale**: Loan disbursed and due on the same day (same-day repayment expected).

#### Case 3: Long-Term Loan
```javascript
givingDate = "2026-01-01"
dueDate = "2027-01-01"

Result: 365 days
```
**Rationale**: Standard year duration.

#### Case 4: Leap Year
```javascript
givingDate = "2024-02-01"
dueDate = "2024-03-01"

Result: 29 days
```
**Rationale**: February 2024 has 29 days (leap year).

---

## 3. Implementation Details

### 3.1 Frontend (JavaScript)

**File**: `backend/static/app.js`

**Helper Function**:
```javascript
function calculateLoanPeriodDays(givingDate, dueDate) {
    // Handle special case: 1970-01-01 means no due date
    if (dueDate === '1970-01-01') {
        return 'N/A';
    }

    const startDate = new Date(givingDate);
    const endDate = new Date(dueDate);

    // Calculate difference in milliseconds, then convert to days
    const diffTime = endDate - startDate;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    return diffDays;
}
```

**Usage in Interest Calculator**:
```javascript
const loanPeriodDays = calculateLoanPeriodDays(loan.giving_date, loan.due_date);

// Display in table
const loanPeriodDisplay = loanPeriodDays === 'N/A' ? 'N/A' : `${loanPeriodDays} days`;
```

### 3.2 Unit Tests

**File**: `backend/tests/unit/test_interest_calculator.py`

**Test Class**: `TestLoanPeriodCalculation`

**Test Cases**:
1. `test_loan_period_30_days()` - Verify 30-day loan calculation
2. `test_loan_period_one_year()` - Verify 365-day (1 year) calculation
3. `test_loan_period_six_months()` - Verify ~181-day (6 months) calculation
4. `test_loan_period_no_due_date()` - Verify "N/A" for 1970-01-01 due dates
5. `test_loan_period_leap_year()` - Verify leap year (29-day February) calculation
6. `test_loan_period_display_format()` - Verify correct display format ("X days")

### 3.3 Display Locations

The **LoanPeriod(Days)** field appears in:

1. **Interest Calculator Report** (Web UI)
   - Table header: "LoanPeriod(Days)"
   - Value format: "365 days" or "N/A"

2. **CSV Export** (Interest Calculator)
   - Column header: "LoanPeriod(Days)"
   - Value format: "365 days" or "N/A"

---

## 4. Examples

### Example 1: Standard 1-Year Loan
```
Giving Date: 2026-01-01
Due Date: 2027-01-01

LoanPeriod(Days) = 365 days
```

### Example 2: Short-Term 30-Day Loan
```
Giving Date: 2026-01-01
Due Date: 2026-01-31

LoanPeriod(Days) = 30 days
```

### Example 3: No Due Date (Perpetual Loan)
```
Giving Date: 2026-01-15
Due Date: 1970-01-01

LoanPeriod(Days) = N/A
```

### Example 4: 6-Month Loan
```
Giving Date: 2026-01-01
Due Date: 2026-07-01

LoanPeriod(Days) = 181 days
```

### Example 5: Leap Year February
```
Giving Date: 2024-02-01
Due Date: 2024-03-01

LoanPeriod(Days) = 29 days
```

---

## 5. Migration from "Ext Month/Days"

### 5.1 Previous Implementation
- **Column Name**: "Ext Month/Days"
- **Value Source**: User input from calculator form (period_count in months)
- **Display Format**: "12 months", "6 months", etc.
- **Issue**: Not based on actual loan dates; arbitrary user input

### 5.2 New Implementation
- **Column Name**: "LoanPeriod(Days)"
- **Value Source**: Calculated from actual loan dates (due_date - giving_date)
- **Display Format**: "365 days", "181 days", "N/A", etc.
- **Benefit**: Accurate, date-based calculation reflecting actual loan duration

### 5.3 Breaking Changes
- Reports using "Ext Month/Days" will now show "LoanPeriod(Days)"
- Values changed from "X months" to "Y days"
- CSV exports updated with new column header

### 5.4 Compatibility
- **Frontend**: Fully backward compatible (only UI changes)
- **API**: No API changes required (dates already in loan schema)
- **Database**: No schema changes required (uses existing fields)
- **Tests**: New test class added; existing tests unaffected

---

## 6. Validation Rules

### 6.1 Input Validation
Since LoanPeriod is calculated (not input), validation applies to source fields:

**giving_date Validation**:
- Must be valid date format (YYYY-MM-DD)
- Cannot be in the future
- Required field

**due_date Validation**:
- Must be valid date format (YYYY-MM-DD)
- Must be >= giving_date (unless 1970-01-01)
- Special value 1970-01-01 allowed (means "no due date")

### 6.2 Calculation Edge Cases

**Negative Days**: Should not occur if validation is correct
```javascript
if (diffDays < 0 && dueDate !== '1970-01-01') {
    console.error('Invalid loan: due_date before giving_date');
    return 'Error';
}
```

**Very Large Values**: Loan periods > 10 years may indicate data entry error
```javascript
if (diffDays > 3650) {  // > 10 years
    console.warn('Loan period exceeds 10 years');
}
```

---

## 7. Performance Considerations

### 7.1 Calculation Cost
- **Operation**: Simple date subtraction and division
- **Complexity**: O(1) - constant time
- **Performance Impact**: Negligible (< 1ms per calculation)

### 7.2 Caching
Not required for current implementation. Calculation is:
- Fast enough to compute on-demand
- Based on immutable dates (don't change frequently)
- Only displayed in reports (not high-frequency queries)

---

## 8. Testing Strategy

### 8.1 Unit Tests (Completed)
Location: `backend/tests/unit/test_interest_calculator.py`

Coverage:
- ✅ Standard date ranges (30 days, 365 days)
- ✅ Special value (1970-01-01 → N/A)
- ✅ Leap year handling
- ✅ Display format

### 8.2 Integration Tests (Future)
Recommended additions:
- CSV export includes LoanPeriod(Days) column
- Interest calculator report displays correct values
- UI renders "N/A" for perpetual loans

### 8.3 Manual Testing Checklist
- [ ] Create loan with due_date = giving_date + 30 days
  - Verify LoanPeriod shows "30 days"
- [ ] Create loan with due_date = 1970-01-01
  - Verify LoanPeriod shows "N/A"
- [ ] Generate Interest Calculator report
  - Verify column header is "LoanPeriod(Days)"
  - Verify values match expected calculations
- [ ] Export CSV from Interest Calculator
  - Verify column header is "LoanPeriod(Days)"
  - Verify values are correct

---

## 9. Future Enhancements

### 9.1 Alternative Display Formats
Allow users to choose display format:
- Days only: "365 days"
- Months + Days: "12 months, 0 days"
- Years + Months: "1 year, 0 months"

### 9.2 Average Loan Period Analytics
Dashboard widget showing:
- Average loan period across all loans
- Shortest and longest active loans
- Loan period distribution histogram

### 9.3 Loan Period Categories
Auto-categorize loans:
- Short-term: < 90 days
- Medium-term: 90-365 days
- Long-term: > 365 days

---

## 10. Related Documentation

- [Business Requirements](./04-business-requirements.md) - Section 3.5 Interest Calculator Report Requirements
- [Frontend Architecture](./03-frontend-architecture.md) - Interest Calculator implementation
- [Test Plan](../testing/TEST_PLAN.md) - Unit test coverage

---

## 11. Change History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-03-08 | System | Initial documentation for LoanPeriod(Days) feature |

---

**Document Status**: ✅ Complete - Ready for Implementation
