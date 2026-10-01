"""The harness tests itself (KCH-248): a check that cannot fail is worthless,
so each guard here has a test that trips it on purpose."""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import os
import socket
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.infrastructure.llm.openai_compat_client import OpenAICompatClient
from loan_manager.infrastructure.seed.demo_fixture import extend_fixture

from tests.evals import gen_expected, metrics, record
from tests.evals.conftest import NetworkBlockedError, live_skip_reason
from tests.evals.gen_expected import expected_for
from tests.evals.harness import (
    REPLAY_SETTINGS,
    CapturingLLM,
    Cassette,
    cassette_path,
    check_case,
    completion_to_dict,
    load_cassette,
    replay_llm,
    run_case,
)
from tests.evals.schema import CaseFileError, load_cases, to_case, validate

_LM_ROOT = Path(__file__).resolve().parents[2]


def _case(case_id: str):
    return next(c for c in load_cases() if c.id == case_id)


def _run(case, cassette: Cassette):
    return run_case(case, replay_llm(cassette), expected_completions=len(cassette.completions))


# --- gen_expected ---------------------------------------------------------


def test_gen_expected_tracks_fixture():
    """Refs come from the fixture handed in, not from anything remembered."""
    extra = tuple(
        dict(
            borrower_name=name, borrower_group="zeta co", depositor_name="d zeta",
            depositor_group=None, amount=amount, giving_date=date(2026, 1, 5),
            due_period=None, due_date=due,
        )
        for name, amount, due in (
            ("z one", 1000, date(2026, 2, 1)),
            ("z two", 2500, date(2026, 3, 1)),
            ("z three", 4000, date(2027, 1, 1)),
        )
    )
    loans = extend_fixture(extra)
    case = dataclasses.replace(
        _case("smoke-001"), where={"borrower_group": "zeta co", "status": "overdue"}
    )

    refs, facts = expected_for(case, loans)

    zeta = [f for f in loans if f.borrower_group == "zeta co"]
    overdue = [
        f for f in zeta
        if StatusEngine.compute(f.giving_date, f.due_date, case.frozen_today).value == "Overdue"
    ]
    assert len(overdue) == 2
    assert refs == sorted(f.ref for f in overdue)
    assert facts["count"] == 2
    assert facts["total_amount"] == "3500.00"


def test_gen_expected_uses_frozen_today():
    """Same question, two dates: the derived refs follow each case's own date."""
    early, late = _case("smoke-002"), _case("smoke-001")
    assert early.frozen_today != late.frozen_today

    early_refs, _ = expected_for(early)
    late_refs, _ = expected_for(late)

    assert early_refs != late_refs
    assert set(early_refs) < set(late_refs)


def test_gen_expected_check_flags_stale_and_rewrites(tmp_path, monkeypatch):
    src = (gen_expected.CASES_DIR / "smoke.jsonl").read_text()
    stale = src.replace('"2026_04_001"', '"2099_01_001"', 1)
    assert stale != src
    (tmp_path / "smoke.jsonl").write_text(stale)
    monkeypatch.setattr(gen_expected, "CASES_DIR", tmp_path)

    assert gen_expected.main(["--check"]) == 1
    assert (tmp_path / "smoke.jsonl").read_text() == stale  # --check never writes
    assert gen_expected.main([]) == 0
    assert (tmp_path / "smoke.jsonl").read_text() == src
    assert gen_expected.main(["--check"]) == 0


# --- check_case -----------------------------------------------------------


def test_check_case_flags_must_not_call():
    case = dataclasses.replace(_case("smoke-001"), must_not_call=("query_loans",))
    cassette = load_cassette(cassette_path("smoke-001"))

    failures = check_case(case, _run(case, cassette))

    assert "must_not_call: query_loans was called" in failures


def test_check_case_flags_missing_trace_step():
    case = _case("smoke-001")
    original = load_cassette(cassette_path("smoke-001"))
    no_query = Cassette(original.meta, [original.completions[0], original.completions[2]])

    failures = check_case(case, _run(case, no_query))

    assert any(f.startswith("trace ") for f in failures)
    assert any(f.startswith("ref_ids ") for f in failures)


def test_leftover_cassette_fails():
    case = _case("smoke-001")
    original = load_cassette(cassette_path("smoke-001"))
    padded = Cassette(original.meta, [*original.completions, original.completions[-1]])

    failures = check_case(case, _run(case, padded))

    assert any("not fully consumed" in f for f in failures)


def test_exhausted_cassette_fails():
    case = _case("smoke-001")
    original = load_cassette(cassette_path("smoke-001"))
    short = Cassette(original.meta, original.completions[:2])

    failures = check_case(case, _run(case, short))

    assert any("outcome 'llm_error'" in f for f in failures)


def test_check_case_flags_wrong_entity_expectation():
    case = dataclasses.replace(_case("smoke-003"), expected_entity={"slug": "iyer chem"})
    cassette = load_cassette(cassette_path("smoke-003"))

    failures = check_case(case, _run(case, cassette))

    assert any(f.startswith("resolver top ") for f in failures)


def test_clarifying_case_never_queries():
    case = _case("smoke-003")
    run = _run(case, load_cassette(cassette_path("smoke-003")))

    assert run.actions == ["resolve_entity"]
    assert run.ref_ids_R == []
    assert run.resolution["status"] == "ambiguous"
    assert run.resolution["top2"] == ["lakshmi iyer", "suresh iyer"]


def test_boundary_rows_sit_on_the_status_edge():
    """due == today is Overdue; giving == today is Active (CLAUDE.md status rules)."""
    overdue = _case("boundary-001")
    active = _case("boundary-002")
    assert overdue.frozen_today == active.frozen_today
    assert expected_for(overdue)[0] == ["2026_03_007"]
    assert expected_for(active)[0] == ["2026_09_001"]


def test_run_never_shows_the_model_a_name_or_amount():
    case = _case("smoke-001")
    run = _run(case, load_cassette(cassette_path("smoke-001")))
    sent = json.dumps(run.requests)

    for plaintext in ("sharma", "550000", "250000", "rakesh"):
        assert plaintext not in sent
    assert "sharma group" in run.raw_final  # rehydrated only for the human


def test_completion_serialiser_round_trips_through_the_fake():
    """`record.py` writes cassettes with `completion_to_dict`; the replay path
    must read back exactly what it wrote."""
    original = load_cassette(cassette_path("smoke-001")).completions
    fake = replay_llm(Cassette({}, original))
    capture = CapturingLLM(fake)
    for _ in original:
        capture.complete([{"role": "user", "content": "x"}], None)

    assert [completion_to_dict(c) for c in capture.completions] == original


# --- offline guard --------------------------------------------------------


def test_network_blocked():
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("127.0.0.1", 9))
    with pytest.raises(NetworkBlockedError):
        socket.socket().connect(("127.0.0.1", 9))
    with pytest.raises(NetworkBlockedError):
        socket.getaddrinfo("openrouter.ai", 443)


def test_openai_client_blocked():
    with pytest.raises(NetworkBlockedError):
        OpenAICompatClient(REPLAY_SETTINGS, api_key="not-a-real-key")


def test_live_skip_reason():
    assert "OPENROUTER_API_KEY" in live_skip_reason(["eval", "llm"], {})
    assert live_skip_reason(["eval", "llm"], {"GROQ_API_KEY": "k"}) is not None
    assert live_skip_reason(["eval", "llm"], {"OPENROUTER_API_KEY": "k"}) is None
    assert live_skip_reason(["eval"], {}) is None


def test_offline_lane_green_without_key():
    """A pull request has no secret. The lane must pass with every key
    variable gone, and the live tests must skip -- not fail, not run."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"OPENROUTER_API_KEY", "GROQ_API_KEY", "CI", "TEST_DATABASE_URL"}
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable, "-m", "pytest", "tests/evals", "-q", "-p", "no:cacheprovider",
            "-rs", "-k", "not test_offline_lane_green_without_key",
        ],
        cwd=_LM_ROOT, env=env, capture_output=True, text=True, timeout=300,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out[-2000:]
    assert "OPENROUTER_API_KEY not set" in out  # the live tests said why they skipped
    assert " passed" in out and " failed" not in out


# --- record.py refusal paths (never a live call) ----------------------------


def test_record_refuses_without_key_or_in_ci(tmp_path):
    assert "OPENROUTER_API_KEY" in record.refusal_reason({})
    assert "CI" in record.refusal_reason({"CI": "true", "OPENROUTER_API_KEY": "k"})
    assert record.refusal_reason({"OPENROUTER_API_KEY": "k"}) is None

    target = cassette_path("smoke-001")
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    assert record.main(["smoke-001"], environ={}) == 2
    assert record.main(["smoke-001"], environ={"CI": "1", "OPENROUTER_API_KEY": "k"}) == 2
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before


# --- schema and ratchet ----------------------------------------------------

_GOOD = {
    "id": "x-1", "suite": "s", "question": "q?", "frozen_today": "2026-09-25",
    "expected_trace": ["resolve_entity"], "expected_entity": {"slug": "a"},
    "focus": {"entity": "a", "metric": "m", "period": None}, "must_not_call": [],
}


def _bad(**change):
    row = copy.deepcopy(_GOOD)
    for key, value in change.items():
        if value is _DROP:
            del row[key]
        else:
            row[key] = value
    return row


_DROP = object()


def test_schema_accepts_a_good_case():
    assert validate(_GOOD) == []
    assert to_case(_GOOD).frozen_today == date(2026, 9, 25)


@pytest.mark.parametrize(
    ("row", "fragment"),
    [
        (_bad(surprise=1), "surprise: unknown key"),
        (_bad(question=_DROP), "question: missing key"),
        (_bad(frozen_today="25/09/2026"), "frozen_today: not an ISO date"),
        (_bad(frozen_today="2026-13-40"), "frozen_today: not an ISO date"),
        (
            _bad(expected_entity={"slug": "a", "ambiguous": ["a", "b"]}),
            "mutually exclusive",
        ),
        (_bad(expected_entity={"ambiguous": ["only-one"]}), "exactly two"),
        (_bad(focus={"entity": "a"}), "focus:"),
        (_bad(where={"amount": 5}), "where:"),
    ],
)
def test_schema_rejects_bad_case(row, fragment):
    assert any(fragment in error for error in validate(row)), validate(row)


def test_load_cases_rejects_duplicate_ids(tmp_path):
    line = json.dumps(_GOOD)
    path = tmp_path / "dup.jsonl"
    path.write_text(f"{line}\n{line}\n")
    with pytest.raises(CaseFileError, match="duplicate case id"):
        load_cases(path)


def test_ratchet():
    baseline = {"answer_correct": 0.9, "grounded": 1.0}

    assert metrics.ratchet({"answer_correct": 0.9, "grounded": 1.0}, baseline) == []
    assert metrics.ratchet({"answer_correct": 0.95, "grounded": 1.0, "new": 0.1}, baseline) == []
    below = metrics.ratchet({"answer_correct": 0.89, "grounded": 1.0}, baseline)
    assert below == ["answer_correct: 0.89 < baseline 0.9"]
    missing = metrics.ratchet({"grounded": 1.0}, baseline)
    assert missing == ["answer_correct: missing (baseline 0.9)"]


def test_shipped_baseline_loads_and_registry_is_empty():
    assert metrics.load_baseline() == {}
    assert metrics.METRICS == {}
