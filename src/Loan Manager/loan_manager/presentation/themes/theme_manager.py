import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor

THEMES_DIR = Path(__file__).parent / "themes"


class ThemeManager:
    _current_config: dict = {}
    _custom_colours: dict = {}

    @classmethod
    def apply_theme(cls, theme_name: str, app: QApplication, custom_colours: dict | None = None) -> None:
        config_path = THEMES_DIR / f"{theme_name}_config.json"
        qss_path = THEMES_DIR / f"{theme_name}.qss"
        cls._current_config = json.loads(config_path.read_text())
        cls._custom_colours = custom_colours or {}
        app.setStyleSheet(qss_path.read_text())

    @classmethod
    def get_status_colour(cls, status: str) -> dict:
        if status in cls._custom_colours:
            return cls._custom_colours[status]
        return cls._current_config.get("status_colours", {}).get(
            status, {"background": "#888888", "text": "#ffffff", "bold": False}
        )

    @classmethod
    def available_themes(cls) -> list[str]:
        return ["dark", "light"]
