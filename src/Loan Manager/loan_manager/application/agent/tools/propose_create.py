"""create_loan: PROPOSE a brand-new loan (KCH-243).

CREATE row convention (`Report.__post_init__`, KCH-242 plan): there is no
existing loan yet, so `reference_id`/`giving_date`/`due_date` all stay None
until approval mints one; the proposed values live in
`post_extension_giving_date` (= `clock.today()`, DEBT [REVIEW REQUIRED] --
see the accepted plan) and `post_extension_due_date` (derived from
`due_period` the same way `LoanCreateDTO.derive_due_date` would, or None).
`extension_period=0`/rates=0/derived amounts=None are placeholders -- a
brand-new loan has no interest history yet.

Both `borrower_group` and an explicit `depositor_group` must already be a
REAL, existing group -- `resolve_group` never invents one. A group that
does not resolve is UNRESOLVED_ENTITY: this tool routes the user to the New
Loan form rather than silently minting a new group string, so a typo never
becomes a permanent new group in the book ([REVIEW REQUIRED], accepted
plan). No observation this tool returns ever contains the borrower/
depositor NAME or GROUP text the caller gave (see propose_common's module
docstring, NPI rule) -- only field names, counts and the report/ref
metadata leave this module.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta

from loan_manager.application.agent.tools.observations import ok
from loan_manager.application.agent.tools.propose_common import (
    ProposalContext,
    resolve_group,
    submit,
)
from loan_manager.application.dtos.report_dto import ReportRecordDTO
from loan_manager.application.interfaces.clock import Clock
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.reports.generate_report import GenerateReport
from loan_manager.domain.value_objects.status import CalculationMode, ExtensionPeriodUnit

_UNRESOLVED_GROUP_NEXT_ACTION = (
    "this group does not exist; new groups are created via the New Loan "
    "form, not through chat -- tell the user to use that form, or give an "
    "existing group instead"
)


class CreateLoanTool:
    def __init__(
        self,
        get_autocomplete: GetAutocompleteValues,
        build_resolver: BuildEntityResolver,
        generate_report: GenerateReport,
        clock: Clock,
        ctx: ProposalContext,
    ) -> None:
        self._get_autocomplete = get_autocomplete
        self._build_resolver = build_resolver
        self._generate_report = generate_report
        self._clock = clock
        self._ctx = ctx

    def execute(self, args: Any) -> dict[str, Any]:
        resolver = self._build_resolver.execute()

        borrower_group, err = resolve_group(
            args.borrower_group,
            "borrower_group",
            self._get_autocomplete,
            resolver,
            unresolved_next_action=_UNRESOLVED_GROUP_NEXT_ACTION,
        )
        if err is not None:
            return err

        depositor_group = None
        if args.depositor_group is not None:
            depositor_group, err = resolve_group(
                args.depositor_group,
                "depositor_group",
                self._get_autocomplete,
                resolver,
                unresolved_next_action=_UNRESOLVED_GROUP_NEXT_ACTION,
            )
            if err is not None:
                return err

        today = self._clock.today()
        post_due = today + relativedelta(months=args.due_period) if args.due_period else None

        record = ReportRecordDTO(
            id=None,
            report_id="",
            reference_id=None,
            borrower_name=args.borrower_name,
            depositor_name=args.depositor_name,
            depositor_group=depositor_group,
            amount=args.amount,
            giving_date=None,
            due_date=None,
            extension_period=0,
            extension_period_unit=ExtensionPeriodUnit.MONTHS,
            interest_rate=Decimal("0"),
            commission_rate=Decimal("0"),
            tds_flag=False,
            interest_amount=None,
            commission_amount=None,
            tds_amount=None,
            chq_amount=None,
            post_extension_giving_date=today,
            post_extension_due_date=post_due,
            paidoff_date=None,
            borrower_group=borrower_group,
            due_period=args.due_period,
        )

        report = submit(self._generate_report, CalculationMode.CREATE, [record], self._ctx)

        return ok(
            report_id=str(report.report_id),
            mode=report.report_mode.value,
            item_count=1,
            due_period=args.due_period,
            amount=args.amount,
            next_action=(
                "a report is now awaiting approval in Pending Approval; do "
                "NOT say the loan exists yet -- tell the user it is "
                "proposed and needs their approval before the loan is created"
            ),
        )
