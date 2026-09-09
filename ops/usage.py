#!/usr/bin/env python3
"""Token and cost meter for the build loop.

Every `claude -p --output-format json` invocation returns what it spent. This
records those into a per-session ledger, reports totals, and answers the one
question the loop needs between issues: are we near the budget?

    ops/usage.py record RESULT.json --issue KCH-78 --phase impl
    ops/usage.py check  --budget-usd 20 --threshold 95     # exit 1 when at/over
    ops/usage.py report                                    # CLI summary

WHAT THIS CANNOT DO — read honestly before trusting it:

Anthropic exposes no endpoint for the remaining balance of a plan's 5-hour
rolling window, so this is NOT a reading of that window. It is an accounting of
what THIS LOOP spent since its session started. Tokens you spend in an
interactive Claude session, another terminal, or an editor plugin are invisible
here and still count against the same window.

So treat the budget as a self-imposed ceiling, not a measurement. The reliable
signal that the real limit was hit is a usage-limit response from the CLI, which
`classify_error` detects and the orchestrator treats as a hard stop regardless of
what this ledger says.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

OPS = Path(__file__).resolve().parent
LEDGER = OPS / "logs" / "usage.jsonl"

DIM, RED, GRN, YEL, RST = "\033[2m", "\033[31m", "\033[32m", "\033[33m", "\033[0m"

# Substrings that mean "the platform stopped us", not "the task failed".
LIMIT_MARKERS = (
    "usage limit", "rate limit", "rate_limit", "quota",
    "spend limit", "credit balance", "insufficient credit",
    "too many requests", "overloaded",
)
AUTH_MARKERS = ("not logged in", "please run /login", "unauthorized", "authentication")


def classify_error(payload: dict) -> str | None:
    """'limit' | 'auth' | 'error' | None — what kind of failure, if any."""
    if not payload.get("is_error"):
        return None
    blob = " ".join(
        str(payload.get(k, "")) for k in ("result", "terminal_reason", "api_error_status", "stop_reason")
    ).lower()
    if any(m in blob for m in LIMIT_MARKERS):
        return "limit"
    if any(m in blob for m in AUTH_MARKERS):
        return "auth"
    return "error"


def session_id() -> str:
    """One id per loop run, set by the orchestrator so a pass groups together."""
    return os.environ.get("FH_SESSION_ID") or time.strftime("%Y%m%dT%H%M%S")


def _rows(sid: str | None = None) -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for line in LEDGER.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue                      # a truncated write must not break reporting
        if sid is None or r.get("session") == sid:
            out.append(r)
    return out


def totals(rows: list[dict]) -> dict:
    t = {"cost_usd": 0.0, "input": 0, "output": 0, "cache_read": 0,
         "cache_write": 0, "turns": 0, "calls": 0, "errors": 0}
    for r in rows:
        t["cost_usd"] += float(r.get("cost_usd") or 0)
        t["input"] += int(r.get("input") or 0)
        t["output"] += int(r.get("output") or 0)
        t["cache_read"] += int(r.get("cache_read") or 0)
        t["cache_write"] += int(r.get("cache_write") or 0)
        t["turns"] += int(r.get("turns") or 0)
        t["calls"] += 1
        if r.get("error"):
            t["errors"] += 1
    return t


def cmd_record(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(Path(args.result).read_text())
    except Exception as exc:                                   # noqa: BLE001
        # A malformed result must not kill the build — record what we can.
        payload = {"is_error": True, "result": f"unparseable result: {exc}"}
    u = payload.get("usage") or {}
    kind = classify_error(payload)
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "session": session_id(),
        "issue": args.issue,
        "phase": args.phase,
        "model": payload.get("model") or args.model or "",
        "cost_usd": payload.get("total_cost_usd") or 0,
        "input": u.get("input_tokens") or 0,
        "output": u.get("output_tokens") or 0,
        "cache_read": u.get("cache_read_input_tokens") or 0,
        "cache_write": u.get("cache_creation_input_tokens") or 0,
        "turns": payload.get("num_turns") or 0,
        "duration_ms": payload.get("duration_ms") or 0,
        "error": kind,
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(row) + "\n")
    # The orchestrator branches on this line, so keep it machine-readable.
    print(f"kind={kind or 'ok'} cost={row['cost_usd']} in={row['input']} out={row['output']}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Exit 0 while under threshold, 1 at/over, 2 when a hard limit was hit."""
    rows = _rows(session_id())
    if any(r.get("error") == "limit" for r in rows):
        print(f"{RED}HARD STOP{RST} — the platform reported a usage limit this session")
        return 2
    t = totals(rows)
    pct = (t["cost_usd"] / args.budget_usd * 100) if args.budget_usd > 0 else 0.0
    bar_n = min(int(pct / 5), 20)
    bar = "█" * bar_n + "·" * (20 - bar_n)
    colour = GRN if pct < 75 else (YEL if pct < args.threshold else RED)
    print(f"  {colour}{bar}{RST} {pct:5.1f}%  ${t['cost_usd']:.4f} / ${args.budget_usd:.2f}"
          f"  {DIM}({t['calls']} calls, {t['input'] + t['output']:,} tok){RST}")
    return 1 if pct >= args.threshold else 0


def cmd_report(args: argparse.Namespace) -> int:
    sid = None if args.all else session_id()
    rows = _rows(sid)
    if not rows:
        print("  no usage recorded")
        return 0
    t = totals(rows)

    by_issue: dict[str, dict] = {}
    for r in rows:
        by_issue.setdefault(r.get("issue") or "-", []).append(r)

    print()
    print(f"  Session {sid or 'ALL'}")
    print(f"  {'─' * 66}")
    print(f"  {'issue':<12} {'phase':<8} {'calls':>5} {'in':>10} {'out':>8} {'cost':>10}")
    for issue in sorted(by_issue):
        phases: dict[str, list[dict]] = {}
        for r in by_issue[issue]:
            phases.setdefault(r.get("phase") or "-", []).append(r)
        for phase, prs in sorted(phases.items()):
            p = totals(prs)
            flag = f" {RED}!{RST}" if p["errors"] else ""
            print(f"  {issue:<12} {phase:<8} {p['calls']:>5} {p['input']:>10,} "
                  f"{p['output']:>8,} ${p['cost_usd']:>9.4f}{flag}")
    print(f"  {'─' * 66}")
    print(f"  {'TOTAL':<12} {'':<8} {t['calls']:>5} {t['input']:>10,} "
          f"{t['output']:>8,} ${t['cost_usd']:>9.4f}")
    print()
    print(f"  cache read   {t['cache_read']:>12,} tok   {DIM}(cheap — already paid for){RST}")
    print(f"  cache write  {t['cache_write']:>12,} tok")
    print(f"  agent turns  {t['turns']:>12,}")
    if t["errors"]:
        kinds = {}
        for r in rows:
            if r.get("error"):
                kinds[r["error"]] = kinds.get(r["error"], 0) + 1
        print(f"  {YEL}failed calls {t['errors']:>12}{RST}   "
              + ", ".join(f"{k}×{v}" for k, v in sorted(kinds.items())))
    print()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("record", help="append one claude result to the ledger")
    r.add_argument("result", help="path to the --output-format json result")
    r.add_argument("--issue", default="-")
    r.add_argument("--phase", default="impl", choices=["impl", "gate", "mediate", "other"])
    r.add_argument("--model", default="")
    r.set_defaults(fn=cmd_record)

    c = sub.add_parser("check", help="are we near the budget?")
    c.add_argument("--budget-usd", type=float,
                   default=float(os.environ.get("SESSION_BUDGET_USD", "20")))
    c.add_argument("--threshold", type=float,
                   default=float(os.environ.get("BUDGET_THRESHOLD_PCT", "95")))
    c.set_defaults(fn=cmd_check)

    p = sub.add_parser("report", help="CLI summary of the session")
    p.add_argument("--all", action="store_true", help="every session, not just this one")
    p.set_defaults(fn=cmd_report)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
