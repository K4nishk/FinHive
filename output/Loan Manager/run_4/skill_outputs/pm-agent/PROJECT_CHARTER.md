# PM Agent: Project Charter — Loan Manager run_4
**Date:** 2026-04-04
**Run:** run_4 (Phase 3 Closure + Phase 4 Kickoff)
**Agent:** pm-agent (Wave 0)

---

## PM: Project Charter — Loan Manager

**Business Objective:** Deliver a reliable, cross-platform (Windows primary, Mac secondary) desktop loan management application that allows a single end-user to record, view, modify, and generate interest reports for personal loan records — without requiring a database or specialist IT support.

**Problem Statement:** The user manages personal loan records manually (likely via spreadsheet or memory). A dedicated application with structured entry, status tracking, interest calculation, and approval-based reporting will reduce errors, improve traceability, and save time during loan review cycles. Four production bugs found during user testing are currently blocking reliable use of the application.

**Success Metrics:**
- All 4 user-testing bugs (BUG-UTR-1 through BUG-UTR-4) fixed and verified on both Windows and Mac
- 197 existing tests remain green after all fixes
- New tests added per bug fix (minimum 1 unit test per backend fix)
- Interest Calculator filter works correctly for all 4 filter types (BorrowerGroup, BorrowerName, DepositorName, DepositorGroup)
- No duplicate reference_ids generated during rapid consecutive entry on Windows
- View Tab Refresh does not trigger spurious write operations
- Date picker opens on single click anywhere on the field (not just the dropdown arrow)
- Phase 4 sprint plan ready to start immediately after BC-03 user decision

**Stakeholders:**
| Name / Role             | Interest                                        | Engagement Level |
|-------------------------|-------------------------------------------------|------------------|
| End User (Windows)      | Loan record accuracy, ease of use               | Decide           |
| Mac Tester              | Cross-platform parity, git-based CSV sharing    | Consult          |
| Developer               | Implementability, test coverage, clean fixes    | Inform           |

**Constraints:**
- Budget: Not defined — single developer, no external services
- Timeline: Phase 3 closure target = run_4 (bug fixes implemented and tested); Phase 4 start = pending BC-03 user decision
- Scope boundary: Phase 4 features (R6 import/export, R9 themes, QComboBox StatusDelegate) are explicitly OUT of run_4 scope until BC-03 resolved

**Assumptions and risks at kick-off:**
- Assumption: All 4 bugs are implementable without schema changes: Risk if wrong = DM or SA agent raises breaking change (low probability per source analysis)
- Assumption: BC-03 user decision will be provided before Phase 4 sprint begins: Risk if wrong = Phase 4 indefinitely delayed
- Assumption: ClickableDateEdit subclass resolves date picker UX on both Windows and Mac: Risk if wrong = OS-specific Qt behaviour differs (medium probability — Qt calendar popup behaviour varies slightly by platform)
- Assumption: PaidoffDialog CHG-02-EXT (interest_rate/commission_rate/tds_flag fields) was not implemented in run_3: Risk = confirmed by source inspection — this is a carry-forward implementation gap that must be included in run_4 scope

**Agreed next step:** Backend Developer implements BUG-UTR-1 through BUG-UTR-4 fixes + BC-301 + CHG-02-EXT (Paidoff dialog fields), Backend QA writes test stubs, QA Lead confirms scope, UAT validates scenarios.

---

## PM: Scope Baseline — run_4 (Phase 3 Closure)

**In scope (agreed):**
- BUG-UTR-1: Fix Interest Calculator filter dropdown reset (P1)
- BUG-UTR-2: Fix duplicate reference_id generation on Windows (P1)
- BUG-UTR-3: Fix View Tab Refresh spurious write of unchanged records (P1)
- BUG-UTR-4: Fix date picker UX — open on single field click (P2)
- BC-301: Implement Paidoff warning label in Pending Approval Tab (option a, LOW)
- CHG-02-EXT: Implement interest_rate/commission_rate/tds_flag fields in PaidoffDialog (carry-forward from run_3 — confirmed not yet coded)
- OS-DRIFT: Apply all fixes consistently across Windows and Mac (non-negotiable per user requirement)
- Test coverage: add new unit tests for BUG-UTR-2 and BUG-UTR-3 backend fixes
- 197 existing tests must remain green

**Out of scope (explicit):**
- R6: Import/export with date hierarchy filter (Phase 4)
- R9: Alternate theme chooser (Phase 4)
- QComboBox StatusDelegate for View Tab inline status toggle (Phase 4)
- Timestamped CSV backup before destructive operations (deferred in requirements: "For prototype scope, this is not required")
- User guide updates for run_4 changes (Phase 4 or standalone)

**Deferred (possible future phase):**
- R6: Full import/export (high effort, Phase 4 — pending BC-03)
- R9: Theme chooser (medium effort, Phase 4 — pending BC-03)
- QComboBox StatusDelegate (medium effort, Phase 4 — pending BC-03)
- R10: User guide for run_4 changes

**Open scope questions (needs PO decision):**
- BC-03: Phase 4 primary focus — user must choose between Track A (R6 + QComboBox) or Track B (R9 + QComboBox): Impact of deferring = Phase 4 sprint cannot be planned

**Traceability:**
| Req ID    | BSA Story              | SA Component              | DM Entity          | Dev Task          | QA Scenario              |
|-----------|------------------------|---------------------------|--------------------|-------------------|--------------------------|
| UTR-1     | US-UTR-1 Filter fix    | InterestCalculatorTab     | None               | Fix _on_apply_filters() | Filter dropdown retains selection |
| UTR-2     | US-UTR-2 Ref ID unique | RefIdManager              | loans_meta.csv     | Fix _active_year_months() + atomic _write_meta() | No duplicate IDs on rapid entry |
| UTR-3     | US-UTR-3 Refresh safe  | ViewTab / CSVManager      | loans.csv          | Status snapshot in load_data() | Refresh does not update unchanged records |
| UTR-4     | US-UTR-4 Date picker   | ClickableDateEdit widget  | None               | Create ui/widgets.py, replace QDateEdit | Calendar opens on single click |
| BC-301    | US-BC-301 Warning lbl  | PendingApprovalTab        | None               | Insert QLabel in detail panel | Warning visible for Paidoff reports |
| CHG-02-EXT| US-CHG-02-EXT Paidoff  | PaidoffDialog             | None               | Add rate fields to PaidoffDialog | Dialog collects rate/commission/TDS |

---

## PM: Phase Roadmap

| Phase   | Status          | Scope Summary                                                                 | Delivered In |
|---------|-----------------|-------------------------------------------------------------------------------|--------------|
| Phase 1 | Complete        | Entry Tab, View Tab (sort/inline edit), Status engine, Paidoff, Extend, Ref IDs, launchers | run_1        |
| Phase 2 | Complete        | Interest Calculator (3 modes), Pending Approval queue, Report CRUD, batch approval | run_1/run_2  |
| Phase 3 | MVP Closure     | BUG-UTR-1 to UTR-4 fixes, BC-301, CHG-02-EXT, Status color palette (run_3)   | run_4        |
| Phase 4 | Planned (blocked) | R6 import/export with date hierarchy filter, R9 themes, QComboBox StatusDelegate — BLOCKED on BC-03 user decision | run_5+       |

---

## PM: Risk Register

| ID    | Risk                                         | Prob | Impact | Status | Mitigation                                      | Owner    |
|-------|----------------------------------------------|------|--------|--------|-------------------------------------------------|----------|
| R-001 | BUG-UTR-1 filter reset fix breaks filter reset on new loan load | L | M | Open | Add regression test for filter-clear-on-data-load vs filter-retain-on-apply | Dev + QA |
| R-002 | BUG-UTR-2 atomic write incompatible with Windows file system | M | H | Open | Use pathlib.Path.replace() which is atomic on POSIX and Windows (rename semantics) | Dev |
| R-003 | BUG-UTR-3 status snapshot misses edge case where recompute_all mutates status in place | M | H | Open | Snapshot must be taken from the pre-recompute loan list | Dev |
| R-004 | BUG-UTR-4 ClickableDateEdit Qt platform behaviour differs Win/Mac | M | M | Open | Test on both platforms; document workaround if needed | Dev + Mac tester |
| R-005 | CHG-02-EXT not yet implemented — was listed as Phase 3 closure in run_3 | H | M | Open | Add to run_4 in-scope; backend dev to implement PaidoffDialog rate fields | Dev |
| R-006 | BC-03 not resolved — Phase 4 cannot be sprint-planned | H | H | Open | Escalate to user; provide two sprint tracks as decision input | PO + PM |
| R-007 | OS drift between Windows and Mac | M | H | Open | All QDateEdit replacements must use ClickableDateEdit; no platform-specific code paths | Dev |

---

## PM: QA Status & Defect Triage — run_4 / Phase 3 Closure

**QA entry criteria met:** No — bugs confirmed from user testing, fixes not yet implemented
**Testing window:** 2026-04-04 → upon completion of fixes

**Defect summary:**
| Severity | Open | In Fix | Closed | Release-blocking? |
|----------|------|--------|--------|-------------------|
| P1       | 3    | 0      | 0      | Yes — must fix     |
| P2       | 1    | 0      | 0      | No — fix before Phase 4 |
| P3+      | 0    | 0      | 0      | No                |

Note: CHG-02-EXT is a missing feature (not a regression), classified P2 — must be implemented before Phase 3 is declared complete.

**Timeline impact of open P1s:** Phase 3 cannot close until BUG-UTR-1, UTR-2, and UTR-3 are fixed and verified.

**PM decision on release-blocking defects:**
- BUG-UTR-1: Fix before Phase 3 close — core feature (R5) non-functional
- BUG-UTR-2: Fix before Phase 3 close — data integrity violation (R4)
- BUG-UTR-3: Fix before Phase 3 close — data corruption risk on every Refresh
- BUG-UTR-4: Fix in run_4 — P2, UX issue, before Phase 4 handoff
- CHG-02-EXT: Implement in run_4 — incomplete Phase 3 item

---

## PM: Go/No-Go Assessment — Phase 3 / run_4

**Release date:** Post run_4 implementation | **Deploy window:** Local desktop, no deployment window required

**Go/No-Go checklist:**
- [ ] BUG-UTR-1 fixed and tested (Interest Calculator filter retains selection)
- [ ] BUG-UTR-2 fixed and tested (no duplicate ref_ids on Windows rapid entry)
- [ ] BUG-UTR-3 fixed and tested (View Tab Refresh does not overwrite unchanged records)
- [ ] BUG-UTR-4 fixed (date picker opens on single click)
- [ ] CHG-02-EXT implemented (PaidoffDialog collects interest_rate, commission_rate, tds_flag)
- [ ] BC-301 implemented (Paidoff warning label visible in Pending Approval Tab)
- [ ] All 197 existing tests pass + new tests for BUG-UTR-2 and BUG-UTR-3 pass
- [ ] QA Lead signoff received
- [ ] UAT Conditional Accept received
- [ ] BC-03 user decision received (required for Phase 4 planning only, not Phase 3 Go/No-Go)

**Open risks at release:**
- CHG-02-EXT PaidoffDialog report generation (the full report pipeline for Paidoff loans) may need additional end-to-end validation if the report_manager integration is complex
- ClickableDateEdit Qt behaviour on Windows — minor risk, needs user validation

**PM recommendation:** Conditional Go — Phase 3 can close after all six items above are checked. Phase 4 planning is on hold until BC-03 user decision.

**Release comms draft:**
"Phase 3 of Loan Manager is closed. Four user-reported bugs have been fixed (filter dropdown, duplicate IDs, refresh data overwrite, date picker UX). The Paidoff dialog now collects interest rate, commission rate, and TDS flag to generate the interest report as originally specified. Phase 4 planning is ready to begin — please provide your Phase 4 scope preference (see BC-03 below)."

**Post-release monitoring window:** User validation session on Windows after fixes deployed | **On-call owner:** Mac Tester (git-based CSV sync)

---

## PM: Sprint Plan — Phase 4 (Two Tracks — Conditional on BC-03)

**Team capacity:** 1 developer, estimated 5-7 person-days per track
**Velocity (estimated):** Comparable to Phase 3 (3-5 days per sprint equivalent)

### Track A — R6 Import/Export + QComboBox StatusDelegate

**Sprint goal:** User can import historical .csv/.xlsx data and export the current loans view; View Tab status column uses a QComboBox dropdown for state transitions.

**Committed items:**
| # | Item                                              | Owner  | Estimate | Dependency          |
|---|---------------------------------------------------|--------|----------|---------------------|
| 1 | R6: Import .csv with preview dialog (new + overwrite) | Dev | 2 days   | None                |
| 2 | R6: Export loans.csv + filtered calculator results | Dev   | 1 day    | None                |
| 3 | R6: Date hierarchy filter (Year > Month > records) in View Tab | Dev | 2 days | None          |
| 4 | QComboBox StatusDelegate in View Tab status column | Dev   | 1 day    | None                |
| 5 | Tests for all Track A items                        | Dev+QA | 1 day   | Items 1-4           |

**Capacity utilisation:** ~100% (7 days / 7 day sprint)

**Explicitly NOT in this sprint:**
- R9 themes: deferred to Track B or Phase 5
- R10 user guide: ongoing, out of sprint

### Track B — R9 Theme Chooser + QComboBox StatusDelegate

**Sprint goal:** User can switch between at least 2 UI themes; View Tab status column uses a QComboBox dropdown.

**Committed items:**
| # | Item                                              | Owner  | Estimate | Dependency          |
|---|---------------------------------------------------|--------|----------|---------------------|
| 1 | R9: Define 2 theme stylesheets (light, dark or alternate) | Dev | 1 day | None            |
| 2 | R9: Theme selector in app menu or settings panel  | Dev    | 1 day    | Item 1              |
| 3 | R9: Persist theme preference to settings file     | Dev    | 0.5 days | Item 2              |
| 4 | QComboBox StatusDelegate in View Tab status column | Dev   | 1 day    | None                |
| 5 | Tests for all Track B items                        | Dev+QA | 1 day   | Items 1-4           |

**Capacity utilisation:** ~64% (4.5 days / 7 day sprint) — lower than Track A, leaves room for R10 user guide

**Explicitly NOT in this sprint:**
- R6 import/export: deferred to Track A or Phase 5
- R6 date hierarchy filter: deferred to Track A or Phase 5

### [REVIEW REQUIRED] — BC-03: User must select Track A or Track B before Phase 4 sprint can begin.

---

## PM: Data Model Delivery Impact — run_4

**Schema change type:** None required for bug fixes

**Schedule impact:** 0 days — all 4 bug fixes are code-only changes. loans_meta.csv gains atomic write process (no column changes). No migration required.

**Coordination needed:**
- Backend Dev: implement atomic _write_meta() (process change only, same schema)
- QA Lead: verify loans_meta.csv counter integrity after fix

**Risk:** Low — no schema changes means no migration risk for existing data files.

---

## PM: Architecture Delivery Review — run_4 Bug Fixes

**Timeline implications:**
- ClickableDateEdit subclass: 0.5 days to create and apply app-wide — low risk
- Atomic _write_meta(): 0.5 days — standard Python pathlib pattern
- Status snapshot in load_data(): 0.5 days — minimal change to existing method
- Filter capture in _on_apply_filters(): 0.5 days — one-line ordering fix + instance variable

**Team capability gaps:** None identified — all fixes use existing Python/PySide6 patterns

**Dependencies introduced:** None

**Risk introduced:**
- ClickableDateEdit calendar popup event may conflict with existing QDateEdit focusIn handling on some Qt versions — low probability, testable

**PM recommendation:** Proceed with flagged items — ClickableDateEdit cross-platform validation required

---

## Carry-forward Resolution Table

| Item   | Status in run_3                      | Status in run_4                                        |
|--------|--------------------------------------|--------------------------------------------------------|
| BC-301 | Open — option (a) as default         | RESOLVED — proceed with option (a), implementation in scope |
| TC-303 | Open — developer read file first     | RESOLVED — developer reads pending_approval_tab.py before implementing BC-301 label |
| BC-03  | Open — user decision required        | STILL OPEN — escalate to user before Phase 4 sprint   |
| CHG-02-EXT | Planned in run_3 docs but not coded | IN SCOPE for run_4 — confirmed implementation gap |
