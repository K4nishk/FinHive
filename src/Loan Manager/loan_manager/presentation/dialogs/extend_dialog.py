from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QSpinBox, QComboBox, QPushButton, QLabel,
)

from loan_manager.application.dtos.loan_dto import ExtendLoanDTO, LoanDTO
from loan_manager.presentation.widgets.date_edit import DateEditFixed
from PySide6.QtCore import QDate


class ExtendDialog(QDialog):
    """Dialog for extending a loan's due date."""

    def __init__(self, loan: LoanDTO, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Extend Loan - {loan.reference_id}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._loan = loan
        self._result: ExtendLoanDTO | None = None

        layout = QVBoxLayout(self)

        info_label = QLabel(
            f"Loan: {loan.reference_id}\n"
            f"Borrower: {loan.borrower_name}\n"
            f"Amount: {loan.amount}\n"
            f"Current Due Date: {loan.due_date or 'None'}"
        )
        layout.addWidget(info_label)

        form = QFormLayout()

        self._period_spin = QSpinBox()
        self._period_spin.setRange(1, 999)
        self._period_spin.setValue(1)
        form.addRow("Extension Period:", self._period_spin)

        self._unit_combo = QComboBox()
        self._unit_combo.addItems(["months", "days"])
        form.addRow("Unit:", self._unit_combo)

        self._has_due_date = loan.due_date is not None

        if self._has_due_date:
            self._preview_label = QLabel()
            form.addRow("Preview:", self._preview_label)
            self._period_spin.valueChanged.connect(self._update_preview)
            self._unit_combo.currentTextChanged.connect(self._update_preview)
            self._update_preview()
        else:
            self._new_due_date_edit = DateEditFixed()
            form.addRow("New Due Date:", self._new_due_date_edit)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Extend")
        ok_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _update_preview(self) -> None:
        if not self._has_due_date:
            return
        period = self._period_spin.value()
        unit = self._unit_combo.currentText()
        old_due = self._loan.due_date
        new_giving = old_due
        if unit == "months":
            new_due = old_due + relativedelta(months=period)
        else:
            new_due = old_due + timedelta(days=period)
        self._preview_label.setText(
            f"New Giving Date: {new_giving}\nNew Due Date: {new_due}"
        )

    def _on_accept(self) -> None:
        period = self._period_spin.value()
        unit = self._unit_combo.currentText()
        new_due_date = None
        if not self._has_due_date:
            qd = self._new_due_date_edit.date()
            new_due_date = date(qd.year(), qd.month(), qd.day())

        self._result = ExtendLoanDTO(
            extension_period=period,
            extension_period_unit=unit,
            new_due_date=new_due_date,
        )
        self.accept()

    def get_result(self) -> ExtendLoanDTO | None:
        return self._result
