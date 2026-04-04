# PM: Project Charter — Loan Manager

**Document Version:** 1.0
**Date:** 2026-04-03
**Run:** run_1 / Wave 0
**Author:** PM Agent

---

## 1. Project Charter

**Business Objective:**
Deliver a desktop Loan Management application that enables a single end-user (Windows) to record, track, extend, and report on personal or small-group loans — replacing manual spreadsheet-based tracking with a structured, auditable PySide6 application.

**Problem Statement:**
The user currently has no structured tool to manage loan entries, track repayment statuses, calculate interest/commissions, and generate approval-ready reports. Manual tracking via spreadsheets is error-prone, lacks status automation, and does not support a repeatable interest-calculation workflow. A Mac OS tester also needs to run the same application to validate and manage CSV data via git, creating a cross-platform requirement.

**Success Metrics:**

| Metric | Target |
|---|---|
| All R1–R10 core features functional and testable | 100% of in-scope requirements pass acceptance criteria |
| User can complete full loan lifecycle (create → extend → paidoff) without data loss | Zero data-loss incidents during UAT |
| Interest calculator produces correct outputs for Monthly, Daily, and Both modes | Calculation outputs match authoritative formulas in R5 |
| Application launches on Windows via `.bat` and on Mac via `.sh` without manual dependency resolution | Both scripts succeed on fresh environments |
| Pending Approval queue persists across restarts | Reports survive app restart |
| User-Testing issues (UT-R1) resolved | All 4 UT-R1 defects closed before prototype sign-off |

---

**Stakeholders:**

| Name / Role | Interest | Engagement Level |
|---|---|---|
| End User (Windows) | Primary consumer — loan entry, status management, report approval | High — daily use, UAT sign-off |
| Mac OS Tester / Bridge User | Cross-platform validation, git-based CSV sharing | Medium — periodic testing, data bridging |
| Developer (Solo) | Implementation, testing, delivery | High — owns all phases |
| PM Agent | Requirements traceability, scope governance | Kick-off and phase reviews |

---

**Constraints:**

- **Budget:** [REVIEW REQUIRED — no budget figure stated in requirements; assumed zero direct cost beyond developer time]
- **Timeline:** [REVIEW REQUIRED — no hard deadline stated; prototype target TBD by end-user; development begins 2026-04-03]
- **Tech Stack Cost:** PySide6 (LGPL, free), CSV storage (no licence cost), Python 3.10+ (free). No database licence required.
- **Scope boundary — explicitly out of scope for prototype:**
  - Multi-user / concurrent session support (R8: no CSV locking needed)
  - Network/cloud CSV sync (Usage Scope: CSV shared via git manually)
  - In-app view for Paidoff loan history (R3: no in-app view required)
  - Timestamped backup before destructive operations — deferred to future phase (R3 notes this explicitly)
  - "Fill all rows / copy down" shortcut in Interest Calculator (R5)
  - Database backend (R8)
  - Production packaging / installer (prototype only)

---

**Assumptions and Risks at Kick-Off:**

| Assumption | Risk if Wrong |
|---|---|
| End user has Python 3.10+ installed on Windows | App fails to launch; mitigation: `run_windows.bat` checks Python version and prints upgrade message (R10) |
| Mac tester shares CSVs via git (no live sync) | Data divergence between Windows and Mac instances; no automated merge — [REVIEW REQUIRED] conflict resolution not defined |
| Max ~1,500 active loan records at any time (R4) | If volume exceeds this, table performance may degrade; PySide6 QTableWidget vs QTableView choice must be documented (R4 architectural note) |
| Loans without a `due_date` are treated as Overdue by the status engine (R7 sample data clarification) | Unexpected status assignments for no-due-date loans; logic must be explicit |
| `giving_date` is reference-only and excluded from all interest period calculations (R5 authoritative decision) | Any legacy implementation using `giving_date` in calculation will produce incorrect results and must be rewritten |
| 999 loans/month is a safe upper bound; fallback to 1000+ must exist (R4) | Counter overflow on high-volume months if fallback not implemented |
| Loss of extend history is explicitly accepted for both R4 (single) and R5 (batch) extend operations | If user later requires audit trail, a schema redesign will be needed |
| Crash-safety (atomic Paidoff write, recovery file) is deferred — prototype risk acknowledged (R3) | A crash between `loans.csv` and `history.csv` writes can permanently lose a record; must be documented in user guide |
| `TDS = 0.1 * Interest` is the fixed formula (R5) | Any regulatory change to TDS rate requires code update |
| Report ID format is `RPT_YYYYMMDD_<order>` with 3-digit order (R5) | Collision if >999 reports generated in a single day — [REVIEW REQUIRED] fallback not specified |
| "Unknown" depositor group for records b14, b15 is handled as an explicit filter option in the Interest Calculator (R5) | If missed, those records become unselectable by depositor group filter |

---

**Agreed Next Step:**
Solution Architect (SA Agent) to produce the Architecture Decision Record (ADR) covering: table widget selection for 1,500 rows, CSV schema design (`loans.csv`, `loans_meta.csv`, `history.csv`, `pending_reports.csv`, `pending_report_records.csv`), and cross-platform launcher approach. Owner: SA Agent. Target: Wave 0 parallel output alongside this charter.

---

## 2. Scope Baseline

Priority order: R5 > R4 > R1 > R2 > R3 > R6 > R8 > R7 > R10 > R9

### 2.1 In-Scope (Current Prototype Phase)

| Req ID | Description | Priority |
|---|---|---|
| R5 | Interest Calculator Tab: Monthly / Daily / Both modes, filtering, inline editing, TDS, report generation, Pending Approval queue, two-file normalised storage (`pending_reports.csv` + `pending_report_records.csv`), conflict warnings, auto-recalc on inline edit | 1 (Highest) |
| R4 | `reference_id` generation (`YYYY_MM_<order>`), high-water mark in `loans_meta.csv`, Delete, Extend (single record), collision handling, 1000+ fallback, counter reset on full deletion | 2 |
| R1 | New loan entry form: all fields, calendar date-picker, autocomplete, INR amount, CSV storage in `./data/loans.csv`, status-bar confirmation with `ref_id` | 3 |
| R2 | View Tab: sortable/filterable table, all columns per view template, "Unknown" for missing fields, inline depositor group edit for Unknown depositor records | 4 |
| R3 | Record modification in View Tab, Status field (`Active/Overdue/Paidoff/Pending`), QComboBox toggle, auto-recompute on launch, Paidoff flow (ask for `paidoff_date`, move to `history.csv`, atomic write with recovery file logging), transition matrix, manual Active override prompting new due date | 5 |
| R6 | Excel-like column filtering (date hierarchy: year -> month), export to `.csv`/`.xlsx`, import `.csv`/`.xlsx` with preview dialog, upsert/overwrite logic, legacy ref_id collision handling | 6 |
| R8 | PySide6 framework, `.bat` (Windows) and `.sh` (Mac) launchers, CSV-only storage, ISO 8601 dates, no file locking | 7 |
| R7 | Windows-ready packaging documentation, dependency guide, `./data/logs/app.log`, sample data for dev testing only, empty data file ships with prototype | 8 |
| R10 | User guide under `/src/Loan Manager/user_guides/`, Python version check in launchers, batch write on startup | 9 |
| R9 | Modern, professional UI, minimum side-scrolling, alternate theme options for user preference | 10 (Lowest) |
| UT-R1 | Fix: Interest Calculator filter reset bug, View Tab color palette readability, Paidoff marking flow, Windows date-picker UX | Bug-fix / UAT |

### 2.2 Out-of-Scope (Explicit)

- Multi-user / concurrent session support
- Database backend (SQLite or otherwise)
- In-app Paidoff history view
- Network or cloud-based CSV sync
- Production installer / packaged executable (e.g., PyInstaller `.exe`)
- Timestamped backup copy before destructive operations (deferred — see risk register)
- "Fill all rows / copy down" shortcut in Interest Calculator
- CSV file locking

### 2.3 Deferred (Future Phases)

| Item | Reason for Deferral |
|---|---|
| Timestamped backup before Paidoff / bulk approve | Acknowledged as meaningful risk in R3; explicitly deferred for prototype |
| Production packaging (`.exe`, `.app` bundle) | Not required for prototype scope (R8) |
| "Fill all / copy down" shortcut in Interest Calculator | R5 explicitly defers; initial record count post-filter not expected to exceed 10 |
| Bulk approve backup | Same as Paidoff backup deferral |
| Paidoff history in-app view | R3 explicitly excludes in-app view; history.csv maintained for future |
| Report ID daily >999 fallback | [REVIEW REQUIRED] not specified in requirements |

---

## 3. Phase Roadmap

### Phase 1 — Core Data Foundation
**Goal:** Working loan entry, viewing, editing, and basic status management. The skeleton all other features build on.

| Req ID | Deliverable |
|---|---|
| R8 | PySide6 project scaffold, `.bat` + `.sh` launchers, CSV I/O layer, `./data/` directory structure, ISO 8601 dates, logging to `./data/logs/app.log` |
| R4 | `reference_id` generation engine with `loans_meta.csv`, Delete, counter reset, 1000+ fallback |
| R1 | New Loan Entry Tab: form, calendar date-picker, autocomplete, INR amount validation, save to `loans.csv`, status-bar confirmation |
| R2 | View Tab: sortable table (QTableView recommended for 1500 rows — see ADR), all view-template columns, "Unknown" fallback, inline depositor group edit |
| R3 | Status field with QComboBox, auto-recompute on launch, transition matrix, Paidoff flow with `history.csv`, atomic write with recovery file |
| R10 | Python version check in launchers, batch write on startup |

**Phase 1 Exit Criteria:** User can create loans, view/sort/filter them, change statuses including Paidoff, and data persists correctly across restarts.

---

### Phase 2 — Interest Calculator and Pending Approval
**Goal:** Full interest calculation workflow from filtering through report generation and approval.

| Req ID | Deliverable |
|---|---|
| R5 | Interest Calculator Tab: 3 modes (Monthly/Daily/Both), 5 filter options, inline editable parameters, TDS flag, auto-recalc on edit, Calculate button, Generate Report button (disabled until Calculate), report format per borrower |
| R5 | Pending Approval Tab: `pending_reports.csv` + `pending_report_records.csv`, report CRUD, approve/decline flow, conflict warning for shared `reference_id`s, deleted-record warning on approve, pre/post extension preview columns, persist across restarts |
| R4 | Extend (single record) from View Tab, reusing `reference_id`, R4 Extend flow |

**Phase 2 Exit Criteria:** User can filter loans, run interest calculations in all 3 modes, generate reports, review/edit in Pending Approval, and approve to update `loans.csv` — with all edge-case warnings functional.

---

### Phase 3 — Import/Export, UI Polish, and UAT Fixes
**Goal:** Production-readiness of prototype: data exchange, UI quality, and resolution of all UT-R1 defects.

| Req ID | Deliverable |
|---|---|
| R6 | Export to `.csv`/`.xlsx`, Import `.csv`/`.xlsx` with preview dialog (overwrite preview, new/overwrite counts), upsert logic, legacy ref_id handling |
| R6 | Excel-like column filtering with date hierarchy (year -> month -> filtered records) in View Tab |
| R7 | Full dependency guide, `run_windows.bat` and `run_mac.sh` final validation |
| R9 | UI theme options, color palette refinement, side-scroll minimization |
| R10 | User guide under `/src/Loan Manager/user_guides/` (Windows + Mac run steps) |
| UT-R1 | Fix Interest Calculator filter reset bug |
| UT-R1 | Fix View Tab color palette (dark background, readable text) |
| UT-R1 | Fix Paidoff marking flow (ensure QComboBox selection triggers paidoff_date dialog) |
| UT-R1 | Fix Windows date-picker UX (picker opens on field click, not dropdown arrow only) |

**Phase 3 Exit Criteria:** User can import historical data, export reports, all UT-R1 issues resolved, user guide complete, prototype accepted by end-user.

---

## 4. Risk Register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| RSK-01 | Crash between `loans.csv` and `history.csv` write causes permanent record loss (Paidoff flow) | Medium | High | Log target row to recovery file before first write (R3 specifies this); document as known prototype risk; full atomic write deferred to future phase |
| RSK-02 | Duplicate `reference_id` collision on import or after counter reset | Low | Medium | Collision detection loop in ref_id service; increment until non-colliding ID found (R4) |
| RSK-03 | Two reports in Pending Approval queue share same `reference_id`; approval silently overwrites the other | Medium | High | Warn user on approval with "Proceed / Cancel" dialog (R5 specified); silent overwrite only after explicit user confirmation |
| RSK-04 | Python version < 3.10 on end-user machine | Low | High | Launcher scripts check version and print upgrade instructions before proceeding (R10) |
| RSK-05 | PySide6 licensing or installation failure on Windows | Low | Medium | Document exact pip install steps; test on clean Windows environment before delivery |
| RSK-06 | Interest calculation using `giving_date` in period (pre-existing implementation error) | Medium | High | R5 authoritative: charge extension window only; rewrite and re-test calculator if legacy code differs |
| RSK-07 | CSV divergence between Windows and Mac users (git-shared CSVs) | Medium | Medium | [REVIEW REQUIRED] — no conflict resolution protocol defined; recommend git pull before launch as convention; document in user guide |
| RSK-08 | UI side-scrolling on smaller Windows screens | Medium | Low | Minimize column widths, allow column resize; test at 1366x768 resolution (common Windows laptop) |
| RSK-09 | `report_id` counter overflow at >999 reports per day | Very Low | Low | [REVIEW REQUIRED] — fallback format not defined in R5; recommend incrementing beyond 3 digits as with ref_id |
| RSK-10 | Paidoff record in Pending Approval queue deleted before approval | Low | Medium | R5 specifies warning dialog: "Records in this report have been deleted." with Ignore / Decline options; skip deleted records on ignore |
| RSK-11 | UT-R1 defects recur after fix due to lack of automated tests | Medium | Medium | Write unit tests for filter logic, status computation, and calculator; run before each commit |

---

## 5. Capacity Estimate

Estimates are for a single developer producing a working prototype (not production-grade). These are rough order-of-magnitude figures.

| Phase | Key Work Items | Estimated Dev-Days |
|---|---|---|
| Phase 1 — Core Data Foundation | Project scaffold, launchers, CSV I/O layer, ref_id engine, New Entry Tab, View Tab (sortable/filterable/inline-edit), Status management + Paidoff flow, atomic write, logging | 8–12 days |
| Phase 2 — Interest Calculator and Pending Approval | Calculator Tab (3 modes, filters, inline params, TDS, Calculate/Generate), Pending Approval Tab (persist, approve/decline, conflict warnings, pre/post preview), Extend (R4) | 10–14 days |
| Phase 3 — Import/Export, UI Polish, UAT Fixes | Import/export with preview dialogs, date-hierarchy filter, UI themes, UT-R1 bug fixes (4 items), user guide, final launcher validation | 5–8 days |
| **Total Prototype Estimate** | | **23–34 dev-days** |

**Notes:**
- Lower bound assumes developer has prior PySide6 and CSV-handling experience.
- Upper bound accounts for UAT feedback loops, edge-case handling (collision logic, atomic writes, filter interactions), and cross-platform testing.
- UT-R1 defects are already identified, reducing discovery time in Phase 3.
- [REVIEW REQUIRED] — User has not specified a target completion date; timeline to be confirmed with end user before Phase 1 kick-off.

---

*End of Project Charter — Loan Manager — run_1 / Wave 0 — 2026-04-03*
