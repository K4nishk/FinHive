"""View Tab — sortable, inline-editable loan table (Requirements 2, 3, 4)."""
import logging
from datetime import date, datetime
from typing import List, Optional

from PySide6.QtCore import (
    QDate,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from data.csv_manager import (
    delete_loan,
    extend_loan,
    mark_paidoff,
    read_loans,
    update_loan,
)
from data.report_manager import generate_report_id, write_report, write_report_records
from data.status_engine import compute_status, recompute_all
from models.loan import Loan
from models.report import PendingReport, ReportRecord
from ui.dialogs.extend_dialog import ExtendDialog
from ui.dialogs.paidoff_dialog import PaidoffDialog

logger = logging.getLogger(__name__)

# Column indices
COL_SNO = 0
COL_REF_ID = 1
COL_BORROWER_NAME = 2
COL_BORROWER_GROUP = 3
COL_AMOUNT = 4
COL_DEPOSITOR_NAME = 5
COL_DEPOSITOR_GROUP = 6
COL_GIVING_DATE = 7
COL_DUE_DATE = 8
COL_STATUS = 9

COLUMN_HEADERS = [
    "SNo",
    "Ref ID",
    "Borrower Name",
    "Borrower Group",
    "Amount",
    "Depositor Name",
    "Depositor Group",
    "Giving Date",
    "Due Date",
    "Status",
]

STATUS_COLORS = {
    "Active": QColor("#d4edda"),
    "Overdue": QColor("#f8d7da"),
    "Pending": QColor("#fff3cd"),
    "Paidoff": QColor("#e2e3e5"),
}


class ViewTab(QWidget):
    """Displays all active loans in a sortable, inline-editable table."""

    data_changed = Signal()  # emitted whenever a loan is modified

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._loans: List[Loan] = []
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self.load_data)
        toolbar.addWidget(self._refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Model + proxy for sorting
        self._model = QStandardItemModel(0, len(COLUMN_HEADERS))
        self._model.setHorizontalHeaderLabels(COLUMN_HEADERS)
        self._model.itemChanged.connect(self._on_item_changed)

        self._proxy = QSortFilterProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.doubleClicked.connect(self._on_double_click)

        # Make ref_id and SNo columns non-editable via delegate workaround
        layout.addWidget(self._table)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_data(self) -> None:
        """Reload loans from CSV, recompute status, persist only changed statuses."""
        try:
            loans = read_loans()
            # Snapshot status BEFORE recompute_all() mutates Loan objects in place
            snapshot = {loan.reference_id: loan.status for loan in loans}
            loans = recompute_all(loans, date.today())
            # Only write loans whose status genuinely changed
            changed = [l for l in loans if l.status != snapshot.get(l.reference_id)]
            for loan in changed:
                update_loan(loan)
            # SRE-mandated log line for operational verification
            if changed:
                logger.info("Refresh: %d loan(s) status changed — persisted", len(changed))
            else:
                logger.debug("Refresh: no status changes — skipping all writes")
        except Exception as exc:
            logger.error("Failed to load loans: %s", exc)
            QMessageBox.critical(self, "Error", f"Could not load loan data: {exc}")
            return

        self._loans = loans
        self._populate_model()

    def _populate_model(self) -> None:
        """Fill the model from self._loans without triggering itemChanged.

        Disconnects itemChanged (not blockSignals) so the QSortFilterProxyModel
        still receives rowsInserted/rowsRemoved and keeps its mapping current.
        """
        self._model.itemChanged.disconnect(self._on_item_changed)
        try:
            self._model.removeRows(0, self._model.rowCount())
            for sno, loan in enumerate(self._loans, start=1):
                row_items = self._make_row(sno, loan)
                self._model.appendRow(row_items)
            self._table.resizeColumnsToContents()
        finally:
            self._model.itemChanged.connect(self._on_item_changed)

    def _make_row(self, sno: int, loan: Loan) -> List[QStandardItem]:
        """Create a list of QStandardItem for one loan row."""
        color = STATUS_COLORS.get(loan.status, QColor("white"))

        def item(text: str, editable: bool = True) -> QStandardItem:
            it = QStandardItem(text)
            it.setEditable(editable)
            it.setBackground(color)
            return it

        def numeric_item(value: int, editable: bool = True) -> QStandardItem:
            """Numeric item sorts correctly when data role is integer."""
            it = QStandardItem()
            it.setData(value, Qt.ItemDataRole.DisplayRole)
            it.setEditable(editable)
            it.setBackground(color)
            return it

        depositor_name = loan.depositor_name or "Unknown"
        depositor_group = loan.depositor_group or "Unknown"
        due_date_str = loan.due_date.isoformat() if loan.due_date else "Unknown"

        row = [
            numeric_item(sno, editable=False),                     # SNo
            item(loan.reference_id, editable=False),               # Ref ID
            item(loan.borrower_name),                              # Borrower Name
            item(loan.borrower_group),                             # Borrower Group
            numeric_item(loan.amount),                             # Amount
            item(depositor_name),                                  # Depositor Name
            item(depositor_group),                                 # Depositor Group
            item(loan.giving_date.isoformat()),                    # Giving Date
            item(due_date_str),                                    # Due Date
            item(loan.status, editable=False),                     # Status
        ]

        # Store reference_id in the first item's user data for easy retrieval
        row[COL_SNO].setData(loan.reference_id, Qt.ItemDataRole.UserRole)
        return row

    # ------------------------------------------------------------------
    # Inline editing
    # ------------------------------------------------------------------

    def _on_item_changed(self, item: QStandardItem) -> None:
        """Persist inline edit changes back to CSV."""
        if not item.isEditable():
            return

        ref_id = self._get_ref_id_for_row(item.row())
        loan = self._find_loan(ref_id)
        if loan is None:
            logger.warning("Could not find loan for ref_id: %s", ref_id)
            return

        col = item.column()
        new_val = item.text().strip()

        try:
            if col == COL_BORROWER_NAME:
                loan.borrower_name = new_val
            elif col == COL_BORROWER_GROUP:
                loan.borrower_group = new_val
            elif col == COL_AMOUNT:
                loan.amount = int(new_val)
            elif col == COL_DEPOSITOR_NAME:
                loan.depositor_name = new_val if new_val and new_val != "Unknown" else None
            elif col == COL_DEPOSITOR_GROUP:
                loan.depositor_group = new_val if new_val and new_val != "Unknown" else None
            elif col == COL_GIVING_DATE:
                loan.giving_date = date.fromisoformat(new_val)
                loan.status = compute_status(loan, date.today())
            elif col == COL_DUE_DATE:
                if new_val and new_val != "Unknown":
                    loan.due_date = date.fromisoformat(new_val)
                else:
                    loan.due_date = None
                loan.status = compute_status(loan, date.today())
            else:
                return  # nothing to update for other cols

            update_loan(loan)
            self._refresh_row(item.row(), loan)
            logger.info("Loan %s updated (col %d)", ref_id, col)
            self.data_changed.emit()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Value", f"Could not parse value: {exc}")
            self.load_data()  # revert by full reload
        except Exception as exc:
            logger.error("Failed to update loan %s: %s", ref_id, exc)
            QMessageBox.critical(self, "Error", f"Could not save change: {exc}")
            self.load_data()

    def _refresh_row(self, row: int, loan: Loan) -> None:
        """Refresh a single row in-place after an edit."""
        self._model.itemChanged.disconnect(self._on_item_changed)
        try:
            sno_item = self._model.item(row, COL_SNO)
            sno = sno_item.data(Qt.ItemDataRole.DisplayRole) if sno_item else row + 1
            new_items = self._make_row(sno, loan)
            for col, it in enumerate(new_items):
                self._model.setItem(row, col, it)
        finally:
            self._model.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        index = self._table.indexAt(pos)
        if not index.isValid():
            return

        src_index = self._proxy.mapToSource(index)
        row = src_index.row()
        ref_id = self._get_ref_id_for_row(row)
        loan = self._find_loan(ref_id)
        if loan is None:
            return

        menu = QMenu(self)

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self._action_delete(ref_id))
        menu.addAction(delete_action)

        extend_action = QAction("Extend", self)
        extend_action.triggered.connect(lambda: self._action_extend(loan))
        menu.addAction(extend_action)

        paidoff_action = QAction("Mark Paidoff", self)
        paidoff_action.triggered.connect(lambda: self._action_paidoff(loan))
        menu.addAction(paidoff_action)

        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _action_delete(self, ref_id: str) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete loan {ref_id}? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = delete_loan(ref_id)
            if not deleted:
                QMessageBox.warning(self, "Not Found", f"Loan {ref_id} not found.")
            else:
                logger.info("Loan deleted: %s", ref_id)
                self.data_changed.emit()
        except Exception as exc:
            logger.error("Failed to delete loan %s: %s", ref_id, exc)
            QMessageBox.critical(self, "Error", f"Could not delete loan: {exc}")
        finally:
            self.load_data()

    def _action_extend(self, loan: Loan) -> None:
        dialog = ExtendDialog(loan.reference_id, loan.due_date, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            new_giving = dialog.new_giving_date()
            new_due = dialog.new_due_date()
            extend_loan(loan.reference_id, new_giving, new_due)
            loan.giving_date = new_giving
            loan.due_date = new_due
            loan.status = compute_status(loan, date.today())
            update_loan(loan)
            logger.info("Loan extended: %s", loan.reference_id)
            self.data_changed.emit()
        except Exception as exc:
            logger.error("Failed to extend loan %s: %s", loan.reference_id, exc)
            QMessageBox.critical(self, "Error", f"Could not extend loan: {exc}")
        finally:
            self.load_data()

    def _action_paidoff(self, loan: Loan) -> None:
        dialog = PaidoffDialog(loan.reference_id, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            paidoff_date = dialog.paidoff_date()
            interest_rate = dialog.interest_rate()
            commission_rate = dialog.commission_rate()
            tds_flag = dialog.tds_flag()

            # Step 1: archive loan (with recovery.tmp crash safety)
            mark_paidoff(loan.reference_id, paidoff_date)
            logger.info("Loan marked paidoff: %s", loan.reference_id)

            # Step 2: compute extension period (TC-401: 0 if no due_date)
            if loan.due_date is not None:
                extension_period = (paidoff_date - loan.due_date).days
            else:
                extension_period = 0
                logger.debug(
                    "Paidoff report for %s: no due_date, extension_period=0",
                    loan.reference_id,
                )

            # Step 3: compute interest amounts
            if extension_period > 0:
                interest_amount = (
                    loan.amount * interest_rate * extension_period
                ) / (365 * 100)
                commission_amount = (
                    loan.amount * commission_rate * extension_period
                ) / (365 * 100)
            else:
                interest_amount = 0.0
                commission_amount = 0.0

            tds_amount = round(0.1 * interest_amount, 4) if tds_flag else 0.0
            interest_amount = round(interest_amount, 4)
            commission_amount = round(commission_amount, 4)

            # Step 4: generate report and send to Pending Approval queue
            try:
                today = date.today()
                report_id = generate_report_id(today)
                now = datetime.now()

                report = PendingReport(
                    report_id=report_id,
                    report_creation_date=today,
                    report_latest_update_dt=now,
                    mode="Paidoff",
                    status="Pending",
                )
                write_report(report)

                record = ReportRecord(
                    report_id=report_id,
                    reference_id=loan.reference_id,
                    borrower_name=loan.borrower_name,
                    amount=loan.amount,
                    depositor_name=loan.depositor_name,
                    giving_date=loan.giving_date,
                    due_date=loan.due_date,
                    interest_rate=interest_rate,
                    commission_rate=commission_rate,
                    extension_period=extension_period,
                    extension_period_unit="days",
                    tds_flag=tds_flag,
                    new_giving_date=None,
                    new_due_date=None,
                    interest_amount=interest_amount,
                    commission_amount=commission_amount,
                    tds_amount=tds_amount,
                )
                write_report_records([record])
                logger.info(
                    "Paidoff report generated: %s for loan %s",
                    report_id, loan.reference_id,
                )
            except Exception as report_exc:
                # Report generation failure does NOT undo the paidoff archival.
                # Log error and notify user — loan is safely in history.csv.
                logger.error(
                    "Paidoff report generation failed for %s: %s",
                    loan.reference_id, report_exc,
                )
                QMessageBox.warning(
                    self,
                    "Report Generation Failed",
                    f"Loan {loan.reference_id} has been marked as Paidoff "
                    f"and moved to history.\n\n"
                    f"However, the interest report could not be generated: "
                    f"{report_exc}\n\n"
                    f"You can manually generate the report from the Interest "
                    f"Calculator Tab.",
                )

            self.data_changed.emit()
        except Exception as exc:
            logger.error("Failed to mark paidoff %s: %s", loan.reference_id, exc)
            QMessageBox.critical(
                self, "Error", f"Could not mark loan as Paidoff: {exc}"
            )
        finally:
            self.load_data()

    # ------------------------------------------------------------------
    # Double-click handler (inline edit is default; double-click opens cell)
    # ------------------------------------------------------------------

    def _on_double_click(self, index: QModelIndex) -> None:
        """Allow double-click to start editing the cell (default behaviour)."""
        src_index = self._proxy.mapToSource(index)
        item = self._model.itemFromIndex(src_index)
        if item and item.isEditable():
            self._table.edit(index)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_ref_id_for_row(self, row: int) -> str:
        sno_item = self._model.item(row, COL_SNO)
        if sno_item is None:
            return ""
        return sno_item.data(Qt.ItemDataRole.UserRole) or ""

    def _find_loan(self, ref_id: str) -> Optional[Loan]:
        for loan in self._loans:
            if loan.reference_id == ref_id:
                return loan
        return None
