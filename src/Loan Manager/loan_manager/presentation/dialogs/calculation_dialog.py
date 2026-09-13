from decimal import Decimal

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox,
    QHeaderView,
)
from PySide6.QtCore import Qt, Signal

from loan_manager.application.dtos.calculation_dto import CalculationLineDTO, CalculationResultDTO
from loan_manager.domain.services.interest_calculator import InterestCalculator
from loan_manager.domain.value_objects.status import ExtensionPeriodUnit


CALC_COLUMNS = [
    "Ref ID", "B Name", "Amt", "D Name", "G Date", "D Date",
    "Rate %", "Comm %", "Period", "Unit", "TDS",
    "Interest", "Commission", "TDS Amt", "CHQ Amt",
]


class CalculationDialog(QDialog):
    report_requested = Signal(list)

    def __init__(self, result: CalculationResultDTO, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Calculation Results")
        self.setModal(True)
        self.setMinimumSize(1100, 600)
        self._result = result
        self._lines: list[CalculationLineDTO] = list(result.lines)

        layout = QVBoxLayout(self)

        self._table = QTableWidget(len(self._lines), len(CALC_COLUMNS))
        self._table.setHorizontalHeaderLabels(CALC_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._populate_table()
        layout.addWidget(self._table)

        self._summary_label = QLabel()
        self._update_summary()
        layout.addWidget(self._summary_label)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        generate_btn = QPushButton("Generate Report")
        generate_btn.clicked.connect(self._on_generate)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(generate_btn)
        layout.addLayout(btn_layout)

    def _populate_table(self) -> None:
        self._table.blockSignals(True)
        for row, line in enumerate(self._lines):
            self._set_read_only_item(row, 0, line.reference_id)
            self._set_read_only_item(row, 1, line.borrower_name)
            self._set_read_only_item(row, 2, str(line.amount))
            self._set_read_only_item(row, 3, line.depositor_name)
            self._set_read_only_item(row, 4, str(line.giving_date))
            self._set_read_only_item(row, 5, str(line.due_date) if line.due_date else "N/A")

            rate_item = QTableWidgetItem(str(line.interest_rate))
            self._table.setItem(row, 6, rate_item)

            comm_item = QTableWidgetItem(str(line.commission_rate))
            self._table.setItem(row, 7, comm_item)

            period_item = QTableWidgetItem(str(line.extension_period))
            self._table.setItem(row, 8, period_item)

            unit_item = QTableWidgetItem(line.extension_period_unit.value)
            self._table.setItem(row, 9, unit_item)

            tds_item = QTableWidgetItem("Yes" if line.tds_flag else "No")
            self._table.setItem(row, 10, tds_item)

            self._set_read_only_item(row, 11, str(line.interest_amount))
            self._set_read_only_item(row, 12, str(line.commission_amount))
            self._set_read_only_item(row, 13, str(line.tds_amount))
            self._set_read_only_item(row, 14, str(line.chq_amount))

        self._table.blockSignals(False)
        self._table.cellChanged.connect(self._on_cell_changed)

    def _set_read_only_item(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(row, col, item)

    def _on_cell_changed(self, row: int, col: int) -> None:
        if col not in (6, 7, 8, 9, 10):
            return
        line = self._lines[row]
        try:
            rate = Decimal(self._table.item(row, 6).text())
            comm = Decimal(self._table.item(row, 7).text())
            period = int(self._table.item(row, 8).text())
            unit_text = self._table.item(row, 9).text()
            unit = ExtensionPeriodUnit(unit_text)
            tds_text = self._table.item(row, 10).text().lower()
            tds_flag = tds_text in ("yes", "true", "1")

            interest = InterestCalculator.calculate(line.amount, rate, period, unit)
            commission = InterestCalculator.calculate(line.amount, comm, period, unit)
            tds_amount = InterestCalculator.calculate_tds(interest) if tds_flag else Decimal("0.00")
            chq_amount = InterestCalculator.calculate_chq(interest, tds_amount)

            self._lines[row] = line.model_copy(update={
                "interest_rate": rate,
                "commission_rate": comm,
                "extension_period": period,
                "extension_period_unit": unit,
                "tds_flag": tds_flag,
                "interest_amount": interest,
                "commission_amount": commission,
                "tds_amount": tds_amount,
                "chq_amount": chq_amount,
            })

            self._table.blockSignals(True)
            self._table.item(row, 11).setText(str(interest))
            self._table.item(row, 12).setText(str(commission))
            self._table.item(row, 13).setText(str(tds_amount))
            self._table.item(row, 14).setText(str(chq_amount))
            self._table.blockSignals(False)

            self._update_summary()
        except (ValueError, KeyError, InvalidOperation):
            pass

    def _update_summary(self) -> None:
        total_amount = sum(l.amount for l in self._lines)
        total_interest = sum(l.interest_amount for l in self._lines)
        total_commission = sum(l.commission_amount for l in self._lines)
        self._summary_label.setText(
            f"Total Amount: {total_amount}  |  "
            f"Total Interest: {total_interest}  |  "
            f"Total Commission: {total_commission}"
        )

    def _on_generate(self) -> None:
        self.report_requested.emit(self._lines)
        self.accept()

    def get_lines(self) -> list[CalculationLineDTO]:
        return self._lines


# Import for exception handling
from decimal import InvalidOperation
