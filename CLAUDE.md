# FinHive

## Project

- **What**: One-Stop shop for custom finance solutions
- **Active product**: Loan Manager **MVP1.1 — `Ask FinHive`**: a conversational agent
  tab added to the existing single-user PySide6 desktop app, as an extension of MVP1.
  Governed by `/docs/MVP1_1_ASK_FINHIVE.md`. MVP2 (web/Postgres) is **paused after
  KCH-109**.
- **Building a `KCH-*` issue? Invoke the `build-issue` skill first.** It carries the
  orchestrator loop, role-to-model mapping, review gate, stacking and blocking rules,
  and the debt policy. Kept out of this file so it does not occupy context while you
  are writing code.
- **Decisions**: `/output/Loan Manager/mvp2/ARB_DECISIONS.md` is LIVE and
  authoritative. Read the M1.1 block before any architectural choice — several
  decisions are conditional and one (D-17) is deliberately unresolved.
- **Data layer note**: MVP1 is **SQLite + SQLAlchemy 2.0**, not CSV. `input/REQUIREMENTS.md`
  still says otherwise in places; run_8 superseded it (WIKI §16, CHG-001). Specify
  against `src/`, never against `input/`.
- **Branch**: `development`
- **Input**: `/input/REQUIREMENTS.md` (authoritative business spec), `/input/prompt*.md` (build/fix prompts)
- **Output**: `/output/YYYY/MM/DD/stdout_HHMMSS.md` (design artifacts, ARD, WIKI, FINAL_REVIEW)
- **Source**: `/src/Loan Manager/loan_manager/` (Python package)
- **WIKI**: `/output/Loan Manager/run_8/WIKI.md` — full repository knowledge base with file index, data flows, and business rules. Read it before making architectural decisions.
- **ARD**: `/output/Loan Manager/run_8/ARD.md` — architecture reference for onboarding context.
- **Agent contract**: `/docs/AGENT_CONTRACT.md` — branch, implement, review gate,
  bounded fix cycles, escalation. **Its CodeRabbit gate is superseded**: the free
  tier ended and `coderabbit usage` exits non-zero. For M1.1 the gate is the
  `reviewer` subagent plus the human — see the `build-issue` skill. An
  unauthenticated CodeRabbit is a gate that did not run, which is a failure, never
  a pass.

---

## Doctrines

Three, always in force. Full application and measured figures: the `build-issue` skill.

- **Ponytail** — stop at the first rung that holds: YAGNI → reuse → stdlib → native
  → existing deps → minimal → necessary. **Rung 2 (reuse) is the default answer in
  this repo.** The data layer, `ReferenceIdService`, `StatusEngine`,
  `InterestCalculator`, the `reports`/`report_records` batch and `finhive/db/`
  already exist. The original MVP1.1 plan budgeted 14.5 days rebuilding them because
  it was written from `input/REQUIREMENTS.md` instead of from `src/`.
- **Caveman** — dense prose, exact identifiers. Compress the wording; never the code,
  commands, paths or error strings. Report honest measurements, including ones that
  cut against the thesis.
- **RTK** — compress before it reaches a context. `rtk` is installed: `rtk test`,
  `rtk err`, `rtk git diff`, `rtk read`. Never pipe raw output into a subagent
  prompt: the failing lines, not the log; `file:line`, not the module. M0 measured a
  **122:1 context re-read ratio** — half the bill was agents re-reading this file and
  the WIKI from zero. Never quote a fixed RTK percentage; it is tree-dependent and is
  re-measured per issue by `ops/rtk_gain.py`.

## Model Tiers (cost-optimised)

**Claude Code is the orchestrator: it delegates and does not implement.** Pick the
cheapest model that can do the job — overkill burns budget, under-spec burns quality.

| Tier | Model | Use when |
|---|---|---|
| **Orchestration** | `claude-opus-5` | The interactive session: select, decompose, spawn, adjudicate, gate |
| **Reasoning** | `claude-opus-4-6` | Planning, review, root-cause analysis, rule adjudication, mediation |
| **Implementation** | `claude-sonnet-4-6` | Writing code, fixing bugs, test authoring, refactoring |
| **Generation** | `claude-haiku-4-5-20251001` | Commit messages, PR bodies, Linear comments, doc summaries |

A reasoning model on a mechanical edit burns budget for nothing; Sonnet adjudicating
a rule conflict returns a confident wrong answer. When configuring `ops/` scripts:
`IMPL_MODEL` → Sonnet, `MEDIATOR_MODEL` → Opus.

---

## Language & Framework Constraints

- Python >= 3.10. Target compatibility: 3.10–3.13.
- PySide6 >= 6.8.0 for GUI.
- SQLAlchemy >= 2.0 ORM, **sync**. SQLite through MVP1; **Postgres from MVP1.1**
  (ARB D-1a, D-16). No raw SQL outside migrations.
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

- **Coverage target**: 85% minimum. Current: 89%.
- Run tests: `cd "src/Loan Manager" && python -m pytest tests/ -v --cov=loan_manager`
- Domain services must have 100% unit test coverage.
- **Unit** tests use in-memory SQLite (`sqlite:///:memory:`). **Integration** tests
  (repository, migration, encryption) run against real Postgres and must SKIP — never
  fail — when `TEST_DATABASE_URL` is unset, because `mvp1-regression` runs the whole
  `tests/` directory as a required check.
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
- **Source of truth**, split by milestone — row order is build order in both, never re-sort either:
  - `output/Loan Manager/mvp1.1/linear_import.csv` — **M1.1** (KCH-222…253), generated by `ops/gen_m11_csv.py`
  - `output/Loan Manager/mvp2/linear_import.csv` — M0 and M1a…M5
  - The four absorbed issues (KCH-99, 100, 105, 114) still live in the mvp2 CSV under the old M1a project name; they are re-milestoned in Linear, not moved between files
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

