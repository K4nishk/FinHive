# Filter Architecture -- Loan Manager

## Overview
Single source of truth: FilterState (owned by ColumnFilterWidget).
Popup is a pure view -- holds no permanent state.

## State Flow Diagram

```
User clicks filter button
  -> ColumnFilterWidget._open_popup()
    -> pending = committed.copy()
    -> popup.render(all_values, pending)  <- fresh render, no stale widget state

User clicks item in popup
  -> popup emits item_toggled(value, new_checked)
    -> ColumnFilterWidget._on_item_toggled()
      -> pending.add/discard(value)
      -> popup.set_item_checked(value, new_checked)  <- popup only updates visuals

User clicks Apply
  -> popup emits apply_clicked
    -> ColumnFilterWidget._on_apply()
      -> committed = pending.copy()
      -> popup.hide()
      -> filter_changed.emit(col, list(committed))

User clicks Cancel
  -> popup emits cancel_clicked
    -> ColumnFilterWidget._on_cancel()
      -> pending = committed.copy()  <- discard edits
      -> popup.hide()

User clicks Clear
  -> popup emits clear_clicked
    -> ColumnFilterWidget._on_clear()
      -> committed = set(); pending = set()
      -> popup.hide()
      -> filter_changed.emit(col, [])

Popup re-opened
  -> Always calls popup.render(all_values, pending)
  -> Popup shows exactly committed state (since pending = committed on open)
```

## State Invariants
- committed = what is applied to the table
- pending = what is shown in the open popup
- popup widget state = always derived from pending (never authoritative itself)
- On open: pending := committed (fresh start for each popup session)
- On apply: committed := pending
- On cancel: pending := committed (discard session)

## Key Design Decisions

### No ItemIsUserCheckable
Popup list/tree items do NOT have the ItemIsUserCheckable flag. This prevents
Qt from auto-toggling checkboxes on click, which eliminates the re-entrancy
problem where itemChanged fires during programmatic setCheckState calls.

### itemPressed instead of itemChanged
The popup connects itemPressed (fires once per physical click) instead of
itemChanged (fires per any state change including programmatic). This means:
1. User clicks item -> popup emits item_toggled with the NEW desired state
2. ColumnFilterWidget updates pending_state
3. ColumnFilterWidget calls popup.set_item_checked() to update the visual
4. No re-entrancy possible since blockSignals wraps all programmatic updates

### Cancel Button
A Cancel button was added (missing in the original architecture). Closing the
popup via Escape or Cancel discards any pending changes and reverts to the
committed state.

### populate() is Safe
ViewTab.refresh() calls populate() on every filter widget. This only updates
all_values and prunes committed state to remove values that no longer exist.
It does NOT touch the popup widget -- the popup is only rendered on open.
