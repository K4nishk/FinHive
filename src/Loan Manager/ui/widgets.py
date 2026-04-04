"""Shared custom PySide6 widgets (ADR-005).

This module contains reusable widget subclasses used across multiple UI tabs.
"""
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QDateEdit, QStyledItemDelegate


class ClickableDateEdit(QDateEdit):
    """QDateEdit subclass that opens the calendar popup on any mouse click or Tab focus.

    Addresses BUG-UTR-4: the default QDateEdit only triggers the calendar
    popup when the small dropdown arrow on the right edge is clicked.
    Overriding mousePressEvent ensures the calendar opens on any click
    within the field area.

    R1: Also overrides focusInEvent to show calendar when user Tabs into the
    field (TabFocusReason or BacktabFocusReason). Programmatic focus changes
    (e.g., form reset) do not trigger the calendar popup.

    setCalendarPopup(True) is called in __init__ so this widget is
    self-contained — callers do not need to call it separately.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(True)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self.showCalendarWidget()

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        # Only show calendar on keyboard Tab navigation, not programmatic focus.
        if event.reason() in (
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
        ):
            self.showCalendarWidget()


class DatePickerDelegate(QStyledItemDelegate):
    """QStyledItemDelegate that provides a ClickableDateEdit as the cell editor.

    R2: Apply to date columns in ViewTab so that inline editing opens a
    calendar date picker rather than a free-text input field.

    Usage:
        delegate = DatePickerDelegate(parent_widget)
        table_view.setItemDelegateForColumn(col_index, delegate)
    """

    def createEditor(self, parent, option, index):
        editor = ClickableDateEdit(parent)
        editor.setDisplayFormat("yyyy-MM-dd")
        return editor

    def setEditorData(self, editor, index) -> None:
        value = index.data(Qt.ItemDataRole.DisplayRole)
        if value and value not in ("Unknown", ""):
            try:
                parsed = date.fromisoformat(str(value))
                editor.setDate(QDate(parsed.year, parsed.month, parsed.day))
                return
            except (ValueError, AttributeError):
                pass
        editor.setDate(QDate.currentDate())

    def setModelData(self, editor, model, index) -> None:
        q = editor.date()
        iso_str = f"{q.year():04d}-{q.month():02d}-{q.day():02d}"
        model.setData(index, iso_str, Qt.ItemDataRole.EditRole)
