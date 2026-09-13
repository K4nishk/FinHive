from decimal import Decimal

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QGroupBox,
    QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox, QPushButton,
    QLabel, QMessageBox,
)

from loan_manager.application.dtos.calculation_dto import CalculationRequestDTO
from loan_manager.application.dtos.loan_dto import LoanFilterDTO
from loan_manager.application.dtos.report_dto import GenerateReportDTO, ReportRecordDTO
from loan_manager.application.use_cases.loans.get_autocomplete import GetAutocompleteValues
from loan_manager.application.use_cases.reports.calculate_interest import CalculateInterest
from loan_manager.application.use_cases.reports.generate_report import GenerateReport
from loan_manager.domain.value_objects.status import CalculationMode, ExtensionPeriodUnit
from loan_manager.presentation.dialogs.calculation_dialog import CalculationDialog


class CalculatorTab(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._main_window = parent
        self._last_result = None
        self._setup_ui()
        self._load_filter_options()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Mode selector
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Monthly", "Daily", "Both"])
        mode_layout.addWidget(self._mode_combo)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # Filters group
        filter_group = QGroupBox("Filters")
        filter_layout = QFormLayout()

        self._borrower_group_filter = QComboBox()
        self._borrower_group_filter.addItem("")
        self._borrower_group_filter.setEditable(True)
        filter_layout.addRow("Borrower Group:", self._borrower_group_filter)

        self._borrower_name_filter = QComboBox()
        self._borrower_name_filter.addItem("")
        self._borrower_name_filter.setEditable(True)
        filter_layout.addRow("Borrower Name:", self._borrower_name_filter)

        self._depositor_name_filter = QComboBox()
        self._depositor_name_filter.addItem("")
        self._depositor_name_filter.setEditable(True)
        filter_layout.addRow("Depositor Name:", self._depositor_name_filter)

        self._depositor_group_filter = QComboBox()
        self._depositor_group_filter.addItem("")
        self._depositor_group_filter.setEditable(True)
        filter_layout.addRow("Depositor Group:", self._depositor_group_filter)

        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        by_month_widget = QWidget()
        by_month_grid = QGridLayout(by_month_widget)
        by_month_grid.setContentsMargins(0, 0, 0, 0)
        self._by_month_checkboxes: list[QCheckBox] = []
        for i, m in enumerate(months):
            checkbox = QCheckBox(m)
            self._by_month_checkboxes.append(checkbox)
            by_month_grid.addWidget(checkbox, i // 4, i % 4)
        filter_layout.addRow("By Month:", by_month_widget)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Global inputs group
        inputs_group = QGroupBox("Calculation Parameters")
        inputs_layout = QFormLayout()

        self._interest_rate = QDoubleSpinBox()
        self._interest_rate.setRange(0.0, 100.0)
        self._interest_rate.setDecimals(2)
        self._interest_rate.setValue(0.0)
        inputs_layout.addRow("Interest Rate (%):", self._interest_rate)

        self._commission_rate = QDoubleSpinBox()
        self._commission_rate.setRange(0.0, 100.0)
        self._commission_rate.setDecimals(2)
        self._commission_rate.setValue(0.0)
        inputs_layout.addRow("Commission Rate (%):", self._commission_rate)

        self._extension_period = QSpinBox()
        self._extension_period.setRange(1, 999)
        self._extension_period.setValue(1)
        inputs_layout.addRow("Extension Period:", self._extension_period)

        self._unit_combo = QComboBox()
        self._unit_combo.addItems(["months", "days"])
        inputs_layout.addRow("Unit:", self._unit_combo)

        self._tds_checkbox = QCheckBox("Apply TDS")
        inputs_layout.addRow("TDS:", self._tds_checkbox)

        inputs_group.setLayout(inputs_layout)
        layout.addWidget(inputs_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._calculate_btn = QPushButton("Calculate")
        self._calculate_btn.clicked.connect(self._on_calculate)
        btn_layout.addWidget(self._calculate_btn)
        layout.addLayout(btn_layout)
        layout.addStretch()

    def _load_filter_options(self) -> None:
        try:
            autocomplete = GetAutocompleteValues(self._container.get_uow)

            for values, combo in [
                (autocomplete.execute("borrower_group"), self._borrower_group_filter),
                (autocomplete.execute("borrower_name"), self._borrower_name_filter),
                (autocomplete.execute("depositor_name"), self._depositor_name_filter),
                (autocomplete.execute("depositor_group"), self._depositor_group_filter),
            ]:
                for v in values:
                    combo.addItem(v)
        except Exception:
            pass

    def _on_calculate(self) -> None:
        mode_text = self._mode_combo.currentText()
        mode = CalculationMode(mode_text)

        b_group = self._borrower_group_filter.currentText().strip() or None
        b_name = self._borrower_name_filter.currentText().strip() or None
        d_name = self._depositor_name_filter.currentText().strip() or None
        d_group = self._depositor_group_filter.currentText().strip() or None
        by_months = [
            i for i, cb in enumerate(self._by_month_checkboxes, start=1)
            if cb.isChecked()
        ] or None

        filters = LoanFilterDTO(
            borrower_group=b_group,
            borrower_name=b_name,
            depositor_name=d_name,
            depositor_group=d_group,
            by_months=by_months,
        )

        unit = ExtensionPeriodUnit(self._unit_combo.currentText())

        try:
            dto = CalculationRequestDTO(
                mode=mode,
                filters=filters,
                interest_rate=Decimal(str(self._interest_rate.value())),
                commission_rate=Decimal(str(self._commission_rate.value())),
                extension_period=self._extension_period.value(),
                extension_period_unit=unit,
                tds_flag=self._tds_checkbox.isChecked(),
            )

            calc_uc = CalculateInterest(self._container.get_uow)
            result = calc_uc.execute(dto)

            if not result.lines:
                QMessageBox.information(
                    self, "No Results", "No loans matched the selected filters."
                )
                return

            dlg = CalculationDialog(result, self)
            dlg.report_requested.connect(self._on_generate_report)
            dlg.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Calculation failed: {e}")

    def _on_generate_report(self, lines) -> None:
        try:
            mode_text = self._mode_combo.currentText()
            mode = CalculationMode(mode_text)

            records = []
            for line in lines:
                records.append(ReportRecordDTO(
                    id=None,
                    report_id="",
                    reference_id=line.reference_id,
                    borrower_name=line.borrower_name,
                    depositor_name=line.depositor_name,
                    depositor_group=None,
                    amount=line.amount,
                    giving_date=line.giving_date,
                    due_date=line.due_date,
                    extension_period=line.extension_period,
                    extension_period_unit=line.extension_period_unit,
                    interest_rate=line.interest_rate,
                    commission_rate=line.commission_rate,
                    tds_flag=line.tds_flag,
                    interest_amount=line.interest_amount,
                    commission_amount=line.commission_amount,
                    tds_amount=line.tds_amount,
                    chq_amount=line.chq_amount,
                    post_extension_giving_date=line.post_extension_giving_date,
                    post_extension_due_date=line.post_extension_due_date,
                    paidoff_date=None,
                ))

            gen_dto = GenerateReportDTO(mode=mode, records=records)
            gen_uc = GenerateReport(
                self._container.get_uow,
                self._container.event_bus,
            )
            report = gen_uc.execute(gen_dto)

            if self._main_window:
                self._main_window.show_status(
                    f"Report {report.report_id} generated successfully. "
                    "Check Pending Approval tab."
                )
                if hasattr(self._main_window, '_approval_tab'):
                    self._main_window._approval_tab.refresh()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate report: {e}")
