# ADR-006 — Pydantic v2 for DTOs and Validation

**Date**: 2026-06-30
**Status**: Accepted

## Context
Data flowing between layers (Presentation → Application → Infrastructure) needs validation and normalisation. Key rules: lowercase string fields, non-negative amounts, date derivation (due_date from due_period), enum validation.

## Decision
Use Pydantic v2 for all DTOs in the Application layer.

## Rationale
- `@field_validator` handles lowercase normalisation at DTO creation (not scattered in UI code)
- `@model_validator` handles `due_date = giving_date + due_period` derivation
- `Field(ge=0)` enforces non-negative amount constraint
- Pydantic v2 is faster than v1; `model_validate()` from dict/ORM row
- Clear validation error messages surfaceable to UI status bar

## Example Validators
```python
@field_validator('borrower_name', 'borrower_group', 'depositor_name', 'depositor_group', mode='before')
@classmethod
def to_lowercase(cls, v):
    return v.lower().strip() if isinstance(v, str) else v

@model_validator(mode='after')
def derive_due_date(self):
    if self.due_period and not self.due_date:
        self.due_date = self.giving_date + relativedelta(months=self.due_period)
    return self
```

## Consequences
- Adds `pydantic>=2.0` and `python-dateutil` to requirements
- Domain entities are NOT Pydantic models (domain stays pure Python dataclasses)
- DTOs are Pydantic; conversion to/from domain entities via thin mapper functions
