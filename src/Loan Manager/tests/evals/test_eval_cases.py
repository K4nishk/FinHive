"""The eval cases themselves (KCH-248).

Replay: every case runs offline against its cassette on every pull request.
Live: the same cases against the real model, `llm`-marked, skipped without a
key. `test_gen_expected_is_current` keeps the generated half of each case
honest against the fixture.
"""
from __future__ import annotations

import pytest
from loan_manager.infrastructure.llm.openai_compat_client import OpenAICompatClient
from loan_manager.infrastructure.llm.settings import load_llm_settings

from tests.evals.gen_expected import expected_for
from tests.evals.harness import (
    cassette_path,
    check_case,
    load_cassette,
    replay_llm,
    run_case,
)
from tests.evals.schema import CASES_DIR, load_cases, read_rows, to_case

CASES = load_cases()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_eval_case(case):
    cassette = load_cassette(cassette_path(case.id))
    run = run_case(
        case, replay_llm(cassette), expected_completions=len(cassette.completions)
    )
    assert check_case(case, run) == []


@pytest.mark.llm
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_eval_case_live(case):
    run = run_case(case, OpenAICompatClient(load_llm_settings()))
    assert check_case(case, run) == []


def test_every_case_has_a_cassette():
    missing = [c.id for c in CASES if not cassette_path(c.id).exists()]
    assert missing == []


def test_gen_expected_is_current():
    stale = []
    for path in sorted(CASES_DIR.glob("*.jsonl")):
        for row in read_rows(path):
            refs, facts = expected_for(to_case(row))
            if row.get("expected_ref_ids") != refs or row.get("expected_facts") != facts:
                stale.append(f"{row['id']}: file has {row.get('expected_ref_ids')}, "
                             f"fixture derives {refs}")
    assert stale == [], "run `python -m tests.evals.gen_expected`"
