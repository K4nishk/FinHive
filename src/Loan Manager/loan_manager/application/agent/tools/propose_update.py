"""update_loan: PROPOSE changing borrower_name, depositor_name and/or
amount on an existing loan (KCH-243).

borrower_group/depositor_group, if given, are MEMBERSHIP CHECKS ONLY (see
`args.UpdateLoan`'s docstring) -- resolved to a real group, then compared
against the loan's OWN current group; a mismatch is GROUP_MISMATCH, never a
move. The proposed UPDATE record is a full name/amount snapshot -- fields
not given keep the loan's current value (`ReportRecordDTO` requires
borrower_name/depositor_name/amount, there is no per-field null to send) --
so `approve_report.py`'s UPDATE branch can overwrite both unconditionally
without separately tracking which field actually changed.

No observation this tool returns ever contains a borrower/depositor NAME or
GROUP string (propose_common's module docstring, NPI rule) --
`changed_fields` names FIELDS ("amount"), never values.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from loan_manager.application.agent.tools.observations import ErrorCode, error, ok
from loan_manager.application.agent.tools.propose_common import (
    ProposalContext,
    pending_ref_ids,
    resolve_group,
    submit,
)
from loan_manager.application.dtos.report_dto import ReportRecordDTO
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.application.use_cases.reports.generate_report import GenerateReport
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports
from loan_manager.domain.value_objects.status import CalculationMode, ExtensionPeriodUnit

_GROUP_FIELDS = ("borrower_group", "depositor_group")


def _normalize_name(value: str) -> str:
    """Mirrors `LoanCreateDTO`/`LoanUpdateDTO.to_lowercase` exactly (strip +
    lower) -- review cycle 1, MAJOR-1: every OTHER write path normalises a
    name before it reaches the book; update_loan must apply the identical
    normalisation BEFORE comparing against the loan's current (already
    normalised) value, or a pure case change is proposed as a real change
    and, on approval, stores mixed case."""
    return value.strip().lower()


class UpdateLoanTool:
    def __init__(
        self,
        get_all_loans: GetAllLoans,
        get_autocomplete: GetAutocompleteValues,
        build_resolver: BuildEntityResolver,
        get_pending_reports: GetPendingReports,
        generate_report: GenerateReport,
        ctx: ProposalContext,
    ) -> None:
        self._get_all_loans = get_all_loans
        self._get_autocomplete = get_autocomplete
        self._build_resolver = build_resolver
        self._get_pending_reports = get_pending_reports
        self._generate_report = generate_report
        self._ctx = ctx

    def execute(self, args: Any) -> dict[str, Any]:
        loans = self._get_all_loans.execute()
        loan = next((row for row in loans if row.reference_id == args.ref_id), None)
        if loan is None:
            return error(
                ErrorCode.REF_ID_NOT_FOUND,
                f"no active loan found for reference_id {args.ref_id!r}",
                "confirm the reference_id with the user, or use query_loans/"
                "resolve_entity to find the correct one",
                ref_id=args.ref_id,
            )

        if args.ref_id in pending_ref_ids(self._get_pending_reports):
            return error(
                ErrorCode.ALREADY_PENDING,
                "a pending report already proposes a change to this loan",
                "tell the user this loan already has a proposal awaiting "
                "approval; do not propose a second one until it is resolved",
                ref_id=args.ref_id,
            )

        resolver = self._build_resolver.execute()
        for field_name in _GROUP_FIELDS:
            given = getattr(args, field_name)
            if given is None:
                continue
            resolved, err = resolve_group(
                given, field_name, self._get_autocomplete, resolver
            )
            if err is not None:
                return err
            current = (getattr(loan, field_name) or "").strip().lower()
            if resolved.strip().lower() != current:
                return error(
                    ErrorCode.GROUP_MISMATCH,
                    f"the {field_name} given does not match this loan's own {field_name}",
                    "the group is a membership check only, never something "
                    "update_loan changes; call resolve_entity or query_loans "
                    "to verify this loan's actual group, then retry with "
                    "the correct group or without one",
                    field=field_name,
                    ref_id=args.ref_id,
                )

        new_borrower_name = (
            _normalize_name(args.borrower_name)
            if args.borrower_name is not None
            else loan.borrower_name
        )
        new_depositor_name = (
            _normalize_name(args.depositor_name)
            if args.depositor_name is not None
            else loan.depositor_name
        )
        new_amount = args.amount if args.amount is not None else loan.amount

        changed_fields: list[str] = []
        if args.borrower_name is not None and new_borrower_name != loan.borrower_name:
            changed_fields.append("borrower_name")
        if args.depositor_name is not None and new_depositor_name != loan.depositor_name:
            changed_fields.append("depositor_name")
        if args.amount is not None and args.amount != loan.amount:
            changed_fields.append("amount")

        if not changed_fields:
            return error(
                ErrorCode.NOTHING_TO_PROPOSE,
                "every field given already matches the loan's current value",
                "tell the user nothing changed; no proposal was created",
                ref_id=args.ref_id,
            )

        record = ReportRecordDTO(
            id=None,
            report_id="",
            reference_id=loan.reference_id,
            borrower_name=new_borrower_name,
            depositor_name=new_depositor_name,
            depositor_group=loan.depositor_group,
            amount=new_amount,
            giving_date=loan.giving_date,
            due_date=loan.due_date,
            extension_period=0,
            extension_period_unit=ExtensionPeriodUnit.MONTHS,
            interest_rate=Decimal("0"),
            commission_rate=Decimal("0"),
            tds_flag=False,
            interest_amount=None,
            commission_amount=None,
            tds_amount=None,
            chq_amount=None,
            post_extension_giving_date=None,
            post_extension_due_date=None,
            paidoff_date=None,
            borrower_group=loan.borrower_group,
            due_period=loan.due_period,
        )

        report = submit(self._generate_report, CalculationMode.UPDATE, [record], self._ctx)

        return ok(
            report_id=str(report.report_id),
            mode=report.report_mode.value,
            item_count=1,
            ref_id=args.ref_id,
            changed_fields=changed_fields,
            next_action=(
                "a report is now awaiting approval in Pending Approval; do "
                "NOT say it is done -- tell the user which field(s) changed "
                "and that it needs their approval"
            ),
        )
