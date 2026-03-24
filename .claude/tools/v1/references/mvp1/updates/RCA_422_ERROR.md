# 🔍 Root Cause Analysis - 422 Unprocessable Content Error

**Date**: 2026-03-08
**Severity**: High (Blocking user data entry)
**Status**: Identified - Fix in progress

---

## 📋 Issue Summary

**Error**: `POST /api/v1/loans/ HTTP/1.1" 422 Unprocessable Content`
**Impact**: Users unable to create new loan entries via Data Entry tab
**Environment**: Windows user demo, Mac validation worked

---

## 🔬 Root Cause Analysis

### Primary Cause: Schema Mismatch

**Problem**: Backend schema requires `currency` field, but frontend form doesn't send it in all scenarios.

#### Evidence:
1. **Backend Schema** (`backend/app/schemas/loan.py`):
   ```python
   class LoanBase(BaseModel):
       currency: Currency = Field(default=Currency.INR, description="Currency (INR or CAD)")
   ```
   - Currency field was added with default value INR
   - **However**, Pydantic validation requires field to be present in request

2. **Frontend Form** (`backend/static/index.html`):
   ```html
   <select id="currency" required>
       <option value="INR" selected>INR (₹)</option>
       <option value="CAD">CAD ($)</option>
   </select>
   ```
   - Field exists in updated version
   - May not exist in older cached version

3. **Frontend JavaScript** (`backend/static/app.js`):
   ```javascript
   const formData = {
       // ...
       currency: document.getElementById('currency').value,
   };
   ```
   - Expects `currency` element to exist
   - If element missing → `document.getElementById('currency')` returns `null`
   - `null.value` throws error OR sends `currency: null`

### Secondary Causes:

#### 1. Browser Caching
- **Scenario**: User's browser cached old HTML without currency field
- **Result**: Form doesn't have `currency` dropdown
- **Impact**: JavaScript tries to read non-existent element

#### 2. Pydantic Validation Strictness
- **Issue**: Even with `default=Currency.INR`, Pydantic requires explicit value in request
- **Behavior**: If `currency: null` or `currency: undefined` sent, validation fails
- **Fix Needed**: Make field truly optional or handle null values

#### 3. Package Distribution Timing
- **Windows Package**: Created before all currency changes finalized
- **Mac Validation**: Used live development code with latest changes
- **Mismatch**: Windows user had partial currency implementation

---

## 🧪 Reproduction Steps

### Scenario 1: Browser Cache Issue
1. User opens app with old HTML cached
2. Fills Data Entry form (no currency dropdown visible)
3. Clicks "Create Loan"
4. JavaScript tries: `document.getElementById('currency').value`
5. Returns `null` because element doesn't exist
6. Sends request with `currency: null`
7. Backend validation fails → 422 error

### Scenario 2: Null Value Issue
1. Currency field exists but has null/empty value
2. Request sent as `{..., "currency": null}`
3. Pydantic validator expects valid Currency enum
4. Validation fails → 422 error

---

## 📊 Error Flow Diagram

```
User Fills Form
    ↓
Click "Create Loan"
    ↓
JavaScript: document.getElementById('currency')
    ↓
   [Element exists?]
    ↓              ↓
   YES            NO
    ↓              ↓
 .value         null
    ↓              ↓
"INR"/"CAD"    null.value → ERROR or null
    ↓              ↓
Backend       Backend
Validation    Validation
    ↓              ↓
   ✅            ❌ 422
```

---

## 🔧 Immediate Fixes Required

### Fix 1: Remove Currency Field (User Requirement)
**User Feedback**: "The user didn't want the option to change currency in the Data Entry tab"

**Solution**:
- Remove currency dropdown from HTML form
- Default all entries to INR in backend
- Update JavaScript to not read currency field

**Files to modify**:
- `backend/static/index.html` - Remove currency dropdown
- `backend/static/app.js` - Set `currency: "INR"` hardcoded
- `backend/app/schemas/loan.py` - Keep currency field but ensure default works

### Fix 2: Make Currency Field Optional in API
**Change**: Allow API to accept requests without currency field

```python
# Before (PROBLEMATIC):
currency: Currency = Field(default=Currency.INR)

# After (BETTER):
currency: Optional[Currency] = Field(default=Currency.INR)

# Or in validator:
@field_validator('currency', mode='before')
@classmethod
def set_default_currency(cls, v):
    return v if v is not None else Currency.INR
```

### Fix 3: Clear Browser Cache Instructions
**Documentation**: Add to troubleshooting guide

```
Issue: 422 Error on form submission
Solution: Clear browser cache (Ctrl+Shift+Delete)
Or: Hard refresh (Ctrl+F5)
```

---

## 🧪 Testing Plan

### Test Case 1: Fresh Install
1. Extract Windows package
2. Start application
3. Create loan without currency selection
4. Verify defaults to INR
5. Check database has currency=INR

### Test Case 2: Browser Cache Cleared
1. Open application
2. Clear browser cache (Ctrl+Shift+Delete)
3. Hard refresh (Ctrl+F5)
4. Verify form loads correctly
5. Create loan
6. Verify success

### Test Case 3: API Direct Test
```bash
# Test with curl
curl -X POST http://localhost:8000/api/v1/loans/ \
  -H "Content-Type: application/json" \
  -d '{
    "borrower_name": "Test User",
    "amount": 10000,
    "depositor_name": "Test Lender",
    "giving_date": "2026-03-08",
    "due_date": "2027-03-08"
  }'

# Should succeed with default currency=INR
```

### Test Case 4: JavaScript Console Check
1. Open DevTools (F12)
2. Console tab
3. Try: `document.getElementById('currency')`
4. Should return `null` (after fix - field removed)
5. Should not cause error

---

## 📝 Long-term Improvements

### 1. Frontend Validation
```javascript
// Add validation before API call
function createLoan(event) {
    event.preventDefault();

    // Ensure currency is set
    const currency = document.getElementById('currency')?.value || 'INR';

    const formData = {
        // ...
        currency: currency,  // Guaranteed non-null
    };
}
```

### 2. Backend Robust Validation
```python
# In LoanCreate schema
@field_validator('currency', mode='before')
@classmethod
def validate_currency(cls, v):
    """Ensure currency is always set."""
    if v is None or v == '':
        return Currency.INR
    return v
```

### 3. API Error Logging
```python
# Enhanced error handling
@router.post("/", response_model=LoanResponse)
async def create_loan(loan: LoanCreate):
    try:
        logger.info("create_loan_request", data=loan.dict())
        return storage_service.create_loan(loan)
    except ValidationException as e:
        logger.error("validation_failed", error=str(e), data=loan.dict())
        raise HTTPException(status_code=422, detail={
            "message": "Validation failed",
            "errors": str(e),
            "hint": "Check required fields and data types"
        })
```

---

## ✅ Resolution Steps

### Step 1: Remove Currency Selection (Immediate)
- [x] Remove currency dropdown from HTML
- [ ] Update JavaScript to hardcode INR
- [ ] Test form submission
- [ ] Verify 422 error resolved

### Step 2: Update Backend Validation
- [ ] Make currency field truly optional
- [ ] Add field validator for null handling
- [ ] Test API with missing currency field
- [ ] Update API tests

### Step 3: Update Documentation
- [ ] Add 422 error to troubleshooting guide
- [ ] Document currency = INR only policy
- [ ] Update business requirements
- [ ] Add testing checklist

### Step 4: Repackage Windows Distribution
- [ ] Run package-windows.sh with fixes
- [ ] Test extracted package
- [ ] Verify form submission works
- [ ] Update version to 1.0.1

---

## 📞 Prevention Measures

### 1. Automated Testing
- **Unit tests**: Test API with missing/null fields
- **Integration tests**: Test frontend form submissions
- **E2E tests**: Full user flow testing

### 2. Validation Strategy
- **Frontend**: Validate before sending request
- **Backend**: Accept and default missing optional fields
- **API**: Return clear error messages with field details

### 3. Deployment Checklist
- [ ] Test on clean Windows install
- [ ] Test on clean Mac install
- [ ] Clear browser cache and retest
- [ ] Test with network DevTools open
- [ ] Verify all API endpoints return expected codes

---

## 🎯 Summary

**Root Cause**: Currency field added to schema but not properly handled as optional
**Impact**: 422 validation error prevents loan creation
**Fix**: Remove currency selection UI, hardcode INR, improve backend validation
**Prevention**: Better testing, validation strategy, deployment checklist

**Status**: Fix in progress ✅
**ETA**: Within current session
**Priority**: P0 (Blocking)

---

**Document Version**: 1.0
**Last Updated**: 2026-03-08
**Author**: Development Team
