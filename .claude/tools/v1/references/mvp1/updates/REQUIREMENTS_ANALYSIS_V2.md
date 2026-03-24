# LoanTracker v2.0 - Requirements Analysis & Test Plan

## 📋 Document Overview

**Version**: 2.0.0
**Date**: March 12, 2026
**Status**: 🔍 Analysis & Planning
**Type**: Feature Enhancement & Redesign

---

## 🚨 Critical Issues Identified in Current Implementation

### Issue 1: Incorrect Interest Calculation Formula

**Current Implementation**:
```javascript
// Monthly calculation
const monthlyInterest = amount * (interestRate / 12);
totalInterest = monthlyInterest * periodCount;

// Daily calculation
const dailyInterest = amount * (interestRate / 365);
totalInterest = dailyInterest * periodCount;
```

**Problem**:
- The current formula treats `periodCount` as a multiplier for period interest
- This is **incorrect** for actual interest calculation
- Example: ₹10,000 at 12% for 12 months should yield ₹1,200 total interest
- Current formula: (10000 × 0.12/12) × 12 = ₹100 × 12 = ₹1,200 ✓ (accidentally correct)
- But for 6 months: (10000 × 0.12/12) × 6 = ₹100 × 6 = ₹600 ❌ (WRONG!)
- **Should be**: 10000 × (0.12/365) × 181 days = ₹595.89 ✓

**Correct Formula** (as per user requirement):
```
Interest = Amount × (Annual Interest Rate / 365) × (Number of days between giving_date and due_date)
```

### Issue 2: Commission Calculation Misunderstanding

**Current Implementation**:
```javascript
commission = totalInterest * commissionRate;
```
**Proposed Implementation**:
```javascript
commission = Interest * commissionRate;
```
**Problem**:
- Current implementation calculates commission as a percentage of interest
- This may not align with business intent
- Need clarification: Is commission on interest or on loan amount?

**User's New Requirement**:
- User wants **per-record interest rate input**
- Interest calculation should be: `Amount × (AnnualInterestRate/365) × days_between_dates`
- For only the records selected as the starting month by user, Total Commission and summary should still be calculated 

---

## 🎯 New Requirements Breakdown

### Requirement 1: View Loans Tab - Sortable Table

**Requirement ID**: REQ-VIEW-001
**Priority**: High
**Status**: New Feature

#### Functional Requirements:

1. **Display All Loan Records**
   - Show all loans in a tabular format
   - Include all relevant fields
   - Support pagination for large datasets

2. **Excel-like Sorting**
   - Sortable columns:
     - Borrower Name (alphabetical A-Z, Z-A)
     - Borrower Group (alphabetical A-Z, Z-A)
     - Depositor Name (alphabetical A-Z, Z-A)
     - Depositor Group (alphabetical A-Z, Z-A)
     - Giving Date (oldest first, newest first)
     - Due Date (earliest first, latest first)

3. **Visual Indicators**
   - Sort direction arrows (▲ ascending, ▼ descending)
   - Active sort column highlighting
   - Hover effects on column headers

#### Technical Specifications:

```javascript
// Sort state management
const [sortConfig, setSortConfig] = useState({
    key: null,        // Column to sort by
    direction: 'asc'  // 'asc' or 'desc'
});

// Sort function
function sortLoans(loans, sortConfig) {
    if (!sortConfig.key) return loans;

    return [...loans].sort((a, b) => {
        const aValue = a[sortConfig.key];
        const bValue = b[sortConfig.key];

        // Handle dates
        if (sortConfig.key.includes('date')) {
            return sortConfig.direction === 'asc'
                ? new Date(aValue) - new Date(bValue)
                : new Date(bValue) - new Date(aValue);
        }

        // Handle strings
        if (typeof aValue === 'string') {
            return sortConfig.direction === 'asc'
                ? aValue.localeCompare(bValue)
                : bValue.localeCompare(aValue);
        }

        // Handle numbers
        return sortConfig.direction === 'asc'
            ? aValue - bValue
            : bValue - aValue;
    });
}
```

#### UI/UX Design:

```html
<table class="loans-table sortable">
    <thead>
        <tr>
            <th onclick="requestSort('borrower_name')" class="sortable-header">
                Borrower Name
                <span class="sort-arrow">▲</span>
            </th>
            <th onclick="requestSort('borrower_group')" class="sortable-header">
                Borrower Group
                <span class="sort-arrow"></span>
            </th>
            <!-- More headers -->
        </tr>
    </thead>
    <tbody>
        <!-- Sorted loan rows -->
    </tbody>
</table>
```

#### Test Cases:

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| TC-SORT-001 | Click "Borrower Name" header once | Sort ascending (A-Z) |
| TC-SORT-002 | Click "Borrower Name" header twice | Sort descending (Z-A) |
| TC-SORT-003 | Click "Borrower Name", then "Giving Date" | Sort by Giving Date, previous sort cleared |
| TC-SORT-004 | Sort by "Due Date" with 1970-01-01 dates | 1970-01-01 dates sorted to beginning/end based on direction |
| TC-SORT-005 | Sort with 100+ records | Sorting completes within 500ms |
| TC-SORT-006 | Sort by empty/null Group fields | Nulls appear first in ascending, last in descending |

---

### Requirement 2: View Loans Tab - Inline Editing

**Requirement ID**: REQ-VIEW-002
**Priority**: High
**Status**: New Feature

#### Functional Requirements:

1. **Editable Fields**:
   - Giving Date
   - Due Date
   - Borrower Name
   - Depositor Name
   - Amount
   - Borrower Group
   - Depositor Group

2. **Edit Interaction**:
   - Click on cell to enter edit mode
   - Show input field with current value
   - Save on blur or Enter key
   - Cancel on Escape key
   - Visual indication of edit mode

3. **Data Persistence**:
   - Auto-save to backend on field change
   - Show success/error notification
   - Optimistic UI update
   - Rollback on save failure

4. **Validation**:
   - Amount: Must be > 0, max 2 decimal places
   - Dates: Must be valid dates, due_date >= giving_date (except 1970-01-01)
   - Names: Non-empty strings, max 200 characters
   - Groups: Optional, max 100 characters

#### Technical Specifications:

```javascript
// Inline edit component
function EditableCell({ value, fieldName, loanId, onSave }) {
    const [isEditing, setIsEditing] = useState(false);
    const [editValue, setEditValue] = useState(value);
    const [isSaving, setIsSaving] = useState(false);

    const handleSave = async () => {
        if (editValue === value) {
            setIsEditing(false);
            return;
        }

        setIsSaving(true);
        try {
            await apiCall(`/loans/${loanId}`, {
                method: 'PATCH',
                body: JSON.stringify({ [fieldName]: editValue })
            });
            onSave(loanId, fieldName, editValue);
            showSuccess('Loan updated successfully');
            setIsEditing(false);
        } catch (error) {
            showError('Failed to update loan');
            setEditValue(value); // Rollback
        } finally {
            setIsSaving(false);
        }
    };

    if (isEditing) {
        return (
            <input
                type={getInputType(fieldName)}
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onBlur={handleSave}
                onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSave();
                    if (e.key === 'Escape') {
                        setEditValue(value);
                        setIsEditing(false);
                    }
                }}
                autoFocus
                disabled={isSaving}
            />
        );
    }

    return (
        <span
            onClick={() => setIsEditing(true)}
            className="editable-cell"
            title="Click to edit"
        >
            {formatValue(value, fieldName)}
        </span>
    );
}
```

#### UI/UX Design:

- **Normal state**: Cell shows value with light gray border on hover
- **Edit state**: Input field with blue border, slightly larger
- **Saving state**: Loading spinner, disabled input
- **Success state**: Green flash animation
- **Error state**: Red flash animation, value reverts

#### Test Cases:

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| TC-EDIT-001 | Click on Amount cell | Input field appears with current value |
| TC-EDIT-002 | Edit amount to "5000.50", press Enter | Value saves, cell shows "₹5,000.50" |
| TC-EDIT-003 | Edit amount to "-100", press Enter | Error shown, value reverts |
| TC-EDIT-004 | Edit giving_date to "2026-12-01" | Value saves and updates |
| TC-EDIT-005 | Edit due_date to "2025-01-01" (before giving_date) | Error shown for invalid date |
| TC-EDIT-006 | Edit borrower_name to empty string | Error shown, value reverts |
| TC-EDIT-007 | Edit amount, press Escape | Edit cancelled, original value remains |
| TC-EDIT-008 | Edit amount, click outside | Value auto-saves |
| TC-EDIT-009 | Edit while offline | Error shown, value reverts |
| TC-EDIT-010 | Edit borrower_group to null/empty | Saves successfully (optional field) |

---

### Requirement 3: Action Status Toggle with Popups

**Requirement ID**: REQ-STATUS-001
**Priority**: High
**Status**: New Feature

#### Functional Requirements:

##### Action 1: Active

**Constraints**: `giving_date <= current_date < due_date`
**Feature**: Default status if constraint is true
**Behavior**:
- Automatically set on loan creation if constraint met
- Cannot manually set if constraint not met
- Visual indicator: Blue badge "Active"

##### Action 2: Paid Off

**Constraints**: `current_date <= due_date`
**Feature**: User-triggered with popup
**Behavior**:
1. User clicks "Mark as Paid Off" button
2. Popup appears with date picker for `paidoff_date`
3. User enters paidoff_date
4. System validates: paidoff_date must be <= current_date
5. If `due_date == current_date` OR `paidoff_date == due_date`:
   - Prompt: "Loan paid on due date. Delete record permanently?"
   - If Yes: Delete loan record
   - If No: Mark as paid_off with paidoff_date
6. Else: Mark as paid_off with paidoff_date
7. Visual indicator: Green badge "Paid Off"

**Data Model Addition**:
```python
class Loan(BaseModel):
    # ... existing fields ...
    paidoff_date: Optional[date] = None  # NEW FIELD
```

##### Action 3: Overdue

**Constraints**: `current_date > due_date`
**Feature**: Default status if constraint is true
**Behavior**:
- Automatically set when current_date exceeds due_date
- Cannot manually set if constraint not met
- Visual indicator: Red badge "Overdue"
- Shows "Days Overdue" count

##### Action 4: Extend

**Constraints**: None (can extend any loan)
**Feature**: User-triggered with popup
**Behavior**:
1. User clicks "Extend Loan" button
2. Popup appears with date picker for `new_due_date`
3. User enters new_due_date
4. System validates: new_due_date must be > old due_date
5. System updates:
   - `giving_date = MIN(old_due_date, current_date)`
   - `due_date = new_due_date`
6. Create audit trail entry (optional enhancement)
7. Visual indicator: Orange badge "Extended"

**Rationale**: When extending, the new loan period starts from the old due date (or current date if past due), and ends on the new due date.

#### Technical Specifications:

```javascript
// Status toggle component
function StatusToggle({ loan, onStatusChange }) {
    const [showPopup, setShowPopup] = useState(false);
    const [actionType, setActionType] = useState(null);

    const handleStatusClick = (action) => {
        if (action === 'paidoff' || action === 'extend') {
            setActionType(action);
            setShowPopup(true);
        }
    };

    const handlePaidOff = async (paidoffDate) => {
        // Check if should delete
        if (loan.due_date === formatDate(new Date()) ||
            paidoffDate === loan.due_date) {
            const shouldDelete = await confirm(
                'Loan paid on due date. Delete record permanently?'
            );

            if (shouldDelete) {
                await apiCall(`/loans/${loan.id}`, { method: 'DELETE' });
                onStatusChange(loan.id, 'deleted');
                return;
            }
        }

        // Mark as paid off
        await apiCall(`/loans/${loan.id}`, {
            method: 'PATCH',
            body: JSON.stringify({
                status: 'paid_off',
                paidoff_date: paidoffDate
            })
        });
        onStatusChange(loan.id, 'paid_off', paidoffDate);
    };

    const handleExtend = async (newDueDate) => {
        const today = new Date();
        const oldDueDate = new Date(loan.due_date);
        const newGivingDate = oldDueDate < today ? oldDueDate : today;

        await apiCall(`/loans/${loan.id}`, {
            method: 'PATCH',
            body: JSON.stringify({
                giving_date: formatDate(newGivingDate),
                due_date: newDueDate,
                status: 'active'  // Reset to active after extension
            })
        });
        onStatusChange(loan.id, 'extended');
    };

    return (
        <>
            <div className="status-toggle">
                <select onChange={(e) => handleStatusClick(e.target.value)}>
                    <option value="">Change Status</option>
                    <option value="paidoff">Mark as Paid Off</option>
                    <option value="overdue">Mark as Overdue</option>
                    <option value="extend">Extend Loan</option>
                </select>
            </div>

            {showPopup && actionType === 'paidoff' && (
                <PaidOffPopup
                    loan={loan}
                    onConfirm={handlePaidOff}
                    onCancel={() => setShowPopup(false)}
                />
            )}

            {showPopup && actionType === 'extend' && (
                <ExtendPopup
                    loan={loan}
                    onConfirm={handleExtend}
                    onCancel={() => setShowPopup(false)}
                />
            )}
        </>
    );
}
```

#### UI/UX Design:

**Status Badge Design**:
```css
.status-badge {
    padding: 4px 12px;
    border-radius: 12px;
    font-size: 0.85em;
    font-weight: 600;
}

.status-active {
    background: #E3F2FD;
    color: #1976D2;
}

.status-paid-off {
    background: #E8F5E9;
    color: #388E3C;
}

.status-overdue {
    background: #FFEBEE;
    color: #D32F2F;
}

.status-extended {
    background: #FFF3E0;
    color: #F57C00;
}
```

**Popup Design**:
```html
<!-- Paid Off Popup -->
<div class="popup-overlay">
    <div class="popup-content">
        <h3>Mark Loan as Paid Off</h3>
        <p><strong>Borrower:</strong> {loan.borrower_name}</p>
        <p><strong>Amount:</strong> ₹{loan.amount}</p>

        <label for="paidoff_date">Paid Off Date *</label>
        <input type="date" id="paidoff_date" max="{today}" required />

        <div class="popup-actions">
            <button class="button button-secondary" onclick="cancel()">Cancel</button>
            <button class="button button-primary" onclick="confirm()">Confirm</button>
        </div>
    </div>
</div>

<!-- Extend Popup -->
<div class="popup-overlay">
    <div class="popup-content">
        <h3>Extend Loan Period</h3>
        <p><strong>Borrower:</strong> {loan.borrower_name}</p>
        <p><strong>Current Due Date:</strong> {loan.due_date}</p>

        <label for="new_due_date">New Due Date *</label>
        <input type="date" id="new_due_date" min="{tomorrow}" required />

        <div class="info-box">
            <p><strong>Note:</strong> Giving date will be updated to {MIN(old_due_date, today)}</p>
        </div>

        <div class="popup-actions">
            <button class="button button-secondary" onclick="cancel()">Cancel</button>
            <button class="button button-primary" onclick="confirm()">Extend Loan</button>
        </div>
    </div>
</div>
```

#### Test Cases:

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| TC-STATUS-001 | New loan with future due_date created | Status auto-set to "Active" |
| TC-STATUS-002 | Current date exceeds due_date | Status auto-changes to "Overdue" |
| TC-STATUS-003 | Click "Mark as Paid Off", enter paidoff_date = due_date | Prompt to delete appears |
| TC-STATUS-004 | Confirm delete on paid-off loan | Loan record deleted from database |
| TC-STATUS-005 | Decline delete on paid-off loan | Loan marked as paid_off, paidoff_date saved |
| TC-STATUS-006 | Click "Mark as Paid Off", enter future paidoff_date | Error: "Paid off date cannot be in future" |
| TC-STATUS-007 | Click "Extend", enter new_due_date < old_due_date | Error: "New due date must be after current due date" |
| TC-STATUS-008 | Extend overdue loan (current_date > due_date) | giving_date = old_due_date, due_date = new_due_date |
| TC-STATUS-009 | Extend active loan (current_date < due_date) | giving_date = current_date, due_date = new_due_date |
| TC-STATUS-010 | Extend loan with due_date = 1970-01-01 | giving_date = current_date, due_date = new_due_date |

---

### Requirement 4: Redesigned Interest Calculator

**Requirement ID**: REQ-CALC-002
**Priority**: Critical
**Status**: Major Redesign

#### Functional Requirements:

1. **Filter by Month**:
   - User selects a month (e.g., "March 2026")
   - System filters loans where `due_date` is in selected month and today's date
   - Display filtered loan records

2. **Per-Record Interest Rate and Commission Rate**:
   - Each filtered loan shows input field for "Annual Interest Rate (%)" and commission rate [OPTIONAL].
   - User enters rate for each loan individually, if commissionRate is not given, it is not calculated and the record does not count towards total commision calculation
   - Default: [12%, 1%] (configurable)

3. **Interest Calculation**:
   - **Correct Formula**: `Interest = Amount × (Annual Rate / 365) × Days Between Dates`
   - **Days Between Dates**: `(due_date - giving_date)` in days
   - **Commission**: `Commission = Interest * commissionRate` and `TotalCommission = Sum of the commission for all records falling between the time window of first day of selected month and today`

4. **Display Results**:
   - Show calculated interest per loan
   - Show total interest for all loans in month
   - Show total commissions for all loans 
   - Export to CSV

#### Old vs New Comparison:

| Aspect | Old Implementation | New Implementation |
|--------|-------------------|-------------------|
| Filter | By Borrower/Group | By Month (due_date) |
| Interest Rate | Single rate for all loans | Per-record rate input |
| Formula | `(Amount × Rate/12) × Months` | `Amount × (Rate/365) × Days` |
| Period Input | User enters period count | Auto-calculated from dates |
| Commission | Calculated | Removed |

#### Technical Specifications:

```javascript
// New Interest Calculator
async function calculateInterestByMonth(event) {
    event.preventDefault();

    const selectedMonth = document.getElementById('month_filter').value; // "2026-03"
    const loans = await loadLoans();

    // Filter loans by month
    const filteredLoans = loans.filter(loan => {
        if (loan.due_date === '1970-01-01') return false;
        const dueMonth = loan.due_date.substring(0, 7); // "2026-03"
        return dueMonth === selectedMonth;
    });

    if (filteredLoans.length === 0) {
        showError('No loans with due dates in selected month');
        return;
    }

    // Calculate interest for each loan
    const results = filteredLoans.map((loan, index) => {
        const amount = parseFloat(loan.amount);
        const annualRate = parseFloat(
            document.getElementById(`rate_${loan.id}`).value
        ) / 100; // Convert % to decimal

        // Calculate days between dates
        const givingDate = new Date(loan.giving_date);
        const dueDate = new Date(loan.due_date);
        const daysBetween = Math.ceil(
            (dueDate - givingDate) / (1000 * 60 * 60 * 24)
        );

        // Calculate interest
        const interest = amount * (annualRate / 365) * daysBetween;

        return {
            sno: generateSNo(index, loan.giving_date),
            borrower: loan.borrower_name,
            depositor: loan.depositor_name,
            amount: amount,
            givingDate: loan.giving_date,
            dueDate: loan.due_date,
            daysBetween: daysBetween,
            annualRate: annualRate * 100,
            interest: interest,
            loanId: loan.id
        };
    });

    // Calculate total
    const totalAmount = results.reduce((sum, r) => sum + r.amount, 0);
    const totalInterest = results.reduce((sum, r) => sum + r.interest, 0);

    displayInterestResults(results, {
        selectedMonth,
        totalAmount,
        totalInterest
    });
}
```

#### UI/UX Design:

```html
<!-- New Interest Calculator Form -->
<form id="interest-calc-form" onsubmit="calculateInterestByMonth(event)">
    <div class="form-group">
        <label for="month_filter">Select Month *</label>
        <input type="month" id="month_filter" required />
        <small>Filter loans by due date month</small>
    </div>

    <button type="button" onclick="loadLoansForMonth()" class="button button-secondary">
        Load Loans for Month
    </button>

    <!-- Dynamically loaded loan list -->
    <div id="loans-list" style="margin-top: 20px;">
        <!-- For each loan in selected month -->
        <div class="loan-interest-row">
            <div class="loan-info">
                <strong>{borrower_name}</strong> - ₹{amount}
                <br>
                <small>{giving_date} → {due_date} ({days_between} days)</small>
            </div>
            <div class="rate-input">
                <label>Annual Rate (%)</label>
                <input
                    type="number"
                    id="rate_{loan_id}"
                    min="0.01"
                    max="100"
                    step="0.01"
                    value="12.00"
                    required
                />
            </div>
        </div>
    </div>

    <button type="submit" class="button button-primary">
        Calculate Interest
    </button>
</form>

<!-- Results Display -->
<div id="interest-results">
    <h3>Interest Calculation Results - {Month YYYY}</h3>

    <table>
        <thead>
            <tr>
                <th>SNo</th>
                <th>Borrower</th>
                <th>Amount</th>
                <th>Giving Date</th>
                <th>Due Date</th>
                <th>Days</th>
                <th>Rate (%)</th>
                <th>Interest</th>
            </tr>
        </thead>
        <tbody>
            {/* For each result */}
            <tr>
                <td>{sno}</td>
                <td>{borrower}</td>
                <td>₹{amount}</td>
                <td>{givingDate}</td>
                <td>{dueDate}</td>
                <td>{daysBetween}</td>
                <td>{annualRate}%</td>
                <td>₹{interest}</td>
            </tr>
        </tbody>
    </table>

    <div class="summary">
        <h4>Summary</h4>
        <p><strong>Total Loans:</strong> {count}</p>
        <p><strong>Total Amount:</strong> ₹{totalAmount}</p>
        <p><strong>Total Interest:</strong> ₹{totalInterest}</p>
    </div>
</div>
```

#### Calculation Examples:

**Example 1: Standard Loan**
```
Loan Amount: ₹100,000
Giving Date: 2026-01-01
Due Date: 2026-03-31 (90 days later)
Annual Interest Rate: 12%

Interest = 100,000 × (0.12 / 365) × 90
         = 100,000 × 0.000328767 × 90
         = ₹2,958.90
```

**Example 2: Short-term Loan**
```
Loan Amount: ₹50,000
Giving Date: 2026-03-01
Due Date: 2026-03-15 (14 days later)
Annual Interest Rate: 18%

Interest = 50,000 × (0.18 / 365) × 14
         = 50,000 × 0.000493151 × 14
         = ₹345.21
```

**Example 3: Long-term Loan**
```
Loan Amount: ₹200,000
Giving Date: 2025-03-01
Due Date: 2026-03-01 (365 days later)
Annual Interest Rate: 10%

Interest = 200,000 × (0.10 / 365) × 365
         = 200,000 × 0.10
         = ₹20,000.00
```

#### Test Cases:

| Test ID | Test Case | Expected Result |
|---------|-----------|-----------------|
| TC-CALC-001 | Select "March 2026", 5 loans have due dates in March | 5 loans loaded with rate inputs |
| TC-CALC-002 | Loan: ₹100,000, 90 days, 12% rate | Interest = ₹2,958.90 |
| TC-CALC-003 | Loan: ₹50,000, 14 days, 18% rate | Interest = ₹345.21 |
| TC-CALC-004 | Loan: ₹200,000, 365 days, 10% rate | Interest = ₹20,000.00 |
| TC-CALC-005 | Enter rate as "15.5%" for one loan | Accepts decimal rates |
| TC-CALC-006 | Select month with no loans | "No loans with due dates in selected month" |
| TC-CALC-007 | Loan with due_date = 1970-01-01 | Not included in any month filter |
| TC-CALC-008 | Change rate from 12% to 15%, recalculate | Interest recalculated with new rate |
| TC-CALC-009 | Export results to CSV | CSV contains all columns with correct calculations |
| TC-CALC-010 | 20 loans in same month with different rates | All calculated correctly |

---

## 📦 Database Schema Changes

### New Field: paidoff_date

**File**: `backend/app/schemas/loan.py`

```python
class Loan(BaseModel):
    id: str
    borrower_name: str
    amount: Decimal
    depositor_name: str
    giving_date: date
    due_date: date
    status: Status
    paidoff_date: Optional[date] = None  # NEW FIELD
    borrower_group: Optional[str] = None
    depositor_group: Optional[str] = None
    currency: Currency = Currency.INR
    created_at: datetime
    updated_at: datetime
```

**Migration**: Add column to CSV storage with default value `None`

---

## 🧪 Comprehensive Test Plan

### Unit Tests

#### Test Suite 1: Sorting Functionality
- `test_sort_by_borrower_name_asc()`
- `test_sort_by_borrower_name_desc()`
- `test_sort_by_giving_date_asc()`
- `test_sort_by_due_date_desc()`
- `test_sort_with_null_values()`
- `test_sort_with_1970_dates()`

#### Test Suite 2: Inline Editing
- `test_edit_amount_valid()`
- `test_edit_amount_negative_rejected()`
- `test_edit_date_valid()`
- `test_edit_date_invalid_rejected()`
- `test_edit_name_empty_rejected()`
- `test_edit_rollback_on_error()`

#### Test Suite 3: Status Actions
- `test_auto_active_status_on_creation()`
- `test_auto_overdue_on_date_exceeded()`
- `test_paidoff_with_delete_confirmation()`
- `test_paidoff_without_delete()`
- `test_extend_loan_updates_dates()`
- `test_extend_overdue_loan()`

#### Test Suite 4: Interest Calculation (NEW)
- `test_interest_90_days_12_percent()`
- `test_interest_14_days_18_percent()`
- `test_interest_365_days_10_percent()`
- `test_filter_by_month_march_2026()`
- `test_empty_month_filter()`
- `test_per_loan_different_rates()`

### Integration Tests

#### Test Suite 5: End-to-End Workflows
- `test_create_loan_edit_amount_mark_paidoff()`
- `test_create_overdue_loan_extend_dates()`
- `test_calculate_interest_for_month_export_csv()`
- `test_sort_loans_edit_inline_verify_persistence()`

### Performance Tests

#### Test Suite 6: Performance Benchmarks
- `test_sort_1000_loans_under_500ms()`
- `test_inline_edit_save_under_200ms()`
- `test_interest_calculation_100_loans_under_1s()`

---

## 📝 Implementation Steps

### Phase 1: View Loans - Sorting (3-4 hours)
1. Add sort state management
2. Implement sort function for all column types
3. Add sort UI indicators (arrows)
4. Add click handlers to table headers
5. Write unit tests for sorting
6. Manual testing with various data sets

### Phase 2: View Loans - Inline Editing (5-6 hours)
1. Create EditableCell component
2. Implement edit mode toggle
3. Add validation for each field type
4. Implement API save with optimistic updates
5. Add error handling and rollback
6. Write unit and integration tests
7. Manual testing of all editable fields

### Phase 3: Status Actions & Popups (6-7 hours)
1. Add paidoff_date field to schema
2. Create PaidOffPopup component
3. Create ExtendPopup component
4. Implement status auto-detection logic
5. Implement paidoff with delete confirmation
6. Implement extend with date calculations
7. Update API endpoints if needed
8. Write comprehensive test suite
9. Manual testing of all action flows

### Phase 4: Interest Calculator Redesign (7-8 hours)
1. Remove old calculator UI
2. Create new month filter UI
3. Implement loan filtering by month
4. Create per-loan rate input fields
5. Implement correct interest formula
6. Remove commission calculation
7. Update results display
8. Update CSV export
9. Write unit tests for calculations
10. Write integration tests
11. Update documentation

### Phase 5: Testing & Documentation (3-4 hours)
1. Run full test suite
2. Fix any failing tests
3. Update business requirements doc
4. Update frontend architecture doc
5. Create user guide
6. Code review and refactoring

**Total Estimated Time**: 24-29 hours

---

## ✅ Success Criteria

1. ✅ All loans sortable by 6 columns (Name, Group, Date fields)
2. ✅ All editable fields save correctly to backend
3. ✅ Validation prevents invalid data entry
4. ✅ Status actions work as specified with correct constraints
5. ✅ Interest calculation uses correct formula: Amount × (Rate/365) × Days
6. ✅ Month filter correctly filters loans by due_date
7. ✅ Per-record interest rates accepted and calculated
8. ✅ All 100+ tests passing
9. ✅ Documentation updated
10. ✅ No regression in existing functionality

---

## 🚧 Known Issues & Limitations

1. **CSV Storage**: Current implementation uses CSV files. Inline editing with concurrent users may have race conditions.
   - **Mitigation**: Add file locking or migrate to SQLite for better concurrency

2. **Large Datasets**: Sorting 1000+ loans in browser may have performance issues
   - **Mitigation**: Implement pagination + server-side sorting

3. **Date Validation**: Edge cases with leap years, timezone differences
   - **Mitigation**: Use date-fns library for robust date handling

4. **Audit Trail**: No history of loan extensions or edits
   - **Enhancement**: Add audit_log table for tracking changes

---

## 📚 Related Documents

- [Business Requirements v1.2.0](../../docs/04-business-requirements.md)
- [Frontend Architecture](../../docs/03-frontend-architecture.md)
- [Previous Enhancement: LoanPeriod Unit](./LOANPERIOD_UNIT_ENHANCEMENT.md)
- [Test Plan](../../testing/TEST_PLAN.md)

---

**Prepared by**: Claude Code Assistant
**Date**: March 12, 2026
**Review Status**: Pending stakeholder review
**Next Steps**: Stakeholder approval → Implementation → Testing → Deployment
