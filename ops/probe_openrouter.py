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

# (label, prompt, tool that SHOULD be called first, must NOT be called)
STAGE2_CASES = [
    # STRICT: resolve_entity must come FIRST. Calling query_loans directly means
    # filtering on the raw string "sharma group", which is not a stored value —
    # it matches nothing and the model reports "no loans found" confidently (§5.2).
    ("entity-first", "How many loans are overdue for the sharma group?",
     {"resolve_entity"}, {"extend_loan", "create_loan"}),
    ("date-relative", "What is due this quarter?",
     {"get_current_context", "query_loans"}, {"extend_loan", "create_loan"}),
    ("no-arithmetic", "What is the interest on loan 2026_03_004 at 12% for 3 months?",
     {"calculate_interest"}, {"extend_loan", "create_loan"}),
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

    spent = 0.0
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
        spent += cost_of(r)
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
        for label, prompt, expect, forbid in STAGE2_CASES:
            if spent >= a.max_usd:
                break
            r = call(key, m, prompt, tools, max_tokens=250)
            if "error" in r:
                print(f"    {R}ERR {RST} {label:<14} {str(r['error'])[:60]}")
                continue
            spent += cost_of(r)
            names = set(tool_names(r))
            broken = bad_args(r)
            hit, viol = names & expect, names & forbid
            if viol:
                mark, note = f"{R}UNSAFE{RST}", f"called {', '.join(viol)} — a PROPOSE tool unprompted"
            elif broken:
                mark, note = f"{R}BADARG{RST}", f"unparseable arguments: {', '.join(broken)}"
            elif hit:
                mark, note = f"{G}OK    {RST}", _args_summary(r)
            else:
                got = _args_summary(r) or "prose"
                mark, note = f"{Y}MISS  {RST}", f"expected {sorted(expect)}, got {got}"
            print(f"    {mark} {label:<14} {note}")

    print("─" * 66)
    print(f"spend: ${spent:.4f} of ${a.max_usd:.3f} cap"
          f"   {D}({spent/100*100:.3f}% of a $100 budget){RST}")
    print(f"{D}Tool-capable: {', '.join(passed) or 'none'}{RST}")
    print(f"{D}Put the winner in data/settings.json['llm']['model'].{RST}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
