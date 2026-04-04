# PO Decisions — Loan Manager
**Run**: run_1, Wave 0
**Date**: 2026-04-03
**Author**: Product Owner Agent

---

## 1. Product Vision Statement

Build a single-user, desktop-based Loan Management application (PySide6, CSV-backed) that enables a Windows end-user and a Mac OS tester to record, view, modify, and interest-calculate personal loan entries with a professional spreadsheet-like UI — delivered as a prototype that covers all core workflows across entry, modification, interest calculation, and report approval.

### Objectives
- Enable accurate recording and lifecycle management of loan records (entry, extension, paidoff, deletion).
- Provide a configurable interest calculator (Monthly / Daily / Both) with a batch approval workflow.
- Support CSV import/export for historical data and cross-platform (Windows + Mac) execution with minimal setup.

### Success Metrics
- All 15 sample records load, display, and are sortable/filterable without error.
- Interest calculation output matches formula spec for all three modes on sample data.
- Paidoff flow writes to history.csv and removes record from loans.csv atomically (crash-recovery file present).
- Prototype runs on Windows via `run_windows.bat` and on Mac via `run_mac.sh` with zero manual dependency resolution beyond Python 3.10+.
- All four User-Testing Requirement 1 bugs are reproduced and fixed before prototype sign-off.

### In Scope
- R1: Loan entry with calendar widget, autocomplete, reference ID, status bar.
- R2: View tab with column sorting, inline Unknown defaults, full column template.
- R3: Record modification, status lifecycle (Active / Overdue / Paidoff / Pending), atomic Paidoff write with recovery file, inline edit.
- R4: Reference ID generation (YYYY_MM_<order>), Delete, Extend, collision handling, loans_meta.csv counter.
- R5: Interest Calculator tab (Monthly / Daily / Both), Pending Approval tab, two-file normalised report storage, duplicate reference_id warning, batch approval, inline editable report records.
- R6: Excel-like column filtering (year > month hierarchy for dates), CSV/XLSX export, CSV/XLSX import with preview dialog and upsert logic.
- R7: Windows packaging, sample data (developer only), app.log.
- R8: PySide6 framework, .bat and .sh launchers, CSV storage, ISO 8601 dates.
- R9: Modern/professional UI with alternate theme choices.
- R10: User guide under `/src/Loan Manager/user_guides/`, Python version check in both launchers, batch write optimisation on startup.
- User-Testing Requirement 1: All 4 reported bugs fixed.

### Out of Scope
- Database backend (SQLite or otherwise) — explicitly deferred by R8.
- In-app Paidoff history view — explicitly excluded by R3.
- Timestamped backup copy of loans.csv before destructive operations — deferred per R3 (meaningful risk, prototype deferral confirmed).
- "Fill all rows / copy down" shortcut in Interest Calculator — deferred per R5.
- CSV file locking for concurrent sessions — explicitly excluded by R8.
- Network/cloud sync between Windows and Mac users (CSV shared via git per Usage Scope).
- Multi-user authentication or role management.

### Stakeholders
- Primary end-user: Windows single-system user (loan record operator).
- Secondary user / tester: Mac OS single-system user (git manager, QA bridge).

---

## 2. Priority Ruling

Stated priority order from REQUIREMENTS.md:
**R5 > R4 > R1 > R2 > R3 > R6 > R8 > R7 > R10 > R9**

This order is confirmed as binding. Rationale per requirement:

| Rank | Req | Rationale |
|------|-----|-----------|
| 1 | R5 | The Interest Calculator and Pending Approval workflow is the primary value-generating feature of the application. Without it the product has no differentiating purpose. Filtering, calculation modes, batch report approval, and the two-file normalised storage are all mission-critical paths. Highest delivery priority. |
| 2 | R4 | Reference ID generation and the Extend / Delete operations underpin data integrity across the entire system. R5 depends on stable reference IDs. Must be solid before any UI layer is finalised. |
| 3 | R1 | Loan entry is the data ingestion point. Without it, nothing exists to view or calculate. Ranked third because R4's ID scheme must be established first. |
| 4 | R2 | The View tab is the primary data-browsing surface. Depends on R1 data existing and R4 IDs being stable. |
| 5 | R3 | Record modification and the full status lifecycle (including atomic Paidoff write) depend on R1, R2, and R4 being functional. The crash-recovery file requirement makes this non-trivial and warrants its lower rank in delivery sequence. |
| 6 | R6 | Import/export and advanced column filtering add significant usability but are not blocking for core workflows. Excel-like date hierarchy filter and XLSX support are valued but come after core CRUD and calculations are stable. |
| 7 | R8 | Framework choice (PySide6), launcher scripts, and CSV storage are architectural foundations confirmed early, but because they are scaffolding decisions rather than feature deliveries they rank below the functional requirements. |
| 8 | R7 | Windows packaging and the developer sample data setup are delivery-time concerns. Important for handoff but do not affect functional correctness during development. |
| 9 | R10 | User guide and batch write optimisation are post-feature documentation and performance work. Valuable but non-blocking. |
| 10 | R9 | Theme and aesthetic polish is the last concern. Functionality must be proven before UI refinement investment is justified. |

---

## 3. Scope Decisions on Key Ambiguities

### a. Prototype Phase Scope

**Decision: ACCEPT with phased breakdown as follows.**

Based on REQUIREMENTS.md and the "Prototype - Phase estimates" section (which requests the PO/team to define phases), the following binding phase split applies for the prototype:

**Phase 1 — Core CRUD and ID Infrastructure (R4, R1, R2)**
- Reference ID generation, loans_meta.csv counter, collision handling.
- Loan entry form (R1) with calendar widget, autocomplete, status bar message.
- View tab (R2) with full column template, sorting, inline Unknown defaults.

**Phase 2 — Record Lifecycle and Modification (R3, partial R5)**
- Status lifecycle: Active, Overdue, Pending, Paidoff.
- Atomic Paidoff write with crash-recovery temp file.
- Extend (R4, linked from R3 status transitions).
- Interest Calculator tab: Monthly and Daily modes, filtering, inline editable records, calculate button, Generate Report button gated behind Calculate (R5).

**Phase 3 — Approval Workflow and Import/Export (R5 completion, R6)**
- Pending Approval tab: two-file normalised storage, inline edit with auto-recalculation, approve/decline, duplicate reference_id warning, deleted-record warning.
- Both mode for Interest Calculator.
- CSV/XLSX import with preview dialog and upsert logic (R6).
- CSV/XLSX export (R6).
- Excel-like column filtering with year > month > date hierarchy (R6).

**Phase 4 — Packaging, Guides, Polish (R7, R8, R10, R9)**
- .bat and .sh launchers, Python version check, virtual env setup.
- User guides under `/src/Loan Manager/user_guides/`.
- Batch write optimisation on startup (R10).
- Theme options / UI polish (R9).
- All four User-Testing Requirement 1 bugs fixed and verified (required before prototype sign-off).

All phases are in scope for the prototype. No requirements are deferred beyond the prototype except the two items called out explicitly in the requirements (backup copy, fill-all shortcut — see 3e and 3f below).

### b. Mac OS Support

**Decision: ACCEPT — Mac OS is equally in scope as Windows.**

The Usage Scope section explicitly states: "Single-System Human-in-the-loop Product i.e. Loan Manager Tester (Mac OS)" and confirms "application should run on both Windows and Mac OS." R8 mandates both a `.bat` file for Windows and "a similar simple executable for Mac." R10 mandates user guides for both platforms. Mac support is a first-class requirement, not an afterthought. The CSV-sharing mechanism between the two users is git (per Usage Scope). Cross-platform packaging must be validated on both operating systems before prototype sign-off.

### c. User-Testing Requirement 1 — All 4 Bugs Must Be Fixed in Prototype

**Decision: ACCEPT — all 4 reported bugs are mandatory fixes for prototype sign-off.**

User-Testing Requirement 1 is an explicit, named requirement section in REQUIREMENTS.md. None of the four items are marked as deferred or optional. The bugs are:
1. Interest Calculator filter (BorrowerGroup, BorrowerName, DepositorName, DepositorGroup) reverts to "All" — must be fixed.
2. View Tab color palette — light colors with white text are not clearly visible — must be fixed.
3. Marking a record as Paidoff is non-functional — must be fixed.
4. Date picker for giving_date and due_date on Windows is not triggered on field click — must be fixed.

All four are blocking for prototype user acceptance.

### d. "No In-App View for Paidoff History" — Confirmed Out of Scope

**Decision: ACCEPT — confirmed out of scope.**

R3 states explicitly: "No in-app view for Paidoff history required." Paidoff records are written to history.csv and removed from loans.csv. The only recovery path for a Paidoff record is manual CSV editing followed by import. No UI, no screen, no report view for historical Paidoff records is to be built. This is a binding exclusion.

### e. Backup Copy of loans.csv Before Destructive Operations — Deferred for Prototype

**Decision: ACCEPT — deferred for prototype, must be tracked as a known risk.**

R3 states: "The app should create a timestamped backup copy of loans.csv before any destructive operation (Paidoff/bulk Approve) to reduce the risk of irrecoverable data loss. For prototype scope, this is not required but is a meaningful risk which has to be deferred for future."

Binding decision: timestamped backup copy is NOT to be implemented in the prototype. However, the crash-recovery temp file for atomic Paidoff write IS required in the prototype (R3 specifies this separately and does not mark it as deferred). The backup copy deferral applies only to the full timestamped backup mechanism, not to the crash-safety temp file. Risk must be documented in the user guide.

### f. "Fill All Rows / Copy Down" Shortcut — Deferred Per R5

**Decision: ACCEPT — deferred, not in prototype scope.**

R5 states: "A 'fill all rows' or 'copy down' shortcut is not needed for prototype but a good feature." The default behaviour (global values pre-filled on all filtered records) is sufficient for the prototype given the expected post-filtering record count does not exceed 10. The shortcut feature is deferred to a future release.

### g. Authoritative Interest Calculation: Time = extension_period ONLY (not original tenure)

**Decision: ACCEPT — this is the definitive and authoritative interpretation. All implementations must conform.**

R5 states explicitly: "giving_date is only a reference column and is not included in any kind of time-period calculations. i.e. For a Rs 10,000 loan at 12% interest with 3-month original term + 1-month extension: Charge extension window only = Rs 100. This is a core calculation change and an authoritative decision, if the previous implementation defers from this. Re-write the logic and tests to adapt."

Binding ruling:
- Time in all interest and commission formulas = `extension_period` (the extension window duration) only.
- Original loan tenure (giving_date to due_date) is never included in the calculation.
- giving_date is a reference/display column with zero computational weight.
- For Paidoff calculations: `extension_period (days) = paidoff_date - due_date` per R3, used in the Daily mode formula.
- Any prior implementation that used original tenure must be fully rewritten. Tests must be updated accordingly.

Formulas (confirmed authoritative):
- Monthly: `Interest = (Amount * interest_rate * extension_period) / (12 * 100)`
- Daily: `Interest = (Amount * interest_rate * extension_period) / (365 * 100)`
- Commission follows the same formula structure substituting commission_rate for interest_rate.
- TDS (when TDS_flag = true): `TDS = 0.1 * Interest`

---

## 4. Open Questions for User Clarity

| ID | Question | Why it blocks delivery |
|----|----------|------------------------|
| BC-01 | When a loan has no due_date and no giving_date context, R7 states "assume it is overdue" — but R3 states "When no due_date given, loan with future giving_date > today, status = Pending." These two rules conflict for the specific case of a no-due_date loan where giving_date <= today. Should a loan with giving_date <= today and no due_date always default to Overdue, or should it remain Active until the user sets a due_date? | Status auto-recompute on launch (R3) will behave differently depending on the ruling. Test cases and the recompute function cannot be finalised without this. |
| BC-02 | R5 specifies for Mode = Both: "extension_period_unit and extension_period have to be entered on a per-record basis." However, it also states "User enters global interest_rate, commission_rate, extension_period_unit and extension_period values to be applied by default on all filtered records." Does "per-record basis" mean the global defaults are pre-filled but overridable per record (inline edit), or does it mean no global defaults apply for extension_period and extension_period_unit in Both mode? | Determines whether the Both mode UI renders a global extension_period input row or forces per-cell entry from the start. |
| BC-03 | R5 states "When the global header values change, the system overwrites all rows (including manually-edited rows)." Does this apply to extension_period and extension_period_unit in Both mode, or only to interest_rate and commission_rate? A strict reading would reset per-record extension values on any global change, which may be undesirable in Both mode. | Directly affects the inline edit / global overwrite interaction for Both mode. Incorrect behaviour here will corrupt report calculations. |
| BC-04 | R6 states "CSV data files should reside in a fixed ./data/ subfolder" but R1 states "Entries are stored in a data folder (./app/output/data/YYYY/) for as loans.csv." These two paths are inconsistent. Which path is canonical for loans.csv storage? | Build scaffolding, launcher scripts, and import/export logic all depend on the authoritative file path. |
| BC-05 | R4 states reference_id format is YYYY_MM_<order> where "YYYY and MM are current year and month for the data entry." For the Extend operation, the record reuses its existing reference_id. If a loan was created in 2026_03 and is extended in 2026_06, does the reference_id remain 2026_03_001 (original creation date) or does it get a new 2026_06_xxx ID? R4 and R5 both say "reference_ids are reused" and "Overwrites the existing record" — this implies original ID is preserved. Confirm this is the definitive rule. | Reference ID counter logic in loans_meta.csv and the Extend handler must behave consistently with this ruling. [REVIEW REQUIRED] |
| BC-06 | R2 states "User can toggle in between these states for any record in the tab" using QComboBox for Status, and R3 states "The app auto-recomputes status on every app launch (overriding any manual toggle)." If a user manually sets a loan to Active (with a new due_date via the Extend-equivalent prompt), will the auto-recompute on next launch evaluate against the new due_date (preserving Active) or the original due_date (potentially reverting to Overdue)? R3 does state "Manual Active override always prompts for a new due date ... recompute evaluates against that new due date — never silently reverting to Overdue" — this appears to answer the question, but the storage update path for the new due_date must be confirmed as persisted to loans.csv before recompute runs. | If due_date is not persisted before recompute, the Active override will silently revert. Needs explicit confirmation in the storage write sequence spec. |
| BC-07 | The report format per borrower (R5) groups records by borrower. In the Pending Approval tab, are reports displayed and approved at the report level (one approval covers all borrowers in the report) or at the borrower-group level within a report? | Affects the approval UI layout and the approve/decline handler logic. |
| BC-08 | R10 mentions "Adding batch write option to avoid O(N^2) write operations on startup." What specific operation on startup is O(N^2)? Is this referring to the status auto-recompute writing each record individually, or another operation? Clarification needed to implement the correct optimisation. | Without knowing the target operation, the batch write optimisation cannot be scoped or implemented correctly. |
