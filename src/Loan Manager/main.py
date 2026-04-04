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

from pathlib import Path  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402  (after logging setup)
from ui.main_window import MainWindow  # noqa: E402


def _seed_on_startup() -> None:
    """R7: Seed sample data if loans.csv is absent or empty."""
    try:
        from data.seed import seed_sample_data
        base = Path(__file__).parent / "data"
        loans_path = base / "loans.csv"
        meta_path = base / "loans_meta.csv"
        seeded = seed_sample_data(loans_path, meta_path)
        if seeded:
            import logging
            logging.getLogger(__name__).info(
                "Application started with sample data loaded for demo purposes."
            )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Seed on startup failed: %s", exc)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Loan Manager")
    app.setOrganizationName("FinHive")

    _seed_on_startup()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
