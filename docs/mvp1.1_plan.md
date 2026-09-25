# MVP1.1 "Ask FinHive" — completion plan (orchestrated)

> **Status: AWAITING REVIEW** (2026-09-25). Answer §8 (open questions), then reply
> `PROCEED` / `PROCEED WITH MODIFICATIONS`. Implementation (W0–W7) does not start
> before that (CLAUDE.md stage gate).

## 1. Context

MVP1.1 = conversational `Ask FinHive` tab on the PySide6 desktop app, governed by
`docs/MVP1_1_ASK_FINHIVE.md`, queue `output/Loan Manager/mvp1.1/linear_import.csv`
(row order = build order), decisions `output/Loan Manager/mvp2/ARB_DECISIONS.md` M1.1
block. Audit of `origin/development` @ `c853a68` (3 Explore agents + 1 Plan agent,
2026-09-25): **only the encryption layer and the D-4a spike are built.** No
`application/agent/`, no `infrastructure/llm/`, no Clock, no fixture, no evals.

Goal: drive every remaining row to merged, gated PRs using the `build-issue` loop —
orchestrator delegates, one planner + one reviewer per issue, parallel implementers
only across disjoint files, stacked PRs, see-it-fail-first, CI-parity test runs.

### Decisions already taken (you, 2026-09-25)

| # | Decision |
|---|---|
| U-1 | **Per-issue branches** `feature/kch-NNN`, one stacked draft PR each; parallel lanes |
| U-2 | **Done = everything**: working tab (≤row 17) + mutation safety (18–22) + real-data migration & evals (23–28) + **D-17 SQL-emission spike** |
| U-3 | **Recorded fakes only** in the cloud — no live LLM calls from agents |
| U-4 | **KCH-100 deferred to M2** (re-milestone; new domain code stays in `loan_manager/domain`) |

## 2. Audit — what exists

| Row / KCH | State | Evidence |
|---|---|---|
| 1 / 222 ARB D-1a, OQ-01 | BUILT | `ARB:205,211` |
| 2 / 226 master key | BUILT | `infrastructure/security/key_provider.py:64-85`; env is `FINHIVE_KEY_VERSION` + `FINHIVE_MASTER_KEY_V<n>` (spec/`ARB:449` drift) |
| 3 / 227 encrypt 9 `_ct` cols | BUILT | `infrastructure/database/models.py:56-151` |
| 4 / 229 blind index | BUILT | `sqlalchemy_loan_repo.py:97-126` exact-only; `get_all_active` needs no `exact` param |
| 10 / 252 D-4a spike | BUILT | PR #36; `qwen/qwen-2.5-72b-instruct`; findings: raw slug, `rate=0.12`, semantic substitution |
| KCH-99 amount-index lint | BUILT | `tests/unit/test_blind_index_lint.py`, `LM/tests/unit/test_blind_index_model_lint.py:97` |
| 5 / 230 + KCH-114 | PARTIAL | no WAL/journal scan, no null-`due_date` round-trip, no raw scan of `loan_history`/`report_records`; `test_encryption_migration_and_rotation.py:412-430` docstring overclaims |
| KCH-105 decrypt-then-sort/sum | PARTIAL | sort only, in `view_tab.py:61-67`; no shared helper |
| 23 / 247 real-data migration | PARTIAL | `infrastructure/migrations/encrypt_existing_rows.py` (verify-before-commit done); missing backup outside `data/`, row counts |
| 6–9, 11–22, 24–28 | NOT BUILT | — |

Live bugs still shipping: **stale status after `ApproveReport`** (`sqlalchemy_loan_repo.py:188-205`
writes dates only; `ReportApproved` has no subscriber); **silent skip on undated extend**
(`calculate_interest.py:57-62` → `approve_report.py:86`).

## 3. Remaining work — one issue each

`LM` = `src/Loan Manager/loan_manager`. Rung = Ponytail rung (2 reuse · 4 native · 5 existing deps · 6 minimal).
KCH ids 239–251, 253 are **inferred** from row order (Q3).

| Row / KCH | Scope (premise corrections vs stale CSV text) | Files | Rung | Hard deps |
|---|---|---|---|---|
| 5 / **230** (+114) | WAL + `-journal` scan; null-`due_date` round-trip; raw `sqlite3` scan of `loan_history`/`report_records` for names **and amounts**; fix overclaiming docstring | new `LM/../tests/integration/test_encryption_at_rest.py` | 2 | — |
| 6 / **231** | `FINHIVE_DB_PATH` (`config.py:6,14`); **WAL connect listener** in `session.py:18-24` (row 17 needs it); seeder through the encrypting repo, `--today`, refuses `data/loans.db`; fixture-constants module (`sharma group`, `iyer chem`/`meera iyer`, `bg10`, undated, future-giving) | `config.py`, `session.py`, new `infrastructure/seed/` | 2 | — |
| 7 / **232** | code half only: pure `queue_sort_key` at `ops/seed_linear.py:204` + test. Re-milestoning = human (Linear unreachable) | `ops/seed_linear.py` | 6 | — |
| 8 / **233** | `Clock` Protocol `application/interfaces/clock.py`, `Container.clock`; 6 use cases take `clock=SystemClock()` kwarg; `ApproveReport` recomputes via `StatusEngine.compute` → existing `bulk_update_status` (`sqlalchemy_loan_repo.py:176`) in the same UoW | 6 use cases, `approve_report.py`, `container.py` | 2 | — |
| 9 / **234** | OpenRouter / `OPENROUTER_API_KEY`, **not Groq**; `openai` dep; recorded fake; `prices.json` in `infrastructure/llm/` (`data/*` gitignored); `LLMPort` in `application/agent/llm_port.py`; fix `settings_tab.py:98-108` saving `{}` on load failure (would wipe `llm`); `llm` pytest marker | `infrastructure/llm/*`, `requirements.txt`, `settings.json`, `settings_tab.py`, `pytest.ini` | 5 | — |
| 11 / **235** | arg models `extra='forbid'`, READ/PROPOSE registry, units + ranges on every numeric field, `rate` validator rejecting `0<rate<1` (Q5); **AST guard** over `application/agent/**` + `use_cases/agent/**` (deny PySide6, sqlalchemy, sqlite3, mutating use cases) | `application/agent/tools/`, `tool_registry.py` | 5 | — |
| 12 / **236** | pure `domain/services/entity_resolver.py` (difflib) over 4 name fields; values fed by `GetAutocompleteValues`; never silently fall back | domain | 4 | — |
| — / **105** | desktop half: `application/services/amounts.py` decrypt-then-sum/sort + numeric test; endpoint half → M2 | application | 2 | — |
| 13 / **237** | `query_loans`, `calculate_interest`, `get_portfolio_summary`, `get_current_context`, `resolve_entity` wrapper; status via `StatusEngine` + Clock, **never** `loans.status`; unknown slug rejected structurally; undated → `days_overdue=None`, in count not in sum | `application/agent/tools/read_*.py` | 2 | 233, 235, 236, 105 |
| 14 / **238** | tokeniser: names + amounts, ingress (resolver pre-pass over prompt) + egress; egress test over the fake's captured request bodies | `application/agent/tokeniser.py` | 6 | 234, 237 |
| 15 / **239** | `RunAgentTurn` six-step loop, `TraceEvent` (thought/action/observation/proposal/final), system prompt + hash, untrusted-data delimiting, step budget; **`TurnRecorder` Protocol, no-op default** so 240 ∥ 241; `Container.get_run_agent_turn()` | `use_cases/agent/run_agent_turn.py`, `container.py` | 6 | 234, 235, 237, 238 |
| 16 / **240** | telemetry models mirroring 0005 column names; `user_message_ct` (D-15) not plaintext; no org/user (D-16); `EncryptedJSON` type reusing `finhive/db/encryption.py:141`; appended at EOF of `models.py` | `models.py`, `encrypted_types.py`, repo | 2 | 239 |
| 17 / **241** | tab + `QThread` worker + `Signal(object)` of `TraceEvent`; trace view model (`QAbstractItemModel`, no hex); session per thread on WAL; offscreen smoke test | `presentation/tabs/ask_finhive_tab.py`, `workers/agent_worker.py`, `widgets/trace_model.py`, `main_window.py`, `*.qss` | 2 | 239, 231 |
| 18 / **242** | `reports` + `actor`, `user_request_ct`, `turn_id`; `report_records` + `borrower_group_ct`, `due_period`, nullable `reference_id`/`giving_date` (CREATE); in-place SQLite rebuild script (`create_all` can't ALTER); CREATE-mode approve path | `models.py` Report classes, `domain/entities/report.py`, report repo, `approve_report.py` | 2 | 233 |
| 20 / **244** | `UndoApprovedReport` for EXTEND (restore prior dates) + CREATE (`set_inactive`); not an agent tool | new `use_cases/reports/undo_approved_report.py` | 2 | 242 |
| 19 / **243** | PROPOSE tools + batch-extend skill; undated extend **rejected** unless explicit `new_due_date` (G-07b) | `application/agent/tools/propose_*.py` | 2 | 237, 242 |
| 21 / **245** | approvals tab: AGENT/FORM badge, user request, Undo button; new sections on `QAbstractTableModel`; existing `QTableWidget` filed as debt (Q12) | `presentation/tabs/pending_approval_tab.py` | 2 | 242, 243, 244 |
| 22 / **246** | length cap, out-of-domain refusal, injection test via a name/group field (no notes column — Q11) | `run_agent_turn.py`, prompt | 6 | 240 |
| 24 / **248** | `tests/evals/`: `fixture.py`, `gen_expected.py`, cases JSONL schema, recorded cassettes, markers `eval/llm/judge`; auto-skip without `OPENROUTER_API_KEY` | `tests/evals/`, `pytest.ini` | 5 | 231, 233, 239 |
| 26 / **250** | `application/agent/grounding.py`: `extract_facts`, `faithfulness`, `raw_money_leak`; 100% unit-tested (lakh/crore, 3 date formats, ref_id boundary) | application | 4 | 240 |
| 25 / **249** | suites E1–E5 on cassettes; thresholds per Q15 | `tests/evals/` | — | 248, 243, 246, 250 |
| 23 / **247** | **encrypted SQLite (hop 1), not Postgres**; dated backup outside `data/`; per-table row counts; applies 242's schema rebuild; you run it on real data | `encrypt_existing_rows.py` | 2 | 241 working, 242 |
| 27 / **251** | nightly workflow (`schedule:` + `workflow_dispatch`), OpenRouter model, judge off by default, GitHub secret; PR lane stays zero-network | new `.github/workflows/evals-nightly.yml`, `test_ci_workflow.py` | 5 | 249 |
| 28 / **253** | feedback column (240) + reject/edit signal via `turn_id` (242) → triage script → golden-set JSONL | `ops/`, `tests/evals/cases/` | 6 | 240, 241, 248 |
| — / **D-17** (new id, Q2) | spike harness: same 10 fixture questions via tools vs model-emitted parameterised SQL; compare `cp`, correctness, tokens, latency. **Lives in `ops/spike_d17/`, never imported by `loan_manager`**; SQL path read-only, restricted to `_bidx` + plaintext columns. Cloud builds harness + cassette replay; **you run the live measurement locally** (U-3). Needs a raw-SQL waiver (Q18) | `ops/spike_d17/` | 6 | 249, 250 |

**Out:** KCH-100 → M2 (U-4). Postgres `migrations/0006` → M1a unless Q10 says otherwise.

## 4. Waves, lanes, critical path

Wave 0 is orchestrator-only (no product code). Cap: **4 issues in flight** (Q17).

| Wave | Parallel issues (disjoint files) | Checkpoint |
|---|---|---|
| **W0** | env bootstrap: `.venv_pg` (py3.11) with `src/Loan Manager/requirements.txt` + `pip install -e ".[dev,server]"` (PySide6, `lint-imports`); record **baseline** suite counts on `origin/development`; `rtk` absent in cloud → plain commands, trimmed output | baseline green |
| **W1a** | 235 · 236 · 233 · 234 | — |
| **W1b** | 231 · 230 · 105 · 232 | **C1** W1 merged |
| **W2** | 237 ∥ 242 → 244 | **C2** |
| **W3** | 238 ∥ 243 | — |
| **W4** | 239 | **C3** |
| **W5** | 240 → 246 → 250 ∥ 241 ∥ 245 ∥ 248 | **C4** — working tab + mutation safety |
| **W6** | 249 ∥ 247 | — |
| **W7** | 251 ∥ 253 ∥ D-17 | **done** |

- Critical path to working tab: 235/236/233 → 237 → 238 → 239 → 241.
- Critical path to done: … 239 → 240 → 250 → 249 → 251 / D-17.
- Lanes (each a stack): **Data** 230→231→247 · **Core** 235→236→105→237→238→239→240→246→250 · **Mut** 233→242→244→243→245 · **UI** 241 · **Eval** 248→249→251→253→D-17 · **Ops** 232.

**Single-owner hotspots** (serialise, never two agents at once):

| File | Owner(s), in order |
|---|---|
| `models.py` | 242 (Report classes in place) · 240 (append at EOF) — second to merge rebases |
| `container.py` | 233 (`clock`) → 239 (factory) |
| `approve_report.py` | 233 → 242 (same lane) |
| `run_agent_turn.py` | 239 → 240 → 246 |
| `requirements.txt`, `settings.json`, `settings_tab.py` | 234 only |
| `pytest.ini` | 234 (`llm`) → 248 (`eval`,`judge`) |
| `main_window.py`, `*.qss` | 241 only |
| `.github/workflows/*`, `test_ci_workflow.py` | 251 only |

## 5. Branching and PRs

1. Base = `origin/development` (local `feature/kch-252-sro3rl` is merged and behind).
2. Per issue: `git worktree add ../wt/kch-NNN -b feature/kch-NNN <lane-tip>`; implementer works only there (Agent `isolation: "worktree"`).
3. After review passes: rebase onto current lane tip, re-run full suite on the combined tree, push `feature/kch-NNN`, open **draft** PR against the previous branch in the lane (lowest PR in a lane → `development`), subscribe to PR activity.
4. Multi-dependency issues (237, 239, 241, 243, 248, 249) wait for checkpoints C1–C4 where you merge bottom-up — or on `integration/m11-cN` merge-only branches if you allow them (Q1).
5. Stage named paths only; `git diff --cached --name-only` + secret scan before every commit; never `.DS_Store`, `*.db`, `.env*`.

## 6. Per-issue agent recipe (build-issue loop)

| Step | Who / model | Prompt carries (caveman: `file:line`, not repo restatement) | Gate |
|---|---|---|---|
| 0 premise | orchestrator | `grep`/`find` for what the row says is missing | wrong premise → stop, report |
| 1 plan | **planner · opus** (skipped for 232) | KCH id, acceptance line verbatim, §3 correction, anchors, forbidden list | ordered change list + rung + reuse + fail-first command |
| 2 implement | **implementer · sonnet** (1–2, disjoint files) | worktree, branch, change list only | acceptance test pasted **failing for the named reason** before the fix; `ruff check <files>` clean |
| 3 test | **tester · sonnet** | CI-parity commands below | real counts pasted; every skip named |
| 4 review | **reviewer · opus** | `git diff base...HEAD`, acceptance line, "verify the central claim independently", attacks (`rate=0.12`, extra args, raw slug, undated loan, injection via name, plaintext NPI) | pass/fail per review-gate item |
| 5 fix | sonnet ↔ opus | findings only | **max 2 cycles**; 3rd → stop, comment on PR, escalate to you |
| 6 scribe | **scribe · haiku** | diff stat, suite counts | commit msg, PR body (debt list), Linear comment text **for you to paste** |

CI-parity commands (tester):
```
cd "src/Loan Manager" && python -m pytest tests/ -q --cov=loan_manager
PATH=/home/user/FinHive/.venv_pg/bin:$PATH pytest tests/unit -q && lint-imports
pytest tests/integration -q          # skips without TEST_DATABASE_URL — say so
git stash push -- <impl files>; pytest <acceptance test>; git stash pop   # fail-first proof
sqlite3 <db> .dump | grep -iE '<fixture names>|<amounts>'                 # no-plaintext scan
```
Then `python3 ops/rtk_gain.py --issue KCH-NNN --measure-gates` — reported as **degenerate** where `rtk` is absent (KCH-254).

Model note: the Agent tool exposes `opus`/`sonnet`/`haiku` only — pinned versions in CLAUDE.md's tier table can't be selected; tiers map by family.

## 7. Definition of done

- Every §3 issue merged to `development` with gate evidence; KCH-100 re-milestoned; three required CI checks green on `development`.
- `src/Loan Manager`: `pytest tests/` green; `env -u OPENROUTER_API_KEY pytest tests/evals -m "eval and not llm"` green on cassettes.
- Evals: E4 = 100%; `cp.query_loans = 1.0`; E3 faithfulness = 1.0; zero `raw_money_leak`; AST guard green; egress test: no name/group/amount in outbound bodies.
- Seeder refuses `data/loans.db`; raw-byte grep of demo DB, `-wal`, and `agent_turns` shows no NPI.
- **Your local demo** (with key) on `FINHIVE_DB_PATH=<demo>`: "what is overdue for the sharma group" streams trace + hydrates table; "iyer" → clarifying question; "extend all overdue sharma loans by one month" → one AGENT batch; approve → Overdue→Active without restart; undo → restored; "delete all loans" → refused, no tool call.
- Row 23 tool verified on a synthetic plaintext DB; you run it on real `loans.db`.
- Nightly workflow run once via `workflow_dispatch` (your secret). D-17 harness merged + your live result recorded in ARB D-17.

## 8. Open questions for your review (answers change the work)

| # | Question | Default if unanswered |
|---|---|---|
| Q1 | May I also push merge-only `integration/m11-cN` branches so checkpoints don't wait on your merges? How often will you merge? | No — waves wait at C1–C4 |
| Q2 | D-17 has no KCH id. You file it in Linear, or I name the branch `feature/d17-spike`? | `feature/d17-spike` |
| Q3 | Linear is unreachable from here (no MCP, no `LINEAR_API_KEY`). You post the scribe's comments, file debt, re-milestone KCH-100 + row 7's Linear half? Also confirm KCH 239–251/253 = rows 15–28 and KCH-114 closes with 230 | You do Linear; mapping as inferred |
| Q4 | Recorded fakes only: cassettes are **hand-authored** from the D-4a probe's observed shapes — they prove the harness, not the model. OK, or will you record real cassettes locally with `--record`? | Hand-authored + a `--record` mode you run |
| Q5 | `[REVIEW REQUIRED]` Reject `0 < rate < 1` — is any real annual rate below 1%? | Reject |
| Q6 | Row 23 "done" = tool verified on synthetic DB; you run it on real data? Retitle row from "Postgres" to encrypted SQLite? | Yes / yes |
| Q10 | Write Postgres `migrations/0006` now (CI Postgres lane tests it) or defer to M1a? | Defer |
| Q11 | Row 22 injection vector: borrower name/group (no notes column exists) or add a notes column? | Name/group |
| Q12 | Existing `QTableWidget` in approvals tab: convert in 245 or file as debt? | Debt |
| Q13 | UI sign-off for 241/245: offscreen smoke + screenshots in PR, then your manual demo | As stated |
| Q14 | Nightly: which OpenRouter model, monthly USD cap; judge off | qwen-2.5-72b, $2/month |
| Q15 | Eval thresholds: KCH-188's 90/85/85 or the doc's (§6: cp=1.0, E3 faithfulness 1.00, ratchet)? | Doc's |
| Q16 | Doc drift: spec + `ARB:449` say `FINHIVE_MASTER_KEY`; code uses `FINHIVE_KEY_VERSION` + `FINHIVE_MASTER_KEY_V<n>`. Fix docs in 230? | Yes |
| Q17 | Issues in flight at once | 4 |
| Q18 | D-17 needs model-authored SQL executed via SQLAlchemy `text()` — violates "no raw SQL outside `migrations/`". Grant a waiver scoped to `ops/spike_d17/` (never imported by the app)? | Waiver needed — spike blocked without it |

## 9. Verification (per wave)

- Before W1: baseline suite counts on `origin/development` recorded in `docs/mvp1.1_plan.md` §progress.
- Each PR: gate evidence pasted in the PR body (fail-first output, suite counts incl. skips, ruff, lint-imports, NPI scan).
- Each checkpoint: full suite on the merged lane tips; CI green on every open PR head.
- End: §7 checklist, then your local demo.

## 10. Execution after approval

1. ✅ This file committed as `docs/mvp1.1_plan.md` on `feature/kch-252-sro3rl` (restarted from `origin/development`), draft PR opened.
2. **STOP** — await your answers to §8 and `PROCEED`.
3. On `PROCEED`: W0 bootstrap, then waves W1→W7 per §4–§6, spawning one planner/reviewer per issue and sonnet implementers in worktrees; report at each checkpoint.
