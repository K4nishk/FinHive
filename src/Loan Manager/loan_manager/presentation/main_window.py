from PySide6.QtWidgets import QMainWindow, QTabWidget, QStatusBar

from loan_manager.presentation.tabs.entry_tab import EntryTab
from loan_manager.presentation.tabs.view_tab import ViewTab
from loan_manager.presentation.tabs.calculator_tab import CalculatorTab
from loan_manager.presentation.tabs.pending_approval_tab import PendingApprovalTab
from loan_manager.presentation.tabs.settings_tab import SettingsTab
from loan_manager.presentation.themes.theme_manager import ThemeManager


class MainWindow(QMainWindow):
    def __init__(self, container, theme_manager):
        super().__init__()
        self.setWindowTitle("Loan Manager")
        self.setMinimumSize(1200, 700)
        self._container = container
        self._theme = theme_manager

        self._tabs = QTabWidget()
        self._entry_tab = EntryTab(container, self)
        self._view_tab = ViewTab(container, theme_manager, self)
        self._calc_tab = CalculatorTab(container, self)
        self._approval_tab = PendingApprovalTab(container, self)
        self._settings_tab = SettingsTab(container, theme_manager, self)

        self._tabs.addTab(self._entry_tab, "Entry")
        self._tabs.addTab(self._view_tab, "View")
        self._tabs.addTab(self._calc_tab, "Calculator")
        self._tabs.addTab(self._approval_tab, "Pending Approval")
        self._tabs.addTab(self._settings_tab, "Settings")

        self.setCentralWidget(self._tabs)
        self.setStatusBar(QStatusBar())

    def show_status(self, message: str, timeout: int = 5000) -> None:
        self.statusBar().showMessage(message, timeout)
