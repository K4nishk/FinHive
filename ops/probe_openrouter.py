#!/usr/bin/env python3
"""Probe OpenRouter for tool-calling fidelity — the D-4a gate.

ARB D-4a approves an OpenAI-compatible client but leaves the PROVIDER conditional:
tool calling is NOT uniformly supported on OpenRouter's cheap/free tiers, and where
it is, fidelity varies by model. Seven tool schemas built against an endpoint that
cannot call them is the expensive mistake this probe exists to prevent.

Deliberately frugal. Two stages, and stage 2 only runs for models that pass
stage 1:

  stage 1  one tiny call, one simple tool   -> can it emit a tool_call at all?
  stage 2  the real FinHive tool set (7)    -> does it pick the RIGHT tool,
                                               with valid arguments, and does it
                                               chain resolve_entity first?

Hard budget cap. Stops before exceeding --max-usd (default 0.05, i.e. 0.05% of a
$100 budget). Reports actual spend from OpenRouter's own usage accounting.

    export OPENROUTER_API_KEY=...        # or: source ops/.env.local
    python3 ops/probe_openrouter.py                  # default candidate list
    python3 ops/probe_openrouter.py --models deepseek/deepseek-chat
    python3 ops/probe_openrouter.py --max-usd 0.02
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import NamedTuple

URL = "https://openrouter.ai/api/v1/chat/completions"

G, Y, R, D, RST = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"

# Open-weights first, per D-4a. ':free' tiers are included precisely because they
# are the ones most likely to LACK tool support — that is the finding we need.
DEFAULT_MODELS = [
    "deepseek/deepseek-chat",
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen-2.5-72b-instruct",
    "mistralai/mistral-small-24b-instruct-2501",
]

SIMPLE_TOOL = [{
    "type": "function",
    "function": {
        "name": "query_loans",
        "description": "Filtered aggregate query over loans. Returns counts and "
                       "totals, never rows.",
        "parameters": {
            "type": "object",
            "properties": {
                "borrower_group": {"type": "string",
                                   "description": "canonical group slug"},
                "status": {"type": "string",
                           "enum": ["active", "overdue", "pending", "paidoff"]},
            },
            "required": ["status"],
            "additionalProperties": False,
        },
    },
}]

# The real M1.1 set. additionalProperties:false mirrors Pydantic extra='forbid' —
# a model that ignores it will happily invent a giving_date argument, which is the
# exact failure CLAUDE.md forbids.
FULL_TOOLS = [
    ("get_current_context", "Today's date, quarter and financial-year boundaries. "
     "The model does not know what day it is.", {}, []),
    ("resolve_entity", "Resolve free text to a canonical borrower or group slug. "
     "Call this BEFORE querying by name.",
     {"text": {"type": "string"}}, ["text"]),
    ("query_loans", "Filtered aggregate query. Returns {count, total_amount, "
     "overdue, ref_ids}, never rows.",
     {"borrower_group": {"type": "string"},
      "status": {"type": "string",
                 "enum": ["active", "overdue", "pending", "paidoff"]}}, ["status"]),
    ("get_portfolio_summary", "Top-N borrowers by outstanding exposure.",
     {"limit": {"type": "integer"}}, []),
    ("calculate_interest", "Deterministic interest arithmetic. NEVER compute "
     "interest yourself.",
     {"ref_id": {"type": "string"}, "rate": {"type": "number"},
      "months": {"type": "integer"}}, ["ref_id", "rate", "months"]),
    ("extend_loan", "PROPOSE extending a loan's due date. Creates a proposal for "
     "human approval; never writes.",
     {"ref_id": {"type": "string"}, "months": {"type": "integer"}},
     ["ref_id", "months"]),
    ("create_loan", "PROPOSE a new loan. Creates a proposal for human approval; "
     "never writes.",
     {"borrower_name": {"type": "string"}, "amount": {"type": "integer"}},
     ["borrower_name", "amount"]),
]

class Case(NamedTuple):
    label: str
    prompt: str
    expect: set[str]     # a tool that SHOULD be called in this first turn
    forbid: set[str]     # PROPOSE tools: calling one is UNSAFE
    want: dict           # {tool: {arg: value it must carry}}, what a name check misses
    premature: set[str]  # tools that need expect's RESULT, so cannot be right yet


PROPOSE = {"extend_loan", "create_loan"}

STAGE2_CASES = [
    # STRICT: resolve_entity must come FIRST. A query_loans in the same turn (in
    # either order) filters on the raw string "sharma group", which is not a stored
    # value: it matches nothing and the model reports "no loans found" (§5.2).
    Case("entity-first", "How many loans are overdue for the sharma group?",
         {"resolve_entity"}, PROPOSE, {}, {"query_loans"}),
    # query_loans takes no date, so it cannot answer this in the first turn: llama
    # swapped in status='overdue', a different question (2026-09-22).
    Case("date-relative", "What is due this quarter?",
         {"get_current_context"}, PROPOSE, {}, {"query_loans"}),
    # Rate is a percent: (amount * rate * months) / 1200. qwen sent rate=0.12 for
    # 12%, which is 100x too little interest (2026-09-25).
    Case("no-arithmetic", "What is the interest on loan 2026_03_004 at 12% for 3 months?",
         {"calculate_interest"}, PROPOSE,
         {"calculate_interest": {"ref_id": "2026_03_004", "rate": 12, "months": 3}}, set()),
]


def full_tool_schemas() -> list[dict]:
    out = []
    for name, desc, props, req in FULL_TOOLS:
        out.append({"type": "function", "function": {
            "name": name, "description": desc,
            "parameters": {"type": "object", "properties": props,
                           "required": req, "additionalProperties": False}}})
    return out


def call(key: str, model: str, prompt: str, tools: list[dict],
         max_tokens: int = 200) -> dict:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.1,          # Groq converts 0 to 1e-8; be explicit everywhere
        "messages": [{"role": "user", "content": prompt}],
        "tools": tools,
        "tool_choice": "auto",
        "usage": {"include": True},  # OpenRouter's own cost accounting
    }
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}",
                 "X-Title": "FinHive D-4a probe"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": {"http": e.code, "body": e.read().decode()[:400]}}
    except Exception as e:  # noqa: BLE001 — surface anything, never crash mid-probe
        return {"error": {"exc": f"{type(e).__name__}: {e}"}}


def tool_names(resp: dict) -> list[str]:
    try:
        tc = resp["choices"][0]["message"].get("tool_calls") or []
        return [c["function"]["name"] for c in tc]
    except (KeyError, IndexError):
        return []


def bad_args(resp: dict) -> list[str]:
    """Arguments that are not parseable JSON — a real and common failure."""
    out = []
    try:
        for c in resp["choices"][0]["message"].get("tool_calls") or []:
            try:
                json.loads(c["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                out.append(c["function"]["name"])
    except (KeyError, IndexError):
        pass
    return out


def _args_summary(resp: dict) -> str:
    """name(arg=value, ...) per tool call — an unresolved raw slug is only
    visible here, never in the tool name alone."""
    out = []
    try:
        for c in resp["choices"][0]["message"].get("tool_calls") or []:
            try:
                a = json.loads(c["function"]["arguments"] or "{}")
                inner = ", ".join(f"{k}={v!r}" for k, v in a.items())
            except json.JSONDecodeError:
                inner = "<unparseable>"
            out.append(f"{c['function']['name']}({inner})")
    except (KeyError, IndexError):
        pass
    return " + ".join(out)


def verdict(case: Case, resp: dict) -> tuple[str, str]:
    """(label, note) for one stage-2 response. Pure, so it is testable offline."""
    expect, forbid, want = case.expect, case.forbid, case.want
    names = set(tool_names(resp))
    broken = bad_args(resp)
    hit, viol, early = names & expect, names & forbid, names & case.premature
    if viol:
        return "UNSAFE", f"called {', '.join(sorted(viol))} — a PROPOSE tool unprompted"
    if broken:
        return "BADARG", f"unparseable arguments: {', '.join(broken)}"
    if early:
        return "MISS", (f"{', '.join(sorted(early))} called before {sorted(expect)} "
                        f"returned: {_args_summary(resp)}")
    msg = ((resp.get("choices") or [{}])[0]).get("message") or {}
    for c in msg.get("tool_calls") or []:
        name = c["function"]["name"]
        args = json.loads(c["function"]["arguments"] or "{}")
        wrong = [f"{k}={args.get(k)!r}, want {v!r}"
                 for k, v in want.get(name, {}).items() if args.get(k) != v]
        if wrong:
            return "WRONGARG", f"{name}: {'; '.join(wrong)}"
    if hit:
        return "OK", _args_summary(resp)
    return "MISS", f"expected {sorted(expect)}, got {_args_summary(resp) or 'prose'}"


def cost_of(resp: dict) -> float:
    return float((resp.get("usage") or {}).get("cost") or 0.0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    ap.add_argument("--max-usd", type=float, default=0.05,
                    help="hard stop once spend reaches this (default 0.05)")
    a = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print(f"{R}OPENROUTER_API_KEY not set.{RST} Run: source ops/.env.local")
        return 1

    spent, calls = 0.0, 0
    s2_spent, s2_calls = 0.0, 0  # 7-schema calls only; stage 1 sends one schema
    passed: list[str] = []
    print(f"\nD-4a PROBE · tool-calling fidelity   {D}budget cap ${a.max_usd:.3f}{RST}")
    print("─" * 66)
    print(f"{D}stage 1 — can the model emit a tool_call at all?{RST}")

    for m in a.models:
        if spent >= a.max_usd:
            print(f"  {Y}budget cap reached — stopping{RST}")
            break
        r = call(key, m, "How many loans are overdue for the sharma group?",
                 SIMPLE_TOOL, max_tokens=150)
        if "error" in r:
            print(f"  {R}ERR {RST} {m:<44} {str(r['error'])[:80]}")
            continue
        spent, calls = spent + cost_of(r), calls + 1
        names = tool_names(r)
        if names:
            passed.append(m)
            print(f"  {G}PASS{RST} {m:<44} -> {', '.join(names)}")
        else:
            txt = (r["choices"][0]["message"].get("content") or "")[:44]
            print(f"  {R}FAIL{RST} {m:<44} prose: {txt!r}")

    if not passed:
        print(f"\n{R}No candidate emitted a tool call.{RST}")
        print("D-4a cannot be closed on this provider. Options: pick a model "
              "documented for tools, or reconsider D-17 (model emits SQL).")
        print(f"spend: ${spent:.4f}")
        return 1

    print(f"\n{D}stage 2 — right tool, valid args, correct chaining?{RST}")
    tools = full_tool_schemas()
    for m in passed:
        if spent >= a.max_usd:
            print(f"  {Y}budget cap reached — stopping{RST}")
            break
        print(f"  {m}")
        for case in STAGE2_CASES:
            label, prompt = case.label, case.prompt
            if spent >= a.max_usd:
                break
            r = call(key, m, prompt, tools, max_tokens=250)
            if "error" in r:
                print(f"    {R}ERR {RST} {label:<14} {str(r['error'])[:60]}")
                continue
            c = cost_of(r)
            spent, calls, s2_spent, s2_calls = spent + c, calls + 1, s2_spent + c, s2_calls + 1
            mark, note = verdict(case, r)
            colour = G if mark == "OK" else Y if mark == "MISS" else R
            print(f"    {colour}{mark:<8}{RST} {label:<14} {note}")

    print("─" * 66)
    print(f"spend: ${spent:.4f} of ${a.max_usd:.3f} cap over {calls} calls"
          f"   {D}({spent/100*100:.3f}% of a $100 budget){RST}")
    if s2_calls:
        across = " (averaged across models)" if len(passed) > 1 else ""
        print(f"stage 2 per call (7 tool schemas): ${s2_spent / s2_calls:.5f}"
              f" over {s2_calls} calls{across}")
    print(f"{D}Tool-capable: {', '.join(passed) or 'none'}{RST}")
    print(f"{D}Put the winner in data/settings.json['llm']['model'].{RST}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
