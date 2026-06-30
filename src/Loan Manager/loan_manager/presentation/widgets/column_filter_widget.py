from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QToolButton, QMenu, QWidgetAction,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
)
from PySide6.QtCore import Signal, Qt


class ColumnFilterWidget(QWidget):
    filter_changed = Signal(int, list)

    def __init__(self, column_index: int, column_name: str, is_date: bool = False, parent=None):
        super().__init__(parent)
        self._col = column_index
        self._is_date = is_date
        self._selected: list[str] = []
        self._list: QListWidget | None = None

        btn = QToolButton(self)
        btn.setText(f"{column_name} \u25bc")
        btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._menu = QMenu(self)
        btn.setMenu(self._menu)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(btn)
        self._btn = btn

    def populate(self, values: list[str]) -> None:
        self._menu.clear()
        if self._is_date:
            self._populate_date_tree(values)
        else:
            self._populate_text_list(values)

    def _populate_date_tree(self, values: list[str]) -> None:
        year_month: dict[str, list[str]] = defaultdict(list)
        for v in values:
            if v and v != "Unknown":
                parts = v.split("-")
                if len(parts) == 3:
                    year_month[parts[0]].append(v)

        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        for year, dates in sorted(year_month.items()):
            year_item = QTreeWidgetItem([year])
            year_item.setCheckState(0, Qt.CheckState.Unchecked)
            months: dict[str, list] = defaultdict(list)
            for d in dates:
                month = d.split("-")[1]
                months[month].append(d)
            for month, month_dates in sorted(months.items()):
                month_item = QTreeWidgetItem([f"{year}-{month}"])
                month_item.setCheckState(0, Qt.CheckState.Unchecked)
                year_item.addChild(month_item)
            tree.addTopLevelItem(year_item)

        clear_btn_action = QWidgetAction(self._menu)
        clear_btn = QToolButton()
        clear_btn.setText("Clear")
        clear_btn.clicked.connect(self.clear_filter)
        clear_btn_action.setDefaultWidget(clear_btn)

        action = QWidgetAction(self._menu)
        action.setDefaultWidget(tree)
        self._menu.addAction(action)
        self._menu.addAction(clear_btn_action)

    def _populate_text_list(self, values: list[str]) -> None:
        lst = QListWidget()
        for v in sorted(set(values)):
            item = QListWidgetItem(v or "Unknown")
            item.setCheckState(Qt.CheckState.Unchecked)
            lst.addItem(item)
        lst.itemChanged.connect(self._on_text_selection_changed)

        clear_action = QWidgetAction(self._menu)
        clear_btn = QToolButton()
        clear_btn.setText("Clear")
        clear_btn.clicked.connect(self.clear_filter)
        clear_action.setDefaultWidget(clear_btn)

        action = QWidgetAction(self._menu)
        action.setDefaultWidget(lst)
        self._menu.addAction(action)
        self._menu.addAction(clear_action)
        self._list = lst

    def _on_text_selection_changed(self, item: QListWidgetItem) -> None:
        self._selected = []
        if self._list is not None:
            for i in range(self._list.count()):
                it = self._list.item(i)
                if it.checkState() == Qt.CheckState.Checked:
                    self._selected.append(it.text())
        self.filter_changed.emit(self._col, self._selected)

    def clear_filter(self) -> None:
        self._selected = []
        self.filter_changed.emit(self._col, [])
        self._menu.close()
