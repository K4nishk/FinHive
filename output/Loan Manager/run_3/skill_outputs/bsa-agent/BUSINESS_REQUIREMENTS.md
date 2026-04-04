# BSA: Business Requirements — Loan Manager run_3
**Date:** 2026-04-03
**Run:** run_3 / Wave 1
**Author:** BSA Agent
**Scope:** Delta changes only — 2 implementable items (CHG-02-EXT, BUG-02-REF)

---

## 1. Change Area: CHG-02 Extended — Paidoff Dialog with Rate Fields (R3)

### Context

Run_2 established that when a loan is marked Paidoff via right-click context menu, a Daily interest report is generated using `extension_period_days = paidoff_date - due_date`. The dialog previously only collected `paidoff_date`.

Run_3 requirement update (R3 text): The dialog must also ask for `interest_rate`, `commission_rate`, and `tds_flag` to generate an appropriate calculation report. These are per-event values (not global defaults). Run_2 open clarifications BC-04 and BC-05 are now resolved by this requirement change.

### Resolved Ambiguities (from run_2)

| ID | Item | Resolution |
|---|---|---|
| BC-04 | Right-click context menu vs QComboBox for Paidoff | Resolved: R3 text confirms right-click context menu ("A toggle option to Mark Paidoff when Right Click on the record") |
| BC-05 | Interest/commission rate source for Paidoff report | Resolved: dialog collects interest_rate, commission_rate, tds_flag per paidoff event |

### Functional Requirements

- FR-R3-01: The "Mark Paidoff" right-click context menu option in View Tab SHALL open a dialog (PaidoffDialog).
- FR-R3-02: PaidoffDialog SHALL include the following fields:
  - `paidoff_date`: Date picker, defaults to today (existing field — retained)
  - `interest_rate`: Floating-point input (QDoubleSpinBox), range 0.0–100.0, default 0.0, label "Interest Rate (%)"
  - `commission_rate`: Floating-point input (QDoubleSpinBox), range 0.0–100.0, default 0.0, label "Commission Rate (%)"
  - `tds_flag`: Checkbox, default unchecked (false), label "Apply TDS"
- FR-R3-03: On dialog acceptance, the Paidoff flow SHALL use the dialog-supplied `interest_rate`, `commission_rate`, and `tds_flag` values to generate the Daily interest report — not any globally configured defaults.
- FR-R3-04: The `extension_period_days = max(0, (paidoff_date - due_date).days)` rule from run_2 (PD-R2-02, BC-01 resolution) remains unchanged.
- FR-R3-05: The Pending Approval Tab SHALL display the following warning message on Paidoff-generated reports: "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied."
- FR-R3-06: If `loan.due_date is None`, the report generation SHALL be skipped (existing behaviour — no change). A WARNING is logged.
- FR-R3-07: Report generation failure SHALL NOT rollback the Paidoff write (existing non-blocking error behaviour — no change).

### User Stories

**Story CHG-02-EXT-01: Paidoff Dialog with Rate Collection**
As a loan operator,
I want the Mark Paidoff dialog to ask for interest rate, commission rate, and TDS flag,
So that the generated interest report uses the correct rates specific to this loan/depositor.

**Acceptance Criteria:**
- Given I right-click a loan record in View Tab, When I select "Mark Paidoff", Then a dialog appears with fields: Paidoff Date, Interest Rate (%), Commission Rate (%), Apply TDS checkbox.
- Given the dialog opens, When no values are changed, Then Interest Rate defaults to 0.0, Commission Rate defaults to 0.0, TDS checkbox defaults to unchecked.
- Given I enter interest_rate=12.0, commission_rate=2.0, tds_flag=true and click OK, Then the generated report record in pending_report_records.csv has interest_rate=12.0, commission_rate=2.0, tds_flag=true.
- Given I enter interest_rate=0.0 and paidoff_date = due_date, Then the generated report has interest_amount=0.0 and commission_amount=0.0.
- Given the dialog is cancelled (Cancel button), Then no Paidoff action is taken and no report is generated.

**Story CHG-02-EXT-02: Paidoff Report Warning in Pending Approval Tab**
As a loan operator,
I want to see a clear warning when reviewing a Paidoff-generated report in Pending Approval,
So that I know this report is for a closed loan and understand that no loan extension was applied.

**Acceptance Criteria:**
- Given a Paidoff-generated report is selected in the Pending Approval Tab, When the report detail is shown, Then the warning message "This report was generated for a Paidoff loan. The loan has been moved to history. No extension was applied." is displayed.
- Given a non-Paidoff report is selected, Then no such warning is displayed.

**[REVIEW REQUIRED — BC-301]:** The requirement states the warning "can be displayed" — it does not specify exactly where in the Pending Approval Tab UI (report header, info bar, inline label, tooltip). BSA recommends displaying it as a highlighted label directly below the report ID/date row when the report is selected. User to confirm preferred placement or accept the recommended default.

---

## 2. Change Area: BUG-02 Refined — Exact Status Color Codes (R6 / UT-R1)

### Context

Run_2 identified BUG-02 as unreadable View Tab colors (light backgrounds + white text) and recommended a dark palette. Run_2 deferred exact color confirmation to the user (BC-02). Run_3 requirement update provides exact hex codes — resolving BC-02.

### Resolved Ambiguities (from run_2)

| ID | Item | Resolution |
|---|---|---|
| BC-02 | Exact color palette for View Tab status rows | Resolved: user provided exact hex codes in requirements |

### Functional Requirements

- FR-R6-01: The View Tab status row colors SHALL use exactly the following background hex values:
  - Active: `#2d6a4f` (dark green)
  - Overdue: `#9b2226` (dark red)
  - Pending: `#ca6702` (dark amber)
  - Paidoff: `#495057` (dark grey)
- FR-R6-02: All status rows SHALL display white foreground text (`#ffffff`) regardless of status.
- FR-R6-03: The `STATUS_COLORS` dict in `ui/view_tab.py` SHALL be updated to use these exact values.
- FR-R6-04: The `_make_row()` method in `view_tab.py` SHALL explicitly set the foreground (text) color to white on each `QStandardItem` in colored rows.

### User Stories

**Story BUG-02-REF: Exact Status Row Colors**
As a loan operator,
I want loan status rows to use the specified dark background colors with white text,
So that the status of each loan is immediately readable without squinting.

**Acceptance Criteria:**
- Given the View Tab is loaded with Active, Overdue, Pending records, Then each row background matches the exact hex: Active=#2d6a4f, Overdue=#9b2226, Pending=#ca6702.
- Given any status row, When displayed, Then text is white (not system default).
- Given a record's status changes (e.g., due date edit makes Active → Overdue), Then the row color updates correctly to the new status color.

---

## 3. Removed Items (No Action Required)

### BUG-03 — Removed

**Previous:** "User was unable to test out marking a record as Paidoff" was tracked as a standalone bug.

**Disposition:** Removed from requirements. The issue was the absence of a clearly working Paidoff flow. CHG-02 and CHG-02-EXT together provide a fully specified Paidoff path (right-click → PaidoffDialog with all required fields → Daily report generation). No separate BUG-03 fix item is needed.

### Priority Section — Removed

**Previous:** `R5 > R4 > R1 > R2 > R3 > R6 > R8 > R7 > R10 > R9` appeared in REQUIREMENTS.md.

**Disposition:** Removed. No implementation impact. All downstream priority decisions remain with the PO.

---

## 4. Deep-Dive: CHG-02-EXT Complexity Analysis (R3 — Highest Complexity Item)

### Process Flow

```
User right-clicks loan row in View Tab
  -> Context menu: "Mark Paidoff"
  -> PaidoffDialog opens with 4 inputs:
       paidoff_date (date picker, default today)
       interest_rate (double spinbox, default 0.0)
       commission_rate (double spinbox, default 0.0)
       tds_flag (checkbox, default unchecked)
  -> User fills fields and clicks OK
  -> _action_paidoff() calls:
       mark_paidoff(loan.reference_id, dialog.paidoff_date())
       _generate_paidoff_report(loan, dialog.paidoff_date(), dialog.interest_rate(), dialog.commission_rate(), dialog.tds_flag())
  -> _generate_paidoff_report():
       Checks loan.due_date is not None
       extension_days = max(0, (paidoff_date - loan.due_date).days)
       record = { ..., interest_rate=dialog_value, commission_rate=dialog_value, tds_flag=dialog_value }
       calculate_daily(record) -> interest_amount, commission_amount, tds_amount
       generate_report_id() -> report_id
       write_report() -> pending_reports.csv entry
       write_report_records() -> pending_report_records.csv entry
  -> Pending Approval Tab shows report with warning message
```

### Data Contract (No Schema Change Required)

The `REPORT_RECORD_FIELDNAMES` already contains `interest_rate`, `commission_rate`, `tds_flag` fields. No CSV schema migration needed. The run_2 DM DATA_MODEL.md confirmed no schema changes for CHG-02; that finding extends to CHG-02-EXT.

### Edge Cases

| Edge Case | Handling |
|---|---|
| paidoff_date < due_date | extension_days = 0; report generated with 0 interest (PD-R2-02 BC-01 resolution — unchanged) |
| loan.due_date is None | Report generation skipped, WARNING logged (FR-R3-06 — unchanged) |
| interest_rate = 0.0, commission_rate = 0.0 | Report generated with interest_amount=0.0, commission_amount=0.0 (valid zero-charge paidoff) |
| tds_flag = true, interest_rate = 0.0 | TDS = 0.1 * 0.0 = 0.0 (correct per formula) |
| User cancels dialog | No action taken — dialog.exec() returns Rejected, _action_paidoff() returns early |

---

## 5. BSA [REVIEW REQUIRED] Summary

| ID | Item | Priority | Impact |
|---|---|---|---|
| BC-301 | Warning message placement in Pending Approval Tab | Medium | Affects UI implementation location; wrong choice reduces UX clarity |

