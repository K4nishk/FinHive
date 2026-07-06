"""Column filter widget with clean state separation.

Architecture:
- FilterState: dataclass owning committed + pending selection state
- TextFilterPopup / DateFilterPopup: pure views — hold NO permanent state
- ColumnFilterWidget: owns FilterState, connects popup signals, mutates state

The popup NEVER reads its own widget state to determine what is selected.
It only renders what it is told. State lives in ColumnFilterWidget via FilterState.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QToolButton,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem,
    QPushButton, QCheckBox, QFrame,
)
from PySide6.QtCore import Signal, Qt, QPoint

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FilterState — single source of truth
# ---------------------------------------------------------------------------

@dataclass
class FilterState:
    """Owns committed and pending filter selection for one column."""

    column: int
    all_values: list[str] = field(default_factory=list)
    committed: set[str] = field(default_factory=set)
    pending: set[str] = field(default_factory=set)
    is_date_column: bool = False

    def is_active(self) -> bool:
        return len(self.committed) > 0

    def commit(self) -> None:
        self.committed = self.pending.copy()

    def cancel(self) -> None:
        self.pending = self.committed.copy()

    def select_all(self) -> None:
        self.pending = set(self.all_values)

    def clear_pending(self) -> None:
        self.pending = set()

    def clear_committed(self) -> None:
        self.committed = set()
        self.pending = set()

    def toggle(self, value: str) -> None:
        if value in self.pending:
            self.pending.discard(value)
        else:
            self.pending.add(value)


# ---------------------------------------------------------------------------
# TextFilterPopup — pure view, holds NO permanent state
# ---------------------------------------------------------------------------

class TextFilterPopup(QFrame):
    """Text column filter popup — renders from authoritative state only."""

    item_toggled = Signal(str, bool)       # (value, new_checked_state)
    select_all_clicked = Signal(bool)      # True = select all, False = deselect all
    apply_clicked = Signal()
    cancel_clicked = Signal()
    clear_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMinimumWidth(200)
        self.setMaximumHeight(350)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self._select_all = QCheckBox("Select All")
        self._select_all.setAccessibleName("Select all filter items")
        self._select_all.stateChanged.connect(self._on_select_all_changed)
        layout.addWidget(self._select_all)

        self._list = QListWidget()
        self._list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Use itemPressed — items do NOT have ItemIsUserCheckable,
        # so Qt will NOT auto-toggle the checkbox on click.
        self._list.itemPressed.connect(self._on_item_pressed)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.setAccessibleName("Clear filter selection")
        clear_btn.clicked.connect(lambda: self.clear_clicked.emit())
        apply_btn = QPushButton("Apply")
        apply_btn.setAccessibleName("Apply filter")
        apply_btn.clicked.connect(lambda: self.apply_clicked.emit())
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setAccessibleName("Cancel filter changes")
        cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit())
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(apply_btn)
        layout.addLayout(btn_layout)

    # -- Pure rendering methods (called by ColumnFilterWidget) --

    def render(self, all_values: list[str], selected: set[str]) -> None:
        """Complete re-render from authoritative state. Called every popup open."""
        self._list.blockSignals(True)
        self._list.clear()

        for value in sorted(set(all_values)):
            text = value or "Unknown"
            item = QListWidgetItem(text)
            # NO ItemIsUserCheckable — we manage checkboxes manually
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setCheckState(
                Qt.CheckState.Checked if text in selected
                else Qt.CheckState.Unchecked
            )
            self._list.addItem(item)

        self._list.blockSignals(False)
        self._sync_select_all_visual(all_values, selected)

    def set_item_checked(self, value: str, checked: bool) -> None:
        """Update a single item's visual state."""
        self._list.blockSignals(True)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self._list.count()):
            if self._list.item(i).text() == value:
                self._list.item(i).setCheckState(state)
                break
        self._list.blockSignals(False)

    def set_all_checked(self, checked: bool) -> None:
        """Set all items to checked/unchecked."""
        self._list.blockSignals(True)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(state)
        self._list.blockSignals(False)
        self._select_all.blockSignals(True)
        self._select_all.setCheckState(state)
        self._select_all.blockSignals(False)
        self._list.viewport().update()

    def update_select_all_visual(self, all_count: int, selected_count: int) -> None:
        """Update the Select All checkbox based on counts."""
        self._select_all.blockSignals(True)
        if all_count == 0:
            self._select_all.setCheckState(Qt.CheckState.Unchecked)
        elif selected_count == all_count:
            self._select_all.setCheckState(Qt.CheckState.Checked)
        elif selected_count == 0:
            self._select_all.setCheckState(Qt.CheckState.Unchecked)
        else:
            self._select_all.setCheckState(Qt.CheckState.PartiallyChecked)
        self._select_all.blockSignals(False)

    # -- Internal signal handlers --

    def _on_item_pressed(self, item: QListWidgetItem) -> None:
        """User clicked an item. Emit toggle signal — do NOT change widget state."""
        currently_checked = item.checkState() == Qt.CheckState.Checked
        # Emit the NEW desired state (opposite of current)
        self.item_toggled.emit(item.text(), not currently_checked)

    def _on_select_all_changed(self, state: int) -> None:
        """Select All checkbox changed by user click."""
        checked = state == Qt.CheckState.Checked.value
        self.select_all_clicked.emit(checked)

    def _sync_select_all_visual(self, all_values: list[str], selected: set[str]) -> None:
        """Sync Select All checkbox during render."""
        unique_count = len(set(all_values))
        # Count how many of the unique display values are selected
        display_values = set(v or "Unknown" for v in all_values)
        selected_count = len(selected & display_values)
        self.update_select_all_visual(unique_count, selected_count)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_clicked.emit()
        else:
            super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# DateFilterPopup — pure view for date hierarchy
# ---------------------------------------------------------------------------

class DateFilterPopup(QFrame):
    """Date column filter popup with hierarchical year/month tree — pure view."""

    item_toggled = Signal(str, bool)       # (value, new_checked_state)
    select_all_clicked = Signal(bool)
    apply_clicked = Signal()
    cancel_clicked = Signal()
    clear_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setMinimumWidth(200)
        self.setMaximumHeight(350)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self._select_all = QCheckBox("Select All")
        self._select_all.setAccessibleName("Select all date filter items")
        self._select_all.stateChanged.connect(self._on_select_all_changed)
        layout.addWidget(self._select_all)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Use itemPressed — items do NOT have ItemIsUserCheckable
        self._tree.itemPressed.connect(self._on_tree_item_pressed)
        layout.addWidget(self._tree)

        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear")
        clear_btn.setAccessibleName("Clear date filter selection")
        clear_btn.clicked.connect(lambda: self.clear_clicked.emit())
        apply_btn = QPushButton("Apply")
        apply_btn.setAccessibleName("Apply date filter")
        apply_btn.clicked.connect(lambda: self.apply_clicked.emit())
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setAccessibleName("Cancel date filter changes")
        cancel_btn.clicked.connect(lambda: self.cancel_clicked.emit())
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(apply_btn)
        layout.addLayout(btn_layout)

        self._has_unknown = False

    # -- Pure rendering methods --

    def render(self, all_values: list[str], selected: set[str]) -> None:
        """Complete re-render of date tree from authoritative state."""
        self._tree.blockSignals(True)
        self._tree.clear()
        self._has_unknown = False

        year_month: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for v in all_values:
            if not v or v == "Unknown":
                self._has_unknown = True
                continue
            parts = v.split("-")
            if len(parts) >= 2:
                year = parts[0]
                month = parts[1]
                year_month[year][month].append(v)

        for year in sorted(year_month.keys()):
            year_item = QTreeWidgetItem([year])
            # NO ItemIsUserCheckable — managed manually
            year_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            all_months_checked = True
            any_month_checked = False
            for month in sorted(year_month[year].keys()):
                month_key = f"{year}-{month}"
                month_item = QTreeWidgetItem([month_key])
                month_item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                if month_key in selected:
                    month_item.setCheckState(0, Qt.CheckState.Checked)
                    any_month_checked = True
                else:
                    month_item.setCheckState(0, Qt.CheckState.Unchecked)
                    all_months_checked = False
                year_item.addChild(month_item)

            if year in selected or all_months_checked:
                year_item.setCheckState(0, Qt.CheckState.Checked)
            elif any_month_checked:
                year_item.setCheckState(0, Qt.CheckState.PartiallyChecked)
            else:
                year_item.setCheckState(0, Qt.CheckState.Unchecked)
            self._tree.addTopLevelItem(year_item)

        if self._has_unknown:
            unknown_item = QTreeWidgetItem(["Unknown"])
            unknown_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            if "Unknown" in selected:
                unknown_item.setCheckState(0, Qt.CheckState.Checked)
            else:
                unknown_item.setCheckState(0, Qt.CheckState.Unchecked)
            self._tree.addTopLevelItem(unknown_item)

        self._tree.expandAll()
        self._sync_select_all()
        self._tree.blockSignals(False)

    def set_all_checked(self, checked: bool) -> None:
        """Set all tree items to checked/unchecked."""
        self._tree.blockSignals(True)
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            top.setCheckState(0, state)
            for j in range(top.childCount()):
                top.child(j).setCheckState(0, state)
        self._tree.blockSignals(False)
        self._select_all.blockSignals(True)
        self._select_all.setCheckState(state)
        self._select_all.blockSignals(False)

    def render_from_pending(self, all_values: list[str], selected: set[str]) -> None:
        """Re-render tree to reflect updated pending state after toggle."""
        self.render(all_values, selected)

    # -- Internal signal handlers --

    def _on_tree_item_pressed(self, item: QTreeWidgetItem, column: int) -> None:
        """User clicked a tree item. Emit toggle signals — do NOT change widget state."""
        currently_checked = item.checkState(0) == Qt.CheckState.Checked
        new_state = not currently_checked
        text = item.text(0)

        # If it's a year node (has children), emit toggles for year + all months
        if item.childCount() > 0:
            self.item_toggled.emit(text, new_state)
            for i in range(item.childCount()):
                self.item_toggled.emit(item.child(i).text(0), new_state)
        else:
            self.item_toggled.emit(text, new_state)

    def _on_select_all_changed(self, state: int) -> None:
        checked = state == Qt.CheckState.Checked.value
        self.select_all_clicked.emit(checked)

    def _sync_select_all(self) -> None:
        """Update Select All checkbox to match current tree state (no signals)."""
        count = self._tree.topLevelItemCount()
        if count == 0:
            self._select_all.setCheckState(Qt.CheckState.Unchecked)
            return
        all_checked = all(
            self._tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
            for i in range(count)
        )
        none_checked = all(
            self._tree.topLevelItem(i).checkState(0) == Qt.CheckState.Unchecked
            for i in range(count)
        )
        old_block = self._select_all.blockSignals(True)
        if all_checked:
            self._select_all.setCheckState(Qt.CheckState.Checked)
        elif none_checked:
            self._select_all.setCheckState(Qt.CheckState.Unchecked)
        else:
            self._select_all.setCheckState(Qt.CheckState.PartiallyChecked)
        self._select_all.blockSignals(old_block)

    def get_all_date_keys(self, all_values: list[str]) -> list[str]:
        """Extract all selectable date keys (year, month, Unknown) from values."""
        keys = []
        year_month: dict[str, set[str]] = defaultdict(set)
        has_unknown = False
        for v in all_values:
            if not v or v == "Unknown":
                has_unknown = True
                continue
            parts = v.split("-")
            if len(parts) >= 2:
                year_month[parts[0]].add(f"{parts[0]}-{parts[1]}")
        for year in sorted(year_month.keys()):
            keys.append(year)
            keys.extend(sorted(year_month[year]))
        if has_unknown:
            keys.append("Unknown")
        return keys

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancel_clicked.emit()
        else:
            super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# ColumnFilterWidget — owns all state
# ---------------------------------------------------------------------------

class ColumnFilterWidget(QWidget):
    """Spreadsheet-style column filter with dropdown popup.

    Owns FilterState (single source of truth). The popup is a pure view.
    """

    filter_changed = Signal(int, list)  # column_index, committed values

    def __init__(
        self,
        column_index: int,
        column_name: str,
        is_date: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._col = column_index
        self._col_name = column_name
        self._is_date = is_date

        self._state = FilterState(
            column=column_index,
            all_values=[],
            committed=set(),
            pending=set(),
            is_date_column=is_date,
        )

        self._btn = QToolButton(self)
        self._btn.setText(f"{column_name} \u25bc")
        self._btn.setAccessibleName(f"Filter by {column_name}")
        self._btn.clicked.connect(self._open_popup)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._btn)

        if is_date:
            self._popup = DateFilterPopup(self)
        else:
            self._popup = TextFilterPopup(self)

        # Connect popup signals — ColumnFilterWidget handles all state mutation
        self._popup.item_toggled.connect(self._on_item_toggled)
        self._popup.select_all_clicked.connect(self._on_select_all)
        self._popup.apply_clicked.connect(self._on_apply)
        self._popup.cancel_clicked.connect(self._on_cancel)
        self._popup.clear_clicked.connect(self._on_clear)

    @property
    def column_name(self) -> str:
        return self._col_name

    @property
    def selected_values(self) -> list[str]:
        return list(self._state.committed)

    def populate(self, values: list[str]) -> None:
        """Update available values. Preserves committed state for values that
        still exist."""
        self._state.all_values = list(values)
        # Keep only committed values that still exist in the new values list
        if self._is_date:
            # For date columns, committed holds year/month keys, not raw values
            # so we don't intersect with raw values
            pass
        else:
            display_values = set(v or "Unknown" for v in values)
            self._state.committed &= display_values
        self._state.pending = self._state.committed.copy()

    def clear_filter(self) -> None:
        """Called by external 'Clear All' button in ViewTab."""
        self._state.clear_committed()
        self._btn.setText(f"{self._col_name} \u25bc")
        self.filter_changed.emit(self._state.column, [])

    def get_committed(self) -> set[str]:
        return self._state.committed.copy()

    # -- Popup lifecycle --

    def _open_popup(self) -> None:
        """Open popup — always renders fresh from committed state."""
        self._state.pending = self._state.committed.copy()
        logger.debug(
            "[FilterState col=%d] popup_open: pending=%s",
            self._state.column, self._state.pending,
        )
        self._popup.render(self._state.all_values, self._state.pending)
        pos = self._btn.mapToGlobal(QPoint(0, self._btn.height()))
        self._popup.move(pos)
        self._popup.show()
        self._popup.raise_()

    # -- Signal handlers --

    def _on_item_toggled(self, value: str, checked: bool) -> None:
        if checked:
            self._state.pending.add(value)
        else:
            self._state.pending.discard(value)
        logger.debug(
            "[FilterState col=%d] item_toggled: %s=%s -> pending=%s",
            self._state.column, value, checked, self._state.pending,
        )

        if self._is_date:
            # For date columns, re-render the whole tree to reflect
            # parent/child state changes
            self._popup.render_from_pending(
                self._state.all_values, self._state.pending
            )
        else:
            self._popup.set_item_checked(value, checked)
            # Update Select All visual
            unique_display = set(v or "Unknown" for v in self._state.all_values)
            self._popup.update_select_all_visual(
                len(unique_display), len(self._state.pending & unique_display)
            )

    def _on_select_all(self, checked: bool) -> None:
        if checked:
            if self._is_date:
                # Collect all selectable date keys
                all_keys = self._popup.get_all_date_keys(self._state.all_values)
                self._state.pending = set(all_keys)
            else:
                # For text, all_values may contain duplicates/empty — use display
                display = set(v or "Unknown" for v in self._state.all_values)
                self._state.pending = display
        else:
            self._state.clear_pending()
        self._popup.set_all_checked(checked)
        logger.debug(
            "[FilterState col=%d] select_all=%s -> pending=%s",
            self._state.column, checked, self._state.pending,
        )

    def _on_apply(self) -> None:
        self._state.commit()
        self._popup.hide()
        logger.debug(
            "[FilterState col=%d] apply: committed=%s",
            self._state.column, self._state.committed,
        )
        self.filter_changed.emit(self._state.column, list(self._state.committed))
        self._update_button_indicator()

    def _on_cancel(self) -> None:
        self._state.cancel()
        self._popup.hide()
        logger.debug(
            "[FilterState col=%d] cancel: reverted pending=%s",
            self._state.column, self._state.pending,
        )

    def _on_clear(self) -> None:
        self._state.clear_committed()
        self._popup.hide()
        logger.debug(
            "[FilterState col=%d] clear: committed=%s",
            self._state.column, self._state.committed,
        )
        self.filter_changed.emit(self._state.column, [])
        self._update_button_indicator()

    def _update_button_indicator(self) -> None:
        """Show visual indicator on button when filter is active."""
        if self._state.is_active():
            self._btn.setText(f"{self._col_name} \u25bc *")
        else:
            self._btn.setText(f"{self._col_name} \u25bc")
