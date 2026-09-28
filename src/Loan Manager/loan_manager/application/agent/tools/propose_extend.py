"""extend_loan / extend_overdue_batch: PROPOSE extending a loan's due date,
singly or for a whole overdue group in one report (KCH-243).

Both tools only ever write a MONTHLY report via `propose_common.submit` --
neither touches a loan directly (ARB D-6: no loan writes from the agent
boundary; the AST guard in `test_agent_import_guard.py` enforces this
statically by denying `extend_loan` (the mutating use case) and every other
loan-writing import from this package).

`ExtendLoanTool` follows the same undated-extend convention
`use_cases/loans/extend_loan.py` already uses for the FORM path: a loan
with no due_date needs an explicit `new_due_date` (post_giving=today,
post_due=new_due_date); a loan that already has one extends by `months`
from its existing due_date, and `new_due_date` must be omitted there.

`ExtendOverdueBatchTool` reuses `CalculateInterest` (Ponytail rung 2) over
every ACTIVE loan in the resolved group, then keeps only the ones
`StatusEngine.compute(...)` -- never the persisted `loans.status` column,
CLAUDE.md -- says are OVERDUE at `clock.today()`. An overdue loan with no
due_date cannot be extended by a batch (there is nowhere to ask the model
for N different `new_due_date`s), so it is EXCLUDED and counted in
`skipped_undated`, never silently applied. A loan already named by another
PENDING report is excluded too (`skipped_pending`) -- proposing a second
change over an unapproved first one is confusing, not incremental. Zero
remaining loans is NOTHING_TO_PROPOSE, and no report is generated at all.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta

from loan_manager.application.agent.tools.observations import ErrorCode, error, ok
from loan_manager.application.agent.tools.propose_common import (
    ProposalContext,
    line_to_record,
    pending_ref_ids,
    resolve_group,
    submit,
)
from loan_manager.application.dtos.calculation_dto import CalculationRequestDTO
from loan_manager.application.dtos.loan_dto import LoanFilterDTO
from loan_manager.application.dtos.report_dto import ReportRecordDTO
from loan_manager.application.interfaces.clock import Clock
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.application.use_cases.reports.calculate_interest import (
    CalculateInterest,
)
from loan_manager.application.use_cases.reports.generate_report import GenerateReport
from loan_manager.application.use_cases.reports.get_reports import GetPendingReports
from loan_manager.domain.services.interest_calculator import InterestCalculator
from loan_manager.domain.services.status_engine import StatusEngine
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    LoanStatus,
)

_NEXT_ACTION_PENDING = (
    "a report is now awaiting approval in Pending Approval; do NOT say the "
    "extension is done -- tell the user it is proposed and needs their approval"
)


class ExtendLoanTool:
    def __init__(
        self,
        get_all_loans: GetAllLoans,
        get_pending_reports: GetPendingReports,
        generate_report: GenerateReport,
        clock: Clock,
        ctx: ProposalContext,
    ) -> None:
        self._get_all_loans = get_all_loans
        self._get_pending_reports = get_pending_reports
        self._generate_report = generate_report
        self._clock = clock
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

        today = self._clock.today()

        if loan.due_date is None:
            if args.new_due_date is None:
                return error(
                    ErrorCode.UNDATED_LOAN,
                    "this loan has no due date to extend from",
                    "call extend_loan again with new_due_date set to the "
                    "agreed new due date (ISO YYYY-MM-DD, after today)",
                    ref_id=args.ref_id,
                )
            if args.new_due_date <= today:
                return error(
                    ErrorCode.NEW_DUE_DATE_INVALID,
                    "new_due_date must be strictly after today",
                    "ask the user for a new_due_date that is after today, "
                    "then retry",
                    ref_id=args.ref_id,
                )
            post_giving = today
            post_due = args.new_due_date
        else:
            if args.new_due_date is not None:
                return error(
                    ErrorCode.NEW_DUE_DATE_INVALID,
                    "this loan already has a due date; new_due_date must be omitted",
                    "call extend_loan again without new_due_date -- it "
                    "extends from the loan's existing due date by months",
                    ref_id=args.ref_id,
                )
            post_giving = loan.due_date
            post_due = post_giving + relativedelta(months=args.months)

        interest_amount = InterestCalculator.calculate(
            loan.amount, args.rate, args.months, ExtensionPeriodUnit.MONTHS
        )
        tds_amount = (
            InterestCalculator.calculate_tds(interest_amount)
            if args.tds_flag
            else Decimal("0.00")
        )
        chq_amount = InterestCalculator.calculate_chq(interest_amount, tds_amount)

        record = ReportRecordDTO(
            id=None,
            report_id="",
            reference_id=loan.reference_id,
            borrower_name=loan.borrower_name,
            depositor_name=loan.depositor_name,
            depositor_group=loan.depositor_group,
            amount=loan.amount,
            giving_date=loan.giving_date,
            due_date=loan.due_date,
            extension_period=args.months,
            extension_period_unit=ExtensionPeriodUnit.MONTHS,
            interest_rate=args.rate,
            commission_rate=Decimal("0"),
            tds_flag=args.tds_flag,
            interest_amount=interest_amount,
            commission_amount=Decimal("0.00"),
            tds_amount=tds_amount,
            chq_amount=chq_amount,
            post_extension_giving_date=post_giving,
            post_extension_due_date=post_due,
            paidoff_date=None,
            borrower_group=loan.borrower_group,
            due_period=loan.due_period,
        )

        report = submit(self._generate_report, CalculationMode.MONTHLY, [record], self._ctx)

        return ok(
            report_id=str(report.report_id),
            mode=report.report_mode.value,
            item_count=1,
            items=[
                {
                    "ref_id": args.ref_id,
                    "new_due_date": post_due.isoformat(),
                    "interest": interest_amount,
                }
            ],
            months=args.months,
            rate_percent=args.rate,
            total_amount=int(loan.amount),
            total_interest=interest_amount,
            next_action=_NEXT_ACTION_PENDING,
        )


class ExtendOverdueBatchTool:
    def __init__(
        self,
        get_all_loans: GetAllLoans,
        get_autocomplete: GetAutocompleteValues,
        build_resolver: BuildEntityResolver,
        get_pending_reports: GetPendingReports,
        calculate_interest: CalculateInterest,
        generate_report: GenerateReport,
        clock: Clock,
        ctx: ProposalContext,
    ) -> None:
        self._get_all_loans = get_all_loans
        self._get_autocomplete = get_autocomplete
        self._build_resolver = build_resolver
        self._get_pending_reports = get_pending_reports
        self._calculate_interest = calculate_interest
        self._generate_report = generate_report
        self._clock = clock
        self._ctx = ctx

    def execute(self, args: Any) -> dict[str, Any]:
        resolver = self._build_resolver.execute()
        group, err = resolve_group(
            args.borrower_group, "borrower_group", self._get_autocomplete, resolver
        )
        if err is not None:
            return err

        today = self._clock.today()
        calc_result = self._calculate_interest.execute(
            CalculationRequestDTO(
                mode=CalculationMode.MONTHLY,
                filters=LoanFilterDTO(borrower_group=group),
                interest_rate=args.rate,
                commission_rate=Decimal("0"),
                extension_period=args.months,
                extension_period_unit=ExtensionPeriodUnit.MONTHS,
                tds_flag=False,
            )
        )

        overdue_lines = [
            line
            for line in calc_result.lines
            if StatusEngine.compute(line.giving_date, line.due_date, today)
            == LoanStatus.OVERDUE
        ]
        skipped_undated = sorted(
            line.reference_id for line in overdue_lines if line.due_date is None
        )
        dated_overdue = [line for line in overdue_lines if line.due_date is not None]

        already_pending = pending_ref_ids(self._get_pending_reports)
        skipped_pending = sorted(
            line.reference_id for line in dated_overdue if line.reference_id in already_pending
        )
        eligible = [
            line for line in dated_overdue if line.reference_id not in already_pending
        ]

        if not eligible:
            return error(
                ErrorCode.NOTHING_TO_PROPOSE,
                "no overdue loan in this group is eligible to extend",
                "tell the user no proposal was created, and why: how many "
                "overdue loans have no due date and how many already have a "
                "pending proposal",
                skipped_undated=skipped_undated,
                skipped_pending=skipped_pending,
            )

        # depositor_group/borrower_group/due_period aren't on
        # CalculationLineDTO (see line_to_record's docstring) -- one extra
        # GetAllLoans call over the same group fills them in.
        by_ref = {
            loan.reference_id: loan
            for loan in self._get_all_loans.execute(LoanFilterDTO(borrower_group=group))
        }

        records = []
        items = []
        for line in eligible:
            loan = by_ref.get(line.reference_id)
            record = line_to_record(
                line,
                depositor_group=loan.depositor_group if loan else None,
                borrower_group=loan.borrower_group if loan else group,
                due_period=loan.due_period if loan else None,
            )
            records.append(record)
            items.append(
                {
                    "ref_id": line.reference_id,
                    "new_due_date": record.post_extension_due_date.isoformat(),
                    "interest": line.interest_amount,
                }
            )

        report = submit(self._generate_report, CalculationMode.MONTHLY, records, self._ctx)

        total_amount = sum(line.amount for line in eligible)
        total_interest = sum((line.interest_amount for line in eligible), Decimal("0"))

        return ok(
            report_id=str(report.report_id),
            mode=report.report_mode.value,
            item_count=len(records),
            items=items,
            months=args.months,
            rate_percent=args.rate,
            total_amount=total_amount,
            total_interest=total_interest,
            skipped_undated=skipped_undated,
            skipped_pending=skipped_pending,
            next_action=(
                f"a report covering {len(records)} loan(s) is now awaiting "
                "approval in Pending Approval; do NOT say it is done -- tell "
                "the user how many of the group's overdue loans were "
                "proposed and, if any were skipped, why (no due date, or "
                "already pending)"
            ),
        )
