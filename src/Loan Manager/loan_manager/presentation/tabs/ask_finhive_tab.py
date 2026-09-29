"""KCH-241: the Ask FinHive tab.

A question box, a live reasoning trace (tokens, not names), the answer and the
loans the answer was about. The turn runs on an `AgentWorker` thread; this
module only renders. It holds no business logic: the loop, tokenisation and
tool dispatch live in `RunAgentTurn`, and the loan rows come from the existing
`GetAllLoans` use case.

Every failure renders FIXED text from `OUTCOME_TEXT`. Neither `result.text` nor
a FINAL event's text is shown unless the turn was ANSWERED, and no exception
message is ever displayed: those strings can carry a name or an amount.
"""
from __future__ import annotations

import contextlib
import logging
import os
import time

from PySide6.QtCore import QElapsedTimer, QSortFilterProxyModel, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from loan_manager.application.agent.trace import TraceEvent, TurnOutcome
from loan_manager.application.use_cases.agent.run_agent_turn import MAX_STEPS
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.infrastructure.logging.logger import get_logger
from loan_manager.presentation.widgets.loan_table_model import LoanTableModel
from loan_manager.presentation.widgets.trace_model import TraceModel
from loan_manager.presentation.workers.agent_worker import AgentWorker, WorkerResult

NOTE_NPI = (
    "Don't type UPI IDs, e-mail addresses or phone numbers — they are not "
    "recognised as private and could be sent to the AI service as typed."
)
NOTE_DIGIT_GLUED = (
    "Keep names apart from numbers and codes: write 'anil sharma 2026', not "
    "'anilsharma2026', and 'b1 ji', not 'b1ji'. A name joined to digits, or 'ji' "
    "joined to a code, is not recognised and could be sent as typed."
)
TRACE_LEGEND = "Names and amounts appear as codes such as B001, AMOUNT_1"

NOT_CONFIGURED_TEXT = (
    "Ask FinHive is not set up yet: the AI service key is missing. Set the "
    "environment variable named by api_key_env in data/settings.json "
    "(OPENROUTER_API_KEY by default), then restart the app."
)
LOAN_LOOKUP_FAILED_TEXT = "The loans behind this answer could not be loaded."
GENERIC_FAILURE_TEXT = "Something went wrong while answering. Please try again."

# One fixed line per non-ANSWERED outcome. Never the model's or an exception's
# words: see the module docstring.
OUTCOME_TEXT: dict[TurnOutcome, str] = {
    TurnOutcome.BUDGET_EXHAUSTED: (
        f"I could not finish within {MAX_STEPS} steps. Please ask a narrower question."
    ),
    TurnOutcome.VALIDATION_EXHAUSTED: (
        "I could not form a valid request for that. Please rephrase the question."
    ),
    TurnOutcome.INCOMPLETE_ANSWER: "The answer came back incomplete. Please ask again.",
    TurnOutcome.BLOCKED_PLAINTEXT: (
        "I stopped before sending the next request: it or an answer contained "
        "data that must not leave this machine. Please rephrase and ask again."
    ),
    TurnOutcome.UNKNOWN_TOKEN: (
        "Codes such as B001 or AMOUNT_1 cannot be typed. Please rewrite the "
        "question without them."
    ),
    TurnOutcome.CONVERSATION_FULL: (
        "This conversation has reached its limit. Press New conversation to continue."
    ),
    TurnOutcome.LLM_ERROR: "The assistant is unavailable right now. Please try again.",
    TurnOutcome.INTERNAL_ERROR: GENERIC_FAILURE_TEXT,
}

logger = get_logger(__name__)

# A worker still running when the window closes is detached, never destroyed
# (destroying a running QThread aborts the process). Held here until finished.
_DETACHED_WORKERS: set[AgentWorker] = set()


_SHUTDOWN_WAIT_MS = 2000  # closeEvent: how long to wait before detaching
_QUIT_WAIT_MS = 5000  # aboutToQuit: total budget for detached turns
_quit_hooked = False


def _wait_for_detached_workers() -> None:
    """On `aboutToQuit`: a still-running QThread must not be destroyed by
    interpreter finalisation (qFatal, exit 134). Give the detached turns
    `_QUIT_WAIT_MS` in total; if one is still running, flush the logs and end
    the process. That is safe: SQLite runs in WAL, so a write transaction the
    turn had open is rolled back atomically, and the turn holds nothing else.
    """
    deadline = time.monotonic() + _QUIT_WAIT_MS / 1000
    for worker in list(_DETACHED_WORKERS):
        worker.wait(max(0, int((deadline - time.monotonic()) * 1000)))
    if any(worker.isRunning() for worker in _DETACHED_WORKERS):
        logging.shutdown()
        os._exit(0)


def _hook_quit() -> None:
    global _quit_hooked
    app = QApplication.instance()
    if app is not None and not _quit_hooked:
        app.aboutToQuit.connect(_wait_for_detached_workers)
        _quit_hooked = True


class AskFinHiveTab(QWidget):
    proposals_queued = Signal(int)

    def __init__(self, container, theme_manager, parent=None) -> None:
        super().__init__(parent)
        self._container = container
        self._theme = theme_manager
        self._conversation = None
        self._run_turn = None
        self._worker: AgentWorker | None = None
        self._busy = False
        self._step = 0
        self._elapsed = QElapsedTimer()
        self._tick = QTimer(self)
        self._tick.setInterval(500)
        self._tick.timeout.connect(self._update_status)
        self._setup_ui()
        _hook_quit()

    # ── layout ────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Ask about your loans, e.g. what is overdue?")
        self._input.setAccessibleName("Ask FinHive question")
        self._input.returnPressed.connect(self._on_ask)
        row.addWidget(self._input, 1)
        self._ask_btn = QPushButton("Ask")
        self._ask_btn.setAccessibleName("Ask FinHive")
        self._ask_btn.clicked.connect(self._on_ask)
        row.addWidget(self._ask_btn)
        self._new_btn = QPushButton("New conversation")
        self._new_btn.setAccessibleName("Start a new conversation")
        self._new_btn.clicked.connect(self._on_new_conversation)
        row.addWidget(self._new_btn)
        layout.addLayout(row)

        self._note_npi = self._note(NOTE_NPI)
        self._note_glued = self._note(NOTE_DIGIT_GLUED)
        layout.addWidget(self._note_npi)
        layout.addWidget(self._note_glued)

        self._status = QLabel("")
        self._status.setAccessibleName("Ask FinHive progress")
        layout.addWidget(self._status)

        self._answer = QLabel("")
        self._answer.setObjectName("askFinhiveAnswer")
        self._answer.setWordWrap(True)
        self._answer.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._answer.setAccessibleName("Ask FinHive answer")
        layout.addWidget(self._answer)

        self._legend = self._note(TRACE_LEGEND)
        layout.addWidget(self._legend)

        self._trace_model = TraceModel(self._theme, self)
        self._trace_view = QTreeView()
        self._trace_view.setModel(self._trace_model)
        self._trace_view.setUniformRowHeights(True)
        self._trace_view.setAccessibleName("Reasoning trace")
        self._trace_view.setColumnWidth(0, 130)
        self._trace_view.setColumnWidth(1, 150)
        self._trace_model.rowsInserted.connect(self._trace_view.expandAll)

        self._loan_model = LoanTableModel(self._theme)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._loan_model)
        self._table = QTableView()
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(True)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.setAccessibleName("Loans in the answer")

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._trace_view)
        splitter.addWidget(self._table)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self._set_busy(False)

    @staticmethod
    def _note(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("askFinhiveNote")
        label.setWordWrap(True)
        return label

    # ── state ─────────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._input.setEnabled(not busy)
        self._ask_btn.setEnabled(not busy)
        self._new_btn.setEnabled(not busy)
        if busy:
            self._elapsed.start()
            self._tick.start()
        else:
            self._tick.stop()

    def _update_status(self) -> None:
        seconds = self._elapsed.elapsed() // 1000 if self._elapsed.isValid() else 0
        self._status.setText(f"Step {self._step} / {MAX_STEPS} · elapsed {seconds}s")

    def _clear_views(self) -> None:
        self._trace_model.clear()
        self._loan_model.load([])
        self._answer.setText("")
        self._status.setText("")
        self._step = 0

    # ── actions ───────────────────────────────────────────────────────────

    def _on_ask(self) -> None:
        text = self._input.text().strip()
        if self._busy or not text:
            return
        self._clear_views()
        worker = AgentWorker(self._container, self._conversation, self._run_turn, text)
        self._worker = worker
        worker.event.connect(self._on_event)
        worker.done.connect(self._on_done)
        worker.finished.connect(self._on_finished)
        self._set_busy(True)
        self._update_status()
        worker.start()

    def _on_new_conversation(self) -> None:
        if self._busy:
            return
        self._conversation = None  # keep the cached RunAgentTurn: same LLM client
        self._clear_views()

    def _on_event(self, event: TraceEvent) -> None:
        self._trace_model.append(event)
        self._step = max(self._step, event.step)
        self._update_status()

    def _on_done(self, result: WorkerResult) -> None:
        if result.run_turn is not None:
            self._run_turn = result.run_turn
        # An INTERNAL_ERROR turn may already have stored an answer the user
        # never saw (recorder failure): the next ask must not continue from it.
        if result.outcome is TurnOutcome.INTERNAL_ERROR:
            self._conversation = None
        elif result.conversation is not None:
            self._conversation = result.conversation

        if result.not_configured:
            text = NOT_CONFIGURED_TEXT
        elif result.outcome is TurnOutcome.ANSWERED:
            text = result.text
        else:
            text = OUTCOME_TEXT.get(result.outcome, GENERIC_FAILURE_TEXT)
        if result.proposals:
            text += (
                f"\n{result.proposals} draft proposal(s) queued for approval — "
                "review them in the Pending Approval tab."
            )
        self._answer.setText(text)
        answered = result.outcome is TurnOutcome.ANSWERED and not result.not_configured
        # a failed turn's partial query is not an answer: show no rows
        if answered and not self._hydrate_table():
            self._answer.setText(f"{text}\n{LOAN_LOOKUP_FAILED_TEXT}")
        if result.proposals:
            self.proposals_queued.emit(result.proposals)

    def _on_finished(self) -> None:
        worker, self._worker = self._worker, None
        self._set_busy(False)
        self._update_status()
        if worker is not None:
            worker.deleteLater()

    def _hydrate_table(self) -> bool:
        """Rows of the LAST successful query_loans observation, read through
        the existing use case (not the trace: the trace holds tokens).

        Not `surfacing_storage_errors`: that helper logs the full exception,
        and a decrypted-row error can carry an amount. Type name only here.
        Returns False when the read failed."""
        ref_ids = set(self._trace_model.last_ref_ids())
        loans = []
        ok = True
        if ref_ids:
            try:
                all_loans = GetAllLoans(
                    self._container.get_uow, clock=self._container.clock
                ).execute()
                loans = [loan for loan in all_loans if loan.reference_id in ref_ids]
            except Exception as exc:
                logger.error("Ask FinHive loan lookup failed: %s", type(exc).__name__)
                ok = False
        self._loan_model.load(loans)
        return ok

    # ── shutdown ──────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        """Called from the window's closeEvent. Give a running turn 2s to end;
        past that, detach the thread rather than destroy it."""
        worker = self._worker
        if worker is None or not worker.isRunning():
            return
        if worker.wait(_SHUTDOWN_WAIT_MS):
            return
        for signal in (worker.event, worker.done, worker.finished):
            with contextlib.suppress(RuntimeError, TypeError):
                signal.disconnect()
        worker.setParent(None)
        _DETACHED_WORKERS.add(worker)
        worker.finished.connect(lambda w=worker: self._release(w))
        self._worker = None

    @staticmethod
    def _release(worker: AgentWorker) -> None:
        _DETACHED_WORKERS.discard(worker)
        worker.deleteLater()
