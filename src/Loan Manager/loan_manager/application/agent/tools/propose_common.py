"""Shared plumbing for every PROPOSE tool (KCH-243).

`ProposalContext` carries the free-text `user_request` and optional
`turn_id` a PROPOSE tool call arrived with, so every report it writes is
attributable back to the turn that asked for it. `submit` is the ONE write
path every PROPOSE tool uses -- it always stamps `actor=ReportActor.AGENT`,
never left to a caller to forget (the same KCH-242 review finding that made
`ReportDTO.actor` required in the first place). `line_to_record` and
`resolve_group` are the two pieces every propose_*.py module needs and none
should reimplement.

NPI rule (CLAUDE.md; orchestrator ruling on this issue): no observation any
PROPOSE tool returns may contain a borrower/depositor NAME or GROUP string
-- the novel-name-at-ingress tokeniser (KCH-238/239) does not exist on this
branch yet, so `resolve_group` below never echoes the free text it was
given, nor a candidate's resolved value, back into an `error()` payload;
only the field name and a candidate count leave this boundary. The actual
"did you mean X?" conversation happens through `resolve_entity` (KCH-237,
a READ tool -- explicitly still allowed to leak until KCH-238 lands), which
next_action always points the caller back to.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loan_manager.application.agent.tools.observations import ErrorCode, error
from loan_manager.application.dtos.calculation_dto import CalculationLineDTO
from loan_manager.application.dtos.report_dto import (
    GenerateReportDTO,
    ReportDTO,
    ReportRecordDTO,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.reports.generate_report import GenerateReport
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports
from loan_manager.domain.services.entity_resolver import EntityResolver
from loan_manager.domain.value_objects.status import CalculationMode, ReportActor

_MAX_CONFIRM_CANDIDATES = 5

_DEFAULT_UNRESOLVED_NEXT_ACTION = (
    "call resolve_entity with the user's text for this group, then retry "
    "with the exact value it returns"
)
_DEFAULT_CONFIRM_NEXT_ACTION = (
    "not an exact match; call resolve_entity with the same text to see "
    "candidates, ask the user to confirm the exact one, then retry this "
    "tool with resolve_entity's exact value"
)


@dataclass(frozen=True)
class ProposalContext:
    """Who/why behind one PROPOSE tool call this agent turn.

    `user_request` is the free text the user typed; `turn_id` ties multiple
    tool calls in one agent turn together. Both are plain attributes here,
    not validated -- validating free text is not this module's job, and
    both are already `Optional` on `ReportDTO`/`GenerateReportDTO`.
    """

    user_request: str
    turn_id: str | None = None


def submit(
    generate_report: GenerateReport,
    mode: CalculationMode,
    records: list[ReportRecordDTO],
    ctx: ProposalContext,
) -> ReportDTO:
    """The ONE write path every PROPOSE tool uses -- see module docstring."""
    dto = GenerateReportDTO(
        mode=mode,
        records=records,
        actor=ReportActor.AGENT,
        user_request=ctx.user_request,
        turn_id=ctx.turn_id,
    )
    return generate_report.execute(dto)


def line_to_record(
    line: CalculationLineDTO,
    *,
    depositor_group: str | None,
    borrower_group: str | None = None,
    due_period: int | None = None,
) -> ReportRecordDTO:
    """A `CalculateInterest` `CalculationLineDTO` -> the `ReportRecordDTO`
    `GenerateReport` expects. `CalculationLineDTO` carries no
    depositor_group (`calculator_tab.py` hardcodes None for the FORM path,
    for the same reason -- KCH-242 never added the field there); callers
    here pass it through explicitly from the underlying `LoanDTO` instead of
    losing it the way the FORM path still does (tracked as DEBT in the
    accepted plan, not fixed by this module)."""
    return ReportRecordDTO(
        id=None,
        report_id="",
        reference_id=line.reference_id,
        borrower_name=line.borrower_name,
        depositor_name=line.depositor_name,
        depositor_group=depositor_group,
        amount=line.amount,
        giving_date=line.giving_date,
        due_date=line.due_date,
        extension_period=line.extension_period,
        extension_period_unit=line.extension_period_unit,
        interest_rate=line.interest_rate,
        commission_rate=line.commission_rate,
        tds_flag=line.tds_flag,
        interest_amount=line.interest_amount,
        commission_amount=line.commission_amount,
        tds_amount=line.tds_amount,
        chq_amount=line.chq_amount,
        post_extension_giving_date=line.post_extension_giving_date,
        post_extension_due_date=line.post_extension_due_date,
        paidoff_date=None,
        borrower_group=borrower_group,
        due_period=due_period,
    )


def pending_ref_ids(get_pending_reports: GetPendingReports) -> set[str]:
    """Every reference_id already named by a PENDING report, across every
    mode -- a ref_id is "already pending" the moment ANY unapproved report
    touches it. CREATE rows contribute nothing (their reference_id is None
    until approval mints one)."""
    pending = get_pending_reports.execute()
    return {
        rec.reference_id
        for report in pending
        for rec in report.records
        if rec.reference_id is not None
    }


def resolve_group(
    text: str,
    field: str,
    get_autocomplete: GetAutocompleteValues,
    resolver: EntityResolver,
    *,
    unresolved_next_action: str = _DEFAULT_UNRESOLVED_NEXT_ACTION,
) -> tuple[str | None, dict[str, Any] | None]:
    """Resolve `text` to an exact, EXISTING value of `field` (a *_group
    field). Returns `(value, None)` on success or `(None, error_observation)`
    on failure -- the caller returns the error observation directly.

    (a) Exact normalised membership in `field`'s own known-value set first
    -- covers the common case where `text` is ALREADY the canonical value
    (e.g. resolve_entity already ran this turn, or the model echoed a prior
    tool's exact output), without going through fuzzy scoring at all.
    (b) Otherwise `EntityResolver.resolve(text)`: an EXACT match on THIS
    field is accepted; `no_match` is UNRESOLVED_ENTITY; anything else
    (resolved-but-not-exact, ambiguous, or an exact match on a DIFFERENT
    field) is CONFIRM_REQUIRED -- the caller must ask before acting.

    Review cycle 1, MINOR (ORCHESTRATOR RULING): the value returned is
    always the STORED (canonical) value, never the caller's raw `text` --
    "Sharma Group" typed against a book that stores "sharma group" must
    resolve to "sharma group", not echo the caller's casing into the
    proposal record (and, downstream, into KCH-245's display of it).

    Neither `text` nor any candidate value is ever put in the returned
    observation -- see module docstring (NPI rule).
    """
    known = {v.strip().lower(): v for v in get_autocomplete.execute(field)}
    normalized_text = text.strip().lower()
    if normalized_text in known:
        return known[normalized_text], None

    resolution = resolver.resolve(text)
    if resolution.exact and resolution.top is not None and resolution.top.field == field:
        return resolution.top.value, None

    if resolution.status == "no_match":
        return None, error(
            ErrorCode.UNRESOLVED_ENTITY,
            f"the {field} given does not match any known {field}",
            unresolved_next_action,
            field=field,
        )

    return None, error(
        ErrorCode.CONFIRM_REQUIRED,
        f"the {field} given is not an exact match for a known {field}",
        _DEFAULT_CONFIRM_NEXT_ACTION,
        field=field,
        candidate_count=min(len(resolution.candidates), _MAX_CONFIRM_CANDIDATES),
    )
