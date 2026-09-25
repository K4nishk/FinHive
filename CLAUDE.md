# FinHive

## Project

- **What**: One-Stop shop for custom finance solutions
- **Active product**: Loan Manager **MVP1.1 — `Ask FinHive`**: a conversational agent
  tab added to the existing single-user PySide6 desktop app, as an extension of MVP1.
  Governed by `/docs/MVP1_1_ASK_FINHIVE.md`. MVP2 (web/Postgres) is **paused after
  KCH-109**.
- **Building a `KCH-*` issue? Invoke the `build-issue` skill first** — orchestrator
  loop, role-to-model mapping, review gate, stacking and blocking rules, debt policy.
- **Writing, moving or reviewing Loan Manager code, touching the UI, or filing a Linear
  issue? Load the `loan-manager-conventions` skill** — layers in detail, DI, UI rules,
  coding conventions, library constraints, repo map, Linear specifics. Kept out of
  this file because it is injected into every task and every subagent, and most of
  them need none of that.
- **Decisions**: `/output/Loan Manager/mvp2/ARB_DECISIONS.md` is LIVE and
  authoritative. Read the M1.1 block before any architectural choice — several
  decisions are conditional and one (D-17) is deliberately unresolved. The run_8
  WIKI (`/output/Loan Manager/run_8/WIKI.md`) is the file and data-flow index.
- **Data layer truth**: MVP1 is **SQLite + SQLAlchemy 2.0**, not CSV.
  `input/REQUIREMENTS.md` still says otherwise in places; run_8 superseded it (WIKI §16,
  CHG-001). Specify against `src/`, never against `input/`.
- **Branch**: `development`. A PR is required; direct pushes are rejected.
- **Agent contract**: `/docs/AGENT_CONTRACT.md`. CodeRabbit was removed (2026-09-25),
  so the review gate is the `reviewer` subagent plus the human — see the `build-issue`
  skill. The unattended orchestrator (`ops/orchestrator.sh`) used CodeRabbit as its
  gate and is dormant. A gate that did not run is a failure, never a pass.

## Doctrines

Three, always in force. Full application and measured figures: the `build-issue` skill.

- **Ponytail** — stop at the first rung that holds: YAGNI → reuse → stdlib → native
  → existing deps → minimal → necessary. **Rung 2 (reuse) is the default answer here.**
  The data layer, `ReferenceIdService`, `StatusEngine`, `InterestCalculator`, the
  `reports`/`report_records` batch and `finhive/db/` already exist; the original
  MVP1.1 plan budgeted 14.5 days rebuilding them because it was written from
  `input/REQUIREMENTS.md` instead of from `src/`.
- **Caveman** — dense prose, exact identifiers. Compress the wording, never the code,
  commands, paths or error strings. Report honest measurements, including ones that
  cut against the thesis.
- **RTK** — compress before it reaches a context. `rtk` is installed: `rtk test`,
  `rtk err`, `rtk git diff`, `rtk read`. Never pipe raw output into a subagent prompt:
  the failing lines, not the log; `file:line`, not the module. M0 measured a **122:1
  context re-read ratio** — half the bill was agents re-reading this file. Never quote
  a fixed RTK percentage; it is tree-dependent.

## Model Tiers (cost-optimised)

**Claude Code is the orchestrator: it delegates and does not implement.** Pick the
cheapest model that can do the job. A reasoning model on a mechanical edit burns budget;
Sonnet adjudicating a rule conflict returns a confident wrong answer.

| Tier | Model | Use when |
|---|---|---|
| **Orchestration** | `claude-opus-5` | The interactive session: select, decompose, spawn, adjudicate, gate |
| **Reasoning** | `claude-opus-4-6` | Planning, review, root-cause analysis, rule adjudication, mediation |
| **Implementation** | `claude-sonnet-4-6` | Writing code, fixing bugs, test authoring, refactoring |
| **Generation** | `claude-haiku-4-5-20251001` | Commit messages, PR bodies, Linear comments, doc summaries |

`ops/` scripts: `IMPL_MODEL` → Sonnet, `MEDIATOR_MODEL` → Opus.

## Architecture

Four-layer Clean Architecture, dependency inward only:
`Presentation → Application → Domain ← Infrastructure`. Put new code in the right layer;
if it needs an import that crosses a boundary the wrong way, restructure. Detail, DI and
the UI conventions: the `loan-manager-conventions` skill.

---

## Business Rules (Authoritative)

These override any conflicting implementation. If code disagrees with these, the code is wrong.

- `giving_date` is **never** used in interest or time-period calculations. Only `extension_period` counts.
- Monthly interest: `(amount * rate * months) / 1200`
- Daily interest: `(amount * rate * days) / 36500`
- Commission uses the same formula as interest but with `commission_rate`.
- TDS: `0.1 * interest_amount` (when `tds_flag` is true).
- CHQ: `interest_amount - tds_amount`.
- Status on startup: `RecomputeAllStatuses` runs on every app launch, overriding persisted status.
- Status rules (evaluated in order): `giving_date > today` → Pending; `due_date is None` → Overdue; `today < due_date` → Active; else → Overdue.
- Extend overwrites the record: `new giving_date = old due_date`, `new due_date = old due_date + extension_period`. History loss is accepted.
- Paidoff: `extension_period(days) = paidoff_date - due_date`. Report generated in Daily mode. On approval, loan archived to `loan_history`, marked `is_active=False`.
- ByMonth filter excludes records without `due_date`. All other filters include them if matching.
- `report_records` stores snapshots of loan data at report time, not live references.

### Data protection (MVP1.1 onward — ARB D-15, D-16)

- **NPI is encrypted at rest.** Migration 0003 encrypts **nine** columns as
  AES-256-GCM `_ct BYTEA` with `key_version`, across `loans`, `loan_history` and
  `report_records`:
  `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group`, `amount`,
  **and the derived financial values** `interest_amount`, `commission_amount`,
  `tds_amount`, `chq_amount`.
  Encryption happens at the **repository boundary only** — the domain entity and
  every use case work in plaintext. Three repositories touch encrypted tables:
  loan, history and report.
- **The derived amounts are not optional.** `interest_rate` and `extension_period`
  stay plaintext (Decisions 13, 14), so a plaintext `interest_amount` solves for the
  principal: `amount = interest × 1200 / (rate × months)`. Leaving any one of the
  four in clear re-opens the path ADR-2.4 closed. Re-run that derivation check
  before adding **any** plaintext column carrying a derived financial value.
- **Never compare, filter, `GROUP BY` or `ORDER BY` a `_ct` column.** A random IV per
  call means two encryptions of the same value differ. Exact match uses the HMAC
  blind index; ordering and totals are app-layer after decrypt.
- **Never blind-index an amount.** Loan amounts cluster on round numbers, so a
  deterministic index over them is reversible by frequency analysis without the key
  (ADR-2.4). Identity columns only.
- **Names and amounts are tokenised before any LLM call** — ingress (the user's typed
  prompt) as well as egress. Data at rest is local, so inference is the only path
  that leaves the machine (OQ-01 as amended).
- Every repository query is **org-scoped**. `loans.org_id` is NOT NULL and UNIQUE is
  `(org_id, reference_id)`.

---

## Testing Requirements

- **See it fail first.** A new or changed test counts only once you have watched it
  fail *for the reason its name states*: break the property it guards (in a scratch
  copy, never the real tree), run it, and read the failure message. Failing on a
  `NameError`, `KeyError`, `ImportError` or config error is not that — neither is a
  test that has only ever passed or skipped. KCH-230 found seven tests in this repo
  that passed for the wrong reason or had never run anywhere, and three migrations
  shipped unrunnable behind them.
- **A skip is not a pass.** Say what ran. Run tests the way CI does — `pytest tests/unit`
  with `lint-imports` on `PATH` (`PATH=.venv_pg/bin:$PATH`) — or the tests that skip
  locally are exactly the ones that fail in CI.
- **Coverage target**: 85% minimum. Domain services: 100%.
- Run: `cd "src/Loan Manager" && python -m pytest tests/ -v --cov=loan_manager`
- **Unit** tests use in-memory SQLite (`sqlite:///:memory:`). **Integration** tests
  (repository, migration, encryption) run against real Postgres and must SKIP — never
  fail — when `TEST_DATABASE_URL` is unset, because CI runs whole test directories.
- Point `TEST_DATABASE_URL` at a **dedicated, disposable** database — never the dev
  database. The lane drops and recreates schemas; the dev ledger lives in `public`.
- Do not assume CI blocks a merge: required checks live in the repo ruleset — verify
  them there before relying on a red check to stop anything.
- Every new use case has a test file. Every bug fix has a regression test that would
  have caught it. No UI tests in prototype scope — verify UI changes manually or in
  review. Run the full suite before any commit; never commit with failing tests.

---

## Explicit Prohibitions

- **Do not** hardcode API keys or secrets. Use `.env` files.
- **Do not** modify files under `.claude/skills/tools/*`.
- **Do not** use `QTableWidget` for data tables. Use `QAbstractTableModel`.
- **Do not** call `showCalendarWidget()`. It does not exist.
- **Do not** hardcode hex colours in presentation code. Use `ThemeManager`.
- **Do not** use `float` for monetary values. Use `Decimal`, quantised to two places
  with `ROUND_HALF_UP`. Python's default context rounds half-even, which silently
  shifts paise: `2.345` becomes `2.34`, not MVP1's `2.35`.
- **Do not** write raw SQL outside `migrations/` (ARB D-1a: parameterised ORM only).
  A raw write also bypasses the encrypting repository and lands plaintext.
- **Do not** use `giving_date` in any interest or time calculation.
- **Do not** import `PySide6` in domain or application layers.
- **Do not** import `sqlalchemy` in domain or presentation layers.
- **Do not** put business logic in presentation layer code.
- **Do not** access repositories directly from presentation — go through use cases.
- **Do not** use `datetime.utcnow()` — it is deprecated in Python 3.12+. Use `datetime.now(timezone.utc)`.
- **Do not** leverage previous run's output as context for a new run.
- **Do not** make assumptions without evidence. Mark uncertain decisions as `[REVIEW REQUIRED]`.
- **Do not** skip the stage-gate approval process. Every stage must STOP and await `PROCEED` or `PROCEED WITH MODIFICATIONS`.
- **Do not** commit `.DS_Store`, `__pycache__/`, `.coverage`, `*.pyc`, or `data/loans.db` to git.
- **Do not** `git add -A` / `git add .`. Stage named paths. Both `data/loans.db` and
  `.DS_Store` are already tracked, so a blanket add sweeps them in. Review
  `git diff --cached --name-only` and scan the staged diff for secrets before committing.
- **Do not** send a raw amount or a raw entity name to an LLM. Tokenise first.
- **Do not** read `loans.status` in agent tools — derive via `StatusEngine` at read;
  the persisted column is stale after a batch approve.
- **Do not** add a blind index to any amount column.
- **Do not** write a `_ct` column from anywhere but the repository layer.
- **Do not** seed or fixture data with raw SQL `INSERT`s — go through the encrypting
  repository, or you produce a database the app cannot read.
- **Do not** specify work against `input/REQUIREMENTS.md` storage claims. They are
  superseded; `src/` is the truth.
- **Do not** run anything that drops tables or schemas without first checking **which
  database** it targets.
