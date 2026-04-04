"""Calculation Dialog — R5 Phase 4 implementation.

Launched when user clicks "Calculate" in the Interest Calculator Tab.
Displays filtered records with inline-editable parameters and on-the-fly
calculation updates. User generates report from within this dialog.

CHQ_Amt formula (R5):
    tds_flag=True:  CHQ_Amt = interest_amount - tds_amount
    tds_flag=False: CHQ_Amt = 0.9 * interest_amount

Report column order per R5 spec:
    [Amount, Giving Date, Depositor, Extension Period, Extension Period Unit,
     Due Date, Interest Amount, TDS, CHQ_Amt, Commission Amount]
"""
import logging
from datetime import date, datetime
from typing import List, Optional

from dateutil.relativedelta import relativedelta
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from loan_manager.interest_calculator import (
    calculate_both,
    calculate_daily,
    calculate_monthly,
)
from models.loan import Loan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column indices
# ---------------------------------------------------------------------------
COL_REF_ID = 0
COL_BORROWER = 1
COL_AMOUNT = 2
COL_DEPOSITOR = 3
COL_GIVING_DATE = 4
COL_DUE_DATE = 5
COL_INT_RATE = 6
COL_COMM_RATE = 7
COL_EXT_PERIOD = 8
COL_EXT_UNIT = 9
COL_TDS_FLAG = 10
COL_INTEREST = 11
COL_TDS_AMT = 12
COL_CHQ_AMT = 13
COL_COMMISSION = 14

DIALOG_HEADERS = [
    "Ref ID", "Borrower", "Amount", "Depositor",
    "Giving Date", "Due Date",
    "Int Rate %", "Comm Rate %", "Ext Period", "Ext Unit", "TDS",
    "Interest", "TDS Amount", "CHQ Amt", "Commission",
]

READONLY_COLS = {
    COL_REF_ID, COL_BORROWER, COL_AMOUNT, COL_DEPOSITOR,
    COL_GIVING_DATE, COL_DUE_DATE,
    COL_INTEREST, COL_TDS_AMT, COL_CHQ_AMT, COL_COMMISSION,
}


def _compute_chq_amt(interest_amount: float, tds_amount: float, tds_flag: bool) -> float:
    """R5: CHQ_Amt = interest - TDS (tds_flag=True) or 0.9 * interest (tds_flag=False)."""
    if tds_flag:
        return interest_amount - tds_amount
    return 0.9 * interest_amount


class CalculationDialog(QDialog):
    """Modal dialog for reviewing and editing calculation results before report generation.

    Receives filtered loans and global parameters from InterestCalculatorTab.
    All parameter cells are inline-editable; changing any cell triggers immediate
    recalculation for that row.
    """

    report_generated = Signal()

    def __init__(
        self,
        filtered_loans: List[Loan],
        mode: str,
        global_interest_rate: float,
        global_commission_rate: float,
        global_extension_period: int,
        global_extension_unit: str,
        global_tds_flag: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Interest Calculation Review")
        self.setMinimumSize(1200, 600)
        self.setModal(True)

        self._loans = filtered_loans
        self._mode = mode
        self._global_interest_rate = global_interest_rate
        self._global_commission_rate = global_commission_rate
        self._global_extension_period = global_extension_period
        self._global_extension_unit = global_extension_unit
        self._global_tds_flag = global_tds_flag

        self._build_ui()
        self._populate_table()
        self._calculate_all()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Info label
        info = QLabel(
            f"Mode: {self._mode} | Edit parameters below to update calculations on-the-fly. "
            f"Click 'Generate Report' to send to Pending Approval."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Records table
        self._table = QTableWidget(0, len(DIALOG_HEADERS))
        self._table.setHorizontalHeaderLabels(DIALOG_HEADERS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.itemChanged.connect(self._on_cell_changed)
        layout.addWidget(self._table)

        # Summary row
        self._lbl_summary = QLabel("Summary: calculating...")
        layout.addWidget(self._lbl_summary)

        # Buttons
        btn_row = QHBoxLayout()

        self._btn_generate = QPushButton("Generate Report")
        self._btn_generate.clicked.connect(self._on_generate_report)
        btn_row.addWidget(self._btn_generate)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self._btn_cancel)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Table population
    # ------------------------------------------------------------------

    def _populate_table(self) -> None:
        """Fill table with filtered loans using global parameter defaults."""
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            for row_idx, loan in enumerate(self._loans):
                self._table.insertRow(row_idx)

                def _ro(text: str) -> QTableWidgetItem:
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    return item

                def _rw(text: str) -> QTableWidgetItem:
                    return QTableWidgetItem(text)

                self._table.setItem(row_idx, COL_REF_ID, _ro(loan.reference_id))
                self._table.setItem(row_idx, COL_BORROWER, _ro(loan.borrower_name))
                self._table.setItem(row_idx, COL_AMOUNT, _ro(str(loan.amount)))
                self._table.setItem(row_idx, COL_DEPOSITOR, _ro(loan.depositor_name or "Unknown"))
                self._table.setItem(row_idx, COL_GIVING_DATE, _ro(loan.giving_date.isoformat()))
                self._table.setItem(
                    row_idx, COL_DUE_DATE,
                    _ro(loan.due_date.isoformat() if loan.due_date else "")
                )

                # Editable parameter columns
                self._table.setItem(
                    row_idx, COL_INT_RATE, _rw(f"{self._global_interest_rate:.2f}")
                )
                self._table.setItem(
                    row_idx, COL_COMM_RATE, _rw(f"{self._global_commission_rate:.2f}")
                )
                self._table.setItem(
                    row_idx, COL_EXT_PERIOD, _rw(str(self._global_extension_period))
                )

                # Extension unit: lock for Monthly/Daily modes
                unit_item = _rw(self._global_extension_unit)
                if self._mode != "Both":
                    unit_item.setFlags(unit_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self._table.setItem(row_idx, COL_EXT_UNIT, unit_item)

                self._table.setItem(
                    row_idx, COL_TDS_FLAG,
                    _rw("true" if self._global_tds_flag else "false")
                )

                # Result columns — populated by _calculate_all()
                for col in [COL_INTEREST, COL_TDS_AMT, COL_CHQ_AMT, COL_COMMISSION]:
                    self._table.setItem(row_idx, col, _ro(""))
        finally:
            self._table.blockSignals(False)

    # ------------------------------------------------------------------
    # Calculation
    # ------------------------------------------------------------------

    def _calculate_all(self) -> None:
        """Calculate interest for all rows and populate result columns."""
        self._table.blockSignals(True)
        try:
            total_amount = 0
            total_interest = 0.0
            total_commission = 0.0
            total_tds = 0.0

            for row_idx in range(self._table.rowCount()):
                record = self._get_record_dict(row_idx)
                try:
                    if self._mode == "Monthly":
                        result = calculate_monthly(record)
                    elif self._mode == "Daily":
                        result = calculate_daily(record)
                    else:
                        result = calculate_both(record)
                except (ValueError, KeyError) as exc:
                    logger.warning("Calculation error at row %d: %s", row_idx, exc)
                    continue

                interest = result["interest_amount"]
                commission = result["commission_amount"]
                tds = result["tds_amount"]
                tds_flag = record.get("tds_flag", False)
                chq_amt = _compute_chq_amt(interest, tds, tds_flag)

                def _ro(text: str) -> QTableWidgetItem:
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    return item

                self._table.setItem(row_idx, COL_INTEREST, _ro(f"{interest:.2f}"))
                self._table.setItem(row_idx, COL_TDS_AMT, _ro(f"{tds:.2f}"))
                self._table.setItem(row_idx, COL_CHQ_AMT, _ro(f"{chq_amt:.2f}"))
                self._table.setItem(row_idx, COL_COMMISSION, _ro(f"{commission:.2f}"))

                amount_str = self._cell(row_idx, COL_AMOUNT)
                total_amount += int(amount_str) if amount_str else 0
                total_interest += interest
                total_commission += commission
                total_tds += tds
        finally:
            self._table.blockSignals(False)

        self._lbl_summary.setText(
            f"Total Amount: {total_amount:,}  |  "
            f"Total Interest: {total_interest:.2f}  |  "
            f"Total Commission: {total_commission:.2f}  |  "
            f"Total TDS: {total_tds:.2f}"
        )

    def _recalc_row(self, row_idx: int) -> None:
        """Recalculate a single row after an inline edit."""
        record = self._get_record_dict(row_idx)
        try:
            if self._mode == "Monthly":
                result = calculate_monthly(record)
            elif self._mode == "Daily":
                result = calculate_daily(record)
            else:
                result = calculate_both(record)
        except (ValueError, KeyError) as exc:
            logger.warning("Recalc error at row %d: %s", row_idx, exc)
            return

        interest = result["interest_amount"]
        commission = result["commission_amount"]
        tds = result["tds_amount"]
        tds_flag = record.get("tds_flag", False)
        chq_amt = _compute_chq_amt(interest, tds, tds_flag)

        self._table.blockSignals(True)
        try:
            def _ro(text: str) -> QTableWidgetItem:
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                return item

            self._table.setItem(row_idx, COL_INTEREST, _ro(f"{interest:.2f}"))
            self._table.setItem(row_idx, COL_TDS_AMT, _ro(f"{tds:.2f}"))
            self._table.setItem(row_idx, COL_CHQ_AMT, _ro(f"{chq_amt:.2f}"))
            self._table.setItem(row_idx, COL_COMMISSION, _ro(f"{commission:.2f}"))
        finally:
            self._table.blockSignals(False)

    def _on_cell_changed(self, item: QTableWidgetItem) -> None:
        """Handle inline edit — recalculate if a parameter column was changed."""
        if item.column() in READONLY_COLS:
            return
        self._recalc_row(item.row())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cell(self, row_idx: int, col: int) -> str:
        item = self._table.item(row_idx, col)
        return item.text().strip() if item else ""

    def _get_record_dict(self, row_idx: int) -> dict:
        """Extract a record dict from a table row for calculator input."""
        amount_str = self._cell(row_idx, COL_AMOUNT)
        due_date_str = self._cell(row_idx, COL_DUE_DATE)
        giving_date_str = self._cell(row_idx, COL_GIVING_DATE)
        tds_raw = self._cell(row_idx, COL_TDS_FLAG).lower()

        return {
            "amount": int(amount_str) if amount_str else 0,
            "interest_rate": float(self._cell(row_idx, COL_INT_RATE) or "0"),
            "commission_rate": float(self._cell(row_idx, COL_COMM_RATE) or "0"),
            "extension_period": int(self._cell(row_idx, COL_EXT_PERIOD) or "0"),
            "extension_period_unit": self._cell(row_idx, COL_EXT_UNIT) or "months",
            "tds_flag": tds_raw in ("true", "1", "yes"),
            "giving_date": date.fromisoformat(giving_date_str) if giving_date_str else date.today(),
            "due_date": date.fromisoformat(due_date_str) if due_date_str else None,
        }

    # ------------------------------------------------------------------
    # Generate Report
    # ------------------------------------------------------------------

    def _on_generate_report(self) -> None:
        """Generate a PendingReport from the current dialog table rows."""
        try:
            from data.report_manager import generate_report_id, write_report, write_report_records
            from models.report import PendingReport, ReportRecord

            today = date.today()
            report_id = generate_report_id(today)

            report = PendingReport(
                report_id=report_id,
                report_creation_date=today,
                report_latest_update_dt=datetime.now(),
                mode=self._mode,
                status="Pending",
            )

            records: List[ReportRecord] = []
            for row_idx in range(self._table.rowCount()):
                rec = self._build_report_record(report_id, row_idx)
                if rec is not None:
                    records.append(rec)

            if not records:
                QMessageBox.warning(
                    self, "No Records", "No valid records to include in the report."
                )
                return

            write_report(report)
            write_report_records(records)
            logger.info(
                "Calculation dialog report generated: %s with %d records",
                report_id, len(records),
            )
            self.report_generated.emit()
            QMessageBox.information(
                self, "Report Generated",
                f"Report {report_id} has been sent to Pending Approval.",
            )
            self.accept()
        except Exception as exc:
            logger.error("Failed to generate report from dialog: %s", exc)
            QMessageBox.critical(self, "Error", f"Failed to generate report:\n{exc}")

    def _build_report_record(self, report_id: str, row_idx: int) -> Optional["ReportRecord"]:
        """Build a ReportRecord from a dialog table row."""
        try:
            from models.report import ReportRecord

            ref_id = self._cell(row_idx, COL_REF_ID)
            due_date_str = self._cell(row_idx, COL_DUE_DATE)
            giving_date_str = self._cell(row_idx, COL_GIVING_DATE)
            extension_period = int(self._cell(row_idx, COL_EXT_PERIOD) or "0")
            extension_unit = self._cell(row_idx, COL_EXT_UNIT) or "months"
            due_date = date.fromisoformat(due_date_str) if due_date_str else None
            tds_raw = self._cell(row_idx, COL_TDS_FLAG).lower()
            tds_flag = tds_raw in ("true", "1", "yes")

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

            interest_str = self._cell(row_idx, COL_INTEREST)
            commission_str = self._cell(row_idx, COL_COMMISSION)
            tds_str = self._cell(row_idx, COL_TDS_AMT)

            interest_amount = float(interest_str) if interest_str else 0.0
            commission_amount = float(commission_str) if commission_str else 0.0
            tds_amount = float(tds_str) if tds_str else 0.0

            return ReportRecord(
                report_id=report_id,
                reference_id=ref_id,
                borrower_name=self._cell(row_idx, COL_BORROWER),
                amount=int(self._cell(row_idx, COL_AMOUNT) or "0"),
                depositor_name=self._cell(row_idx, COL_DEPOSITOR) or None,
                giving_date=date.fromisoformat(giving_date_str) if giving_date_str else date.today(),
                due_date=due_date,
                interest_rate=float(self._cell(row_idx, COL_INT_RATE) or "0"),
                commission_rate=float(self._cell(row_idx, COL_COMM_RATE) or "0"),
                extension_period=extension_period,
                extension_period_unit=extension_unit,
                tds_flag=tds_flag,
                new_giving_date=new_giving_date,
                new_due_date=new_due_date,
                interest_amount=interest_amount,
                commission_amount=commission_amount,
                tds_amount=tds_amount,
            )
        except Exception as exc:
            logger.warning("Failed to build ReportRecord for row %d: %s", row_idx, exc)
            return None
