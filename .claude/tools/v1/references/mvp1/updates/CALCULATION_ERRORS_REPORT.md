# Critical Calculation Errors - LoanTracker v1.x

## 🚨 Executive Summary

**Date**: March 12, 2026
**Severity**: HIGH
**Impact**: Interest calculations are mathematically incorrect for most loan periods
**Status**: Identified - Requires Immediate Fix

---

## ❌ Error #1: Incorrect Interest Calculation Logic

### Current Implementation (WRONG)

**Location**: `backend/static/app.js:379-393`

```javascript
// Current INCORRECT formula
if (periodUnit === 'days') {
    const dailyInterest = amount * (interestRate / 365);
    periodInterest = dailyInterest;
    totalInterest = dailyInterest * periodCount;  // ❌ WRONG
    totalCommission = totalInterest * commissionRate;
} else {
    const monthlyInterest = amount * (interestRate / 12);
    periodInterest = monthlyInterest;
    totalInterest = monthlyInterest * periodCount;  // ❌ WRONG
    totalCommission = totalInterest * commissionRate;
}
```

### Why This Is Wrong

The current formula assumes that interest compounds over the period by multiplying the period interest by the period count. This is **incorrect** because:

1. **It ignores the actual loan dates**: The formula uses `periodCount` (user input) instead of actual days between `giving_date` and `due_date`
2. **Incorrect for partial periods**: If a loan is for 6 months, it calculates as if it were 6 separate 1-month loans
3. **Not aligned with actual interest calculation standards**

### Correct Implementation

```javascript
// CORRECT formula
const givingDate = new Date(loan.giving_date);
const dueDate = new Date(loan.due_date);

// Calculate actual days between dates
const daysBetween = Math.ceil((dueDate - givingDate) / (1000 * 60 * 60 * 24));

// Calculate interest based on actual days
const totalInterest = amount * (annualInterestRate / 365) * daysBetween;
```

### Impact Examples

**Example 1: 6-month loan**
```
Amount: ₹100,000
Annual Rate: 12%
Giving Date: 2026-01-01
Due Date: 2026-07-01 (181 days)

Current (WRONG):
  Monthly Interest = 100,000 × (0.12 / 12) = ₹1,000
  Total Interest = ₹1,000 × 6 = ₹6,000 ❌

Correct:
  Total Interest = 100,000 × (0.12 / 365) × 181 = ₹5,950.68 ✓

Difference: ₹49.32 (0.8% error)
```

**Example 2: 90-day loan**
```
Amount: ₹50,000
Annual Rate: 18%
Giving Date: 2026-01-01
Due Date: 2026-04-01 (90 days)

Current (if using days mode):
  Daily Interest = 50,000 × (0.18 / 365) = ₹24.66
  Total Interest = ₹24.66 × 90 = ₹2,219.40 ✓

Current (if using months mode with 3 months):
  Monthly Interest = 50,000 × (0.18 / 12) = ₹750
  Total Interest = ₹750 × 3 = ₹2,250 ❌

Difference: ₹30.60 (1.4% error)
```

**Example 3: 1-year loan**
```
Amount: ₹200,000
Annual Rate: 10%
Giving Date: 2026-01-01
Due Date: 2027-01-01 (365 days)

Current (months mode):
  Monthly Interest = 200,000 × (0.10 / 12) = ₹1,666.67
  Total Interest = ₹1,666.67 × 12 = ₹20,000.04 ✓ (rounding)

Current (days mode):
  Daily Interest = 200,000 × (0.10 / 365) = ₹54.79
  Total Interest = ₹54.79 × 365 = ₹20,000.35 ✓ (rounding)

This case happens to work, but only coincidentally!
```

---

## ❌ Error #2: Period Count vs Actual Days Mismatch

### Problem

The current implementation asks the user to input `periodCount` and `periodUnit`, then uses these values in calculations. However:

1. **User enters "12 months"** but the actual loan might be 365 days, 360 days, or 366 days (leap year)
2. **User enters "30 days"** but forgets that the month has 31 days
3. **The loan's actual dates are ignored** in the interest calculation

### Correct Approach

The interest calculation should:
1. **Always use actual calendar days** between `giving_date` and `due_date`
2. **Ignore user input for period** - it's redundant when dates are known
3. **Use the formula**: `Amount × (Annual Rate / 365) × Actual Days`

---

## ❌ Error #3: Auto-calculated Due Dates Without Validation

### Current Implementation

**Location**: `backend/static/app.js:399-416`

```javascript
if (loan.due_date === '1970-01-01') {
    loanPeriodValue = periodCount;
    calculatedDueDate = new Date(givingDate);

    if (periodUnit === 'days') {
        calculatedDueDate.setDate(calculatedDueDate.getDate() + periodCount);
    } else {
        calculatedDueDate.setMonth(calculatedDueDate.getMonth() + periodCount);
    }
    calculatedDueDate = calculatedDueDate.toISOString().split('T')[0];
    needsUpdate = true;
}
```

### Problems

1. **Month arithmetic is imprecise**: Adding 1 month to Jan 31 gives Feb 28/29, not Mar 31
2. **Leap year edge cases**: Adding 1 year to Feb 29, 2024 gives Feb 28, 2025
3. **No validation**: If user enters 120 months, it blindly adds 10 years

### Impact

This creates inconsistency between what the user expects and what gets saved:
- User expects "6 months from Jan 15" to be July 15
- System might calculate July 14 or July 16 depending on month lengths

---

## ✅ Recommended Fixes

### Fix #1: Use Correct Interest Formula

**Priority**: CRITICAL
**Effort**: 2-3 hours

```javascript
function calculateLoanInterest(loan, annualInterestRate) {
    const amount = parseFloat(loan.amount);
    const givingDate = new Date(loan.giving_date);
    const dueDate = new Date(loan.due_date);

    // Calculate actual days
    const daysBetween = Math.ceil((dueDate - givingDate) / (1000 * 60 * 60 * 24));

    // Calculate interest
    const interest = amount * (annualInterestRate / 365) * daysBetween;

    return {
        amount,
        days: daysBetween,
        rate: annualInterestRate,
        interest
    };
}
```

### Fix #2: Remove Period Input from Interest Calculator

**Priority**: HIGH
**Effort**: 4-5 hours

- Remove `period_count` and `period_unit` inputs
- Calculate interest based solely on actual loan dates
- Filter loans by month (as per new requirement)
- Allow per-loan interest rate input

### Fix #3: Improve Date Calculation Precision

**Priority**: MEDIUM
**Effort**: 2-3 hours

```javascript
// Use date-fns library for precise date arithmetic
import { addMonths, addDays } from 'date-fns';

// For month-based periods
const newDueDate = addMonths(givingDate, monthCount);

// For day-based periods
const newDueDate = addDays(givingDate, dayCount);
```

---

## 📊 Test Cases to Add

### Test Suite: Correct Interest Calculations

```python
def test_interest_calculation_90_days():
    """Test interest for 90-day loan at 12% annual rate."""
    amount = Decimal('100000.00')
    annual_rate = Decimal('0.12')
    days = 90

    expected_interest = amount * (annual_rate / 365) * days
    # Expected: ₹2,958.90

    actual_interest = calculate_interest(amount, annual_rate, days)
    assert abs(actual_interest - expected_interest) < Decimal('0.01')

def test_interest_calculation_181_days():
    """Test interest for 181-day loan at 12% annual rate."""
    amount = Decimal('100000.00')
    annual_rate = Decimal('0.12')
    days = 181

    expected_interest = amount * (annual_rate / 365) * days
    # Expected: ₹5,950.68

    actual_interest = calculate_interest(amount, annual_rate, days)
    assert abs(actual_interest - expected_interest) < Decimal('0.01')

def test_interest_uses_actual_days_not_months():
    """Verify that interest uses actual days, not month approximations."""
    amount = Decimal('50000.00')
    annual_rate = Decimal('0.18')
    giving_date = date(2026, 1, 1)
    due_date = date(2026, 4, 1)

    # Actual days: 90
    days = (due_date - giving_date).days

    # Should use 90 days, not "3 months"
    expected_interest = amount * (annual_rate / 365) * Decimal(days)
    # Expected: ₹2,219.18

    actual_interest = calculate_interest_from_dates(
        amount, annual_rate, giving_date, due_date
    )
    assert abs(actual_interest - expected_interest) < Decimal('0.01')
```

---

## 📈 Migration Strategy

### Step 1: Deprecation Notice (Week 1)
- Add warning banner to Interest Calculator
- "Note: Interest calculation formula will be updated in next release"
- Allow users to export current calculations for comparison

### Step 2: Implement New Calculator (Week 2-3)
- Build new Interest Calculator with correct formula
- Keep old calculator accessible as "Legacy Mode"
- Run both calculators in parallel for testing

### Step 3: Validation & Testing (Week 4)
- Compare results from old vs new calculator
- Identify any business rules that depend on old formula
- Get stakeholder sign-off on new calculations

### Step 4: Deployment (Week 5)
- Deploy new calculator as default
- Archive old calculator
- Update all documentation

---

## 💰 Business Impact

### Potential Financial Discrepancies

If the incorrect formula has been used in production:

1. **Overcharged Interest** (months mode for periods < 12 months):
   - Example: 6-month loan incorrectly calculated as 6 × monthly interest
   - Could lead to customer complaints or refunds

2. **Undercharged Interest** (days mode with wrong period count):
   - Example: User enters "30 days" for a 31-day loan
   - Lost revenue on interest

3. **Commission Calculation Errors**:
   - If commission is based on incorrect interest, all commission reports are wrong
   - May need to recalculate historical commissions

### Recommended Actions

1. **Audit Historical Data**: Review past 6 months of interest calculations
2. **Customer Communication**: Notify customers of calculation correction
3. **Reconciliation**: Offer to recalculate and adjust any significantly impacted loans
4. **Documentation**: Update all user-facing documentation with correct formula

---

## 📝 Summary

| Error | Severity | Impact | Fix Effort |
|-------|----------|--------|------------|
| Incorrect interest formula | CRITICAL | Financial discrepancies | 2-3 hours |
| Period count vs actual days | HIGH | Calculation inaccuracy | 4-5 hours |
| Date arithmetic imprecision | MEDIUM | Edge case errors | 2-3 hours |

**Total Fix Effort**: 8-11 hours
**Recommended Timeline**: 1-2 weeks (including testing & validation)

---

**Reported by**: Claude Code Assistant
**Date**: March 12, 2026
**Status**: Pending stakeholder review and approval for fixes
