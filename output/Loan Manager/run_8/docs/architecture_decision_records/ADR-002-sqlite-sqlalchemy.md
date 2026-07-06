# ADR-002 — SQLite + SQLAlchemy over Pure CSV

**Date**: 2026-06-30
**Status**: Accepted

## Context
The previous prototype used flat CSV files for all storage. User confirmed (CHG-001) that SQLite is required for MVP1. The prompt.md Stage 2 tech stack also explicitly lists SQLite + SQLAlchemy + Alembic.

## Decision
SQLite as the primary data store accessed via SQLAlchemy 2.x ORM. Alembic for schema migrations. CSV import/export maintained for data portability and cross-platform git sharing.

## Rationale
- SQLite is bundled with Python; no extra installation for end users
- SQLAlchemy provides type-safe ORM, transaction management (UoW), and query building
- Alembic enables versioned schema evolution without manual SQL
- Repository pattern abstracts persistence; domain layer unchanged if storage changes

## Trade-offs
- Adds dependencies (SQLAlchemy, Alembic) to requirements.txt
- Slightly more complex than raw CSV writes
- `approval_recovery.tmp` crash-safety still needed because SQLite transactions don't cover the backup file write

## Migration Path
- On first MVP1 launch: detect existing CSV files, offer one-time migration via `csv_to_sqlite.py`
- CSV export always available for backward compatibility
