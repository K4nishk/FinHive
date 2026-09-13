from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PySide6.QtGui import QColor, QFont, QBrush
from loan_manager.application.dtos.loan_dto import LoanDTO

COLUMNS = [
    "SNo", "Ref ID", "B Name", "B Grp", "Amt",
    "D Name", "D Grp", "G Date", "D Date", "Status",
]
COL_IDX = {name: i for i, name in enumerate(COLUMNS)}


class LoanTableModel(QAbstractTableModel):
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self._loans: list[LoanDTO] = []
        self._theme = theme_manager

    def load(self, loans: list[LoanDTO]) -> None:
        self.beginResetModel()
        self._loans = loans
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._loans)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        loan = self._loans[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(loan, col, index.row())

        if role == Qt.ItemDataRole.BackgroundRole and col == COL_IDX["Status"]:
            colour_info = self._theme.get_status_colour(loan.status.value)
            return QBrush(QColor(colour_info["background"]))

        if role == Qt.ItemDataRole.ForegroundRole and col == COL_IDX["Status"]:
            colour_info = self._theme.get_status_colour(loan.status.value)
            return QBrush(QColor(colour_info["text"]))

        if role == Qt.ItemDataRole.FontRole and col == COL_IDX["Status"]:
            colour_info = self._theme.get_status_colour(loan.status.value)
            font = QFont()
            font.setBold(colour_info.get("bold", False))
            return font

        if role == Qt.ItemDataRole.UserRole:
            return loan

        return None

    def _display_value(self, loan: LoanDTO, col: int, row: int) -> str:
        mapping = {
            0: str(row + 1),
            1: loan.reference_id,
            2: loan.borrower_name or "Unknown",
            3: loan.borrower_group or "Unknown",
            4: str(loan.amount),
            5: loan.depositor_name or "Unknown",
            6: loan.depositor_group or "Unknown",
            7: str(loan.giving_date) if loan.giving_date else "Unknown",
            8: str(loan.due_date) if loan.due_date else "Unknown",
            9: loan.status.value,
        }
        return mapping.get(col, "")

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        if index.column() in (0, 1):
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return (
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEditable
        )

    def loan_at(self, row: int) -> LoanDTO | None:
        if 0 <= row < len(self._loans):
            return self._loans[row]
        return None
