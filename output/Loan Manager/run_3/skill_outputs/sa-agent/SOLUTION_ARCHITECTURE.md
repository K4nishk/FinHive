# SA: Solution Architecture — Loan Manager run_3
**Date:** 2026-04-03
**Run:** run_3 / Wave 1
**Author:** Solution Architect Agent
**Scope:** Delta assessment for 2 implementable items (CHG-02-EXT, BUG-02-REF)

---

## 1. Architecture Context (Unchanged from run_2)

Three-layer architecture remains intact:

```
UI Layer         : ui/*.py, ui/dialogs/*.py (PySide6 widgets)
Data Adapter     : data/*.py (app-layer CSV adapters — shims to loan_manager/)
Domain/Service   : loan_manager/*.py (injectable, class-based, testable)
File Storage     : ./data/*.csv
```

Layer contract confirmed:
- `loan_manager/` = injectable class-based implementations (used by tests)
- `data/` = app-layer adapter shims binding loan_manager classes to concrete CSV paths
- UI imports exclusively from `data/*` — never from `loan_manager/*` directly

---

## 2. CHG-02-EXT — Paidoff Dialog Extended Fields

### Feasibility: High | Complexity: Low-Medium

### Affected Components

| Component | File | Change Type |
|---|---|---|
| PaidoffDialog | `ui/dialogs/paidoff_dialog.py` | Field additions (3 new widgets) |
| ViewTab._action_paidoff | `ui/view_tab.py` | Reads 3 additional dialog values |
| ViewTab._generate_paidoff_report | `ui/view_tab.py` | Accepts 3 new parameters; removes hardcoded defaults |
| PendingApprovalTab | `ui/pending_approval_tab.py` | Warning message display for paidoff reports |

### Design Decision: PaidoffDialog Widget Additions

The existing `PaidoffDialog._build_ui()` uses a `QVBoxLayout`. The 3 new fields must be added below the existing date picker:

```
[Warning label — "Warning: This will archive the record to history..."]
[Reference ID label]
[Paidoff Date label]
[QDateEdit — paidoff_date]
--- NEW BELOW ---
[Interest Rate (%) label]
[QDoubleSpinBox — interest_rate, range 0.0–100.0, step 0.5, default 0.0]
[Commission Rate (%) label]
[QDoubleSpinBox — commission_rate, range 0.0–100.0, step 0.5, default 0.0]
[Apply TDS checkbox — default unchecked]
--- END NEW ---
[OK / Cancel buttons]
```

A `QFormLayout` nested inside the `QVBoxLayout` would present the 3 new fields cleanly alongside their labels with minimal code change.

### Design Decision: _generate_paidoff_report() Signature Change

Current signature inferred from run_2 plan (pseudocode):
```python
def _generate_paidoff_report(self, loan: Loan, paidoff_date: date) -> None
```

Updated signature for run_3:
```python
def _generate_paidoff_report(
    self,
    loan: Loan,
    paidoff_date: date,
    interest_rate: float,
    commission_rate: float,
    tds_flag: bool,
) -> None
```

The `interest_rate`, `commission_rate`, and `tds_flag` previously hardcoded (`12.0`, `2.0`, `False`) are replaced by these parameters.

### Design Decision: Paidoff Warning Message in Pending Approval Tab

R3 specifies the warning: "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied."

The warning must be tied to Paidoff-generated reports. The `pending_reports.csv` `mode` field currently stores `"Daily"` for paidoff reports (same as regular Daily calculator reports). This creates an identification problem: how does the Pending Approval Tab distinguish a paidoff report from a regular Daily report?

**[REVIEW REQUIRED — TC-301]:** A paidoff-generated report stored in `pending_reports.csv` with `mode="Daily"` is indistinguishable from a regular Daily Calculator report at the storage layer. The SA recommends adding a `paidoff_flag` boolean column to `pending_reports.csv` (set to `true` for paidoff-generated reports) to enable the Pending Approval Tab to conditionally display the warning. Alternatively, a reserved `mode` value (e.g., `"Paidoff"`) could be used without a schema change.

**SA Recommended Resolution:** Use `mode="Paidoff"` as a reserved mode value for paidoff-generated reports. This requires no schema change (existing `mode` column is STRING — any value is valid). The Pending Approval Tab checks `report.mode == "Paidoff"` to display the warning. This is the lowest-risk implementation and avoids a schema migration.

**Cross-reference to DM Agent:** DM must confirm whether `mode="Paidoff"` is acceptable or whether a `paidoff_flag` column is preferred.

### Layer Integrity Check

- `PaidoffDialog` remains in `ui/dialogs/` — correct
- `_generate_paidoff_report()` remains in `ui/view_tab.py` (UI layer) — calls `data/` adapter functions — correct
- `calculate_daily()` imported from `loan_manager.interest_calculator` — confirms no layer violation (loan_manager is imported by UI indirectly via data layer; the import in run_2 plan shows direct import from `loan_manager.interest_calculator` which is a minor layer skip — acceptable for calculator functions which have no I/O and are pure functions)

---

## 3. BUG-02-REF — Exact Status Color Codes

### Feasibility: High | Complexity: Trivial

### Affected Components

| Component | File | Change Type |
|---|---|---|
| STATUS_COLORS dict | `ui/view_tab.py` (line 73-78) | Value replacement — 4 QColor hex values |
| _make_row() | `ui/view_tab.py` | Add foreground color (white) to each QStandardItem |

### Current State (from source)

```python
STATUS_COLORS = {
    "Active": QColor("#d4edda"),
    "Overdue": QColor("#f8d7da"),
    "Pending": QColor("#fff3cd"),
    "Paidoff": QColor("#e2e3e5"),
}
```

### Target State

```python
STATUS_COLORS = {
    "Active": QColor("#2d6a4f"),
    "Overdue": QColor("#9b2226"),
    "Pending": QColor("#ca6702"),
    "Paidoff": QColor("#495057"),
}

STATUS_TEXT_COLOR = QColor("#ffffff")
```

### Foreground Color Application

Current `_make_row()` `item()` helper sets `it.setBackground(color)` but does NOT call `it.setForeground()`. On Windows with some Qt styles, the system default text color may be near-white, causing the readability issue reported in BUG-02.

The fix must add `it.setForeground(STATUS_TEXT_COLOR)` (or `QColor("white")`) in the `item()` and `numeric_item()` helper closures inside `_make_row()`.

### Architecture Impact

None — single file, two-line functional change plus a constant addition. No layer contract changes.

---

## 4. Removed Items — Architecture Assessment

### BUG-03 Removed

No architecture impact. The right-click context menu path (`_show_context_menu()` → `_action_paidoff()`) was already implemented in `view_tab.py`. CHG-02-EXT merely extends the dialog that this path opens.

### Priority Section Removed

No architecture impact.

---

## 5. SA [REVIEW REQUIRED] Summary

| ID | Item | Severity | Recommendation |
|---|---|---|---|
| TC-301 | Paidoff report identification in Pending Approval Tab: mode="Paidoff" vs paidoff_flag column | Medium | Use mode="Paidoff" as reserved value (no schema change); DM to confirm |

---

## 6. Phase 4 Architecture Implications

The following run_3 design decisions have Phase 4 implications:

| Decision | Phase 4 Impact |
|---|---|
| mode="Paidoff" reserved value (if accepted) | Phase 4 report filtering in Pending Approval Tab must handle this mode string |
| PaidoffDialog extended with rate fields | Phase 4 QComboBox StatusDelegate (if implemented) must also open the extended PaidoffDialog — not the old single-field version |
| White foreground color on status rows | Phase 4 theme chooser (R9) must override STATUS_COLORS and STATUS_TEXT_COLOR consistently |

