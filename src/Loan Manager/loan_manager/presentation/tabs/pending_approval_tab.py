"""Approvals tab (KCH-245): agent- and form-authored batches, side by side.

Presentation only -- every mutation goes through a use case constructed with
`self._container`'s own factories/services, exactly like the rest of this
tab's siblings. `ReportRecordModel`'s `on_edit` callback is the one place a
model-driven edit reaches a use case, and even that call lives here in the
tab (`_on_edit_record`), never inside the model itself.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from loan_manager.application.dtos.report_dto import ReportDTO, ReportRecordUpdateDTO
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.application.use_cases.reports.approve_report import ApproveReport
from loan_manager.application.use_cases.reports.decline_report import DeclineReport
from loan_manager.application.use_cases.reports.get_recent_approved_reports import (
    GetRecentlyApprovedReports,
)
from loan_manager.application.use_cases.reports.get_reports import (
    GetPendingReports,
    UpdateReportRecord,
)
from loan_manager.application.use_cases.reports.undo_approved_report import UndoApprovedReport
from loan_manager.domain.value_objects.status import CalculationMode
from loan_manager.presentation.errors import surfacing_storage_errors
from loan_manager.presentation.view_models.approval_messages import (
    approve_outcome,
    undo_refusal_text,
)
from loan_manager.presentation.widgets.report_table_models import (
    ReportListModel,
    ReportRecordModel,
)

RECENT_APPROVED_LIMIT = 20


class PendingApprovalTab(QWidget):
    def __init__(self, container, theme_manager, parent=None):
        super().__init__(parent)
        self._container = container
        self._theme = theme_manager
        self._main_window = parent
        self._selected_report: ReportDTO | None = None
        self._selected_approved: ReportDTO | None = None
        self._setup_ui()
        self.refresh()

    # -- UI construction ---------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        splitter.addWidget(self._build_pending_section())
        splitter.addWidget(self._build_detail_section())
        splitter.addWidget(self._build_recently_approved_section())

        layout.addWidget(splitter)
        layout.addLayout(self._build_button_row())

    def _build_pending_section(self) -> QWidget:
        widget = QWidget()
        section_layout = QVBoxLayout(widget)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.addWidget(QLabel("Pending Reports"))

        self._report_model = ReportListModel(self._theme)
        self._report_proxy = QSortFilterProxyModel()
        self._report_proxy.setSourceModel(self._report_model)

        self._report_table = QTableView()
        self._report_table.setModel(self._report_proxy)
        self._report_table.setAccessibleName("Pending reports")
        self._report_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._report_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._report_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._report_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._report_table.selectionModel().currentRowChanged.connect(
            self._on_report_selected
        )
        section_layout.addWidget(self._report_table)
        return widget

    def _build_detail_section(self) -> QWidget:
        widget = QWidget()
        section_layout = QVBoxLayout(widget)
        section_layout.setContentsMargins(0, 0, 0, 0)

        strip = QHBoxLayout()
        self._actor_badge = QLabel("")
        self._actor_badge.setAccessibleName("Report author")
        strip.addWidget(self._actor_badge)

        # PlainText, never logged (ARB D-15/D-16, this tab's own contract):
        # the agent's own words can name a borrower or an amount, so this
        # label shows them verbatim to the user and nowhere near a logger.
        self._user_request_label = QLabel("")
        self._user_request_label.setTextFormat(Qt.TextFormat.PlainText)
        self._user_request_label.setWordWrap(True)
        self._user_request_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._user_request_label.setAccessibleName("Agent user request")
        strip.addWidget(self._user_request_label, 1)

        self._conflict_label = QLabel("")
        self._conflict_label.setAccessibleName("Conflict warning")
        self._conflict_label.setVisible(False)
        strip.addWidget(self._conflict_label)

        section_layout.addLayout(strip)

        section_layout.addWidget(QLabel("Report Records"))
        self._record_model = ReportRecordModel(self._theme, on_edit=self._on_edit_record)
        self._record_proxy = QSortFilterProxyModel()
        self._record_proxy.setSourceModel(self._record_model)

        self._record_table = QTableView()
        self._record_table.setModel(self._record_proxy)
        self._record_table.setAccessibleName("Report records")
        self._record_table.setAlternatingRowColors(True)
        self._record_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        section_layout.addWidget(self._record_table)
        return widget

    def _build_recently_approved_section(self) -> QWidget:
        widget = QWidget()
        section_layout = QVBoxLayout(widget)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.addWidget(QLabel("Recently Approved"))

        self._approved_model = ReportListModel(self._theme, time_header="Approved")
        self._approved_proxy = QSortFilterProxyModel()
        self._approved_proxy.setSourceModel(self._approved_model)

        self._approved_table = QTableView()
        self._approved_table.setModel(self._approved_proxy)
        self._approved_table.setAccessibleName("Recently approved reports")
        self._approved_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._approved_table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self._approved_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._approved_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._approved_table.selectionModel().currentRowChanged.connect(
            self._on_approved_selected
        )
        section_layout.addWidget(self._approved_table)

        undo_row = QHBoxLayout()
        undo_row.addStretch()
        self._undo_btn = QPushButton("Undo")
        self._undo_btn.setAccessibleName("Undo selected report")
        self._undo_btn.clicked.connect(self._on_undo)
        self._undo_btn.setEnabled(False)
        undo_row.addWidget(self._undo_btn)
        section_layout.addLayout(undo_row)
        return widget

    def _build_button_row(self) -> QHBoxLayout:
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

        return btn_layout

    # -- data loading --------------------------------------------------

    def refresh(self) -> None:
        pending: list[ReportDTO] = []
        with surfacing_storage_errors(self, "loading pending reports"):
            pending = GetPendingReports(self._container.get_uow).execute()
        self._report_model.load(pending)

        approved: list[ReportDTO] = []
        with surfacing_storage_errors(self, "loading recently approved reports"):
            approved = GetRecentlyApprovedReports(self._container.get_uow).execute(
                limit=RECENT_APPROVED_LIMIT
            )
        self._approved_model.load(approved)

        self._selected_report = None
        self._selected_approved = None
        self._record_model.load([], None)
        self._clear_detail_strip()
        self._print_btn.setEnabled(False)
        self._decline_btn.setEnabled(False)
        self._approve_btn.setEnabled(False)
        self._undo_btn.setEnabled(False)

    def _apply_badge_colour(self, label: QLabel, colour: dict) -> None:
        # KCH-245 review cycle 1, M1: the app-wide QSS (themes/*.qss) sets
        # `QLabel { color: ...; background-color: transparent; }` -- a
        # stylesheet always wins over QPalette (Qt's own precedence rule),
        # so setPalette()/setAutoFillBackground() here were a silent no-op:
        # only the bold survived, because that comes from QFont, not the
        # palette. setStyleSheet built from ThemeManager's own colours is
        # the established pattern (settings_tab.py:231's `_update_colour_button`).
        weight = "bold" if colour.get("bold", False) else "normal"
        label.setStyleSheet(
            f"background-color: {colour['background']}; color: {colour['text']};"
            f" font-weight: {weight}; padding: 2px 6px;"
        )

    def _clear_detail_strip(self) -> None:
        self._actor_badge.setText("")
        self._actor_badge.setStyleSheet("")
        self._user_request_label.setText("")
        self._conflict_label.setText("")
        self._conflict_label.setStyleSheet("")
        self._conflict_label.setVisible(False)

    def _populate_detail_strip(self, report: ReportDTO) -> None:
        self._actor_badge.setText(report.actor.value)
        self._apply_badge_colour(
            self._actor_badge, self._theme.get_badge_colour(report.actor.value)
        )

        self._user_request_label.setText(report.user_request or "")

        if report.conflict_ref_ids:
            self._conflict_label.setText(
                "Conflicts with: " + ", ".join(report.conflict_ref_ids)
            )
            self._apply_badge_colour(self._conflict_label, self._theme.get_badge_colour("CONFLICT"))
            self._conflict_label.setVisible(True)
        else:
            self._conflict_label.setText("")
            self._conflict_label.setVisible(False)

    # -- selection handlers ----------------------------------------------

    def _on_report_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        if not current.isValid():
            self._selected_report = None
            self._record_model.load([], None)
            self._clear_detail_strip()
            self._print_btn.setEnabled(False)
            self._decline_btn.setEnabled(False)
            self._approve_btn.setEnabled(False)
            return

        source_index = self._report_proxy.mapToSource(current)
        report = self._report_model.report_at(source_index.row())
        if report is None:
            return

        self._selected_report = report
        self._populate_detail_strip(report)

        # KCH-245 plan: GetAllLoans is only ever called when an UPDATE
        # report is the one selected -- every other mode's "Current"
        # columns are N/A and need no live loan lookup.
        current_loans = {}
        if report.report_mode == CalculationMode.UPDATE:
            loans = []
            with surfacing_storage_errors(self, "loading current loan values"):
                loans = GetAllLoans(self._container.get_uow).execute()
            current_loans = {loan.reference_id: loan for loan in loans}

        self._record_model.load(
            report.records, report.report_mode, report.conflict_ref_ids, current_loans
        )
        self._print_btn.setEnabled(True)
        self._decline_btn.setEnabled(True)
        self._approve_btn.setEnabled(True)

    def _on_approved_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
        if not current.isValid():
            self._selected_approved = None
            self._undo_btn.setEnabled(False)
            return
        source_index = self._approved_proxy.mapToSource(current)
        report = self._approved_model.report_at(source_index.row())
        self._selected_approved = report
        self._undo_btn.setEnabled(report is not None)

    # -- record editing ----------------------------------------------------

    def _on_edit_record(self, record_id: int, field: str, value):
        if self._selected_report is None:
            return None
        try:
            dto = ReportRecordUpdateDTO(**{field: value})
            update_uc = UpdateReportRecord(self._container.get_uow)
            updated = update_uc.execute(self._selected_report.report_id, record_id, dto)
            if self._main_window:
                self._main_window.show_status("Record recalculated.")
            return updated
        except Exception as e:
            if self._main_window:
                self._main_window.show_status(f"Update failed: {e}")
            return None

    # -- approve / decline / undo ------------------------------------------

    def _on_approve(self) -> None:
        if self._selected_report is None:
            return
        report_id = self._selected_report.report_id
        is_paidoff = self._selected_report.report_mode == CalculationMode.PAIDOFF

        approve_uc = ApproveReport(
            self._container.get_uow,
            self._container.recovery_service,
            self._container.backup_service,
            self._container.event_bus,
            clock=self._container.clock,
        )

        try:
            result = approve_uc.execute(report_id, force=False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Approval failed: {e}")
            return

        kind, text = approve_outcome(result, is_paidoff)

        if kind == "confirm":
            reply = QMessageBox.warning(
                self, "Confirmation Required", text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            try:
                result = approve_uc.execute(report_id, force=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Approval failed: {e}")
                return
            kind, text = approve_outcome(result, is_paidoff)

        if kind == "refused":
            QMessageBox.warning(self, "Cannot approve", text)
            return

        if kind == "not_pending":
            QMessageBox.information(self, "No longer pending", text)
            self.refresh()
            return

        # kind == "done"
        if self._main_window:
            self._main_window.show_status(f"Report {report_id} approved.")
            if hasattr(self._main_window, "_view_tab"):
                self._main_window._view_tab.refresh()
        # KCH-245 review cycle 1, m4: `text` can note skipped-deleted
        # records (approve_outcome's "done" branch) -- the status bar
        # message above is a fixed one-liner that drops it, so the plan's
        # "done notes skipped deleted" never reached the user. An info box
        # only when there is something extra to say; a plain approval stays
        # silent-but-not-hidden (status bar alone), same as before.
        if result.deleted_ref_ids:
            QMessageBox.information(self, "Report approved", text)
        self.refresh()

    def _on_decline(self) -> None:
        if self._selected_report is None:
            return
        report_id = self._selected_report.report_id

        reply = QMessageBox.question(
            self, "Confirm Decline",
            f"Are you sure you want to decline report {report_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            decline_uc = DeclineReport(self._container.get_uow, self._container.event_bus)
            decline_uc.execute(report_id)
            if self._main_window:
                self._main_window.show_status(f"Report {report_id} declined.")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Decline failed: {e}")

    def _on_undo(self) -> None:
        if self._selected_approved is None:
            return
        report_id = self._selected_approved.report_id
        report_mode = self._selected_approved.report_mode

        # KCH-245 review cycle 1, m3: PAIDOFF and UPDATE are refused by
        # UndoApprovedReport UNCONDITIONALLY (never depend on what changed
        # since approval), so asking "Are you sure?" first and refusing
        # right after is a pointless extra click -- go straight to the use
        # case and show ITS refusal (never a presentation-side rule that
        # would duplicate/drift from UndoApprovedReport's own decision).
        if report_mode not in (CalculationMode.PAIDOFF, CalculationMode.UPDATE):
            reply = QMessageBox.question(
                self, "Confirm Undo",
                f"Are you sure you want to undo report {report_id}?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        undo_uc = UndoApprovedReport(
            self._container.get_uow, self._container.event_bus, clock=self._container.clock
        )
        try:
            result = undo_uc.execute(report_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Undo failed: {e}")
            return

        if not result.success:
            QMessageBox.warning(self, "Cannot undo", undo_refusal_text(result, report_mode))
            return

        if self._main_window:
            self._main_window.show_status(f"Report {report_id} undone.")
            if hasattr(self._main_window, "_view_tab"):
                self._main_window._view_tab.refresh()
        self.refresh()

    def _on_print(self) -> None:
        if self._selected_report is None:
            return
        from loan_manager.presentation.widgets.report_printer import ApprovalReportPrinter

        printer = ApprovalReportPrinter()
        printer.print_report(self._selected_report, self)
