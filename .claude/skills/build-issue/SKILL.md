---
name: build-issue
description: Orchestrate one FinHive KCH-* Linear issue end to end — select, plan, implement, test, review, commit, stack a PR, comment on Linear and report RTK gain. Use when asked to build, implement, start or work an issue, to pick up the next issue, or when running the M1.1 Ask FinHive queue. Also use when deciding which model an agent should run on, whether an issue is blocked, or how to handle work found outside an issue's scope.
---

# Build one issue — FinHive orchestrator contract

**The interactive session is the orchestrator. It delegates and does not implement.**

Scope: `docs/MVP1_1_ASK_FINHIVE.md`. Issues:
`output/Loan Manager/mvp1.1/linear_import.csv`, row order = build order.
Decisions: `output/Loan Manager/mvp2/ARB_DECISIONS.md` — read the M1.1 block before
starting anything; several are conditional and one (D-17) is deliberately unresolved.

**CodeRabbit is gone.** The free tier ended; `coderabbit usage` exits non-zero. Every
gate that used to be CodeRabbit is now a `reviewer` subagent plus the human. Do not
call `coderabbit`, and never treat its absence as a passing gate — a gate that did not
run is a failure, not a pass.

---

## Roles and models

Pick the cheapest model that can do the job. Spawning a reasoning model for a
mechanical edit burns budget for nothing; spawning Sonnet to adjudicate a rule
conflict buys a confident wrong answer.

| Role | Model | Does | Never |
|---|---|---|---|
| **Orchestrator** | `claude-opus-5` | Selects, decomposes, spawns, adjudicates, gates, writes the Linear comment | Writes product code |
| **planner** | `claude-opus-4-6` | Reads the issue and the real files; produces the change list with `file:line` | Edits anything |
| **reviewer** | `claude-opus-4-6` | Adversarial review against the gate below | Fixes what it finds |
| **implementer** | `claude-sonnet-4-6` | Writes code and tests to the planner's list | Re-plans, widens scope |
| **tester** | `claude-sonnet-4-6` | Runs suites, writes regressions, pastes real output | Marks a failing suite green |
| **scribe** | `claude-haiku-4-5-20251001` | Commit messages, PR bodies, Linear comments, doc summaries | Decides anything |

One planner and one reviewer per issue. Implementers may run in parallel **only**
across files that do not import each other.

**Skip the planner** on a genuinely mechanical issue (a rename, a config line, a
one-file fix) where the change list is obvious from the issue text. Spawning one to
restate the ticket is the waste Ponytail rejects.

---

## Doctrines

### Ponytail — stop at the first rung that holds

YAGNI → reuse → stdlib → native → existing deps → minimal → necessary.

Every planner output names its rung. **Rung 2 (reuse) is the default answer here,
not rung 7.** This repo already has: the SQLAlchemy data layer, `ReferenceIdService`,
`StatusEngine`, `InterestCalculator`, the `reports`/`report_records` proposal batch,
and `finhive/db/` for encryption, key derivation and blind indexing.

Measured cost of ignoring this: the original MVP1.1 plan budgeted **14.5 days**
rebuilding what already existed, because it was written from `input/REQUIREMENTS.md`
instead of from `src/`.

### Caveman — why use many token when few token do trick

Dense prompts, dense reports. Compress the prose; **never** compress code, commands,
paths, identifiers or error strings — those are reproduced exactly. Report honest
measurements including ones that cut against the thesis.

### RTK — compress before it reaches the context

`rtk` is installed. Wrap every command whose output reaches a context:

```
rtk test <cmd>   rtk err <cmd>   rtk git diff   rtk git status
rtk read <file>  rtk find …      rtk psql …     rtk docker …
```

**The saving is entirely working-tree dependent — never quote a fixed number.**
Measured on this repo across runs minutes apart: `git status` −39% to −55%,
`git diff` −2% to −14%, overall **−3% to −30%**. On a clean tree the framing can
exceed the output. Far below RTK's advertised 60–90%, because a code diff is mostly
lines it cannot compress.

RTK is not a substitute for judgement. Never pipe raw output into a subagent prompt
even wrapped: pass the failing lines, not the whole log; the diff, not the file;
`file:line` plus the function, not the module. The M0 ledger measured a **122:1
context re-read ratio** — roughly half the bill was agents re-reading `CLAUDE.md`,
the WIKI and the tree from zero. A subagent prompt that restates the repo is that
bill, and `rtk` will not save you from it.

---

## The loop

### 1. Select

The lowest unbuilt row whose hard blockers are resolved. Read the issue in full.

### 2. Verify the premise before writing anything

**Non-negotiable, and the most valuable step here.** Issue descriptions go stale and
plans get written from the wrong document. Before implementing, confirm the thing
the issue says is missing is actually missing:

```
rtk find . -name '<the module it says to create>'
grep -rn '<the function it says to write>' src/ finhive/
```

Precedent: KCH-226 read "load the master key from the environment" — `load_key_ring`
already did exactly that, with 21 tests. The real gap was an integration blocker no
issue covered. **If the premise is wrong, stop and say so.** Do not improvise, and
do not build the thing anyway.

### 3. Plan — `planner`

Ordered change list with `file:line`, the Ponytail rung, what is reused, and the
acceptance test. If the issue's premise is wrong it says so and stops.

### 4. Implement — `implementer`

On `feature/kch-NNN` branched from the stack tip.

**Branch carefully.** Stash unrelated work with a labelled message first; a failed
checkout that half-switches the tree is recoverable but costs a turn. Verify
`git status` is clean before switching.

### 5. Test — `tester`

Full MVP1 suite plus the issue's own tests. **Real output pasted, never a summary of
intent.** A suite that skips everything is not a passing suite — say what ran.

### 6. Review — `reviewer`

Adversarially, against the gate below. Findings return to the implementer for at
most **two** cycles. A third means the issue is under-specified: stop, comment on
Linear, escalate to the human.

Brief the reviewer with what changed and what to attack, not with the whole repo.
Tell it to verify the central claim independently — reviewers have caught claims
that were true-sounding and wrong, including an acceptance criterion that was never
implemented.

### 7. Commit and stack

Scribe writes the message. **Stage explicitly — never `git add -A`**, which sweeps
up `data/loans.db` and `.DS_Store`. Scan the staged diff for secrets before
committing. Open the PR against the branch below it, never `development` directly
(it is protected; direct pushes are rejected).

### 8. Comment on Linear

Scribe posts, verbatim:

> Development and testing completed, awaiting PR review and merge.

plus the PR link, the suites that ran with their real counts, and the RTK Gain block.

### 9. Report RTK gain

```
python3 ops/rtk_gain.py --issue KCH-NNN --measure-gates
```

Non-optional. Axis A is measured on this machine by running the gate commands both
ways; Axis B is agent tokens billed, from `ops/logs/usage.jsonl`. **If the number is
degenerate — a clean tree, or no metered calls because the work was done in-session —
say so rather than dressing it up.**

---

## Review gate

A PR may open only when all of these hold, each proven by pasted output:

- Full MVP1 suite green — `cd "src/Loan Manager" && rtk test python -m pytest tests/`
  Postgres/crypto tests must **skip** cleanly when their dependency is absent, never
  fail: CI runs whole test directories. Do NOT count on CI to block a bad merge —
  `mvp1-regression` is only *documented* as required (`docs/AGENT_CONTRACT.md`); as
  of 2026-09-24 GitHub requires no status checks, so a red PR can still merge
- Run the lane the way CI does: `pytest tests/unit` needs `lint-imports` on `PATH`
  (`PATH=.venv_pg/bin:$PATH`), or `test_import_boundaries` silently skips. A test
  that only ever skips locally has never been checked by anyone
- `TEST_DATABASE_URL` points at a disposable database, never the dev one
- `rtk err ruff check <changed files>` clean
- The issue's own acceptance test exists and **fails without the change**
- No layer violation: `domain/` imports no `infrastructure`/`presentation`/PySide6/
  sqlalchemy; `application/agent/` imports no PySide6, sqlalchemy, sqlite3 or
  mutating use case
- No raw SQL outside `migrations/` (ARB D-1a keeps D-1's parameterised-only rule)
- No `float` for money; no `datetime.utcnow()`; no hardcoded hex in `presentation/`;
  no `QTableWidget` for new data tables
- **No plaintext NPI** — a direct `SELECT` over changed tables shows no borrower or
  depositor name, group, or amount (principal *or* derived) in clear (ARB D-15)
- **No blind index on any amount column** — amounts cluster on round numbers, so a
  deterministic index over them is reversible by frequency analysis without the key
  (ADR-2.4, KCH-99)
- No secret, key or token added to a tracked file

---

## Stacking and blocking

PRs stack; **an unreviewed PR never blocks the next issue.** Branch the next issue
from the previous branch's tip, PR against it, and let the human merge bottom-up.

A **hard blocker** — the only thing that stops the queue — is when the next issue
cannot begin until the previous is fully resolved:

| Blocked | Blocker | Why |
|---|---|---|
| anything writing NPI | master key source | Encrypting with a key that vanishes next launch is data loss |
| blind index · dev fixture · anything reading NPI | encryption at the boundary | The `_ct` columns must be readable first |
| EntityResolver | encryption at the boundary | The index is built from decrypted names |
| READ tools · loop | tool arg models | The registry is their call contract |
| loop | LLM client | Nothing to call |
| tool schemas | the D-4a provider spike | Schemas built against an endpoint that cannot call them are the expensive half to undo |
| Ask FinHive tab | loop · dev fixture | Nothing to stream, and nothing to stream about |
| PROPOSE tools · approvals tab | report-batch schema | The columns must exist |
| real-data migration | the tab working on seeded data | Deliberate: exercise the encryption path for weeks before real data touches it |
| eval suites | fixture + harness | No ground truth without it |

Everything else proceeds. When a hard blocker is unresolved, work the next unblocked
row — do not idle, and do not start the blocked issue "partially".

---

## Technical debt

Debt is not deferred silently. When work outside the issue's scope is found:

1. Fix it in-issue **only** if it is a one-line correctness fix and the issue already
   touches that file.
2. Otherwise file a Linear issue immediately, in the same session, with
   `product:finhive` and the `file:line` — and link it from the PR body.
3. Never leave a `TODO` in the code as the record. The tracker is the record.

An issue is not complete while its own acceptance test is skipped, xfailed, or
asserting something weaker than the acceptance line.

---

## Creating issues

Invoke the `write-linear-issue` skill first — it carries the labelling, project and
estimate conventions. FinHive specifics live in the `loan-manager-conventions` skill
under Linear.

M1.1 issues are generated: edit `ops/gen_m11_csv.py`, not the CSV. The seeder is
idempotent **by title**, so changing a title creates a duplicate rather than editing
the original — existing issues need their titles and descriptions updated by hand.
