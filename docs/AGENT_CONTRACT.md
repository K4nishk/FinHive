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
   blocking finding must be resolved before a normal branch push or PR — never push a
   revision the gate hasn't cleared. The one exception is the escalation draft PR
   (below), which is allowed to carry a blocking finding precisely because it is not a
   normal push.
5. **Push, open a PR** targeting `development` (or the branch it stacked on), once the
   gate has no blocking findings.
6. **Fix cycles — maximum two.**
   - No blocking findings → ready for human review.
   - Cycle 1: commit the fix, record the commit SHA and the gate output, re-run the
     test suite, and re-run the gate.
   - Cycle 2: if findings persist, repeat — a new commit, re-run the test suite,
     re-run the gate — and retain both cycles' gate results.
   - Still blocking after cycle 2 → **escalate** (below). Do not attempt a third cycle.
   - Only push (or push an update) once a cycle ends with no blocking findings.
7. **Human merges.** The agent never merges. It opens PRs (and marks one draft on
   escalation); a human approves and merges to `development`.

## Escalation payload

After two failed cycles the agent stops and files a Linear issue containing:

- The **blocking finding**, verbatim, that persisted through both cycles.
- **Every fix attempted** — the commit SHA, what changed, the gate result it produced,
  and specifically why it was rejected or failed (a test failure, a regression, a
  finding that came back). This is why step 6 requires a commit and a retained gate
  result per cycle — a no-change re-review must not count as a completed cycle, and the
  evidence must survive to the escalation issue.
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

On escalation the agent may push once more and open **one draft PR**, to preserve the
attempted work and give the escalation issue something concrete to link to — this is
the sole exception to "never push a revision the gate hasn't cleared" in step 4. The
draft PR remains blocked: it cannot merge and does not count as a cleared gate. It is
not ready for human review — the escalation issue is.

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

## Branch protection

`main` must stay always-deployable, so nothing lands on it except a release PR that
has cleared every gate and one human approval — no direct pushes, no admin bypass.
This is a one-time repo-admin action (same category as `gh auth login` in
`ops/README.md`), applied once via `gh api` and not re-run per PR:

```bash
# Resolve the GitHub Actions app's id instead of hardcoding it -- pinning a
# guessed constant into this doc would be worse than not binding at all if it's
# ever wrong. Look it up at apply time:
GH_ACTIONS_APP_ID="$(gh api apps/github-actions --jq '.id')"

gh api "repos/$OWNER/$REPO/branches/main/protection" -X PUT --input - <<JSON
{
  "required_status_checks": {
    "strict": true,
    "checks": [
      { "context": "Fast gates", "app_id": $GH_ACTIONS_APP_ID },
      { "context": "MVP1 regression", "app_id": $GH_ACTIONS_APP_ID },
      { "context": "coderabbit/cli-gate", "app_id": null }
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": { "required_approving_review_count": 1 },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
```

The three contexts must match what CI actually publishes: `"Fast gates"` is the
`fast-gates` job's display name in `.github/workflows/ci.yml`, `"MVP1 regression"` is
the `mvp1-regression` job's display name in the same file — it runs the full MVP1
suite (150 unit/integration tests plus 22 smoke tests) against `src/Loan Manager` on
every PR regardless of changed paths, so a deliberate break in MVP1 domain code blocks
an unrelated MVP2 PR (KCH-88) — and `"coderabbit/cli-gate"` is `GATE_CONTEXT` in
`ops/pr_gate.sh` — the status the CLI gate publishes per PR (see `ops/pr_gate.sh
--require-check`, which appends that context to an existing protection rule rather
than creating one). If any name changes, this block must change with it;
`tests/unit/test_branch_protection.py` pins all three names so a rename doesn't
silently desync the documented command from what CI/the gate actually report.

`checks[].app_id` (not the legacy `contexts` list) is what actually binds a required
context to its publisher, so an unrelated app can't satisfy the same context name.
`"Fast gates"` and `"MVP1 regression"` both run as GitHub Actions jobs, so both are
bound to the GitHub Actions app's id, resolved at apply time rather than hardcoded.
`"coderabbit/cli-gate"` is
deliberately left unbound (`app_id: null`, meaning "any app") because `ops/pr_gate.sh`
currently publishes it via a human- or agent-authenticated `gh auth login` session
(`ops/orchestrator.sh` checks `gh auth status`), not a distinct GitHub App — a PAT-created
status has no app identity to bind to. The residual mitigation is that creating a commit
status already requires push/write access to the repo, so this isn't open to arbitrary
third parties, but the gap stays open until `pr_gate.sh`'s status-setting step runs under
a machine identity (e.g. a GitHub Actions job authenticated with `GITHUB_TOKEN`) that has
its own app id to bind to.

`development` gets the lighter-weight `--require-check` treatment (§ "Where this is
enforced" below) rather than this full ruleset, since it is the integration branch
agents push feature branches into directly, not the always-deployable one.

## Where this is enforced

- `ops/orchestrator.sh` — the build loop: branch → implement → CLI gate → fix cycles
  (`CR_MAX_ROUNDS`, default 2) → escalate-or-PR. Never merges.
- `ops/pr_gate.sh` — publishes the CLI gate's round-by-round trail as a PR comment and
  sets the `coderabbit/cli-gate` commit status, so the gate's result is visible on
  GitHub and can be made a required check.
- `.coderabbit.yaml` — the repo-root config the CodeRabbit GitHub App and CLI both read:
  path filters, per-layer review instructions restating CLAUDE.md, and
  `reviews.request_changes_workflow: true`, which turns any actionable SaaS finding
  into a blocking GitHub review rather than an advisory comment — it has no severity
  threshold. Step 4's CLI gate is narrower: it only blocks on
  `CR_BLOCKING` (`critical|major|blocker|high`). A finding the CLI gate would treat
  as advisory can still block the SaaS review.
- `ops/README.md` — operational rules for running the toolchain (locking, worktree
  safety, review surfaces). This contract describes *what* the loop must do; that file
  describes *how to operate it safely*.

Nothing in this loop merges a PR without a human. The agent's authority ends at
"ready for review" or "escalated."
