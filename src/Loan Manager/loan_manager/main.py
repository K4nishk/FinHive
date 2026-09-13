"""
Application entry point.
Startup sequence:
1. Setup logging
2. Check for approval_recovery.tmp
3. Initialize database (create tables)
4. Launch UI (Stage 5)
"""
import logging
import sys

from loan_manager.infrastructure.logging.logger import setup_logging, get_logger
from loan_manager.infrastructure.database.session import DatabaseSession
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
from loan_manager.container import Container

logger = get_logger(__name__)


def main() -> None:
    setup_logging()
    logger.info("Loan Manager starting up")

    # Step 1: Check for crash recovery file
    recovery = RecoveryService()
    if recovery.exists():
        logger.warning(
            "approval_recovery.tmp detected — an approval was in progress when the app last closed. "
            "Please check the Pending Approval queue and verify loan records."
        )
        print(
            "\nWARNING: An approval was in progress when the application last closed. "
            "Please check the Pending Approval queue and verify loan records.\n"
        )

    # Step 2: Initialize database
    DatabaseSession.initialize()
    logger.info("Database initialized")

    # Step 3: Wire container
    container = Container()
    logger.info("Container initialized")

    # Step 4: Recompute statuses on launch
    from loan_manager.application.use_cases.loans.recompute_statuses import RecomputeAllStatuses
    recompute = RecomputeAllStatuses(container.get_uow)
    updated = recompute.execute()
    logger.info(f"Recomputed statuses for {updated} loans")

    # Step 5: Launch UI
    from PySide6.QtWidgets import QApplication
    from loan_manager.presentation.main_window import MainWindow
    from loan_manager.presentation.themes.theme_manager import ThemeManager

    app = QApplication(sys.argv)

    saved_theme = _load_saved_theme()
    custom_colours = _load_custom_colours()
    ThemeManager.apply_theme(saved_theme, app, custom_colours or None)

    window = MainWindow(container, ThemeManager)
    window.show()
    sys.exit(app.exec())


def _load_saved_theme() -> str:
    import json
    from loan_manager.config import SETTINGS_FILE
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text()).get("theme", "dark")
        except Exception:
            pass
    return "dark"


def _load_custom_colours() -> dict:
    import json
    from loan_manager.config import SETTINGS_FILE
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text()).get("custom_colours", {})
        except Exception:
            pass
    return {}


if __name__ == "__main__":
    main()
