# FinHive

## Project

- **What**: One-Stop shop for custom finance solutions
- **Active product**: Loan Manager MVP1 — single-user desktop loan management app.
- **Branch**: `development`
- **Input**: `/input/REQUIREMENTS.md` (authoritative business spec), `/input/prompt*.md` (build/fix prompts)
- **Output**: `/output/YYYY/MM/DD/stdout_HHMMSS.md` (design artifacts, ARD, WIKI, FINAL_REVIEW)
- **Source**: `/src/Loan Manager/loan_manager/` (Python package)
- **WIKI**: `/output/Loan Manager/run_8/WIKI.md` — full repository knowledge base with file index, data flows, and business rules. Read it before making architectural decisions.
- **ARD**: `/output/Loan Manager/run_8/ARD.md` — architecture reference for onboarding context.
- **Agent contract**: `/docs/AGENT_CONTRACT.md` — the rules any agent (orchestrator-driven or interactive) follows when implementing a `KCH-*` issue: branch, implement, CodeRabbit gate, bounded fix cycles, escalation.

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
tests, run the CodeRabbit CLI gate, fix blocking findings for at most two cycles, then
escalate to a new Linear issue carrying the finding, each attempted fix, why it failed,
and a suggested direction. An agent never merges — it opens a PR (or, on escalation,
a draft PR) for a human to review.

## Development Workflow

1. **Explore** → Read WIKI, ARD, and relevant source before changing anything.
2. **Plan** → For non-trivial changes, use `/plan` or enter plan mode. Get approval.
3. **Implement** → Small, atomic changes. One concern per commit.
4. **Test** → Run full suite. Add regression test for every fix.
5. **Review** → Run `/code-review` before requesting human review.
6. **Stage-gate** → If working within a staged run, STOP after each stage. Await approval.
