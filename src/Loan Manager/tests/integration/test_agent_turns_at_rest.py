"""KCH-240: no NPI from an Ask FinHive turn reaches disk in the clear.

Scans the raw main file, `-wal` and `-journal` (same helpers and same method
as `test_encryption_at_rest.py`: a raw byte scan sees freed pages and old WAL
frames that a SELECT never would). `-shm` is NOT scanned: it is the WAL
*index* (frame numbers and checksums), never page content.

The rows are written ONLY by `SqlAlchemyTurnRecorder`, never a raw INSERT.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from loan_manager.application.agent.llm_port import Completion, ToolCall, Usage
from loan_manager.application.agent.trace import TraceEvent, TraceKind, TurnOutcome
from loan_manager.application.interfaces.turn_recorder import TurnRecord
from loan_manager.application.use_cases.agent.run_agent_turn import RunAgentTurn
from loan_manager.infrastructure.database.models import AgentTurnModel, Base
from loan_manager.infrastructure.repositories.sqlalchemy_turn_recorder import (
    SqlAlchemyTurnRecorder,
)
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from tests.integration.test_encryption_at_rest import (
    _amount_needles,
    _assert_no_needles,
    _haystacks,
    _string_needles,
    needs_crypto,
)
from tests.unit.application.agent.test_run_agent_turn import _no_propose, _rec, make_rig

pytestmark = needs_crypto

USER_TEXT = "extend Anil Kumar's ₹1,50,000 loan"
FINAL_TEXT = "Anil Kumar's loan of ₹1,50,000 is overdue"
NAMES = ["Anil Kumar"]
AMOUNTS = [150000]


def _needles() -> list[bytes]:
    out: list[bytes] = []
    for name in NAMES:
        out += _string_needles(name)
    for amount in AMOUNTS:
        out += _amount_needles(amount)
    out += [b"1,50,000", "₹".encode()]
    return out


@pytest.fixture()
def wal_db(tmp_path):
    path = tmp_path / "turns.db"
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _rec):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA wal_autocheckpoint=0")
        cur.close()

    keepalive = engine.connect()  # keeps the WAL from being checkpointed away
    Base.metadata.create_all(engine)
    yield path, engine, sessionmaker(bind=engine, expire_on_commit=False)
    keepalive.close()
    engine.dispose()


def _completion(content: str, calls=()) -> Completion:
    return Completion(
        content=content, tool_calls=tuple(calls), finish_reason="stop", model="m/x",
        usage=Usage(prompt_tokens=5, completion_tokens=2, latency_ms=1.0,
                    cost_usd=None, price_version=None),
    )


def _fixture_record() -> TurnRecord:
    return TurnRecord(
        conversation_id="conv-1", turn_id="turn-1", prompt_version="pv", user_text=USER_TEXT,
        outcome=TurnOutcome.ANSWERED, step_count=1,
        events=(
            TraceEvent(TraceKind.THOUGHT, 1, 6, text="looking at Anil Kumar"),
            TraceEvent(TraceKind.ACTION, 1, 6, text='{"amount": 150000}', tool="query_loans"),
            TraceEvent(TraceKind.FINAL, 1, 6, text=FINAL_TEXT, outcome=TurnOutcome.ANSWERED),
        ),
        completions=(_completion("looking at Anil Kumar",
                                 [ToolCall("c1", "query_loans", '{"amount": 150000}')]),),
        latency_ms=10,
    )


def _assert_wal_written(path: Path) -> None:
    wal = Path(str(path) + "-wal")
    assert wal.exists() and wal.stat().st_size > 0, "no WAL content: the scan would prove nothing"


def test_no_plaintext_name_or_amount_in_db_wal_or_journal(wal_db) -> None:
    path, engine, factory = wal_db
    recorder = SqlAlchemyTurnRecorder(factory)

    recorder.record(_fixture_record())

    assert recorder.failure_count == 0
    _assert_wal_written(path)
    haystack = _haystacks(path)
    _assert_no_needles(haystack, _needles(), label="agent_turns")

    # Positive control: the same scan DOES find the same values when they are
    # written in the clear, so the assertion above is capable of failing.
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE plain_control (t TEXT)")
        conn.exec_driver_sql("INSERT INTO plain_control VALUES (?)", (USER_TEXT,))
    controlled = _haystacks(path)
    assert any(n in controlled for n in _needles())


def test_a_full_agent_turn_leaves_no_plaintext_on_disk(wal_db) -> None:
    path, engine, factory = wal_db
    rig = make_rig([
        _rec("checking Q001", calls=[("c1", "get_current_context", {})]),
        _rec("Q001's loan of AMOUNT_1 is overdue"),
    ])
    recorder = SqlAlchemyTurnRecorder(factory)
    uc = RunAgentTurn(rig.llm, rig.uc._read_registry, _no_propose, recorder=recorder,
                      new_id=lambda: "turn-e2e")

    result = uc.execute(rig.conv, USER_TEXT)

    assert result.outcome is TurnOutcome.ANSWERED
    assert result.text == "Anil Kumar's loan of ₹1,50,000.00 is overdue"  # rehydrated
    assert recorder.failure_count == 0
    _assert_wal_written(path)
    _assert_no_needles(_haystacks(path), _needles(), label="agent_turns e2e")
    with factory() as s:  # ...and it is really there, decryptable
        row = s.get(AgentTurnModel, "turn-e2e")
        assert row.user_message == USER_TEXT
        assert row.react_trace["events"][-1]["text"] == result.text
