# CLARIFICATIONS — Loan Manager run_3
**Date:** 2026-04-03
**Run:** run_3 (MVP Closure Stage)
**Author:** Loop Operator (orchestrator) + PO Agent (Wave 3 synthesis)

---

## Resolved Items (No User Action Required)

The following run_2 open items are now resolved by the run_3 requirements update. No user input needed.

| ID | Item | Resolution |
|---|---|---|
| BC-04 | Right-click context menu vs QComboBox for Paidoff | Resolved: R3 text confirms right-click ("A toggle option to Mark Paidoff when Right Click on the record") |
| BC-05 | Interest/commission rate source for Paidoff report | Resolved: per-event entry confirmed (dialog collects interest_rate, commission_rate, tds_flag) |
| BC-02 | View Tab color palette confirmation | Resolved: exact hex codes provided in requirements (Active=#2d6a4f, Overdue=#9b2226, Pending=#ca6702, Paidoff=#495057) |
| TC-301 | Paidoff report identification in Pending Approval Tab | Resolved: mode="Paidoff" reserved string adopted (DM ruling — no schema change) |
| TC-302 | data/report_manager.py adapter shim existence | Resolved: shim confirmed present; generate_report_id/write_report/write_report_records verified |
| TC-304 | Pending Approval approval handler guard for None new_giving_date/new_due_date | Resolved: guard already exists (line 619 of pending_approval_tab.py): if rec.new_giving_date is None and rec.new_due_date is None: continue |

---

## Technical Clarifications

Items requiring a developer or architect decision before implementation is complete.

### TC-303 — Read pending_approval_tab.py Before Implementing Warning Label

**Source:** Backend Dev Agent, Backend QA Agent
**Priority:** High
**Description:** The Paidoff warning label (IMPL-5) must be inserted into `pending_approval_tab.py` at the correct location relative to the report header and records table. The file has been read sufficiently to confirm a `QSplitter` layout with a reports list (top) and records detail (bottom). The warning label should be inserted in the bottom panel, above the `QTableWidget` for records. The exact insertion point requires reading the full `_build_detail_panel()` or equivalent method.
**Action Required:** Backend developer must read `pending_approval_tab.py` `_build_ui()` / `_build_detail_panel()` method before implementing IMPL-5 to confirm the correct widget insertion order.
**Impact if deferred:** Warning label may be placed in an invisible or incorrect location.
**Blocking:** Implementation of IMPL-5 (warning label) only. Does not block IMPL-1 to IMPL-4.

---

## Business Clarifications

Items requiring user input before or after implementation.

### BC-301 — Paidoff Warning Label Placement in Pending Approval Tab

**Source:** PM Agent, BSA Agent, Dev Lead Agent, Backend Dev Agent, QA Lead Agent
**Priority:** Low
**Description:** R3 states the warning message "can be displayed" — it does not specify where in the Pending Approval Tab the warning should appear. Three options:

| Option | Description | Recommended |
|---|---|---|
| (a) Below report header, above records table | When a Paidoff report is selected, a highlighted label appears between the report info (ID, date, status) and the records detail table | Yes — default implementation |
| (b) Inline with report row in the list | Warning icon or text appended to the report row entry in the reports list | Not recommended — clutters the list |
| (c) As a tooltip on the report row | Hover tooltip on the Paidoff report row | Not recommended — invisible by default |

**Default action:** If user does not respond, implementation proceeds with option (a) above.
**User question:** Do you accept option (a) as the placement, or do you prefer a different location?
**Impact:** UX only. Wrong placement reduces clarity but does not affect data integrity.

---

### BC-03 — Phase 4 Scope Prioritisation (Carried from run_2)

**Source:** PM Agent, PO Agent
**Priority:** Medium
**Description:** Phase 4 cannot be sprint-planned without knowing which of the following is the primary focus:

| Option | Description | Effort |
|---|---|---|
| A | R6: Full import/export with date hierarchy filter (year→month→date) and .xlsx export | High |
| B | R9: Alternate theme chooser for the application | Medium |
| C | QComboBox StatusDelegate for inline Paidoff toggle in View Tab (deferred from Phase 3) | Medium |
| D | Combination: A + C (skip B) | High |

**User question:** Which items should Phase 4 prioritise? Please rank or select from the options above. If no response, Phase 4 will default to Option A (R6 import/export) as the primary focus, with C as secondary.
**Impact:** Phase 4 sprint planning and resource estimation depend on this decision.

---

## PO TLDR

### Product Summary

Loan Manager is a single-user PySide6 desktop application for managing personal loan records on Windows and Mac. It provides: loan entry with auto-reference IDs, a sortable/filterable View Tab with inline editing and right-click context actions, an Interest Calculator (Monthly/Daily/Both modes), a Pending Approval queue for batch-extend reports, CSV import/export, and cross-platform launchers.

Run_3 (MVP Closure) delivers the final two Phase 3 items: the extended Paidoff dialog (CHG-02-EXT — collecting interest_rate, commission_rate, tds_flag per paidoff event, generating a Daily report with mode="Paidoff" and the exact R3 warning message) and the refined View Tab status colors (BUG-02-REF — applying the user-specified dark palette with white text). Three run_2 open clarifications (BC-02, BC-04, BC-05) are resolved by the new requirements. The prototype is functionally complete for Phase 3 delivery after these items are implemented and tested.

### Phase Recommendation

| Phase | Status | Scope |
|---|---|---|
| Phase 1 — Core Data Foundation | Complete (run_1) | Entry, View, Status, Paidoff, Ref IDs, launchers |
| Phase 2 — Interest Calculator and Pending Approval | Complete (run_1) | Calculator (3 modes), Pending Approval queue, report CRUD |
| Phase 3 — Bug Fixes + R1/R3 Changes | MVP Closure (run_3) | CHG-01, CHG-02, CHG-02-EXT, BUG-01, BUG-02-REF, BUG-04, DOC-01, CHG-03 verification |
| Phase 4 — Import/Export + UI Polish | Planned — BC-03 decision required | R6 import/export with date hierarchy, R9 themes, QComboBox StatusDelegate |

### PO Decisions Issued This Run

| ID | Item | Decision | Rationale |
|---|---|---|---|
| PD-R3-01 | CHG-02-EXT: Paidoff dialog rate fields | Accept | R3 explicit; BC-04 and BC-05 from run_2 resolved |
| PD-R3-02 | Paidoff warning message exact text | Accept; placement is BC-301 | R3 text authoritative; user to confirm placement |
| PD-R3-03 | mode="Paidoff" reserved string in pending_reports.csv | Accept DM/SA ruling | No schema change; zero migration risk |
| PD-R3-04 | BUG-02-REF: exact hex color codes | Accept; BC-02 resolved | User provided exact hex values; no further confirmation needed |
| PD-R3-05 | BUG-03 removal and priority doc cleanup | Accept | BUG-03 subsumed by CHG-02; documentation only |
| PD-R3-06 | TC-302 data/report_manager.py shim | Resolved by source verification | Adapter shim confirmed present and correct |
| PD-R3-07 | TC-304 approval handler None guard | Resolved by source verification | Guard already exists at line 619 of pending_approval_tab.py |

### Where User Clarity is Required (Priority Order)

1. **TC-303** [HIGH — Developer action] — Backend developer must read `pending_approval_tab.py` `_build_ui()` method before implementing the Paidoff warning label (IMPL-5) to identify the correct widget insertion point. This is a dev task, not a user decision.

2. **BC-301** [LOW — User input optional] — Where should the Paidoff warning message appear in the Pending Approval Tab? Default is below the report header, above the records table. If user does not respond, implementation proceeds with the default. No blocking impact.

3. **BC-03** [MEDIUM — User input required before Phase 4] — Phase 4 scope: which items to prioritise (R6 import/export, R9 themes, QComboBox StatusDelegate)? Phase 4 sprint planning cannot begin without this decision. Does not block run_3 or Phase 3 closure.

