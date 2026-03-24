"""Entry point for the Loan Manager application."""
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configure logging before importing PySide6 or app modules
# ---------------------------------------------------------------------------

def _setup_logging() -> None:
    """Set up application logging to ./data/logs/app.log and stderr."""
    log_dir = Path(__file__).parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


_setup_logging()

from PySide6.QtWidgets import QApplication  # noqa: E402  (after logging setup)
from ui.main_window import MainWindow  # noqa: E402


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Loan Manager")
    app.setOrganizationName("FinHive")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
