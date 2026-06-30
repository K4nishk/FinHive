from PySide6.QtWidgets import QComboBox, QStyledItemDelegate
from PySide6.QtCore import QModelIndex, Qt
from loan_manager.domain.value_objects.status import LoanStatus


class StatusDelegate(QStyledItemDelegate):
    """Renders Status column cells as coloured QComboBox."""

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self._theme = theme_manager

    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        for s in LoanStatus:
            combo.addItem(s.value)
        return combo

    def setEditorData(self, editor, index):
        value = index.data()
        idx = editor.findText(value)
        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), role=Qt.ItemDataRole.UserRole + 1)
