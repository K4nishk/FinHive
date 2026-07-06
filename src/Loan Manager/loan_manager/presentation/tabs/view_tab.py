from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QPushButton, QMenu,
    QMessageBox, QStyledItemDelegate, QHeaderView, QLabel, QFrame,
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

# Date column indices for prefix-based matching
_DATE_COLUMNS = {COL_IDX["G Date"], COL_IDX["D Date"]}


class DateDelegate(QStyledItemDelegate):
    """Delegate that opens DatePickerDialog for date columns."""

    def createEditor(self, parent, option, index):
        return None  # We handle editing via double-click

    def editorEvent(self, event, model, option, index):
        return False


class MultiColumnFilterProxy(QSortFilterProxyModel):
    """Proxy model that supports per-column filtering with date prefix matching."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._column_filters: dict[int, list[str]] = {}

    def set_column_filter(self, column: int, values: list[str]) -> None:
        if values:
            self._column_filters[column] = values
        else:
            self._column_filters.pop(column, None)
        self.invalidateFilter()

    def clear_all_filters(self) -> None:
        self._column_filters.clear()
        self.invalidateFilter()

    def get_active_filters(self) -> dict[int, list[str]]:
        return dict(self._column_filters)

    # Columns that should sort numerically
    _NUMERIC_COLUMNS = {COL_IDX["SNo"], COL_IDX["Amt"]}

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        left_data = self.sourceModel().data(left, Qt.ItemDataRole.DisplayRole)
        right_data = self.sourceModel().data(right, Qt.ItemDataRole.DisplayRole)

        if left.column() in self._NUMERIC_COLUMNS:
            try:
                return int(left_data or 0) < int(right_data or 0)
            except (ValueError, TypeError):
                pass

        return (left_data or "") < (right_data or "")

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self._column_filters:
            return True
        model = self.sourceModel()
        for col, allowed in self._column_filters.items():
            if not allowed:
                continue
            index = model.index(source_row, col, source_parent)
            value = model.data(index, Qt.ItemDataRole.DisplayRole)
            cell_str = str(value) if value is not None else ""

            if col in _DATE_COLUMNS:
                # Date columns use prefix matching
                if not self._date_matches(cell_str, allowed):
                    return False
            else:
                # Text columns use exact match
                if cell_str not in allowed:
                    return False
        return True

    @staticmethod
    def _date_matches(cell_value: str, allowed: list[str]) -> bool:
        """Check if a cell date value matches any of the allowed filter selections.

        Allowed values can be:
        - "YYYY" (year): match if cell starts with "YYYY"
        - "YYYY-MM" (month): match if cell starts with "YYYY-MM"
        - "YYYY-MM-DD" (day): exact match
        - "Unknown": match empty/Unknown/None values
        """
        for selection in allowed:
            if selection == "Unknown":
                if cell_value in ("", "Unknown", "None"):
                    return True
            elif cell_value.startswith(selection):
                return True
        return False


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
        refresh_btn.setAccessibleName("Refresh loan records")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)

        self._print_btn = QPushButton("Print")
        self._print_btn.setAccessibleName("Print loan records")
        self._print_btn.clicked.connect(self._on_print)
        toolbar.addWidget(self._print_btn)

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

        # Active filters summary
        self._filter_summary_frame = QFrame()
        summary_layout = QHBoxLayout(self._filter_summary_frame)
        summary_layout.setContentsMargins(4, 2, 4, 2)
        self._filter_summary_label = QLabel("")
        self._filter_summary_label.setAccessibleName("Active filters summary")
        summary_layout.addWidget(self._filter_summary_label)
        summary_layout.addStretch()
        self._clear_all_btn = QPushButton("Clear All")
        self._clear_all_btn.setAccessibleName("Clear all filters")
        self._clear_all_btn.clicked.connect(self._clear_all_filters)
        summary_layout.addWidget(self._clear_all_btn)
        self._filter_summary_frame.setVisible(False)
        layout.addWidget(self._filter_summary_frame)

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

        # Empty results label
        self._empty_label = QLabel("No matching records found.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setAccessibleName("No matching records found")
        self._empty_label.setStyleSheet("color: gray; font-size: 14px; padding: 20px;")
        self._empty_label.setVisible(False)
        layout.addWidget(self._empty_label)

    def refresh(self) -> None:
        try:
            get_loans = GetAllLoans(self._container.get_uow)
            loans = get_loans.execute()
            self._model.load(loans)
            self._update_filters(loans)
            self._update_empty_state()
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
        self._update_filter_summary()
        self._update_empty_state()

    def _update_filter_summary(self) -> None:
        active = self._proxy.get_active_filters()
        if not active:
            self._filter_summary_frame.setVisible(False)
            return

        parts = []
        for col, values in active.items():
            col_name = COLUMNS[col] if col < len(COLUMNS) else f"Col {col}"
            # Find matching filter widget for display name
            for fw in self._filter_widgets:
                if fw._col == col:
                    col_name = fw.column_name
                    break
            parts.append(f"{col_name}: {', '.join(values)}")

        self._filter_summary_label.setText("Active Filters:  " + "  |  ".join(parts))
        self._filter_summary_frame.setVisible(True)

    def _clear_all_filters(self) -> None:
        self._proxy.clear_all_filters()
        for fw in self._filter_widgets:
            fw.clear_filter()
        self._update_filter_summary()
        self._update_empty_state()

    def _update_empty_state(self) -> None:
        visible_rows = self._proxy.rowCount()
        self._empty_label.setVisible(visible_rows == 0)

    def get_active_filters_dict(self) -> dict[str, list[str]]:
        """Return active filters as {column_name: [values]} for printing."""
        active = self._proxy.get_active_filters()
        result = {}
        for col, values in active.items():
            col_name = COLUMNS[col] if col < len(COLUMNS) else f"Col {col}"
            for fw in self._filter_widgets:
                if fw._col == col:
                    col_name = fw.column_name
                    break
            result[col_name] = values
        return result

    def get_visible_loans(self) -> list[LoanDTO]:
        """Return all currently visible loans in proxy sort order."""
        loans = []
        for row in range(self._proxy.rowCount()):
            source_index = self._proxy.mapToSource(self._proxy.index(row, 0))
            loan = self._model.loan_at(source_index.row())
            if loan is not None:
                loans.append(loan)
        return loans

    def _on_print(self) -> None:
        from loan_manager.presentation.widgets.report_printer import LoanReportPrinter

        loans = self.get_visible_loans()
        filters = self.get_active_filters_dict()
        printer = LoanReportPrinter()
        printer.print_loans(loans, filters, self)

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
