# Prompt.md — Stage Execution Prompt (Bug Fixes + Reporting Enhancements)

## Role

You are a **Senior Staff Software Engineer**, **Technical Architect**, **QA Engineer**, and **UX Engineer** working on the **Loan Manager** application.

You have been provided with the complete project specification in `LoanManager.md`.

Your responsibility is **NOT** to redesign the application. Instead, you must preserve all existing business logic while fixing the reported defects and improving the reporting functionality.

You must think and work like an engineer responsible for maintaining a production financial application.

---

# Objective

Implement the following fixes and enhancements while ensuring:

* no existing functionality is broken
* all current calculations remain unchanged
* database schema remains compatible unless explicitly required
* code quality is improved where appropriate
* UI behaviour is intuitive and consistent
* all reports are printable in a professional banking-style format

---

# Execution Rules

## Work in a Single Stage

Only execute the work described in this prompt.

When complete:

1. Stop execution.
2. Produce a detailed implementation summary.
3. List every modified file.
4. List every newly created file.
5. Explain every architectural decision.
6. Explain any assumptions made.
7. Provide manual QA test cases.
8. Wait for user approval.

Do **NOT** begin any additional work until the user replies with one of:

* Proceed
* Proceed with modifications

If the user selects **Proceed with modifications**, first review the requested changes, incorporate them into the current stage, verify everything again, and only then stop for another review.

---

# Development Standards

All code must:

* be production-ready
* follow existing project architecture
* follow SOLID principles
* avoid duplicated logic
* be modular
* be strongly typed where applicable
* include defensive programming
* include meaningful logging
* preserve backwards compatibility

---

# Mandatory Verification

Before considering the work complete, verify:

* filtering
* sorting
* printing
* pagination
* report generation
* PDF generation
* edge cases
* empty datasets
* null values
* invalid inputs

Do not assume anything works.

Test it.

---

# Issue 1 — View Tab Filtering UI Is Broken

## Existing Problems

The filtering UX behaves inconsistently.

Example:

* Click **B Name**
* Select one value
* Checkbox does not appear
* Clicking the selected value again does not remove the selection
* UI state becomes inconsistent

---

## Expected Behaviour

Every filter should behave like a standard spreadsheet filter.

Requirements:

* clicking an item selects it
* selected item immediately shows a checkbox
* clicking again deselects it
* checkbox state always matches internal filter state
* multiple selections supported
* "Select All" behaves correctly
* "Clear Filter" works
* filter state persists while interacting with the page
* visual state always reflects actual filter state

No UI desynchronization is allowed.

---

## Validation

Verify:

* zero selections
* one selection
* multiple selections
* deselect all
* select all
* rapidly clicking values
* switching between filters

---

# Issue 2 — Date Filtering Logic Is Incorrect

Current behaviour:

Checkbox appears correctly.

Filtering does not.

Example:

Selecting

```
2026-05
```

returns zero rows even though records exist.

---

## Investigate

Determine root cause.

Potential causes include:

* string comparison
* timestamp parsing
* locale conversion
* timezone conversion
* incorrect formatter
* filter predicate
* stale state
* memoization issue

Do not patch blindly.

Find the actual defect.

---

## Requirements

Filtering must support:

* exact month
* exact year
* exact date
* multiple month selections
* combined filters
* sorting after filtering
* filtering after sorting
* clearing filters

---

## Edge Cases

Verify:

* empty dates
* null dates
* duplicate dates
* future dates
* leap year
* timezone boundaries

---

# Issue 3 — Print Support for View Tab

The View Tab currently lacks proper reporting.

Add:

```
Print
```

button.

---

## Requirements

The printed report must reflect exactly what the user currently sees.

Meaning:

If filters are active:

Print only filtered rows.

If sorting is active:

Maintain sorting.

If filters cleared:

Print complete report.

---

## Print Output

Professional table.

Include:

* title
* report generation timestamp
* applied filters
* page numbers
* total records
* table headers
* table body

No debug fields.

No hidden columns.

No raw JSON.

---

# Issue 4 — Pending Approval Report Format

Current implementation prints raw calculated report data grouped by report_id.

This is not acceptable.

Replace with borrower-centric grouped report.

---

## Required Structure

For each borrower:

```
Borrower Name

------------------------------------------------

Amount

Giving Date

Depositor

Extension Period

Extension Unit

Due Date

Interest Amount

TDS

CHQ Amount

Commission

------------------------------------------------

record

record

record

...

Totals

Total Amount

Total Interest

Total Commission

Total TDS

================================================
```

Repeat for every borrower.

---

## Requirements

Borrowers sorted alphabetically.

Within borrower:

Sort by Giving Date.

Totals calculated independently.

No duplicated records.

No hidden records.

No report_id grouping.

---

## Totals

Calculate:

Total Principal

Total Interest

Total Commission

Total TDS

Display clearly.

---

# Issue 5 — Improve Print / PDF Quality

Current print layout:

* inconsistent spacing
* poor typography
* clipping
* unreadable columns
* poor scaling

This must be redesigned.

---

## Requirements

PDF should resemble professional financial reports.

Use:

* A4 portrait where feasible
* Automatically switch to landscape when required by column count
* Consistent margins
* Readable font sizes (10–12 pt body, larger headings)
* Clear table borders
* Proper row spacing
* Alternating row shading (if supported)
* Repeating table headers on new pages
* Automatic page numbering
* Report title and generation timestamp on every report

---

## Pagination

Large reports should:

* never cut rows in half
* split cleanly across pages
* repeat headers
* preserve totals

---

## PDF

Ensure:

* PDF export matches browser print layout
* No clipped columns
* No overlapping text
* Proper scaling to A4
* Embedded fonts where supported
* Consistent rendering across Chrome, Edge, and PDF viewers

---

# Additional Functional Requirements

## Active Filter Summary

Display active filters above the table.

Example:

```
Borrower:
John Smith

Date:
2026-05

Depositor:
RBC
```

These active filters must also appear in printed/PDF reports.

---

## Empty Results

When filters return no data:

Display:

```
No matching records found.
```

Printing should also produce a professional report indicating that no records matched the selected filters, while still listing the active filters.

---

## Accessibility

Ensure:

* keyboard navigation works
* focus indicators remain visible
* checkbox controls are accessible
* print buttons include accessible labels
* sufficient color contrast is maintained

---

# Testing Requirements

Perform comprehensive verification for:

## Filtering

* Borrower filter
* Date filter
* Depositor filter
* Multiple filters
* Clearing filters
* Select All
* Deselect All
* Rapid repeated selections
* Combined filter scenarios

---

## Printing

Verify:

* All records
* Filtered records
* Empty datasets
* Large datasets
* Multi-page reports
* Landscape mode
* Portrait mode
* Browser print preview
* PDF export fidelity

---

## Regression Testing

Confirm that the following continue to function correctly after changes:

* Loan calculations
* Interest calculations
* Commission calculations
* TDS calculations
* Pending Approval workflows
* Existing reports
* CRUD operations
* Search
* Sorting
* Pagination
* Data persistence

---

# Deliverables

At completion, provide:

1. Executive summary of all implemented fixes.
2. Root cause analysis for each reported bug.
3. Complete list of modified files.
4. Complete list of new files.
5. Architectural rationale for significant changes.
6. Manual QA checklist covering all scenarios.
7. Any known limitations or recommendations.

Then stop execution and wait for user review.

Do not proceed with any unrelated enhancements until explicit approval is received.
