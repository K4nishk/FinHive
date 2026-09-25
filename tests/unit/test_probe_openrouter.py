"""D-4a provider spike (KCH-252) -- the probe's verdicts, checked offline.

The 2026-09-22 gate picked qwen/qwen-2.5-72b-instruct by a human reading the
argument summaries, because the probe judged on tool NAMES alone. The 2026-09-25
re-run (qwen only) printed OK for calculate_interest(rate=0.12) on "12%": 100x too
little interest under (amount * rate * months) / 1200. The same name-only logic
also scores llama's 2026-09-22 answer, query_loans(status='overdue') for "due this
quarter", as OK. It judged a response as a SET of names, so a raw-name query sent
in the same turn as resolve_entity passed as well. Review of KCH-252 found that.

Canned responses shaped like the real ones: no network, no spend.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "ops" / "probe_openrouter.py"
SETTINGS = ROOT / "src" / "Loan Manager" / "data" / "settings.json"
ARB = ROOT / "output" / "Loan Manager" / "mvp2" / "ARB_DECISIONS.md"


def _load_probe():
    spec = importlib.util.spec_from_file_location("probe_openrouter", PROBE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


probe = _load_probe()


def _case(label: str) -> tuple:
    return next(c for c in probe.STAGE2_CASES if c[0] == label)


def _resp(*calls: tuple[str, dict]) -> dict:
    return {"choices": [{"message": {"tool_calls": [
        {"function": {"name": n, "arguments": json.dumps(a)}} for n, a in calls
    ]}}]}


def test_rate_passed_as_a_fraction_is_flagged_not_ok() -> None:
    # qwen, measured 2026-09-25. The prompt says 12%; the formula wants 12.
    r = _resp(("calculate_interest",
               {"ref_id": "2026_03_004", "rate": 0.12, "months": 3}))
    label, note = probe.verdict(_case("no-arithmetic"), r)
    assert label == "WRONGARG", f"rate=0.12 for 12% judged {label}: {note}"


def test_rate_passed_in_percent_is_ok() -> None:
    r = _resp(("calculate_interest",
               {"ref_id": "2026_03_004", "rate": 12, "months": 3}))
    assert probe.verdict(_case("no-arithmetic"), r)[0] == "OK"


def test_status_substituted_for_a_date_range_is_a_miss() -> None:
    # llama, 2026-09-22: answered "overdue" when asked "due this quarter".
    # query_loans takes no date, so without get_current_context the question
    # cannot be answered -- only swapped for a different one.
    r = _resp(("query_loans", {"status": "overdue"}))
    label, note = probe.verdict(_case("date-relative"), r)
    assert label == "MISS", f"status substitution judged {label}: {note}"


def test_querying_a_raw_name_before_resolving_it_is_a_miss() -> None:
    # qwen, 2026-09-22 and 2026-09-25: 'sharma group' is not a stored slug, so
    # this matches nothing and the model reports "no loans" with confidence.
    r = _resp(("query_loans", {"borrower_group": "sharma group", "status": "overdue"}))
    assert probe.verdict(_case("entity-first"), r)[0] == "MISS"


def test_raw_name_queried_beside_resolve_entity_is_a_miss() -> None:
    # One turn: the query runs before resolve_entity's answer exists.
    r = _resp(("resolve_entity", {"text": "sharma group"}),
              ("query_loans", {"borrower_group": "sharma group", "status": "overdue"}))
    label, note = probe.verdict(_case("entity-first"), r)
    assert label == "MISS", f"parallel raw-name query judged {label}: {note}"


def test_raw_name_queried_before_resolve_entity_is_a_miss() -> None:
    r = _resp(("query_loans", {"borrower_group": "sharma group", "status": "overdue"}),
              ("resolve_entity", {"text": "sharma group"}))
    label, note = probe.verdict(_case("entity-first"), r)
    assert label == "MISS", f"raw-name query before resolve judged {label}: {note}"


def test_status_substituted_beside_get_current_context_is_a_miss() -> None:
    r = _resp(("get_current_context", {}), ("query_loans", {"status": "overdue"}))
    label, note = probe.verdict(_case("date-relative"), r)
    assert label == "MISS", f"parallel status substitution judged {label}: {note}"


def test_resolving_the_name_first_is_ok() -> None:
    r = _resp(("resolve_entity", {"text": "sharma group"}))
    assert probe.verdict(_case("entity-first"), r)[0] == "OK"


def test_skipping_resolve_is_reported_as_skipped() -> None:
    # A human reads this note at the gate: it must say what the model actually did.
    r = _resp(("query_loans", {"borrower_group": "sharma group", "status": "overdue"}))
    label, note = probe.verdict(_case("entity-first"), r)
    assert label == "MISS" and "without" in note, note


def test_an_invented_argument_is_flagged() -> None:
    # additionalProperties:false mirrors extra='forbid'; giving_date is the argument
    # CLAUDE.md bans from every interest calculation.
    r = _resp(("calculate_interest", {"ref_id": "2026_03_004", "rate": 12, "months": 3,
                                      "giving_date": "2026-01-01"}))
    label, note = probe.verdict(_case("no-arithmetic"), r)
    assert label == "WRONGARG", f"undeclared giving_date judged {label}: {note}"


def test_non_object_arguments_are_badarg_not_a_crash() -> None:
    # Valid JSON, wrong shape: a crash here aborts a paid run before spend is printed.
    for raw in ("null", "[]", "12"):
        r = {"choices": [{"message": {"tool_calls": [
            {"function": {"name": "calculate_interest", "arguments": raw}}]}}]}
        assert probe.verdict(_case("no-arithmetic"), r)[0] == "BADARG", raw


def test_a_propose_tool_is_unsafe_even_beside_the_right_tool() -> None:
    r = _resp(("calculate_interest", {"ref_id": "2026_03_004", "rate": 12, "months": 3}),
              ("extend_loan", {"ref_id": "2026_03_004", "months": 3}))
    assert probe.verdict(_case("no-arithmetic"), r)[0] == "UNSAFE"


def test_settings_records_the_model_d4a_chose() -> None:
    chosen = re.search(r"GATE CLOSED [\d-]+ — `([^`]+)`", ARB.read_text(encoding="utf-8"))
    assert chosen, "ARB D-4a no longer names the model it closed on"
    llm = json.loads(SETTINGS.read_text(encoding="utf-8")).get("llm")
    assert llm, "settings.json has no 'llm' block -- the D-4a winner is unrecorded"
    assert llm.get("model") == chosen.group(1), (llm.get("model"), chosen.group(1))
    # Money is never a float (CLAUDE.md); json.loads turns a bare number into one.
    assert isinstance(llm.get("measured_usd_per_call"), str), llm
