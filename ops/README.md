# ops/ — development orchestration

Supervised autonomous development: agents implement Linear issues in dependency order
and open stacked PRs, CodeRabbit reviews every branch. **Nothing merges without you.**

| File | Role | Status |
|---|---|---|
| `tmux_orchestrator.sh` | the attended cockpit — build, review, queue, repo, test panes | ✅ built |
| `seed_linear.py` | parses `linear_import.csv` → creates Linear issues (idempotent) | ✅ built |
| `orchestrator.sh` | the build loop: implement → CodeRabbit gate → mediate → PR | ⬜ ticketed |
| `run_builder.sh` | guard wrapper: skips if running / in flight / queue done | ⬜ ticketed |
| `pr_gate.sh` | publishes the CLI gate's findings trail and sets `coderabbit/cli-gate` | ✅ built |
| `orchestrator.test.sh` | ledger + phase-selection tests for the loop | ✅ built |
| `pr_gate.test.sh` | unit tests for the gate publisher's pure helpers | ✅ built |
| `remediate_prs.sh` | answers CodeRabbit's PR comments in place | ⬜ ticketed |
| `review_sweeper.sh` | settles deferred reviews from the debt ledger | ⬜ ticketed |

State (all gitignored): `.completed_issues` · `.review_debt.tsv` · `.issue_map.tsv` ·
`queue.tsv` · `.env.local` · `logs/` · `.builder.lock/` · `.worktree.lock/`

---

## First run

```bash
gh auth login                       # scopes: repo, workflow
coderabbit auth login
```

Put credentials in `ops/.env.local` (gitignored — every tmux pane sources it):

```bash
export LINEAR_API_KEY="lin_api_..."
export LINEAR_TEAM_KEY="FIN"        # the issue-id PREFIX, not the team name
```

Seed Linear, then open the cockpit:

```bash
python3 ops/seed_linear.py          # dry run first — always
python3 ops/seed_linear.py --apply
./ops/tmux_orchestrator.sh
```

---

## The cockpit

```bash
./ops/tmux_orchestrator.sh              # create + attach
./ops/tmux_orchestrator.sh --status     # read-only; starts nothing
./ops/tmux_orchestrator.sh --detached   # create without attaching
./ops/tmux_orchestrator.sh --kill       # kill session, leave locks
./ops/tmux_orchestrator.sh --reset      # kill session AND clear stale locks
```

Six windows: `build` (orchestrator + live log) · `review` (three surfaces + open PRs) ·
`queue` (status + Linear) · `repo` (git + stack depth) · `test` (pytest, Playwright,
e2e personas) · `shell`.

Detach `Ctrl-b d` · switch `Ctrl-b <n>`.

The session refuses to start with uncommitted changes in `ops/` — see rule 1.

**tmux vs launchd**: this is the *attended* path, for when you want to watch and
interrupt mid-issue. A launchd loop is the unattended overnight path. Both drive the
same `orchestrator.sh`.

---

## Rules learned the hard way — do not relax

Carried from `AssetAuditor/ops`. Each cost a real session.

1. **Never launch with uncommitted changes in `ops/`.** The orchestrator's first
   `git reset --hard` restores the last *committed* toolchain and deletes untracked
   scripts — every safety property added since vanishes without a word.
   `tmux_orchestrator.sh` refuses to start in this state.
2. **Lock directories must stay gitignored.** `git clean -fd` removes untracked
   *directories*, and the loop runs it two lines after taking `.worktree.lock` — an
   unignored lock deletes itself and mutual exclusion silently stops working.
3. **Every worktree toucher takes `ops/.worktree.lock`.** All panes share one checkout;
   two `git checkout`s at once move the branch under a running agent.
4. **Merging a PR while the build runs deletes the base out from under it.** GitHub
   removes the branch on merge and `gh pr create` then fails with "Base ref must be a
   branch". Review the stack **bottom-up**, and expect the branch under the in-flight
   issue to move.
5. **Scripts that rewrite their own worktree must re-exec from `$TMPDIR`.**

---

## Models

| Env | Default | Used by |
|---|---|---|
| `IMPL_MODEL` | `claude-sonnet-5` | implementing agent · CodeRabbit fix rounds |
| `MEDIATOR_MODEL` | `claude-opus-5` | mediator only — adjudicating disputed findings |

Implementation works against a spec that already exists and burns most of the tokens, so
it runs on the cheaper tier. Mediation is a judgement call a human reads later, so it
keeps the stronger model. Override per run: `IMPL_MODEL=claude-opus-5 ./ops/run_builder.sh`.

Other knobs: `CR_MAX_ROUNDS` (2) · `MAX_TURNS` · `LOCAL_CHECKS` · `SKIP_KILL_GATE`.

---

## The three review surfaces

Passing one does not answer the others.

1. **CLI gate** (pre-push, inside `orchestrator.sh`) — blocking findings return to the
   agent up to `CR_MAX_ROUNDS`, then a mediator fixes, dismisses with rationale, or
   escalates to a new Linear issue carrying every attempted fix and why it failed.
2. **SaaS PR review** (`remediate_prs.sh`) — answers comments posted after a PR opens.
   Pushes to the **same branch**, so the stack never deepens.
3. **Deferred** (`review_sweeper.sh`) — when CodeRabbit's quota runs dry the build does
   not wait; debt is banked and settled later.

A green `coderabbit/cli-gate` means *no **blocking** findings* — not *no findings*. Read
the round detail in the PR comment for the rest.

### Publishing the CLI gate result

The CLI gate runs pre-push inside `orchestrator.sh`, so from GitHub's side its result
is just a claim — the findings sit in gitignored logs under `ops/logs/`. Run
`ops/pr_gate.sh ISSUE` to re-publish that trail as evidence on the PR: every round's
blocking findings, the commit that answered each one, and the final round's verdict —
then set the `coderabbit/cli-gate` commit status. Success only when the final round
returned zero blocking findings; no logs at all or a final round that errored/hit quota
both count as failure, not success. No Claude involved — bash, `git`, `gh`, and the logs
already on disk, so it still runs when spend is capped.

### Drafts, re-gating, and clearing the backlog

A PR the builder opens while the gate is unclean opens as a **draft**, and nothing used
to promote it afterwards — so one bad gate left the PR a draft forever. `pr_gate.sh`
now clears the draft itself when the verdict is success (`--no-promote` opts out). A
draft is a statement about the gate, never a stale flag.

```bash
ops/pr_gate.sh KCH-78              # publish the trail, set the status, clear the draft if clean
ops/pr_gate.sh --regate KCH-78     # re-review the WHOLE branch vs development first
ops/pr_gate.sh --stack             # walk every open PR bottom-up, stopping at the first blocked one
```

`--regate` exists because the builder reviews each branch against the branch *below* it
— the right diff while stacking, but it means the bottom PR's full contents are never
reviewed as one unit. It reviews `feature/<issue>` against `development` and **appends**
a round rather than overwriting one, so the fix history survives. It runs in a
throwaway **detached** worktree, so it is safe while a build is in flight: the shared
checkout is untouched, and leaving the branch unclaimed keeps the builder's own
`git checkout` of it from failing with "already used by worktree".

`--stack` stops at the first PR whose gate is not clean. That is deliberate — a stack
merges bottom-up, so a blocked PR blocks everything above it and publishing the rest is
noise.

Make the check required, once, with admin access to the repo (needs branch protection
already enabled on `development`):

```bash
ops/pr_gate.sh --require-check
```

---

## Review debt — cleared before any new feature

`ops/.review_debt.tsv` holds issues whose **PR is open but whose gate is not clean**:
quota, a dropped review, or blocking findings that survived. A pass drains it first,
before it touches the queue.

That ordering is not cosmetic. The stack merges bottom-up, so one unclean PR near the
bottom blocks everything above it no matter how many features get built on top —
building more only makes the eventual merge walk longer.

Debt is **remediated in place, never rebuilt**. `remediate_issue()` checks out the
existing branch (fast-forward only), feeds the last round's findings to the agent,
commits `fix(ISSUE): address CodeRabbit round N`, re-gates against the **PR's own
base**, and pushes to the same branch. The PR updates; the stack does not deepen and
the review trail survives.

Two guards keep an open PR from being overwritten:

- `run_issue` refuses an issue that already has an open PR and banks it as debt.
- A PR that opens with an unclean gate is banked as debt immediately, instead of
  being left unrecorded — which used to make the next pass treat it as unbuilt and
  rebuild it from scratch over the PR. KCH-84 and KCH-85 sat one pass away from
  exactly that.

```bash
cat ops/.review_debt.tsv                        # what is queued
DEBT_ONLY=1 ./ops/run_builder.sh                # clear debt, then STOP before the queue
ops/pr_gate.sh --regate KCH-84                  # re-review one PR by hand
```

`DEBT_ONLY=1` matters more than it looks. Without it a pass drains the debt and
carries straight on into the queue until 95% of the budget — roughly fourteen more
issues at the default — stacking new PRs on top of the stack you just made mergeable.
Use it whenever the intent is "unblock the stack, then merge".

---

## Reviewing a stack

**Approve and squash-merge strictly bottom-up.** The first PR targets `development`, the
next targets that PR's branch, and so on. GitHub retargets a child as its parent merges.
Out-of-order merges conflict.

Per PR: read the CodeRabbit verdict → check escalated issues → sanity-check the four
things a tool misses (**unmasked text reaching an LLM**, **unparameterised SQL**,
**floats on money**, **a role check that only hides a button**) → approve → merge.

Those four are FinHive-specific and map to hard rules: PII masking is the control that
keeps personal data in India (ARB OQ-01), raw SQL is only safe parameterised (ADR-2.2),
money is `Decimal`, and authorization is server-side because *the UI hides what RLS
already refuses*.
