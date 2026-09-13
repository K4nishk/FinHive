# ADR-004 — Date Picker Implementation (Bug Fix)

**Date**: 2026-06-30
**Status**: Accepted

## Context
The previous prototype had `AttributeError: 'ClickableDateEdit' object has no attribute 'showCalendarWidget'`. The method does not exist on QDateEdit. The date picker must open on Tab focus and on double-click in both Entry Tab and View Tab date cells.

## Decision
Create `DateEditFixed(QDateEdit)` widget that:
1. Sets `calendarPopup(True)` in `__init__`
2. Overrides `focusInEvent` to open the popup via `QTimer.singleShot(0, self.showPopup)` — the timer avoids recursion issues with focus events
3. Overrides `mouseDoubleClickEvent` to call `self.showPopup()`
4. Never calls `showCalendarWidget()` (does not exist)

For View Tab inline date editing: use a `QStyledItemDelegate` that spawns a `DatePickerDialog(QDialog)` containing a standalone `QCalendarWidget`. The dialog returns the selected date to the table model via `setData()`.

## Rationale
- `calendarPopup(True)` is the correct PySide6 API
- `QTimer.singleShot(0, ...)` defers the popup open until after the focus-in event completes, preventing the event loop re-entrance error
- Standalone `DatePickerDialog` for inline table editing is cleaner than embedding a QDateEdit in a delegate for date-only selection

## Cross-Platform Notes
- Tested on both macOS and Windows; PySide6 QCalendarWidget is cross-platform
- No OS-specific date picker used (would introduce drift)

## Consequences
- All date fields across Entry Tab and View Tab use the same `DateEditFixed` or `DatePickerDialog`
- Zero drift between OS implementations (user requirement)
