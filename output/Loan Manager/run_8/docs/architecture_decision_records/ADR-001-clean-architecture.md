# ADR-001 — Clean Architecture with Lightweight DDD

**Date**: 2026-06-30
**Status**: Accepted

## Context
Loan Manager MVP1 is a complex desktop application with interleaved business rules (status engine, interest calculator, approval workflow). A flat script structure would become unmaintainable quickly. The overhaul starts from scratch with no legacy code to preserve.

## Decision
Adopt Clean Architecture with four layers: Domain, Application, Infrastructure, Presentation. Apply lightweight DDD: aggregate roots (Loan, Report), value objects (ReferenceId, Money, LoanStatus), domain services (StatusEngine, InterestCalculator), and domain events.

## Rationale
- Domain layer is pure Python; unit-testable with no DB or UI dependencies
- Application layer use cases are independently testable
- Infrastructure swappable (CSV prototype → SQLite MVP1 → possible future DB)
- Clear boundaries prevent UI logic bleeding into business rules (issue in previous prototype)

## Consequences
- More files/folders than a flat script; acceptable for a project of this complexity
- Domain entities must be mapped to/from SQLAlchemy ORM models (thin mapper layer)
- Constructor injection used throughout; no DI container (simple enough for single-user app)
