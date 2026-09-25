from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from loan_manager.application.use_cases.data.export_loans import ExportLoans
from loan_manager.application.use_cases.data.import_loans import ImportLoans
from loan_manager.config import DATA_DIR, SETTINGS_FILE
from loan_manager.domain.value_objects.status import LoanStatus
from loan_manager.infrastructure.logging.logger import get_logger
from loan_manager.presentation.dialogs.import_preview_dialog import ImportPreviewDialog
from loan_manager.presentation.themes.theme_manager import ThemeManager

logger = get_logger(__name__)


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
        # True once this tab's view of custom colours legitimately reflects
        # disk -- either it parsed a real custom_colours dict, or there is
        # provably nothing on disk to lose (file missing). _save_settings()
        # consults it below (KCH-234 review round 1, item 11) so a tab that
        # never saw the file's real colours cannot blow them away with
        # whatever __init__ defaulted this to. A FAILED load (corrupt JSON,
        # bad UTF-8, non-object top level) leaves this False on purpose --
        # this tab has no idea what, if anything, is really on disk (KCH-234
        # review round 2, item 1).
        self._custom_colours_loaded = False
        if not SETTINGS_FILE.exists():
            # Nothing on disk to lose -- a fresh install / deleted file is a
            # legitimately-loaded "no colours yet" state, not a failed load.
            self._custom_colours_loaded = True
            return
        try:
            data = json.loads(SETTINGS_FILE.read_text())
        except (OSError, ValueError) as exc:
            # ValueError also catches UnicodeDecodeError (invalid UTF-8) and
            # json.JSONDecodeError, not just the latter -- either way this
            # file is not usable, and self._settings stays {} on purpose:
            # _save_settings() never writes this dict verbatim, so a corrupt
            # file cannot wipe itself just because this tab loaded first.
            logger.error("failed to load %s: %s", SETTINGS_FILE, exc)
            return
        if not isinstance(data, dict):
            logger.error(
                "refusing to use %s: top-level JSON is a %s, not an object",
                SETTINGS_FILE, type(data).__name__,
            )
            return
        self._settings = data
        self._custom_colours = data.get("custom_colours", {})
        self._custom_colours_loaded = True

    def _save_settings(self, edited_colour: str | None = None) -> bool:
        """Read-modify-write, not overwrite: re-read the file on disk right
        now and touch only `theme` and `custom_colours` in it. `self._settings`
        is this tab's own view and is not authoritative -- if the load at
        startup failed (or another tab/process wrote the file since), it can
        be stale or empty, and writing it back verbatim would silently drop
        every key this tab does not know about, in particular `llm`
        (KCH-234). If the re-read itself fails -- unreadable, invalid UTF-8,
        or valid JSON that is not an object -- nothing is written.

        `edited_colour`, when given, is the one status key the caller just
        changed via `_pick_colour`. That single key is always merged into
        whatever `custom_colours` is freshly re-read from disk right now
        (KCH-234 review round 2, item 1): a user's own edit must never be
        lost just because this tab's own `_custom_colours_loaded` view is
        stale or false (fresh install, or a load that failed and was later
        repaired by something else). Without `edited_colour` (a plain theme
        apply, no colour touched), `custom_colours` is only overwritten
        wholesale when this tab's view is known-good
        (`_custom_colours_loaded`); otherwise the on-disk value -- which this
        tab never actually saw and so cannot safely replace -- is left alone.

        Returns True if the file was written, False if the save was refused
        (nothing was written)."""
        current: dict = {}
        if SETTINGS_FILE.exists():
            try:
                current = json.loads(SETTINGS_FILE.read_text())
            except (OSError, ValueError) as exc:
                logger.error(
                    "refusing to save settings: could not re-read %s: %s",
                    SETTINGS_FILE, exc,
                )
                if self._main_window:
                    self._main_window.show_status(
                        "Settings not saved: existing settings file is unreadable."
                    )
                return False
            if not isinstance(current, dict):
                logger.error(
                    "refusing to save settings: %s top-level JSON is a %s, not an object",
                    SETTINGS_FILE, type(current).__name__,
                )
                if self._main_window:
                    self._main_window.show_status(
                        "Settings not saved: existing settings file is unreadable."
                    )
                return False

        current["theme"] = self._settings.get("theme", current.get("theme", "dark"))

        if edited_colour is not None:
            on_disk_colours = current.get("custom_colours")
            if not isinstance(on_disk_colours, dict):
                on_disk_colours = {}
            on_disk_colours[edited_colour] = self._custom_colours[edited_colour]
            current["custom_colours"] = on_disk_colours
        elif self._custom_colours_loaded:
            current["custom_colours"] = self._custom_colours
        # else: this tab never loaded real colours and isn't editing one now
        # -- leave current's on-disk custom_colours (if any) untouched.
        self._settings = current

        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(current, indent=2))
        return True

    def _on_apply_theme(self) -> None:
        theme = self._theme_combo.currentText()
        self._settings["theme"] = theme
        saved = self._save_settings()
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            ThemeManager.apply_theme(theme, app, self._custom_colours or None)
        # A refused save already put its own "Settings not saved" message on
        # the status bar (KCH-234 review round 2, item 5) -- overwriting it
        # here with a success message would hide that the theme was never
        # actually persisted.
        if saved and self._main_window:
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
            self._save_settings(edited_colour=status)
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
