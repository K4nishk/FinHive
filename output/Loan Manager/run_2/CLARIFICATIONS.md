# CLARIFICATIONS — Loan Manager run_2
**Date:** 2026-04-03
**Run:** run_2 (Phase 3 closure)
**Author:** Loop Operator (Wave 3 PO Synthesis)
**Status:** Final — all [REVIEW REQUIRED] items consolidated and deduplicated from 9 agent outputs

---

## Technical Clarifications

These items require user or developer input to unblock implementation or resolve architectural ambiguity.

---

### TC-01 — Paidoff Report Approval Warning Copy Update

**Source:** SA-agent (ADR-002)
**Status:** Recommended for Phase 3 in-scope

**Issue:** When a Paidoff report in the Pending Approval tab is approved, the existing `batch_extend_loans()` logic looks for the loan in `loans.csv`. Because `mark_paidoff()` has already moved the loan to `history.csv`, the approval flow triggers the existing "Records in this report have been deleted" warning dialog. This is architecturally expected (the loan is gone from loans.csv — it moved to history.csv) but is confusing to a user who sees an "error" warning when approving a report they just created.

**Options:**
1. Update the warning message copy in `pending_approval_tab.py` to distinguish Paidoff reports from genuinely-deleted extension reports (Phase 3 — one-line copy change). e.g.: "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied."
2. Introduce a `report_type` column in `pending_reports.csv` and branch the approval logic (`extension` vs `paidoff`). Paidoff reports use "Acknowledge" flow. (Phase 4 — schema + logic change)

**PO recommendation:** Option 1 for Phase 3 (copy update only). Option 2 for Phase 4.

**User action required:** Confirm Option 1 is acceptable for Phase 3 UAT, or if the "Acknowledge" flow is needed before sign-off.

---

### TC-02 — Startup Resilience for Missing Meta CSV Files

**Source:** SRE-agent
**Status:** Phase 3 regression verification

**Issue:** If `loans_meta.csv` or `reports_meta.csv` are absent (first run on a new machine, or files manually deleted), `generate_ref_id()` and `generate_report_id()` may raise an unhandled exception rather than recreating the files with seed values.

**User action required:** None (developer verification item). Backend QA test scenarios BE (TC-02a, TC-02b) cover this. No user decision needed — flagged for developer awareness.

---

## Business Clarifications

Items requiring user decision before Phase 4 sprint planning or prototype sign-off.

---

### BC-02 — View Tab Color Palette Confirmation

**Source:** PO-agent (PD-R2-05), SA-agent
**Status:** Implementation can proceed; user to confirm at prototype UAT

**Context:** BUG-02 (unreadable row colors) is being fixed with a high-contrast dark palette:
- Active: dark green (#2d6a4f) with white text
- Overdue: dark red (#9b2226) with white text
- Pending: dark amber (#ca6702) with white text
- Paidoff: dark grey (#495057) with white text

**User action required:** Review the colors at prototype UAT and confirm acceptability. If you prefer different shades or a different design approach (e.g., colored text on white background), flag at UAT review. This is a low-risk change to iterate on.

---

### BC-04 — QComboBox Status Delegate for Paidoff (Scope Gate)

**Source:** PO-agent, BSA-agent, SA-agent
**Status:** HIGH priority — gate for Phase 3 UAT sign-off

**Context:** R3 states "User can toggle in between these states for any record in the tab. Leverage QComboBox for simplicity." The current implementation does NOT have a QComboBox in the Status column. The right-click context menu path ("Mark Paidoff") is available and functional.

The PO deferred the QComboBox Status delegate to Phase 4 (PD-R2-06), citing non-trivial `QItemDelegate` implementation risk for Phase 3. The context menu path works but may not be obvious to end users.

**User action required:** Answer one of the following:
- **Option A:** The right-click context menu path ("Mark Paidoff") is sufficient for Phase 3 prototype UAT sign-off. QComboBox delegate moves to Phase 4.
- **Option B:** The QComboBox Status delegate is required for prototype UAT. Phase 3 scope expands to include `StatusDelegate(QItemDelegate)` implementation. This adds approximately 2–3 dev-days and Phase 3 UAT cannot be signed off without it.

**This is the highest-priority open item for Phase 4 kickoff.**

---

### BC-05 — Interest Rate at Paidoff Time

**Source:** BSA-agent (BC-05), DM-agent (DM-R01), Backend Dev-agent
**Status:** Pending PO decision — affects CHG-02 implementation

**Context:** When a Paidoff interest report is generated automatically (CHG-02), the report uses global default rates: `interest_rate = 12.0%`, `commission_rate = 2.0%`, `tds_flag = False`. The Loan model does not store per-loan rates, so there is no alternative source for these values.

**Options:**
1. **Use global defaults** (current implementation) — simple, consistent. If all loans use the same rate, this is correct. A TODO comment in code marks BC-05 pending.
2. **Prompt user for rates at Paidoff time** — extend PaidoffDialog to collect `interest_rate`, `commission_rate`, `tds_flag`. Adds one form step to the Paidoff workflow. Requires PaidoffDialog UI change (~1 dev-day).
3. **Store rates per loan** — add `interest_rate` and `commission_rate` columns to loans.csv (schema change). All loans carry their rates and the Paidoff report uses them automatically. This is a schema change (Phase 4 scope minimum).

**User action required:** Which option is correct for your business? Do all loans in practice use the same 12%/2% rate, or do rates vary? This determines whether Option 1 is acceptable or Option 2/3 is needed.

---

### BC-06 — Paidoff Report Approval Flow (Semantic Conflict)

**Source:** BSA-agent, SA-agent (ADR-002), DM-agent (DM-R02)
**Status:** Phase 4 architectural item — user to acknowledge

**Context:** When a Paidoff report is approved in the Pending Approval tab, the approval calls `batch_extend_loans()` which looks for the loan in `loans.csv`. The Paidoff loan has already been moved to `history.csv` by `mark_paidoff()`. The approval will therefore trigger the "Records in this report have been deleted" warning (existing warning path). The loan is NOT extended (it is already Paidoff). The report approval has no meaningful effect on loan data.

**Phase 3 mitigation:** TC-01 copy update distinguishes this expected warning from a real error.

**Phase 4 full fix:** Introduce `report_type = "paidoff"` vs `report_type = "extension"` in `pending_reports.csv` schema. The approval flow branches: Paidoff reports show an "Acknowledge" button (no `batch_extend_loans()` call); extension reports use the existing approval flow.

**User action required:** Acknowledge this known limitation for Phase 3. Confirm whether Phase 4 approval flow branching is a priority (it would move to the Phase 4 backlog alongside R6, R9, and the QComboBox delegate).

---

### BC-03 — Phase 4 Scope Ordering

**Source:** PM-agent (PROJECT_CHARTER.md), PO-agent
**Status:** Phase 4 sprint planning gate

**Context:** Two Phase 4 requirements are competing for priority:
- **R6** — Full import/export with date hierarchy filter (complex feature — ~5 dev-days)
- **R9** — Theme chooser (cosmetic feature — ~2 dev-days)

Additional Phase 4 backlog items discovered in run_2:
- QComboBox Status delegate (BC-04 — if required)
- Paidoff report approval flow (BC-06 full fix)
- Atomic writes for report CSV files (SRE recommendation)

**User action required:** Before Phase 4 sprint planning, confirm:
1. Is R6 (import/export date filter) the primary Phase 4 focus, or is R9 (themes) first?
2. Which of the run_2 discovered backlog items (BC-04, BC-06, atomic report writes) should be included in Phase 4 vs deferred further?

---

## PO TLDR

### Product Summary

Loan Manager is a single-user PySide6 desktop application for managing personal loan records with CSV file storage. It provides loan entry and auto-reference-ID generation, a sortable/filterable View Tab with status colour coding, an Interest Calculator (Monthly/Daily/Both modes), a Pending Approval queue for interest report review, CSV import with conflict detection, and cross-platform launchers for Windows and Mac.

Phase 3 (run_2) delivers: 4 user-reported bug fixes (filter reset, unreadable colors, Paidoff marking flow, Windows date picker), 2 new requirements (No Due Date default pre-checked, Paidoff auto-generates Daily interest report), and 1 discovered import parser bug (DD-MM-YYYY date format support). Python version check was previously confirmed as already implemented. No database schema changes required.

### Phase Status

| Phase | Status | Scope |
|---|---|---|
| Phase 1 — Core Data Foundation | Complete (run_1) | Entry, View, Status, Paidoff, Ref IDs, launchers |
| Phase 2 — Interest Calculator and Pending Approval | Complete (run_1) | Calculator (3 modes), Pending Approval queue, report CRUD |
| Phase 3 — Bug Fixes + R1/R3 Changes | Prototype ready (run_2) | CHG-01, CHG-02, BUG-01–04, DOC-01, CHG-03 verification |
| Phase 4 — Import/Export + UI Polish | Planned | R6 (full import/export), R9 (theme chooser), QComboBox Status delegate, Paidoff approval flow, per-loan rates |

### PO Decisions Issued This Run

| ID | Item | Decision |
|---|---|---|
| PD-R2-01 | CHG-01 No Due Date default | Accept — code fix confirmed |
| PD-R2-02 | CHG-02 Paidoff generates report (BC-01 early payoff) | Accept; early payoff clamps extension to 0 |
| PD-R2-03 | CHG-03 Python version check mandatory | Accept — already implemented, verification only |
| PD-R2-04 | BUG-01 Filter reset fix | Accept — root cause confirmed |
| PD-R2-05 | BUG-02 Color palette fix | Accept; palette to be confirmed by user at UAT (BC-02) |
| PD-R2-06 | BUG-03 Paidoff context menu | Accept partial; QComboBox deferred to Phase 4 |
| PD-R2-07 | BUG-04 Windows date picker | Accept — ClickableDateEdit subclass |
| PD-R2-08 | DOC-01 Import parser DD-MM-YYYY | Accept as code fix — _parse_flexible_date() helper |

### Open Items Requiring User Action (Priority Order)

1. **BC-04** [HIGH — Phase 3 gate] Is the right-click context menu sufficient for Paidoff in Phase 3 UAT, or is the QComboBox Status delegate required? Answer determines whether Phase 3 can be signed off as-is.

2. **BC-05** [MEDIUM — CHG-02 implementation] Are global defaults (12%/2%) acceptable for Paidoff report interest rates, or should the user supply rates at Paidoff time? Affects PaidoffDialog scope.

3. **TC-01** [MEDIUM — Phase 3 UX] Confirm that a copy-only update to the Paidoff report approval warning message is acceptable for Phase 3 (rather than a full "Acknowledge" flow split).

4. **BC-06** [LOW — acknowledged] The Paidoff report approval "deleted records" warning is expected and not an error. Acknowledge as a known Phase 3 limitation. Full fix in Phase 4.

5. **BC-02** [LOW — confirm at UAT] Review the dark color palette at prototype UAT and confirm or request adjustments.

6. **BC-03** [MEDIUM — before Phase 4 kickoff] Confirm Phase 4 scope priority: R6 (import/export) vs R9 (themes) vs BC-04 QComboBox vs BC-06 approval flow.
