---
name: loan-manager-conventions
description: How to write code that fits the FinHive Loan Manager codebase, and where things live. Load before writing, moving or reviewing code under src/Loan Manager (placing a module in the right layer, adding a use case, repository, DTO, entity or value object, wiring the Container), before touching presentation/ (tables, column filters, date pickers, themes and colours), when choosing a library or checking a version constraint, when looking for a file, doc or artefact in the repo, and before creating or importing a FinHive Linear issue.
---

# Loan Manager conventions

Reference material moved out of `CLAUDE.md` so it does not ride along on every task and
every subagent. Everything here is as binding as `CLAUDE.md`; it is just not needed on
every turn. `CLAUDE.md` keeps the always-on rules: business rules, data protection,
testing, prohibitions.

---

## Where things are

```
/input/*                          Requirements and prompt specs (read-only reference)
/output/<Title>/<run_order>/*     Design artefacts per run (ARD, WIKI, FINAL_REVIEW, docs/)
/src/<Title>/*                    Source code
/.claude/agents/*                 Subagent definitions (markdown + YAML frontmatter)
/.claude/skills/*                 Skill definitions (markdown)
/.claude/tools/*                  Reference snippets (do not modify)
```

- **Input**: `/input/REQUIREMENTS.md` (authoritative business spec — only its storage
  claims are superseded; `src/` is the truth there), `/input/prompt*.md` (build/fix
  prompts)
- **Output**: `/output/YYYY/MM/DD/stdout_HHMMSS.md` (design artefacts, ARD, WIKI,
  FINAL_REVIEW)
- **WIKI**: `/output/Loan Manager/run_8/WIKI.md` — file index, data flows, business
  rules. Read it before an architectural decision.
- **ARD**: `/output/Loan Manager/run_8/ARD.md` — architecture reference.
- **Filter design**: `src/Loan Manager/docs/filter_architecture.md`

### Loan Manager source (`/src/Loan Manager/loan_manager/`)

```
main.py              Entry point: logging → recovery check → DB init → key ring → status recompute → UI launch
config.py            All path constants: DATA_DIR, DB_PATH, LOG_FILE, RECOVERY_FILE, etc.
container.py         DI wiring: Container class
domain/              Layer 1: entities, value_objects, services, repositories (interfaces), events, errors
application/         Layer 2: use_cases/, dtos/, interfaces/unit_of_work.py, event_bus.py
infrastructure/      Layer 3: database/ (ORM models, session, UoW, encrypted types), repositories/,
                              csv/ (import/export), recovery/, logging/, migrations/, security/
presentation/        Layer 4: main_window, tabs/, dialogs/, widgets/, view_models/, themes/, errors
```

---

## Language and framework constraints

- Python >= 3.10; target 3.10–3.13. (Local venvs may be 3.14; `asyncpg` has no
  guaranteed cp314 wheel, so Postgres tooling uses a 3.13 venv.)
- PySide6 >= 6.8.0 for the GUI.
- SQLAlchemy >= 2.0 ORM, **sync**. SQLite through MVP1; Postgres from MVP1.1
  (ARB D-1a, D-16). No raw SQL outside `migrations/`.
- Alembic for schema migrations.
- Pydantic >= 2.5 for all DTOs: `BaseModel`, field validators, model validators.
- `python-dateutil` (`relativedelta`) for date arithmetic. No manual month maths.
- `openpyxl` for XLSX. No other Excel library.
- `Decimal`, never `float`, for money. `ROUND_HALF_UP`, quantised to two places.
- Dates stored and compared as `datetime.date`, ISO 8601.
- Enums as `str, Enum` for serialisation (see `domain/value_objects/status.py`).

---

## Layers in detail

`Presentation → Application → Domain ← Infrastructure`. Dependency flows inward only.

- **Domain** (`domain/`): pure Python. No imports from `infrastructure/`,
  `presentation/`, PySide6 or SQLAlchemy. Entities, value objects, domain services,
  repository interfaces, domain events, domain errors.
- **Application** (`application/`): use cases and DTOs only. Imports `domain/` only. No
  DB queries, no UI code.
- **Infrastructure** (`infrastructure/`): implements the domain repository interfaces.
  Imports `domain/` and SQLAlchemy. No PySide6. Translates storage failures into domain
  errors (e.g. a `DecryptionError` becomes `DataUnreadableError`) so presentation never
  imports the crypto layer.
- **Presentation** (`presentation/`): PySide6 UI. Calls use cases. No business logic, no
  direct repository access.

If logic needs an import that crosses a boundary in the wrong direction, restructure
instead of importing. Note that `lint-imports` covers the `finhive` package only, not
`loan_manager`: for this app the layering is enforced by review, not by CI.

**Dependency injection**: constructor injection via `Container` (`container.py`). No DI
framework, and no service locator beyond `Container`.

---

## Presentation conventions

- **Tables**: `QAbstractTableModel` + `QSortFilterProxyModel` for every data table. Never
  `QTableWidget`. Sorting happens in the proxy's `lessThan` over decrypted display values,
  which is why encrypting columns at rest did not break sorting.
- **Filter state**: `ColumnFilterWidget` owns a single-source-of-truth `FilterState`. The
  popup is a pure view and holds no permanent state. Read
  `src/Loan Manager/docs/filter_architecture.md` before touching filter code.
- **Filter checkpoints** (sample data): `bg3` → 2 records (b3, b4); `dg3` → 4 records
  (b6, b7, b8, b9). Exact match, not substring: `bg1` must not match `bg13`.
- **Date picker**: `setCalendarPopup(True)` + `QTimer.singleShot(0, showPopup)`. Never
  `showCalendarWidget()` — it does not exist in PySide6.
- **Theme**: every colour comes from `ThemeManager` + `dark_config.json` /
  `light_config.json`. Never hardcode hex in UI code.
- **Storage errors**: wrap reads in `presentation.errors.surfacing_storage_errors`, never
  `except Exception: pass`. An unreadable loan book and an empty one must not look alike.

---

## Coding conventions

- PEP 8.
- Modules: lowercase with underscores (`interest_calculator.py`). Agent and skill files:
  lowercase with hyphens (`python-reviewer.md`).
- `from __future__ import annotations` at the top of every module.
- `Optional[X]` for dataclass fields, `X | None` in function signatures.
- Dataclasses for domain entities, Pydantic `BaseModel` for DTOs. Do not mix.
- Frozen dataclasses for value objects (`@dataclass(frozen=True)`).
- Use cases are classes with an `execute()` method, one per file, each with a test file.
- Repositories return domain entities, never ORM models; map inside the repository.
- Normalise `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group` to
  lowercase at write time.
- Amounts are non-negative whole INR rupees: `Money` value object or `Field(ge=0)`.
  Negative derived amounts are rejected by design.
- Log with `get_logger(__name__)` from `infrastructure/logging/logger.py`. No `print()`
  in production code.

---

## Linear (FinHive specifics)

Invoke the `write-linear-issue` skill first; it carries the team-wide conventions. Team
`KCH` is shared with other products (Aegis, AssetAuditor).

- **Product label**: `product:finhive` on every issue, always first.
- **Projects**: `FinHive <milestone> · <name>`, e.g. `FinHive M1a · Local Setup, Login &
  Encryption`.
- **Workstream labels**: `ops`, `ci-cd`, `data`, `security`, `backend`, `business-logic`,
  `frontend`, `agent`, `auth`, `testing`, `observability`, `docs`.
- **Source of truth**, split by milestone. Row order is build order in both; never
  re-sort either.
  - `output/Loan Manager/mvp1.1/linear_import.csv` — **M1.1** (KCH-222…253), generated
    by `ops/gen_m11_csv.py`. Edit the generator, not the CSV.
  - `output/Loan Manager/mvp2/linear_import.csv` — M0 and M1a…M5.
  - KCH-99, 100, 105 and 114 still live in the mvp2 CSV under the old M1a project name.
    They were re-milestoned in Linear, not moved between files.
  - Issues created directly in Linear (e.g. KCH-254) and descriptions rewritten there
    (e.g. KCH-230) are not in the CSVs. The seeder is idempotent by title, so re-seeding
    does not duplicate them.
- **Import**: `python3 ops/seed_linear.py` (dry run), then `--apply`.
