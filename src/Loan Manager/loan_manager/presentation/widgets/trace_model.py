"""KCH-241: tree model for the Ask FinHive reasoning trace.

Two levels: one top-level row per model step ("Step n / max") holding that
step's THOUGHT / ACTION / OBSERVATION / PROPOSAL events, plus a single
top-level "Answer" row for the FINAL event.

The trace shows TOKENS (B001, AMOUNT_1), exactly what the model saw: no local
rehydration. The FINAL row shows the outcome label only, never `event.text`:
on a failure that text is fixed, but on success it is the rehydrated answer,
and the answer belongs in the answer label, not in a debug feed.
"""
from __future__ import annotations

import json
from typing import Any

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtGui import QBrush

from loan_manager.application.agent.trace import TraceEvent, TraceKind, TurnOutcome

COLUMNS = ["Kind", "Tool", "Detail"]
DETAIL_LIMIT = 200
PROPOSAL_TEXT = "Draft queued for approval — review it in the Pending Approval tab"

_KIND_LABEL = {
    TraceKind.THOUGHT: "Thought",
    TraceKind.ACTION: "Action",
    TraceKind.OBSERVATION: "Observation",
    TraceKind.PROPOSAL: "Proposal",
    TraceKind.FINAL: "Answer",
}

OUTCOME_LABEL = {
    TurnOutcome.ANSWERED: "Answered",
    TurnOutcome.BUDGET_EXHAUSTED: "Stopped: step limit reached",
    TurnOutcome.VALIDATION_EXHAUSTED: "Stopped: invalid requests",
    TurnOutcome.INCOMPLETE_ANSWER: "Stopped: incomplete answer",
    TurnOutcome.BLOCKED_PLAINTEXT: "Stopped: private data blocked",
    TurnOutcome.UNKNOWN_TOKEN: "Stopped: unknown code typed",
    TurnOutcome.PROMPT_TOO_LONG: "Stopped: question too long",
    TurnOutcome.CONVERSATION_FULL: "Stopped: conversation full",
    TurnOutcome.LLM_ERROR: "Stopped: assistant unavailable",
    TurnOutcome.LLM_UNREACHABLE: "Stopped: AI server unreachable",
    TurnOutcome.LLM_BUSY: "Stopped: AI server busy",
    TurnOutcome.CANCELLED: "Stopped by you",
    TurnOutcome.INTERNAL_ERROR: "Stopped: internal error",
}


class _Node:
    __slots__ = ("parent", "children", "event", "label")

    def __init__(
        self, parent: _Node | None, event: TraceEvent | None = None, label: str = ""
    ) -> None:
        self.parent = parent
        self.children: list[_Node] = []
        self.event = event
        self.label = label

    def row(self) -> int:
        return self.parent.children.index(self) if self.parent else 0


def _compact(payload: dict[str, Any] | None) -> str:
    return json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":"), default=str)


def _outcome_label(outcome: TurnOutcome | None) -> str:
    return OUTCOME_LABEL.get(outcome, "Stopped") if outcome else "Stopped"


class TraceModel(QAbstractItemModel):
    def __init__(self, theme_manager, parent=None) -> None:
        super().__init__(parent)
        self._theme = theme_manager
        self._root = _Node(None)
        self._steps: dict[int, _Node] = {}
        self._proposals = 0
        self._ref_ids: list[str] = []

    # ── mutation ──────────────────────────────────────────────────────────

    def append(self, event: TraceEvent) -> None:
        if event.kind is TraceKind.FINAL:
            self._drop_final()  # a later FINAL (a failure after an answer) is the truth
            parent = self._root
            node = _Node(parent, event, "Answer")
        else:
            parent = self._step_node(event)
            node = _Node(parent, event)
        parent_index = self._index_of(parent)
        row = len(parent.children)
        self.beginInsertRows(parent_index, row, row)
        parent.children.append(node)
        self.endInsertRows()
        self._track(event)

    def _drop_final(self) -> None:
        for row, node in enumerate(self._root.children):
            if node.event is not None and node.event.kind is TraceKind.FINAL:
                self.beginRemoveRows(QModelIndex(), row, row)
                del self._root.children[row]
                self.endRemoveRows()
                return

    def _step_node(self, event: TraceEvent) -> _Node:
        step = self._steps.get(event.step)
        if step is None:
            step = _Node(self._root, None, f"Step {event.step} / {event.max_steps}")
            row = len(self._root.children)
            self.beginInsertRows(QModelIndex(), row, row)
            self._root.children.append(step)
            self.endInsertRows()
            self._steps[event.step] = step
        return step

    def _track(self, event: TraceEvent) -> None:
        if event.kind is TraceKind.PROPOSAL:
            self._proposals += 1
        elif (
            event.kind is TraceKind.OBSERVATION
            and event.tool == "query_loans"
            and isinstance(event.payload, dict)
            and event.payload.get("ok") is True
            and isinstance(event.payload.get("ref_ids"), list)
        ):
            self._ref_ids = [str(r) for r in event.payload["ref_ids"]]

    def clear(self) -> None:
        self.beginResetModel()
        self._root = _Node(None)
        self._steps = {}
        self._proposals = 0
        self._ref_ids = []
        self.endResetModel()

    # ── queries ───────────────────────────────────────────────────────────

    def proposal_count(self) -> int:
        return self._proposals

    def last_ref_ids(self) -> list[str]:
        return list(self._ref_ids)

    def _index_of(self, node: _Node) -> QModelIndex:
        if node is self._root:
            return QModelIndex()
        return self.createIndex(node.row(), 0, node)

    # ── QAbstractItemModel ────────────────────────────────────────────────

    def index(self, row, column, parent=QModelIndex()) -> QModelIndex:  # noqa: B008
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parent_node = parent.internalPointer() if parent.isValid() else self._root
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index=QModelIndex()) -> QModelIndex:  # noqa: B008
        if not index.isValid():
            return QModelIndex()
        parent_node = index.internalPointer().parent
        if parent_node is None or parent_node is self._root:
            return QModelIndex()
        return self.createIndex(parent_node.row(), 0, parent_node)

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        if parent.column() > 0:
            return 0
        node = parent.internalPointer() if parent.isValid() else self._root
        return len(node.children)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: B008
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        node: _Node = index.internalPointer()
        column = index.column()
        event = node.event
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(node, event, column)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(event, column)
        if role == Qt.ItemDataRole.ForegroundRole and event is not None:
            return self._foreground(event)
        return None

    # ── rendering ─────────────────────────────────────────────────────────

    def _display(self, node: _Node, event: TraceEvent | None, column: int) -> str:
        if event is None:  # a "Step n / max" row
            return node.label if column == 0 else ""
        if column == 0:
            return _KIND_LABEL[event.kind]
        if column == 1:
            return event.tool or ""
        return self._detail(event, full=False)

    def _detail(self, event: TraceEvent, *, full: bool) -> str:
        kind = event.kind
        if kind is TraceKind.FINAL:
            return _outcome_label(event.outcome)  # never event.text
        if kind is TraceKind.PROPOSAL:
            return PROPOSAL_TEXT
        if kind is TraceKind.OBSERVATION:
            text = _compact(event.payload)
            if not full and len(text) > DETAIL_LIMIT:
                return text[: DETAIL_LIMIT - 1] + "…"
            return text
        return event.text  # THOUGHT / ACTION: tokenised by the loop already

    def _tooltip(self, event: TraceEvent | None, column: int) -> str | None:
        if event is None or column != 2:
            return None
        return self._detail(event, full=True)

    def _foreground(self, event: TraceEvent) -> QBrush | None:
        if event.kind is TraceKind.FINAL and event.outcome is not TurnOutcome.ANSWERED:
            key = "error"
        else:
            key = event.kind.value
        colour = self._theme.get_trace_colour(key)
        return QBrush(colour) if colour is not None else None
