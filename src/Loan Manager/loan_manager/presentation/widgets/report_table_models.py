"""QAbstractTableModel pair for the approvals tab (KCH-245).

`ReportListModel` backs the pending/recently-approved report list;
`ReportRecordModel` backs the record detail view for whichever report is
selected. Neither imports a use case: `ReportRecordModel.setData` calls an
injected `on_edit` callback the tab wires to `UpdateReportRecord` through the
container, keeping business logic out of presentation (loan-manager-
conventions) while still letting the model be the thing Qt edits.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont

from loan_manager.application.dtos.loan_dto import LoanDTO
from loan_manager.application.dtos.report_dto import ReportDTO, ReportRecordDTO
from loan_manager.domain.value_objects.status import CalculationMode, ExtensionPeriodUnit

REPORT_COLUMNS = ["Report ID", "Author", "Mode", "Records", "Conflict", "Updated"]
REPORT_COL_IDX = {name: i for i, name in enumerate(REPORT_COLUMNS)}

RECORD_COLUMNS = [
    "Ref ID", "B Name", "D Name", "Amount",
    "Current B Name", "Current D Name", "Current Amount",
    "Orig G.Date", "Orig D.Date", "New G.Date", "New D.Date",
    "Rate %", "Comm %", "Period", "Unit", "TDS",
    "Interest", "Commission", "TDS Amt", "CHQ Amt",
]
REC_COL_IDX = {name: i for i, name in enumerate(RECORD_COLUMNS)}

# Rate/Comm/Period/Unit/TDS -- editable only when the report is a
# rate-driven mode (MONTHLY/DAILY/BOTH/PAIDOFF). A CREATE record has no
# existing loan to recalculate against and an UPDATE record carries no
# rate/period at all (see propose_update.py) -- editing either here would
# either silently do nothing or corrupt a field the proposal never touched
# (R3, orchestrator-accepted behaviour change from the old tab, which let
# every mode edit these).
_EDITABLE_COLS = {
    REC_COL_IDX["Rate %"], REC_COL_IDX["Comm %"], REC_COL_IDX["Period"],
    REC_COL_IDX["Unit"], REC_COL_IDX["TDS"],
}
_READONLY_MODES = {CalculationMode.CREATE, CalculationMode.UPDATE}

_FIELD_BY_COL = {
    REC_COL_IDX["Rate %"]: "interest_rate",
    REC_COL_IDX["Comm %"]: "commission_rate",
    REC_COL_IDX["Period"]: "extension_period",
    REC_COL_IDX["Unit"]: "extension_period_unit",
    REC_COL_IDX["TDS"]: "tds_flag",
}

# Proposed-value columns an UPDATE row bolds when they differ from the live
# loan (R1: "Current" is the live loan via GetAllLoans, not a stored
# before-snapshot -- see DEBT D1).
_PROPOSED_VS_CURRENT = {
    REC_COL_IDX["B Name"]: ("borrower_name", "borrower_name"),
    REC_COL_IDX["D Name"]: ("depositor_name", "depositor_name"),
    REC_COL_IDX["Amount"]: ("amount", "amount"),
}

_NOT_ACTIVE = "(loan not active)"
_NA = "N/A"
_NEW = "(new)"


class ReportListModel(QAbstractTableModel):
    """One row per report (pending, or recently approved)."""

    def __init__(self, theme_manager, parent=None, time_header: str = "Updated"):
        super().__init__(parent)
        self._theme = theme_manager
        self._reports: list[ReportDTO] = []
        # KCH-245 review cycle 1, m1: the Recently Approved panel reuses
        # this model, but its time column is when the report was approved,
        # not the last-edited timestamp "Updated" implies for the pending
        # list -- override just the header text, same data (updated_at).
        self._time_header = time_header

    def load(self, reports: list[ReportDTO]) -> None:
        self.beginResetModel()
        self._reports = reports
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._reports)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(REPORT_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            if section == REPORT_COL_IDX["Updated"]:
                return self._time_header
            return REPORT_COLUMNS[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        report = self._reports[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(report, col)

        if col == REPORT_COL_IDX["Author"]:
            colour = self._theme.get_badge_colour(report.actor.value)
            if role == Qt.ItemDataRole.BackgroundRole:
                return QBrush(QColor(colour["background"]))
            if role == Qt.ItemDataRole.ForegroundRole:
                return QBrush(QColor(colour["text"]))
            if role == Qt.ItemDataRole.FontRole:
                font = QFont()
                font.setBold(colour.get("bold", False))
                return font

        if col == REPORT_COL_IDX["Conflict"] and report.conflict_ref_ids:
            colour = self._theme.get_badge_colour("CONFLICT")
            if role == Qt.ItemDataRole.BackgroundRole:
                return QBrush(QColor(colour["background"]))
            if role == Qt.ItemDataRole.ForegroundRole:
                return QBrush(QColor(colour["text"]))

        if role == Qt.ItemDataRole.UserRole:
            return report

        return None

    def _display_value(self, report: ReportDTO, col: int):
        if col == REPORT_COL_IDX["Report ID"]:
            return report.report_id
        if col == REPORT_COL_IDX["Author"]:
            return report.actor.value
        if col == REPORT_COL_IDX["Mode"]:
            return report.report_mode.value
        if col == REPORT_COL_IDX["Records"]:
            # KCH-245 review cycle 1, m7: an int, not str -- QSortFilterProxyModel's
            # default sortRole is DisplayRole, and Qt compares two ints
            # numerically but two strings lexically ("10" < "9"). Qt renders
            # a plain int exactly like the str did, so this changes sorting
            # only, not what the cell shows.
            return len(report.records)
        if col == REPORT_COL_IDX["Conflict"]:
            return ", ".join(report.conflict_ref_ids) if report.conflict_ref_ids else ""
        if col == REPORT_COL_IDX["Updated"]:
            return report.updated_at.strftime("%Y-%m-%d %H:%M")
        return ""

    def report_at(self, row: int) -> ReportDTO | None:
        if 0 <= row < len(self._reports):
            return self._reports[row]
        return None


class ReportRecordModel(QAbstractTableModel):
    """Records for whichever report is currently selected."""

    def __init__(
        self,
        theme_manager,
        on_edit: Callable[[int, str, Any], ReportRecordDTO | None] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme_manager
        self._on_edit = on_edit
        self._records: list[ReportRecordDTO] = []
        self._report_mode: CalculationMode | None = None
        self._conflict_ref_ids: set[str] = set()
        self._current_loans: dict[str, LoanDTO] = {}

    def load(
        self,
        records: list[ReportRecordDTO],
        report_mode: CalculationMode | None,
        conflict_ref_ids=(),
        current_loans: dict[str, LoanDTO] | None = None,
    ) -> None:
        self.beginResetModel()
        self._records = records
        self._report_mode = report_mode
        self._conflict_ref_ids = set(conflict_ref_ids)
        self._current_loans = current_loans or {}
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._records)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(RECORD_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return RECORD_COLUMNS[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        col = index.column()
        if col in _EDITABLE_COLS and self._report_mode not in _READONLY_MODES:
            return base | Qt.ItemFlag.ItemIsEditable
        return base

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        rec = self._records[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return self._display_value(rec, col)

        if col == REC_COL_IDX["Ref ID"] and rec.reference_id in self._conflict_ref_ids:
            colour = self._theme.get_badge_colour("CONFLICT")
            if role == Qt.ItemDataRole.BackgroundRole:
                return QBrush(QColor(colour["background"]))
            if role == Qt.ItemDataRole.ForegroundRole:
                return QBrush(QColor(colour["text"]))

        if role == Qt.ItemDataRole.FontRole:
            font = QFont()
            if self._is_changed_from_current(rec, col):
                font.setBold(True)
            return font

        if role == Qt.ItemDataRole.UserRole:
            return rec

        return None

    def _current_loan_for(self, rec: ReportRecordDTO) -> LoanDTO | None:
        if rec.reference_id is None:
            return None
        return self._current_loans.get(rec.reference_id)

    def _is_changed_from_current(self, rec: ReportRecordDTO, col: int) -> bool:
        if self._report_mode != CalculationMode.UPDATE:
            return False
        pair = _PROPOSED_VS_CURRENT.get(col)
        if pair is None:
            return False
        proposed_field, current_field = pair
        current = self._current_loan_for(rec)
        if current is None:
            return False
        return getattr(rec, proposed_field) != getattr(current, current_field)

    def _display_value(self, rec: ReportRecordDTO, col: int) -> str:
        if col == REC_COL_IDX["Ref ID"]:
            return rec.reference_id if rec.reference_id else _NEW
        if col == REC_COL_IDX["B Name"]:
            return rec.borrower_name
        if col == REC_COL_IDX["D Name"]:
            return rec.depositor_name
        if col == REC_COL_IDX["Amount"]:
            return str(rec.amount)

        if col in (
            REC_COL_IDX["Current B Name"],
            REC_COL_IDX["Current D Name"],
            REC_COL_IDX["Current Amount"],
        ):
            if self._report_mode != CalculationMode.UPDATE:
                return _NA
            current = self._current_loan_for(rec)
            if current is None:
                return _NOT_ACTIVE
            if col == REC_COL_IDX["Current B Name"]:
                return current.borrower_name
            if col == REC_COL_IDX["Current D Name"]:
                return current.depositor_name
            return str(current.amount)

        if col == REC_COL_IDX["Orig G.Date"]:
            return str(rec.giving_date) if rec.giving_date else _NA
        if col == REC_COL_IDX["Orig D.Date"]:
            return str(rec.due_date) if rec.due_date else _NA
        if col == REC_COL_IDX["New G.Date"]:
            return str(rec.post_extension_giving_date) if rec.post_extension_giving_date else _NA
        if col == REC_COL_IDX["New D.Date"]:
            return str(rec.post_extension_due_date) if rec.post_extension_due_date else _NA

        if col == REC_COL_IDX["Rate %"]:
            return str(rec.interest_rate)
        if col == REC_COL_IDX["Comm %"]:
            return str(rec.commission_rate)
        if col == REC_COL_IDX["Period"]:
            return str(rec.extension_period)
        if col == REC_COL_IDX["Unit"]:
            return rec.extension_period_unit.value
        if col == REC_COL_IDX["TDS"]:
            return "Yes" if rec.tds_flag else "No"

        if col == REC_COL_IDX["Interest"]:
            return str(rec.interest_amount) if rec.interest_amount is not None else _NA
        if col == REC_COL_IDX["Commission"]:
            return str(rec.commission_amount) if rec.commission_amount is not None else _NA
        if col == REC_COL_IDX["TDS Amt"]:
            return str(rec.tds_amount) if rec.tds_amount is not None else _NA
        if col == REC_COL_IDX["CHQ Amt"]:
            return str(rec.chq_amount) if rec.chq_amount is not None else _NA

        return ""

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        if not (self.flags(index) & Qt.ItemFlag.ItemIsEditable):
            return False
        row, col = index.row(), index.column()
        rec = self._records[row]
        field = _FIELD_BY_COL.get(col)
        if field is None or rec.id is None or self._on_edit is None:
            return False

        try:
            payload = self._coerce(field, value)
        except (ValueError, TypeError):
            return False

        updated = self._on_edit(rec.id, field, payload)
        if updated is None:
            return False

        self._records[row] = updated
        top_left = self.index(row, 0)
        bottom_right = self.index(row, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right)
        return True

    @staticmethod
    def _coerce(field: str, value: Any) -> Any:
        from decimal import Decimal

        if field in ("interest_rate", "commission_rate"):
            return Decimal(str(value))
        if field == "extension_period":
            return int(value)
        if field == "extension_period_unit":
            return ExtensionPeriodUnit(str(value))
        if field == "tds_flag":
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in ("yes", "true", "1")
        return value

    def record_at(self, row: int) -> ReportRecordDTO | None:
        if 0 <= row < len(self._records):
            return self._records[row]
        return None
