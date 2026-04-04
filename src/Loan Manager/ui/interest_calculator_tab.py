"""Interest Calculator Tab — R5 implementation.

Three calculation modes:
    Monthly (default): Interest = (Amount * rate * period) / (12 * 100)
    Daily:             Interest = (Amount * rate * period) / (365 * 100)
    Both:              Per-record extension_period_unit (months or days)

Filter behavior (PD-29 / R5):
    No filter applied: show all loans with no due_date.
    Any filter applied: exclude no-due-date loans; show only matching records.

Generate Report button is disabled until Calculate has been clicked (PD-24 / R5).
Global header value changes overwrite all row values (R5).
blockSignals() guards prevent itemChanged recursion during programmatic cell population.
"""
import logging
from datetime import date, datetime
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data.csv_manager import read_loans
from loan_manager.interest_calculator import (
    calculate_both,
    calculate_daily,
    calculate_monthly,
)
from models.loan import Loan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column indices for the filtered records table
# ---------------------------------------------------------------------------
COL_REF_ID = 0
COL_BORROWER_NAME = 1
COL_AMOUNT = 2
COL_DEPOSITOR_NAME = 3
COL_GIVING_DATE = 4
COL_DUE_DATE = 5
COL_INTEREST_RATE = 6
COL_COMMISSION_RATE = 7
COL_EXTENSION_PERIOD = 8
COL_EXTENSION_UNIT = 9
COL_TDS_FLAG = 10
COL_INTEREST_AMOUNT = 11
COL_COMMISSION_AMOUNT = 12
COL_TDS_AMOUNT = 13

TABLE_HEADERS = [
    "Ref ID", "Borrower", "Amount", "Depositor",
    "Giving Date", "Due Date",
    "Int Rate %", "Comm Rate %", "Ext Period", "Ext Unit", "TDS",
    "Interest", "Commission", "TDS Amount",
]

READONLY_COLS = {COL_REF_ID, COL_BORROWER_NAME, COL_AMOUNT, COL_DEPOSITOR_NAME,
                 COL_GIVING_DATE, COL_DUE_DATE, COL_INTEREST_AMOUNT,
                 COL_COMMISSION_AMOUNT, COL_TDS_AMOUNT}


class InterestCalculatorTab(QWidget):
    """Interest Calculator Tab — R5."""

    report_generated = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._loans: List[Loan] = []
        self._filtered_loans: List[Loan] = []
        self._calculated = False
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Mode selector
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Monthly", "Daily", "Both"])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # Filter panel
        filter_group = QGroupBox("Filters")
        filter_layout = QFormLayout(filter_group)

        self._filter_borrower_group = QComboBox()
        self._filter_borrower_group.addItem("All")
        filter_layout.addRow("Borrower Group:", self._filter_borrower_group)

        self._filter_borrower_name = QComboBox()
        self._filter_borrower_name.addItem("All")
        filter_layout.addRow("Borrower Name:", self._filter_borrower_name)

        self._filter_depositor_name = QComboBox()
        self._filter_depositor_name.addItem("All")
        filter_layout.addRow("Depositor Name:", self._filter_depositor_name)

        self._filter_depositor_group = QComboBox()
        self._filter_depositor_group.addItem("All")
        self._filter_depositor_group.addItem("Unknown")
        filter_layout.addRow("Depositor Group:", self._filter_depositor_group)

        self._filter_by_month = QComboBox()
        self._filter_by_month.addItem("All")
        for m in range(1, 13):
            self._filter_by_month.addItem(date(2000, m, 1).strftime("%B"))
        filter_layout.addRow("By Month (due date):", self._filter_by_month)

        btn_apply = QPushButton("Apply Filters")
        btn_apply.clicked.connect(self._on_apply_filters)
        filter_layout.addRow("", btn_apply)

        layout.addWidget(filter_group)

        # Global parameters panel
        params_group = QGroupBox("Calculation Parameters (applied to all records)")
        params_layout = QFormLayout(params_group)

        self._global_interest_rate = QDoubleSpinBox()
        self._global_interest_rate.setRange(0.0, 100.0)
        self._global_interest_rate.setDecimals(2)
        self._global_interest_rate.setValue(12.0)
        params_layout.addRow("Interest Rate %:", self._global_interest_rate)

        self._global_commission_rate = QDoubleSpinBox()
        self._global_commission_rate.setRange(0.0, 100.0)
        self._global_commission_rate.setDecimals(2)
        self._global_commission_rate.setValue(2.0)
        params_layout.addRow("Commission Rate %:", self._global_commission_rate)

        self._global_extension_period = QSpinBox()
        self._global_extension_period.setRange(1, 9999)
        self._global_extension_period.setValue(1)
        params_layout.addRow("Extension Period:", self._global_extension_period)

        self._global_extension_unit = QComboBox()
        self._global_extension_unit.addItems(["months", "days"])
        params_layout.addRow("Extension Unit:", self._global_extension_unit)
        self._lbl_ext_unit = params_layout.labelForField(self._global_extension_unit)

        self._global_tds_flag = QCheckBox("Apply TDS (10% of interest)")
        params_layout.addRow("TDS:", self._global_tds_flag)

        # Wire global param changes to overwrite all rows
        self._global_interest_rate.valueChanged.connect(self._on_global_param_changed)
        self._global_commission_rate.valueChanged.connect(self._on_global_param_changed)
        self._global_extension_period.valueChanged.connect(self._on_global_param_changed)
        self._global_extension_unit.currentTextChanged.connect(self._on_global_param_changed)
        self._global_tds_flag.toggled.connect(self._on_global_param_changed)

        layout.addWidget(params_group)

        # Records table
        self._table = QTableWidget(0, len(TABLE_HEADERS))
        self._table.setHorizontalHeaderLabels(TABLE_HEADERS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.itemChanged.connect(self._on_cell_changed)
        layout.addWidget(self._table)

        # Summary row
        summary_group = QGroupBox("Summary")
        summary_layout = QHBoxLayout(summary_group)
        self._lbl_total_amount = QLabel("Total Amount: --")
        self._lbl_total_interest = QLabel("Total Interest: --")
        self._lbl_total_commission = QLabel("Total Commission: --")
        self._lbl_total_tds = QLabel("Total TDS: --")
        for lbl in [self._lbl_total_amount, self._lbl_total_interest,
                    self._lbl_total_commission, self._lbl_total_tds]:
            summary_layout.addWidget(lbl)
        layout.addWidget(summary_group)

        # Action buttons
        btn_row = QHBoxLayout()
        self._btn_calculate = QPushButton("Calculate")
        self._btn_calculate.clicked.connect(self._on_calculate)
        btn_row.addWidget(self._btn_calculate)

        self._btn_generate = QPushButton("Generate Report")
        self._btn_generate.setEnabled(False)
        self._btn_generate.clicked.connect(self._on_generate_report)
        btn_row.addWidget(self._btn_generate)

        layout.addLayout(btn_row)

        # Initialise mode state
        self._on_mode_changed("Monthly")

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------

    def _on_mode_changed(self, mode: str) -> None:
        """Lock/unlock extension unit based on mode."""
        if mode == "Monthly":
            self._global_extension_unit.setCurrentText("months")
            self._global_extension_unit.setEnabled(False)
        elif mode == "Daily":
            self._global_extension_unit.setCurrentText("days")
            self._global_extension_unit.setEnabled(False)
        else:  # Both
            self._global_extension_unit.setEnabled(True)

        # Re-populate table with correct unit lock state
        if self._filtered_loans:
            self._populate_table(self._filtered_loans)

    # ------------------------------------------------------------------
    # Filter management
    # ------------------------------------------------------------------

    def _load_loans(self) -> None:
        """Reload loans from CSV and repopulate filter dropdowns."""
        self._loans = read_loans()
        self._populate_filters()

    def _populate_filters(self) -> None:
        """Populate filter combo boxes from active loan records."""
        borrower_groups = sorted({l.borrower_group for l in self._loans if l.borrower_group})
        borrower_names = sorted({l.borrower_name for l in self._loans if l.borrower_name})
        depositor_names = sorted({l.depositor_name for l in self._loans if l.depositor_name})
        depositor_groups = sorted({l.depositor_group for l in self._loans if l.depositor_group})

        def _reset_combo(combo: QComboBox, items: list, include_unknown: bool = False) -> None:
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("All")
            if include_unknown:
                combo.addItem("Unknown")
            combo.addItems(items)
            combo.blockSignals(False)

        _reset_combo(self._filter_borrower_group, borrower_groups)
        _reset_combo(self._filter_borrower_name, borrower_names)
        _reset_combo(self._filter_depositor_name, depositor_names)
        _reset_combo(self._filter_depositor_group, depositor_groups, include_unknown=True)

    def _on_apply_filters(self) -> None:
        """Apply current filter selections and populate the records table."""
        # Capture filter values BEFORE _load_loans() clears the combos
        bg = self._filter_borrower_group.currentText()
        bn = self._filter_borrower_name.currentText()
        dn = self._filter_depositor_name.currentText()
        dg = self._filter_depositor_group.currentText()
        mo = self._filter_by_month.currentText()

        self._load_loans()  # clears combos via _populate_filters()

        # Restore captured values so _get_filtered_loans() reads them correctly
        self._filter_borrower_group.setCurrentText(bg)
        self._filter_borrower_name.setCurrentText(bn)
        self._filter_depositor_name.setCurrentText(dn)
        self._filter_depositor_group.setCurrentText(dg)
        self._filter_by_month.setCurrentText(mo)

        self._filtered_loans = self._get_filtered_loans()
        self._populate_table(self._filtered_loans)
        self._calculated = False
        self._btn_generate.setEnabled(False)

    def _get_filtered_loans(self) -> List[Loan]:
        """Return filtered loans based on current filter selections."""
        bg_filter = self._filter_borrower_group.currentText()
        bn_filter = self._filter_borrower_name.currentText()
        dn_filter = self._filter_depositor_name.currentText()
        dg_filter = self._filter_depositor_group.currentText()
        month_filter = self._filter_by_month.currentText()

        any_filter_applied = (
            bg_filter != "All" or bn_filter != "All" or
            dn_filter != "All" or dg_filter != "All" or
            month_filter != "All"
        )

        result: List[Loan] = []
        today = date.today()

        for loan in self._loans:
            if not any_filter_applied:
                # No filter: show only loans with no due_date (PD-29 / R5)
                if loan.due_date is None:
                    result.append(loan)
                continue

            # Any filter applied: exclude no-due-date loans
            if loan.due_date is None:
                continue

            # Apply filters
            if bg_filter != "All":
                if (loan.borrower_group or "") != bg_filter:
                    continue

            if bn_filter != "All":
                if loan.borrower_name != bn_filter:
                    continue

            if dn_filter != "All":
                if (loan.depositor_name or "") != dn_filter:
                    continue

            if dg_filter != "All":
                if dg_filter == "Unknown":
                    if loan.depositor_group:
                        continue
                else:
                    if (loan.depositor_group or "") != dg_filter:
                        continue

            if month_filter != "All":
                month_num = datetime.strptime(month_filter, "%B").month
                # ByMonth: due_date in selected month for current calendar year,
                # including Overdue records
                if not (loan.due_date.year == today.year and
                        loan.due_date.month == month_num):
                    continue

            result.append(loan)

        return result

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------

    def _populate_table(self, loans: List[Loan]) -> None:
        """Fill the records table with loans. Applies global parameter defaults."""
        mode = self._mode_combo.currentText()
        global_rate = self._global_interest_rate.value()
        global_comm = self._global_commission_rate.value()
        global_period = self._global_extension_period.value()
        global_unit = self._global_extension_unit.currentText()
        global_tds = self._global_tds_flag.isChecked()

        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            for row_idx, loan in enumerate(loans):
                self._table.insertRow(row_idx)

                def _ro_item(text: str) -> QTableWidgetItem:
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    return item

                def _rw_item(text: str) -> QTableWidgetItem:
                    return QTableWidgetItem(text)

                self._table.setItem(row_idx, COL_REF_ID, _ro_item(loan.reference_id))
                self._table.setItem(row_idx, COL_BORROWER_NAME, _ro_item(loan.borrower_name))
                self._table.setItem(row_idx, COL_AMOUNT, _ro_item(str(loan.amount)))
                self._table.setItem(row_idx, COL_DEPOSITOR_NAME,
                                    _ro_item(loan.depositor_name or "Unknown"))
                self._table.setItem(row_idx, COL_GIVING_DATE,
                                    _ro_item(loan.giving_date.isoformat()))
                self._table.setItem(row_idx, COL_DUE_DATE,
                                    _ro_item(loan.due_date.isoformat() if loan.due_date else ""))

                self._table.setItem(row_idx, COL_INTEREST_RATE, _rw_item(f"{global_rate:.2f}"))
                self._table.setItem(row_idx, COL_COMMISSION_RATE, _rw_item(f"{global_comm:.2f}"))
                self._table.setItem(row_idx, COL_EXTENSION_PERIOD, _rw_item(str(global_period)))

                # Extension unit: locked for Monthly/Daily, editable for Both
                unit_item = _rw_item(global_unit)
                if mode != "Both":
                    unit_item.setFlags(unit_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row_idx, COL_EXTENSION_UNIT, unit_item)

                self._table.setItem(row_idx, COL_TDS_FLAG,
                                    _rw_item("true" if global_tds else "false"))

                # Result columns — blank until Calculate
                for col in [COL_INTEREST_AMOUNT, COL_COMMISSION_AMOUNT, COL_TDS_AMOUNT]:
                    self._table.setItem(row_idx, col, _ro_item(""))
        finally:
            self._table.blockSignals(False)

    def _on_global_param_changed(self) -> None:
        """Overwrite all rows with updated global parameter values (R5)."""
        if self._table.rowCount() == 0:
            return
        mode = self._mode_combo.currentText()
        global_rate = self._global_interest_rate.value()
        global_comm = self._global_commission_rate.value()
        global_period = self._global_extension_period.value()
        global_unit = self._global_extension_unit.currentText()
        global_tds = self._global_tds_flag.isChecked()

        self._table.blockSignals(True)
        try:
            for row_idx in range(self._table.rowCount()):
                self._table.item(row_idx, COL_INTEREST_RATE).setText(f"{global_rate:.2f}")
                self._table.item(row_idx, COL_COMMISSION_RATE).setText(f"{global_comm:.2f}")
                self._table.item(row_idx, COL_EXTENSION_PERIOD).setText(str(global_period))
                unit_item = self._table.item(row_idx, COL_EXTENSION_UNIT)
                if mode != "Both":
                    unit_item.setFlags(unit_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                unit_item.setText(global_unit)
                self._table.item(row_idx, COL_TDS_FLAG).setText(
                    "true" if global_tds else "false"
                )
        finally:
            self._table.blockSignals(False)

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        """Handle user edits on editable cells. No-op for read-only columns."""
        if item.column() in READONLY_COLS:
            return
        # Per-cell edits are valid; no immediate recalculation here
        # (recalculation happens on Calculate button click)

    # ------------------------------------------------------------------
    # Calculate
    # ------------------------------------------------------------------

    def _on_calculate(self) -> None:
        """Calculate interest for all rows and populate result columns."""
        mode = self._mode_combo.currentText()

        self._table.blockSignals(True)
        try:
            for row_idx in range(self._table.rowCount()):
                record = self._get_record_dict(row_idx)
                try:
                    if mode == "Monthly":
                        result = calculate_monthly(record)
                    elif mode == "Daily":
                        result = calculate_daily(record)
                    else:
                        result = calculate_both(record)
                except (ValueError, KeyError) as exc:
                    logger.warning("Calculation error at row %d: %s", row_idx, exc)
                    continue

                def _ro_item(text: str) -> QTableWidgetItem:
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    return item

                self._table.setItem(
                    row_idx, COL_INTEREST_AMOUNT,
                    _ro_item(f"{result['interest_amount']:.2f}")
                )
                self._table.setItem(
                    row_idx, COL_COMMISSION_AMOUNT,
                    _ro_item(f"{result['commission_amount']:.2f}")
                )
                self._table.setItem(
                    row_idx, COL_TDS_AMOUNT,
                    _ro_item(f"{result['tds_amount']:.2f}")
                )
        finally:
            self._table.blockSignals(False)

        self._calculated = True
        self._btn_generate.setEnabled(True)
        self._update_summary()

    def _get_record_dict(self, row_idx: int) -> dict:
        """Extract a record dict from the table row for calculator input."""
        def _cell(col: int) -> str:
            item = self._table.item(row_idx, col)
            return item.text().strip() if item else ""

        amount_str = _cell(COL_AMOUNT)
        due_date_str = _cell(COL_DUE_DATE)
        giving_date_str = _cell(COL_GIVING_DATE)
        tds_raw = _cell(COL_TDS_FLAG).lower()

        return {
            "amount": int(amount_str) if amount_str else 0,
            "interest_rate": float(_cell(COL_INTEREST_RATE) or "0"),
            "commission_rate": float(_cell(COL_COMMISSION_RATE) or "0"),
            "extension_period": int(_cell(COL_EXTENSION_PERIOD) or "0"),
            "extension_period_unit": _cell(COL_EXTENSION_UNIT) or "months",
            "tds_flag": tds_raw in ("true", "1", "yes"),
            "giving_date": date.fromisoformat(giving_date_str) if giving_date_str else date.today(),
            "due_date": date.fromisoformat(due_date_str) if due_date_str else None,
        }

    def _update_summary(self) -> None:
        """Recompute and display summary totals."""
        total_amount = 0
        total_interest = 0.0
        total_commission = 0.0
        total_tds = 0.0

        for row_idx in range(self._table.rowCount()):
            def _cell(col: int) -> str:
                item = self._table.item(row_idx, col)
                return item.text().strip() if item else ""

            amount_str = _cell(COL_AMOUNT)
            interest_str = _cell(COL_INTEREST_AMOUNT)
            commission_str = _cell(COL_COMMISSION_AMOUNT)
            tds_str = _cell(COL_TDS_AMOUNT)

            try:
                total_amount += int(amount_str) if amount_str else 0
                total_interest += float(interest_str) if interest_str else 0.0
                total_commission += float(commission_str) if commission_str else 0.0
                total_tds += float(tds_str) if tds_str else 0.0
            except ValueError:
                pass

        self._lbl_total_amount.setText(f"Total Amount: {total_amount:,}")
        self._lbl_total_interest.setText(f"Total Interest: {total_interest:.2f}")
        self._lbl_total_commission.setText(f"Total Commission: {total_commission:.2f}")
        self._lbl_total_tds.setText(f"Total TDS: {total_tds:.2f}")

    # ------------------------------------------------------------------
    # Generate Report
    # ------------------------------------------------------------------

    def _on_generate_report(self) -> None:
        """Generate a PendingReport from the current calculated table rows."""
        if not self._calculated:
            return

        try:
            from data.report_manager import (
                generate_report_id,
                write_report,
                write_report_records,
            )
            from models.report import PendingReport, ReportRecord
            from dateutil.relativedelta import relativedelta

            today = date.today()
            report_id = generate_report_id(today)
            mode = self._mode_combo.currentText()

            report = PendingReport(
                report_id=report_id,
                report_creation_date=today,
                report_latest_update_dt=datetime.now(),
                mode=mode,
                status="Pending",
            )

            records: List[ReportRecord] = []
            for row_idx in range(self._table.rowCount()):
                rec = self._build_report_record(report_id, row_idx)
                if rec is not None:
                    records.append(rec)

            if not records:
                QMessageBox.warning(self, "No Records",
                                    "No valid records to include in the report.")
                return

            write_report(report)
            write_report_records(records)
            logger.info("Report generated: %s with %d records", report_id, len(records))
            self.report_generated.emit()
            QMessageBox.information(self, "Report Generated",
                                    f"Report {report_id} has been sent to Pending Approval.")
        except Exception as exc:
            logger.error("Failed to generate report: %s", exc)
            QMessageBox.critical(self, "Error", f"Failed to generate report: {exc}")

    def _build_report_record(self, report_id: str, row_idx: int) -> Optional["ReportRecord"]:
        """Build a ReportRecord from a table row."""
        try:
            from models.report import ReportRecord
            from dateutil.relativedelta import relativedelta

            def _cell(col: int) -> str:
                item = self._table.item(row_idx, col)
                return item.text().strip() if item else ""

            ref_id = _cell(COL_REF_ID)
            due_date_str = _cell(COL_DUE_DATE)
            giving_date_str = _cell(COL_GIVING_DATE)
            extension_period = int(_cell(COL_EXTENSION_PERIOD) or "0")
            extension_unit = _cell(COL_EXTENSION_UNIT) or "months"
            due_date = date.fromisoformat(due_date_str) if due_date_str else None

            # Compute post-extension dates
            if due_date:
                new_giving_date = due_date
                if extension_unit == "months":
                    new_due_date = due_date + relativedelta(months=extension_period)
                else:
                    from datetime import timedelta
                    new_due_date = due_date + timedelta(days=extension_period)
            else:
                new_giving_date = None
                new_due_date = None

            tds_raw = _cell(COL_TDS_FLAG).lower()
            interest_str = _cell(COL_INTEREST_AMOUNT)
            commission_str = _cell(COL_COMMISSION_AMOUNT)
            tds_str = _cell(COL_TDS_AMOUNT)

            return ReportRecord(
                report_id=report_id,
                reference_id=ref_id,
                borrower_name=_cell(COL_BORROWER_NAME),
                amount=int(_cell(COL_AMOUNT) or "0"),
                depositor_name=_cell(COL_DEPOSITOR_NAME) or None,
                giving_date=date.fromisoformat(giving_date_str) if giving_date_str else date.today(),
                due_date=due_date,
                interest_rate=float(_cell(COL_INTEREST_RATE) or "0"),
                commission_rate=float(_cell(COL_COMMISSION_RATE) or "0"),
                extension_period=extension_period,
                extension_period_unit=extension_unit,
                tds_flag=tds_raw in ("true", "1", "yes"),
                new_giving_date=new_giving_date,
                new_due_date=new_due_date,
                interest_amount=float(interest_str) if interest_str else 0.0,
                commission_amount=float(commission_str) if commission_str else 0.0,
                tds_amount=float(tds_str) if tds_str else 0.0,
            )
        except Exception as exc:
            logger.warning("Failed to build ReportRecord for row %d: %s", row_idx, exc)
            return None

    # ------------------------------------------------------------------
    # Refresh on tab activation
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        """Reload loans when tab becomes visible."""
        super().showEvent(event)
        self._load_loans()
