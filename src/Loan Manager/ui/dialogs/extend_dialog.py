"""Dialog for extending a loan's due date."""
import logging
from datetime import date
from dateutil.relativedelta import relativedelta
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class ExtendDialog(QDialog):
    """Prompts for extension period and unit, previews new dates.

    Two cases:
    - Loan has a due_date: new giving_date = old due_date,
      new due_date = old due_date + extension_period
    - Loan has no due_date:  [REVIEW REQUIRED] new giving_date = today,
      new due_date = picked via extension relative to today
    """

    def __init__(
        self,
        reference_id: str,
        current_due_date: Optional[date],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Extend Loan")
        self.setMinimumWidth(400)
        self._reference_id = reference_id
        self._current_due_date = current_due_date
        self._base_date = current_due_date if current_due_date else date.today()
        self._new_giving_date: date = self._base_date
        self._new_due_date: date = self._base_date
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        ref_label = QLabel(f"Reference ID: {self._reference_id}")
        layout.addWidget(ref_label)

        if self._current_due_date:
            current_label = QLabel(f"Current Due Date: {self._current_due_date.isoformat()}")
        else:
            current_label = QLabel("Current Due Date: None (new giving date will be today)")
        layout.addWidget(current_label)

        form = QFormLayout()
        layout.addLayout(form)

        self._period_spin = QSpinBox()
        self._period_spin.setMinimum(1)
        self._period_spin.setValue(1)
        form.addRow("Extension Period:", self._period_spin)

        self._unit_combo = QComboBox()
        self._unit_combo.addItems(["months", "days"])
        self._unit_combo.setCurrentIndex(0)
        form.addRow("Extension Unit:", self._unit_combo)

        self._preview_label = QLabel()
        layout.addWidget(self._preview_label)

        self._period_spin.valueChanged.connect(self._update_preview)
        self._unit_combo.currentIndexChanged.connect(self._update_preview)
        self._update_preview()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _compute_new_dates(self) -> tuple[date, date]:
        """Compute new giving_date and new due_date based on form values."""
        period = self._period_spin.value()
        unit = self._unit_combo.currentText()
        base = self._base_date

        if unit == "months":
            new_due = base + relativedelta(months=period)
        else:
            from datetime import timedelta
            new_due = base + timedelta(days=period)

        new_giving = base
        return new_giving, new_due

    def _update_preview(self) -> None:
        try:
            new_giving, new_due = self._compute_new_dates()
            self._preview_label.setText(
                f"New Giving Date: {new_giving.isoformat()}\n"
                f"New Due Date:    {new_due.isoformat()}"
            )
        except Exception as exc:
            self._preview_label.setText(f"Preview error: {exc}")

    def _on_accept(self) -> None:
        self._new_giving_date, self._new_due_date = self._compute_new_dates()
        logger.debug(
            "Extend accepted: giving=%s due=%s",
            self._new_giving_date,
            self._new_due_date,
        )
        self.accept()

    def new_giving_date(self) -> date:
        return self._new_giving_date

    def new_due_date(self) -> date:
        return self._new_due_date
