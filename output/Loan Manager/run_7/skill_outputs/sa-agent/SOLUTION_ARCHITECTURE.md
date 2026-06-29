# Loan Manager — Solution Architecture
**Agent:** sa-agent (Wave 1)
**Run:** run_7
**Date:** 2026-04-05
**Phase:** Phase 3 Closure / Phase 4 MVP

---

## Architecture State — Run 7

### Current Layered Architecture (Confirmed Stable)

```
main.py
  └── ui/main_window.py          QMainWindow — tab host, startup recompute, recovery check
        ├── ui/entry_tab.py      EntryTab — new loan form
        ├── ui/view_tab.py       ViewTab — sortable/inline-editable table
        │     └── ui/dialogs/extend_dialog.py
        │     └── ui/dialogs/paidoff_dialog.py
        ├── ui/interest_calculator_tab.py  InterestCalculatorTab
        │     └── ui/dialogs/calculation_dialog.py
        └── ui/pending_approval_tab.py    PendingApprovalTab
              └── ui/widgets.py   ClickableDateEdit, DatePickerDelegate

data/  (adapter layer — used by UI only)
  ├── csv_manager.py    read_loans, write_loan, update_loan, delete_loan, mark_paidoff,
  │                     extend_loan, batch_extend_loans, read_autocomplete_values
  ├── ref_id_manager.py adapter → loan_manager/ref_id_manager.py
  ├── report_manager.py adapter → loan_manager/report_manager.py
  ├── status_engine.py  re-export shim → loan_manager/status_engine.py (canonical)
  ├── export_service.py
  ├── import_service.py
  └── seed.py

loan_manager/  (canonical business logic layer)
  ├── status_engine.py      compute_status(), recompute_all()
  ├── interest_calculator.py calculate_monthly(), calculate_daily(), calculate_both()
  ├── ref_id_manager.py     RefIdManager: generate_ref_id(), reset_counter()
  ├── report_manager.py     CSVReportManager: full report CRUD
  └── csv_manager.py        CSVManager: batch_extend_loans()

models/
  ├── loan.py       Loan dataclass, CSV_FIELDNAMES
  └── report.py     PendingReport dataclass, ReportRecord dataclass
```

**ADR-005 Canonical:** `loan_manager/status_engine.py` is the authoritative status engine. `data/status_engine.py` is the re-export shim only. This is resolved from run_2 and confirmed.

---

### ADR-TC05-01: has_pending_paidoff_report() Placement

**Decision (PD-12, CONFIRMED):** `has_pending_paidoff_report(reference_id: str) -> bool` belongs in `data/report_manager.py` as a new adapter function. It delegates to `loan_manager/report_manager.py` `CSVReportManager`.

**Implementation signature:**
```python
# data/report_manager.py
def has_pending_paidoff_report(reference_id: str) -> bool:
    """Return True if any Pending Paidoff-mode report contains this reference_id."""
    return _manager.has_pending_paidoff_report(
        _reports_path(), _records_path(), reference_id
    )
```

**CSVReportManager method:**
```python
# loan_manager/report_manager.py
def has_pending_paidoff_report(
    self, reports_path: Path, records_path: Path, reference_id: str
) -> bool:
    """Check if a Pending Paidoff-mode report exists for the given reference_id."""
    # Read all pending reports, filter mode="Paidoff"
    pending_reports = self.read_pending_reports(reports_path)
    paidoff_report_ids = {
        r.report_id for r in pending_reports if r.mode == "Paidoff"
    }
    if not paidoff_report_ids:
        return False
    # Check records
    all_records = self._read_all_records(records_path)
    for rec in all_records:
        if rec.report_id in paidoff_report_ids and rec.reference_id == reference_id:
            return True
    return False
```

**view_tab.py update — _show_context_menu():**
```python
from data.report_manager import has_pending_paidoff_report

# In _show_context_menu():
paidoff_action.setEnabled(
    loan.due_date is not None and not has_pending_paidoff_report(loan.reference_id)
)
```

---

### ADR-TC08-A/B: paidoff_date Field Architecture

**Option A (field reuse — zero code change):**
- `ReportRecord.new_due_date` holds `paidoff_date` when mode="Paidoff"
- Approval logic reads `rec.new_due_date` in both paths — correct today
- Comment annotation only: `# For mode="Paidoff", new_due_date = paidoff_date`
- SA assessment: Acceptable for prototype. Creates schema ambiguity but works correctly.

**Option B (dedicated column — SA recommended):**
```python
# models/report.py — add to ReportRecord dataclass
paidoff_date: Optional[date] = None
```

CSV_FIELDNAMES for `pending_report_records.csv` gains `paidoff_date` column. Additive — no migration needed. Existing rows parse with `paidoff_date=""` → `None`.

Backward compatibility note: `_on_approve()` in pending_approval_tab.py must read `rec.paidoff_date or rec.new_due_date` for Paidoff mode to handle records written under Option A schema.

**SA Recommendation:** Option B. The semantic clarity outweighs the 2-hour investment. Prototype timeline permits.

**[REVIEW REQUIRED] TC-08:** User to choose Option A or B.

---

### ADR-BC02: Case Normalization Architecture

**Option B implementation (SA recommended):**
```python
# data/csv_manager.py — write_loan()
def _normalize_loan_names(loan: Loan) -> None:
    loan.borrower_name = (loan.borrower_name or "").lower()
    loan.borrower_group = (loan.borrower_group or "").lower()
    loan.depositor_name = (loan.depositor_name or "").lower() if loan.depositor_name else None
    loan.depositor_group = (loan.depositor_group or "").lower() if loan.depositor_group else None

def write_loan(loan: Loan) -> None:
    _normalize_loan_names(loan)
    # ... existing write logic
```

This normalizes at write time only (new entries). Existing CSV data is unaffected unless re-imported. Consistent with sample data convention (all lowercase).

**[REVIEW REQUIRED] BC-02:** User to choose Option A (no change), B (lowercase), or C (title case).

---

### SRE-01: Startup Recovery Warning — Architecture Review

**Finding from source code review of `ui/main_window.py`:**
The `_check_recovery_file()` method already handles all three recovery scenarios:
1. `recovery.tmp` — paidoff crash warning
2. `import_recovery.tmp` — import crash warning
3. `approval_recovery.tmp` — approval crash warning

**SA Conclusion:** SRE-01 is ALREADY IMPLEMENTED. No architectural change needed. Close this item.

---

### Architectural Completeness Assessment

| Component | Architecture Compliance | Issues |
|---|---|---|
| models/loan.py | Clean dataclass, minimal | None |
| models/report.py | Clean dataclass | TC-08 Option B would add paidoff_date field |
| loan_manager/status_engine.py | Canonical, well-tested | None |
| loan_manager/interest_calculator.py | Pure functions, no I/O | None |
| loan_manager/report_manager.py | CSVReportManager, injectable paths | Add has_pending_paidoff_report() |
| data/csv_manager.py | Adapter, correct layering | Add normalization (BC-02 if chosen) |
| data/report_manager.py | Adapter, correct | Add has_pending_paidoff_report() adapter |
| ui/view_tab.py | Correct QStandardItemModel+proxy pattern | Add TC-05 guard to _show_context_menu() |
| ui/widgets.py | ClickableDateEdit — setCalendarPopup(True) confirmed | None — UTR1 resolved |
| ui/main_window.py | Startup recompute + recovery check | SRE-01 already done |

**Architecture risk: LOW.** All Phase 4 changes are additive. No breaking changes to existing schemas or function signatures.
