# FinHive

## Project

- **What**: One-Stop shop for custom finance solutions
- **Active product**: Loan Manager **MVP1.1 — `Ask FinHive`**: a conversational agent
  tab added to the existing single-user PySide6 desktop app, as an extension of MVP1.
  Governed by `/docs/MVP1_1_ASK_FINHIVE.md`. MVP2 (web/Postgres) is **paused after
  KCH-109**. Demo and onboarding: `/docs/AskFinHive_instructions.md`.
- **Building a `KCH-*` issue? Invoke the `build-issue` skill first** — per-issue
  workflow, when to plan or review with Opus, stacking and blocking rules, debt policy.
- **Before any commit: run the `verify-change` skill** — CI-parity test commands,
  see-it-fail-first, staging and secret scan, PR stacking.
- **Writing, moving or reviewing Loan Manager code, touching the UI, or filing a Linear
  issue? Load the `loan-manager-conventions` skill** — layers in detail, DI, UI rules,
  coding conventions, library constraints, repo map, Linear specifics.
- **Decisions**: `/output/Loan Manager/mvp2/ARB_DECISIONS.md` is LIVE and
  authoritative. Read the M1.1 block before any architectural choice — several
  decisions are conditional and one (D-17) is deliberately unresolved. The run_8
  WIKI (`/output/Loan Manager/run_8/WIKI.md`) is the file and data-flow index.
- **Data layer truth**: MVP1 is **SQLite + SQLAlchemy 2.0**, not CSV.
  `input/REQUIREMENTS.md` still says otherwise in places; run_8 superseded it (WIKI §16,
  CHG-001). Specify against `src/`, never against `input/`.
- **Branch**: `development`. A PR is required; direct pushes are rejected.
- **Agent contract**: `/docs/AGENT_CONTRACT.md`. CodeRabbit was removed (2026-09-25).
  A gate that did not run is a failure, never a pass — say so in the PR.

## Agent and model policy (enforced — owner decision 2026-10-01)

Token budget is shared across all of the owner's projects. MVP1.1 spent most of its
budget on agent ceremony (≈1M tokens for one tab), not on code. Default to the
cheapest path that ships correct code.

1. **One Sonnet session per issue.** The same session reads the issue, plans, writes
   code and tests, runs the gates, commits and opens the PR. No orchestrator fleet; no
   separate tester or scribe agents; no parallel agents unless the owner asks.
2. **Opus planner only when the plan is unclear** — the premise looks wrong, the change
   crosses layers with more than one sane design, or ARB decisions conflict. A plan the
   issue text already implies needs no planner.
3. **Opus review only for security-critical changes**: encryption, keys or `_ct`
   columns; the tokeniser or anything that sends data to an LLM; agent tool
   permissions (the READ/PROPOSE gate, new PROPOSE tools); raw SQL or migrations;
   anything touching the real `data/loans.db`. Everything else: self-review against
   the `verify-change` checklist, CI, and the human.
4. **At most one fix cycle** after an Opus review. Still failing → stop and ask the
   owner; never a third cycle.
5. **Timebox.** A component that has not converged after two attempts ships with its
   limits written in the PR body as DEBT, or the owner cuts it.
6. **Build the thinnest slice a user can see first.** Evals, telemetry, nightly CI and
   spikes come after the owner has seen it working.

## Doctrines

- **Ponytail** — stop at the first rung that holds: YAGNI → reuse → stdlib → native →
  existing deps → minimal → necessary. **Rung 2 (reuse) is the default here**: the
  data layer, `ReferenceIdService`, `StatusEngine`, `InterestCalculator`, the
  `reports`/`report_records` batch and `finhive/db/` already exist.
- **Caveman** — dense prose, exact identifiers. Never compress code, commands, paths
  or error strings. Report honest measurements, including unflattering ones.
- **RTK** — compress before it reaches a context (`rtk test`, `rtk err`,
  `rtk git diff`). Pass failing lines, not logs; `file:line`, not modules.

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
  every use case work in plaintext. Repositories touching encrypted tables: loan,
  history, report, and the agent turn recorder (`agent_turns`).
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
  that leaves the machine (OQ-01 as amended). Never send a raw amount or entity name.
- Every repository query is **org-scoped**. `loans.org_id` is NOT NULL and UNIQUE is
  `(org_id, reference_id)`.

---

## Testing (procedure: the `verify-change` skill)

- **See it fail first.** A new or changed test counts only once you have watched it
  fail for the reason its name states. A `NameError`/`ImportError` failure, or a test
  that has only ever passed or skipped, does not count.
- **A skip is not a pass.** Run tests the way CI does and say what ran.
- **Coverage**: 85% minimum; domain services 100%. Every bug fix has a regression test.
- Unit tests use in-memory SQLite. Integration tests use a **disposable** Postgres via
  `TEST_DATABASE_URL` and must SKIP, never fail, when it is unset.

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
- **Do not** `git add -A` / `git add .`. Stage named paths (see `verify-change`).
- **Do not** read `loans.status` in agent tools — derive via `StatusEngine` at read;
  the persisted column is stale after a batch approve.
- **Do not** write a `_ct` column from anywhere but the repository layer.
- **Do not** seed or fixture data with raw SQL `INSERT`s — go through the encrypting
  repository, or you produce a database the app cannot read.
- **Do not** specify work against `input/REQUIREMENTS.md` storage claims. They are
  superseded; `src/` is the truth.
- **Do not** run anything that drops tables or schemas without first checking **which
  database** it targets.
