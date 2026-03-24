# 🧪 LoanTracker - How to Run Tests

**Version**: 1.0.1
**Last Updated**: March 8, 2026

---

## 📋 Overview

This guide explains how to run different types of tests for LoanTracker, from quick smoke tests to comprehensive test suites.

---

## 1. Quick Smoke Test (5 minutes)

**Purpose**: Verify the application works after installation or updates

### Steps

1. **Start the Application**:
   ```bash
   # Mac/Linux
   ./start-dev.sh

   # Windows
   start-windows.bat
   ```

2. **Verify Startup**:
   - ✅ Application starts without errors
   - ✅ Terminal/console shows "Uvicorn running on http://127.0.0.1:8000"
   - ✅ Browser opens automatically (or visit localhost:8000)

3. **Test Core Features**:
   - ✅ **Data Entry**: Create one loan with all required fields
   - ✅ **View Loans**: Verify loan appears in table
   - ✅ **Interest Calculator**: Run calculation for one borrower
   - ✅ **Status**: Verify loan status is "active"

4. **Smoke Test Pass Criteria**:
   - All 4 core features work
   - No errors in browser console (F12)
   - No errors in terminal/console

**If smoke test fails, do NOT proceed with deployment!**

---

## 2. Manual E2E Test (30 minutes)

**Purpose**: Test complete workflows end-to-end

### 2.1 Workflow 1: Create and Manage Loans

1. **Create Loan with All Fields**:
   - Data Entry tab
   - Fill all fields including optional (borrower_group, depositor_group, due_date)
   - Click "Add Loan"
   - ✅ Verify success message
   - ✅ Verify loan in View Loans tab

2. **Create Loan with Minimal Fields**:
   - Fill only required fields
   - Leave due_date empty
   - ✅ Verify defaults to 1970-01-01
   - ✅ Verify status is "active"

3. **Update Loan Status**:
   - Go to View Loans tab
   - Change status to "paid_off"
   - ✅ Verify update immediately
   - ✅ Verify success message

4. **Delete Loan**:
   - Click Delete button
   - ✅ Verify loan removed
   - ✅ Verify success message

**Pass Criteria**: All operations complete successfully

---

### 2.2 Workflow 2: Interest Calculator

1. **Create Test Data**:
   - Create 3 loans for borrower "John Doe"
   - Amounts: ₹10,000, ₹5,000, ₹8,000
   - All status: "active"

2. **Calculate Interest**:
   - Go to Interest Calculator tab
   - Select "John Doe"
   - Filter: "By Borrower Name"
   - Interest Rate: 12%
   - Commission Rate: 10%
   - Period: 12 months
   - Click "Calculate Interest"

3. **Verify Report Format**:
   - ✅ Borrower name "John Doe" as header
   - ✅ Table shows all 3 loans
   - ✅ Columns: SNo, Amount, Giving Date, Depositor, Ext Period, Due Date, Interest, Commission
   - ✅ SNo in YYYY/xxx format
   - ✅ All amounts show ₹ symbol
   - ✅ Extension period shows "12 months"
   - ✅ Summary section with totals

4. **Verify Calculations** (for ₹10,000 loan):
   - Monthly Interest = ₹10,000 × (12% / 12) = ₹100
   - Total Interest (12 months) = ₹1,200
   - Commission per month = ₹100 × 10% = ₹10
   - Total Commission (12 months) = ₹120
   - ✅ Verify numbers match

5. **Export CSV**:
   - Click "Export Interest Report as CSV"
   - ✅ File downloads
   - ✅ Open file and verify content

**Pass Criteria**: Report format correct, calculations accurate, CSV export works

---

### 2.3 Workflow 3: CSV Import/Export

1. **Export Current Data**:
   - Go to View Loans tab
   - Note number of loans
   - (CSV export functionality - if implemented)

2. **Prepare Import CSV**:
   Create `test_import.csv`:
   ```csv
   borrower_name,amount,depositor_name,giving_date,due_date,borrower_group,depositor_group
   Alice Brown,15000,Bank ABC,2026-01-15,2026-12-31,Family,Bank
   Bob Smith,25000,Credit Union,2026-02-20,2027-02-20,Business,Credit Union
   Charlie Davis,5000,Personal Savings,2026-03-01,,,
   ```

3. **Import CSV**:
   - Go to Import CSV tab
   - Choose file: test_import.csv
   - Click "Preview CSV"
   - ✅ Verify 3 rows shown correctly
   - Click "Import Loans"
   - ✅ Verify success message

4. **Verify Imported Data**:
   - Go to View Loans tab
   - ✅ Verify 3 new loans appear
   - ✅ Verify borrower_group = "Family" for Alice
   - ✅ Verify due_date = 1970-01-01 for Charlie (empty in CSV)
   - ✅ Verify all amounts in ₹

**Pass Criteria**: CSV import successful, all data correct including defaults

---

## 3. Cross-Platform Testing (1 hour)

**Purpose**: Verify application works on both Mac and Windows

### 3.1 Test Matrix

Run smoke test and E2E workflows on BOTH platforms:

| Test | Mac | Windows | Notes |
|------|-----|---------|-------|
| Smoke Test | ☐ | ☐ | |
| Create Loan | ☐ | ☐ | |
| View Loans | ☐ | ☐ | |
| Update Status | ☐ | ☐ | |
| Delete Loan | ☐ | ☐ | |
| Interest Calculator | ☐ | ☐ | |
| CSV Import | ☐ | ☐ | |
| CSV Export | ☐ | ☐ | |
| INR Formatting | ☐ | ☐ | Verify ₹ symbol displays |
| SNo Format | ☐ | ☐ | Verify YYYY/xxx format |

### 3.2 Platform-Specific Checks

**On Windows**:
- ✅ `start-windows.bat` works without errors
- ✅ CSV files open correctly in Excel
- ✅ UTF-8 encoding preserved (test with special characters)
- ✅ Date format consistent

**On Mac**:
- ✅ `./start-dev.sh` executable permission set
- ✅ Application runs on Safari, Chrome
- ✅ Numbers formatted correctly

**Pass Criteria**: All tests pass on both platforms

---

## 4. API Testing with curl (15 minutes)

**Purpose**: Test backend API endpoints directly

### 4.1 Setup

Ensure application is running:
```bash
# Should see: "Uvicorn running on http://127.0.0.1:8000"
```

### 4.2 Test Cases

**Test 1: Get All Loans**
```bash
curl http://localhost:8000/api/v1/loans/
```
**Expected**: HTTP 200, JSON array of loans

---

**Test 2: Create Loan (Valid)**
```bash
curl -X POST http://localhost:8000/api/v1/loans/ \
  -H "Content-Type: application/json" \
  -d '{
    "borrower_name": "API Test User",
    "amount": 5000,
    "currency": "INR",
    "depositor_name": "API Test Lender",
    "giving_date": "2026-03-08",
    "due_date": "1970-01-01"
  }'
```
**Expected**: HTTP 201, loan object with ID and status="active"

---

**Test 3: Create Loan (Invalid - Past Due Date)**
```bash
curl -X POST http://localhost:8000/api/v1/loans/ \
  -H "Content-Type: application/json" \
  -d '{
    "borrower_name": "Test",
    "amount": 5000,
    "currency": "INR",
    "depositor_name": "Lender",
    "giving_date": "2026-03-08",
    "due_date": "2026-03-01"
  }'
```
**Expected**: HTTP 422, error message about due_date

---

**Test 4: Get Statistics**
```bash
curl http://localhost:8000/api/v1/statistics/
```
**Expected**: HTTP 200, JSON with total_loans, total_amount, active_count, etc.

---

**Test 5: Health Check**
```bash
curl http://localhost:8000/api/v1/health/
```
**Expected**: HTTP 200, {"status": "healthy"}

---

**Test 6: Update Loan Status**
```bash
# Replace {loan_id} with actual loan ID from Test 2
curl -X PATCH http://localhost:8000/api/v1/loans/{loan_id} \
  -H "Content-Type: application/json" \
  -d '{"status": "paid_off"}'
```
**Expected**: HTTP 200, loan object with updated status

---

**Test 7: Delete Loan**
```bash
# Replace {loan_id} with actual loan ID
curl -X DELETE http://localhost:8000/api/v1/loans/{loan_id}
```
**Expected**: HTTP 200, success message

---

### 4.3 API Test Checklist

- ☐ All endpoints return expected status codes
- ☐ Error handling works (422 for validation errors)
- ☐ CORS headers present (if needed)
- ☐ Response times < 500ms for simple queries
- ☐ No SQL injection vulnerabilities (test with `' OR '1'='1`)

**Pass Criteria**: All API tests pass, no errors in terminal

---

## 5. Regression Testing (30 minutes)

**Purpose**: Ensure bug fixes didn't break existing features

### 5.1 Known Fixed Bugs

**Bug 1: 422 Error on Loan Creation (Fixed in v1.0.1)**
- **Test**: Create loan with empty due_date
- **Expected**: Defaults to 1970-01-01, status="active", no 422 error
- **Status**: ☐ PASS / ☐ FAIL

**Bug 2: Status Calculation for 1970-01-01 (Fixed in v1.0.1)**
- **Test**: Create loan with due_date=1970-01-01
- **Expected**: Status="active", NOT "overdue"
- **Status**: ☐ PASS / ☐ FAIL

**Bug 3: NaN in Borrower/Depositor Groups (Fixed in v1.0.1)**
- **Test**: Create loan with empty groups, fetch via API
- **Expected**: Groups are null, NOT NaN
- **Status**: ☐ PASS / ☐ FAIL

### 5.2 Regression Test Checklist

- ☐ All previously fixed bugs still fixed
- ☐ No new bugs introduced
- ☐ Features working as before

**Pass Criteria**: All regression tests pass

---

## 6. Performance Testing (Optional)

**Purpose**: Ensure application performs well with realistic data

### 6.1 Load Test

1. **Import Large CSV** (100-500 loans)
2. **Verify Performance**:
   - ☐ View Loans tab loads < 2 seconds
   - ☐ Interest Calculator completes < 3 seconds
   - ☐ CSV export completes < 5 seconds
   - ☐ No browser freezing

### 6.2 Browser Console Check

1. Open Developer Tools (F12)
2. Go to Console tab
3. Use the application
4. **Verify**:
   - ☐ No JavaScript errors
   - ☐ No 404 errors for resources
   - ☐ No CORS errors

**Pass Criteria**: No performance issues, no console errors

---

## 7. Test Reporting

### 7.1 Create Test Report

After running tests, create a report:

```
LoanTracker Test Execution Report
==================================
Date: [YYYY-MM-DD]
Version: 1.0.1
Tester: [Your Name]
Platform: Mac / Windows / Both

Test Results:
-------------
Smoke Test: PASS / FAIL
E2E Workflow 1: PASS / FAIL
E2E Workflow 2: PASS / FAIL
E2E Workflow 3: PASS / FAIL
Cross-Platform: PASS / FAIL
API Testing: PASS / FAIL
Regression: PASS / FAIL

Summary:
--------
Total Tests: __
Passed: __
Failed: __
Pass Rate: __%

Critical Issues Found: [None / List]

Recommendation: APPROVE FOR RELEASE / REJECT

Notes:
------
[Any observations, issues, or comments]

Sign-Off:
---------
Tester: _____________ Date: _______
```

### 7.2 Save Report

Save as: `testing/test_report_YYYY-MM-DD.md`

---

## 8. Troubleshooting Tests

### Test Fails: Application Won't Start

**Check**:
1. Python version: `python3 --version` (should be 3.8+)
2. Port availability: `lsof -ti:8000` (Mac) or `netstat -ano | findstr :8000` (Windows)
3. Dependencies: Run `pip install -r backend/requirements.txt`

**Fix**:
- Kill process on port 8000
- Reinstall dependencies
- Check logs: `logs/loantracker.log`

---

### Test Fails: 422 Error on Loan Creation

**Check**:
1. Browser cache cleared?
2. Hard refresh: Ctrl+F5 (Cmd+Shift+R on Mac)
3. API endpoint directly with curl

**Fix**:
- Clear browser cache
- Restart application
- Check backend logs

---

### Test Fails: Interest Calculator Wrong Results

**Debug**:
1. Verify input values
2. Manual calculation:
   - Monthly Interest = Amount × (Rate / 12)
   - Commission = Monthly Interest × Commission Rate × Period
3. Check browser console for errors

**Fix**:
- Verify logic in `backend/static/app.js` - `calculateCommission()` function
- Test with simple round numbers first

---

### Test Fails: CSV Import

**Check**:
1. CSV format (UTF-8, comma-delimited)
2. Required columns present
3. Date format (YYYY-MM-DD)

**Fix**:
- Validate CSV structure
- Check for special characters
- Try sample_loans.csv first

---

## 9. Automated Unit Tests with pytest ✅

**Available in MVP1**:

### Running Unit Tests

**Basic test run**:
```bash
# From project root
cd backend
pytest tests/

# Or run specific test files
pytest tests/unit/test_loans.py
pytest tests/unit/test_status_calculation.py
pytest tests/unit/test_currency.py
pytest tests/unit/test_interest_calculator.py
```

**Run with verbose output**:
```bash
pytest tests/ -v

# See test names and results clearly
pytest tests/ -v --tb=short
```

**Run specific test class**:
```bash
pytest tests/unit/test_status_calculation.py::TestStatusCalculation
```

**Run specific test**:
```bash
pytest tests/unit/test_status_calculation.py::TestStatusCalculation::test_no_due_date_is_active
```

---

### Running Integration Tests

**Test all API endpoints**:
```bash
pytest tests/integration/

# Specific API test file
pytest tests/integration/test_api.py
pytest tests/integration/test_api_v101.py
```

**Test specific endpoint**:
```bash
pytest tests/integration/test_api_v101.py::TestAPIWithNoDueDate::test_create_loan_without_due_date_no_422_error
```

---

### Test Coverage

**Run with coverage report**:
```bash
# Install pytest-cov if not already installed
pip install pytest-cov

# Run tests with coverage
pytest tests/ --cov=app --cov-report=html

# Open coverage report
open htmlcov/index.html  # Mac
start htmlcov/index.html  # Windows
```

**Coverage by module**:
```bash
pytest tests/ --cov=app --cov-report=term-missing
```

---

### Test Categories

**Unit Tests** (`tests/unit/`):
- `test_loans.py` - Basic CRUD operations
- `test_status_calculation.py` - Status auto-calculation logic
- `test_currency.py` - INR currency handling
- `test_interest_calculator.py` - Interest/commission calculations, SNo generation

**Integration Tests** (`tests/integration/`):
- `test_api.py` - Basic API endpoints
- `test_api_v101.py` - v1.0.1 features (422 fix, currency, status)

---

### Quick Test Commands

**Smoke test (run fastest tests)**:
```bash
pytest tests/unit/test_loans.py::TestLoanCreation -v
```

**Full test suite**:
```bash
pytest tests/ -v
```

**Only failed tests from last run**:
```bash
pytest --lf
```

**Stop on first failure**:
```bash
pytest tests/ -x
```

**Run tests in parallel** (faster):
```bash
# Install pytest-xdist
pip install pytest-xdist

# Run in parallel
pytest tests/ -n auto
```

---

### Continuous Integration (Future)

**Planned CI/CD Pipeline**:
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
      - name: Run tests
        run: |
          cd backend
          pytest tests/ --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

### Test Results Interpretation

**Passing test output**:
```
tests/unit/test_loans.py::TestLoanCreation::test_create_loan_with_all_fields PASSED
tests/unit/test_status_calculation.py::TestStatusCalculation::test_no_due_date_is_active PASSED
```

**Failing test output**:
```
tests/unit/test_loans.py::TestLoanCreation::test_create_loan_with_all_fields FAILED

AssertionError: assert 'overdue' == 'active'
```

**Test summary**:
```
======================== 45 passed in 2.34s ========================
```

---

### Troubleshooting Tests

**Import errors**:
```bash
# Make sure you're in backend directory
cd backend

# Make sure dependencies installed
pip install -r requirements.txt

# Run tests
pytest tests/
```

**Test database conflicts**:
```bash
# Clean test data directory
rm -rf tests/test_data/

# Run tests (will recreate)
pytest tests/
```

**Port already in use**:
```bash
# Kill process on port 8000
lsof -ti:8000 | xargs kill -9  # Mac
```

---

### Test Checklist

Before approving release, ensure:

- ☐ All unit tests pass: `pytest tests/unit/ -v`
- ☐ All integration tests pass: `pytest tests/integration/ -v`
- ☐ Coverage > 70%: `pytest tests/ --cov=app`
- ☐ No import errors
- ☐ No database conflicts
- ☐ Tests run in < 30 seconds

---

### Frontend Tests (Future)

```bash
# Planned for future versions
npm test
npm run test:e2e
```

---

## 10. Quick Reference Commands

**Start Application**:
```bash
./start-dev.sh          # Mac/Linux
start-windows.bat       # Windows
```

**Stop Application**:
- Press Ctrl+C in terminal

**Kill Process on Port 8000**:
```bash
lsof -ti:8000 | xargs kill -9        # Mac/Linux
FOR /F "tokens=5" %P IN ('netstat -ano ^| findstr :8000') DO TaskKill /PID %P /F  # Windows
```

**Check Logs**:
```bash
tail -f logs/loantracker.log         # Mac/Linux
type logs\loantracker.log            # Windows
```

**Test API**:
```bash
curl http://localhost:8000/api/v1/health/
curl http://localhost:8000/api/v1/loans/
```

---

## 11. Test Checklist Summary

Before approving a release, ensure:

- ☐ Smoke test passes
- ☐ All E2E workflows pass
- ☐ Cross-platform testing complete (Mac + Windows)
- ☐ API tests pass
- ☐ Regression tests pass
- ☐ No critical (P0) bugs
- ☐ Test report created and reviewed
- ☐ Sign-off from QA lead

---

**Happy Testing!** 🧪
