# BSA: Business Requirements — Loan Manager run_2
**Date:** 2026-04-03
**Run:** run_2 / Wave 1
**Author:** BSA Agent
**Scope:** Delta changes only — 7 change items (CHG-01, CHG-02, BUG-01–04, DOC-01)

---

## 1. Change Area: CHG-01 — No Due Date Default Checked (R1)

### Functional Requirements
- FR-R2-01: The "No Due Date" checkbox in the New Loan Entry form SHALL default to the checked state when the form is first rendered.
- FR-R2-02: The "No Due Date" checkbox SHALL default to the checked state after a successful loan submission resets the form.
- FR-R2-03: When "No Due Date" is checked, the Due Date field SHALL be disabled and its value SHALL be ignored on submission.

### User Story

**Story CHG-01: Default No Due Date**
As a loan operator,
I want the "No Due Date" checkbox to be pre-checked when I open the entry form,
So that I do not have to manually check it every time I enter a loan without a due date.

**Acceptance Criteria:**
- Given the New Loan Entry tab is loaded, When the form renders, Then the "No Due Date" checkbox is checked and the Due Date field is disabled.
- Given a loan has been saved and the form resets, When the form is ready for the next entry, Then the "No Due Date" checkbox is checked and the Due Date field is disabled.
- Given the "No Due Date" checkbox is checked, When I submit the form, Then the saved loan record has `due_date = null` in storage.
- Given the "No Due Date" checkbox is unchecked, When I enter a date and submit, Then the saved loan record has the entered `due_date` in storage.

---

## 2. Change Area: CHG-02 — Paidoff Generates Daily Interest Report (R3 + R5)

### Functional Requirements
- FR-R2-04: When a user marks a loan as Paidoff and provides a `paidoff_date`, the system SHALL generate an interest report using Daily Calculator mode.
- FR-R2-05: The `extension_period_days` for the report SHALL be computed as `max(0, (paidoff_date - due_date).days)`.
- FR-R2-06: If the loan has no `due_date`, the system SHALL skip report generation and log a warning. The Paidoff write SHALL still complete.
- FR-R2-07: The generated report SHALL be placed in the Pending Approval queue with mode = "Daily" and status = "Pending".
- FR-R2-08: If report generation fails (e.g., file write error) AFTER the Paidoff write succeeds, the system SHALL display a non-blocking warning to the user. The Paidoff write SHALL NOT be rolled back.
- FR-R2-09: The report record SHALL use the loan's `interest_rate` and `commission_rate` from existing global defaults (12% and 2% respectively as the form defaults), since the user does not supply these at paidoff time. **[REVIEW REQUIRED — BC-05]:** Should the user be prompted for `interest_rate` and `commission_rate` at paidoff time, or should defaults be used? Requirements do not specify input collection for these values during Paidoff.

### User Story

**Story CHG-02: Paidoff Interest Report**
As a loan operator,
I want an interest report to be automatically generated when I mark a loan as Paidoff,
So that the interest owed for the extension period is captured for approval without manual re-entry.

**Acceptance Criteria:**
- Given a loan with `due_date = 2026-04-01` is marked Paidoff with `paidoff_date = 2026-05-01`, When the Paidoff dialog is confirmed, Then a Daily-mode report is created in the Pending Approval queue with `extension_period_days = 30`.
- Given a loan with `due_date = 2026-04-01` is marked Paidoff with `paidoff_date = 2026-04-01` (same day), When the Paidoff dialog is confirmed, Then a Daily-mode report is created with `extension_period_days = 0` and `interest_amount = 0.00`.
- Given a loan with `due_date = 2026-04-01` is marked Paidoff with `paidoff_date = 2026-03-15` (early payoff), When the Paidoff dialog is confirmed, Then a Daily-mode report is created with `extension_period_days = 0` (PD-R2-02 decision: negative clamped to 0).
- Given a loan with no `due_date` is marked Paidoff, When the Paidoff dialog is confirmed, Then the Paidoff write completes and NO report is generated. A warning log entry is written.
- Given report generation fails after the Paidoff write succeeds, When the error occurs, Then the user sees a warning dialog. The loan record IS in history.csv. The View Tab no longer shows the loan.
- Given the Paidoff report is generated, When the user opens Pending Approval, Then the report appears with the paidoff loan's reference_id, borrower name, amount, and calculated interest.

### Open Questions
- **[REVIEW REQUIRED — BC-05]:** Should the PaidoffDialog be extended to collect `interest_rate` and `commission_rate` from the user at paidoff time? The current requirements do not specify this input step.
- **[REVIEW REQUIRED — BC-06]:** Should the paidoff report in the Pending Approval queue auto-decline if the user declines it, or is the intention that approving the report updates anything? At paidoff time, the loan is already moved to history.csv. Approving the report would attempt to batch-extend the loan — but the loan is no longer in loans.csv. This creates a semantic conflict. The report may need a new "FYI" status rather than triggering the normal approval extension flow.

---

## 3. Change Area: BUG-01 — Interest Calculator Filter Reset

### Functional Requirements
- FR-R2-10: When the user selects a non-"All" value in any Interest Calculator filter and clicks "Apply Filters", the selected filter value SHALL persist and the table SHALL show only matching records.
- FR-R2-11: After applying filters, the filter combo boxes SHALL display the user's selected values (not reset to "All").
- FR-R2-12: If a selected filter value no longer exists after data reload (e.g., a borrower was deleted), that filter SHALL revert to "All".

### User Story

**Story BUG-01: Filter Persistence**
As a loan operator,
I want the filter values I select to stay selected after I click Apply Filters,
So that I can see the filtered records I asked for rather than being shown all records.

**Acceptance Criteria:**
- Given the Interest Calculator tab has loans from borrower groups "bg1" and "bg2", When I select "bg1" in the Borrower Group filter and click Apply Filters, Then the Borrower Group filter shows "bg1" and the table shows only bg1 loans.
- Given filters are applied with BorrowerGroup="bg1" and BorrowerName="b1", When I click Apply Filters, Then both filters display their selected values and the table shows only matching records.
- Given I apply BorrowerGroup="bg1", When I click Apply Filters again without changing anything, Then the filter still shows "bg1" (no reset to All on re-apply).

---

## 4. Change Area: BUG-02 — View Tab Color Palette

### Functional Requirements
- FR-R2-13: Status row colors in the View Tab SHALL use sufficient contrast so that text is readable without additional user configuration.
- FR-R2-14: The foreground text color SHALL be explicitly set (not inherited from system default) when a background color is applied.

### User Story

**Story BUG-02: Readable Color Palette**
As a loan operator,
I want the View Tab rows to use colors where I can clearly read the text,
So that I can identify loan statuses at a glance without straining to read light-on-light text.

**Acceptance Criteria:**
- Given the View Tab displays Active loans, When I look at the row, Then the status row background and text are clearly distinguishable (high contrast).
- Given the View Tab displays Overdue loans, When I look at the row, Then the overdue row is visually distinct from Active rows and text is legible.
- Given the application runs on Windows with default system settings, When rows are displayed, Then text color is explicitly set per row (not inherited from OS theme).

---

## 5. Change Area: BUG-03 — Paidoff Marking Flow

### Functional Requirements
- FR-R2-15: The user SHALL be able to mark a loan as Paidoff through the View Tab's context menu (right-click → "Mark Paidoff").
- FR-R2-16: When "Mark Paidoff" is selected, a dialog SHALL prompt for `paidoff_date`.
- FR-R2-17: After confirming Paidoff, the loan SHALL be removed from the View Tab and moved to history.csv.
- FR-R2-18 (Phase 4): **[REVIEW REQUIRED — BC-04]:** The Status column SHOULD support inline QComboBox editing for all status transitions including Paidoff. For Phase 3, context menu is the accepted path.

### User Story

**Story BUG-03: Paidoff via Context Menu**
As a loan operator,
I want to right-click a loan record and select "Mark Paidoff" to trigger the paidoff workflow,
So that I can complete the full loan lifecycle from the View Tab.

**Acceptance Criteria:**
- Given the View Tab shows loan "2026_03_001", When I right-click the row and select "Mark Paidoff", Then the PaidoffDialog opens prompting for paidoff_date.
- Given the PaidoffDialog is open, When I select a date and click OK, Then the loan is removed from the View Tab and appears in history.csv.
- Given BUG-02 is fixed (readable colors), When I look at the View Tab, Then I can identify and right-click the correct row.

---

## 6. Change Area: BUG-04 — Windows Date Picker Click Behavior

### Functional Requirements
- FR-R2-19: Date input fields (Giving Date, Due Date in Entry Tab; Paidoff Date in PaidoffDialog; Extension dates in ExtendDialog) SHALL open the calendar popup when the user clicks anywhere in the field.
- FR-R2-20: The calendar popup SHALL NOT require the user to click a specific dropdown arrow button to open.

### User Story

**Story BUG-04: Date Picker Click to Open**
As a Windows user,
I want to click on any date field to open the calendar,
So that I can pick a date without needing to find and click a small dropdown arrow.

**Acceptance Criteria:**
- Given the New Loan Entry tab is open on Windows, When I click the Giving Date field (not the arrow), Then the calendar popup opens.
- Given the PaidoffDialog is open, When I click the Paidoff Date field, Then the calendar popup opens.
- Given the ExtendDialog is open, When I click the date preview area, Then behavior is consistent (ExtendDialog uses SpinBox+Combo, not DateEdit — verify no regression).

---

## 7. Change Area: DOC-01 — Import Parser DD-MM-YYYY (Confirmed Code Bug)

### Functional Requirements
- FR-R2-21: The loan import parser SHALL accept date fields in both ISO 8601 format (`YYYY-MM-DD`) and DD-MM-YYYY format.
- FR-R2-22: When parsing an imported date in DD-MM-YYYY format, the system SHALL correctly interpret it (e.g., `02-01-2026` = January 2nd 2026).
- FR-R2-23: All dates SHALL be stored internally in ISO 8601 format regardless of input format.
- FR-R2-24: A malformed date that cannot be parsed in either format SHALL be treated as a parse failure, the row SHALL be skipped with a WARNING log, and an `ImportResult.skipped` counter SHALL be incremented.

### User Story

**Story DOC-01: Flexible Date Import**
As a loan operator,
I want to import a CSV file with dates in DD-MM-YYYY format,
So that I can import the sample data format directly without reformatting.

**Acceptance Criteria:**
- Given an import CSV with `giving_date = "02-01-2026"`, When the import runs, Then the loan is created with `giving_date = 2026-01-02` in storage.
- Given an import CSV with `giving_date = "2026-01-02"` (ISO format), When the import runs, Then the loan is created with `giving_date = 2026-01-02` in storage (backward compatibility maintained).
- Given an import CSV with `giving_date = "invalid-date"`, When the import runs, Then the row is skipped and logged as a warning.

---

## 8. BSA → DM Data Requirements Brief

**Feature:** CHG-02 Paidoff Report Generation

**Business entities involved:**
- `PendingReport` (existing) — one report created per Paidoff event
- `ReportRecord` (existing) — one line item per paidoff loan

**Key attributes for CHG-02 report record:**
- `extension_period`: integer, `max(0, (paidoff_date - due_date).days)`
- `extension_period_unit`: "days" (fixed for Paidoff reports)
- `mode`: "Daily" (fixed for Paidoff reports)
- `interest_rate`: default value (12.0) — [REVIEW REQUIRED BC-05] user may want to provide this
- `commission_rate`: default value (2.0) — [REVIEW REQUIRED BC-05] same
- `tds_flag`: false (default) — [REVIEW REQUIRED BC-05] same

**Data not stored in report:** `paidoff_date` itself is stored in `history.csv` under the loan record. The report does not store `paidoff_date` explicitly — only `extension_period_days` derived from it.

**[REVIEW REQUIRED — BC-06]:** When a Paidoff report in Pending Approval is approved, the batch-extend logic will look for the loan in `loans.csv` — but the loan was already moved to `history.csv` by `mark_paidoff()`. The approval will trigger the "Records in this report have been deleted" warning. This is architecturally awkward. DM and SA should flag this to PO.

**Schema changes required:** None. Existing `pending_reports.csv` and `pending_report_records.csv` schemas accommodate the Paidoff report without modification.
