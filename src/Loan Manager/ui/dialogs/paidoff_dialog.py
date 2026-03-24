"""Dialog for marking a loan as Paidoff."""
import logging
from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class PaidoffDialog(QDialog):
    """Prompts the user for a paidoff_date before archiving a loan.

    Warns the user that the record will be moved to history and will no
    longer be visible in the View Tab.
    """

    def __init__(self, reference_id: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mark as Paidoff")
        self.setMinimumWidth(380)
        self._reference_id = reference_id
        self._paidoff_date: date = date.today()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        warning = QLabel(
            "Warning: This will archive the record to history.\n"
            "It will not be visible in the View Tab after this action."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)

        ref_label = QLabel(f"Reference ID: {self._reference_id}")
        layout.addWidget(ref_label)

        date_label = QLabel("Paidoff Date:")
        layout.addWidget(date_label)

        today = date.today()
        self._date_edit = QDateEdit()
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setDate(QDate(today.year, today.month, today.day))
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self._date_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        q = self._date_edit.date()
        self._paidoff_date = date(q.year(), q.month(), q.day())
        logger.debug("Paidoff date selected: %s", self._paidoff_date)
        self.accept()

    def paidoff_date(self) -> date:
        """Return the selected paidoff date."""
        return self._paidoff_date
