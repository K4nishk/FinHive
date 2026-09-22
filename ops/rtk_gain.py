#!/usr/bin/env python3
"""RTK Gain — measured token savings per Linear issue.

Printed by the M1.1 orchestrator after every completed issue.

RTK (https://github.com/rtk-ai/rtk) is a CLI proxy that compresses command output
before it reaches a context window. It is installed here (`rtk 0.49.0`) but has no
`--stats`, so it compresses without reporting. This measures the delta directly:
run a gate command BOTH ways, diff the output size, and add the agent-side token
cost from ops/logs/usage.jsonl.

Every figure below is measured on this machine. No vendor percentage is applied —
the plan's own RTK section warns against presenting an estimate as a measurement.

    # measure the gate commands the orchestrator actually runs
    python3 ops/rtk_gain.py --issue KCH-222 --measure-gates

    # ledger only (no command re-runs)
    python3 ops/rtk_gain.py --issue KCH-222
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LEDGER = REPO / "ops" / "logs" / "usage.jsonl"

G, Y, R, D, RST = "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[0m"

# The gate commands the orchestrator wraps. (label, raw argv, rtk argv)
GATES: list[tuple[str, list[str], list[str]]] = [
    ("git status", ["git", "status"], ["rtk", "git", "status"]),
    ("git diff", ["git", "diff"], ["rtk", "git", "diff"]),
    ("tree ops", ["tree", "ops"], ["rtk", "tree", "ops"]),
]

# ~4 chars per token is the usual English/code approximation. Stated, not hidden:
# this converts measured BYTES into an estimated token count. Bytes are the
# measurement; tokens are the readable unit.
CHARS_PER_TOKEN = 4


def rows(ledger: Path) -> list[dict]:
    if not ledger.exists():
        return []
    out = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a half-written row must not break the report
    return out


def agg(rs: list[dict]) -> dict:
    out = sum(r.get("output") or 0 for r in rs)
    cr = sum(r.get("cache_read") or 0 for r in rs)
    return {
        "calls": len(rs),
        "errors": sum(1 for r in rs if r.get("error")),
        "input": sum(r.get("input") or 0 for r in rs),
        "output": out,
        "cache_read": cr,
        "cost": sum(float(r.get("cost_usd") or 0) for r in rs),
        "err_cost": sum(float(r.get("cost_usd") or 0) for r in rs if r.get("error")),
        "ms": sum(r.get("duration_ms") or 0 for r in rs),
        "reread": (cr / out) if out else 0.0,
    }


def run_bytes(argv: list[str]) -> int | None:
    """Byte count of a command's combined output, or None if it cannot run."""
    if shutil.which(argv[0]) is None:
        return None
    try:
        p = subprocess.run(argv, cwd=REPO, capture_output=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return len(p.stdout) + len(p.stderr)


def measure_gates() -> list[tuple[str, int, int]]:
    """(label, raw_bytes, rtk_bytes) for each gate command that ran both ways."""
    out = []
    for label, raw, wrapped in GATES:
        a, b = run_bytes(raw), run_bytes(wrapped)
        if a is not None and b is not None and a > 0:
            out.append((label, a, b))
    return out


def fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    return f"{n/1_000:.1f}k" if n >= 1_000 else str(n)


def band(v: float, good: float, bad: float) -> str:
    return G if v <= good else (R if v >= bad else Y)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--issue", help="KCH-NNN")
    ap.add_argument("--measure-gates", action="store_true",
                    help="run gate commands raw and via rtk to measure the delta")
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    a = ap.parse_args()

    have = shutil.which("rtk")
    all_rows = rows(a.ledger)
    sel = [r for r in all_rows if r.get("issue") == a.issue] if a.issue else all_rows
    m = agg(sel)

    print(f"\n{'─' * 64}\nRTK GAIN · {a.issue or 'session'}\n{'─' * 64}")

    # ---- Axis A: build-loop output compression (measured, not claimed) ----
    if a.measure_gates and have:
        gates = measure_gates()
        if gates:
            raw = sum(g[1] for g in gates)
            wrapped = sum(g[2] for g in gates)
            cut = (raw - wrapped) / raw * 100 if raw else 0.0
            print(f"  {D}Axis A · command output, measured on this machine{RST}")
            for label, r_b, w_b in gates:
                pc = (r_b - w_b) / r_b * 100 if r_b else 0.0
                col = G if pc > 0 else Y
                print(f"    {label:<12} {fmt(r_b):>8} → {fmt(w_b):>8}  "
                      f"{col}{pc:+5.0f}%{RST}")
            saved_tok = (raw - wrapped) // CHARS_PER_TOKEN
            print(f"    {'total':<12} {fmt(raw):>8} → {fmt(wrapped):>8}  "
                  f"{G if cut > 0 else Y}{cut:+5.0f}%{RST}   "
                  f"{D}≈{fmt(saved_tok)} tok/invocation{RST}")
        else:
            print(f"  {Y}Axis A · no gate command ran both ways (missing binary?){RST}")
    elif a.measure_gates:
        print(f"  {Y}Axis A · rtk not on PATH{RST}")
    else:
        print(f"  {D}Axis A · not measured this run (pass --measure-gates){RST}")

    # ---- Axis B: agent-side tokens actually billed ----
    print()
    if not m["calls"]:
        print(f"  {Y}Axis B · no ledger rows for {a.issue or 'this session'}.{RST}")
        print(f"{'─' * 64}\n")
        return 0

    waste = (m["err_cost"] / m["cost"] * 100) if m["cost"] else 0.0
    print(f"  {D}Axis B · agent tokens billed{RST}")
    print(f"    calls      {m['calls']:>8}   "
          f"{band(m['errors'], 0, 1)}{m['errors']} errored{RST}")
    print(f"    in / out   {fmt(m['input']):>8} / {fmt(m['output'])}")
    print(f"    cache read {fmt(m['cache_read']):>8}   "
          f"re-read {band(m['reread'], 40, 100)}{m['reread']:.1f}:1{RST}")
    print(f"    cost       {m['cost']:>8.4f}   "
          f"{band(waste, 5, 25)}{waste:.0f}% on errored calls{RST}")
    print(f"    wall clock {m['ms']/60000:>8.1f}m")
    print(f"  {D}M0 baseline: 122:1 re-read across 502 calls — roughly half the{RST}")
    print(f"  {D}bill was agents re-reading CLAUDE.md, the WIKI and the tree.{RST}")
    print(f"{'─' * 64}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
