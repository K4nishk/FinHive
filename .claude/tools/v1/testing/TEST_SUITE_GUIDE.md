# 📋 LoanTracker - Test Suite Guide

**Version**: 1.0.1
**Last Updated**: March 8, 2026

---

## 📚 Overview

This document provides detailed test cases for all LoanTracker features, organized by functional area. Each test case includes steps, expected results, and actual results tracking.

---

## 1. Data Entry Form Tests

### TC-DE-001: Create Loan with All Required Fields

**Priority**: P0 (Critical)
**Type**: Functional

**Prerequisites**:
- Application running at localhost:8000
- Data Entry tab opened

**Test Steps**:
1. Navigate to Data Entry tab
2. Enter borrower_name: "Test Borrower"
3. Enter amount: "10000"
4. Enter depositor_name: "Test Lender"
5. Select giving_date: Today's date
6. Leave due_date empty
7. Leave borrower_group empty
8. Leave depositor_group empty
9. Click "Add Loan" button

**Expected Result**:
- ✅ Success message displayed
- ✅ Loan appears in View Loans tab
- ✅ due_date defaults to 1970-01-01
- ✅ Status is "active"
- ✅ Amount shows as ₹10,000.00

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

**Defect ID** (if failed): _____

---

### TC-DE-002: Create Loan with All Fields Including Optional

**Priority**: P1
**Type**: Functional

**Test Steps**:
1. Navigate to Data Entry tab
2. Enter all required fields (as TC-DE-001)
3. Enter due_date: 30 days from today
4. Enter borrower_group: "Family"
5. Enter depositor_group: "Bank"
6. Click "Add Loan"

**Expected Result**:
- ✅ Loan created successfully
- ✅ due_date saved correctly
- ✅ Groups display in View Loans table
- ✅ Status calculated correctly

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-DE-003: Validation - Empty Borrower Name

**Priority**: P0
**Type**: Validation

**Test Steps**:
1. Leave borrower_name empty
2. Fill all other required fields
3. Click "Add Loan"

**Expected Result**:
- ❌ Form does not submit
- ❌ Error message: "Borrower name is required" or browser validation
- ❌ No API call made

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-DE-004: Validation - Zero Amount

**Priority**: P0
**Type**: Validation

**Test Steps**:
1. Fill all required fields
2. Enter amount: "0"
3. Click "Add Loan"

**Expected Result**:
- ❌ Form validation error
- ❌ Amount must be greater than 0

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-DE-005: Validation - Negative Amount

**Priority**: P0
**Type**: Validation

**Test Steps**:
1. Fill all required fields
2. Enter amount: "-5000"
3. Click "Add Loan"

**Expected Result**:
- ❌ Form validation error or browser prevents negative input
- ❌ Amount must be positive

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-DE-006: Due Date Before Giving Date

**Priority**: P1
**Type**: Validation

**Test Steps**:
1. Fill all required fields
2. Set giving_date: 2026-03-08
3. Set due_date: 2026-03-01 (before giving_date)
4. Click "Add Loan"

**Expected Result**:
- ❌ Validation error: "Due date must be after giving date"
- ❌ HTTP 422 response from API

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

## 2. View Loans Table Tests

### TC-VL-001: Display All Loans

**Priority**: P0
**Type**: Functional

**Prerequisites**:
- At least 5 loans in the system

**Test Steps**:
1. Navigate to View Loans tab
2. Observe the table

**Expected Result**:
- ✅ All loans displayed in table
- ✅ SNo column shows YYYY/xxx format
- ✅ Amount column shows ₹ symbol
- ✅ Currency badge shows "INR"
- ✅ Status badge color-coded (green/yellow/red)
- ✅ Actions column has status dropdown and delete button

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-VL-002: SNo Format Verification

**Priority**: P1
**Type**: Functional

**Test Steps**:
1. Create 3 loans with giving_date in 2026
2. Create 2 loans with giving_date in 2025
3. Navigate to View Loans tab
4. Check SNo column

**Expected Result**:
- ✅ 2026 loans: 2026/001, 2026/002, 2026/003
- ✅ 2025 loans: 2025/001, 2025/002
- ✅ SNo based on giving_date year, not current year

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-VL-003: Update Loan Status

**Priority**: P0
**Type**: Functional

**Test Steps**:
1. Navigate to View Loans tab
2. Select a loan with status "active"
3. Click status dropdown
4. Select "paid_off"
5. Observe the update

**Expected Result**:
- ✅ API call made (PATCH /api/v1/loans/{id})
- ✅ Success message displayed
- ✅ Status badge updates to "PAID_OFF"
- ✅ Badge color changes

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-VL-004: Delete Loan

**Priority**: P0
**Type**: Functional

**Test Steps**:
1. Navigate to View Loans tab
2. Click "Delete" button on a loan
3. Confirm deletion (if prompted)

**Expected Result**:
- ✅ API call made (DELETE /api/v1/loans/{id})
- ✅ Success message displayed
- ✅ Loan removed from table immediately
- ✅ Table re-renders without page reload

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-VL-005: INR Currency Display

**Priority**: P1
**Type**: Functional

**Test Steps**:
1. Create loan with amount: 100000
2. Navigate to View Loans tab
3. Check amount column

**Expected Result**:
- ✅ Amount displays as: ₹100,000.00
- ✅ Indian number formatting (lakhs comma placement)
- ✅ Two decimal places
- ✅ Rupee symbol (₹) not dollar ($)

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

## 3. Interest Calculator Tests

### TC-IC-001: Calculate Interest for Individual Borrower

**Priority**: P0
**Type**: Functional

**Prerequisites**:
- Create 2 loans for borrower "John Doe" (status: active)

**Test Steps**:
1. Navigate to Interest Calculator tab
2. Select borrower: "John Doe"
3. Select filter type: "By Borrower Name"
4. Enter interest rate: 12
5. Enter commission rate: 10
6. Enter period: 12 months
7. Click "Calculate Interest"

**Expected Result**:
- ✅ Report displays borrower name "John Doe" as header
- ✅ Table shows both loans with:
  - SNo in YYYY/xxx format
  - Amount in ₹
  - Giving Date
  - Depositor name
  - "12 months" in Ext Period column
  - Due Date
  - Interest Amount (correct calculation)
  - Commission (correct calculation)
- ✅ Summary shows: Total Loans, Total Amount, Total Interest, Total Commission
- ✅ All amounts in ₹ with Indian formatting

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-IC-002: Calculate Interest for Borrower Group

**Priority**: P1
**Type**: Functional

**Prerequisites**:
- Create 3 loans with borrower_group = "Family" (status: active)

**Test Steps**:
1. Navigate to Interest Calculator tab
2. Select "Family" from dropdown
3. Select filter type: "By Borrower Group"
4. Enter interest rate: 12
5. Enter commission rate: 10
6. Enter period: 6 months
7. Click "Calculate Interest"

**Expected Result**:
- ✅ Report displays "Family" as header
- ✅ All 3 loans shown in table
- ✅ Each row shows "6 months" in Ext Period
- ✅ Correct calculations for 6-month period
- ✅ Summary totals all 3 loans

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-IC-003: Validation - Commission Rate >= Interest Rate

**Priority**: P1
**Type**: Validation

**Test Steps**:
1. Navigate to Interest Calculator tab
2. Select any borrower
3. Enter interest rate: 12
4. Enter commission rate: 12 (equal to interest)
5. Click "Calculate Interest"

**Expected Result**:
- ❌ Error message: "Commission rate must be less than interest rate!"
- ❌ No report generated

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-IC-004: Interest Calculation Accuracy

**Priority**: P0
**Type**: Business Logic

**Test Data**:
- Loan Amount: ₹10,000
- Interest Rate: 12% per annum
- Commission Rate: 10%
- Period: 12 months

**Test Steps**:
1. Create loan with amount: 10000
2. Calculate interest with rates above
3. Verify calculations

**Expected Result**:
- ✅ Monthly Interest = ₹10,000 × (12% / 12) = ₹100
- ✅ Total Interest (12 months) = ₹100 × 12 = ₹1,200
- ✅ Commission per month = ₹100 × 10% = ₹10
- ✅ Total Commission (12 months) = ₹10 × 12 = ₹120

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-IC-005: Export Interest Calculator CSV

**Priority**: P1
**Type**: Functional

**Test Steps**:
1. Generate an interest report
2. Click "Export Interest Report as CSV" button
3. Check downloaded file

**Expected Result**:
- ✅ CSV file downloads with name: interest_report_[borrower]_[date].csv
- ✅ File contains:
  - Header with borrower name
  - Interest rate, commission rate, period
  - Table with all columns: SNo, Amount, Giving Date, Depositor, Ext Period, Due Date, Interest, Commission
  - Summary section with totals
- ✅ All amounts prefixed with ₹

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-IC-006: Exclude Paid Off Loans

**Priority**: P1
**Type**: Business Logic

**Test Steps**:
1. Create 3 loans for "John Doe"
2. Mark one loan as "paid_off"
3. Navigate to Interest Calculator
4. Calculate for "John Doe"

**Expected Result**:
- ✅ Only 2 active loans shown in report
- ✅ Paid-off loan excluded from calculations
- ✅ Summary totals reflect only active loans

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

## 4. CSV Import Tests

### TC-CSV-001: Import Valid CSV with All Fields

**Priority**: P0
**Type**: Functional

**Test Data**:
Create CSV file:
```csv
borrower_name,amount,depositor_name,giving_date,due_date,borrower_group,depositor_group
Alice Brown,15000,Bank ABC,2026-01-15,2026-12-31,Family,Bank
Bob Smith,25000,Credit Union,2026-02-20,2027-02-20,Business,Credit Union
```

**Test Steps**:
1. Navigate to Import CSV tab
2. Click "Choose File"
3. Select the test CSV
4. Click "Preview CSV"
5. Review preview
6. Click "Import Loans"

**Expected Result**:
- ✅ Preview shows 2 rows
- ✅ All fields correctly parsed
- ✅ Import successful
- ✅ Success message: "2 loans imported successfully"
- ✅ Loans appear in View Loans tab

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-CSV-002: Import CSV with Missing Optional Fields

**Priority**: P1
**Type**: Functional

**Test Data**:
```csv
borrower_name,amount,depositor_name,giving_date,due_date,borrower_group,depositor_group
Charlie Davis,5000,Personal Savings,2026-03-01,,,
```

**Test Steps**:
1. Import CSV with missing due_date and groups
2. Check imported loan

**Expected Result**:
- ✅ Import successful
- ✅ due_date defaults to 1970-01-01
- ✅ borrower_group = null/empty
- ✅ depositor_group = null/empty
- ✅ Status = "active"

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-CSV-003: Reject CSV with Missing Required Fields

**Priority**: P1
**Type**: Validation

**Test Data**:
```csv
borrower_name,amount,depositor_name,giving_date
,10000,Lender X,2026-03-08
John Doe,,Lender Y,2026-03-08
```

**Test Steps**:
1. Import CSV with missing borrower_name (row 1) and amount (row 2)
2. Review preview

**Expected Result**:
- ❌ Validation errors shown
- ❌ Error message lists missing fields
- ❌ Invalid rows highlighted or skipped
- ❌ Option to import only valid rows (if any)

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

## 5. Status Auto-Calculation Tests

### TC-STATUS-001: Default Status (No Due Date)

**Priority**: P0
**Type**: Business Logic

**Test Steps**:
1. Create loan with due_date = 1970-01-01 (empty field)
2. Check loan status

**Expected Result**:
- ✅ Status = "active"
- ✅ Does NOT auto-change to "overdue"

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-STATUS-002: Future Due Date

**Priority**: P0
**Type**: Business Logic

**Test Steps**:
1. Create loan with due_date = 30 days from today
2. Check loan status immediately

**Expected Result**:
- ✅ Status = "active"

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-STATUS-003: Past Due Date (Overdue)

**Priority**: P0
**Type**: Business Logic

**Test Steps**:
1. Manually edit CSV to create loan with due_date = yesterday
2. Restart application
3. Check loan status

**Expected Result**:
- ✅ Status = "overdue"
- ✅ Status badge is red

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

## 6. Cross-Platform Tests

### TC-XP-001: Mac Application Startup

**Priority**: P0
**Type**: Cross-Platform

**Platform**: macOS Sonoma/Sequoia

**Test Steps**:
1. Run `./start-dev.sh`
2. Check terminal output
3. Access localhost:8000

**Expected Result**:
- ✅ Virtual environment activates
- ✅ Dependencies install (if needed)
- ✅ Application starts on port 8000
- ✅ No errors in terminal
- ✅ Browser shows LoanTracker UI

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-XP-002: Windows Application Startup

**Priority**: P0
**Type**: Cross-Platform

**Platform**: Windows 10/11

**Test Steps**:
1. Double-click `start-windows.bat`
2. Check command prompt output
3. Access localhost:8000

**Expected Result**:
- ✅ Virtual environment activates
- ✅ Dependencies install (if needed)
- ✅ Application starts on port 8000
- ✅ No errors in command prompt
- ✅ Browser shows LoanTracker UI

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-XP-003: CSV Encoding (Windows)

**Priority**: P1
**Type**: Cross-Platform

**Platform**: Windows

**Test Steps**:
1. Create CSV with special characters (é, ñ, etc.)
2. Import on Windows
3. Check display

**Expected Result**:
- ✅ Special characters display correctly
- ✅ UTF-8 encoding preserved
- ✅ No garbled text

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

## 7. API Endpoint Tests

### TC-API-001: GET /api/v1/loans/

**Priority**: P0
**Type**: API

**Test Steps**:
```bash
curl http://localhost:8000/api/v1/loans/
```

**Expected Result**:
- ✅ HTTP 200 OK
- ✅ Returns array of loan objects
- ✅ Each loan has all fields
- ✅ No NaN values in JSON

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-API-002: POST /api/v1/loans/ (Valid Data)

**Priority**: P0
**Type**: API

**Test Steps**:
```bash
curl -X POST http://localhost:8000/api/v1/loans/ \
  -H "Content-Type: application/json" \
  -d '{
    "borrower_name": "API Test",
    "amount": 5000,
    "currency": "INR",
    "depositor_name": "API Lender",
    "giving_date": "2026-03-08",
    "due_date": "1970-01-01"
  }'
```

**Expected Result**:
- ✅ HTTP 201 Created
- ✅ Returns loan object with ID
- ✅ status = "active"

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

### TC-API-003: POST /api/v1/loans/ (Invalid Data - 422 Error)

**Priority**: P0
**Type**: API

**Test Steps**:
```bash
curl -X POST http://localhost:8000/api/v1/loans/ \
  -H "Content-Type: application/json" \
  -d '{
    "borrower_name": "Test",
    "amount": 5000,
    "currency": "INR",
    "depositor_name": "Lender",
    "giving_date": "2026-03-08",
    "due_date": "2026-01-01"
  }'
```
(due_date before giving_date)

**Expected Result**:
- ❌ HTTP 422 Unprocessable Entity
- ❌ Error message: "Due date must be after giving date"

**Actual Result**: _____________________

**Status**: PASS / FAIL / BLOCKED

---

## 8. Test Coverage Matrix

| Feature Area | Total Tests | Critical (P0) | High (P1) | Medium (P2) |
|--------------|-------------|---------------|-----------|-------------|
| Data Entry | 6 | 4 | 2 | 0 |
| View Loans | 5 | 2 | 3 | 0 |
| Interest Calculator | 6 | 2 | 4 | 0 |
| CSV Import | 3 | 1 | 2 | 0 |
| Status Calculation | 3 | 3 | 0 | 0 |
| Cross-Platform | 3 | 2 | 1 | 0 |
| API Endpoints | 3 | 3 | 0 | 0 |
| **TOTAL** | **29** | **17** | **12** | **0** |

---

## 9. Test Execution Log Template

```
Date: __________
Tester: __________
Version: 1.0.1
Platform: Mac / Windows

Test Results:
- Total Executed: ___
- Passed: ___
- Failed: ___
- Blocked: ___
- Pass Rate: ___%

Critical Failures: [List TC IDs]

Notes:
[Any observations or issues]
```

---

**End of Test Suite Guide**
