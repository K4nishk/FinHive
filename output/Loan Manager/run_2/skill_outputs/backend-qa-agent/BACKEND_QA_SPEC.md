# Backend QA: Test Scenarios — Loan Manager run_2
**Date:** 2026-04-03
**Run:** run_2 / Wave 2
**Author:** Backend QA Agent
**Scope:** Desktop app — all layers (service + UI) per agent selection matrix (no frontend-qa-agent for PySide6 apps)

---

## Backend QA → Backend Dev Response: Loan Manager run_2

**Sync received:** Yes
**Test scope — agreed:**
- [x] CHG-01: checkbox default state + reset state
- [x] CHG-02: report creation happy path, zero extension, early payoff clamp, no due_date skip, failure isolation
- [x] BUG-01: filter persist + graceful revert
- [x] BUG-02: color role assignment (bg + fg)
- [x] BUG-03: context menu connection verification
- [x] BUG-04: ClickableDateEdit mousePressEvent calls showPopup
- [x] DOC-01: ISO accepted, DD-MM-YYYY accepted, invalid skipped

**Test scope — additions from QA:**
- [ ] CHG-02: Verify pending_approval_tab.py renders empty report gracefully (no records for orphan report — REL-02)
- [ ] CHG-02: Verify `logger.info()` called on successful report generation (log observability)
- [ ] DOC-01: Backward compatibility — existing ISO imports not broken after parser change
- [ ] DOC-01: Mixed file — some rows ISO, some DD-MM-YYYY — all imported correctly
- [ ] BUG-01: Verify "All" filter still shows all loans (regression: no over-filtering after fix)
- [ ] BUG-02: Verify no status with missing color key causes KeyError (unknown status graceful handling)

**Clarifications needed before I can finalise scope:**
- [Q1] CHG-02: What are the exact column names written to `pending_report_records.csv` for the Paidoff report row? Needed to write assertion on CSV content. (e.g., is it `extension_period` or `extension_period_days`?)
- [Q2] DOC-01: Is `_parse_flexible_date()` a private function (not callable from tests directly) or can it be imported for unit testing? If private, tests must go through `import_loans()` integration path.

**Scope confirmed:** Yes (pending Q1 and Q2 clarifications — will not block writing test skeletons)

---

## Backend Test Scenarios: Loan Manager run_2

### CHG-01 — No Due Date Default

| ID | Scenario | Input | Expected | Priority |
|---|---|---|---|---|
| BE-01 | EntryTab initialises with No Due Date checkbox checked | Form created (no user action) | `_no_due_date_cb.isChecked() == True` | P1 |
| BE-02 | _reset_form() restores checkbox to checked | Submit loan → form resets | `_no_due_date_cb.isChecked() == True` after reset | P1 |
| BE-03 | Due Date field disabled when No Due Date checked at init | Form created | `_due_date_edit.isEnabled() == False` | P1 |
| BE-04 | Uncheck No Due Date → Due Date field becomes enabled | User unchecks | `_due_date_edit.isEnabled() == True` | P2 |

**Runner:** `pytest tests/ui/test_entry_tab.py -k "no_due_date or due_date_default"`

---

### CHG-02 — Paidoff Report Generation

| ID | Scenario | Input | Expected | Priority |
|---|---|---|---|---|
| BE-05 | Paidoff with due_date — normal extension | paidoff_date=2026-05-01, due_date=2026-04-01 | pending_reports.csv: 1 new row mode="Daily" status="Pending"; pending_report_records.csv: extension_period=30 | P1 |
| BE-06 | Paidoff same day as due_date — zero extension | paidoff_date=2026-04-01, due_date=2026-04-01 | extension_period=0, interest_amount=0.00 | P1 |
| BE-07 | Paidoff before due_date — early payoff | paidoff_date=2026-03-15, due_date=2026-04-01 | extension_period=0 (clamped), interest_amount=0.00 | P1 |
| BE-08 | Paidoff with no due_date — skip report | loan.due_date=None, paidoff_date=any | No new rows in pending_reports.csv; WARNING log emitted; Paidoff write succeeds | P1 |
| BE-09 | Report generation raises exception after Paidoff write | Mock write_report() to raise IOError | Loan in history.csv (Paidoff write preserved); ERROR log emitted; QMessageBox warning shown | P1 |
| BE-10 | Paidoff report appears in Pending Approval tab | Normal paidoff flow | Report visible in pending_approval_tab with loan reference_id | P2 |
| BE-11 | Paidoff report INFO log on success | Normal paidoff flow | `logger.info` called with report_id and loan.reference_id | P2 |
| BE-12 | Orphan pending_reports.csv row (no matching records) handled gracefully | Manually insert header row with no records | pending_approval_tab renders without KeyError or crash | P2 |

**Runner:** `pytest tests/ui/test_view_tab_paidoff.py`
**Integration runner:** `pytest tests/integration/test_paidoff_flow.py`

**Data setup requirements:**
- Loan fixture with `due_date` set (BE-05, BE-06, BE-07, BE-10)
- Loan fixture with `due_date=None` (BE-08)
- Mock for `write_report()` that raises IOError (BE-09)
- Temporary CSV files for pending_reports.csv and pending_report_records.csv (use tmp_path fixture)

---

### BUG-01 — Filter Persistence

| ID | Scenario | Input | Expected | Priority |
|---|---|---|---|---|
| BE-13 | BorrowerGroup filter persists after Apply Filters | Select "bg1", click Apply | combo shows "bg1", table shows only bg1 loans | P1 |
| BE-14 | All five filters persist simultaneously | Select all five filters, click Apply | All five combos show selected values | P1 |
| BE-15 | Filter reverts to "All" when value no longer in list | Select "bg1", remove all bg1 loans, click Apply | combo shows "All" | P2 |
| BE-16 | "All" filter shows all loans after fix | Leave all filters as "All", click Apply | All loans shown, no over-filtering | P1 |

**Runner:** `pytest tests/ui/test_interest_calculator_tab.py -k "filter"`

---

### BUG-02 — View Tab Colors

| ID | Scenario | Input | Expected | Priority |
|---|---|---|---|---|
| BE-17 | Active loan row has dark green bg and white fg | Loan with status="Active" | Qt.BackgroundRole = QColor("#2d6a4f"), Qt.ForegroundRole = QColor("#ffffff") | P1 |
| BE-18 | Overdue loan row has dark red bg and white fg | Loan with status="Overdue" | Qt.BackgroundRole = QColor("#9b2226"), Qt.ForegroundRole = QColor("#ffffff") | P1 |
| BE-19 | Pending loan row has dark amber bg and white fg | Loan with status="Pending" | Qt.BackgroundRole = QColor("#ca6702"), Qt.ForegroundRole = QColor("#ffffff") | P1 |
| BE-20 | Paidoff loan row has dark grey bg and white fg | Loan with status="Paidoff" | Qt.BackgroundRole = QColor("#495057"), Qt.ForegroundRole = QColor("#ffffff") | P1 |
| BE-21 | Unknown status does not raise KeyError | Loan with status="Unknown" | No exception; default Qt rendering used | P2 |

**Runner:** `pytest tests/ui/test_view_tab_colors.py`

---

### BUG-03 — Context Menu Connection

| ID | Scenario | Input | Expected | Priority |
|---|---|---|---|---|
| BE-22 | "Mark Paidoff" action is present in context menu | Right-click on view tab row | QAction "Mark Paidoff" exists in context menu | P1 |
| BE-23 | "Mark Paidoff" action is connected to _action_paidoff | Inspect action connections | action.triggered is connected (receivers > 0) | P1 |

**Runner:** `pytest tests/ui/test_view_tab_context_menu.py`

---

### BUG-04 — ClickableDateEdit

| ID | Scenario | Input | Expected | Priority |
|---|---|---|---|---|
| BE-24 | mousePressEvent calls showPopup | QMouseEvent sent to widget | showPopup() invoked (mock/spy) | P1 |
| BE-25 | entry_tab giving_date is ClickableDateEdit | Inspect widget type | isinstance(widget._giving_date_edit, ClickableDateEdit) == True | P2 |
| BE-26 | paidoff_dialog paidoff_date is ClickableDateEdit | Inspect widget type | isinstance(widget._paidoff_date_edit, ClickableDateEdit) == True | P2 |

**Runner:** `pytest tests/ui/test_clickable_date_edit.py tests/ui/test_entry_tab.py::test_giving_date_is_clickable`

---

### DOC-01 — Import Date Parsing

| ID | Scenario | Input | Expected | Priority |
|---|---|---|---|---|
| BE-27 | ISO format giving_date accepted | "2026-01-02" | giving_date = date(2026, 1, 2) | P1 |
| BE-28 | DD-MM-YYYY giving_date accepted | "02-01-2026" | giving_date = date(2026, 1, 2) | P1 |
| BE-29 | Invalid date format → None returned + WARNING | "not-a-date" | returns None, logger.warning called | P1 |
| BE-30 | Invalid date → row skipped, skipped counter incremented | Import with invalid giving_date | result.skipped += 1 | P1 |
| BE-31 | ISO due_date accepted | "2026-06-30" | due_date = date(2026, 6, 30) | P1 |
| BE-32 | DD-MM-YYYY due_date accepted | "30-06-2026" | due_date = date(2026, 6, 30) | P1 |
| BE-33 | Mixed ISO + DD-MM-YYYY in same file | 5 ISO rows + 5 DD-MM-YYYY rows | All 10 loans imported, 0 skipped | P1 |
| BE-34 | Backward compat: existing ISO imports unchanged | Original test CSV with ISO dates | Same result as before DOC-01 change | P1 |

**Runner:** `pytest tests/test_import_service.py -k "date or parse"`

---

### Reliability Scenarios (from SRE)

| ID | Scenario | Input | Expected | Priority |
|---|---|---|---|---|
| REL-01 | mark_paidoff mutual exclusivity | Call mark_paidoff(ref_id, date) | ref_id not in loans.csv AND ref_id in history.csv | P1 |
| REL-03 | Import batch with 10 malformed rows | 100-row CSV, 10 with missing giving_date | result.skipped=10, result.inserted=90 | P1 |
| TC-02a | Missing loans_meta.csv on generate_ref_id | Delete loans_meta.csv, call generate_ref_id | No unhandled exception; either creates file or raises ValueError with message | P2 |
| TC-02b | Missing reports_meta.csv on generate_report_id | Delete reports_meta.csv, call generate_report_id | No unhandled exception | P2 |

**Runner:** `pytest tests/test_csv_manager.py::test_mark_paidoff_mutual_exclusivity tests/test_import_service.py::test_batch_skip_count tests/test_ref_id_manager.py tests/test_report_manager.py`

---

## QA Testability Review

### `_generate_paidoff_report()` Testability

**Testability assessment:**
- [x] Business logic is separate from transport layer — the method only calls domain functions and writes CSVs
- [x] Error conditions are observable — IOError on CSV write is catchable; QMessageBox is shown
- [x] DB changes are verifiable — pending_reports.csv and pending_report_records.csv are file-based, easily inspected in tests using tmp_path
- [ ] The method uses `_data_dir()` internally — tests must mock or override `_data_dir()` to use tmp_path CSVs
- [ ] `CSVReportManager.generate_report_id()` requires a real or mocked reports_meta.csv

**Feedback:** The method should accept `data_dir: Optional[Path] = None` as an injectable parameter for testability, defaulting to `_data_dir()` when None. This avoids the need for monkeypatching `_data_dir` in every test.

**Verdict:** Ready for testing with monkeypatching; improved with injectable data_dir parameter

---

### `_parse_flexible_date()` Testability

**Testability assessment:**
- [x] Pure function — no side effects beyond logging
- [x] Easily unit tested with direct input/output assertion
- [ ] If defined as a module-level private function (`_parse_flexible_date`), it can be imported directly in tests via `from data.import_service import _parse_flexible_date`

**Verdict:** Ready for testing

---

## Test File Templates

The following test files should be created as part of Phase 3 implementation:

| File | Change Items Covered |
|---|---|
| `tests/ui/test_entry_tab.py` | CHG-01, BUG-04 |
| `tests/ui/test_view_tab_paidoff.py` | CHG-02 |
| `tests/ui/test_view_tab_colors.py` | BUG-02 |
| `tests/ui/test_view_tab_context_menu.py` | BUG-03 |
| `tests/ui/test_interest_calculator_tab.py` | BUG-01 |
| `tests/ui/test_clickable_date_edit.py` | BUG-04 |
| `tests/test_import_service.py` | DOC-01 (supplement existing if present) |
| `tests/integration/test_paidoff_flow.py` | CHG-02 integration |

**Common pytest fixtures needed (conftest.py):**
```python
@pytest.fixture
def tmp_data_dir(tmp_path):
    """Provides a temporary data directory with empty CSV schema files."""
    # Create empty CSVs: loans.csv, history.csv, loans_meta.csv,
    # pending_reports.csv, pending_report_records.csv, reports_meta.csv
    ...
    return tmp_path

@pytest.fixture
def sample_loan_with_due_date():
    return Loan(
        reference_id="2026_03_001",
        borrower_name="Test Borrower",
        borrower_group=None,
        amount=10000,
        giving_date=date(2026, 1, 1),
        due_date=date(2026, 4, 1),
        status="Active",
    )

@pytest.fixture
def sample_loan_no_due_date():
    return Loan(
        reference_id="2026_03_002",
        borrower_name="Test Borrower 2",
        borrower_group=None,
        amount=5000,
        giving_date=date(2026, 1, 1),
        due_date=None,
        status="Overdue",
    )
```

---

## Backend QA → QA Lead Report

**Scenarios defined:** 34 test scenarios across 8 change items
**P1 scenarios:** 22
**P2 scenarios:** 12
**New test files required:** 8
**Key risk areas:** CHG-02 report generation path (requires tmp_path CSV mocking); DOC-01 backward compatibility

**QA recommendation:** Scope confirmed — ready for QA Lead signoff
