"""D-4a provider spike (KCH-252) -- the probe's verdicts, checked offline.

The 2026-09-22 gate picked qwen/qwen-2.5-72b-instruct by a human reading the
argument summaries, because the probe judged on tool NAMES alone. Re-run on
2026-09-25, it printed OK for two wrong answers: calculate_interest(rate=0.12)
for "12%" -- 100x too little interest under (amount * rate * months) / 1200 --
and, for llama, query_loans(status='overdue') for "due this quarter".

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
