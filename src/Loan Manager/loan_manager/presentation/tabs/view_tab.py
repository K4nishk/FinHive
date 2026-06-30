from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton, QMenu,
    QMessageBox, QStyledItemDelegate, QHeaderView,
)
from PySide6.QtCore import Qt, QSortFilterProxyModel, QModelIndex

from loan_manager.application.dtos.loan_dto import LoanUpdateDTO, LoanDTO
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.application.use_cases.loans.update_loan import UpdateLoan
from loan_manager.application.use_cases.loans.delete_loan import DeleteLoan
from loan_manager.application.use_cases.loans.extend_loan import ExtendLoan
from loan_manager.application.use_cases.loans.mark_paidoff import MarkPaidOff
from loan_manager.domain.value_objects.status import LoanStatus
from loan_manager.presentation.widgets.loan_table_model import LoanTableModel, COLUMNS, COL_IDX
from loan_manager.presentation.widgets.status_combobox import StatusDelegate
from loan_manager.presentation.widgets.column_filter_widget import ColumnFilterWidget
from loan_manager.presentation.dialogs.date_picker_dialog import DatePickerDialog
from loan_manager.presentation.dialogs.extend_dialog import ExtendDialog
from loan_manager.presentation.dialogs.paidoff_dialog import PaidOffDialog


class DateDelegate(QStyledItemDelegate):
    """Delegate that opens DatePickerDialog for date columns."""

    def createEditor(self, parent, option, index):
        return None  # We handle editing via double-click

    def editorEvent(self, event, model, option, index):
        return False


class MultiColumnFilterProxy(QSortFilterProxyModel):
    """Proxy model that supports per-column filtering."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._column_filters: dict[int, list[str]] = {}

    def set_column_filter(self, column: int, values: list[str]) -> None:
        if values:
            self._column_filters[column] = values
        else:
            self._column_filters.pop(column, None)
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._column_filters:
            return True
        model = self.sourceModel()
        for col, allowed in self._column_filters.items():
            if not allowed:
                continue
            index = model.index(source_row, col, source_parent)
            value = model.data(index, Qt.ItemDataRole.DisplayRole)
            if value not in allowed:
                return False
        return True


class ViewTab(QWidget):
    def __init__(self, container, theme_manager, parent=None):
        super().__init__(parent)
        self._container = container
        self._theme = theme_manager
        self._main_window = parent
        self._filter_widgets: list[ColumnFilterWidget] = []
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Filter bar
        filter_bar = QHBoxLayout()
        filterable = [
            (COL_IDX["B Name"], "B Name", False),
            (COL_IDX["B Grp"], "B Grp", False),
            (COL_IDX["D Name"], "D Name", False),
            (COL_IDX["D Grp"], "D Grp", False),
            (COL_IDX["G Date"], "G Date", True),
            (COL_IDX["D Date"], "D Date", True),
            (COL_IDX["Status"], "Status", False),
        ]
        for col_idx, name, is_date in filterable:
            fw = ColumnFilterWidget(col_idx, name, is_date=is_date)
            fw.filter_changed.connect(self._on_filter_changed)
            filter_bar.addWidget(fw)
            self._filter_widgets.append(fw)
        filter_bar.addStretch()
        layout.addLayout(filter_bar)

        # Table
        self._model = LoanTableModel(self._theme)
        self._proxy = MultiColumnFilterProxy()
        self._proxy.setSourceModel(self._model)
        self._proxy.setDynamicSortFilter(True)

        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.doubleClicked.connect(self._on_double_click)

        # Set column widths
        header = self._table.horizontalHeader()
        header.setStretchLastSection(True)
        col_widths = {0: 40, 1: 120, 2: 100, 3: 80, 4: 80, 5: 100, 6: 80, 7: 90, 8: 90, 9: 90}
        for col, width in col_widths.items():
            self._table.setColumnWidth(col, width)

        # Set status delegate
        self._status_delegate = StatusDelegate(self._theme, self._table)
        self._table.setItemDelegateForColumn(COL_IDX["Status"], self._status_delegate)

        layout.addWidget(self._table)

    def refresh(self) -> None:
        try:
            get_loans = GetAllLoans(self._container.get_uow)
            loans = get_loans.execute()
            self._model.load(loans)
            self._update_filters(loans)
        except Exception as e:
            if self._main_window:
                self._main_window.show_status(f"Error loading loans: {e}")

    def _update_filters(self, loans: list[LoanDTO]) -> None:
        for fw in self._filter_widgets:
            col = fw._col
            values = []
            for loan in loans:
                val = self._model._display_value(loan, col, 0)
                values.append(val)
            fw.populate(values)

    def _on_filter_changed(self, column: int, values: list[str]) -> None:
        self._proxy.set_column_filter(column, values)

    def _on_double_click(self, proxy_index: QModelIndex) -> None:
        source_index = self._proxy.mapToSource(proxy_index)
        col = source_index.column()
        row = source_index.row()
        loan = self._model.loan_at(row)
        if loan is None:
            return

        # Date columns: open DatePickerDialog
        if col in (COL_IDX["G Date"], COL_IDX["D Date"]):
            current = loan.giving_date if col == COL_IDX["G Date"] else loan.due_date
            dlg = DatePickerDialog(current, self)
            if dlg.exec() == DatePickerDialog.DialogCode.Accepted:
                new_date = dlg.selected_date()
                if new_date:
                    field = "giving_date" if col == COL_IDX["G Date"] else "due_date"
                    self._update_loan_field(loan.reference_id, field, new_date)
            return

        # Status column: handled via delegate, but capture setData
        if col == COL_IDX["Status"]:
            return

        # Text columns: use inline editing (default delegate handles it)
        # We handle the commit via a timer approach

    def _show_context_menu(self, pos) -> None:
        index = self._table.indexAt(pos)
        if not index.isValid():
            return
        source_index = self._proxy.mapToSource(index)
        loan = self._model.loan_at(source_index.row())
        if loan is None:
            return

        menu = QMenu(self)
        extend_action = menu.addAction("Extend")
        paidoff_action = menu.addAction("Mark Paidoff")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")

        # Disable paidoff if no due_date
        if loan.due_date is None:
            paidoff_action.setEnabled(False)

        action = menu.exec(self._table.viewport().mapToGlobal(pos))
        if action == extend_action:
            self._extend_loan(loan)
        elif action == paidoff_action:
            self._mark_paidoff(loan)
        elif action == delete_action:
            self._delete_loan(loan)

    def _extend_loan(self, loan: LoanDTO) -> None:
        dlg = ExtendDialog(loan, self)
        if dlg.exec() == ExtendDialog.DialogCode.Accepted:
            result = dlg.get_result()
            if result:
                try:
                    extend_uc = ExtendLoan(
                        self._container.get_uow,
                        self._container.event_bus,
                    )
                    extend_uc.execute(loan.reference_id, result)
                    if self._main_window:
                        self._main_window.show_status(
                            f"Loan {loan.reference_id} extended successfully."
                        )
                    self.refresh()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to extend loan: {e}")

    def _mark_paidoff(self, loan: LoanDTO) -> None:
        dlg = PaidOffDialog(loan, self)
        if dlg.exec() == PaidOffDialog.DialogCode.Accepted:
            result = dlg.get_result()
            if result:
                try:
                    paidoff_uc = MarkPaidOff(
                        self._container.get_uow,
                        self._container.event_bus,
                    )
                    paidoff_uc.execute(loan.reference_id, result)
                    if self._main_window:
                        self._main_window.show_status(
                            f"Paidoff report generated for {loan.reference_id}. "
                            "Check Pending Approval tab."
                        )
                    self.refresh()
                    # Refresh pending approval tab
                    if hasattr(self._main_window, '_approval_tab'):
                        self._main_window._approval_tab.refresh()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to mark paidoff: {e}")

    def _delete_loan(self, loan: LoanDTO) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete loan {loan.reference_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                delete_uc = DeleteLoan(self._container.get_uow)
                delete_uc.execute(loan.reference_id)
                if self._main_window:
                    self._main_window.show_status(
                        f"Loan {loan.reference_id} deleted."
                    )
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete loan: {e}")

    def _update_loan_field(self, ref_id: str, field: str, value) -> None:
        try:
            update_data = {field: value}
            dto = LoanUpdateDTO(**update_data)
            update_uc = UpdateLoan(self._container.get_uow)
            update_uc.execute(ref_id, dto)
            if self._main_window:
                self._main_window.show_status(f"Loan {ref_id} updated.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update loan: {e}")
