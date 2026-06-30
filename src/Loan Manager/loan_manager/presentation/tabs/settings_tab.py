import json
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QPushButton, QLabel, QMessageBox, QFileDialog,
    QColorDialog,
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from loan_manager.config import SETTINGS_FILE, DATA_DIR
from loan_manager.application.use_cases.data.export_loans import ExportLoans
from loan_manager.application.use_cases.data.import_loans import ImportLoans
from loan_manager.presentation.dialogs.import_preview_dialog import ImportPreviewDialog
from loan_manager.presentation.themes.theme_manager import ThemeManager
from loan_manager.domain.value_objects.status import LoanStatus


class SettingsTab(QWidget):
    def __init__(self, container, theme_manager, parent=None):
        super().__init__(parent)
        self._container = container
        self._theme = theme_manager
        self._main_window = parent
        self._custom_colours: dict = {}
        self._colour_buttons: dict[str, QPushButton] = {}
        self._load_settings()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Theme section
        theme_group = QGroupBox("Theme")
        theme_layout = QHBoxLayout()
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(ThemeManager.available_themes())
        current = self._settings.get("theme", "dark")
        idx = self._theme_combo.findText(current)
        if idx >= 0:
            self._theme_combo.setCurrentIndex(idx)
        theme_layout.addWidget(QLabel("Theme:"))
        theme_layout.addWidget(self._theme_combo)
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._on_apply_theme)
        theme_layout.addWidget(apply_btn)
        theme_layout.addStretch()
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        # Status colours section
        colour_group = QGroupBox("Status Colours")
        colour_layout = QFormLayout()
        for status in LoanStatus:
            btn = QPushButton()
            btn.setFixedSize(80, 30)
            self._update_colour_button(btn, status.value)
            btn.clicked.connect(lambda checked, s=status.value: self._pick_colour(s))
            colour_layout.addRow(f"{status.value}:", btn)
            self._colour_buttons[status.value] = btn
        colour_group.setLayout(colour_layout)
        layout.addWidget(colour_group)

        # Data directory
        data_group = QGroupBox("Data")
        data_layout = QFormLayout()
        data_dir_label = QLabel(str(DATA_DIR))
        data_dir_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        data_layout.addRow("Data Directory:", data_dir_label)
        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

        # Import/Export
        io_group = QGroupBox("Import / Export")
        io_layout = QHBoxLayout()

        import_btn = QPushButton("Import Legacy Data")
        import_btn.clicked.connect(self._on_import)
        io_layout.addWidget(import_btn)

        export_csv_btn = QPushButton("Export CSV")
        export_csv_btn.clicked.connect(lambda: self._on_export("csv"))
        io_layout.addWidget(export_csv_btn)

        export_xlsx_btn = QPushButton("Export XLSX")
        export_xlsx_btn.clicked.connect(lambda: self._on_export("xlsx"))
        io_layout.addWidget(export_xlsx_btn)

        io_layout.addStretch()
        io_group.setLayout(io_layout)
        layout.addWidget(io_group)

        layout.addStretch()

    def _load_settings(self) -> None:
        self._settings = {}
        if SETTINGS_FILE.exists():
            try:
                self._settings = json.loads(SETTINGS_FILE.read_text())
                self._custom_colours = self._settings.get("custom_colours", {})
            except Exception:
                pass

    def _save_settings(self) -> None:
        self._settings["custom_colours"] = self._custom_colours
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(self._settings, indent=2))

    def _on_apply_theme(self) -> None:
        theme = self._theme_combo.currentText()
        self._settings["theme"] = theme
        self._save_settings()
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            ThemeManager.apply_theme(theme, app, self._custom_colours or None)
        if self._main_window:
            self._main_window.show_status(f"Theme changed to {theme}.")

    def _update_colour_button(self, btn: QPushButton, status: str) -> None:
        colour_info = self._theme.get_status_colour(status)
        bg = colour_info["background"]
        txt = colour_info["text"]
        btn.setStyleSheet(f"background-color: {bg}; color: {txt}; border: 1px solid gray;")
        btn.setText(bg)

    def _pick_colour(self, status: str) -> None:
        current_info = self._theme.get_status_colour(status)
        colour = QColorDialog.getColor(
            QColor(current_info["background"]), self, f"Pick colour for {status}"
        )
        if colour.isValid():
            self._custom_colours[status] = {
                "background": colour.name(),
                "text": current_info.get("text", current_info["text"]),
                "bold": current_info.get("bold", True),
            }
            self._save_settings()
            btn = self._colour_buttons.get(status)
            if btn:
                self._update_colour_button(btn, status)

            # Re-apply theme with custom colours
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                theme = self._theme_combo.currentText()
                ThemeManager.apply_theme(theme, app, self._custom_colours)

    def _on_import(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return

        try:
            import_uc = ImportLoans(self._container.get_uow)
            preview = import_uc.preview(file_path)

            dlg = ImportPreviewDialog(preview, self)
            if dlg.exec() == ImportPreviewDialog.DialogCode.Accepted and dlg.should_proceed():
                result = import_uc.commit(file_path, overwrite_existing=True)
                msg = (
                    f"Import complete.\n"
                    f"Inserted: {result.inserted}\n"
                    f"Updated: {result.updated}\n"
                    f"Skipped: {result.skipped}"
                )
                if result.errors:
                    msg += f"\nErrors: {len(result.errors)}"
                QMessageBox.information(self, "Import Result", msg)

                if self._main_window and hasattr(self._main_window, '_view_tab'):
                    self._main_window._view_tab.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Import failed: {e}")

    def _on_export(self, fmt: str) -> None:
        try:
            export_uc = ExportLoans(self._container.get_uow)
            output_path = export_uc.execute(format=fmt)
            if self._main_window:
                self._main_window.show_status(f"Exported to {output_path}")
            QMessageBox.information(
                self, "Export Complete", f"Loans exported to:\n{output_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
