# Prompt.md — Principal Engineering Architecture Review (Cross-Platform Compatibility, Python Modernization & Report Computation Consistency)

## Role

You are acting as the **Principal Software Engineer**, **Software Architect**, **Cross-Platform Desktop Application Specialist**, and **Technical Lead** for the Loan Manager application.

This iteration is **not a feature implementation**. It is an **architecture review and focused remediation exercise** based on QA observations from the latest build.

The previous iteration successfully resolved the majority of the filtering architecture issues. Do **not** revisit or refactor previously resolved functionality unless your investigation proves it is directly responsible for one of the issues below.

Your responsibility is to:

1. Conduct a proper Root Cause Analysis (RCA).
2. Validate assumptions with the current codebase.
3. Produce a focused remediation plan.
4. Implement only the approved remediation.
5. Verify that no regressions are introduced.
6. Update the project documentation to reflect any architectural changes.

---

# Engineering Principles

All work must follow senior engineering standards.

* Root-cause driven, not symptom driven.
* Preserve existing business logic.
* Preserve backwards compatibility wherever practical.
* Minimize unnecessary code changes.
* Avoid introducing duplicate logic.
* Prefer architectural consistency over isolated fixes.
* Keep platform-specific behavior isolated where required.
* Ensure the solution remains maintainable and testable.

Do **not** implement workaround-based solutions.

---

# Phase 1 — Root Cause Analysis

Before making any code changes:

For each issue below:

* identify the true root cause
* identify the affected components
* identify whether the issue is architectural, implementation-specific, or platform-specific
* explain why the current implementation behaves the way it does
* explain why previous implementations did not expose the issue
* propose the smallest architectural change required to permanently resolve it

Only after completing the RCA should implementation begin.

---

# Issue 1 — macOS Filter UI State Synchronization

## Observation

The filtering architecture now behaves correctly on Windows.

However, on macOS:

* reopening filter popups does not consistently refresh checkbox state
* previously applied filters are not visually restored
* UI refresh behavior differs from Windows

Windows behaves correctly.

macOS does not.

This strongly suggests either:

* Qt platform-specific behavior
* repaint lifecycle differences
* model/view synchronization differences
* platform event ordering
* widget lifecycle differences

Do **not** assume the previous filter architecture is incorrect simply because one platform behaves differently.

---

## Investigation Requirements

Review:

* widget lifecycle
* popup lifecycle
* event ordering
* focus events
* paint/update events
* model/view synchronization
* Qt platform abstractions
* any macOS-specific code paths
* Python/Qt version differences, if applicable

Determine whether this is:

* rendering issue
* event issue
* model synchronization issue
* platform compatibility issue

---

## Expected Result

The filtering UI must behave identically on:

* Windows
* macOS

Previously applied filters must always be visually represented when the popup is reopened.

---

# Issue 2 — Python 3.13 / 3.14 Compatibility

## Observation

The application is currently not fully compatible with Python 3.13/3.14.

The application should support modern Python releases.

---

## Investigation

Review the project for:

* deprecated APIs
* removed stdlib modules
* typing incompatibilities
* packaging issues
* dependency compatibility
* PySide/PyQt compatibility
* build tooling
* virtual environment setup
* linting/tooling assumptions
* CI configuration (if present)

Determine whether incompatibility originates from:

* project code
* third-party libraries
* build configuration
* runtime assumptions

---

## Requirements

Produce a compatibility remediation plan.

Where practical:

* update code to modern Python idioms
* remove deprecated usage
* maintain compatibility with supported versions
* avoid unnecessary breaking changes

If a dependency currently blocks support, document it clearly and recommend the appropriate upgrade path.

---

# Issue 3 — Generated Report Uses Pre-Approval Values

## Business Observation

This is now considered a business correctness issue.

Current behavior:

Pending Approval report displays:

* original Giving Date
* original Due Date
After approval:

Business logic correctly updates:

Giving Date = previous Due Date

Due Date = previous Due Date + extension period

Interest = recalculated

Commission = recalculated

TDS = recalculated

The approval workflow itself is correct.

---

## Business Expectation

The Pending Approval report should already display the **computed values that will become effective after approval**, allowing the business user to review the actual post-approval outcome before committing it.

The report should therefore present the projected values rather than the currently persisted values.

---

## Investigation

Determine:

* how report data is currently sourced
* where calculations are performed
* whether calculations are duplicated
* whether approval performs recomputation or simply persists previously computed values
* whether report generation bypasses the calculation engine

The objective is to avoid duplicate business logic.

---

## Architectural Requirement

The report generation pipeline should leverage the same calculation engine used by the approval workflow.

Avoid maintaining two independent implementations of:

* due date calculation
* interest calculation
* commission calculation
* TDS calculation

There must be a single authoritative computation path.

---

## Expected Report Output

Before approval, the report should display:

* projected Giving Date
* projected Due Date
* projected Interest
* projected Commission
* projected TDS

These values should exactly match the values that will be persisted if the report is approved without modification.

The report becomes a true "preview of approval."

---

# Documentation Update

After implementation:

Update project documentation with:

## Cross-Platform Compatibility

Document:

* platform-specific considerations
* macOS behavior
* Windows behavior
* compatibility guarantees

---

## Python Compatibility

Document:

* supported Python versions
* required dependency versions
* compatibility notes
* known limitations (if any)

---

## Report Calculation Flow

Document:

* calculation ownership
* report generation workflow
* approval workflow
* shared calculation engine
* data flow from pending report to approval

Include an architecture diagram (Mermaid or equivalent) illustrating the relationship between:

* source loan data
* calculation engine
* pending report preview
* approval workflow
* persisted data

---

# Focused Remediation Plan

Before implementation, produce a concise remediation plan containing:

1. Root cause for each issue.
2. Proposed architectural change.
3. Components/files expected to change.
4. Risk assessment.
5. Regression impact analysis.
6. Testing strategy.

Only then proceed with implementation.

---

# Regression Validation

Confirm there are no regressions in:

## Filtering

* single selection
* multiple selection
* Apply
* Cancel
* Select All
* Clear
* reopening filter popup
* cross-platform behavior

---

## Reports

* borrower grouping
* totals
* formatting
* print output
* PDF generation
* calculated preview values
* approval values matching preview values

---

## Application

* loan calculations
* approval workflow
* CRUD operations
* sorting
* filtering
* search
* pagination
* persistence
* printing

---

# Deliverables

When complete, stop execution and provide:

1. Root Cause Analysis for each issue.
2. Focused remediation plan (implemented vs. proposed).
3. Summary of architectural changes.
4. List of modified files.
5. Documentation updates completed.
6. Python compatibility assessment and supported versions.
7. Cross-platform validation results (Windows/macOS).
8. Regression test checklist with pass/fail status.
9. Any remaining risks, assumptions, or follow-up recommendations.

Do **not** implement unrelated enhancements or refactors. Limit this iteration strictly to the issues identified above and await review after completion.
