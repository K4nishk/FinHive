"""Pydantic argument models for every Ask FinHive agent tool (KCH-235).

Rung 5 (pydantic already a dependency: `loan_manager/application/dtos/*` and
root `finhive` both use it — see CLAUDE.md Ponytail). One model per tool,
each subclassing `ToolArgs` so every model shares the same hard rules:

- `extra="forbid"` — a model that invents an argument (e.g. `giving_date`,
  which CLAUDE.md bans from every interest/time calculation) is rejected at
  the schema boundary, not silently accepted.
- `frozen=True` — args are read-only once parsed; nothing downstream can
  mutate what the model asked for.
- `str_strip_whitespace=True` — LLM output routinely pads free text.

Money and rates are never `float` (CLAUDE.md): `PercentRate` and the rupee
types use `Decimal`/`int`. Rates are PERCENTAGES (12 means 12%, never 0.12),
quantised to 2 decimal places (`decimal_places=2`) so a many-digit float
(e.g. 12.345, which `json.loads(..., parse_float=Decimal)` in
`tool_registry.parse_args` preserves exactly instead of rounding through
`float`) is rejected rather than silently truncated.

Whole-count integer fields (`Months`, `RupeesWhole`, the portfolio `limit`)
use `Field(strict=True)`: pydantic's lax `int` mode accepts `True` (bool is
an int subclass), the string `"3"`, and `3.0`, any of which would otherwise
smuggle the wrong type past an LLM's loose JSON past this boundary.

No field anywhere carries a date — `giving_date` never enters interest or
time-period arithmetic, and the agent boundary should not be able to name a
date field at all.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    WithJsonSchema,
    model_validator,
)

from loan_manager.domain.value_objects.reference_id import REFERENCE_ID_PATTERN
from loan_manager.domain.value_objects.status import LoanStatus


class ToolArgs(BaseModel):
    """Base for every agent tool's argument model. See module docstring."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


def _reject_fraction(v: Decimal) -> Decimal:
    """Catches the classic 12% -> 0.12 mistake before it reaches arithmetic."""
    if 0 < v < 1:
        raise ValueError("rate is a percentage, not a fraction - did you mean 12?")
    return v


def _default_when_null(default: object):
    """BeforeValidator factory: an explicit JSON `null` for an optional-with-
    default field falls back to that default instead of failing type
    validation (a field that is merely ABSENT already gets the default;
    this covers a model that sends the key with a null value)."""

    def _coalesce(v: object) -> object:
        return default if v is None else v

    return _coalesce


# ── shared field types ───────────────────────────────────────────────────────

RefId = Annotated[
    str,
    Field(
        pattern=REFERENCE_ID_PATTERN.pattern,
        description="Loan reference id, format YYYY_MM_NNN, e.g. 2026_03_004",
    ),
]

PercentRate = Annotated[
    Decimal,
    Field(ge=0, le=100, decimal_places=2),
    AfterValidator(_reject_fraction),
    WithJsonSchema(
        {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": (
                "Annual interest rate as a PERCENTAGE: 12 means 12%. "
                "Never a fraction (not 0.12)."
            ),
        }
    ),
]

Months = Annotated[
    int, Field(strict=True, ge=1, le=120, description="Whole calendar months (integer)")
]

RupeesWhole = Annotated[
    int,
    Field(
        strict=True,
        ge=1,
        le=10**10,
        description="Whole INR rupees, e.g. 150000 for 1.5 lakh; no paise, no lakh/crore units",
    ),
]

# Canonical slug returned by resolve_entity. Slug itself does not validate
# that the value NAMES AN EXISTING borrower/group — KCH-237 adds that check
# for query_loans (READ), and KCH-243 owns the equivalent check for the
# PROPOSE tools (extend_loan, update_loan, extend_overdue_batch). Until then
# this type only enforces shape (non-empty, bounded length).
Slug = Annotated[
    str,
    Field(
        min_length=1,
        max_length=120,
        description="Canonical value returned by resolve_entity, never free text",
    ),
]

_STATUS_VALUES = tuple(sorted(s.value.lower() for s in LoanStatus))
StatusLiteral = Literal[_STATUS_VALUES]  # type: ignore[valid-type]


# ── READ tools ───────────────────────────────────────────────────────────────

class GetCurrentContext(ToolArgs):
    """No arguments: today's date, quarter and financial-year boundaries."""


class ResolveEntity(ToolArgs):
    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=200,
            description="Free text naming a borrower or group, e.g. as the user typed it",
        ),
    ]


class QueryLoans(ToolArgs):
    status: StatusLiteral
    borrower_group: Slug | None = None
    depositor_group: Slug | None = None


class GetPortfolioSummary(ToolArgs):
    limit: Annotated[
        int,
        Field(strict=True, ge=1, le=50, description="number of borrowers"),
        BeforeValidator(_default_when_null(10)),
    ] = 10


class CalculateInterestArgs(ToolArgs):
    ref_id: RefId
    rate: PercentRate
    months: Months


class FormatInr(ToolArgs):
    amount: Annotated[
        Decimal,
        Field(ge=0, le=Decimal("1000000000000"), decimal_places=2),
        WithJsonSchema(
            {
                "type": "number",
                "minimum": 0,
                "maximum": 1e12,
                "description": "INR rupees, paise allowed",
            }
        ),
    ]


# ── PROPOSE tools ────────────────────────────────────────────────────────────

class ExtendLoan(ToolArgs):
    ref_id: RefId
    months: Months
    rate: PercentRate
    tds_flag: Annotated[
        bool,
        Field(description="Whether TDS applies to this extension"),
        BeforeValidator(_default_when_null(False)),
    ] = False


class CreateLoan(ToolArgs):
    borrower_name: Annotated[
        str, Field(min_length=1, max_length=200, description="Borrower's full name")
    ]
    # DEBT [REVIEW REQUIRED]: borrower_group/depositor_group are Slug, i.e. a
    # value resolve_entity already returned for an EXISTING group. create_loan
    # has no way to name a brand-new group that has never been seen before —
    # unclear whether that is intended (every group must pre-exist) or a gap.
    # Not this issue's call; flagging for KCH-242/243.
    borrower_group: Slug
    depositor_name: Annotated[
        str, Field(min_length=1, max_length=200, description="Depositor's full name")
    ]
    depositor_group: Slug | None = None
    amount: RupeesWhole
    due_period: Months | None = None


NewBorrowerName = Annotated[
    str, Field(min_length=1, max_length=200, description="New borrower name")
]
NewDepositorName = Annotated[
    str, Field(min_length=1, max_length=200, description="New depositor name")
]


class UpdateLoan(ToolArgs):
    ref_id: RefId
    borrower_name: NewBorrowerName | None = None
    borrower_group: Slug | None = None
    depositor_name: NewDepositorName | None = None
    depositor_group: Slug | None = None
    amount: RupeesWhole | None = None

    @model_validator(mode="after")
    def _require_at_least_one_field(self) -> UpdateLoan:
        updatable = (
            "borrower_name",
            "borrower_group",
            "depositor_name",
            "depositor_group",
            "amount",
        )
        if not any(getattr(self, field) is not None for field in updatable):
            raise ValueError("update_loan requires at least one field to update")
        return self


class ExtendOverdueBatch(ToolArgs):
    borrower_group: Slug
    months: Months
    rate: PercentRate
