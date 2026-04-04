# QA Lead: Test Scope — Loan Manager run_3
**Date:** 2026-04-03
**Run:** run_3 / Wave 2
**Author:** QA Lead Agent
**Scope:** Test scope for 2 implementable items (CHG-02-EXT, BUG-02-REF)

---

## 1. Test Entry Criteria

Before testing begins, the following must be confirmed:
- [x] PaidoffDialog updated with 3 new fields and accessor methods
- [x] _action_paidoff() updated to read new dialog values
- [x] _generate_paidoff_report() updated with new signature and per-event params
- [x] STATUS_COLORS dict updated with exact hex values
- [x] STATUS_TEXT_COLOR = QColor("#ffffff") added
- [x] setForeground() applied in _make_row() helpers
- [x] TC-302 verified (data/report_manager.py adapter shim exists)

---

## 2. CHG-02-EXT Test Scope

### Test Area 1: PaidoffDialog — New Fields

| Test ID | Description | Type | Expected Result |
|---|---|---|---|
| T-R3-01 | Dialog opens with default field values | Unit | paidoff_date=today, interest_rate=0.0, commission_rate=0.0, tds_flag=False |
| T-R3-02 | Dialog accessors return set values | Unit | interest_rate() returns 12.5, commission_rate() returns 2.0, tds_flag() returns True when set |
| T-R3-03 | Dialog Cancel does not proceed | Integration | _action_paidoff() returns early; no mark_paidoff() or _generate_paidoff_report() called |
| T-R3-04 | Dialog OK proceeds with default values | Integration | interest_rate=0.0, commission_rate=0.0, tds_flag=False passed to report generator |

### Test Area 2: _generate_paidoff_report() Logic

| Test ID | Description | Type | Expected Result |
|---|---|---|---|
| T-R3-05 | loan.due_date is None — report skipped | Unit | WARNING logged; no CSV write; function returns early |
| T-R3-06 | paidoff_date = due_date → extension_days = 0 | Unit | report generated with extension_period=0, interest_amount=0.0 |
| T-R3-07 | paidoff_date > due_date → positive extension | Unit | extension_days > 0; interest calculated correctly |
| T-R3-08 | paidoff_date < due_date → extension_days = max(0,...) = 0 | Unit | interest_amount = 0.0 (no negative extension) |
| T-R3-09 | interest_rate=12.0, commission_rate=2.0, extension_days=30 | Unit | interest_amount=(amount*12*30)/(365*100); commission=(amount*2*30)/(365*100) |
| T-R3-10 | tds_flag=True, interest_rate > 0 | Unit | tds_amount = 0.1 * interest_amount |
| T-R3-11 | tds_flag=False | Unit | tds_amount = 0.0 |
| T-R3-12 | Report mode="Paidoff" written to pending_reports.csv | Integration | report.mode == "Paidoff" in read_pending_reports() |
| T-R3-13 | Report record reference_id matches loan | Integration | ReportRecord.reference_id == loan.reference_id |
| T-R3-14 | SRE-R3-02: interest_rate out of range (e.g. 101.0) | Unit | ERROR logged; function returns early; no report written |
| T-R3-15 | SRE-R3-02: commission_rate out of range | Unit | ERROR logged; function returns early |
| T-R3-16 | SRE-R3-01: DEBUG log emitted with params | Unit | Log contains interest_rate and commission_rate values |
| T-R3-17 | Report generation failure does NOT rollback Paidoff | Integration | loan archived in history.csv; WARNING shown in UI; no crash |

### Test Area 3: Pending Approval Tab — Paidoff Warning

| Test ID | Description | Type | Expected Result |
|---|---|---|---|
| T-R3-18 | Paidoff report selected → warning label visible | Integration | _paidoff_warning_label.isVisible() == True |
| T-R3-19 | Non-Paidoff report selected → warning label hidden | Integration | _paidoff_warning_label.isVisible() == False |
| T-R3-20 | Warning text exact match | Integration | Label text == "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied." |

---

## 3. BUG-02-REF Test Scope

### Test Area 4: Status Colors

| Test ID | Description | Type | Expected Result |
|---|---|---|---|
| T-R3-21 | STATUS_COLORS["Active"] hex value | Unit | QColor("#2d6a4f") == STATUS_COLORS["Active"] |
| T-R3-22 | STATUS_COLORS["Overdue"] hex value | Unit | QColor("#9b2226") == STATUS_COLORS["Overdue"] |
| T-R3-23 | STATUS_COLORS["Pending"] hex value | Unit | QColor("#ca6702") == STATUS_COLORS["Pending"] |
| T-R3-24 | STATUS_COLORS["Paidoff"] hex value | Unit | QColor("#495057") == STATUS_COLORS["Paidoff"] |
| T-R3-25 | STATUS_TEXT_COLOR is white | Unit | STATUS_TEXT_COLOR == QColor("#ffffff") |
| T-R3-26 | _make_row() sets background and foreground | Unit | item.background().color().name() == expected_hex and item.foreground().color().name() == "#ffffff" |
| T-R3-27 | Color update on status change | Integration | After inline due_date edit changes status, row color updates to new status color |

---

## 4. Regression Test Areas

| Area | Risk | Tests to Verify |
|---|---|---|
| Paidoff write atomicity (mark_paidoff) | Low — unchanged | Existing tests for mark_paidoff() |
| calculate_daily() formula | Low — unchanged | Existing tests in test_interest_calculator.py |
| read_pending_reports() — mode filter | Low — only Pending-status filtering, no mode filtering | Existing read tests; add T-R3-12 for mode="Paidoff" |
| _action_paidoff() error path | Medium — signature changed | T-R3-17 |
| ClickableDateEdit in PaidoffDialog | Low — should be present from run_2 | Verify paidoff_dialog.py uses ClickableDateEdit not plain QDateEdit |

---

## 5. Test Implementation Notes

### Unit Test Approach (Python/PySide6)

Tests for dialog fields require a QApplication instance. Use pytest-qt or a conftest.py fixture:

```python
import pytest
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])
```

For STATUS_COLORS tests, no QApplication is needed — QColor can be instantiated without a display.

For `_generate_paidoff_report()` tests, inject mock write functions to avoid real CSV writes:

```python
# Use monkeypatch to stub write_report and write_report_records
```

### Test File Locations

| Test File | Tests Covered |
|---|---|
| `tests/test_paidoff_dialog.py` (new or update) | T-R3-01 to T-R3-04 |
| `tests/test_view_tab_paidoff.py` (new or update) | T-R3-05 to T-R3-17 |
| `tests/test_pending_approval_warning.py` (new or update) | T-R3-18 to T-R3-20 |
| `tests/test_view_tab_colors.py` (new or update) | T-R3-21 to T-R3-27 |

---

## 6. QA Lead [REVIEW REQUIRED] Items

| ID | Item | Priority | Blocking? |
|---|---|---|---|
| TC-302 | data/report_manager.py adapter shim must be verified before T-R3-12 and T-R3-13 can be run | High | Yes — if shim missing, integration tests cannot run |
| BC-301 | Warning label placement — affects which widget to query in T-R3-18 to T-R3-20 | Medium | No — tests can reference label by text content regardless of position |

---

## 7. Dev Lead Test Scope Co-Sign Request

QA Lead requests Dev Lead sign-off on the following additions beyond the KT handoff:
1. T-R3-14 and T-R3-15 (SRE-R3-02 range validation tests) — these were not in the Dev Lead KT but are SRE-mandated
2. T-R3-27 (color update on status change after inline edit) — integration test that covers the full repaint cycle

**Status:** Awaiting Dev Lead co-sign.

