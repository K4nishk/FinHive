# Developer Agent Operating Contract

Canonical source: [ARD §18 — The Agentic Development Loop](../output/Loan%20Manager/mvp2/mvp2_ard_v2.0.0.md#18-the-agentic-development-loop).
This document restates that section as an operating contract and points to where it is
enforced in code. If the two ever disagree, the ARD is the design record and this file
is stale — fix this file.

Applies to any agent — orchestrator-driven (`ops/orchestrator.sh`) or interactive —
implementing a `KCH-*` Linear issue in this repository.

## The loop

1. **Branch** — `feature/<issue-key>` (lowercase, e.g. `feature/kch-80`), cut from the
   tip of `development` (or from the current stack tip — see Stacked PRs below).
2. **Implement** — the smallest correct change for the issue, with tests. No unrelated
   refactors, no scope creep.
3. **Test** — run the full test suite before every commit. Do not commit with failing
   tests.
4. **CodeRabbit CLI gate** — run before pushing: `coderabbit review --committed --base
   <base>`. Blocking findings return to the agent; advisory findings do not block. A
   blocking finding must be resolved (or escalated, below) before the branch is pushed
   or a PR is opened — never push a revision the gate hasn't cleared.
5. **Push, open a PR** targeting `development` (or the branch it stacked on), once the
   gate has no blocking findings.
6. **Fix cycles — maximum two.**
   - No blocking findings → ready for human review.
   - Cycle 1: fix the blocking findings, re-run the test suite, re-run the gate.
   - Cycle 2: if findings persist, fix again, re-run the test suite, re-run the gate.
   - Still blocking after cycle 2 → **escalate** (below). Do not attempt a third cycle.
   - Only push (or push an update) once a cycle ends with no blocking findings.
7. **Human merges.** The agent never merges. It opens PRs (and marks one draft on
   escalation); a human approves and merges to `development`.

## Escalation payload

After two failed cycles the agent stops and files a Linear issue containing:

- The **blocking finding**, verbatim, that persisted through both cycles.
- **Every fix attempted** — what changed, and specifically why it was rejected or
  failed (a test failure, a regression, a finding that came back).
- **Why this needs a human** — the reason no further automated attempt is likely to
  help (usually: the fix requires a decision above the agent's authority, e.g. an
  architecture or security-policy change).
- A **suggested direction** — one or more concrete options for a human to choose
  between, not just "needs investigation."

Example, from the ARD:

```markdown
## Escalated from FIN-42 (PR #128)

**Blocking finding (persisted through 2 fix cycles)**
CodeRabbit: "Potential N+1 query in `get_portfolio_summary` —
`resolve_borrower` called inside a loop over 200 rows."

**Attempt 1** — Added `functools.lru_cache` to `resolve_borrower`.
Rejected: cache is per-process; serverless cold starts make hit
rate ~0. Finding persisted.

**Attempt 2** — Batched with `WHERE borrower_id = ANY($1)`.
Rejected: broke RLS — the batch query bypassed the per-row
policy check. Integration test `test_rls_isolation` failed.

**Why this needs a human**
The fix requires an RLS policy change (adding a security-definer
function for batch reads). That is an architecture decision above
this agent's authority.

**Suggested direction**
Either (a) a `SECURITY DEFINER` function with an explicit org_id
guard, or (b) denormalize borrower_name onto the summary mart in
dbt and drop the join entirely. (b) is likely simpler.
```

The PR is marked **draft** on escalation — it is not ready for human review, the
escalation issue is.

## Why two cycles, not more

Cycle 1 catches mechanical issues. Cycle 2 catches a wrong first fix. A third cycle
almost always means the blocker is a design constraint the agent cannot see, and
burning more rounds on it is waste, not progress. Same bounded-retry philosophy as the
ReAct loop (ARD §11): **fail fast, escalate with context.**

## Stacked PRs

`development` is the integration base and is always the eventual target. Feature
branches may stack on each other's unmerged work rather than each cutting fresh from
`development` — this keeps `main` always-deployable while letting an agent build on a
sibling branch that hasn't merged yet. A release PR promotes `development` → `main`.
Review and merge a stack **bottom-up**; merging out of order leaves a child PR's base
retargeted mid-review.

## Where this is enforced

- `ops/orchestrator.sh` — the build loop: branch → implement → CLI gate → fix cycles
  (`CR_MAX_ROUNDS`, default 2) → escalate-or-PR. Never merges.
- `ops/pr_gate.sh` — publishes the CLI gate's round-by-round trail as a PR comment and
  sets the `coderabbit/cli-gate` commit status, so the gate's result is visible on
  GitHub and can be made a required check.
- `ops/README.md` — operational rules for running the toolchain (locking, worktree
  safety, review surfaces). This contract describes *what* the loop must do; that file
  describes *how to operate it safely*.

Nothing in this loop merges a PR without a human. The agent's authority ends at
"ready for review" or "escalated."
