"""Dialog for marking a loan as Paidoff."""
import logging
from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from ui.widgets import ClickableDateEdit

logger = logging.getLogger(__name__)


class PaidoffDialog(QDialog):
    """Prompts the user for a paidoff_date and interest parameters before archiving a loan.

    Warns the user that the record will be moved to history and will no
    longer be visible in the View Tab.

    CHG-02-EXT: extends with interest_rate, commission_rate, tds_flag fields
    that feed into the report pipeline in view_tab._action_paidoff().
    """

    def __init__(self, reference_id: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mark as Paidoff")
        self.setMinimumWidth(400)
        self._reference_id = reference_id
        self._paidoff_date: date = date.today()
        self._interest_rate_val: float = 12.0
        self._commission_rate_val: float = 2.0
        self._tds_flag_val: bool = False
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
        self._date_edit = ClickableDateEdit()
        self._date_edit.setDate(QDate(today.year, today.month, today.day))
        self._date_edit.setDisplayFormat("yyyy-MM-dd")
        layout.addWidget(self._date_edit)

        # CHG-02-EXT: interest rate, commission rate, TDS flag
        form = QFormLayout()

        self._interest_rate_spin = QDoubleSpinBox()
        self._interest_rate_spin.setRange(0.0, 100.0)
        self._interest_rate_spin.setDecimals(2)
        self._interest_rate_spin.setValue(12.0)
        self._interest_rate_spin.setSuffix(" %")
        form.addRow("Interest Rate:", self._interest_rate_spin)

        self._commission_rate_spin = QDoubleSpinBox()
        self._commission_rate_spin.setRange(0.0, 100.0)
        self._commission_rate_spin.setDecimals(2)
        self._commission_rate_spin.setValue(2.0)
        self._commission_rate_spin.setSuffix(" %")
        form.addRow("Commission Rate:", self._commission_rate_spin)

        self._tds_checkbox = QCheckBox("Apply TDS (10% of Interest)")
        self._tds_checkbox.setChecked(False)
        form.addRow("TDS:", self._tds_checkbox)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        q = self._date_edit.date()
        self._paidoff_date = date(q.year(), q.month(), q.day())
        self._interest_rate_val = self._interest_rate_spin.value()
        self._commission_rate_val = self._commission_rate_spin.value()
        self._tds_flag_val = self._tds_checkbox.isChecked()
        logger.debug(
            "Paidoff confirmed: date=%s ir=%.2f cr=%.2f tds=%s",
            self._paidoff_date, self._interest_rate_val,
            self._commission_rate_val, self._tds_flag_val,
        )
        self.accept()

    def paidoff_date(self) -> date:
        """Return the selected paidoff date."""
        return self._paidoff_date

    def interest_rate(self) -> float:
        """Return the entered interest rate percentage."""
        return self._interest_rate_val

    def commission_rate(self) -> float:
        """Return the entered commission rate percentage."""
        return self._commission_rate_val

    def tds_flag(self) -> bool:
        """Return whether TDS is applied."""
        return self._tds_flag_val
