# PO Decisions — Loan Manager
**Run:** run_2, Wave 0 Initial + Wave 3 Synthesis
**Date:** 2026-04-03
**Author:** Product Owner Agent

---

## 1. Wave 0 Binding PO Decisions (Pre-Agent Unblocking)

These decisions are issued before Wave 1/2 agents begin work to eliminate downstream [REVIEW REQUIRED] blockers resolvable from REQUIREMENTS.md.

---

### PD-R2-01 — CHG-01: No Due Date Default Checked

**Decision:** Accept

**Business Rationale:** R1 explicitly states "By default, `No Due Date` is checked." The run_1 implementation has `setChecked(False)` which contradicts the requirement. This is a specification defect in run_1 code, not a scope change.

**Scope Impact:** Single-line change in `entry_tab.py` (line 89) and `_reset_form()` method. No data model impact.

**Implementation direction:** `self._no_due_date_cb.setChecked(True)` at form init and in `_reset_form()`.

---

### PD-R2-02 — CHG-02: Paidoff Generates Daily Interest Report

**Decision:** Accept

**Business Rationale:** R3 explicitly states: "When `paidoff_date` is entered, A report is generated for the interest calculations which is then sent over for approval, the calculations happen as per Daily Calculator. Refer to Requirement 5 `Daily` mode, `extension_period(days) = paidoff_date - due_date`."

**Scope Impact:** Extends `_action_paidoff()` in `view_tab.py` to call report generation after `mark_paidoff()` succeeds. Uses existing `calculate_daily()`, `write_report()`, and `write_report_records()` infrastructure — no new modules required.

**Implementation direction:**
- After `mark_paidoff()` completes successfully, call `_generate_paidoff_report(loan, paidoff_date)`.
- `extension_period_days = (paidoff_date - loan.due_date).days`
- If `loan.due_date is None`: skip report generation entirely (no due_date means no calculable interest period). Log a WARNING.
- Report generation failure must NOT rollback the Paidoff write. Log error and show user a non-blocking warning message.

**BC-01 Resolution — Early Payoff (paidoff_date < due_date):**
Requirements state `extension_period(days) = paidoff_date - due_date`. When `paidoff_date < due_date`, this yields a negative value. **PO Decision: treat negative extension_period_days as 0 days.** A loan paid before its due date has zero interest for the extension period. The report is still generated (with 0 interest amount) so the record is preserved in the approval queue as a zero-charge paidoff. This aligns with the principle that the report captures the paidoff event — not just positive extension scenarios.

---

### PD-R2-03 — CHG-03: Python Version Check Mandatory

**Decision:** Accept — already implemented, verification only

**Business Rationale:** R10 previously flagged this as [Low priority] but the new requirements remove that tag, making it mandatory. Code review of `run_windows.bat` (lines 6–26) and `run_mac.sh` (lines 7–19) confirms the check is already present and functional. No code change needed — only verification and documentation update.

---

### PD-R2-04 — BUG-01: Interest Calculator Filter Reset

**Decision:** Accept fix

**Business Rationale:** User explicitly reported this defect in User-Testing Requirement 1. Root cause is confirmed: `_on_apply_filters()` calls `_load_loans()` which calls `_populate_filters()` which clears and repopulates all combo boxes — erasing the user's selections before they are read.

**Fix direction:** Read all five filter values into local variables before calling `_load_loans()`. After reload, restore combo selections to previously-selected values if those values still exist in the refreshed list. If the previously-selected value no longer exists (e.g., a borrower was deleted), revert that filter to "All".

---

### PD-R2-05 — BUG-02: View Tab Color Palette

**Decision:** Accept fix — DEFER exact palette to user preference confirmation

**Business Rationale:** User explicitly reported data is unreadable due to light colors with white text. The current `STATUS_COLORS` uses `#d4edda` (light green), `#f8d7da` (light pink), `#fff3cd` (light yellow), `#e2e3e5` (light grey) — all pale backgrounds. On Windows, default system text may render as white or very light, making these unreadable.

**Fix direction:** Use darker, high-contrast background colors with explicit dark foreground text set per item. Recommended palette:
- Active: `#2d6a4f` (dark green) — white text
- Overdue: `#9b2226` (dark red) — white text
- Pending: `#ca6702` (dark amber) — white text
- Paidoff: `#495057` (dark grey) — white text

**[REVIEW REQUIRED — BC-02]:** User should confirm preferred color palette after seeing the fix. The palette above is functional but user may have preferences. This is logged for Phase 4 under R9 theme choices if the user wants to refine.

---

### PD-R2-06 — BUG-03: Paidoff Marking Flow

**Decision:** Accept partial fix — context menu confirmed as working path; QComboBox for Paidoff deferred

**Business Rationale:** User reported "unable to test out marking a record as Paidoff." Investigation reveals the context menu path (`_action_paidoff()` via right-click → Mark Paidoff) is correctly implemented. The likely reason for being "unable to test" is BUG-02 (unreadable records) or the QComboBox Status column not being present.

R3 says "User can toggle in between these states for any record in the tab. Leverage QComboBox for simplicity." The current implementation has Status as a read-only column (no QComboBox delegate). Context menu provides the Paidoff path.

**PO Decision:** For Phase 3, the context menu path for Paidoff is the accepted UX. Full QComboBox delegate for Status column (including Paidoff transition) is deferred to Phase 4. Rationale: QComboBox delegate requires a custom `QItemDelegate` which is non-trivial and adds Phase 3 scope risk. BUG-02 fix (improving readability) will make the context menu path fully usable.

**Phase 4 backlog item:** Implement `StatusDelegate(QItemDelegate)` for the Status column in View Tab, with Paidoff triggering the PaidoffDialog on selection.

---

### PD-R2-07 — BUG-04: Windows Date Picker Click Behavior

**Decision:** Accept fix

**Business Rationale:** User reported that the date picker requires clicking the dropdown arrow rather than the field itself. On Windows, PySide6 `QDateEdit` with `setCalendarPopup(True)` shows a dropdown button but does not open the calendar on field click by default.

**Fix direction:** Implement a `ClickableDateEdit` subclass of `QDateEdit` that overrides `mousePressEvent` to call `self.showPopup()`. Apply this subclass wherever `QDateEdit` is instantiated with calendar popup: `entry_tab.py` (giving_date and due_date fields), `paidoff_dialog.py`, and `extend_dialog.py`. This ensures cross-platform consistency.

---

### PD-R2-08 — DOC-01: Import Parser DD-MM-YYYY

**Decision:** Accept as code fix (not documentation-only)

**Business Rationale:** The sample input documentation shows `giving_date(DD-MM-YYYY)` format. Investigation confirms `import_service._row_to_loan()` calls `date.fromisoformat(giving_raw)` which only handles ISO format (YYYY-MM-DD). A DD-MM-YYYY input will raise `ValueError` and cause the row to be skipped silently. This is a real data import bug.

**Fix direction:** Add `_parse_flexible_date(s: str) -> Optional[date]` helper in `import_service.py`:
- First try `date.fromisoformat(s)` (handles YYYY-MM-DD)
- On `ValueError`, try `datetime.strptime(s, "%d-%m-%Y").date()` (handles DD-MM-YYYY)
- On second failure, return `None` and log a WARNING
- Apply to both `giving_date` and `due_date` fields in `_row_to_loan()`

**Storage remains ISO 8601 (R8):** Input parsing is flexible; internal storage and all date-to-string conversions remain `date.isoformat()`.

---

## 2. Open Business Clarifications (requiring user input)

| ID | Item | Impact | Priority |
|---|---|---|---|
| BC-02 | View Tab color palette — user to confirm acceptable color scheme for BUG-02 fix before prototype sign-off | Visual UX only; does not block implementation | Low — can fix then confirm |
| BC-03 | Phase 4 scope: R6 import/export full date hierarchy filter vs R9 theme chooser — which is Phase 4 primary focus? | Sprint planning for Phase 4 cannot be committed without this | Medium |
| BC-04 | QComboBox Status delegate for Paidoff (BUG-03 full fix) — is this required for prototype UAT or acceptable as Phase 4 item? | Affects whether Phase 3 is UAT-ready for Paidoff via UI toggle | High |

---

## 3. PO TLDR (Wave 3 Synthesis)

*This section is populated after all Wave 1 and Wave 2 agents complete.*

### Product Summary

Loan Manager is a single-user PySide6 desktop application for managing personal loan records. It provides loan entry with automatic reference ID generation, a sortable/filterable View Tab with inline editing, an Interest Calculator (Monthly/Daily/Both modes), a Pending Approval queue for batch-extend reports, CSV import/export, and cross-platform launchers for Windows and Mac. All data is stored in local CSV files.

Run_2 closes the Phase 3 gap: 4 user-reported defects (filter reset, color palette, paidoff flow, date picker) and 2 new requirements (No Due Date default, Paidoff interest report generation) plus 1 discovered import parser bug.

### Phase Recommendation

| Phase | Status | Scope |
|---|---|---|
| Phase 1 — Core Data Foundation | Complete (run_1) | Entry, View, Status, Paidoff, Ref IDs, launchers |
| Phase 2 — Interest Calculator and Pending Approval | Complete (run_1) | Calculator (3 modes), Pending Approval queue, report CRUD |
| Phase 3 — Bug Fixes + R1/R3 Changes | In progress (run_2) | CHG-01, CHG-02, BUG-01–04, DOC-01, CHG-03 verification |
| Phase 4 — Import/Export + UI Polish | Planned | R6 (full import/export with date hierarchy filter), R9 (theme chooser), QComboBox Status delegate, user guide update |

### PO Decisions Issued This Run

| ID | Item | Decision | Rationale |
|---|---|---|---|
| PD-R2-01 | CHG-01 No Due Date default | Accept | R1 explicit requirement; was a run_1 code defect |
| PD-R2-02 | CHG-02 Paidoff generates report | Accept; BC-01 resolved as 0 days for early payoff | R3 explicit; uses existing infrastructure |
| PD-R2-03 | CHG-03 Python version check mandatory | Accept — already implemented | R10 priority elevation; code already correct |
| PD-R2-04 | BUG-01 Filter reset fix | Accept | User-reported P1 defect with confirmed root cause |
| PD-R2-05 | BUG-02 Color palette fix | Accept fix; palette to be confirmed by user | User-reported P1 defect; BC-02 for palette preference |
| PD-R2-06 | BUG-03 Paidoff context menu | Accept partial; QComboBox deferred to Phase 4 | Context menu path works; QComboBox is Phase 4 scope |
| PD-R2-07 | BUG-04 Windows date picker | Accept | User-reported P2 defect; ClickableDateEdit subclass fix |
| PD-R2-08 | DOC-01 Import parser DD-MM-YYYY | Accept as code fix | Confirmed bug: fromisoformat() rejects DD-MM-YYYY |

### Where User Clarity is Required (Priority Order)

1. **BC-04** [HIGH] — Is the QComboBox Status delegate for Paidoff required for prototype UAT, or is the context menu path acceptable? If the user cannot mark a loan as Paidoff via the UI without this, Phase 3 UAT cannot be signed off until resolved. Context menu right-click IS available but may not be obvious to end users.

2. **BC-01** [RESOLVED by PD-R2-02] — Early paidoff (paidoff_date < due_date) yields 0 days extension_period. PO decision issued. No user action required unless the business uses a different convention.

3. **BC-02** [LOW] — Color palette confirmation after BUG-02 fix is deployed. Implementation can proceed with the recommended dark palette; user reviews and confirms at UAT.

4. **BC-03** [MEDIUM] — Phase 4 scope ordering: R6 import/export full date hierarchy vs R9 themes. User to confirm before Phase 4 sprint planning begins.
