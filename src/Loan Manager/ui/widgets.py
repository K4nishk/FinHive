"""Shared custom PySide6 widgets (ADR-005).

This module contains reusable widget subclasses used across multiple UI tabs.
"""
from PySide6.QtWidgets import QDateEdit


class ClickableDateEdit(QDateEdit):
    """QDateEdit subclass that opens the calendar popup on any mouse click.

    Addresses BUG-UTR-4: the default QDateEdit only triggers the calendar
    popup when the small dropdown arrow on the right edge is clicked.
    Overriding mousePressEvent ensures the calendar opens on any click
    within the field area.

    setCalendarPopup(True) is called in __init__ so this widget is
    self-contained — callers do not need to call it separately.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCalendarPopup(True)

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        self.showCalendarWidget()
