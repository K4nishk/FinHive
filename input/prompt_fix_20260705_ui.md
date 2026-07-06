# Prompt.md — Iteration 3 (Re-Architecture of Filter State Management & UI Synchronization)

## Role

You are acting as the **Principal Software Engineer**, **UI Architecture Lead**, **Senior QA Engineer**, and **Code Reviewer** for the Loan Manager application.

This is **NOT** another bug-fix iteration.

This is an architectural correction.

The current implementation has reached the point where incremental fixes are no longer sufficient. The filtering engine works correctly, but the **UI representation of the filter state is not architecturally reliable**.

Your responsibility is to redesign the **filter state management architecture** while preserving all existing functionality.

---

# Context

All previous issues have been resolved except one.

## Remaining Critical Issue

**Checkbox Visual Desynchronization**

The filtering logic itself works correctly.

The internal selected values are correct.

The Apply operation correctly filters the table.

The only remaining defect is that the popup UI does not faithfully represent the internal selection state.

This has now become the highest-priority UX defect in the application.

---

# Previous Root Cause Analysis

The previous implementation concluded:

> TextFilterPopup.populate() recreated items without restoring selected state.

The following changes were made:

* populate(selected)
* restoring check state
* blockSignals()
* viewport().update()
* ItemIsUserCheckable

Although technically correct, these fixes **did not eliminate the defect**.

This strongly suggests that the identified RCA addressed only a symptom and **not the architectural source of truth**.

Do **not** continue patching this implementation.

---

# New Objective

Treat this as an architecture review.

Assume the current filter popup implementation is fundamentally incorrect.

Your task is to redesign the synchronization model between:

* UI
* filter popup
* filter model
* table model
* Apply button
* Cancel button
* Select All
* Clear
* popup reopen

The redesign must produce a **single, authoritative source of truth** for filter selections.

---

# Required Investigation

Before writing any code, perform a complete architectural review.

Document:

1. How filter state currently flows through the application.
2. Every object responsible for holding selection state.
3. Every location where selection state is copied.
4. Every place where selection state is recreated.
5. Every place where UI is rebuilt.
6. Every signal that mutates selection state.
7. Every signal emitted during Populate().
8. Every lifecycle event when opening/closing the popup.

Do not assume the previous RCA is complete.

Continue investigating until the **true lifecycle** is understood.

---

# Suspected Architectural Problem

The current implementation appears to have multiple independent representations of filter state.

Possible examples:

* popup checkbox state
* _selected list
* model state
* applied state
* pending state
* table filter state

If multiple copies exist, synchronization bugs are inevitable.

The architecture should instead have exactly **one canonical state**.

Everything else should simply render that state.

---

# Required Architecture

Design the filtering system around explicit state ownership.

Recommended architecture (adapt if a better design exists):

```
FilterState (single source of truth)
        │
        │
        ├─────────────── Table Filter Engine
        │
        ├─────────────── Popup Renderer
        │
        ├─────────────── Apply Logic
        │
        ├─────────────── Cancel Logic
        │
        └─────────────── Select All / Clear
```

No UI component should own permanent state.

The popup should become a **pure view** of the FilterState.

---

# Popup Behaviour Requirements

Every time the popup opens:

Render entirely from FilterState.

Never from stale widget state.

Never from previous checkbox instances.

Never from temporary variables.

---

# Apply Behaviour

Pressing Apply should:

1. Commit pending selections into FilterState.
2. Apply FilterState to the table.
3. Close popup.

The popup should **not** become the owner of filter state.

---

# Cancel Behaviour

Cancel should:

Discard pending edits.

Restore popup from committed FilterState.

No partial state leakage.

---

# Select All Behaviour

When selecting Select All:

Every value must immediately display:

✓

Internally:

Every value must also exist inside FilterState.

Closing and reopening the popup must still show every checkbox selected.

---

# Clear Behaviour

Clear:

Immediately unchecks every visible checkbox.

FilterState becomes empty.

Reopening popup must still show every checkbox cleared.

---

# Multiple Selection Behaviour

Example:

```
Borrower A

Borrower B

Borrower C
```

Click:

✓ Borrower A

✓ Borrower B

✓ Borrower C

Expected:

All three remain visually checked.

Apply.

Close popup.

Open popup.

Still:

✓ Borrower A

✓ Borrower B

✓ Borrower C

Not only the most recently clicked item.

---

# Mandatory State Invariants

At every point in time:

```
Displayed Checkbox State

==

Pending Popup State

==

Committed FilterState (after Apply)

==

Applied Table Filter
```

No divergence is acceptable.

---

# Signal Review

Review every Qt signal.

Identify:

* duplicate itemChanged handlers
* recursive emissions
* re-entrant updates
* multiple populate() calls
* hidden refreshes
* repaint timing
* widget reconstruction

Document each one.

Eliminate unnecessary signal chains.

---

# Avoid Incremental Patches

Do NOT:

* add more blockSignals()
* add more viewport().update()
* add more repaint()
* add delayed timers
* add refresh hacks

If these are required, the architecture is likely incorrect.

---

# Debug Instrumentation

Temporarily add structured debug logging.

Log:

Popup Open

Current FilterState

Rendered Checkboxes

User Click

Updated Pending State

Apply

Committed FilterState

Popup Reopen

Rendered Checkboxes

This logging should make it impossible for state transitions to be ambiguous.

Remove or downgrade verbose logging before finalizing.

---

# Regression Requirements

Verify:

Single selection

Multiple selection

Select All

Clear

Cancel

Apply

Close popup

Re-open popup

Rapid clicking

Keyboard navigation

Filtering after sorting

Sorting after filtering

Multiple columns simultaneously

Date filters

Borrower filters

Depositor filters

Mixed filter types

No regressions are permitted.

---

# Documentation Update

After implementation, update the project documentation.

Include a new section:

## Filter Architecture

Document:

* ownership of filter state
* popup lifecycle
* state transition flow
* Apply workflow
* Cancel workflow
* rendering workflow
* synchronization guarantees

Include an architecture diagram showing the new data flow.

---

# Git Comparison

Compare the implementation against the **previous Git commit**.

Generate a concise changelog including:

* files modified
* architectural changes
* removed code paths
* new state management approach
* rationale for redesign
* backward compatibility considerations

Do not simply list changed files—explain **why** each change was necessary.

---

# Deliverables

When complete, stop execution and provide:

1. Root cause analysis (updated after architectural review).
2. Explanation of why the previous RCA was incomplete.
3. Description of the new filter architecture.
4. State-flow diagram (text or Mermaid).
5. List of modified files.
6. Documentation updates completed.
7. Git diff summary compared to the previous commit.
8. Comprehensive regression test results covering all filter scenarios.

Do **not** proceed to any unrelated enhancements. Await review before making further changes.
