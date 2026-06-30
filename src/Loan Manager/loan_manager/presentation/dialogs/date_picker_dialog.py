from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QCalendarWidget
from PySide6.QtCore import QDate
from datetime import date


class DatePickerDialog(QDialog):
    """Standalone calendar dialog for inline table date editing."""

    def __init__(self, current_date: date | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Date")
        self.setModal(True)
        self._selected: date | None = None

        cal = QCalendarWidget(self)
        cal.setGridVisible(True)
        if current_date:
            cal.setSelectedDate(QDate(current_date.year, current_date.month, current_date.day))
        cal.clicked.connect(self._on_date_selected)

        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(cal)
        layout.addLayout(btn_layout)
        self._cal = cal

    def _on_date_selected(self, qdate: QDate):
        self._selected = date(qdate.year(), qdate.month(), qdate.day())

    def selected_date(self) -> date | None:
        qd = self._cal.selectedDate()
        return date(qd.year(), qd.month(), qd.day())
