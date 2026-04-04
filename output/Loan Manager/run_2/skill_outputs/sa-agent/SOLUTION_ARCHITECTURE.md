# SA: Solution Architecture — Loan Manager run_2
**Date:** 2026-04-03
**Run:** run_2 / Wave 1
**Author:** Solution Architect Agent
**Scope:** Delta assessment for 7 change items (CHG-01, CHG-02, BUG-01–04, DOC-01)

---

## 1. Architecture Context

Loan Manager is a single-user PySide6 desktop application following a three-layer architecture:

```
UI Layer (PySide6 tabs/dialogs)
    |
Data Adapter Layer (data/*.py — app-layer CSV adapters)
    |
Domain/Service Layer (loan_manager/*.py — injectable, testable services)
    |
File Storage (CSV files: loans.csv, history.csv, loans_meta.csv,
               pending_reports.csv, pending_report_records.csv, reports_meta.csv)
```

**Layer contract (confirmed from run_1):**
- `loan_manager/` = canonical class-based implementations with dependency injection (used by tests)
- `data/` = app-layer adapter shims that bind loan_manager classes to concrete CSV paths
- `data/status_engine.py` is a re-export of `loan_manager/status_engine.py` (confirmed shim)
- UI widgets import exclusively from `data/*` — never from `loan_manager/*` directly

---

## 2. SA Technical Assessment per Change Item

---

### CHG-01 — No Due Date Default Checked

**Feasibility:** High
**Complexity:** Low

**Architectural Impact:**
- `ui/entry_tab.py`: Single-line fix at widget initialisation (`setChecked(True)`) and in `_reset_form()`
- No domain layer changes. No data model changes.

**Recommended Approach:**
Change `self._no_due_date_cb.setChecked(False)` to `setChecked(True)` at both call sites in `entry_tab.py`. The `_toggle_due_date()` slot already handles the cascade (disabling/enabling the due_date field), so the fix is purely at the initialisation point.

**Technical Risks:**
- Low: no downstream propagation risk. The only dependency is the due_date enable/disable toggle which is driven by the checkbox state event.

**Estimated Technical Effort:** S

---

### CHG-02 — Paidoff Generates Daily Interest Report

**Feasibility:** High
**Complexity:** Medium

**Architectural Impact:**
- `ui/view_tab.py`: `_action_paidoff()` must be extended to call a new private method `_generate_paidoff_report(loan, paidoff_date)` after `mark_paidoff()` returns success.
- `data/csv_manager.py`: `mark_paidoff()` is unchanged — it retains its atomic-write contract.
- `loan_manager/interest_calculator.py`: `calculate_daily()` is reused without modification.
- `loan_manager/report_manager.py`: `generate_report_id()`, `write_report()`, `write_report_records()` are reused without modification.
- No new modules required.

**Recommended Approach:**
Implement `_generate_paidoff_report(loan, paidoff_date)` as a private method on `ViewTab`. The sequence:
1. Compute `extension_period_days = max(0, (paidoff_date - loan.due_date).days)`
2. If `loan.due_date is None`, log WARNING and return (no report generated)
3. Build a report record dict compatible with `calculate_daily()` input format
4. Call `calculate_daily(record)` to get `interest_amount` and `commission_amount`
5. Call `generate_report_id()` → `write_report()` → `write_report_records()`
6. On any exception in steps 3–5, log ERROR and show a non-blocking QMessageBox warning to the user
7. The `mark_paidoff()` write is NOT rolled back on report generation failure

**Architecture Decision Records:**

**ADR-001: Report generation is best-effort, not transactional with Paidoff write**
- Chosen: Best-effort (non-atomic)
- Rationale: `mark_paidoff()` uses an atomic write with `recovery.tmp` sentinel. Wrapping the entire Paidoff+Report operation in a single transaction is not feasible with CSV storage. The business impact of a missing report is lower than the impact of a failed Paidoff write. The user is notified via non-blocking warning if report fails.

**ADR-002: Paidoff report approval flow — BC-06 semantic conflict**
- Status: Flagging to PO and DM (from BSA finding)
- Issue: When a Paidoff report is approved in the Pending Approval tab, `batch_extend_loans()` looks for the loan in `loans.csv`. But `mark_paidoff()` has already moved the loan to `history.csv`. The approval will trigger the "Records in this report have been deleted" warning path in the existing approval flow.
- Recommended approach for Phase 3: Accept the existing "deleted records" warning as the outcome for Paidoff report approval — the warning message should be updated to clarify this is expected for Paidoff reports, not an error.
- Phase 4 backlog: Introduce a `report_type` field (`extension` vs `paidoff`) and branch the approval logic accordingly. Paidoff reports would use "FYI/Acknowledge" flow rather than `batch_extend_loans()`.
- **[REVIEW REQUIRED — TC-01]:** The SA recommends updating the approval warning message in Phase 3 to distinguish Paidoff reports from genuinely-deleted extension reports. This requires a one-line copy change in `pending_approval_tab.py`. Confirm whether this is in-scope for Phase 3 or deferred.

**Technical Risks:**
- Race condition: None expected (single-user desktop app — no concurrent writes)
- Data consistency: If `write_report()` partially writes (OS-level crash mid-write), the CSV may be truncated. Existing CSV write pattern does not use atomic two-phase for reports. For Phase 3, acceptable. Phase 4: consider extending atomic write pattern to report writes.

**Estimated Technical Effort:** M

---

### BUG-01 — Interest Calculator Filter Reset

**Feasibility:** High
**Complexity:** Low-Medium

**Architectural Impact:**
- `ui/interest_calculator_tab.py`: `_on_apply_filters()` ordering fix only.
- No domain layer, data layer, or storage changes.

**Recommended Approach:**
Capture all five filter combo current values into local variables (using `combo.currentText()`) at the top of `_on_apply_filters()` BEFORE calling `_load_loans()`. After `_load_loans()` and `_populate_filters()` complete (which clears and repopulates combos), restore each combo to the captured value using `combo.setCurrentText(captured_value)`. If the captured value is no longer present in the combo (item was deleted), the combo will silently revert to index 0 ("All") — which is the correct graceful fallback.

**ADR-003: blockSignals guard is already present in _populate_filters()**
- The existing `combo.blockSignals(True)` pattern in `_populate_filters()` is correct and must be preserved. The fix adds value capture before and value restore after, not a change to the signal-blocking logic.

**Technical Risks:**
- Low: only affect is the ordering of operations in a single method. No cross-module impact.

**Estimated Technical Effort:** S

---

### BUG-02 — View Tab Color Palette

**Feasibility:** High
**Complexity:** Low

**Architectural Impact:**
- `ui/view_tab.py`: `STATUS_COLORS` dict and the item-coloring loop in `_make_row()` (or equivalent rendering path).
- Must explicitly set both `Qt.BackgroundRole` and `Qt.ForegroundRole` on each item.

**Recommended Approach:**
Replace the `STATUS_COLORS` dict values with high-contrast pairs:
```
STATUS_COLORS = {
    "Active":  {"bg": "#2d6a4f", "fg": "#ffffff"},
    "Overdue": {"bg": "#9b2226", "fg": "#ffffff"},
    "Pending": {"bg": "#ca6702", "fg": "#ffffff"},
    "Paidoff": {"bg": "#495057", "fg": "#ffffff"},
}
```
In the row-coloring loop, apply `QBrush` for both `Qt.BackgroundRole` and `Qt.ForegroundRole` on every `QStandardItem` in the row.

**Technical Risks:**
- Low. Color is a pure presentational change. The dark palette applies exclusively to the status cell background or full row based on existing implementation pattern.
- **[REVIEW REQUIRED — BC-02]:** User to confirm the palette choice at prototype review. Implementation can proceed with the above palette; user may request adjustments.

**Estimated Technical Effort:** S

---

### BUG-03 — Paidoff Marking Flow

**Feasibility:** High (context menu path — Phase 3 scope only)
**Complexity:** Low (for context menu fix)

**Architectural Impact:**
- Phase 3: Verify `_action_paidoff()` is connected to the context menu. If BUG-02 (color fix) makes rows readable, the right-click path should be usable.
- Phase 4: `StatusDelegate(QItemDelegate)` for inline QComboBox editing. Not in Phase 3 scope per PD-R2-06.

**Technical Risks:**
- If the context menu is not visible due to a missing connection, the risk is P1. Code inspection confirmed the context menu path is wired in `view_tab.py`. The primary blocker for users was BUG-02 (unreadable rows).

**Estimated Technical Effort:** S (Phase 3 verification only)

---

### BUG-04 — Windows Date Picker Click Behavior

**Feasibility:** High
**Complexity:** Low

**Architectural Impact:**
- New shared widget: `ClickableDateEdit(QDateEdit)` subclass — should live in `ui/widgets/` or `ui/dialogs/` as a shared utility.
- Replace `QDateEdit` instantiation in:
  - `ui/entry_tab.py` (giving_date and due_date fields)
  - `ui/dialogs/paidoff_dialog.py` (paidoff_date field)
  - `ui/dialogs/extend_dialog.py` — verify: ExtendDialog uses SpinBox+Combo for period, not DateEdit. If a DateEdit is present, replace it. If absent, no change needed.

**ADR-004: ClickableDateEdit placement**
- Chosen: Create `ui/widgets/clickable_date_edit.py` as a standalone module
- Rationale: Avoids import cycles and makes the widget reusable across all dialog and tab files. Single import line change in each consumer file.

**Technical Risks:**
- Low: `mousePressEvent` override calling `self.showPopup()` is a well-understood PySide6 pattern.
- Cross-platform: On macOS, the field already opens on click — the override is a no-op since `showPopup()` when already open is a safe call.

**Estimated Technical Effort:** S

---

### DOC-01 — Import Parser DD-MM-YYYY

**Feasibility:** High
**Complexity:** Low

**Architectural Impact:**
- `data/import_service.py`: Add `_parse_flexible_date(s: str) -> Optional[date]` private helper.
- Replace direct `date.fromisoformat()` calls at lines 168 and 171 of `_row_to_loan()`.
- No schema changes. No UI changes.

**ADR-005: Date parsing fallback order**
- Chosen: ISO first (`date.fromisoformat()`), then `strptime("%d-%m-%Y")`, then return None + WARNING log
- Rationale: ISO is the canonical internal format (R8). Preserving ISO-first ensures backward compatibility with all existing import files. Adding DD-MM-YYYY as a secondary format matches the sample input documentation format exactly.

**Technical Risks:**
- Ambiguous dates: `01-02-2026` in DD-MM-YYYY is February 1st. In ISO it would fail `fromisoformat` (not a valid ISO date) so there is no ambiguity with the two-format fallback.
- XLSX imports: The XLSX parser (`_parse_xlsx`) converts cell values to strings before passing to `_row_to_loan()`. Dates stored as Excel date serial numbers in XLSX will arrive as numeric strings (e.g., "46019") — these will fail both parse attempts and be logged as WARNING. This is a pre-existing limitation and out of scope for DOC-01.

**Estimated Technical Effort:** S

---

## 3. Integration Impact Analysis — CHG-02 Paidoff Report

## Integration Impact Analysis: CHG-02 Paidoff Report Generation

**Affected Systems:**
| System / Component | Type of Impact | Action Required |
|---|---|---|
| `ui/view_tab.py` `_action_paidoff()` | Additive | Add `_generate_paidoff_report()` call after `mark_paidoff()` |
| `loan_manager/report_manager.py` | No change | Reuse `generate_report_id()`, `write_report()`, `write_report_records()` |
| `loan_manager/interest_calculator.py` | No change | Reuse `calculate_daily()` |
| `pending_reports.csv` | Additive write | New row per Paidoff event |
| `pending_report_records.csv` | Additive write | New row per Paidoff event |
| `ui/pending_approval_tab.py` | Indirect — approval flow semantics | See ADR-002 and TC-01 |

**API / Contract Changes:**
- None. All interactions use existing function signatures.

**Migration / Rollout Considerations:**
- No data migration required. Existing CSV schemas accommodate new Paidoff reports without column additions.
- Existing pending reports are unaffected.

---

## 4. Architecture Design — Shared Widget Module

## Architecture Design: ui/widgets/ Shared Widget Layer

**Architecture Pattern:** Layered — new shared widget sub-layer within UI layer

**Components:**
| Component | Responsibility | Technology |
|---|---|---|
| `ui/widgets/clickable_date_edit.py` | `QDateEdit` subclass that opens calendar on any click | PySide6 QDateEdit |
| `ui/entry_tab.py` | Consumer — replaces both QDateEdit instances | Import `ClickableDateEdit` |
| `ui/dialogs/paidoff_dialog.py` | Consumer — replaces QDateEdit instance | Import `ClickableDateEdit` |
| `ui/dialogs/extend_dialog.py` | Verify — if DateEdit present, replace | Import `ClickableDateEdit` |

**Data Flow:**
User click event → `ClickableDateEdit.mousePressEvent()` → `self.showPopup()` → calendar visible

**Non-Functional Requirements:**
- Cross-platform: `showPopup()` is idempotent. No macOS regression.
- No new dependencies: PySide6 only.

---

## 5. Risk Register (SA additions for run_2)

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| SA-R01 | BC-06: Paidoff report approval triggers "deleted records" warning — architecturally expected but user-confusing | Medium | Update approval warning copy in Phase 3 to clarify Paidoff reports; full fix in Phase 4 |
| SA-R02 | CHG-02 partial CSV write on OS crash (report files not atomic) | Low | Acceptable for Phase 3 single-user desktop; Phase 4 extend atomic write to reports |
| SA-R03 | XLSX date serial number import (pre-existing limitation) | Low | Out of scope DOC-01; document known limitation in user guide |
| SA-R04 | QComboBox Status delegate deferred (BUG-03 full fix) — Paidoff via right-click only | Medium | Context menu is viable path; document in user guide; Phase 4 delegate |

---

## 6. SA Naming Discrepancy Check (cross-reference with run_1 backend-dev spec)

Per SA SKILL.md: cross-reference method names against prior run's backend-dev spec to catch discrepancies early.

Prior run backend-dev spec (`run_1`) was not available in this run context. The SA has verified all method names against the actual source code:

| Method Referenced in Design | Confirmed in Source | File |
|---|---|---|
| `mark_paidoff(reference_id, paidoff_date)` | Confirmed | `data/csv_manager.py` |
| `calculate_daily(record: dict) -> dict` | Confirmed | `loan_manager/interest_calculator.py` |
| `write_report(report)` | Confirmed | `loan_manager/report_manager.py` |
| `write_report_records(records)` | Confirmed | `loan_manager/report_manager.py` |
| `generate_report_id(reports_meta_path, report_date)` | Confirmed | `loan_manager/report_manager.py` |
| `_on_apply_filters()` | Confirmed | `ui/interest_calculator_tab.py` |
| `_populate_filters()` | Confirmed | `ui/interest_calculator_tab.py` |
| `_action_paidoff()` | Confirmed | `ui/view_tab.py` |
| `STATUS_COLORS` | Confirmed | `ui/view_tab.py` |

No naming discrepancies found.
