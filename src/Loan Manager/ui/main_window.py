"""Main application window."""
import logging
from datetime import date

from PySide6.QtWidgets import QMainWindow, QTabWidget

from data.csv_manager import read_loans, update_loan
from data.status_engine import recompute_all
from ui.entry_tab import EntryTab
from ui.view_tab import ViewTab
from ui.interest_calculator_tab import InterestCalculatorTab
from ui.pending_approval_tab import PendingApprovalTab

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Application main window containing the tab widget."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Loan Manager")
        self.setMinimumSize(1024, 768)
        self._build_ui()
        self._startup_recompute()

    def _build_ui(self) -> None:
        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)

        self._entry_tab = EntryTab()
        self._tabs.addTab(self._entry_tab, "Entry")

        self._view_tab = ViewTab()
        self._tabs.addTab(self._view_tab, "View")

        self._interest_calculator_tab = InterestCalculatorTab()
        self._tabs.addTab(self._interest_calculator_tab, "Interest Calculator")

        self._pending_approval_tab = PendingApprovalTab()
        self._tabs.addTab(self._pending_approval_tab, "Pending Approval")

        # Connect signals
        self._entry_tab.loan_added.connect(self._on_loan_added)
        self._view_tab.data_changed.connect(self._entry_tab.refresh_completers)

        # Cross-tab signal wiring
        self._interest_calculator_tab.report_generated.connect(
            self._pending_approval_tab.load_reports
        )
        self._pending_approval_tab.data_changed.connect(self._view_tab.load_data)
        self._pending_approval_tab.data_changed.connect(
            self._entry_tab.refresh_completers
        )

    def _startup_recompute(self) -> None:
        """On launch: check for stale recovery file, recompute all statuses, refresh view."""
        self._check_recovery_file()

        try:
            loans = read_loans()
            updated = recompute_all(loans, date.today())
            for loan in updated:
                update_loan(loan)
            logger.info("Startup status recompute complete (%d loans)", len(updated))
        except Exception as exc:
            logger.error("Startup recompute failed: %s", exc)

        self._view_tab.load_data()

    def _check_recovery_file(self) -> None:
        """Warn if any recovery.tmp files exist from previous crashed write operations.

        Checks for:
        - recovery.tmp: crashed paidoff operation
        - import_recovery.tmp: crashed import operation (RR-001)
        - approval_recovery.tmp: crashed batch approval operation (RR-003)
        """
        from pathlib import Path
        from PySide6.QtWidgets import QMessageBox

        data_dir = Path(__file__).parent.parent / "data"

        recovery_configs = [
            (
                data_dir / "recovery.tmp",
                "Data Recovery Warning",
                "A previous paidoff operation for loan '{token}' may not have completed.\n\n"
                "Please verify the loan record and history.csv are consistent before continuing.\n\n"
                "If data looks correct, you may safely dismiss this warning.",
            ),
            (
                data_dir / "import_recovery.tmp",
                "Import Recovery Warning",
                "A previous import operation may not have completed.\n\n"
                "Source file: {token}\n\n"
                "Please verify your loan records are consistent before continuing.",
            ),
            (
                data_dir / "approval_recovery.tmp",
                "Approval Recovery Warning",
                "A previous approval for report '{token}' may not have completed.\n\n"
                "Please check if the report status and loan records are consistent before continuing.",
            ),
        ]

        for recovery_path, title, message_template in recovery_configs:
            if recovery_path.exists():
                token = recovery_path.read_text(encoding="utf-8").strip()
                logger.error(
                    "Startup: stale %s detected (token='%s'). "
                    "A previous write may have been interrupted.",
                    recovery_path.name,
                    token,
                )
                QMessageBox.warning(
                    self,
                    title,
                    message_template.format(token=token),
                )

    def _on_loan_added(self) -> None:
        """Refresh view tab and entry tab completers after a new loan entry."""
        self._view_tab.load_data()
        self._entry_tab.refresh_completers()
