"""KCH-240: `SqlAlchemyTurnRecorder` persists one Ask FinHive turn to
`agent_turns`, encrypted, and never raises.

In-memory SQLite (StaticPool so the recorder's own sessions share one
database). The on-disk / WAL scan lives in
`tests/integration/test_agent_turns_at_rest.py`.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from loan_manager.application.agent.llm_port import Completion, ToolCall, Usage
from loan_manager.application.agent.trace import TraceEvent, TraceKind, TurnOutcome
from loan_manager.application.interfaces.turn_recorder import TurnRecord
from loan_manager.infrastructure.database.models import AgentTurnModel, Base, ReportMetaModel
from loan_manager.infrastructure.database.session import DatabaseSession
from loan_manager.infrastructure.repositories.sqlalchemy_turn_recorder import (
    SqlAlchemyTurnRecorder,
    _trace_json,
)
from loan_manager.infrastructure.security.key_provider import set_active_key_ring
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from finhive.db.keys import KeyRing

USER_TEXT = "extend Anil Kumar's ₹1,50,000 loan"
FINAL_TEXT = "Anil Kumar's loan of ₹1,50,000 is overdue"
NOW = datetime(2026, 9, 29, 10, 30, tzinfo=timezone.utc)


def _usage(pt=100, ct=10, cost: Decimal | None = Decimal("0.000123")) -> Usage:
    return Usage(prompt_tokens=pt, completion_tokens=ct, latency_ms=1.0,
                 cost_usd=cost, price_version=None)


def _completion(usage: Usage | None = None, *, calls=(), content="thinking about Anil Kumar",
                finish="tool_calls", model="m/one") -> Completion:
    return Completion(content=content, tool_calls=tuple(calls), finish_reason=finish,
                      model=model, usage=usage or _usage())


def _record(completions=None, latency_ms: int | None = 250, turn_id="turn-1") -> TurnRecord:
    if completions is None:
        completions = (
            _completion(calls=[ToolCall("c1", "query_loans", '{"amount": 150000}')]),
            _completion(content="done", finish="stop", model="m/two"),
        )
    events = (
        TraceEvent(TraceKind.THOUGHT, 1, 6, text="checking Anil Kumar"),
        TraceEvent(TraceKind.ACTION, 1, 6, text='{"amount": 150000}', tool="query_loans"),
        TraceEvent(TraceKind.OBSERVATION, 1, 6, tool="query_loans",
                   payload={"ok": True, "rows": [{"ref_id": "2026_03_004", "due": "2026-04-01"}]}),
        TraceEvent(TraceKind.FINAL, 2, 6, text=FINAL_TEXT, outcome=TurnOutcome.ANSWERED),
    )
    return TurnRecord(
        conversation_id="conv-1", turn_id=turn_id, prompt_version="pv-1", user_text=USER_TEXT,
        outcome=TurnOutcome.ANSWERED, step_count=2, events=events,
        completions=tuple(completions), latency_ms=latency_ms,
    )


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://", poolclass=StaticPool,
                        connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture()
def recorder(factory):
    return SqlAlchemyTurnRecorder(factory, now=lambda: NOW)


def _row(factory) -> AgentTurnModel:
    with factory() as s:
        return s.query(AgentTurnModel).one()


def test_round_trip_user_message_and_final_event(recorder, factory) -> None:
    recorder.record(_record())
    row = _row(factory)
    assert row.id == "turn-1" and row.conversation_id == "conv-1"
    assert row.user_message == USER_TEXT
    final = row.react_trace["events"][-1]
    assert final["kind"] == "final"
    assert final["text"] == FINAL_TEXT
    assert final["outcome"] == "answered"
    assert row.outcome == "answered" and row.step_count == 2
    assert row.prompt_version == "pv-1"
    assert row.created_at == datetime(2026, 9, 29, 10, 30)
    assert recorder.failure_count == 0


def _sql_columns(sql_file: Path, table: str) -> set[str]:
    body = re.search(rf"CREATE TABLE {table} \((.*?)\n\);", sql_file.read_text(), re.S).group(1)
    return {
        m.group(1)
        for line in body.splitlines()
        if (m := re.match(r"\s+([a-z_]+)\s+[A-Z]", line))
    }


def _migration_0005() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "migrations" / "0005_create_audit_tables.sql"
        if candidate.exists():
            return candidate
    pytest.skip("migrations/0005_create_audit_tables.sql not found from this checkout")


def test_model_mirrors_0005_agent_turns_column_names() -> None:
    sql_cols = _sql_columns(_migration_0005(), "agent_turns")
    assert {"latency_ms", "react_trace_ct", "cost_usd", "feedback"} <= sql_cols
    expected = (sql_cols - {"org_id", "user_id", "user_message"}) | {"user_message_ct"}
    model_cols = {c.name for c in AgentTurnModel.__table__.columns}
    assert expected <= model_cols


def test_no_org_or_user_column_d16() -> None:
    model_cols = {c.name for c in AgentTurnModel.__table__.columns}
    assert model_cols.isdisjoint({"org_id", "user_id"})


def test_no_blind_index_column() -> None:
    assert not [c.name for c in AgentTurnModel.__table__.columns if c.name.endswith("_bidx")]


def test_raw_columns_are_ciphertext_bytes(recorder, engine) -> None:
    recorder.record(_record())
    with engine.connect() as conn:
        raw = conn.exec_driver_sql(
            "SELECT user_message_ct, react_trace_ct FROM agent_turns"
        ).one()
    for blob in raw:
        assert isinstance(blob, bytes)
        for needle in (b"Anil", b"150000", "₹".encode(), b"1,50,000", b"final"):
            assert needle not in blob


def test_eval_scores_persisted_encrypted_with_grounding_shape(recorder, factory, engine) -> None:
    recorder.record(_record())
    row = _row(factory)
    assert row.eval_scores == {
        "grounding_version": "1", "faithfulness_proxy": "1.0000", "facts_total": 0,
        "facts_unsupported": 0, "unsupported_kinds": [], "raw_money_leak": False,
        "context_precision_proxy": None, "trace_relevancy_proxy": None,
    }
    with engine.connect() as conn:
        raw = conn.exec_driver_sql("SELECT eval_scores_ct FROM agent_turns").scalar_one()
    assert isinstance(raw, bytes) and b"faithfulness" not in raw


def test_eval_scores_count_unsupported_facts_from_this_turn(recorder, factory) -> None:
    done = _completion(content="2 loans: 2026_03_004 and 2026_03_099", finish="stop")
    recorder.record(_record(completions=(done,)))
    scores = _row(factory).eval_scores
    assert (scores["facts_total"], scores["facts_unsupported"]) == (3, 2)
    assert scores["faithfulness_proxy"] == "0.3333"
    assert scores["unsupported_kinds"] == ["count", "ref_id"]


def test_scoring_bug_leaves_eval_scores_none_but_writes_the_row(
    recorder, factory, monkeypatch, caplog
) -> None:
    import loan_manager.infrastructure.repositories.sqlalchemy_turn_recorder as mod

    def boom(events, completions):
        raise KeyError("Anil Kumar")

    monkeypatch.setattr(mod, "production_scores", boom)
    with caplog.at_level(logging.WARNING):
        recorder.record(_record())
    row = _row(factory)
    assert row.eval_scores is None and row.user_message == USER_TEXT
    assert recorder.failure_count == 0
    assert "KeyError" in caplog.text and "Anil" not in caplog.text


def test_blocked_plaintext_turn_records_raw_money_leak(recorder, factory) -> None:
    leaked = _completion(content="Anil Kumar owes ₹1,50,000", finish="stop")
    base = _record(completions=(leaked,))
    recorder.record(TurnRecord(**{**base.__dict__, "outcome": TurnOutcome.BLOCKED_PLAINTEXT}))
    row = _row(factory)
    assert row.outcome == "blocked_plaintext"
    assert row.eval_scores["raw_money_leak"] is True
    assert "150000" not in json.dumps(row.eval_scores)


def test_recorder_failure_is_swallowed_counted_and_logged_without_npi(caplog, factory) -> None:
    def broken():
        raise OperationalError("INSERT ...", {}, Exception("disk I/O error near Anil Kumar"))

    rec = SqlAlchemyTurnRecorder(broken, now=lambda: NOW)
    with caplog.at_level(logging.WARNING):
        assert rec.record(_record()) is None
        assert rec.failure_count == 1
        # DatabaseSession uninitialised -> RuntimeError from get_session.
        saved = (DatabaseSession._engine, DatabaseSession._SessionLocal)
        DatabaseSession._engine, DatabaseSession._SessionLocal = None, None
        try:
            uninit = SqlAlchemyTurnRecorder(DatabaseSession.get_session)
            assert uninit.record(_record()) is None
            assert uninit.failure_count == 1
        finally:
            DatabaseSession._engine, DatabaseSession._SessionLocal = saved
    assert "OperationalError" in caplog.text
    assert "Anil" not in caplog.text and "150000" not in caplog.text


def test_commit_failure_rolls_back_and_counts(factory) -> None:
    rec = SqlAlchemyTurnRecorder(factory, now=lambda: NOW)
    rec.record(_record())
    rec.record(_record())  # same PK -> IntegrityError on commit
    assert rec.failure_count == 1
    with factory() as s:
        assert s.query(AgentTurnModel).count() == 1


def test_key_version_is_active_and_old_rows_decrypt_after_rotation(factory) -> None:
    rec = SqlAlchemyTurnRecorder(factory, now=lambda: NOW)
    m1, m2 = b"\x42" * 32, b"\x77" * 32
    set_active_key_ring(KeyRing(current_version=1, masters={1: m1}))
    rec.record(_record(turn_id="old"))
    set_active_key_ring(KeyRing(current_version=2, masters={1: m1, 2: m2}))
    rec.record(_record(turn_id="new"))
    with factory() as s:
        old, new = s.get(AgentTurnModel, "old"), s.get(AgentTurnModel, "new")
        assert (old.key_version, new.key_version) == (1, 2)
        assert old.user_message == USER_TEXT  # v1 blob, v2 active
        assert new.react_trace["events"][-1]["text"] == FINAL_TEXT


def test_no_float_and_every_observation_shape_survives_encryption(recorder, factory) -> None:
    rec = _record()
    trace = _trace_json(rec)

    def no_float(node):
        if isinstance(node, float):
            raise AssertionError("float in trace")
        if isinstance(node, dict):
            [no_float(v) for v in node.values()]
        elif isinstance(node, list):
            [no_float(v) for v in node]

    no_float(trace)
    recorder.record(rec)
    row = _row(factory)
    # cost survives at full precision as text, in the blob and in the column.
    costs = [c["usage"]["cost_usd"] for c in row.react_trace["completions"]]
    assert costs == ["0.000123", "0.000123"]
    assert row.cost_usd == "0.000246"


def test_read_and_propose_observation_shapes_encrypt(recorder, factory) -> None:
    from loan_manager.application.agent.tools.observations import ok

    shapes = [
        ok(count=3, rows=[{"ref_id": "2026_03_004", "amount": "AMOUNT_1", "due": "2026-04-01"}]),
        ok(proposal_id="p-1", report_id="R1", records=2),
        {"ok": False, "error": {"code": "INVALID_ARGS", "message": "x", "hint": "y"}},
    ]
    events = tuple(
        TraceEvent(TraceKind.OBSERVATION, 1, 6, tool="query_loans", payload=p) for p in shapes
    ) + (TraceEvent(TraceKind.FINAL, 1, 6, text="ok", outcome=TurnOutcome.ANSWERED),)
    base = _record()
    recorder.record(TurnRecord(**{**base.__dict__, "events": events}))
    assert recorder.failure_count == 0
    row = _row(factory)
    assert [e["payload"] for e in row.react_trace["events"][:3]] == shapes


def test_token_totals_none_when_any_completion_lacks_usage(recorder, factory) -> None:
    recorder.record(_record(completions=(
        _completion(_usage(100, 10, Decimal("0.5"))),
        _completion(_usage(None, None, None), finish="stop"),
    )))
    row = _row(factory)
    assert (row.prompt_tokens, row.completion_tokens, row.cost_usd) == (None, None, None)


def test_totals_sum_when_every_completion_reports(recorder, factory) -> None:
    recorder.record(_record())
    row = _row(factory)
    assert (row.prompt_tokens, row.completion_tokens) == (200, 20)
    assert row.model == "m/two" and row.finish_reason == "stop"
    assert row.latency_ms == 250


def test_no_completions_means_no_model_and_no_totals(recorder, factory) -> None:
    recorder.record(_record(completions=(), latency_ms=None))
    row = _row(factory)
    assert row.model is None and row.finish_reason is None
    assert (row.prompt_tokens, row.completion_tokens, row.cost_usd) == (None, None, None)
    assert row.latency_ms == 0


def test_feedback_check_constraint(recorder, factory) -> None:
    recorder.record(_record())
    for good in ("up", "down", None):
        with factory() as s:
            s.get(AgentTurnModel, "turn-1").feedback = good
            s.commit()
    with factory() as s:
        s.get(AgentTurnModel, "turn-1").feedback = "maybe"
        with pytest.raises(IntegrityError):
            s.commit()


def test_create_all_adds_agent_turns_to_a_pre_240_db_without_touching_loans(tmp_path) -> None:
    eng = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    tables = [t for n, t in Base.metadata.tables.items() if n != "agent_turns"]
    Base.metadata.create_all(eng, tables=tables)
    with sessionmaker(bind=eng)() as s:
        s.add(ReportMetaModel(report_date="20260101", last_order=7))
        s.commit()
    assert "agent_turns" not in inspect(eng).get_table_names()

    Base.metadata.create_all(eng)

    assert "agent_turns" in inspect(eng).get_table_names()
    with eng.connect() as conn:
        assert conn.execute(text("SELECT last_order FROM report_meta")).scalar_one() == 7
    eng.dispose()


def test_a_resolve_entity_turn_is_recorded_despite_its_float_score(recorder, factory) -> None:
    """Regression (found by KCH-248): resolve_entity returns `score` as a
    float, encrypt_json rejects floats, so every turn that resolved a name was
    silently dropped (failure_count += 1). Scores are not money; they are
    stored as their repr text."""
    resolve = TraceEvent(
        TraceKind.OBSERVATION, 1, 6, tool="resolve_entity",
        payload={"ok": True, "status": "resolved",
                 "candidates": [{"field": "borrower_group", "value": "G001", "rank": 1,
                                 "score": 0.912}]},
    )
    base = _record()
    record = TurnRecord(
        conversation_id=base.conversation_id, turn_id=base.turn_id,
        prompt_version=base.prompt_version, user_text=base.user_text,
        outcome=base.outcome, step_count=base.step_count,
        events=(resolve, *base.events), completions=base.completions,
        latency_ms=base.latency_ms,
    )
    recorder.record(record)
    assert recorder.failure_count == 0
    stored = _row(factory).react_trace["events"][0]["payload"]["candidates"][0]["score"]
    assert stored == "0.912"
