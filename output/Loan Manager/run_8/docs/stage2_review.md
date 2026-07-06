# Stage 2 Review — Architecture + System Design

**Stage**: 2 of 6
**Model**: claude-sonnet-4-6 (Sonnet — planning tier)
**Date**: 2026-06-30
**Status**: COMPLETE — AWAITING APPROVAL

---

## Outputs Produced

| Artifact | Path | Summary |
|---|---|---|
| Technical Design | docs/technical_design_document.md | Full architecture; layer breakdown; folder structure; tech stack |
| Data Model | docs/data_model.md | 6 tables; SQLAlchemy entity mapping; Pydantic DTO examples |
| Migration Strategy | docs/migration_strategy.md | Alembic setup; CSV-to-SQLite BL-24 migration; startup sequence |
| API Boundaries | docs/api_boundaries.md | All use case signatures; repository interfaces; DTO contracts |
| UI Wireframes | docs/ui_wireframes.md | All 5 tabs + all dialogs in text wireframes |
| ADR-001 | docs/architecture_decision_records/ | Clean Architecture rationale |
| ADR-002 | docs/architecture_decision_records/ | SQLite + SQLAlchemy decision |
| ADR-003 | docs/architecture_decision_records/ | QAbstractTableModel over QTableWidget |
| ADR-004 | docs/architecture_decision_records/ | Date picker bug fix approach |
| ADR-005 | docs/architecture_decision_records/ | Configurable theme + status colours |
| ADR-006 | docs/architecture_decision_records/ | Pydantic v2 for DTOs |

---

## Architecture Summary

**Pattern**: Clean Architecture + Lightweight DDD

```
Presentation (PySide6 tabs, dialogs, widgets, themes)
    ↓ calls use cases via DTOs
Application (use cases, event bus, UoW interface)
    ↓ calls domain services + repository interfaces
Domain (Loan, Report entities; StatusEngine; InterestCalculator; ReferenceIdService)
    ↑ implemented by
Infrastructure (SQLAlchemy repos, Alembic, CSV services, recovery, backup)
```

---

## Tech Stack Confirmed

| Component | Choice |
|---|---|
| Language | Python >= 3.10 |
| GUI | PySide6 |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Database | SQLite |
| Excel I/O | openpyxl |
| Testing | pytest + pytest-cov |

---

## Key Architectural Decisions

1. **QAbstractTableModel** (not QTableWidget) — required for 1500 rows + sort + filter performance (ADR-003)
2. **DateEditFixed** — uses `calendarPopup(True)` + `QTimer.singleShot` for Tab-triggered open; no `showCalendarWidget` call (ADR-004)
3. **ThemeManager** — all status colours from JSON config; fully configurable; no hardcoded hex in code (ADR-005)
4. **Repository interfaces in Domain layer** — Infrastructure implements them; Application depends only on abstractions
5. **Pydantic v2 DTOs** — lowercase normalisation + due_date derivation at DTO validation time (ADR-006)
6. **Startup sequence**: logging → recovery check → Alembic migrations → status recompute → launch UI
7. **Crash safety**: `RecoveryService` writes `approval_recovery.tmp` before any dual-write operation; checked on startup

---

## Folder Structure (definitive for Stage 3)

```
src/loan_manager/
  domain/           ← pure Python; no external dependencies
  application/      ← use cases; calls domain only
  infrastructure/   ← SQLAlchemy, Alembic, CSV, logging, recovery
  presentation/     ← PySide6 UI
  config.py
  container.py      ← ApplicationServiceLocator (DI wiring)
  main.py
data/               ← runtime data (created by app)
migrations/         ← Alembic root
tests/
  unit/domain/
  unit/application/
  integration/
  fixtures/
user_guides/
run_windows.bat
run_mac.sh
requirements.txt
```

---

## Data Model Summary (6 tables)

| Table | Purpose |
|---|---|
| loans | Active loan records (is_active=FALSE = hidden paidoff) |
| loan_meta | YYYY_MM → last_order counter |
| loan_history | Immutable paidoff loan archive |
| reports | Report header metadata |
| report_records | Per-loan line items in a report (snapshot data) |
| report_meta | YYYYMMDD → last_order for report IDs |

---

## Acceptance Checklist

- [x] Architecture diagram + layer breakdown documented
- [x] All 6 ADRs written with rationale
- [x] Full folder structure defined (definitive for Stage 3)
- [x] Data model: all 6 tables with columns, types, constraints, indexes
- [x] Migration strategy: Alembic setup + CSV-to-SQLite BL-24
- [x] API boundaries: all use case signatures + repository interfaces + DTO contracts
- [x] UI wireframes: all 5 tabs + 5 dialogs
- [x] Date picker bug fix approach documented (ADR-004)
- [x] Configurable theme approach documented (ADR-005)
- [x] Performance decision for 1500-row table documented (ADR-003)
- [x] Testing strategy: 85% target; unit vs integration split defined

---

## Stage 3 Handoff Notes (for Opus)

Stage 3 implements scaffold only. No business logic. No UI. Deliverables:

1. Full folder structure (`src/`, `tests/`, `migrations/`) created
2. `requirements.txt` with all pinned dependencies
3. SQLAlchemy models (`infrastructure/database/models.py`) — all 6 tables
4. Alembic setup + initial migration (creates all tables)
5. `DatabaseSession` + `UnitOfWork` implementation
6. Repository interfaces (stubs, not implementations)
7. `config.py` — data directory, DB path, log path
8. `logger.py` — rotating file handler to `./data/logs/app.log`
9. `RecoveryService` + `BackupService` stubs
10. `main.py` skeleton (startup sequence, no UI launched)
11. `run_windows.bat` + `run_mac.sh` (Python version check + venv + install + run)
12. `conftest.py` with in-memory SQLite fixture
13. Build verification: `python -m pytest tests/` passes (empty test stubs)

**Model for Stage 3**: claude-opus-4-6

---

## Open Questions for Stage 3+

- OQ-09: Theme preference (light/dark) still open. Stage 5 will deliver both; user picks after demo.
- `settings.json` location: `./data/settings.json` (not in src/). Needs to be created on first launch with defaults.

---

## Awaiting Response

Reply with:
- **PROCEED** — to advance to Stage 3 (Project Scaffold + Persistence) using claude-opus-4-6
- **PROCEED WITH MODIFICATIONS** — to request changes to Stage 2 artifacts
