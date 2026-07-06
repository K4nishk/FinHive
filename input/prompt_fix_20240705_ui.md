# Prompt.md — Iteration 2 (Targeted Bug Fixes, Print Layout Improvements & Regression Validation)

## Role

You are acting as a **Senior Staff Software Engineer**, **Software Architect**, **QA Lead**, and **UI/UX Engineer** responsible for maintaining a production-grade financial application.

The previous implementation has already addressed the majority of the requested functionality. **This iteration is strictly a corrective refinement** based on QA findings.

Your objective is to **fix only the issues listed below** while preserving all existing functionality.

---

# Primary Goal

Implement the requested fixes **without introducing regressions**.

This is **not** a refactor or redesign task.

Do **not** replace working implementations.

Instead:

* identify the precise root cause of each issue
* make the smallest safe change necessary
* preserve existing business logic
* preserve all report calculations
* preserve current filtering behaviour
* preserve printing behaviour except where explicitly modified

---

# Engineering Principles

All changes must follow senior engineering practices.

Specifically:

* SOLID principles
* Single Responsibility Principle
* DRY
* KISS
* minimal code changes
* reusable components where appropriate
* avoid duplicated rendering logic
* avoid duplicated filter state logic
* avoid introducing technical debt

Do **not** introduce hacks or UI-only workarounds that leave the underlying state inconsistent.

---

# Mandatory Investigation Before Coding

For every issue:

1. Identify the actual root cause.
2. Explain why the bug occurs.
3. Implement the fix.
4. Verify the fix using manual and edge-case testing.
5. Ensure no regressions are introduced.

Do **not** patch symptoms.

---

# Issue 1 — View Tab Print Layout Margin Improvements

## Current State

The View Tab print output is now functionally correct.

However:

* table spans almost the full width of the page
* right-most column is too close to the printable edge
* depending on printer/PDF viewer, content may be clipped

---

## Required Fix

Adjust the printable layout so that:

* there is a safe printable margin on the right side
* no values are clipped
* the table still utilizes as much page width as possible

Where appropriate:

* slightly reduce the left margin
* slightly increase usable printable width
* reserve a consistent right-side safety margin

The objective is to maximize usable space **without allowing any content to reach the page edge**.

---

## Requirements

Ensure:

* no column clipping
* no wrapped numeric values
* no hidden characters
* table remains centered
* page scaling remains consistent

Verify using:

* browser Print Preview
* generated PDF
* multiple page reports

---

# Issue 2 — Pending Approval Report Layout

## Current State

Borrower grouping works correctly.

Totals are correct.

However:

* headers wrap across multiple lines
* each record wraps into several text lines
* output no longer resembles a professional financial report

---

## Required Fix

Convert each borrower section into a proper table.

Expected layout:

Borrower Name

---

| Amount | Giving Date | Depositor | Extension | Unit | Due Date | Interest | TDS | CHQ | Commission |

|---------|-------------|-----------|-----------|------|----------|----------|-----|------|------------|

| Record 1 |

| Record 2 |

| Record 3 |

...

Totals

* Total Amount
* Total Interest
* Total Commission
* Total TDS

============================================================

Each record must occupy **exactly one table row**.

The header must occupy **exactly one table row**.

---

## Formatting Requirements

Columns should:

* auto-size intelligently
* wrap only if absolutely necessary
* prefer reducing font slightly rather than wrapping every cell
* maintain consistent alignment

Numeric columns:

* right aligned

Dates:

* centered

Names:

* left aligned

---

## Page Layout

Use the same margin philosophy as Issue 1.

Specifically:

* maximize printable width
* maintain a safe right margin
* avoid clipping
* repeat table headers on new pages

---

# Issue 3 — View Tab Filter Checkbox State Synchronization

Filtering itself is functioning correctly.

The issue is purely with UI state synchronization.

---

## Current Behaviour

Example:

User clicks:

Borrower A

Filtering works after Apply.

However:

checkbox does not immediately reflect selection.

---

Multiple selection:

Borrower A

Borrower B

Borrower C

Only Borrower C visually remains checked.

Internally:

all three are selected correctly.

UI:

only latest selection appears checked.

---

Select All:

Selecting:

Select All

does not visually update all checkboxes.

---

## Required Behaviour

The visual checkbox state must always represent the internal filter state.

Every interaction must remain synchronized.

---

## Verify

Single selection

Multiple selections

Select All

Clear All

Apply

Cancel

Re-open filter popup

Rapid clicking

Keyboard navigation

Switching between filters

---

## Important

Do **not** rewrite the filtering engine.

The filtering engine already behaves correctly.

Fix only the synchronization between:

* internal selection state
* rendered checkbox state
* Apply button state
* filter popup state

There must be a **single source of truth** for filter selections.

Avoid duplicated UI state.

---

# Issue 4 — Numeric Sorting for SNo

Current implementation performs string comparison.

Example:

1

10

11

2

20

3

instead of

1

2

3

10

11

20

---

## Required Fix

Detect numeric columns and perform numeric comparisons.

The SNo column must always sort numerically.

---

## Requirements

Ascending

Descending

Null values

Large numbers

Single digit

Double digit

Triple digit

Sorting after filtering

Filtering after sorting

Pagination after sorting

---

## Do Not

Do not break sorting behaviour for:

* text columns
* date columns
* currency columns

Only numeric columns should use numeric comparison.

---

# Regression Testing

After implementation, verify the following continue to function exactly as before.

## Filtering

* Borrower
* Depositor
* Dates
* Multiple filters
* Combined filters
* Select All
* Clear Filter
* Apply
* Cancel

---

## Sorting

* Numeric
* Text
* Dates
* Ascending
* Descending

---

## Printing

View Tab

Reports

Filtered reports

Large reports

Multi-page reports

Landscape

Portrait

PDF export

Browser print preview

---

## Reports

Borrower totals

Interest totals

Commission totals

TDS totals

Grouping

Ordering

Pagination

---

## Existing Business Logic

Confirm there are **no regressions** in:

* loan calculations
* due date calculations
* interest calculations
* commission calculations
* TDS calculations
* CRUD operations
* search
* pagination
* data persistence

---

# Deliverables

When complete, stop execution and provide:

1. Root cause analysis for each issue.
2. Summary of implemented fixes.
3. Complete list of modified files.
4. Explanation of why each modification was necessary.
5. Regression testing checklist with pass/fail results.
6. Manual QA scenarios executed.
7. Any remaining risks or observations.

Do **not** continue to unrelated improvements.

Await user review and approval before making any further changes.
