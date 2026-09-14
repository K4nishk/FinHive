# Orchestrator retrospective and recovery

Evidence-based. Every number here comes from `ops/logs/usage.jsonl` (502 metered
calls) or `ops/logs/builder.log` (12k lines), not from recollection.

> **Correction, 2026-09-14.** An earlier version of this file diagnosed "OAuth
> token expiry" and prescribed setting `ANTHROPIC_API_KEY`. **Both were wrong.**
> The binding constraint was the subscription's 5-hour usage window (369 hits),
> not token expiry. And setting `ANTHROPIC_API_KEY` *overrides* the working
> claude.ai subscription login — following that advice with an `sk-ant-oat01`
> OAuth token caused 62 consecutive 401 failures over 3 hours. See "Auth" below.

---

## Auth: read this before touching anything

`ANTHROPIC_API_KEY` is not additive. When set, it **replaces** the claude.ai
subscription login. The CLI says so:

```
⚠ claude.ai connectors are disabled because ANTHROPIC_API_KEY or another auth
  source is set and takes precedence over your claude.ai login
```

Two token shapes exist and they are not interchangeable:

| Prefix | What it is | Valid in `ANTHROPIC_API_KEY`? |
|---|---|---|
| `sk-ant-oat01-` | OAuth token (subscription) | **No** — API returns `401 API key is invalid` |
| `sk-ant-api03-` | API key (console, pay-as-you-go) | Yes |

**Default: leave `ANTHROPIC_API_KEY` unset.** The subscription login works for
headless `claude -p`. Set it only if you deliberately want console billing, and
only with an `sk-ant-api03-` key.

The 5-hour subscription window is a real limit and will stop a long run. That is
correct behaviour, not a fault. Stop and wait; do not retry it in a loop.

---

## What actually happened

```
19:42  ANTHROPIC_API_KEY="sk-ant-oat01-…" added to ops/.env.local
       └─ overrode working subscription auth with a token the API rejects
21:01  builder started; KCH-99 → kind=auth, cost=0
21:04  KCH-99 → error. Logged as a normal per-issue ERROR line.
21:04–00:14  62 more issues, every one identical, 3h10m
       └─ nothing counted consecutive failures; nothing halted
```

Separately, the 20:22 "is it running?" confusion: `tmux_orchestrator.sh` ran
`touch builder.log` before `tail -f`, moving the file's mtime to 20:22 while its
last content line was 17:35. The launcher never starts the builder — it only
opens panes. Fixed: `tail -n 50 -F`, no touch.

---

## The money

`python3 ops/usage.py report --all` — 502 calls, **$76.82** total.

| Phase | Calls | $ |
|---|---|---|
| `impl` | 31 | 41.27 |
| `gate` | 30 | 27.68 |
| `mediate` | 378 | 7.87 |

Failed calls: **389** — `limit`×369, `error`×19, `auth`×1.

Three mechanisms, ranked by cost:

1. **369 retries against a hit usage limit.** `run_builder.sh` returned 0
   unconditionally, so a platform hard-stop was indistinguishable from success;
   `--loop` restarted every 30s for ~10 hours on one issue (KCH-90).
2. **`error_max_turns` committed half-finished work.** 5 calls, 61 turns each,
   **$15.97**. The agent was truncated mid-edit; the loop committed the partial
   tree, gated it, and opened a PR. This is the source of the half-finished PRs.
3. **$20 budget cap never fired, once, in 5 days.** `usage.py cmd_check` scopes
   to `_rows(session_id())` and `FH_SESSION_ID` is new per pass. 381 passes each
   started at `$0.0000 / $20.00`. Cumulative spend is 3.8× the stated cap.

Caveat worth stating: these are CLI-reported figures, not a billing statement.
Reconcile against the account usage page before treating $76.82 as money.

---

## Confirmed bugs (fixed 2026-09-14)

| File:line | Bug | Consequence |
|---|---|---|
| `orchestrator.sh:887` | `grep -c . f \|\| echo 0` → `"0\n0"` on empty file | Debt guard **and** debt phase silently skipped every clean run |
| `orchestrator.sh:928` | same | "Queue exhausted" exit skipped; `--loop` immortal |
| `run_builder.sh:55` | same | Guard 3 dead |
| `tmux_orchestrator.sh:67` | same | Status panel prints a two-line count |
| `orchestrator.sh:176` | no wall-clock timeout | A hung call held the worktree lock 3h+ |
| `orchestrator.sh:176` | no `</dev/null` | Child could eat the queue via `done < "$QUEUE_RUN"` |
| `orchestrator.sh:181` | `AGENT_KIND` defaulted to `ok` | Empty/failed result committed as success |
| `run_builder.sh:170` | `return 0` unconditional | Hard stop retried 366× |
| `tmux_orchestrator.sh:211` | `touch` before `tail -f` | Fabricated log freshness |
| main loop | no consecutive-failure counter | 62 identical failures, no halt |

The `grep -c` bug is one shape repeated four times. On an empty file `grep -c .`
prints `0` **and** exits 1, so `|| echo 0` also fires. Use `wc -l`:

```bash
N="$(wc -l < "$f" 2>/dev/null | tr -d ' ')"; N="${N:-0}"
```

---

## Why it wasn't caught

`ops/orchestrator.test.sh` did contain the exact buggy line — but only ever ran
it against a ledger with **one row**. The empty-file path, the only one that
triggers the bug, was never exercised. 53 tests passed while the bug shipped.

Regression test added: an empty snapshot must count as `0` and must survive a
numeric test.

---

## Guardrails added

**`ops/preflight.sh`** — runs before any spend, exits non-zero to block the
builder. `run_builder.sh` calls it automatically (`SKIP_PREFLIGHT=1` to bypass).

Checks: token shape and whether it shadows the subscription · one real cheap
`claude -p` round trip · the `grep -c` bug is absent · `claude -p` is wall-clock
bounded · circuit breaker present · locks live-vs-stale by pid · queue readable ·
cumulative spend.

**Circuit breaker** — `CONSEC_ERR_MAX` (default 3). Three consecutive issues with
no commits halts the pass, prints the last 3 lines of the agent log, and points
at preflight. A systemic fault fails every issue identically, so the third one is
already proof it is not issue-specific.

**Timeout** — `AGENT_TIMEOUT` (default 1800s). `timeout`/`gtimeout` are not on
this machine; `perl -e 'alarm shift; exec @ARGV'` is and needs no dependency.

---

## Recovery checklist

```bash
# 1. Prove the toolchain. Never skip this.
./ops/preflight.sh

# 2. Stale locks (preflight tells you which)
rm -rf ops/.builder.lock ops/.worktree.lock

# 3. True spend — the in-loop bar is per-pass and lies
python3 ops/usage.py report --all

# 4. Only then
./ops/run_builder.sh
```

Do **not** use `--loop` unattended until the propagated exit codes have been
watched through at least one real hard-stop.

---

## What must not be simplified away

The audit found much to cut, but these earned their place and are load-bearing:

1. **Nothing merges without a human.** No auto-merge, ever.
2. **Refuse to build when an open PR exists** for the branch
   (`gh pr list --state open --head`). This demonstrably prevented force-pushing
   over review history on KCH-84/85.
3. **Refuse to `checkout -B` over unpushed commits.** `feature/kch-109` holds 17
   unpushed commits ($3.05 of work) and this guard is why they still exist.
4. **One builder at a time.**
5. **A gate that cannot run is not a pass** — `gate=2` must never read as clean.

Counter-evidence, stated plainly: 20 of 144 issues did ship and merge bottom-up
in 5 days, and `git log --merges origin/development` shows 22 merges. The
machinery mostly works. What failed was composition — no preflight, no circuit
breaker, no timeout, and a budget that resets.
