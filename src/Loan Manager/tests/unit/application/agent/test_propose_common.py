"""Unit tests for propose_common.py (KCH-243): resolve_group.

`submit`, `line_to_record` and `pending_ref_ids` are already exercised
indirectly, thoroughly, by test_propose_extend.py/test_propose_create.py/
test_propose_update.py/test_propose_tools.py; this file is `resolve_group`'s
own dedicated coverage, added in review cycle 1 (MINOR-4, M9/M10).
"""
from __future__ import annotations

from loan_manager.application.agent.tools.propose_common import resolve_group
from loan_manager.application.use_cases.loans.build_entity_resolver import (
    BuildEntityResolver,
)
from loan_manager.application.use_cases.loans.get_autocomplete import (
    GetAutocompleteValues,
)

from .conftest import assert_no_npi_leak, make_loan, uow_factory_for


def _resolver_for(loans):
    get_autocomplete = GetAutocompleteValues(uow_factory_for(loans))
    return get_autocomplete, BuildEntityResolver(get_autocomplete).execute()


def test_group_exact_on_requested_field_accepted() -> None:
    loans = [make_loan(borrower_name="rakesh sharma", borrower_group="sharma group")]
    get_autocomplete, resolver = _resolver_for(loans)

    value, err = resolve_group("sharma group", "borrower_group", get_autocomplete, resolver)

    assert err is None
    assert value == "sharma group"


def test_group_exact_on_other_field_confirms() -> None:
    """Review cycle 1, MINOR-4 (M9, ORCHESTRATOR RULING): an EXACT match on
    a DIFFERENT field must not be accepted as if it were the field asked
    for -- "rakesh sharma" is an exact borrower_NAME, not a borrower_GROUP.
    Without this check, create_loan would mint a brand-new group literally
    named "rakesh sharma" the first time a user's typed borrower name
    happened to also be a perfect string match."""
    loans = [make_loan(borrower_name="rakesh sharma", borrower_group="sharma group")]
    get_autocomplete, resolver = _resolver_for(loans)

    value, err = resolve_group("rakesh sharma", "borrower_group", get_autocomplete, resolver)

    assert value is None
    assert err is not None
    assert err["error"]["code"] == "CONFIRM_REQUIRED"


def test_no_typed_or_candidate_text_in_any_error_observation() -> None:
    """Review cycle 1, MINOR-4 (M10, ORCHESTRATOR RULING): the NPI scan
    must cover EVERY error path resolve_group can return, not just
    create_loan's success observation -- CONFIRM_REQUIRED and
    UNRESOLVED_ENTITY must never echo the caller's typed text or a
    resolved candidate's value."""
    loans = [
        make_loan(borrower_name="rakesh sharma", borrower_group="sharma group"),
        make_loan(borrower_name="vikram sharma", borrower_group="sharma group"),
    ]
    get_autocomplete, resolver = _resolver_for(loans)
    forbidden = (
        "rakesh sharma", "vikram sharma", "sharma group", "sharma",
        "totally unknown group",
    )

    _, confirm_err = resolve_group("sharma", "borrower_group", get_autocomplete, resolver)
    assert confirm_err["error"]["code"] == "CONFIRM_REQUIRED"
    assert_no_npi_leak(confirm_err, *forbidden)

    _, unresolved_err = resolve_group(
        "totally unknown group", "borrower_group", get_autocomplete, resolver
    )
    assert unresolved_err["error"]["code"] == "UNRESOLVED_ENTITY"
    assert_no_npi_leak(unresolved_err, *forbidden)

    _, other_field_err = resolve_group(
        "rakesh sharma", "borrower_group", get_autocomplete, resolver
    )
    assert other_field_err["error"]["code"] == "CONFIRM_REQUIRED"
    assert_no_npi_leak(other_field_err, *forbidden)
