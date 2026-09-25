# ops/ — project tooling

Standalone scripts for issue tracking and measurement.

The unattended build loop that used to live here — `orchestrator.sh`,
`tmux_orchestrator.sh`, `run_builder.sh`, `pr_gate.sh`, `preflight.sh` and their
tests — was **deleted on 2026-09-25**. Its review gate was the CodeRabbit CLI, which
stopped working when the free tier ended, and CodeRabbit was removed from the repository
the same day. Issues are now built interactively with the `build-issue` skill, gated by
a `reviewer` subagent plus you.

To read or recover the loop, it is intact in `d9b6a44` and every commit before it:
`git show d9b6a44:ops/orchestrator.sh`. How it failed, and what that taught, is recorded
in `docs/ORCHESTRATOR_RECOVERY.md`.

| File | Role |
|---|---|
| `seed_linear.py` | parses a `linear_import.csv` and creates Linear issues; idempotent by title. `--write-queue` writes `ops/queue.tsv` in build order |
| `gen_m11_csv.py` | emits `output/Loan Manager/mvp1.1/linear_import.csv`, the M1.1 build order. Edit this, not the CSV |
| `rtk_gain.py` | the per-issue RTK gain report (build-issue step 9). Axis A is currently degenerate — KCH-254 |
| `probe_openrouter.py` | tool-calling probe against OpenRouter models (ARB D-4a) |
| `usage.py` | the metered-call ledger (`ops/logs/usage.jsonl`) that `rtk_gain.py` reads for Axis B |

## Credentials

`ops/.env.local` (gitignored) holds `LINEAR_API_KEY`, `LINEAR_TEAM_KEY`,
`OPENROUTER_API_KEY`, `FINHIVE_KEY_VERSION` and `FINHIVE_MASTER_KEY_V1`.

**Keep a trailing newline.** Appending with `>>` to a file that does not end in one glues
the new line onto the last, corrupting that variable. On 2026-09-25 this turned
`OPENROUTER_API_KEY` into its real value followed by `export`, which loads fine and
fails later with a 401.

## Stacked PRs

Merging a PR deletes its branch, and GitHub retargets the PR stacked on it onto that
PR's base.

- Review and merge a stack **bottom-up**.
- After a merge, do not re-run `gh pr create` for the PR above: it already exists and
  has been retargeted, so the command fails with "Base ref must be a branch".
