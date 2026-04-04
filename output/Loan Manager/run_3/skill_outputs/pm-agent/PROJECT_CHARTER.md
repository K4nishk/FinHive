# PM: Project Charter — Loan Manager run_3
**Document Version:** 3.0
**Date:** 2026-04-03
**Run:** run_3 / Wave 0
**Author:** PM Agent
**Supersedes:** run_2/skill_outputs/pm-agent/PROJECT_CHARTER.md

---

## 1. Run_3 Delta Summary

This charter is a targeted update for run_3 (MVP Closure Stage). The overall project charter from run_1 and run_2 remain valid. This document records only what changed relative to run_2, the sprint plan for Phase 3 final closure, and the Phase 4 readiness gate.

### 1.1 Requirement Changes vs. run_2

| Change ID | Requirement | Description | Scope Classification |
|---|---|---|---|
| CHG-02-EXT | R3 | Paidoff dialog now collects `interest_rate`, `commission_rate`, `tds_flag` per event — resolves BC-04 (right-click confirmed) and BC-05 (per-event values, not global defaults) | Dialog extension — extends prior CHG-02 scope |
| BUG-02-REF | UT-R1 | Exact color hex codes now specified: Active=#2d6a4f, Overdue=#9b2226, Pending=#ca6702, Paidoff=#495057 — all white text | Color precision update — was deferred pending user confirmation |
| BUG-03-REM | UT-R1 | Standalone BUG-03 tracking removed — subsumed by CHG-02 Paidoff flow; no separate fix needed | Scope reduction — removes a work item |
| DOC-CLEAN | REQUIREMENTS.md | Priority section `R5 > R4 > R1 > ...` removed from document | Documentation cleanup — zero implementation impact |

### 1.2 Items Carried from run_2 as Resolved

| ID | Item | Resolution |
|---|---|---|
| BC-04 | QComboBox vs right-click for Paidoff | Resolved: right-click context menu confirmed in R3 text |
| BC-05 | Global vs per-event interest_rate/commission_rate for Paidoff | Resolved: per-event entry confirmed via new dialog fields |
| BC-02 | View Tab color palette user confirmation | Resolved: exact hex codes now provided in requirements |

---

## 2. Run_3 Scope Baseline

### 2.1 In-Scope for run_3

| Item ID | Description | Priority | File(s) Affected |
|---|---|---|---|
| CHG-02-EXT | Extend PaidoffDialog to include `interest_rate` (QDoubleSpinBox), `commission_rate` (QDoubleSpinBox), `tds_flag` (QCheckBox, default unchecked) | P1 — must implement | `ui/dialogs/paidoff_dialog.py`, `ui/view_tab.py` |
| CHG-02-EXT | Update `_action_paidoff()` in `view_tab.py` to pass `interest_rate`, `commission_rate`, `tds_flag` from dialog to `_generate_paidoff_report()` | P1 — must implement | `ui/view_tab.py` |
| CHG-02-EXT | Update `_generate_paidoff_report()` to use dialog-supplied values instead of hardcoded defaults (12.0, 2.0, False) | P1 — must implement | `ui/view_tab.py` |
| CHG-02-EXT | Paidoff warning message to display: "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied." | P1 — display in Pending Approval tab | `ui/pending_approval_tab.py` |
| BUG-02-REF | Replace STATUS_COLORS dict in `view_tab.py` with exact hex values from requirements | P1 — must implement | `ui/view_tab.py` |
| BUG-02-REF | Ensure foreground (text) color is set to white for all status rows in `_make_row()` | P1 — must implement | `ui/view_tab.py` |

### 2.2 Out of Scope for run_3

| Item | Reason |
|---|---|
| QComboBox Status delegate for View Tab | Phase 4 backlog — PD-R2-06 from run_2 |
| R6 import/export full date hierarchy | Phase 4 |
| R9 theme chooser | Phase 4 |
| Any run_2 items (CHG-01, BUG-01, BUG-04, DOC-01) | Already planned in run_2 |
| UAT agent invocation | Implementation not yet complete; UAT follows implementation |

### 2.3 Deferred to Phase 4

| Item | Target Phase |
|---|---|
| QComboBox StatusDelegate for inline Paidoff toggle | Phase 4 |
| R6 full date-hierarchy filter + export to .xlsx | Phase 4 |
| R9 alternate theme chooser | Phase 4 |
| BC-03 Phase 4 scope ordering (user to confirm) | Phase 4 planning |

---

## 3. Sprint Plan — run_3

**Sprint Goal:** Complete MVP closure by implementing CHG-02-EXT (Paidoff dialog + report warning) and BUG-02-REF (status colors), achieving a shippable prototype ready for Phase 4 kickoff.

**Team Capacity (estimated):** 1 developer, desktop Python/PySide6 stack. No external blockers.

### Sprint Backlog

| # | Item | Owner | Estimate | Dependency | Acceptance Criteria |
|---|---|---|---|---|---|
| 1 | PaidoffDialog: add interest_rate, commission_rate, tds_flag fields | Backend Dev | 1 hour | None | Dialog renders 3 new fields; values retrievable via accessors |
| 2 | view_tab.py: update _action_paidoff() to read new dialog fields | Backend Dev | 30 min | Item 1 | interest_rate, commission_rate, tds_flag passed to report generator |
| 3 | view_tab.py: update _generate_paidoff_report() to use per-event values (remove hardcoded 12.0, 2.0, False) | Backend Dev | 30 min | Item 2 | Report record uses values entered by user, not defaults |
| 4 | pending_approval_tab.py: display paidoff warning message per spec | Backend Dev | 30 min | None | Warning text matches spec exactly |
| 5 | view_tab.py: replace STATUS_COLORS with exact hex codes + set white foreground | Backend Dev | 30 min | None | Status colors match #2d6a4f/#9b2226/#ca6702/#495057 with white text |
| 6 | Write/update tests for CHG-02-EXT dialog fields and report values | Backend QA | 1 hour | Items 1-3 | Unit tests pass; dialog default state verified |
| 7 | Write/update tests for BUG-02-REF color constants | Backend QA | 30 min | Item 5 | Constant values match expected hex strings |

**Capacity utilisation:** ~4 hours developer + 1.5 hours QA. Well within a single-day sprint.

**Sprint risks:**
- **R-301**: `pending_approval_tab.py` paidoff warning display location is not fully specified — does it appear in the report detail row, or as a header? [REVIEW REQUIRED — BC-301]: User to clarify where the warning message appears in the Pending Approval Tab (report header row vs. below report title vs. tooltip on row).
- **R-302**: The existing `_generate_paidoff_report()` in `view_tab.py` uses hardcoded `interest_rate=12.0`, `commission_rate=2.0`. Confirm these are the only two call sites for these defaults; no other callers should be affected.

---

## 4. Phase 4 Readiness Gate

Phase 4 kickoff is gated on ALL of the following:

| Gate Item | Owner | Status |
|---|---|---|
| CHG-02-EXT implemented and tested | Backend Dev + QA | Pending run_3 |
| BUG-02-REF colors applied | Backend Dev | Pending run_3 |
| All run_2 items implemented (CHG-01, BUG-01, BUG-04, DOC-01) | Backend Dev | Pending run_2 delivery |
| BC-03 Phase 4 scope decision (user input) | User / PO | [REVIEW REQUIRED — BC-03] |
| BC-301 Paidoff warning display location (user input) | User / PO | [REVIEW REQUIRED — BC-301] |

---

## 5. Risk Register (Active Only)

| ID | Risk | Prob | Impact | Status | Mitigation | Owner |
|---|---|---|---|---|---|---|
| R-201 | Hardcoded interest_rate/commission_rate in _generate_paidoff_report() used by real users with different rates before run_3 fix ships | High | Medium | Open — fixed by CHG-02-EXT | Replace with per-dialog values | Backend Dev |
| R-202 | STATUS_COLORS white text not explicitly set in _make_row() — row may still display dark text if foreground not forced | Medium | High | Open — fixed by BUG-02-REF | Set foreground color explicitly on each QStandardItem | Backend Dev |
| R-301 | Paidoff warning location ambiguous — may be implemented in wrong UI location | Medium | Low | Open — awaiting BC-301 | Log [REVIEW REQUIRED]; implement in most visible location (report header) as default | Backend Dev |
| R-302 | BC-03 Phase 4 scope not confirmed — cannot start Phase 4 sprint planning | High | Medium | Open | Escalate to user for decision | PO |

---

## 6. Traceability Matrix (run_3 items only)

| Req ID | Change ID | BSA Story | SA Component | DM Entity | Dev Task | QA Scenario |
|---|---|---|---|---|---|---|
| R3 | CHG-02-EXT | STORY-CHG-02-EXT-01 | PaidoffDialog widget | No schema change | Items 1-3 | PaidoffDialog field defaults, report values |
| R3 | CHG-02-EXT | STORY-CHG-02-EXT-02 | pending_approval_tab | No schema change | Item 4 | Warning message display |
| UT-R1 | BUG-02-REF | STORY-BUG-02-REF | view_tab STATUS_COLORS | No schema change | Item 5 | Color constants assertion |

---

## 7. PM [REVIEW REQUIRED] Items

| ID | Item | Impact of deferring decision |
|---|---|---|
| BC-301 | Where in the Pending Approval Tab should the paidoff warning message appear? Options: (a) as a label in the report header row, (b) as a tooltip on the row, (c) as a static info bar at the top of the tab when a paidoff report is selected | Implementation will use option (a) as default; wrong placement reduces UX clarity |
| BC-03 | Phase 4 primary focus: R6 import/export full date hierarchy vs R9 themes vs QComboBox Status delegate | Phase 4 sprint planning cannot be committed without this decision |

