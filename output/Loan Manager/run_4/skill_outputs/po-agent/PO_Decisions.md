# PO Agent: Early Binding Decisions — Loan Manager run_4
**Date:** 2026-04-04
**Run:** run_4 (Phase 3 Closure + Phase 4 Kickoff)
**Wave:** 0 — issued before all other agents to unblock downstream work
**Agent:** po-agent

---

## Cross-Reference: run_3 Open Items

Before issuing decisions, cross-referencing run_3 CLARIFICATIONS to avoid duplicate escalations:

| run_3 Item | Status at run_3 Close | run_4 Disposition |
|---|---|---|
| BC-04 (Right-click vs QComboBox for Paidoff) | Resolved | Closed — no re-raise |
| BC-05 (Rate source for Paidoff report) | Resolved | Closed — CHG-02-EXT accepted (PD-R3-01) |
| BC-02 (View Tab color palette) | Resolved | Closed — implemented |
| TC-301 (mode="Paidoff" string) | Resolved | Closed |
| TC-302 (data/report_manager.py shim) | Resolved | Closed |
| TC-304 (None guard in approval handler) | Resolved | Closed |
| TC-303 (Read pending_approval_tab.py before IMPL-5) | Developer action — open | RESOLVED by run_4 scope: developer must read the file; this is a dev pre-condition, not a user decision. Closing as TC. |
| BC-301 (Paidoff warning label placement) | Low — option (a) as default | RESOLVED: No user response received. Default option (a) accepted. Proceeding. |
| BC-03 (Phase 4 scope) | Medium — user input required | STILL OPEN — escalated again below as BC-03 |

**Key finding from source code inspection:** CHG-02-EXT (PaidoffDialog rate fields — interest_rate, commission_rate, tds_flag) was accepted in run_3 (PD-R3-01) but was NOT implemented in the source code. The PaidoffDialog in `/src/Loan Manager/ui/dialogs/paidoff_dialog.py` contains only a date picker and confirmation buttons. This is an implementation gap that must be addressed in run_4.

---

## PO Decision: BUG-UTR-1 — Interest Calculator Filter Dropdown Reset

**Decision:** Accept — P1

**Business Rationale:** R5 explicitly defines 5 filter options (Borrower Group, Borrower Name, Depositor Name, Depositor Group, By Month). The user reports these filters do not retain their selection when applied. A filter that resets itself on every use is functionally broken — R5 is non-operational for 4 of 5 filter types. This is a P1 defect against a core feature.

**Scope Impact:** Fix confined to `ui/interest_calculator_tab.py`, method `_on_apply_filters()`. Root cause confirmed: method calls `_load_loans()` → `_populate_filters()` which clears all combo boxes before filter values are read. Fix: capture filter selections before calling `_load_loans()`.

**Timeline Impact:** Single method fix — estimated 0.5 days including unit/manual test.

**Risk:** Regression risk: filter combo reset on new data load is intentional behaviour (correct) — the fix must preserve that while also preserving the user's selection when the user explicitly clicks Apply Filters. Dev must ensure `_populate_filters()` is still called on initial tab load but filter values are captured before the reload on Apply Filters.

**Updated Backlog Item:**
- As a user, when I select a Borrower Group from the filter dropdown and click Apply Filters, the table shows only loans matching that Borrower Group and the dropdown retains my selection.
- Acceptance: All 4 named filter combos retain selection after Apply Filters is clicked. By Month filter continues to work.

---

## PO Decision: BUG-UTR-2 — Duplicate Reference IDs on Windows

**Decision:** Accept — P1

**Business Rationale:** R4 states: "The increment of the order is crucial and should be validated." Duplicate reference_ids violate the core identifier contract. The user reports multiple entries with the same ID (2026_04_001). Reference ID uniqueness is load-bearing — the entire edit/delete/extend/paidoff workflow depends on it.

**Scope Impact:** Two fixes required:
1. `data/ref_id_manager.py`: `_active_year_months()` currently derives year_month from `loan.giving_date` — incorrect. Must use `reference_id` field to extract the year_month bucket (first two underscore-separated segments of the ref_id).
2. `loan_manager/ref_id_manager.py`: `_write_meta()` must use atomic write (write to temp file, then rename via `pathlib.Path.replace()`) to prevent meta file corruption on Windows crash or concurrent write.

**Timeline Impact:** Estimated 1 day including tests for counter uniqueness.

**Risk:** `_active_year_months()` fix changes which year_month buckets are considered "active". Edge case: a loan with giving_date in a different month than its reference_id year_month (e.g., back-dated entry). The fix must use ref_id not giving_date — this is the correct semantics per R4 which says counter is per YYYY_MM of the entry date, not the giving date.

**Updated Backlog Item:**
- As a user entering multiple loans in rapid succession in April 2026, each loan receives a unique reference_id (2026_04_001, 2026_04_002, etc.) with no duplicates.
- Acceptance: 10 rapid consecutive entries all have unique, sequentially incremented reference_ids.

---

## PO Decision: BUG-UTR-3 — View Tab Refresh Overwrites All Records

**Decision:** Accept — P1

**Business Rationale:** The user reports data corruption on Refresh. Source analysis confirms: `load_data()` in `view_tab.py` calls `update_loan(loan)` for every loan after `recompute_all()` — even when status has not changed. Each `update_loan()` call triggers a full CSV rewrite. This is both a performance issue (O(N) rewrites on every Refresh) and a data integrity risk (any in-memory state drift is persisted on every Refresh regardless of intent).

**Scope Impact:** Fix confined to `ui/view_tab.py`, method `load_data()`. Pattern: snapshot `{reference_id: status}` before `recompute_all()`; after recompute, call `update_loan()` only for loans where `new_status != snapshot[reference_id]`.

**Timeline Impact:** Estimated 0.5 days including test.

**Risk:** If recompute_all() returns a different object (copy vs mutation), the snapshot comparison must operate on the correct objects. Developer must verify whether `recompute_all()` mutates the input list or returns a new list — the status_engine source shows it returns a new list for dict inputs and mutates Loan objects. Snapshot must therefore be taken from the pre-call list before objects are mutated.

**Updated Backlog Item:**
- As a user, clicking Refresh in the View Tab does not trigger any CSV write operations when no loan status has changed since last load.
- Acceptance: Application log shows zero "Loan updated" entries after a Refresh where no status changes occurred.

---

## PO Decision: BUG-UTR-4 — Date Picker Opens Only on Arrow Click

**Decision:** Accept — P2

**Business Rationale:** R1 states "a calendar widget for date-picker is needed." The current implementation requires clicking the small dropdown arrow on the right edge of the QDateEdit field — unintuitive for non-technical users. The user explicitly flagged this. R10 requires minimum dependency resolution for Windows users; a confusing UI undermines adoption.

**Scope Impact:** Create `ui/widgets.py` with `ClickableDateEdit(QDateEdit)` subclass that overrides `mousePressEvent` to trigger `showCalendarWidget()`. Apply to all QDateEdit usages in the application: `entry_tab.py` (giving_date, due_date), `paidoff_dialog.py` (date_edit), and any other QDateEdit instances found in dialogs. The user forbids OS drift — this fix must apply identically on Windows and Mac.

**Timeline Impact:** Estimated 0.5 days to create the subclass and apply across the codebase.

**Risk:** Qt calendar popup behaviour on different platforms may vary slightly with `mousePressEvent` override — developer must test on both Windows and Mac. If platform-specific Qt event handling causes issues, the fallback is to set `self.setFocusPolicy(Qt.ClickFocus)` and call `showCalendarWidget()` in `focusInEvent` instead.

**Updated Backlog Item:**
- As a user, clicking anywhere on the date field (not just the dropdown arrow) opens the calendar popup.
- Acceptance: Single click on the text area of any date field opens the calendar. Behaviour is identical on Windows and Mac.

---

## PO Decision: BC-301 — Paidoff Warning Label Placement (Default Accepted)

**Decision:** Accept — option (a) — Proceed

**Business Rationale:** run_3 BC-301 offered option (a) as default with a 24-hour response window. No user response was received. Per run_3 protocol: "If user does not respond, implementation proceeds with option (a)." The warning text from R3 is exact: "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied." Option (a) places it below report header, above records table — the most visible and contextually correct position.

**Scope Impact:** Backend developer must read `pending_approval_tab.py` `_build_ui()` before implementing to locate the bottom panel (QSplitter, bottom widget, above QTableWidget for records). Insert a styled QLabel, hidden by default, shown only when selected report mode == "Paidoff".

**Timeline Impact:** Estimated 0.5 days including the file read and insertion.

**Risk:** TC-303 from run_3 required developer to read the file first — this remains the pre-condition for correct placement. Not a user risk.

**Updated Backlog Item:**
- As a user, when I select a Paidoff report in the Pending Approval Tab, I see the warning message "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied." displayed above the records table.
- Acceptance: Warning is visible for mode="Paidoff" reports; hidden for all other report modes.

---

## PO Decision: CHG-02-EXT — PaidoffDialog Rate Fields (Implementation Gap)

**Decision:** Accept — Must implement in run_4

**Business Rationale:** PD-R3-01 in run_3 accepted CHG-02-EXT. R3 is explicit: "the dialog box should also ask for interest_rate, commission_rate and tds_flag values to generate appropriate calculation report." Source inspection of `paidoff_dialog.py` confirms this was never implemented — the dialog only has a date picker. This is an unimplemented accepted requirement from Phase 3 that blocks Phase 3 closure.

**Scope Impact:** Extend `PaidoffDialog` to include:
- `interest_rate` input (QDoubleSpinBox, 0–100%, default 12.0)
- `commission_rate` input (QDoubleSpinBox, 0–100%, default 2.0)
- `tds_flag` checkbox (default unchecked/False)
- `extension_period` derived from: `paidoff_date - due_date` in days (per R3: "extension_period(days) = paidoff_date - due_date")
- On acceptance: generate a Daily-mode report (mode="Paidoff") via the report pipeline and send to Pending Approval queue
- Display the R3 warning message in the Pending Approval Tab for this report (BC-301, handled separately)

**Timeline Impact:** Estimated 1 day — requires wiring PaidoffDialog output to the report generation pipeline.

**Risk:** If the loan has no due_date, `paidoff_date - due_date` is undefined. Business rule needed: [REVIEW REQUIRED — TC-401] What is the extension_period for a Paidoff loan with no due_date? Options: (a) extension_period = 0 days, interest = 0; (b) user must provide extension_period manually in the dialog; (c) use today as the reference date (paidoff_date - today). R3 does not cover this edge case. Default: proceed with option (a) — extension_period = 0, interest = 0 for no-due-date loans — unless user specifies otherwise.

**Updated Backlog Item:**
- As a user right-clicking a loan and selecting Mark Paidoff, the dialog asks for: paidoff_date, interest_rate, commission_rate, and TDS flag (in addition to the date).
- On confirm: a Paidoff-mode Daily interest report is generated and sent to Pending Approval queue.
- Acceptance: Dialog collects all 4 inputs. Report appears in Pending Approval with mode="Paidoff" and correct Daily interest calculation (Amount * interest_rate * extension_period_days) / (365 * 100).

---

## PO Escalation: BC-03 — Phase 4 Scope (STILL OPEN — User Input Required)

**Decision:** ESCALATE — Cannot resolve from requirements

**Business Rationale:** Requirements list three Phase 4 candidates (R6, R9, QComboBox StatusDelegate) without specifying relative priority. The PO cannot determine which delivers more business value to this specific user without explicit input. Both tracks deliver real value; the choice depends on the user's current workflow pain.

**Options Remaining:**

| Option | Description | Effort Estimate | Business Value |
|---|---|---|---|
| A | R6: Import/export (csv/xlsx) + Year→Month date hierarchy filter in View Tab | High (~7 days) | High — enables historical data loading and external reporting |
| B | R9: Alternate theme chooser (2 themes, preference-based) | Medium (~4 days) | Medium — UX polish, not workflow-critical |
| C | QComboBox StatusDelegate in View Tab (inline status toggle) | Medium (~2 days) | Medium — UX convenience |
| D | A + C (skip B) | High (~9 days) | High — full import/export + inline status |
| E | B + C (skip A) | Medium (~6 days) | Medium — UX focus |

**PO recommendation if user does not respond within the next run:** Default to Option D (R6 + QComboBox StatusDelegate) per the run_3 BC-03 note: "If no response, Phase 4 will default to Option A (R6 import/export) as the primary focus, with C as secondary."

**User question:** Please select one of the 5 options above (A, B, C, D, or E) for Phase 4 scope. If no response before run_5, Option D (A+C) will be used as the default.

**Impact if not resolved:** Phase 4 sprint plan cannot be finalised. Phase 4 implementation cannot begin.

---

## PO Decisions Summary Table — run_4

| ID | Item | Decision | Rationale | Blocks |
|---|---|---|---|---|
| PD-R4-01 | BUG-UTR-1: Filter dropdown reset | Accept P1 | R5 functional requirement broken | Phase 3 close |
| PD-R4-02 | BUG-UTR-2: Duplicate reference IDs | Accept P1 | R4 uniqueness contract violated | Phase 3 close |
| PD-R4-03 | BUG-UTR-3: Refresh overwrites all records | Accept P1 | Data integrity risk on every Refresh | Phase 3 close |
| PD-R4-04 | BUG-UTR-4: Date picker single-click | Accept P2 | R1 calendar widget UX requirement | Phase 4 start |
| PD-R4-05 | BC-301: Paidoff warning label option (a) | Accept — proceed | Default accepted, no user response needed | BC-301 resolved |
| PD-R4-06 | BC-03: Phase 4 scope | Escalate | Cannot determine user's priority from requirements | Phase 4 planning |
| PD-R4-07 | CHG-02-EXT: PaidoffDialog rate fields | Accept — must implement run_4 | PD-R3-01 accepted in run_3 but code was never written | Phase 3 close |

---

## TC-401 — PaidoffDialog No-Due-Date Edge Case

**Classification:** Technical Clarification (new, raised by PD-R4-07 analysis)
**Priority:** Low
**Description:** When marking a loan Paidoff where `due_date` is None, `extension_period = paidoff_date - due_date` is undefined. R3 does not specify this case.
**Default:** Proceed with extension_period = 0 days (interest = 0) for no-due-date Paidoff loans unless user specifies otherwise.
**User question (optional):** If a loan has no due date and is marked Paidoff, should the interest calculation use (a) extension_period = 0, interest = 0; or (b) the user manually enters extension_period in the dialog?

---

## Resolved Items from run_3 (Closed in run_4)

| Item | run_3 Status | run_4 Resolution |
|---|---|---|
| BC-301 | Open — user not required to respond; option (a) default | Closed — option (a) proceeding |
| TC-303 | Developer action pre-condition | Closed — subsumed into PD-R4-05 implementation task; dev reads file before implementing |
| CHG-02-EXT (PD-R3-01) | Accepted in run_3 docs | Re-opened — source confirms not coded; added as PD-R4-07 |

---

## PO Wave 3 Synthesis — run_4 (Post All-Wave Review)

**Wave 3 date:** 2026-04-04
**Inputs reviewed:** pm-agent, bsa-agent, sa-agent, dm-agent, sre-agent, dev-lead-agent, qa-lead-agent, backend-dev-agent, backend-qa-agent, uat-agent

### Implementation Status at Wave 3

All 6 run_4 scope items have been fully implemented in source code. 197 baseline tests pass. The code is ready for user acceptance testing.

| ID | Item | Implementation | Tests |
|---|---|---|---|
| BUG-UTR-1 | Filter dropdown reset | DONE — `_on_apply_filters()` fixed | 197 green |
| BUG-UTR-2 | Duplicate reference IDs | DONE — Fix A (bucket) + Fix B (atomic write) | 197 green |
| BUG-UTR-3 | Refresh overwrites all records | DONE — snapshot + conditional write + SRE log | 197 green |
| BUG-UTR-4 | Date picker single-click | DONE — `ui/widgets.py` ClickableDateEdit | 197 green |
| BC-301 | Paidoff warning label | DONE — QLabel in pending_approval_tab.py | 197 green |
| CHG-02-EXT | PaidoffDialog rate fields + report pipeline | DONE — dialog + view_tab._action_paidoff() | 197 green |

### [REVIEW REQUIRED] Item Deduplication — Wave 3 Binding Decisions

Agents produced 15 raw [REVIEW REQUIRED] references across 10 skill output files. After deduplication these collapse to 5 unique items:

**PO-BIND-01 (TC-401) — No-due-date Paidoff extension_period**
Raised by: PO (Wave 0), BSA (Wave 1), DM (Wave 1), QA Lead (Wave 2), UAT (Wave 3) — 6 instances.
**Binding PO decision:** Proceed with option (a) — extension_period = 0, interest_amount = 0, commission_amount = 0 for loans with no due_date when marked Paidoff. This is already implemented. The behaviour must be clearly documented in UAT-06. User confirmation is requested to formally close this; if no response before run_5, option (a) is the permanent default.

**PO-BIND-02 (SA-401) — history.csv in `_active_year_months()` scope**
Raised by: SA (Wave 1), DM (Wave 1), Dev Lead (Wave 2), Backend Dev (Wave 2) — 6 instances.
**Binding PO decision:** Deferred to Phase 4. The risk is limited: a counter reset only occurs when ALL loans for a given month have been archived to history.csv AND a new entry is made for that same month in a later session. This is a low-frequency scenario with a bounded impact (reference_id collision with a historically archived record). The current implementation (loans.csv only) is acceptable for Phase 3. Phase 4 scope note added below.

**PO-BIND-03 (BC-03) — Phase 4 feature scope selection**
Raised by: PM (Wave 0), UAT (Wave 3) — 2 instances.
**Binding PO decision:** ESCALATE TO USER. Cannot be resolved without user input. Default if no response before run_5: Option D (R6 import/export + QComboBox StatusDelegate). This is the highest-value combination per PO recommendation.

**PO-BIND-04 (SRE-001) — Startup recovery.tmp detection**
Raised by: SRE (Wave 1) — 1 instance.
**Binding PO decision:** Deferred to Phase 4. Risk is rare (requires a crash between the two writes of the Paidoff two-write protocol). Manual recovery via history.csv inspection is documented in the SRE runbook. Phase 4 scope note: add a startup check that reads recovery.tmp, presents a guided recovery dialog, and offers the user a single-click resolution path.

**PO-BIND-05 (UAT-01-EDGE) — Filter fallback when selected value is deleted**
Raised by: UAT (Wave 3) — 1 instance.
**Binding PO decision:** Accepted as designed behaviour. When a loan is deleted and its group/name value is no longer in the combo, `setCurrentText()` silently falls back to "All". This is explicitly documented by Dev Lead as an acceptable edge case. No change required. UAT must document this as known behaviour, not a defect.

### Phase 3 Closure Verdict

**Phase 3 is CLOSED.** All 6 scope items are implemented and the 197-test baseline is preserved. Two items (SA-401 and SRE-001) are formally deferred to Phase 4 with documented risk levels. One item (BC-03) requires user input before Phase 4 can begin.

### Phase 4 Kickoff Pre-conditions

| Pre-condition | Status |
|---|---|
| BC-03 user decision (Phase 4 scope) | REQUIRED — user must respond |
| SA-401 Phase 4 scoping (history.csv inclusion) | Recommended — user to confirm option (a) or (b) |
| UAT-01 through UAT-06 user acceptance sign-off | Recommended before Phase 4 start |
| TC-401 user confirmation (no-due-date default) | Optional — current default is option (a) |

### PO TLDR

Phase 3 is complete. The Loan Manager application has had four production bugs fixed and two features implemented: the filter dropdown now works correctly, reference ID generation is duplicate-free and crash-safe, the Refresh button no longer overwrites unchanged records, date pickers open on a single click anywhere on the field, a Paidoff warning label appears in the Pending Approval tab for archived loans, and the Mark Paidoff dialog now collects interest rate, commission rate, and TDS flag to generate a full interest report. All 197 automated tests are green. The code is ready for user acceptance testing on Windows.

Two questions require the user's answer before Phase 4 can begin. First: which Phase 4 feature set do you want — please select option A (import/export), B (themes), C (inline status toggle), D (import/export + inline status), or E (themes + inline status)? Second: for a loan with no due date that you mark as Paidoff, should the system use zero interest (current behaviour), or should the dialog ask you to enter the extension period manually? If you do not respond, the current defaults (option D for Phase 4 scope, zero interest for no-due-date Paidoff) will be used in run_5.
