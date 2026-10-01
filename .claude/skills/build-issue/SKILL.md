---
name: build-issue
description: Build one FinHive KCH-* Linear issue end to end in a single session — select, plan, implement, test, review, commit, stack a PR, comment on Linear and report RTK gain. Use when asked to build, implement, start or work an issue, to pick up the next issue, or when running the M1.1 Ask FinHive queue. Also use when deciding which model an agent should run on, whether an issue is blocked, or how to handle work found outside an issue's scope.
---

# Build one issue — FinHive per-issue workflow

**One Sonnet session per issue builds it end to end** (CLAUDE.md, Agent and model
policy). Opus is called in only for an unclear plan or a security-critical review.

Scope: `docs/MVP1_1_ASK_FINHIVE.md`. Issues:
`output/Loan Manager/mvp1.1/linear_import.csv`, row order = build order.
Decisions: `output/Loan Manager/mvp2/ARB_DECISIONS.md` — read the M1.1 block before
starting anything; several are conditional and one (D-17) is deliberately unresolved.

**CodeRabbit is removed** (2026-09-25): the GitHub App is uninstalled and
`.coderabbit.yaml` deleted. Every gate that used to be CodeRabbit is now a `reviewer`
subagent plus the human. Do not call `coderabbit`, and never treat its absence as a
passing gate — a gate that did not run is a failure, not a pass. CI's required checks
(`Fast gates`, `MVP1 regression`, `Postgres integration`) are enforced by the repo
ruleset on `development` and `main`.

---

## Roles and models

Measured on MVP1.1: a planner + implementer + tester + reviewer + scribe fleet spent
≈1M tokens on one UI tab, mostly agents cold-reading the same code. The policy below
replaces it (owner decision 2026-10-01).

| Role | Model | When |
|---|---|---|
| **Builder** — reads, plans, codes, tests, commits, writes the PR and Linear note | Sonnet (the session itself) | Every issue |
| **Planner** — change list with `file:line` | Opus | **Only** when the plan is unclear: suspect premise, more than one sane cross-layer design, or conflicting ARB decisions |
| **Reviewer** — adversarial review | Opus | **Only** for security-critical changes: encryption/keys/`_ct`, tokeniser or anything sent to an LLM, agent tool permissions (READ/PROPOSE), raw SQL/migrations, real `data/loans.db` |

- No separate tester or scribe agents; no parallel agents unless the owner asks.
- After an Opus review: **at most one** fix cycle, then stop and ask the owner.
- Brief any Opus agent with `file:line` and the diff, never the repo.

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

### 3. Plan — yourself; Opus planner only if unclear

Ordered change list with `file:line`, the Ponytail rung, what is reused, and the
acceptance test. If the issue's premise is wrong, say so and stop.

### 4. Implement

On `feature/kch-NNN` branched from the stack tip.

**Branch carefully.** Stash unrelated work with a labelled message first; a failed
checkout that half-switches the tree is recoverable but costs a turn. Verify
`git status` is clean before switching.

### 5. Verify — the `verify-change` skill, steps 1–4

Fail-first proof, CI-parity gates, self-review checklist. **Real output pasted, never
a summary of intent.** A suite that skips everything is not a passing suite.

### 6. Review — Opus only if security-critical

Brief the reviewer with what changed and what to attack, not the repo; tell it to
verify the central claim independently. One fix cycle at most, then the owner decides.
Not security-critical: your step-5 self-review is the review; the human reviews the PR.

### 7. Commit and stack — `verify-change` steps 5–6

Stage named paths, scan, commit, open the PR **ready for review** against the branch
below it (lowest open PR → `development`).

### 8. Comment on Linear

Post (or write to `ops/linear/YYYYMMDD/kch-NNN.md`), verbatim:

> Development and testing completed, awaiting PR review and merge.

plus the PR link, the suites that ran with their real counts, and the RTK Gain block.

### 9. Report RTK gain

```
python3 ops/rtk_gain.py --issue KCH-NNN --measure-gates
```

Non-optional. Axis A is measured on this machine by running the gate commands both
ways; Axis B is agent tokens billed, from `ops/logs/usage.jsonl`. Nothing has written
that ledger since the orchestrator was deleted (2026-09-25), so Axis B is empty for
an in-session build. **If the number is
degenerate — a clean tree, or no metered calls because the work was done in-session —
say so rather than dressing it up.**

---

## Review gate

A PR may open only when every step of the `verify-change` skill has passed with
pasted evidence, and the issue's own acceptance test exists and **fails without the
change**. The checklist (layers, raw SQL, money, NPI at rest, amount blind index,
secrets) lives there, once.

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
