from PySide6.QtWidgets import QDateEdit
from PySide6.QtCore import QTimer, Qt, QDate


class DateEditFixed(QDateEdit):
    """
    Fixed QDateEdit that opens the calendar popup on Tab focus and double-click.
    NEVER calls showCalendarWidget() -- uses setCalendarPopup(True) + showPopup().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("yyyy-MM-dd")
        self.setDate(QDate.currentDate())

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if event.reason() in (
            Qt.FocusReason.TabFocusReason,
            Qt.FocusReason.BacktabFocusReason,
        ):
            QTimer.singleShot(0, self.showPopup)

    def mouseDoubleClickEvent(self, event):
        super().mouseDoubleClickEvent(event)
        QTimer.singleShot(0, self.showPopup)
