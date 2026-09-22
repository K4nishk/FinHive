# FinHive

## Project

- **What**: One-Stop shop for custom finance solutions
- **Active product**: Loan Manager **MVP1.1 — `Ask FinHive`**: a conversational agent
  tab added to the existing single-user PySide6 desktop app, as an extension of MVP1.
  Governed by `/docs/MVP1_1_ASK_FINHIVE.md` and the M1.1 Orchestrator Contract below.
  MVP2 (web/Postgres) is **paused after KCH-109**.
- **Data layer note**: MVP1 is **SQLite + SQLAlchemy 2.0**, not CSV. `input/REQUIREMENTS.md`
  still says otherwise in places; run_8 superseded it (WIKI §16, CHG-001). Specify
  against `src/`, never against `input/`.
- **Branch**: `development`
- **Input**: `/input/REQUIREMENTS.md` (authoritative business spec), `/input/prompt*.md` (build/fix prompts)
- **Output**: `/output/YYYY/MM/DD/stdout_HHMMSS.md` (design artifacts, ARD, WIKI, FINAL_REVIEW)
- **Source**: `/src/Loan Manager/loan_manager/` (Python package)
- **WIKI**: `/output/Loan Manager/run_8/WIKI.md` — full repository knowledge base with file index, data flows, and business rules. Read it before making architectural decisions.
- **ARD**: `/output/Loan Manager/run_8/ARD.md` — architecture reference for onboarding context.
- **Agent contract**: `/docs/AGENT_CONTRACT.md` — the rules any agent (orchestrator-driven or interactive) follows when implementing a `KCH-*` issue: branch, implement, review gate, bounded fix cycles, escalation. For M1.1 the gate is the `reviewer` subagent, not CodeRabbit (free tier ended) — see the M1.1 Orchestrator Contract below.

---

## Model Tiers (cost-optimised)

Use the right model for the task. Overkill burns budget; under-spec burns quality.

| Tier | Model | Use when |
|---|---|---|
| **Reasoning** | `claude-opus-4-6` | Architecture decisions, root-cause analysis, code review adjudication, complex debugging, mediation |
| **Implementation** | `claude-sonnet-4-6` | Writing code, fixing bugs, implementing features, test authoring, refactoring |
| **Generation** | `claude-haiku-4-5-20251001` | Output formatting, simple text generation, commit message drafting, doc summaries |

When configuring `ops/` scripts: `IMPL_MODEL` → Sonnet, `MEDIATOR_MODEL` → Opus.
Interactive sessions default to Opus for reasoning-heavy work and Sonnet for code changes.

---

## M1.1 Orchestrator Contract — `Ask FinHive`

**Active while the `FinHive M1.1 · Ask FinHive` project has open issues.** The
interactive session is the orchestrator; it delegates and does not implement.
Scope: `docs/MVP1_1_ASK_FINHIVE.md`. Issues:
`output/Loan Manager/mvp1.1/linear_import.csv`, row order = build order.

**CodeRabbit is gone.** The free tier ended; `coderabbit usage` exits non-zero.
Every gate below that used to be CodeRabbit is now a `reviewer` subagent plus the
human. Do not call `coderabbit`, and do not treat its absence as a passing gate.

### Roles and models

| Role | Model | Does | Never |
|---|---|---|---|
| **Orchestrator** | `claude-opus-5` | Picks the issue, decomposes, spawns, adjudicates, gates, writes the Linear comment | Writes product code |
| **planner** | `claude-opus-4-6` | Reads the issue + real files, produces the change list with `file:line` | Edits anything |
| **reviewer** | `claude-opus-4-6` | Adversarial review; validates against the rules below | Fixes what it finds |
| **implementer** | `claude-sonnet-4-6` | Writes code and tests to the planner's list | Re-plans, or widens scope |
| **tester** | `claude-sonnet-4-6` | Runs suites, writes regressions, reports real output | Marks a failing suite green |
| **scribe** | `claude-haiku-4-5-20251001` | Commit messages, PR bodies, Linear comments, doc summaries | Decides anything |

One planner and one reviewer per issue. Implementers may run in parallel **only**
across files that do not import each other. Spawn a reasoning model for a
mechanical edit and you have burned the budget for nothing; spawn Sonnet to adjudicate
a rule conflict and you get a confident wrong answer.

### Doctrines

**Ponytail — stop at the first rung that holds.** YAGNI → reuse → stdlib → native
→ existing deps → minimal → necessary. Every planner output names the rung. MVP1
already has the data layer, `ReferenceIdService`, `StatusEngine`,
`InterestCalculator` and the `reports`/`report_records` proposal batch — rung 2
(reuse) is the default answer, not rung 7.

**Caveman — why use many token when few token do trick.** Dense prompts, dense
reports. Preserve code, commands, paths, identifiers and error strings exactly;
compress the prose around them. Report honest measurements including ones that cut
against the thesis.

**RTK — compress before it reaches the context.** `rtk` is installed
(`/opt/homebrew/bin/rtk`). **Wrap every command whose output reaches a context**:

```
rtk test <cmd>   rtk err <cmd>   rtk git diff   rtk git status
rtk read <file>  rtk find …      rtk psql …     rtk docker …
```

Measured on this repo, not quoted from the README: `git status` −44%,
`git diff` −14%, **−15% overall**. Useful, and far below RTK's advertised 60–90%
because a code diff is mostly lines it cannot compress. Never cite the advertised
range as if it were observed here.

RTK is not a substitute for judgement. Never pipe raw output into a subagent
prompt even wrapped: pass the failing lines, not the whole log; the diff, not the
file; `file:line` plus the function, not the module. The M0 ledger measured a
**122:1 context re-read ratio** — roughly half the bill was agents re-reading
`CLAUDE.md`, the WIKI and the tree from zero. A subagent prompt that restates the
repo is that bill, and `rtk` will not save you from it.

### Per-issue loop

1. **Select** the lowest unbuilt row whose hard blockers are resolved (below).
2. **Plan** — `planner`. Reads the issue, the cited files and
   `docs/MVP1_1_ASK_FINHIVE.md`. Output: ordered change list with `file:line`, the
   Ponytail rung, what is reused, and the acceptance test. If the issue's premise
   is wrong, it says so and stops — it does not improvise.
3. **Implement** — `implementer`, on `feature/kch-NNN` branched from the stack tip.
4. **Test** — `tester`. Full MVP1 suite plus the issue's own tests. Real output
   pasted, never a summary of intent.
5. **Review** — `reviewer`, adversarially, against the review gate below. Findings
   go back to the implementer for at most **two** cycles. A third means the issue
   is under-specified: stop, comment on Linear, escalate to the human.
6. **Commit and stack** — scribe writes the message; open the PR against the branch
   below it, never `development` directly.
7. **Comment** — scribe posts to Linear, verbatim:
   `Development and testing completed, awaiting PR review and merge.`
   plus the PR link, the suites that ran with their real counts, and the RTK Gain
   block.
8. **Report** — `python3 ops/rtk_gain.py --issue KCH-NNN --measure-gates`, printed
   in the result. Non-optional; it is how the human sees the cost of each issue.
   Axis A is measured on this machine by running the gate commands both ways;
   Axis B is the agent tokens actually billed, from `ops/logs/usage.jsonl`.

### Review gate (replaces CodeRabbit)

A PR may open only when all of these hold, each proven by pasted output:

- Full MVP1 suite green — `cd "src/Loan Manager" && rtk test python -m pytest tests/`
  Postgres integration tests must **skip** cleanly with no container running, never fail
- `rtk err ruff check <changed files>` clean
- The issue's own acceptance test exists and fails without the change
- No layer violation: `domain/` imports no `infrastructure`/`presentation`/PySide6/
  sqlalchemy; `application/agent/` imports no PySide6, sqlalchemy, sqlite3 or
  mutating use case
- No raw SQL outside `migrations/` (ARB D-1a keeps D-1's parameterised-only rule)
- No `float` for money; no `datetime.utcnow()`; no hardcoded hex in
  `presentation/`; no `QTableWidget` for new data tables
- **No plaintext NPI** — a direct `SELECT` over changed tables shows no borrower or
  depositor name, group, or amount in clear (ARB D-15)
- **No blind index on any amount column** — deterministic indexing over round-number
  amounts is reversible by frequency analysis without the key (ADR-2.4, KCH-99)
- No secret, key or token added to a tracked file

### Stacking and blocking

PRs stack; **an unreviewed PR never blocks the next issue.** Branch the next issue
from the previous branch's tip, PR against it, and let the human merge bottom-up.

A **hard blocker** — the only thing that stops the queue — is when the next issue
cannot begin until the previous is fully resolved:

| Blocked | Blocker | Why |
|---|---|---|
| everything | Docker Postgres · model port · migrations 0001-0005 | There is no database to build against |
| encryption at the boundary | master key source | Encrypting with a key that vanishes on next launch is data loss |
| blind index · dev fixture · anything reading NPI | encryption at the boundary | The `_ct` columns must be readable first |
| EntityResolver | encryption at the boundary | The index is built from decrypted names |
| READ tools · loop | tool arg models | The registry is their call contract |
| loop | LLM client | Nothing to call |
| Ask FinHive tab | loop · dev fixture | Nothing to stream, and nothing to stream it about |
| PROPOSE tools · approvals tab | report-batch schema | The columns must exist |
| real-data migration | the tab working on seeded data | Deliberate: exercise the encryption path for weeks before real data touches it |
| eval suites | fixture + harness | No ground truth without it |

Everything else proceeds on the stack. When a hard blocker is unresolved, work the
next unblocked row — do not idle, and do not start the blocked issue "partially".

### Technical debt

Debt is not deferred silently. When work outside the issue's scope is found:

1. Fix it in-issue **only** if it is a one-line correctness fix and the issue
   already touches that file.
2. Otherwise file a Linear issue immediately, in the same session, with
   `product:finhive` and the file:line — and link it from the PR body.
3. Never leave a `TODO` in the code as the record. The tracker is the record.

An issue is not complete while its own acceptance test is skipped, xfailed, or
asserting something weaker than the acceptance line.

---

## Language & Framework Constraints

- Python >= 3.10. Target compatibility: 3.10–3.13.
- PySide6 >= 6.8.0 for GUI.
- SQLAlchemy >= 2.0 ORM with SQLite backend. No raw SQL outside migrations.
- Alembic for schema migrations.
- Pydantic >= 2.5 for all DTOs. Use `BaseModel`, field validators, model validators.
- `python-dateutil` for date arithmetic (`relativedelta`). No manual month math.
- `openpyxl` for XLSX. No other Excel library.
- `Decimal` (not `float`) for all monetary calculations. Use `ROUND_HALF_UP`. Quantize to two decimal places.
- All dates stored and compared as `datetime.date` objects in ISO 8601 format.
- Enums via `str, Enum` for serialisation compatibility (see `domain/value_objects/status.py`).

---

## Architecture Rules

Four-layer Clean Architecture. Dependency flows inward only.

```
Presentation → Application → Domain ← Infrastructure
```

- **Domain** (`domain/`): Pure Python. No imports from `infrastructure/`, `presentation/`, `PySide6`, or `sqlalchemy`. Entities, value objects, domain services, repository interfaces, domain events.
- **Application** (`application/`): Use cases and DTOs only. Imports `domain/` only. No DB queries, no UI code.
- **Infrastructure** (`infrastructure/`): Implements domain repository interfaces. Imports `domain/` and `sqlalchemy`. No `PySide6`.
- **Presentation** (`presentation/`): PySide6 UI. Calls application use cases. No business logic. No direct repository access.

When adding new code, place it in the correct layer. If a piece of logic requires imports that cross layer boundaries in the wrong direction, restructure.

### Dependency Injection

Constructor injection via `Container` (`container.py`). No DI framework. No service locator pattern beyond `Container`.

### Table Model

Use `QAbstractTableModel` + `QSortFilterProxyModel` for all data tables. Never use `QTableWidget`.

### Filter State

`ColumnFilterWidget` owns a single-source-of-truth `FilterState`. The popup is a pure view — it holds no permanent state. Read `src/Loan Manager/docs/filter_architecture.md` before touching filter code.

### Date Picker

Use `setCalendarPopup(True)` + `QTimer.singleShot(0, showPopup)` for date picker activation. Never call `showCalendarWidget()` — it does not exist in PySide6.

### Theme

All colours come from `ThemeManager` + JSON config files (`dark_config.json`, `light_config.json`). Never hardcode hex colour values in UI code.

---

## Coding Conventions

- PEP 8 style. 
- File naming: lowercase with underscores (`interest_calculator.py`, `loan_table_model.py`).
- Agent/skill file naming: lowercase with hyphens (`python-reviewer.md`, `tdd-workflow.md`).
- Normalise `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group` to lowercase at write time.
- All monetary amounts are non-negative integers (whole INR rupees). Enforce via `Money` value object or Pydantic `Field(ge=0)`.
- Use `from __future__ import annotations` at the top of every module.
- Use `Optional[X]` or `X | None` consistently — prefer `Optional[X]` for dataclass fields, `X | None` for type hints in function signatures.
- Dataclasses for domain entities. Pydantic `BaseModel` for DTOs. Do not mix.
- Frozen dataclasses for value objects (`@dataclass(frozen=True)`).
- Use cases are classes with an `execute()` method. One use case per file.
- Repository methods return domain entities, not ORM models. Map in the repository implementation.
- Log via `get_logger(__name__)` from `infrastructure/logging/logger.py`. No `print()` in production code.

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

- **NPI is encrypted at rest.** `borrower_name`, `borrower_group`, `depositor_name`,
  `depositor_group` and `amount` are AES-256-GCM `_ct BYTEA` columns with
  `key_version`. Encryption happens at the **repository boundary only** — the domain
  entity and every use case work in plaintext.
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

- **Coverage target**: 85% minimum. Current: 89%.
- Run tests: `cd "src/Loan Manager" && python -m pytest tests/ -v --cov=loan_manager`
- Domain services must have 100% unit test coverage.
- Test against in-memory SQLite (`sqlite:///:memory:`) for integration tests.
- Validate filter logic with sample data checkpoints: `bg3` → 2 records (b3, b4); `dg3` → 4 records (b6, b7, b8, b9).
- Every new use case must have a corresponding test file.
- Every bug fix must include a regression test that would have caught the bug.
- No UI tests in prototype scope — verify UI changes manually or via code review.
- Run the full test suite before any commit. Do not commit with failing tests.

---

## Linear

Team `KCH` is shared with other products (Aegis, AssetAuditor). See the global
`~/.claude/CLAUDE.md` for the full convention. FinHive specifics:

- **Product label**: `product:finhive` on every issue, always first
- **Projects**: `FinHive <milestone> · <name>` — e.g. `FinHive M1a · Local Setup, Login & Encryption`
- **Workstream label**: `ops`, `ci-cd`, `data`, `security`, `backend`, `business-logic`, `frontend`, `agent`, `auth`, `testing`, `observability`, `docs`
- **Source of truth**: `output/Loan Manager/mvp2/linear_import.csv` — row order is build order, never re-sort it
- **Import**: `python3 ops/seed_linear.py` (dry run) → `--apply`. Idempotent by title.

## Explicit Prohibitions

- **Do not** hardcode API keys or secrets. Use `.env` files.
- **Do not** modify files under `.claude/skills/tools/*`.
- **Do not** use `QTableWidget` for data tables. Use `QAbstractTableModel`.
- **Do not** call `showCalendarWidget()`. It does not exist.
- **Do not** hardcode hex colours in presentation code. Use `ThemeManager`.
- **Do not** use `float` for monetary values. Use `Decimal`.
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
- **Do not** send a raw amount or a raw entity name to an LLM. Tokenise first.
- **Do not** read `loans.status` in agent tools — derive via `StatusEngine` at read;
  the persisted column is stale after a batch approve.
- **Do not** add a blind index to any amount column.
- **Do not** write a `_ct` column from anywhere but the repository layer.
- **Do not** seed or fixture data with raw SQL `INSERT`s — go through the encrypting
  repository, or you produce a database the app cannot read.
- **Do not** specify work against `input/REQUIREMENTS.md` storage claims. They are
  superseded; `src/` is the truth.

---

## File Structure

```
/input/*                          Requirements and prompt specs (read-only reference)
/output/<Title>/<run_order>/*     Design artifacts per run (ARD, WIKI, FINAL_REVIEW, docs/)
/src/<Title>/*                    Source code (populated during implementation stages)
/.claude/agents/*                 Subagent definitions (markdown + YAML frontmatter)
/.claude/skills/*                 Skill definitions (markdown)
/.claude/tools/*                  Reference snippets (do not modify)
```

### Loan Manager Source (`/src/Loan Manager/loan_manager/`)

```
main.py              Entry point: logging → recovery check → DB init → status recompute → UI launch
config.py            All path constants: DATA_DIR, DB_PATH, LOG_FILE, RECOVERY_FILE, etc.
container.py         DI wiring: Container class
domain/              Layer 1: entities, value_objects, services, repositories (interfaces), events
application/         Layer 2: use_cases/, dtos/, interfaces/unit_of_work.py, event_bus.py
infrastructure/      Layer 3: database/ (ORM models, session, UoW), repositories/ (implementations),
                              csv/ (import/export), recovery/, logging/, migrations/
presentation/        Layer 4: main_window, tabs/, dialogs/, widgets/, view_models/, themes/
```

---

## Available Agents

- `.claude/agents/architect.md` — Architecture decisions
- `.claude/agents/build-error-resolver.md` — Fix build errors
- `.claude/agents/code-reviewer.md` — Code quality review
- `.claude/agents/doc-updater.md` — Documentation updates
- `.claude/agents/loop-operator.md` — Orchestrates child agents and skills (starter agent)
- `.claude/agents/planner.md` — Implementation planning
- `.claude/agents/python-reviewer.md` — Python-specific review
- `.claude/agents/refactor-cleaner.md` — Refactoring and cleanup
- `.claude/agents/security-reviewer.md` — Security review
- `.claude/agents/tdd-guide.md` — Test-driven development guidance

## Skills

See `.claude/skills/*/SKILL.md` for full list. Key categories:
- **Role agents**: pm, po, bsa, sa, dev-lead, backend-dev, frontend-dev, backend-qa, frontend-qa, qa-lead, uat, sre, dm
- **Pattern skills**: backend-patterns, frontend-patterns, python-patterns, coding-standards, deployment-patterns
- **Process skills**: tdd-workflow, python-testing, agentic-engineering, ai-first-engineering

## Commands

- `/tdd` — Test-driven development workflow
- `/plan` — Implementation planning
- `/code-review` — Quality review
- `/build-fix` — Fix build errors
- `/learn` — Extract patterns from sessions
- `/skill-create` — Generate skills from git history

---

## Agentic Development Loop

When work is implemented by an agent against a `KCH-*` Linear issue, follow
`/docs/AGENT_CONTRACT.md`: branch from `development` as `feature/kch-N`, implement with
tests, pass the review gate, fix blocking findings for at most two cycles, then
escalate to a new Linear issue carrying the finding, each attempted fix, why it failed,
and a suggested direction. An agent never merges — it opens a PR (or, on escalation,
a draft PR) for a human to review.

**For M1.1 the review gate is NOT CodeRabbit** — the free tier has ended and
`coderabbit usage` exits non-zero. Use the `reviewer` subagent and the explicit
checklist in the M1.1 Orchestrator Contract above. An unauthenticated CodeRabbit is
a gate that did not run, which is a failure, never a pass.

## Development Workflow

1. **Explore** → Read WIKI, ARD, and relevant source before changing anything.
2. **Plan** → For non-trivial changes, use `/plan` or enter plan mode. Get approval.
3. **Implement** → Small, atomic changes. One concern per commit.
4. **Test** → Run full suite. Add regression test for every fix.
5. **Review** → Run `/code-review` before requesting human review.
6. **Stage-gate** → If working within a staged run, STOP after each stage. Await approval.
