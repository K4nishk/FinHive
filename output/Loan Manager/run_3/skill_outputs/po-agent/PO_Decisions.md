# PO Decisions — Loan Manager run_3
**Run:** run_3, Wave 0 Initial + Wave 3 Synthesis
**Date:** 2026-04-03
**Author:** Product Owner Agent

---

## 1. Wave 0 Binding PO Decisions (Pre-Agent Unblocking)

These decisions are issued before Wave 1/2 agents begin work to eliminate downstream blockers resolvable from REQUIREMENTS.md.

---

### PD-R3-01 — CHG-02-EXT: Paidoff Dialog Rate Fields

**Decision:** Accept

**Business Rationale:** R3 explicitly states: "the dialog box should also ask for `interest_rate`, `commission_rate` and `tds_flag` values to generate appropriate calculation report." This removes the BC-05 ambiguity from run_2 (global defaults vs per-event values). Per-event entry is now the authoritative behaviour.

**Scope Impact:**
- `PaidoffDialog` must add 3 new fields: `interest_rate` (QDoubleSpinBox), `commission_rate` (QDoubleSpinBox), `tds_flag` (QCheckBox, default false)
- `_action_paidoff()` reads and passes these values
- `_generate_paidoff_report()` uses per-event values (not hardcoded 12.0/2.0/False)
- No schema changes (confirmed by DM)

**BC-04 Resolution (run_2 open item):** Resolved. R3 text "A toggle option to `Mark Paidoff` when Right Click on the record" confirms right-click context menu is the accepted UX path. QComboBox Status delegate remains deferred to Phase 4.

**BC-05 Resolution (run_2 open item):** Resolved. Per-event rate entry via dialog is confirmed.

---

### PD-R3-02 — CHG-02-EXT: Paidoff Warning Message

**Decision:** Accept — exact text specified; placement is BC-301

**Business Rationale:** R3 specifies the exact warning: "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied." The text is authoritative and must appear exactly.

**Implementation direction:** Display as a passive UI label in the Pending Approval Tab when a Paidoff-mode report is selected. The `mode="Paidoff"` convention (DM ruling) enables detection. Exact widget placement is BC-301 (user to confirm or accept default).

**Default placement (if user does not respond):** Below report header, above records table.

---

### PD-R3-03 — mode="Paidoff" Reserved String (TC-301)

**Decision:** Accept SA/DM ruling

**Business Rationale:** SA proposed and DM confirmed: use `mode="Paidoff"` as a reserved mode string in `pending_reports.csv`. This requires no schema migration, no `PENDING_REPORT_FIELDNAMES` change, and no `PendingReport` dataclass change. The `mode` field is untyped STRING at storage level.

**Risk:** The Pending Approval Tab UI code that handles mode strings must be updated to handle `"Paidoff"` without crashing. Mode="Paidoff" reports should NOT attempt to process extension dates since `new_giving_date` and `new_due_date` will be `None`.

**[REVIEW REQUIRED — TC-304]:** Does the Pending Approval Tab approval handler currently guard against None `new_giving_date`/`new_due_date` when approving? If it blindly attempts to update loan dates from report records, a Paidoff report approval would fail or corrupt data. Backend dev must verify and add a guard: if `report.mode == "Paidoff"`, the approval handler should skip the date-update step (the loan is already in history — no update needed).

---

### PD-R3-04 — BUG-02-REF: Exact Color Codes

**Decision:** Accept — BC-02 resolved

**Business Rationale:** User has provided exact hex codes in requirements (UT-R1 section). BC-02 from run_2 is resolved. No further user confirmation required for the color palette.

**Exact colors (authoritative):**
- Active: `#2d6a4f` (dark green) with white text
- Overdue: `#9b2226` (dark red) with white text
- Pending: `#ca6702` (dark amber) with white text
- Paidoff: `#495057` (dark grey) with white text

---

### PD-R3-05 — BUG-03 and Priority Section Removal

**Decision:** Accept removal — no action required

**Business Rationale:** BUG-03 ("User was unable to test out marking a record as Paidoff") is subsumed by the CHG-02 Paidoff flow. With CHG-02-EXT fully specifying the right-click → dialog → report flow, there is no separate bug to fix. Priority section removal is documentation hygiene only.

---

### PD-R3-06 — TC-302 Resolution

**Decision:** Accept — resolved by source code verification

**Business Rationale:** `data/report_manager.py` confirmed to exist with correct adapter function signatures: `generate_report_id(report_date: date)`, `write_report(report: PendingReport)`, `write_report_records(records: list[ReportRecord])`. TC-302 is closed.

---

## 2. Open Items (requiring user input or further dev verification)

| ID | Item | Impact | Priority |
|---|---|---|---|
| BC-301 | Paidoff warning message placement in Pending Approval Tab | UX only — implementation defaults to below report header | Low |
| BC-03 | Phase 4 scope: R6 import/export vs R9 themes vs QComboBox StatusDelegate | Phase 4 sprint planning cannot start without this | Medium |
| TC-304 | Pending Approval Tab approval handler — does it guard against None new_giving_date/new_due_date for mode="Paidoff" reports? | Data integrity risk if not guarded — Paidoff reports should not update loan dates | High |

---

## 3. PO TLDR (Wave 3 Synthesis)

*Populated after all Wave 1 and Wave 2 agents complete.*

### Product Summary

Loan Manager is a single-user PySide6 desktop application for managing personal loan records. It provides loan entry with auto-reference IDs, a sortable/filterable View Tab with inline editing, an Interest Calculator (Monthly/Daily/Both modes), a Pending Approval queue for batch-extend reports, CSV import/export, and cross-platform launchers for Windows and Mac. All data resides in local CSV files.

Run_3 (MVP Closure) closes the final two outstanding items from Phase 3: the extended Paidoff dialog (CHG-02-EXT, implementing the user-specified rate fields and exact warning message) and the refined status colors (BUG-02-REF, applying the user-specified dark palette with white text). BC-04, BC-05, and BC-02 from run_2 are all resolved by the new requirements. The prototype is functionally complete for Phase 3 after these 2 items are implemented.

### Phase Recommendation

| Phase | Status | Scope |
|---|---|---|
| Phase 1 — Core Data Foundation | Complete (run_1) | Entry, View, Status, Paidoff, Ref IDs, launchers |
| Phase 2 — Interest Calculator and Pending Approval | Complete (run_1) | Calculator (3 modes), Pending Approval queue, report CRUD |
| Phase 3 — Bug Fixes + R1/R3 Changes | MVP Closure (run_3) | CHG-01, CHG-02, CHG-02-EXT, BUG-01, BUG-02-REF, BUG-04, DOC-01, CHG-03 verification |
| Phase 4 — Import/Export + UI Polish | Planned | R6 (full import/export with date hierarchy filter), R9 (theme chooser), QComboBox Status delegate, user guide update |

### PO Decisions Issued This Run

| ID | Item | Decision | Rationale |
|---|---|---|---|
| PD-R3-01 | CHG-02-EXT Paidoff dialog rate fields | Accept | R3 explicit; BC-04 and BC-05 from run_2 resolved |
| PD-R3-02 | Paidoff warning message exact text | Accept; placement is BC-301 | R3 exact text specified; default placement: below report header |
| PD-R3-03 | mode="Paidoff" reserved string | Accept SA/DM ruling | No schema change; zero migration risk |
| PD-R3-04 | BUG-02-REF exact color codes | Accept; BC-02 resolved | User provided exact hex values in requirements |
| PD-R3-05 | BUG-03 removal and priority doc cleanup | Accept removal | BUG-03 subsumed by CHG-02 flow; doc-only removal |
| PD-R3-06 | TC-302 data/report_manager.py existence | Resolved by source verification | Adapter shim confirmed present |

### Where User Clarity is Required (Priority Order)

1. **TC-304** [HIGH] — Does the Pending Approval Tab approval handler guard against None `new_giving_date`/`new_due_date` for `mode="Paidoff"` reports? If not, approving a Paidoff report would attempt to update loan dates for a loan already archived in history.csv — creating a data integrity failure. Backend dev must read `pending_approval_tab.py` approval logic and add a guard if absent. This is the highest-priority item to resolve before the prototype is shipped.

2. **BC-301** [LOW] — Where exactly in the Pending Approval Tab should the Paidoff warning label appear? Options: (a) below report header above records table (default), (b) inline with the report row in the list, (c) as a tooltip. If user does not respond, implementation proceeds with option (a). No blocking impact.

3. **BC-03** [MEDIUM] — Phase 4 primary focus: R6 import/export full date hierarchy vs R9 theme chooser vs QComboBox Status delegate. User input required before Phase 4 sprint planning begins. Does not block run_3 delivery.

