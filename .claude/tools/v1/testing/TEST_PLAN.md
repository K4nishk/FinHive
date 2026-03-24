# 🧪 LoanTracker - Test Plan

**Version**: 1.0.1
**Last Updated**: March 8, 2026
**Status**: Active

---

## 📋 Document Overview

This document outlines the comprehensive testing strategy for LoanTracker, including test scope, objectives, environments, types, and success criteria.

---

## 1. Test Strategy Overview

### 1.1 Objectives

**Primary Goals**:
- Ensure all core functionality works correctly
- Validate business logic and calculations
- Verify data integrity and security
- Confirm cross-platform compatibility
- Identify and fix critical bugs before release

**Success Criteria**:
- Zero critical (P0) bugs in production
- <5 minor (P2) bugs per release
- 100% of core features tested
- Manual E2E tests pass on both Mac and Windows

---

### 1.2 Test Scope

**In Scope**:
- ✅ Data Entry form (all fields, validation)
- ✅ CRUD operations (Create, Read, Update, Delete loans)
- ✅ Interest Calculator (individual and group)
- ✅ CSV Import/Export
- ✅ Reports and statistics
- ✅ Status calculation (active, overdue, paid_off)
- ✅ Currency display (INR formatting)
- ✅ Serial Number generation (YYYY/xxx)
- ✅ API endpoints (all routes)
- ✅ Frontend-backend integration
- ✅ Cross-platform compatibility (Mac, Windows)

**Out of Scope** (Future versions):
- ❌ Mobile app testing
- ❌ Performance/load testing (>10,000 records)
- ❌ Security penetration testing
- ❌ Accessibility testing (WCAG compliance)
- ❌ Multi-user/concurrent access
- ❌ Database migrations

---

## 2. Test Environments

### 2.1 Development Environment

**Platform**: Mac (Primary), Windows (Secondary)
**Python Version**: 3.8+
**Dependencies**: As per requirements.txt

**Setup**:
```bash
# Mac/Linux
./start-dev.sh

# Windows
start-windows.bat
```

**Test Data**:
- Sample CSV file: `backend/sample_loans.csv`
- 10-15 test loan records
- Various borrower/depositor combinations

---

### 2.2 Test Environment Checklist

**Pre-Test Setup**:
- [ ] Clean CSV file (backup existing data)
- [ ] Start application successfully
- [ ] Verify localhost:8000 accessible
- [ ] Clear browser cache
- [ ] Check Python version (3.8+)
- [ ] Verify all dependencies installed

**Post-Test Cleanup**:
- [ ] Restore original data (if needed)
- [ ] Stop application
- [ ] Review logs for errors
- [ ] Document any issues found

---

## 3. Test Types

### 3.1 Functional Testing

**What**: Verify all features work as designed

**Test Areas**:
1. **Data Entry**
   - Create loan with all required fields
   - Create loan with optional fields
   - Validation error handling
   - Date field validation
   - Amount validation (positive numbers only)

2. **View Loans**
   - Display all loans in table
   - SNo format (YYYY/xxx)
   - Currency display (₹)
   - Status badges
   - Update status dropdown
   - Delete button

3. **Interest Calculator**
   - Select borrower by name
   - Select borrower by group
   - Calculate interest (valid rates)
   - Calculate commission (valid rates)
   - Validation (commission < interest)
   - Report format (detailed breakdown)
   - CSV export

4. **CSV Import**
   - Import valid CSV
   - Handle missing optional fields
   - Reject invalid rows
   - Show preview
   - Error reporting

5. **Reports**
   - Statistics dashboard
   - Total loans, total amount
   - Active/overdue/paid_off counts
   - Proper INR formatting

---

### 3.2 Integration Testing

**What**: Verify frontend-backend communication

**Test Scenarios**:
1. **Form Submission**
   - Fill Data Entry form
   - Click "Add Loan"
   - Verify API call (POST /api/v1/loans/)
   - Verify 201 Created response
   - Verify loan appears in View Loans tab

2. **Status Update**
   - Change loan status in dropdown
   - Verify API call (PATCH /api/v1/loans/{id})
   - Verify status updates in table
   - Verify success message

3. **Delete Operation**
   - Click Delete button
   - Verify confirmation (if any)
   - Verify API call (DELETE /api/v1/loans/{id})
   - Verify loan removed from table

4. **Interest Calculator Flow**
   - Select borrower
   - Enter rates
   - Click Calculate
   - Verify calculation logic
   - Verify report display
   - Export CSV

---

### 3.3 Business Logic Testing

**What**: Verify calculations and business rules

**Test Cases**:

**Interest Calculation**:
```
Test Case 1: Single Loan Monthly Interest
Input: Amount = ₹10,000, Interest Rate = 12%, Period = 1 month
Expected: Monthly Interest = ₹100

Test Case 2: Commission Calculation
Input: Interest = ₹100, Commission Rate = 10%
Expected: Commission = ₹10

Test Case 3: Multi-Month Calculation
Input: Amount = ₹10,000, Interest Rate = 12%, Period = 12 months, Commission Rate = 10%
Expected: Total Interest = ₹1,200, Total Commission = ₹120
```

**Status Auto-Calculation**:
```
Test Case 1: No Due Date
Input: due_date = 1970-01-01
Expected: status = "active"

Test Case 2: Future Due Date
Input: due_date = tomorrow
Expected: status = "active"

Test Case 3: Past Due Date
Input: due_date = yesterday
Expected: status = "overdue"
```

**SNo Generation**:
```
Test Case 1: First loan in 2026
Input: index = 0, giving_date = 2026-03-08
Expected: SNo = "2026/001"

Test Case 2: 150th loan in 2025
Input: index = 149, giving_date = 2025-12-31
Expected: SNo = "2025/150"
```

---

### 3.4 Validation Testing

**What**: Verify input validation and error handling

**Test Cases**:

**Required Field Validation**:
- Submit form with empty borrower_name → Error
- Submit form with empty amount → Error
- Submit form with zero/negative amount → Error
- Submit form with empty depositor_name → Error
- Submit form with empty giving_date → Error

**Date Validation**:
- giving_date in future → Error (if validation exists)
- due_date before giving_date (except 1970-01-01) → Error
- due_date = 1970-01-01 → Success (no due date)

**Interest Calculator Validation**:
- Commission rate >= Interest rate → Error
- Interest rate = 0 → Error
- Negative rates → Error
- Period count = 0 → Error

---

### 3.5 Cross-Platform Testing

**What**: Verify application works on both Mac and Windows

**Test Matrix**:

| Feature | Mac (Sonoma/Sequoia) | Windows 10/11 | Status |
|---------|----------------------|---------------|--------|
| Application starts | ✅ | ✅ | |
| Create loan | ✅ | ✅ | |
| View loans table | ✅ | ✅ | |
| Update status | ✅ | ✅ | |
| Delete loan | ✅ | ✅ | |
| Interest Calculator | ✅ | ✅ | |
| CSV Import | ✅ | ✅ | |
| CSV Export | ✅ | ✅ | |
| INR formatting | ✅ | ✅ | |
| SNo generation | ✅ | ✅ | |

**Platform-Specific Issues**:
- File path differences (/ vs \)
- Date format differences
- Number formatting (locale)
- CSV encoding (UTF-8)

---

## 4. Test Execution

### 4.1 Test Cycle

**Frequency**: Before each release

**Phases**:
1. **Smoke Test** (15 min): Quick check that app starts and core features work
2. **Functional Test** (1 hour): All features tested systematically
3. **Integration Test** (30 min): API calls and data flow
4. **Regression Test** (30 min): Re-test previously fixed bugs
5. **Cross-Platform Test** (1 hour): Test on both Mac and Windows

**Total Test Time**: ~3-4 hours per release

---

### 4.2 Test Execution Process

**Step 1: Pre-Test Setup**
- Back up `loan_records.csv`
- Clean test environment
- Clear browser cache
- Start application
- Verify access at localhost:8000

**Step 2: Execute Test Cases**
- Follow test suite guide
- Document results in test log
- Screenshot any failures
- Note error messages

**Step 3: Report Defects**
- Create issue for each bug found
- Classify severity (P0/P1/P2)
- Include reproduction steps
- Attach screenshots/logs

**Step 4: Regression Testing**
- After fixes, re-test failed cases
- Verify fix doesn't break other features
- Update test log

**Step 5: Sign-Off**
- Review test results
- Ensure exit criteria met
- Approve for release or reject

---

## 5. Entry and Exit Criteria

### 5.1 Entry Criteria

**Required Before Testing**:
- [ ] Code complete for all planned features
- [ ] Application builds successfully
- [ ] No known critical (P0) bugs
- [ ] Test environment set up
- [ ] Test data prepared
- [ ] Test cases reviewed and approved

---

### 5.2 Exit Criteria

**Required Before Release**:
- [ ] All test cases executed
- [ ] Zero critical (P0) bugs
- [ ] <5 high priority (P1) bugs
- [ ] All P1 bugs have workarounds documented
- [ ] Cross-platform testing complete
- [ ] Test report generated
- [ ] Sign-off from business owner

---

## 6. Defect Classification

### P0 - Critical (Blocking)
**Definition**: Feature completely broken, no workaround
**Examples**:
- Application crashes on startup
- Cannot create loans (422 error)
- Data loss or corruption
- Security vulnerability

**Action**: Fix immediately, block release

---

### P1 - High Priority
**Definition**: Major feature broken, workaround exists
**Examples**:
- Interest Calculator shows wrong values
- CSV import fails for valid files
- Status not auto-calculating
- SNo format incorrect

**Action**: Fix before release or document workaround

---

### P2 - Medium Priority
**Definition**: Minor issue, doesn't affect core functionality
**Examples**:
- UI alignment issues
- Misleading error messages
- Performance slowdown (non-critical)
- Missing tooltips

**Action**: Fix in next release

---

### P3 - Low Priority
**Definition**: Cosmetic or nice-to-have
**Examples**:
- Color scheme preferences
- Font size requests
- Feature enhancement ideas

**Action**: Backlog for future consideration

---

## 7. Test Reporting

### 7.1 Test Log Format

**For Each Test Case**:
```
Test Case ID: TC-001
Feature: Data Entry
Test: Create loan with all required fields
Status: PASS / FAIL / BLOCKED
Date: 2026-03-08
Tester: Name
Notes: [Any observations]
Defect ID: [If failed]
```

### 7.2 Test Summary Report

**Template**:
```
LoanTracker Test Summary Report
Version: 1.0.1
Date: 2026-03-08

Test Execution:
- Total Test Cases: 50
- Passed: 48
- Failed: 2
- Blocked: 0
- Pass Rate: 96%

Defects Found:
- P0 (Critical): 0
- P1 (High): 1
- P2 (Medium): 1
- P3 (Low): 0

Recommendation: PASS / FAIL / CONDITIONAL PASS

Sign-Off:
Tester: _____________ Date: _______
QA Lead: ____________ Date: _______
```

---

## 8. Testing Tools

### 8.1 Manual Testing
- **Browser**: Chrome, Safari, Edge
- **Tools**: Developer Console (F12)
- **Screen Recording**: For bug reproduction

### 8.2 API Testing
- **curl**: Command-line API testing
- **Browser DevTools**: Network tab for API calls
- **Postman** (optional): API endpoint testing

### 8.3 Future Automation (Post-MVP1)
- **pytest**: Python unit tests
- **Selenium**: Browser automation
- **GitHub Actions**: CI/CD pipeline

---

## 9. Risk Assessment

### High Risk Areas
1. **Interest Calculator Logic**: Complex calculations, easy to introduce errors
2. **CSV Import**: Many edge cases (missing fields, encoding, formats)
3. **Date Handling**: Timezone issues, 1970-01-01 special case
4. **Cross-Platform**: Windows vs Mac path and encoding differences

### Mitigation Strategy
- Extra test coverage for high-risk areas
- Peer review of calculation logic
- Test with real-world CSV files
- Platform-specific testing on each release

---

## 10. Test Schedule

### MVP 1.0.1 Release
```
Week 1:
- Day 1-2: Create test cases
- Day 3-4: Execute functional tests
- Day 5: Cross-platform testing

Week 2:
- Day 1-2: Bug fixes
- Day 3: Regression testing
- Day 4: Final sign-off
- Day 5: Release
```

---

## 11. Approval

**Test Plan Approved By**:

**QA Lead**: _______________ Date: ___________
**Tech Lead**: _______________ Date: ___________
**Business Owner**: _______________ Date: ___________

---

**This is a living document. Update as testing processes evolve.**
