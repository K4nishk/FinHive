"""Pending Approval Tab — R5 implementation.

Displays all pending interest reports and allows approve/decline workflow.

Approve:
    - Batch-extends matching loan records in loans.csv (new giving_date/due_date).
    - Marks report status as Approved.
    - Emits data_changed so View Tab and Entry Tab refresh.
    - Uses approval_recovery.tmp for crash safety (PD-34/R5).

Decline:
    - Deletes report line items from pending_report_records.csv.
    - Marks report status as Declined (header retained per PD-16).

Inline editing (PD-25/R5):
    - interest_rate, commission_rate, extension_period, extension_period_unit,
      tds_flag are editable per row.
    - Editing any of these auto-recalculates interest_amount, commission_amount,
      tds_amount and updates the post-extension date previews.
    - Edits are saved immediately to pending_report_records.csv.
    - Report latest_update_dt is refreshed in pending_reports.csv on each edit.

Shared ref-id warning (R5):
    - Warn when approving a report whose ref_ids appear in another Pending report.

Deleted-loan warning (R5):
    - Warn when a record's ref_id no longer exists in loans.csv.
"""
import logging
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data.csv_manager import batch_extend_loans, mark_paidoff, read_loans
from data.report_manager import (
    delete_report_records,
    get_active_reference_ids_in_queue,
    read_pending_reports,
    read_report_records,
    update_report_records,
    update_report_status,
)
from models.report import PendingReport, ReportRecord

logger = logging.getLogger(__name__)

# Recovery file lives next to loans.csv in the data directory
_APPROVAL_RECOVERY = Path(__file__).parent.parent / "data" / "approval_recovery.tmp"

# ---------------------------------------------------------------------------
# Report list table column indices
# ---------------------------------------------------------------------------
RPT_COL_REPORT_ID = 0
RPT_COL_MODE = 1
RPT_COL_CREATED = 2
RPT_COL_UPDATED = 3
RPT_COL_STATUS = 4

RPT_HEADERS = ["Report ID", "Mode", "Created", "Last Updated", "Status"]

# ---------------------------------------------------------------------------
# Record detail table column indices
# ---------------------------------------------------------------------------
REC_COL_REF_ID = 0
REC_COL_BORROWER = 1
REC_COL_AMOUNT = 2
REC_COL_DEPOSITOR = 3
REC_COL_GIVING_DATE = 4    # pre-extension (readonly)
REC_COL_DUE_DATE = 5       # pre-extension (readonly)
REC_COL_POST_GIVING = 6    # preview: new_giving_date (readonly, auto-updated)
REC_COL_POST_DUE = 7       # preview: new_due_date (readonly, auto-updated)
REC_COL_INT_RATE = 8       # editable
REC_COL_COMM_RATE = 9      # editable
REC_COL_EXT_PERIOD = 10    # editable
REC_COL_EXT_UNIT = 11      # editable
REC_COL_TDS_FLAG = 12      # editable
REC_COL_INTEREST = 13      # auto-computed (readonly)
REC_COL_COMMISSION = 14    # auto-computed (readonly)
REC_COL_TDS_AMOUNT = 15    # auto-computed (readonly)

REC_HEADERS = [
    "Ref ID", "Borrower", "Amount", "Depositor",
    "Giving Date", "Due Date",
    "Post Giving Date", "Post Due Date",
    "Int Rate %", "Comm Rate %", "Ext Period", "Ext Unit", "TDS",
    "Interest", "Commission", "TDS Amount",
]

REC_READONLY_COLS = {
    REC_COL_REF_ID, REC_COL_BORROWER, REC_COL_AMOUNT, REC_COL_DEPOSITOR,
    REC_COL_GIVING_DATE, REC_COL_DUE_DATE,
    REC_COL_POST_GIVING, REC_COL_POST_DUE,
    REC_COL_INTEREST, REC_COL_COMMISSION, REC_COL_TDS_AMOUNT,
}

REC_EDITABLE_COLS = {
    REC_COL_INT_RATE, REC_COL_COMM_RATE, REC_COL_EXT_PERIOD,
    REC_COL_EXT_UNIT, REC_COL_TDS_FLAG,
}


class PendingApprovalTab(QWidget):
    """Pending Approval Tab — R5."""

    data_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._reports: List[PendingReport] = []
        self._selected_report_id: Optional[str] = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        # --- Top panel: reports list ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        top_header = QHBoxLayout()
        top_header.addWidget(QLabel("Pending Reports"))
        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.clicked.connect(self.load_reports)
        top_header.addStretch()
        top_header.addWidget(self._btn_refresh)
        top_layout.addLayout(top_header)

        self._report_table = QTableWidget(0, len(RPT_HEADERS))
        self._report_table.setHorizontalHeaderLabels(RPT_HEADERS)
        self._report_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._report_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self._report_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._report_table.setAlternatingRowColors(True)
        self._report_table.selectionModel().selectionChanged.connect(
            self._on_report_selection_changed
        )
        top_layout.addWidget(self._report_table)
        splitter.addWidget(top_widget)

        # --- Bottom panel: record detail + action buttons ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)

        detail_header = QHBoxLayout()
        self._lbl_selected = QLabel("Select a report above to view its records.")
        detail_header.addWidget(self._lbl_selected)
        detail_header.addStretch()

        self._btn_approve = QPushButton("Approve")
        self._btn_approve.setEnabled(False)
        self._btn_approve.clicked.connect(self._on_approve)
        detail_header.addWidget(self._btn_approve)

        self._btn_decline = QPushButton("Decline")
        self._btn_decline.setEnabled(False)
        self._btn_decline.clicked.connect(self._on_decline)
        detail_header.addWidget(self._btn_decline)

        bottom_layout.addLayout(detail_header)

        # BC-301: Paidoff warning label — hidden by default, shown for mode="Paidoff" reports
        self._paidoff_warning = QLabel(
            "This report was generated for a Paidoff loan. "
            "The loan has been moved to history. No extension was applied."
        )
        self._paidoff_warning.setWordWrap(True)
        self._paidoff_warning.setStyleSheet(
            "background-color: #ca6702; color: white; padding: 6px; font-weight: bold;"
        )
        self._paidoff_warning.setVisible(False)
        bottom_layout.addWidget(self._paidoff_warning)

        self._rec_table = QTableWidget(0, len(REC_HEADERS))
        self._rec_table.setHorizontalHeaderLabels(REC_HEADERS)
        self._rec_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._rec_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._rec_table.setAlternatingRowColors(True)
        self._rec_table.itemChanged.connect(self._on_rec_item_changed)
        bottom_layout.addWidget(self._rec_table)

        splitter.addWidget(bottom_widget)
        splitter.setSizes([200, 400])

    # ------------------------------------------------------------------
    # Reports list
    # ------------------------------------------------------------------

    def load_reports(self) -> None:
        """Reload pending reports from storage. Called by external signal."""
        try:
            self._reports = read_pending_reports()
        except Exception as exc:
            logger.error("Failed to load pending reports: %s", exc)
            self._reports = []
        self._populate_report_table(self._reports)

    def _populate_report_table(self, reports: List[PendingReport]) -> None:
        self._report_table.blockSignals(True)
        try:
            self._report_table.setRowCount(0)
            for row_idx, report in enumerate(reports):
                self._report_table.insertRow(row_idx)

                def _item(text: str) -> QTableWidgetItem:
                    return QTableWidgetItem(text)

                self._report_table.setItem(
                    row_idx, RPT_COL_REPORT_ID, _item(report.report_id)
                )
                self._report_table.setItem(
                    row_idx, RPT_COL_MODE, _item(report.mode)
                )
                self._report_table.setItem(
                    row_idx, RPT_COL_CREATED,
                    _item(report.report_creation_date.isoformat())
                )
                self._report_table.setItem(
                    row_idx, RPT_COL_UPDATED,
                    _item(report.report_latest_update_dt.isoformat(timespec="seconds"))
                )
                self._report_table.setItem(
                    row_idx, RPT_COL_STATUS, _item(report.status)
                )
        finally:
            self._report_table.blockSignals(False)

        # Clear detail panel if no reports
        if not reports:
            self._selected_report_id = None
            self._clear_record_table()
            self._btn_approve.setEnabled(False)
            self._btn_decline.setEnabled(False)
            self._lbl_selected.setText("No pending reports.")

    def _on_report_selection_changed(self) -> None:
        selected_rows = self._report_table.selectionModel().selectedRows()
        if not selected_rows:
            self._selected_report_id = None
            self._clear_record_table()
            self._btn_approve.setEnabled(False)
            self._btn_decline.setEnabled(False)
            self._lbl_selected.setText("Select a report above to view its records.")
            self._paidoff_warning.setVisible(False)
            return

        row_idx = selected_rows[0].row()
        report_id_item = self._report_table.item(row_idx, RPT_COL_REPORT_ID)
        if report_id_item is None:
            return

        self._selected_report_id = report_id_item.text().strip()
        self._lbl_selected.setText(f"Report: {self._selected_report_id}")
        self._btn_approve.setEnabled(True)
        self._btn_decline.setEnabled(True)

        try:
            records = read_report_records(self._selected_report_id)
        except Exception as exc:
            logger.error(
                "Failed to load records for %s: %s", self._selected_report_id, exc
            )
            records = []

        self._populate_record_table(records)

        # BC-301: Show warning only for Paidoff-mode reports
        report = next(
            (r for r in self._reports if r.report_id == self._selected_report_id),
            None,
        )
        self._paidoff_warning.setVisible(
            report is not None and report.mode == "Paidoff"
        )

    # ------------------------------------------------------------------
    # Record detail table
    # ------------------------------------------------------------------

    def _clear_record_table(self) -> None:
        self._rec_table.blockSignals(True)
        self._rec_table.setRowCount(0)
        self._rec_table.blockSignals(False)

    def _populate_record_table(self, records: List[ReportRecord]) -> None:
        self._rec_table.blockSignals(True)
        try:
            self._rec_table.setRowCount(0)
            for row_idx, rec in enumerate(records):
                self._rec_table.insertRow(row_idx)

                def _ro_item(text: str) -> QTableWidgetItem:
                    item = QTableWidgetItem(text)
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    return item

                def _rw_item(text: str) -> QTableWidgetItem:
                    return QTableWidgetItem(text)

                self._rec_table.setItem(
                    row_idx, REC_COL_REF_ID, _ro_item(rec.reference_id)
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_BORROWER, _ro_item(rec.borrower_name)
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_AMOUNT, _ro_item(str(rec.amount))
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_DEPOSITOR,
                    _ro_item(rec.depositor_name or "Unknown")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_GIVING_DATE,
                    _ro_item(rec.giving_date.isoformat())
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_DUE_DATE,
                    _ro_item(rec.due_date.isoformat() if rec.due_date else "")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_POST_GIVING,
                    _ro_item(rec.new_giving_date.isoformat() if rec.new_giving_date else "")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_POST_DUE,
                    _ro_item(rec.new_due_date.isoformat() if rec.new_due_date else "")
                )

                self._rec_table.setItem(
                    row_idx, REC_COL_INT_RATE,
                    _rw_item(f"{rec.interest_rate:.2f}")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_COMM_RATE,
                    _rw_item(f"{rec.commission_rate:.2f}")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_EXT_PERIOD,
                    _rw_item(str(rec.extension_period))
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_EXT_UNIT,
                    _rw_item(rec.extension_period_unit)
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_TDS_FLAG,
                    _rw_item("true" if rec.tds_flag else "false")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_INTEREST,
                    _ro_item(f"{rec.interest_amount:.2f}")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_COMMISSION,
                    _ro_item(f"{rec.commission_amount:.2f}")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_TDS_AMOUNT,
                    _ro_item(f"{rec.tds_amount:.2f}")
                )
        finally:
            self._rec_table.blockSignals(False)

    def _on_rec_item_changed(self, item: QTableWidgetItem) -> None:
        """Handle inline edits: recalculate results and persist to CSV."""
        if item.column() not in REC_EDITABLE_COLS:
            return
        row_idx = item.row()
        self._recalc_row(row_idx)
        self._save_current_records()
        # Update report_latest_update_dt (status stays Pending)
        if self._selected_report_id:
            try:
                update_report_status(
                    self._selected_report_id, "Pending", datetime.now()
                )
            except Exception as exc:
                logger.warning(
                    "Failed to update report timestamp for %s: %s",
                    self._selected_report_id, exc
                )

    def _recalc_row(self, row_idx: int) -> None:
        """Recalculate interest/commission/tds and post-extension dates for a row."""
        def _cell(col: int) -> str:
            item = self._rec_table.item(row_idx, col)
            return item.text().strip() if item else ""

        try:
            amount = int(_cell(REC_COL_AMOUNT) or "0")
            int_rate = float(_cell(REC_COL_INT_RATE) or "0")
            comm_rate = float(_cell(REC_COL_COMM_RATE) or "0")
            ext_period = int(_cell(REC_COL_EXT_PERIOD) or "0")
            ext_unit = _cell(REC_COL_EXT_UNIT) or "months"
            tds_raw = _cell(REC_COL_TDS_FLAG).lower()
            tds_flag = tds_raw in ("true", "1", "yes")

            divisor = 12 if ext_unit == "months" else 365
            interest = (amount * int_rate * ext_period) / (divisor * 100)
            commission = (amount * comm_rate * ext_period) / (divisor * 100)
            tds = 0.1 * interest if tds_flag else 0.0

            # Recompute post-extension dates
            due_date_str = _cell(REC_COL_DUE_DATE)
            if due_date_str:
                due_date_val = date.fromisoformat(due_date_str)
                new_giving = due_date_val
                if ext_unit == "months":
                    from dateutil.relativedelta import relativedelta
                    new_due = due_date_val + relativedelta(months=ext_period)
                else:
                    from datetime import timedelta
                    new_due = due_date_val + timedelta(days=ext_period)
            else:
                new_giving = None
                new_due = None

            self._rec_table.blockSignals(True)
            try:
                def _ro_item(text: str) -> QTableWidgetItem:
                    it = QTableWidgetItem(text)
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    return it

                self._rec_table.setItem(
                    row_idx, REC_COL_INTEREST, _ro_item(f"{interest:.2f}")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_COMMISSION, _ro_item(f"{commission:.2f}")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_TDS_AMOUNT, _ro_item(f"{tds:.2f}")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_POST_GIVING,
                    _ro_item(new_giving.isoformat() if new_giving else "")
                )
                self._rec_table.setItem(
                    row_idx, REC_COL_POST_DUE,
                    _ro_item(new_due.isoformat() if new_due else "")
                )
            finally:
                self._rec_table.blockSignals(False)

        except (ValueError, TypeError) as exc:
            logger.warning("Recalc failed for row %d: %s", row_idx, exc)

    def _get_record_from_row(
        self, row_idx: int, report_id: str
    ) -> Optional[ReportRecord]:
        """Build a ReportRecord from the current state of a table row."""
        def _cell(col: int) -> str:
            item = self._rec_table.item(row_idx, col)
            return item.text().strip() if item else ""

        try:
            due_date_str = _cell(REC_COL_DUE_DATE)
            post_giving_str = _cell(REC_COL_POST_GIVING)
            post_due_str = _cell(REC_COL_POST_DUE)
            tds_raw = _cell(REC_COL_TDS_FLAG).lower()

            return ReportRecord(
                report_id=report_id,
                reference_id=_cell(REC_COL_REF_ID),
                borrower_name=_cell(REC_COL_BORROWER),
                amount=int(_cell(REC_COL_AMOUNT) or "0"),
                depositor_name=(_cell(REC_COL_DEPOSITOR) or None)
                if _cell(REC_COL_DEPOSITOR) != "Unknown"
                else None,
                giving_date=date.fromisoformat(_cell(REC_COL_GIVING_DATE))
                if _cell(REC_COL_GIVING_DATE)
                else date.today(),
                due_date=date.fromisoformat(due_date_str) if due_date_str else None,
                interest_rate=float(_cell(REC_COL_INT_RATE) or "0"),
                commission_rate=float(_cell(REC_COL_COMM_RATE) or "0"),
                extension_period=int(_cell(REC_COL_EXT_PERIOD) or "0"),
                extension_period_unit=_cell(REC_COL_EXT_UNIT) or "months",
                tds_flag=tds_raw in ("true", "1", "yes"),
                new_giving_date=date.fromisoformat(post_giving_str)
                if post_giving_str
                else None,
                new_due_date=date.fromisoformat(post_due_str)
                if post_due_str
                else None,
                interest_amount=float(_cell(REC_COL_INTEREST) or "0"),
                commission_amount=float(_cell(REC_COL_COMMISSION) or "0"),
                tds_amount=float(_cell(REC_COL_TDS_AMOUNT) or "0"),
            )
        except Exception as exc:
            logger.warning(
                "Failed to build record from row %d: %s", row_idx, exc
            )
            return None

    def _save_current_records(self) -> None:
        """Persist current record table state to pending_report_records.csv."""
        if not self._selected_report_id:
            return
        records: List[ReportRecord] = []
        for row_idx in range(self._rec_table.rowCount()):
            rec = self._get_record_from_row(row_idx, self._selected_report_id)
            if rec is not None:
                records.append(rec)
        try:
            update_report_records(self._selected_report_id, records)
        except Exception as exc:
            logger.error(
                "Failed to save records for %s: %s", self._selected_report_id, exc
            )

    # ------------------------------------------------------------------
    # Approve
    # ------------------------------------------------------------------

    def _on_approve(self) -> None:
        if not self._selected_report_id:
            return

        report_id = self._selected_report_id

        # Build current records from table
        records: List[ReportRecord] = []
        for row_idx in range(self._rec_table.rowCount()):
            rec = self._get_record_from_row(row_idx, report_id)
            if rec is not None:
                records.append(rec)

        if not records:
            QMessageBox.warning(self, "No Records", "This report has no records.")
            return

        ref_ids_in_report = {rec.reference_id for rec in records}

        # --- Check shared ref-ids in OTHER pending reports (R5) ---
        try:
            all_active_ids = get_active_reference_ids_in_queue()
            # all_active_ids includes records from THIS report too; subtract them
            shared_ids = all_active_ids - ref_ids_in_report
            # Now check if any of this report's IDs appear in records of OTHER reports
            # get_active_reference_ids_in_queue returns IDs across all pending reports,
            # so overlap = (all_active minus this report's own IDs) ∩ this report's IDs
            # Re-check: if an ID in ref_ids_in_report also appears in all_active_ids
            # (from OTHER reports), warn.
            overlap = ref_ids_in_report & (all_active_ids - ref_ids_in_report)
            # Correct approach: IDs in this report that ALSO appear in the full active set
            # means they are in other reports (since we haven't removed this report yet)
            # Actually get_active_reference_ids_in_queue includes this report. We need
            # to detect if any ID appears in ANOTHER pending report.
            # Simpler: overlap = ref_ids_in_report ∩ all_active_ids - but that always
            # equals ref_ids_in_report. We need to check IDs from OTHER reports only.
            # get_active_reference_ids_in_queue returns IDs from ALL pending reports
            # including this one. So other_ids = all_active_ids - ref_ids_in_report,
            # then overlap = ref_ids_in_report ∩ other_ids.
            other_active_ids = all_active_ids - ref_ids_in_report
            overlap = ref_ids_in_report & other_active_ids
        except Exception as exc:
            logger.warning("Could not check for shared ref-ids: %s", exc)
            overlap = set()

        if overlap:
            reply = QMessageBox.warning(
                self,
                "Shared Loan Records",
                "This report shares loan records with another pending report. "
                "Approving may overwrite previous updates.\n\n"
                f"Shared ref IDs: {', '.join(sorted(overlap))}",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Ok:
                return

        # --- Check for deleted loans (R5) ---
        try:
            existing_loans = read_loans()
            existing_ref_ids = {loan.reference_id for loan in existing_loans}
            deleted_ids = ref_ids_in_report - existing_ref_ids
        except Exception as exc:
            logger.warning("Could not check for deleted loans: %s", exc)
            deleted_ids = set()

        if deleted_ids:
            reply = QMessageBox.warning(
                self,
                "Deleted Loan Records",
                "Records in this report have been deleted.\n\n"
                f"Deleted ref IDs: {', '.join(sorted(deleted_ids))}\n\n"
                "Approving will skip the deleted records and update only the remaining ones.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if reply != QMessageBox.StandardButton.Ok:
                return

        # --- Determine report mode (Paidoff vs regular extension) ---
        report = next(
            (r for r in self._reports if r.report_id == report_id), None
        )
        is_paidoff_report = report is not None and report.mode == "Paidoff"

        # --- Write approval_recovery.tmp (crash safety PD-34) ---
        try:
            _APPROVAL_RECOVERY.parent.mkdir(parents=True, exist_ok=True)
            _APPROVAL_RECOVERY.write_text(report_id, encoding="utf-8")
        except Exception as exc:
            logger.error("Failed to write approval_recovery.tmp: %s", exc)

        if is_paidoff_report:
            # R3: Paidoff approval — call mark_paidoff() for each record
            # paidoff_date is stored in new_due_date field of the ReportRecord
            paidoff_errors = []
            for rec in records:
                if rec.reference_id in deleted_ids:
                    continue
                paidoff_date = rec.new_due_date if rec.new_due_date else date.today()
                try:
                    mark_paidoff(rec.reference_id, paidoff_date)
                    logger.info(
                        "Paidoff approval: archived loan %s (paidoff_date=%s)",
                        rec.reference_id, paidoff_date,
                    )
                except ValueError as exc:
                    # Loan may have already been removed (deleted between report gen and approval)
                    logger.warning(
                        "Paidoff archive skipped for %s (not in loans.csv): %s",
                        rec.reference_id, exc,
                    )
                except Exception as exc:
                    logger.error(
                        "Paidoff archive failed for %s: %s", rec.reference_id, exc
                    )
                    paidoff_errors.append(str(exc))

            if paidoff_errors:
                QMessageBox.critical(
                    self, "Paidoff Approval Error",
                    f"Some records could not be archived:\n" + "\n".join(paidoff_errors)
                )
                return
        else:
            # --- Batch extend loans (regular reports) ---
            try:
                extensions = []
                for rec in records:
                    if rec.reference_id in deleted_ids:
                        continue
                    if rec.new_giving_date is None and rec.new_due_date is None:
                        continue
                    extensions.append(
                        {
                            "reference_id": rec.reference_id,
                            "new_giving_date": rec.new_giving_date,
                            "new_due_date": rec.new_due_date,
                        }
                    )
                if extensions:
                    batch_extend_loans(extensions)
                    logger.info(
                        "Approval batch-extended %d loans for report %s",
                        len(extensions), report_id
                    )
            except Exception as exc:
                logger.error(
                    "Batch extend failed for report %s: %s", report_id, exc
                )
                QMessageBox.critical(
                    self, "Approval Failed",
                    f"Failed to update loan records:\n{exc}"
                )
                return

        # --- Mark report Approved ---
        try:
            update_report_status(report_id, "Approved", datetime.now())
        except Exception as exc:
            logger.error("Failed to update report status: %s", exc)

        # --- Delete recovery file ---
        try:
            if _APPROVAL_RECOVERY.exists():
                _APPROVAL_RECOVERY.unlink()
        except Exception as exc:
            logger.warning("Could not delete approval_recovery.tmp: %s", exc)

        logger.info("Report approved: %s", report_id)
        self._selected_report_id = None
        self.load_reports()
        self.data_changed.emit()
        QMessageBox.information(
            self, "Approved",
            f"Report {report_id} approved. Loan records updated."
        )

    # ------------------------------------------------------------------
    # Decline
    # ------------------------------------------------------------------

    def _on_decline(self) -> None:
        if not self._selected_report_id:
            return

        report_id = self._selected_report_id
        reply = QMessageBox.question(
            self,
            "Decline Report",
            f"Decline report {report_id}?\n\nThe calculated values will be discarded.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_report_records(report_id)
            update_report_status(report_id, "Declined", datetime.now())
            logger.info("Report declined: %s", report_id)
        except Exception as exc:
            logger.error("Failed to decline report %s: %s", report_id, exc)
            QMessageBox.critical(
                self, "Error", f"Failed to decline report:\n{exc}"
            )
            return

        self._selected_report_id = None
        self.load_reports()
        QMessageBox.information(
            self, "Declined", f"Report {report_id} has been declined."
        )

    # ------------------------------------------------------------------
    # Refresh on tab activation
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        """Reload reports when tab becomes visible."""
        super().showEvent(event)
        self.load_reports()
