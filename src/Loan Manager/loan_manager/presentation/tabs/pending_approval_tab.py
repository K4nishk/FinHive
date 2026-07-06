from decimal import Decimal

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QMessageBox, QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtPrintSupport import QPrinter, QPrintDialog

from loan_manager.application.dtos.report_dto import (
    ReportDTO, ReportRecordUpdateDTO,
)
from loan_manager.application.use_cases.reports.get_reports import (
    GetPendingReports, UpdateReportRecord,
)
from loan_manager.application.use_cases.reports.approve_report import ApproveReport
from loan_manager.application.use_cases.reports.decline_report import DeclineReport
from loan_manager.domain.value_objects.status import CalculationMode, ExtensionPeriodUnit


REPORT_COLUMNS = ["Report ID", "Mode", "Records", "Created", "Updated"]
RECORD_COLUMNS = [
    "Ref ID", "B Name", "D Name", "Amount", "G Date", "D Date",
    "Rate %", "Comm %", "Period", "Unit", "TDS",
    "Interest", "Commission", "TDS Amt", "CHQ Amt",
]


class PendingApprovalTab(QWidget):
    def __init__(self, container, parent=None):
        super().__init__(parent)
        self._container = container
        self._main_window = parent
        self._reports: list[ReportDTO] = []
        self._selected_report: ReportDTO | None = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # Report list
        report_widget = QWidget()
        report_layout = QVBoxLayout(report_widget)
        report_layout.setContentsMargins(0, 0, 0, 0)
        report_layout.addWidget(QLabel("Pending Reports"))
        self._report_table = QTableWidget(0, len(REPORT_COLUMNS))
        self._report_table.setHorizontalHeaderLabels(REPORT_COLUMNS)
        self._report_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._report_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._report_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._report_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._report_table.currentCellChanged.connect(self._on_report_selected)
        report_layout.addWidget(self._report_table)
        splitter.addWidget(report_widget)

        # Record detail
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.addWidget(QLabel("Report Records"))
        self._record_table = QTableWidget(0, len(RECORD_COLUMNS))
        self._record_table.setHorizontalHeaderLabels(RECORD_COLUMNS)
        self._record_table.setAlternatingRowColors(True)
        self._record_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._record_table.cellChanged.connect(self._on_record_edited)
        detail_layout.addWidget(self._record_table)
        splitter.addWidget(detail_widget)

        layout.addWidget(splitter)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._print_btn = QPushButton("Print/PDF")
        self._print_btn.setAccessibleName("Print approval report")
        self._print_btn.clicked.connect(self._on_print)
        self._print_btn.setEnabled(False)
        btn_layout.addWidget(self._print_btn)

        self._decline_btn = QPushButton("Decline")
        self._decline_btn.setAccessibleName("Decline selected report")
        self._decline_btn.clicked.connect(self._on_decline)
        self._decline_btn.setEnabled(False)
        btn_layout.addWidget(self._decline_btn)

        self._approve_btn = QPushButton("Approve")
        self._approve_btn.setAccessibleName("Approve selected report")
        self._approve_btn.clicked.connect(self._on_approve)
        self._approve_btn.setEnabled(False)
        btn_layout.addWidget(self._approve_btn)

        layout.addLayout(btn_layout)

    def refresh(self) -> None:
        try:
            get_reports = GetPendingReports(self._container.get_uow)
            self._reports = get_reports.execute()
            self._populate_report_table()
            self._selected_report = None
            self._record_table.setRowCount(0)
            self._print_btn.setEnabled(False)
            self._decline_btn.setEnabled(False)
            self._approve_btn.setEnabled(False)
        except Exception as e:
            if self._main_window:
                self._main_window.show_status(f"Error loading reports: {e}")

    def _populate_report_table(self) -> None:
        self._report_table.setRowCount(len(self._reports))
        for row, report in enumerate(self._reports):
            self._report_table.setItem(row, 0, QTableWidgetItem(report.report_id))
            self._report_table.setItem(row, 1, QTableWidgetItem(report.report_mode.value))
            self._report_table.setItem(row, 2, QTableWidgetItem(str(len(report.records))))
            self._report_table.setItem(
                row, 3, QTableWidgetItem(report.created_at.strftime("%Y-%m-%d %H:%M"))
            )
            self._report_table.setItem(
                row, 4, QTableWidgetItem(report.updated_at.strftime("%Y-%m-%d %H:%M"))
            )

    def _on_report_selected(self, row: int, col: int, prev_row: int, prev_col: int) -> None:
        if row < 0 or row >= len(self._reports):
            return
        self._selected_report = self._reports[row]
        self._populate_record_table()
        self._print_btn.setEnabled(True)
        self._decline_btn.setEnabled(True)
        self._approve_btn.setEnabled(True)

    def _populate_record_table(self) -> None:
        if self._selected_report is None:
            return
        records = self._selected_report.records
        self._record_table.blockSignals(True)
        self._record_table.setRowCount(len(records))

        for row, rec in enumerate(records):
            self._set_readonly(row, 0, rec.reference_id)
            self._set_readonly(row, 1, rec.borrower_name)
            self._set_readonly(row, 2, rec.depositor_name)
            self._set_readonly(row, 3, str(rec.amount))
            self._set_readonly(row, 4, str(rec.giving_date))
            self._set_readonly(row, 5, str(rec.due_date) if rec.due_date else "N/A")

            # Editable fields
            self._record_table.setItem(row, 6, QTableWidgetItem(str(rec.interest_rate)))
            self._record_table.setItem(row, 7, QTableWidgetItem(str(rec.commission_rate)))
            self._record_table.setItem(row, 8, QTableWidgetItem(str(rec.extension_period)))
            self._record_table.setItem(
                row, 9, QTableWidgetItem(rec.extension_period_unit.value)
            )
            self._record_table.setItem(
                row, 10, QTableWidgetItem("Yes" if rec.tds_flag else "No")
            )

            self._set_readonly(row, 11, str(rec.interest_amount or 0))
            self._set_readonly(row, 12, str(rec.commission_amount or 0))
            self._set_readonly(row, 13, str(rec.tds_amount or 0))
            self._set_readonly(row, 14, str(rec.chq_amount or 0))

        self._record_table.blockSignals(False)

    def _set_readonly(self, row: int, col: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._record_table.setItem(row, col, item)

    def _on_record_edited(self, row: int, col: int) -> None:
        if col not in (6, 7, 8, 9, 10):
            return
        if self._selected_report is None:
            return
        if row >= len(self._selected_report.records):
            return

        rec = self._selected_report.records[row]
        if rec.id is None:
            return

        try:
            update = {}
            if col == 6:
                update["interest_rate"] = Decimal(self._record_table.item(row, 6).text())
            elif col == 7:
                update["commission_rate"] = Decimal(self._record_table.item(row, 7).text())
            elif col == 8:
                update["extension_period"] = int(self._record_table.item(row, 8).text())
            elif col == 9:
                update["extension_period_unit"] = ExtensionPeriodUnit(
                    self._record_table.item(row, 9).text()
                )
            elif col == 10:
                text = self._record_table.item(row, 10).text().lower()
                update["tds_flag"] = text in ("yes", "true", "1")

            dto = ReportRecordUpdateDTO(**update)
            update_uc = UpdateReportRecord(self._container.get_uow)
            updated_rec = update_uc.execute(
                self._selected_report.report_id, rec.id, dto
            )

            # Update display
            self._record_table.blockSignals(True)
            self._record_table.item(row, 11).setText(str(updated_rec.interest_amount or 0))
            self._record_table.item(row, 12).setText(str(updated_rec.commission_amount or 0))
            self._record_table.item(row, 13).setText(str(updated_rec.tds_amount or 0))
            self._record_table.item(row, 14).setText(str(updated_rec.chq_amount or 0))
            self._record_table.blockSignals(False)

            if self._main_window:
                self._main_window.show_status("Record recalculated.")

        except Exception as e:
            if self._main_window:
                self._main_window.show_status(f"Update failed: {e}")

    def _on_approve(self) -> None:
        if self._selected_report is None:
            return

        report_id = self._selected_report.report_id
        is_paidoff = self._selected_report.report_mode == CalculationMode.PAIDOFF

        try:
            approve_uc = ApproveReport(
                self._container.get_uow,
                self._container.recovery_service,
                self._container.backup_service,
                self._container.event_bus,
            )

            result = approve_uc.execute(report_id, force=False)

            if result.requires_confirmation:
                messages = []
                if result.duplicate_ref_ids:
                    messages.append(
                        "This report shares loan records with another pending report. "
                        "Approving may overwrite previous updates."
                    )
                if result.deleted_ref_ids:
                    messages.append(
                        f"Records in this report have been deleted: "
                        f"{', '.join(result.deleted_ref_ids)}"
                    )
                if is_paidoff:
                    messages.append(
                        "This report was generated for a Paidoff loan. "
                        "The loan will be moved to history. No extension will be applied."
                    )

                msg = "\n\n".join(messages) + "\n\nProceed anyway?"
                reply = QMessageBox.warning(
                    self,
                    "Confirmation Required",
                    msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    result = approve_uc.execute(report_id, force=True)
                else:
                    return
            else:
                if is_paidoff:
                    reply = QMessageBox.information(
                        self,
                        "Paidoff Report",
                        "This report was generated for a Paidoff loan. "
                        "The loan will be moved to history. No extension will be applied.\n\n"
                        "Report approved successfully.",
                        QMessageBox.StandardButton.Ok,
                    )

            if result.success:
                if self._main_window:
                    self._main_window.show_status(
                        f"Report {report_id} approved."
                    )
                    if hasattr(self._main_window, '_view_tab'):
                        self._main_window._view_tab.refresh()
                self.refresh()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Approval failed: {e}")

    def _on_decline(self) -> None:
        if self._selected_report is None:
            return
        report_id = self._selected_report.report_id

        reply = QMessageBox.question(
            self,
            "Confirm Decline",
            f"Are you sure you want to decline report {report_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                decline_uc = DeclineReport(
                    self._container.get_uow,
                    self._container.event_bus,
                )
                decline_uc.execute(report_id)
                if self._main_window:
                    self._main_window.show_status(f"Report {report_id} declined.")
                self.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Decline failed: {e}")

    def _on_print(self) -> None:
        if self._selected_report is None:
            return

        from loan_manager.presentation.widgets.report_printer import ApprovalReportPrinter

        printer = ApprovalReportPrinter()
        printer.print_report(self._selected_report, self)
