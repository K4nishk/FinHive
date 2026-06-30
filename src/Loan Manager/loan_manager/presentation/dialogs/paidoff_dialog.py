from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QDoubleSpinBox, QCheckBox, QPushButton, QLabel,
)
from PySide6.QtCore import QDate

from loan_manager.application.dtos.loan_dto import PaidOffRequestDTO, LoanDTO
from loan_manager.presentation.widgets.date_edit import DateEditFixed


class PaidOffDialog(QDialog):
    """Dialog for marking a loan as paid off."""

    def __init__(self, loan: LoanDTO, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Mark Paid Off - {loan.reference_id}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._loan = loan
        self._result: PaidOffRequestDTO | None = None

        layout = QVBoxLayout(self)

        info_label = QLabel(
            f"Loan: {loan.reference_id}\n"
            f"Borrower: {loan.borrower_name}\n"
            f"Amount: {loan.amount}\n"
            f"Due Date: {loan.due_date}"
        )
        layout.addWidget(info_label)

        warning_label = QLabel("This report will be sent to Pending Approval.")
        warning_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(warning_label)

        form = QFormLayout()

        self._paidoff_date = DateEditFixed()
        self._paidoff_date.setDate(QDate.currentDate())
        form.addRow("Paidoff Date:", self._paidoff_date)

        self._interest_rate = QDoubleSpinBox()
        self._interest_rate.setRange(0.0, 100.0)
        self._interest_rate.setDecimals(2)
        self._interest_rate.setValue(0.0)
        form.addRow("Interest Rate (%):", self._interest_rate)

        self._commission_rate = QDoubleSpinBox()
        self._commission_rate.setRange(0.0, 100.0)
        self._commission_rate.setDecimals(2)
        self._commission_rate.setValue(0.0)
        form.addRow("Commission Rate (%):", self._commission_rate)

        self._tds_flag = QCheckBox("Apply TDS")
        form.addRow("TDS:", self._tds_flag)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("Mark Paid Off")
        ok_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def _on_accept(self) -> None:
        qd = self._paidoff_date.date()
        paidoff_date = date(qd.year(), qd.month(), qd.day())

        self._result = PaidOffRequestDTO(
            paidoff_date=paidoff_date,
            interest_rate=Decimal(str(self._interest_rate.value())),
            commission_rate=Decimal(str(self._commission_rate.value())),
            tds_flag=self._tds_flag.isChecked(),
        )
        self.accept()

    def get_result(self) -> PaidOffRequestDTO | None:
        return self._result
